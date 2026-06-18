from fastapi.testclient import TestClient

from app.api.deps import get_account_performance_service, require_authenticated_session
from app.domains.performance.schemas import AccountPerformanceSummary, PerformanceSeriesResponse
from app.main import app


class FakeAccountPerformanceService:
    def get_series(self, *, start_date: str | None = None, end_date: str | None = None, base_index: float = 100.0) -> PerformanceSeriesResponse:
        return PerformanceSeriesResponse(
            summary=AccountPerformanceSummary(
                start_date=start_date or "2026-01-01",
                end_date=end_date or "2026-01-02",
                start_nav=100.0,
                end_nav=110.0,
                total_net_cash_flow=0.0,
                money_gain=10.0,
                twr_total_return=0.10,
                annualized_return=1.0,
                max_drawdown=0.0,
                volatility=None,
                sharpe_ratio=None,
                data_quality="partial",
                data_limitations=["nav_yesterday_missing"],
            ),
            series=[
                {
                    "date": "2026-01-01",
                    "nav": 100.0,
                    "net_cash_flow": 0.0,
                    "investment_pnl": None,
                    "daily_return": None,
                    "twr_index": base_index,
                    "data_quality": "missing",
                    "data_limitations": ["nav_yesterday_missing"],
                },
                {
                    "date": "2026-01-02",
                    "nav": 110.0,
                    "net_cash_flow": 0.0,
                    "investment_pnl": 10.0,
                    "daily_return": 0.10,
                    "twr_index": base_index * 1.1,
                    "data_quality": "complete",
                    "data_limitations": [],
                },
            ],
            methodology={"return_method": "time_weighted_return", "cashflow_adjusted": True, "base_index": base_index},
        )

    def get_summary(self, *, start_date: str | None = None, end_date: str | None = None, base_index: float = 100.0) -> AccountPerformanceSummary:
        return self.get_series(start_date=start_date, end_date=end_date, base_index=base_index).summary


def test_account_performance_api_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.get("/api/performance/account/series")

    assert response.status_code in {401, 403}


def test_account_performance_series_api_returns_response() -> None:
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_account_performance_service] = lambda: FakeAccountPerformanceService()
    try:
        with TestClient(app) as client:
            response = client.get("/api/performance/account/series?start_date=2026-01-01&base_index=100")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["methodology"]["return_method"] == "time_weighted_return"
    assert payload["methodology"]["cashflow_adjusted"] is True
    assert payload["series"][1]["daily_return"] == 0.10
    assert payload["summary"]["twr_total_return"] == 0.10


def test_account_performance_summary_api_returns_summary() -> None:
    app.dependency_overrides[require_authenticated_session] = lambda: object()
    app.dependency_overrides[get_account_performance_service] = lambda: FakeAccountPerformanceService()
    try:
        with TestClient(app) as client:
            response = client.get("/api/performance/account/summary?end_date=2026-01-02")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["start_nav"] == 100.0
    assert payload["end_nav"] == 110.0
    assert payload["money_gain"] == 10.0
