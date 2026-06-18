import pytest

from app.domains.performance.baseline_schemas import PerformanceBaselineType
from app.domains.performance.baseline_service import PerformanceBaselineService, _estimate_start_cash
from app.domains.performance.schemas import AccountPerformanceSummary, PerformanceSeriesResponse


class FakeAccountPerformanceService:
    def __init__(self, *, start_after_end: bool = False) -> None:
        self.start_after_end = start_after_end

    def get_series(self, *, start_date=None, end_date=None, base_index=100.0):
        if self.start_after_end:
            raise ValueError("start_date must be before or equal to end_date")
        return PerformanceSeriesResponse(
            summary=AccountPerformanceSummary(
                start_date="2026-01-01",
                end_date="2026-01-02",
                start_nav=100.0,
                end_nav=120.0,
                total_net_cash_flow=0.0,
                money_gain=20.0,
                twr_total_return=0.20,
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
                    "nav": 120.0,
                    "net_cash_flow": 0.0,
                    "investment_pnl": 20.0,
                    "daily_return": 0.20,
                    "twr_index": base_index * 1.2,
                    "data_quality": "complete",
                    "data_limitations": [],
                },
            ],
            methodology={"return_method": "time_weighted_return", "cashflow_adjusted": True, "base_index": base_index},
        )


class FakeRepository:
    def latest_position_report_date_on_or_before(self, report_date):
        return "2026-01-01"

    def list_positions_for_report_date(self, report_date):
        return [{"symbol": "AMD", "quantity": 10}]


class FakePriceProvider:
    def __init__(self, missing_spy: bool = False) -> None:
        self.missing_spy = missing_spy

    def get_close_prices(self, symbol, *, start_date, end_date):
        if self.missing_spy and symbol == "SPY":
            return {}, ["benchmark_price_missing:SPY"]
        return {"2026-01-01": 10.0, "2026-01-02": 11.0}, []

    def get_close_prices_for_symbols(self, symbols, *, start_date, end_date):
        return {symbol: {"2026-01-01": 10.0, "2026-01-02": 11.0} for symbol in symbols}, []


def test_baseline_service_returns_actual_and_three_baselines() -> None:
    service = PerformanceBaselineService(FakeAccountPerformanceService(), FakeRepository(), FakePriceProvider())

    response = service.get_series()

    assert PerformanceBaselineType.ACTUAL_ACCOUNT in response.series
    assert len(response.summary.baselines) == 3
    assert {item.baseline_type for item in response.summary.baselines} == {
        PerformanceBaselineType.SPY_CASHFLOW_MATCHED,
        PerformanceBaselineType.QQQ_CASHFLOW_MATCHED,
        PerformanceBaselineType.START_PORTFOLIO_BUY_AND_HOLD,
    }
    buy_hold = next(
        item
        for item in response.summary.baselines
        if item.baseline_type == PerformanceBaselineType.START_PORTFOLIO_BUY_AND_HOLD
    )
    assert buy_hold.metadata["start_portfolio_symbols"] == ["AMD"]
    assert buy_hold.metadata["start_portfolio_holdings"] == [{"symbol": "AMD", "quantity": 10.0}]


def test_baseline_service_calculates_excess_return_and_value_added() -> None:
    service = PerformanceBaselineService(FakeAccountPerformanceService(), FakeRepository(), FakePriceProvider())

    summary = service.get_summary(baselines=[PerformanceBaselineType.SPY_CASHFLOW_MATCHED])

    assert summary.excess_returns["vs_spy_cashflow_matched"] == pytest.approx(0.10)
    assert summary.value_added["vs_spy_cashflow_matched"] == pytest.approx(10.0)


def test_baseline_service_missing_spy_does_not_crash() -> None:
    service = PerformanceBaselineService(FakeAccountPerformanceService(), FakeRepository(), FakePriceProvider(missing_spy=True))

    summary = service.get_summary(baselines=[PerformanceBaselineType.SPY_CASHFLOW_MATCHED])

    assert summary.baselines[0].data_quality == "missing"
    assert summary.excess_returns["vs_spy_cashflow_matched"] is None


def test_estimate_start_cash_uses_next_available_price_for_non_trading_start_date() -> None:
    cash = _estimate_start_cash(
        100.0,
        [{"symbol": "AMD", "quantity": 2}],
        {"AMD": {"2026-01-02": 10.0}},
        "2026-01-01",
    )

    assert cash == 80.0


def test_baseline_service_propagates_invalid_date_range() -> None:
    service = PerformanceBaselineService(FakeAccountPerformanceService(start_after_end=True), FakeRepository(), FakePriceProvider())

    with pytest.raises(ValueError):
        service.get_summary(start_date="2026-01-02", end_date="2026-01-01")
