from fastapi.testclient import TestClient

from app.api.deps import get_performance_baseline_service, require_authenticated_session
from app.domains.performance.baseline_schemas import PerformanceBaselineType
from app.domains.performance.baseline_service import PerformanceBaselineService
from app.main import app
from tests.test_performance_baseline_service import FakeAccountPerformanceService, FakePriceProvider, FakeRepository


class MissingBenchmarkPriceProvider(FakePriceProvider):
    def get_close_prices(self, symbol, *, start_date, end_date):
        return {}, [f"benchmark_price_history_not_found:{symbol}"]


def test_performance_baseline_api_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.get("/api/performance/baselines/series")

    assert response.status_code in {401, 403}


def test_performance_baseline_series_api_returns_response() -> None:
    service = PerformanceBaselineService(FakeAccountPerformanceService(), FakeRepository(), FakePriceProvider())
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_performance_baseline_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.get("/api/performance/baselines/series")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert "actual_account" in payload["series"]
    assert "spy_cashflow_matched" in payload["series"]
    assert len(payload["summary"]["baselines"]) == 3


def test_performance_baseline_summary_api_returns_response() -> None:
    service = PerformanceBaselineService(FakeAccountPerformanceService(), FakeRepository(), FakePriceProvider())
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_performance_baseline_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.get("/api/performance/baselines/summary")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["excess_returns"]["vs_spy_cashflow_matched"] == 0.1


def test_performance_baseline_api_filters_baselines() -> None:
    service = PerformanceBaselineService(FakeAccountPerformanceService(), FakeRepository(), FakePriceProvider())
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_performance_baseline_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.get("/api/performance/baselines/series?baselines=spy_cashflow_matched")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert "spy_cashflow_matched" in payload["series"]
    assert "qqq_cashflow_matched" not in payload["series"]
    assert [item["baseline_type"] for item in payload["summary"]["baselines"]] == [
        PerformanceBaselineType.SPY_CASHFLOW_MATCHED.value
    ]


def test_performance_baseline_api_returns_200_when_spy_and_qqq_prices_missing() -> None:
    service = PerformanceBaselineService(FakeAccountPerformanceService(), FakeRepository(), MissingBenchmarkPriceProvider())
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_performance_baseline_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.get("/api/performance/baselines/series?start_date=2026-01-01&end_date=2026-01-02")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert "actual_account" in payload["series"]
    assert payload["summary"]["data_quality"] in {"partial", "missing"}
    benchmark_summaries = {
        item["baseline_type"]: item
        for item in payload["summary"]["baselines"]
        if item["baseline_type"] in {"spy_cashflow_matched", "qqq_cashflow_matched"}
    }
    assert benchmark_summaries["spy_cashflow_matched"]["data_quality"] == "missing"
    assert benchmark_summaries["qqq_cashflow_matched"]["data_quality"] == "missing"


def test_performance_baseline_api_invalid_date_range_returns_422() -> None:
    service = PerformanceBaselineService(FakeAccountPerformanceService(start_after_end=True), FakeRepository(), FakePriceProvider())
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_performance_baseline_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.get("/api/performance/baselines/summary?start_date=2026-01-02&end_date=2026-01-01")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
