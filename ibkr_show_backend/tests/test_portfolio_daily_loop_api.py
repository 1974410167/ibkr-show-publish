from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.deps import get_agent_task_repository, get_portfolio_daily_loop_service, require_authenticated_session
from app.domains.portfolio_manager.daily_loop.schemas import PortfolioDailyLoopRun
from app.main import app


def _run(run_id: str = "portfolio_daily_loop:2026-07-15:manual:test", task_id: str | None = None) -> dict:
    return {
        "id": run_id,
        "run_date": "2026-07-15",
        "run_type": "manual",
        "status": "success",
        "task_id": task_id,
        "started_at": "2026-07-15T00:00:00+00:00",
        "completed_at": "2026-07-15T00:00:01+00:00",
        "duration_ms": 1000,
        "options": {
            "sync_holdings": True,
            "run_watchtower": True,
            "run_auto_decision": True,
            "generate_portfolio_report": True,
            "run_evaluation": False,
            "generate_improvement_report": False,
            "dry_run_auto_decision": False,
            "max_auto_decisions": 5,
            "force_refresh_auto_decision": False,
            "evaluation_horizons": ["1d", "5d", "20d"],
            "evaluation_lookback_days": 180,
            "improvement_horizons": ["5d", "20d", "60d"],
            "improvement_lookback_days": 180,
            "improvement_min_sample_size": 5,
        },
        "steps": [],
        "linked_run_ids": {},
        "summary": {},
        "data_limitations": [],
        "error_code": None,
        "error_message": None,
        "created_at": "2026-07-15T00:00:00+00:00",
        "updated_at": "2026-07-15T00:00:01+00:00",
    }


class FakeDailyLoopService:
    def __init__(self) -> None:
        self.shell = _run("portfolio_daily_loop:shell")

    def create_running_run(self, **_kwargs):
        return PortfolioDailyLoopRun.model_validate(self.shell)

    def attach_task(self, run_id: str, task_id: str):
        self.shell["task_id"] = task_id
        return PortfolioDailyLoopRun.model_validate(self.shell)

    def run_daily_loop(self, **kwargs):
        return PortfolioDailyLoopRun.model_validate(_run(kwargs.get("run_id") or "portfolio_daily_loop:sync", kwargs.get("task_id")))

    def list_runs(self, **_kwargs):
        return [_run()]

    def get_latest_run(self):
        return _run("portfolio_daily_loop:latest")

    def get_run(self, run_id: str):
        return _run(run_id)


class FakeTaskRepo:
    def __init__(self) -> None:
        self.task = None

    def create_task(self, **kwargs):
        self.task = {
            "id": "task:1",
            "agent": kwargs["agent"],
            "task_type": kwargs["task_type"],
            "label": kwargs["label"],
            "status": "queued",
            "payload": kwargs["payload"],
            "result_id": None,
            "error_code": None,
            "error_message": None,
            "created_at": "2026-07-15T00:00:00+00:00",
            "started_at": None,
            "completed_at": None,
            "updated_at": "2026-07-15T00:00:00+00:00",
            "updated_seq": 0,
            "graph_snapshot": None,
            "graph_progress_summary": {},
            "graph_events": [],
        }
        return self.task

    def init_graph_progress(self, *_args, **_kwargs):
        return self.task

    def mark_running(self, task_id):
        self.task["status"] = "running"
        return self.task

    def mark_completed(self, task_id, *, result_id):
        self.task["status"] = "completed"
        self.task["result_id"] = result_id
        return self.task

    def mark_failed(self, task_id, *, error_code, error_message):
        self.task["status"] = "failed"
        return self.task

    def sync_graph_from_run_trace(self, *_args, **_kwargs):
        return self.task

    def mark_graph_failed(self, *_args, **_kwargs):
        return self.task

    def mark_node_running(self, *_args, **_kwargs):
        return self.task

    def mark_node_finished(self, *_args, **_kwargs):
        return self.task

    def mark_node_failed(self, *_args, **_kwargs):
        return self.task


def test_portfolio_daily_loop_api_requires_login() -> None:
    with TestClient(app) as client:
        response = client.get("/api/portfolio-manager/daily-loop/runs")

    assert response.status_code in {401, 403}


def test_portfolio_daily_loop_api_authenticated_routes_and_order() -> None:
    fake_service = FakeDailyLoopService()
    fake_tasks = FakeTaskRepo()
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_portfolio_daily_loop_service] = lambda: fake_service
    app.dependency_overrides[get_agent_task_repository] = lambda: fake_tasks
    try:
        with TestClient(app) as client:
            sync_response = client.post("/api/portfolio-manager/daily-loop/run", json={"background": False})
            background_response = client.post("/api/portfolio-manager/daily-loop/run", json={"background": True})
            list_response = client.get("/api/portfolio-manager/daily-loop/runs")
            latest_response = client.get("/api/portfolio-manager/daily-loop/runs/latest")
            detail_response = client.get("/api/portfolio-manager/daily-loop/runs/portfolio_daily_loop:detail")
    finally:
        app.dependency_overrides.clear()

    assert sync_response.status_code == 200
    assert sync_response.json()["background"] is False
    assert sync_response.json()["run"]["id"] == "portfolio_daily_loop:sync"
    assert background_response.status_code == 200
    assert background_response.json()["background"] is True
    assert background_response.json()["task_id"] == "task:1"
    assert list_response.status_code == 200
    assert latest_response.status_code == 200
    assert latest_response.json()["id"] == "portfolio_daily_loop:latest"
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == "portfolio_daily_loop:detail"
