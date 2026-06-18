from app.domains.performance.baseline_schemas import PerformanceBaselineType
from app.domains.performance.buy_and_hold_baseline import StartPortfolioBuyAndHoldBaselineCalculator
from app.domains.performance.schemas import AccountPerformancePoint


def _actual(day: str, flow: float = 0.0) -> AccountPerformancePoint:
    return AccountPerformancePoint(date=day, nav=100.0, net_cash_flow=flow)


def test_buy_and_hold_keeps_start_holdings_and_price_changes_nav() -> None:
    calculator = StartPortfolioBuyAndHoldBaselineCalculator()

    series, summary = calculator.build(
        actual_series=[_actual("2026-01-01"), _actual("2026-01-02")],
        holdings=[{"symbol": "AMD", "quantity": 2}],
        prices_by_symbol={"AMD": {"2026-01-01": 10.0, "2026-01-02": 12.0}},
    )

    assert series[0].nav == 20.0
    assert series[1].nav == 24.0
    assert series[1].daily_return == 0.2
    assert summary.baseline_type == PerformanceBaselineType.START_PORTFOLIO_BUY_AND_HOLD


def test_buy_and_hold_deposit_goes_to_cash_not_stock() -> None:
    calculator = StartPortfolioBuyAndHoldBaselineCalculator()

    series, _summary = calculator.build(
        actual_series=[_actual("2026-01-01"), _actual("2026-01-02", flow=20.0)],
        holdings=[{"symbol": "AMD", "quantity": 2}],
        prices_by_symbol={"AMD": {"2026-01-01": 10.0, "2026-01-02": 10.0}},
    )

    assert series[1].cash == 20.0
    assert series[1].nav == 40.0
    assert series[1].daily_return == 0.0


def test_buy_and_hold_withdrawal_comes_from_cash() -> None:
    calculator = StartPortfolioBuyAndHoldBaselineCalculator()

    series, _summary = calculator.build(
        actual_series=[
            _actual("2026-01-01"),
            _actual("2026-01-02", flow=20.0),
            _actual("2026-01-03", flow=-10.0),
        ],
        holdings=[{"symbol": "AMD", "quantity": 2}],
        prices_by_symbol={"AMD": {"2026-01-01": 10.0, "2026-01-02": 10.0, "2026-01-03": 10.0}},
    )

    assert series[2].cash == 10.0
    assert series[2].nav == 30.0


def test_buy_and_hold_forward_fills_missing_price() -> None:
    calculator = StartPortfolioBuyAndHoldBaselineCalculator()

    series, summary = calculator.build(
        actual_series=[_actual("2026-01-01"), _actual("2026-01-02")],
        holdings=[{"symbol": "AMD", "quantity": 2}],
        prices_by_symbol={"AMD": {"2026-01-01": 10.0}},
    )

    assert series[1].nav == 20.0
    assert series[1].data_quality == "partial"
    assert "price_forward_filled:AMD" in series[1].data_limitations
    assert summary.data_quality == "partial"


def test_buy_and_hold_uses_next_available_price_for_non_trading_start_date() -> None:
    calculator = StartPortfolioBuyAndHoldBaselineCalculator()

    series, summary = calculator.build(
        actual_series=[_actual("2026-01-01"), _actual("2026-01-02")],
        holdings=[{"symbol": "AMD", "quantity": 2}],
        prices_by_symbol={"AMD": {"2026-01-02": 10.0}},
    )

    assert series[0].nav == 20.0
    assert series[0].data_quality == "complete"
    assert "price_missing:AMD" not in series[0].data_limitations
    assert "price_forward_filled:AMD" not in series[0].data_limitations
    assert summary.data_quality == "complete"
    assert "start_portfolio_price_shifted_to_next_trading_day:AMD:2026-01-02" in summary.data_limitations
    assert summary.metadata["start_portfolio_symbols"] == ["AMD"]
    assert summary.metadata["start_portfolio_holdings"] == [{"symbol": "AMD", "quantity": 2.0}]


def test_buy_and_hold_start_cash_uses_shifted_start_price_consistently() -> None:
    calculator = StartPortfolioBuyAndHoldBaselineCalculator()

    series, _summary = calculator.build(
        actual_series=[_actual("2026-01-01"), _actual("2026-01-02")],
        holdings=[{"symbol": "AMD", "quantity": 2}],
        prices_by_symbol={"AMD": {"2026-01-02": 10.0}},
        start_cash=80.0,
    )

    assert series[0].nav == 100.0


def test_buy_and_hold_missing_start_holdings_returns_missing() -> None:
    calculator = StartPortfolioBuyAndHoldBaselineCalculator()

    series, summary = calculator.build(
        actual_series=[_actual("2026-01-01")],
        holdings=[],
        prices_by_symbol={},
    )

    assert series == []
    assert summary.data_quality == "missing"
    assert "start_portfolio_holdings_missing" in summary.data_limitations
