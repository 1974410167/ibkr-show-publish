from fastapi.testclient import TestClient

from app.api.deps import get_performance_price_auto_backfill_service, require_authenticated_session
from app.domains.performance.price_auto_backfill import PerformancePriceEnsureResult, PerformancePriceEnsureSymbolResult
from app.main import app


class FakePerformancePriceAutoBackfillService:
    def __init__(self, limitations: list[str] | None = None) -> None:
        self.limitations = limitations or []
        self.calls: list[dict] = []

    def ensure_for_baselines(self, *, symbols: str | list[str] | None, start_date: str | None, end_date: str | None, force: bool):
        self.calls.append({"symbols": symbols, "start_date": start_date, "end_date": end_date, "force": force})
        return PerformancePriceEnsureResult(
            start_date=start_date or "2026-01-01",
            end_date=end_date or "2026-01-05",
            symbols=["SPY", "QQQ", "AAPL"],
            inserted=1,
            failed=1 if self.limitations else 0,
            missing_symbols=["AAPL"] if self.limitations else [],
            per_symbol={
                "AAPL": PerformancePriceEnsureSymbolResult(
                    symbol="AAPL",
                    source_symbol="AAPL.US",
                    fetched=1,
                    inserted=1,
                    first_date="2026-01-02",
                    last_date="2026-01-02",
                )
            },
            data_limitations=self.limitations,
        )


def test_performance_price_ensure_api_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.post("/api/performance/prices/ensure-for-baselines")

    assert response.status_code in {401, 403}


def test_performance_price_ensure_api_returns_result_and_passes_params() -> None:
    service = FakePerformancePriceAutoBackfillService()
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_performance_price_auto_backfill_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/performance/prices/ensure-for-baselines?symbols=AAPL,ASML&start_date=2026-01-01&end_date=2026-01-05&force=true"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["inserted"] == 1
    assert service.calls == [
        {"symbols": "AAPL,ASML", "start_date": "2026-01-01", "end_date": "2026-01-05", "force": True}
    ]


def test_performance_price_ensure_api_can_return_longbridge_limitations() -> None:
    service = FakePerformancePriceAutoBackfillService(limitations=["longbridge_oauth_required"])
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_performance_price_auto_backfill_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.post("/api/performance/prices/ensure-for-baselines?symbols=AAPL")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["data_limitations"] == ["longbridge_oauth_required"]
