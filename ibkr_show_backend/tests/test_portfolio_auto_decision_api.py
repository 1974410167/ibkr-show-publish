from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.deps import get_portfolio_auto_decision_service, require_authenticated_session
from app.main import app


def _run_doc() -> dict:
    return {
        "id": "auto_decision_run:2026-06-15:manual:test",
        "run_date": "2026-06-15",
        "run_type": "manual",
        "source_watchtower_run_id": "watchtower_run:2026-06-15:manual:test",
        "status": "success",
        "constitution_version": "portfolio_constitution_v1",
        "budget": {"max_decisions": 5, "used_decisions": 1, "skipped_by_budget": 0},
        "summary": {"selected": 0, "completed": 1, "failed": 0, "skipped": 0},
        "selected_symbols": ["AMD"],
        "skipped_symbols": [],
        "data_limitations": [],
        "created_at": "2026-06-15T00:00:00+00:00",
        "updated_at": "2026-06-15T00:00:00+00:00",
    }


def _item_doc(symbol: str = "AMD") -> dict:
    return {
        "id": f"auto_decision_item:auto_decision_run:2026-06-15:manual:test:{symbol}",
        "run_id": "auto_decision_run:2026-06-15:manual:test",
        "run_date": "2026-06-15",
        "source_watchtower_run_id": "watchtower_run:2026-06-15:manual:test",
        "source_watchtower_item_id": f"watchtower_item:{symbol}",
        "symbol": symbol,
        "display_symbol": symbol,
        "universe_type": "holding",
        "ai_theme_role": "semiconductor",
        "priority": "high",
        "watchtower_status": "decision_required",
        "watchtower_severity": "high",
        "trigger_reasons": [],
        "selection_status": "completed",
        "skip_reason": None,
        "decision_type": "holding_decision",
        "decision_request": {"symbol": symbol},
        "decision_id": f"trade_decision:{symbol}",
        "decision_summary": {"final_action": "hold", "target_position_pct": 0.08},
        "error_code": None,
        "error_message": None,
        "scan_snapshot": {"symbol": symbol},
        "created_at": "2026-06-15T00:00:00+00:00",
        "updated_at": "2026-06-15T00:00:00+00:00",
    }


class FakeAutoDecisionService:
    def run_auto_decisions(self, **_kwargs):
        return {**_run_doc(), "items": [_item_doc()]}

    def list_runs(self, **_kwargs):
        return [_run_doc()]

    def get_run_detail(self, run_id: str):
        return {**_run_doc(), "id": run_id, "items": [_item_doc()]}

    def list_symbol_history(self, symbol: str, **_kwargs):
        return [_item_doc(symbol.upper())]


def test_auto_decision_api_requires_login() -> None:
    with TestClient(app) as client:
        response = client.get("/api/portfolio-manager/auto-decisions/runs")

    assert response.status_code in {401, 403}


def test_auto_decision_api_authenticated_routes_and_order() -> None:
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_portfolio_auto_decision_service] = lambda: FakeAutoDecisionService()
    try:
        with TestClient(app) as client:
            run_response = client.post(
                "/api/portfolio-manager/auto-decisions/run",
                json={"watchtower_run_id": "watchtower_run:2026-06-15:manual:test", "max_decisions": 5, "dry_run": True},
            )
            list_response = client.get("/api/portfolio-manager/auto-decisions/runs?limit=20")
            detail_response = client.get("/api/portfolio-manager/auto-decisions/runs/auto_decision_run:2026-06-15:manual:test")
            history_response = client.get("/api/portfolio-manager/auto-decisions/symbols/amd/history?limit=30")
    finally:
        app.dependency_overrides.clear()

    assert run_response.status_code == 200
    assert run_response.json()["items"][0]["decision_id"] == "trade_decision:AMD"
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["id"].startswith("auto_decision_run:")
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == "auto_decision_run:2026-06-15:manual:test"
    assert history_response.status_code == 200
    assert history_response.json()["items"][0]["symbol"] == "AMD"
