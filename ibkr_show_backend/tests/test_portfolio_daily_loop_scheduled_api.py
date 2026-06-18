from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.deps import get_agent_task_repository, get_portfolio_daily_loop_service, require_authenticated_session
from app.core.auth import SESSION_COOKIE_NAME, create_session_token
from app.core.config import get_settings
from app.main import app
from app.domains.portfolio_manager.daily_loop.schemas import PortfolioDailyLoopRun


def _settings(**overrides):
    data = {
        "auth_session_secret": "secret",
        "portfolio_daily_loop_schedule_enabled": False,
        "portfolio_daily_loop_schedule_time": "09:00",
        "portfolio_daily_loop_schedule_timezone": "Asia/Shanghai",
        "portfolio_daily_loop_max_auto_decisions": 5,
        "portfolio_daily_loop_dry_run_auto_decision": False,
        "portfolio_daily_loop_force_refresh_auto_decision": False,
        "portfolio_daily_loop_run_evaluation": False,
        "portfolio_daily_loop_generate_improvement_report": False,
        "portfolio_daily_loop_internal_token": "",
    }
    data.update(overrides)
    return type("Settings", (), data)()


def _run(run_id: str = "portfolio_daily_loop:scheduled", status: str = "success") -> dict:
    return {
        "id": run_id,
        "run_date": "2026-07-15",
        "run_type": "scheduled",
        "status": status,
        "task_id": None,
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


class Repo:
    def __init__(self) -> None:
        self.existing = []

    def list_runs(self, **_kwargs):
        return self.existing


class FakeDailyLoopService:
    def __init__(self) -> None:
        self.repository = Repo()
        self.calls = []

    def create_running_run(self, **kwargs):
        self.calls.append(("create_running_run", kwargs))
        return PortfolioDailyLoopRun.model_validate({**_run("portfolio_daily_loop:shell", "running"), "summary": kwargs.get("initial_summary") or {}})

    def attach_task(self, run_id: str, task_id: str):
        return PortfolioDailyLoopRun.model_validate({**_run(run_id, "running"), "task_id": task_id})

    def run_daily_loop(self, **kwargs):
        self.calls.append(("run_daily_loop", kwargs))
        return PortfolioDailyLoopRun.model_validate({**_run("portfolio_daily_loop:sync"), "summary": kwargs.get("run_metadata") or {}})


class FakeTaskRepo:
    def create_task(self, **kwargs):
        return {
            "id": "task:scheduled",
            "agent": kwargs["agent"],
            "task_type": kwargs["task_type"],
            "label": kwargs["label"],
            "status": "queued",
            "payload": kwargs["payload"],
            "created_at": "2026-07-15T00:00:00+00:00",
            "updated_at": "2026-07-15T00:00:00+00:00",
        }

    def init_graph_progress(self, *_args, **_kwargs):
        return None

    def mark_running(self, *_args, **_kwargs):
        return {"id": "task:scheduled"}

    def mark_completed(self, *_args, **_kwargs):
        return None

    def mark_failed(self, *_args, **_kwargs):
        return None

    def sync_graph_from_run_trace(self, *_args, **_kwargs):
        return None

    def mark_graph_failed(self, *_args, **_kwargs):
        return None

    def mark_node_running(self, *_args, **_kwargs):
        return None

    def mark_node_finished(self, *_args, **_kwargs):
        return None

    def mark_node_failed(self, *_args, **_kwargs):
        return None


def test_schedule_status_requires_login_and_returns_settings() -> None:
    app.dependency_overrides[get_settings] = lambda: _settings(portfolio_daily_loop_schedule_enabled=True, portfolio_daily_loop_max_auto_decisions=7)
    try:
        with TestClient(app) as client:
            unauth = client.get("/api/portfolio-manager/daily-loop/schedule/status")
        app.dependency_overrides[require_authenticated_session] = lambda: object()
        with TestClient(app) as client:
            auth = client.get("/api/portfolio-manager/daily-loop/schedule/status")
    finally:
        app.dependency_overrides.clear()

    assert unauth.status_code in {401, 403}
    assert auth.status_code == 200
    assert auth.json()["enabled"] is True
    assert auth.json()["max_auto_decisions"] == 7


def test_scheduled_api_rejects_without_auth_or_internal_token() -> None:
    app.dependency_overrides[get_settings] = lambda: _settings(portfolio_daily_loop_internal_token="secret-token")
    try:
        with TestClient(app) as client:
            missing = client.post("/api/portfolio-manager/daily-loop/scheduled/run", json={"run_date": "2026-07-15"})
            wrong = client.post("/api/portfolio-manager/daily-loop/scheduled/run", json={"run_date": "2026-07-15"}, headers={"X-Internal-Token": "bad"})
    finally:
        app.dependency_overrides.clear()

    assert missing.status_code == 401
    assert wrong.status_code == 403


def test_scheduled_api_internal_token_background_uses_settings() -> None:
    svc = FakeDailyLoopService()
    app.dependency_overrides[get_settings] = lambda: _settings(
        portfolio_daily_loop_internal_token="secret-token",
        portfolio_daily_loop_max_auto_decisions=8,
        portfolio_daily_loop_dry_run_auto_decision=True,
        portfolio_daily_loop_run_evaluation=True,
        portfolio_daily_loop_generate_improvement_report=True,
    )
    app.dependency_overrides[get_portfolio_daily_loop_service] = lambda: svc
    app.dependency_overrides[get_agent_task_repository] = lambda: FakeTaskRepo()
    try:
        with TestClient(app) as client:
            response = client.post("/api/portfolio-manager/daily-loop/scheduled/run", json={"run_date": "2026-07-15", "background": True}, headers={"X-Internal-Token": "secret-token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["skipped"] is False
    assert response.json()["task_id"] == "task:scheduled"
    create_kwargs = svc.calls[0][1]
    assert create_kwargs["run_type"] == "scheduled"
    assert create_kwargs["options"].max_auto_decisions == 8
    assert create_kwargs["options"].dry_run_auto_decision is True
    assert create_kwargs["options"].run_evaluation is True
    assert create_kwargs["initial_summary"]["triggered_by"] == "scheduled"


def test_scheduled_api_logged_in_sync_and_force_rerun() -> None:
    svc = FakeDailyLoopService()
    svc.repository.existing = [_run("portfolio_daily_loop:existing", "success")]
    app.dependency_overrides[get_settings] = lambda: _settings()
    app.dependency_overrides[get_portfolio_daily_loop_service] = lambda: svc
    app.dependency_overrides[get_agent_task_repository] = lambda: FakeTaskRepo()
    try:
        with TestClient(app) as client:
            token = create_session_token(username="admin", secret="secret", max_age_seconds=3600)
            client.cookies.set(SESSION_COOKIE_NAME, token)
            skipped = client.post("/api/portfolio-manager/daily-loop/scheduled/run", json={"run_date": "2026-07-15", "background": False})
            forced = client.post("/api/portfolio-manager/daily-loop/scheduled/run", json={"run_date": "2026-07-15", "background": False, "force": True})
    finally:
        app.dependency_overrides.clear()

    assert skipped.status_code == 200
    assert skipped.json()["skipped"] is True
    assert skipped.json()["existing_run_id"] == "portfolio_daily_loop:existing"
    assert forced.status_code == 200
    assert forced.json()["skipped"] is False
    assert forced.json()["run"]["run_type"] == "scheduled"
    assert svc.calls[-1][1]["run_type"] == "scheduled"
