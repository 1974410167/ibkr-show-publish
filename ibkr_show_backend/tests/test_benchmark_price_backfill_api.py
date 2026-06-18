from fastapi.testclient import TestClient

from app.api.deps import get_benchmark_price_backfill_service, require_authenticated_session
from app.domains.performance.benchmark_price_backfill import (
    BenchmarkPriceBackfillResult,
    BenchmarkPriceBackfillSymbolResult,
    BenchmarkPriceBackfillUnavailable,
    BenchmarkPriceStatusItem,
    BenchmarkPriceStatusResponse,
)
from app.main import app


class FakeBenchmarkPriceBackfillService:
    def __init__(self, unavailable: bool = False) -> None:
        self.unavailable = unavailable
        self.backfill_calls: list[dict] = []
        self.status_calls: list[dict] = []

    def backfill(self, *, symbols: str | list[str] | None, start_date: str | None, end_date: str | None, force: bool):
        self.backfill_calls.append({"symbols": symbols, "start_date": start_date, "end_date": end_date, "force": force})
        if self.unavailable:
            raise BenchmarkPriceBackfillUnavailable("Longbridge OpenAPI is not available", data_limitations=["longbridge_oauth_required"])
        return BenchmarkPriceBackfillResult(
            symbols=["SPY"],
            start_date=start_date or "2026-01-01",
            end_date=end_date or "2026-01-05",
            inserted=1,
            per_symbol={
                "SPY": BenchmarkPriceBackfillSymbolResult(
                    requested_symbol="SPY",
                    source_symbol="SPY.US",
                    fetched=1,
                    inserted=1,
                    first_date="2026-01-02",
                    last_date="2026-01-02",
                )
            },
        )

    def status(self, *, symbols: str | list[str] | None, start_date: str | None, end_date: str | None):
        self.status_calls.append({"symbols": symbols, "start_date": start_date, "end_date": end_date})
        return BenchmarkPriceStatusResponse(
            symbols=["SPY"],
            start_date=start_date or "2026-01-01",
            end_date=end_date or "2026-01-05",
            per_symbol={"SPY": BenchmarkPriceStatusItem(count=1, first_date="2026-01-02", last_date="2026-01-02", has_data=True)},
            data_quality="complete",
        )


def test_benchmark_price_backfill_api_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.post("/api/performance/benchmark-prices/backfill")

    assert response.status_code in {401, 403}


def test_benchmark_price_backfill_api_returns_result() -> None:
    service = FakeBenchmarkPriceBackfillService()
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_benchmark_price_backfill_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/performance/benchmark-prices/backfill?symbols=SPY&start_date=2026-01-01&end_date=2026-01-05&force=true"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["inserted"] == 1
    assert service.backfill_calls == [
        {"symbols": "SPY", "start_date": "2026-01-01", "end_date": "2026-01-05", "force": True}
    ]


def test_benchmark_price_backfill_api_returns_503_when_longbridge_unavailable() -> None:
    service = FakeBenchmarkPriceBackfillService(unavailable=True)
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_benchmark_price_backfill_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.post("/api/performance/benchmark-prices/backfill?symbols=SPY")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"]["data_limitations"] == ["longbridge_oauth_required"]


def test_benchmark_price_status_api_returns_status() -> None:
    service = FakeBenchmarkPriceBackfillService()
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_benchmark_price_backfill_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.get("/api/performance/benchmark-prices/status?symbols=SPY&start_date=2026-01-01&end_date=2026-01-05")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["per_symbol"]["SPY"]["count"] == 1
    assert service.status_calls == [
        {"symbols": "SPY", "start_date": "2026-01-01", "end_date": "2026-01-05"}
    ]
