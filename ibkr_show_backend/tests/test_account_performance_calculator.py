import pytest

from app.domains.performance.account_performance_calculator import AccountPerformanceCalculator


def test_daily_return_without_cashflow() -> None:
    calculator = AccountPerformanceCalculator()

    series = calculator.build_series(
        [
            {"report_date": "2026-01-01", "total_equity": 100.0},
            {"report_date": "2026-01-02", "total_equity": 110.0},
        ],
        {},
    )
    summary = calculator.build_summary(series)

    assert series[0].daily_return is None
    assert series[1].investment_pnl == 10.0
    assert series[1].daily_return == pytest.approx(0.10)
    assert series[1].twr_index == pytest.approx(110.0)
    assert summary.twr_total_return == pytest.approx(0.10)


def test_daily_return_with_deposit() -> None:
    calculator = AccountPerformanceCalculator()

    series = calculator.build_series(
        [
            {"report_date": "2026-01-01", "total_equity": 100.0},
            {"report_date": "2026-01-02", "total_equity": 130.0},
        ],
        {"2026-01-02": 20.0},
    )

    assert series[1].investment_pnl == 10.0
    assert series[1].daily_return == pytest.approx(0.10)


def test_daily_return_with_withdrawal() -> None:
    calculator = AccountPerformanceCalculator()

    series = calculator.build_series(
        [
            {"report_date": "2026-01-01", "total_equity": 100.0},
            {"report_date": "2026-01-02", "total_equity": 80.0},
        ],
        {"2026-01-02": -10.0},
    )

    assert series[1].investment_pnl == -10.0
    assert series[1].daily_return == pytest.approx(-0.10)


def test_missing_previous_nav_marks_point_missing() -> None:
    calculator = AccountPerformanceCalculator()

    series = calculator.build_series([{"report_date": "2026-01-01", "total_equity": 100.0}], {})
    summary = calculator.build_summary(series)

    assert series[0].daily_return is None
    assert series[0].data_quality == "missing"
    assert "nav_yesterday_missing" in series[0].data_limitations
    assert summary.data_quality == "missing"


def test_max_drawdown_uses_twr_index() -> None:
    calculator = AccountPerformanceCalculator()

    series = calculator.build_series(
        [
            {"report_date": "2026-01-01", "total_equity": 100.0},
            {"report_date": "2026-01-02", "total_equity": 120.0},
            {"report_date": "2026-01-03", "total_equity": 90.0},
        ],
        {},
    )
    summary = calculator.build_summary(series)

    assert summary.max_drawdown == pytest.approx(-0.25)


def test_metrics_do_not_crash_for_empty_data() -> None:
    calculator = AccountPerformanceCalculator()

    summary = calculator.build_summary([])

    assert summary.data_quality == "missing"
    assert summary.annualized_return is None
    assert summary.volatility is None
    assert summary.sharpe_ratio is None
