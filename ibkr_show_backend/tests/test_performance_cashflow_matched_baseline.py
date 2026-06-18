import pytest

from app.domains.performance.baseline_schemas import PerformanceBaselineType
from app.domains.performance.cashflow_matched_baseline import CashFlowMatchedBaselineCalculator
from app.domains.performance.schemas import AccountPerformancePoint


def _actual(nav: float = 100.0, flow: float = 0.0, day: str = "2026-01-01") -> AccountPerformancePoint:
    return AccountPerformancePoint(date=day, nav=nav, net_cash_flow=flow)


def test_cashflow_matched_initial_units_and_price_return() -> None:
    calculator = CashFlowMatchedBaselineCalculator()

    series, summary = calculator.build(
        baseline_type=PerformanceBaselineType.SPY_CASHFLOW_MATCHED,
        actual_series=[_actual(100, day="2026-01-01"), _actual(110, day="2026-01-02")],
        prices_by_date={"2026-01-01": 10.0, "2026-01-02": 11.0},
        benchmark_symbol="SPY",
    )

    assert series[0].units == 10.0
    assert series[1].nav == 110.0
    assert series[1].return_index == 110.0
    assert summary.total_return == pytest.approx(0.10)


def test_cashflow_matched_deposit_adds_units() -> None:
    calculator = CashFlowMatchedBaselineCalculator()

    series, _summary = calculator.build(
        baseline_type=PerformanceBaselineType.SPY_CASHFLOW_MATCHED,
        actual_series=[_actual(100, day="2026-01-01"), _actual(120, flow=20, day="2026-01-02")],
        prices_by_date={"2026-01-01": 10.0, "2026-01-02": 10.0},
        benchmark_symbol="SPY",
    )

    assert series[1].units == 12.0
    assert series[1].nav == 120.0


def test_cashflow_matched_withdrawal_reduces_units() -> None:
    calculator = CashFlowMatchedBaselineCalculator()

    series, _summary = calculator.build(
        baseline_type=PerformanceBaselineType.SPY_CASHFLOW_MATCHED,
        actual_series=[_actual(100, day="2026-01-01"), _actual(80, flow=-20, day="2026-01-02")],
        prices_by_date={"2026-01-01": 10.0, "2026-01-02": 10.0},
        benchmark_symbol="SPY",
    )

    assert series[1].units == 8.0
    assert series[1].nav == 80.0


def test_cashflow_matched_missing_start_price_is_missing() -> None:
    calculator = CashFlowMatchedBaselineCalculator()

    series, summary = calculator.build(
        baseline_type=PerformanceBaselineType.QQQ_CASHFLOW_MATCHED,
        actual_series=[_actual(100, day="2026-01-01")],
        prices_by_date={},
        benchmark_symbol="QQQ",
    )

    assert series == []
    assert summary.data_quality == "missing"
    assert "benchmark_start_price_missing_after_trading_day_shift:QQQ" in summary.data_limitations


def test_cashflow_matched_shifts_start_price_to_next_trading_day() -> None:
    calculator = CashFlowMatchedBaselineCalculator()

    series, summary = calculator.build(
        baseline_type=PerformanceBaselineType.SPY_CASHFLOW_MATCHED,
        actual_series=[_actual(100, day="2026-01-01"), _actual(110, day="2026-01-02")],
        prices_by_date={"2026-01-02": 10.0},
        benchmark_symbol="SPY",
    )

    assert series[0].benchmark_price == 10.0
    assert series[0].return_index == 100.0
    assert series[0].data_quality == "complete"
    assert "benchmark_price_forward_filled" not in series[0].data_limitations
    assert summary.data_quality == "complete"
    assert "benchmark_start_price_shifted_to_next_trading_day:SPY:2026-01-02" in summary.data_limitations


def test_cashflow_matched_forward_fills_middle_price() -> None:
    calculator = CashFlowMatchedBaselineCalculator()

    series, summary = calculator.build(
        baseline_type=PerformanceBaselineType.SPY_CASHFLOW_MATCHED,
        actual_series=[_actual(100, day="2026-01-01"), _actual(110, day="2026-01-02")],
        prices_by_date={"2026-01-01": 10.0},
        benchmark_symbol="SPY",
    )

    assert series[1].benchmark_price == 10.0
    assert series[1].data_quality == "partial"
    assert "benchmark_price_forward_filled" in series[1].data_limitations
    assert summary.data_quality == "partial"


def test_cashflow_matched_withdrawal_more_than_units_records_limitation() -> None:
    calculator = CashFlowMatchedBaselineCalculator()

    series, summary = calculator.build(
        baseline_type=PerformanceBaselineType.SPY_CASHFLOW_MATCHED,
        actual_series=[_actual(100, day="2026-01-01"), _actual(0, flow=-200, day="2026-01-02")],
        prices_by_date={"2026-01-01": 10.0, "2026-01-02": 10.0},
        benchmark_symbol="SPY",
    )

    assert series[1].units == 0.0
    assert "benchmark_units_insufficient_for_withdrawal" in series[1].data_limitations
    assert "benchmark_units_insufficient_for_withdrawal" in summary.data_limitations
