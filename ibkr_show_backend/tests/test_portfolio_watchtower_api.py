from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.deps import get_portfolio_watchtower_service, require_authenticated_session
from app.main import app


def _run_doc() -> dict:
    return {
        "id": "watchtower_run:2026-06-15:manual:test",
        "run_date": "2026-06-15",
        "run_type": "manual",
        "status": "success",
        "constitution_version": "portfolio_constitution_v1",
        "universe_snapshot": {"total": 1, "holding": 1, "watchlist": 0, "candidate": 0, "excluded": 0, "enabled": 1},
        "summary": {"normal": 0, "watch": 0, "attention_required": 0, "decision_required": 1},
        "top_attention_symbols": ["AMD"],
        "data_limitations": [],
        "created_at": "2026-06-15T00:00:00+00:00",
        "updated_at": "2026-06-15T00:00:00+00:00",
    }


def _item_doc() -> dict:
    return {
        "id": "watchtower_item:watchtower_run:2026-06-15:manual:test:AMD",
        "run_id": "watchtower_run:2026-06-15:manual:test",
        "run_date": "2026-06-15",
        "symbol": "AMD",
        "display_symbol": "AMD",
        "name": "AMD",
        "universe_type": "holding",
        "priority": "high",
        "enabled": True,
        "ai_theme_role": "semiconductor",
        "theme_tags": ["AI"],
        "status": "decision_required",
        "severity": "high",
        "trigger_reasons": [],
        "metrics": {"consecutive_up_days": 0, "consecutive_down_days": 7, "data_points": 60},
        "suggested_next_step": "trigger_trade_decision",
        "decision_candidate": True,
        "decision_type_hint": "holding_decision",
        "scan_snapshot": {"universe": {}},
        "data_limitations": [],
        "created_at": "2026-06-15T00:00:00+00:00",
        "updated_at": "2026-06-15T00:00:00+00:00",
    }


class FakeWatchtowerService:
    def run_watchtower(self, **_kwargs):
        return {**_run_doc(), "items": [_item_doc()]}

    def list_runs(self, **_kwargs):
        return [_run_doc()]

    def get_run_detail(self, run_id: str):
        return {**_run_doc(), "id": run_id, "items": [_item_doc()]}

    def list_symbol_history(self, symbol: str, **_kwargs):
        return [{**_item_doc(), "symbol": symbol.upper()}]


def test_watchtower_api_requires_login() -> None:
    with TestClient(app) as client:
        response = client.get("/api/portfolio-manager/watchtower/runs")

    assert response.status_code in {401, 403}


def test_watchtower_api_authenticated_routes_and_order() -> None:
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_portfolio_watchtower_service] = lambda: FakeWatchtowerService()
    try:
        with TestClient(app) as client:
            run_response = client.post("/api/portfolio-manager/watchtower/run", json={"run_type": "manual", "force_refresh": False})
            list_response = client.get("/api/portfolio-manager/watchtower/runs?limit=20")
            detail_response = client.get("/api/portfolio-manager/watchtower/runs/watchtower_run:2026-06-15:manual:test")
            history_response = client.get("/api/portfolio-manager/watchtower/symbols/AMD.US/history?limit=30")
    finally:
        app.dependency_overrides.clear()

    assert run_response.status_code == 200
    assert run_response.json()["items"][0]["symbol"] == "AMD"
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["id"].startswith("watchtower_run:")
    assert detail_response.status_code == 200
    assert history_response.status_code == 200
    assert history_response.json()["items"][0]["symbol"] == "AMD.US"

