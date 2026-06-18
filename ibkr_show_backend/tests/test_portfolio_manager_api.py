from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.deps import (
    get_portfolio_constitution_service,
    get_portfolio_universe_service,
    require_authenticated_session,
)
from app.domains.portfolio_manager.constitution.default_policy import default_constitution_document
from app.main import app


class FakeConstitutionService:
    def __init__(self) -> None:
        self.current = {
            **default_constitution_document(),
            "created_at": "2026-06-15T00:00:00+00:00",
            "updated_at": "2026-06-15T00:00:00+00:00",
            "disclaimer": "投资宪法是系统最高层长期约束，不代表收益承诺，不构成投资建议。",
        }

    def get_current(self) -> dict:
        return self.current

    def update_current(self, payload) -> dict:
        self.current = {**self.current, **payload.model_dump(), "updated_at": "2026-06-15T01:00:00+00:00"}
        return self.current

    def reset_default(self) -> dict:
        return self.current


class FakeUniverseService:
    def __init__(self) -> None:
        self.item = {
            "id": "universe:AMD",
            "symbol": "AMD",
            "display_symbol": "AMD",
            "name": "Advanced Micro Devices",
            "universe_type": "watchlist",
            "theme_tags": ["AI"],
            "ai_theme_role": "semiconductor",
            "priority": "high",
            "enabled": True,
            "scan_frequency": "daily",
            "decision_frequency": "event_driven",
            "max_llm_runs_per_week": 3,
            "source": "manual",
            "notes": "",
            "excluded_reason": None,
            "created_at": "2026-06-15T00:00:00+00:00",
            "updated_at": "2026-06-15T00:00:00+00:00",
        }

    def list_symbols(self, **_filters) -> list[dict]:
        return [self.item]

    def get_symbol(self, symbol: str) -> dict:
        return {**self.item, "symbol": symbol.upper()}

    def upsert_symbol(self, symbol: str, payload) -> dict:
        return {**self.item, **payload.model_dump(), "symbol": symbol.upper(), "id": f"universe:{symbol.upper()}"}

    def disable_symbol(self, symbol: str) -> dict:
        return {**self.item, "symbol": symbol.upper(), "enabled": False}

    def mark_excluded(self, symbol: str, payload) -> dict:
        return {
            **self.item,
            "symbol": symbol.upper(),
            "universe_type": "excluded",
            "enabled": False,
            "excluded_reason": payload.excluded_reason,
            "scan_frequency": "disabled",
            "decision_frequency": "disabled",
        }

    def sync_holdings_from_positions(self):
        return ([{**self.item, "universe_type": "holding", "source": "ibkr_holding_sync"}], [])


def test_portfolio_manager_api_requires_login() -> None:
    with TestClient(app) as client:
        response = client.get("/api/portfolio-manager/constitution")

    assert response.status_code in {401, 403}


def test_constitution_api_authenticated_get_put_reset() -> None:
    constitution_service = FakeConstitutionService()
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_portfolio_constitution_service] = lambda: constitution_service
    try:
        with TestClient(app) as client:
            get_response = client.get("/api/portfolio-manager/constitution")
            payload = get_response.json()
            put_response = client.put(
                "/api/portfolio-manager/constitution",
                json={**payload, "target_account_value_usd": 1600000},
            )
            reset_response = client.post("/api/portfolio-manager/constitution/reset")
    finally:
        app.dependency_overrides.clear()

    assert get_response.status_code == 200
    assert put_response.status_code == 200
    assert put_response.json()["target_account_value_usd"] == 1600000
    assert reset_response.status_code == 200


def test_universe_api_authenticated_and_sync_route_order() -> None:
    universe_service = FakeUniverseService()
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_portfolio_universe_service] = lambda: universe_service
    try:
        with TestClient(app) as client:
            list_response = client.get("/api/portfolio-manager/universe")
            put_response = client.put("/api/portfolio-manager/universe/AMD.US", json=universe_service.item)
            sync_response = client.post("/api/portfolio-manager/universe/sync-holdings")
            exclude_response = client.post(
                "/api/portfolio-manager/universe/AMD/exclude",
                json={"excluded_reason": "manual exclusion"},
            )
    finally:
        app.dependency_overrides.clear()

    assert list_response.status_code == 200
    assert put_response.status_code == 200
    assert put_response.json()["symbol"] == "AMD.US"
    assert sync_response.status_code == 200
    assert sync_response.json()["synced"][0]["universe_type"] == "holding"
    assert exclude_response.status_code == 200
    assert exclude_response.json()["universe_type"] == "excluded"

