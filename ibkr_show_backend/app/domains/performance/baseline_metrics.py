from __future__ import annotations

import math
from datetime import date
from statistics import mean, pstdev

from app.domains.performance.baseline_schemas import (
    BaselinePerformancePoint,
    BaselinePerformanceSummary,
    PerformanceBaselineType,
)

TRADING_DAYS_PER_YEAR = 252


def build_baseline_summary(
    *,
    baseline_type: PerformanceBaselineType,
    label: str,
    series: list[BaselinePerformancePoint],
    data_limitations: list[str] | None = None,
    metadata: dict[str, object] | None = None,
) -> BaselinePerformanceSummary:
    limitations = _dedupe([*(data_limitations or []), *[item for point in series for item in point.data_limitations]])
    if not series:
        return BaselinePerformanceSummary(
            baseline_type=baseline_type,
            label=label,
            data_quality="missing",
            data_limitations=limitations or ["baseline_series_missing"],
            metadata=metadata or {},
        )

    nav_points = [point for point in series if point.nav is not None]
    if not nav_points:
        return BaselinePerformanceSummary(
            baseline_type=baseline_type,
            label=label,
            start_date=series[0].date,
            end_date=series[-1].date,
            data_quality="missing",
            data_limitations=limitations or ["baseline_nav_missing"],
            metadata=metadata or {},
        )

    start = nav_points[0]
    end = nav_points[-1]
    total_net_cash_flow = sum(point.net_cash_flow for point in series)
    money_gain = None
    if start.nav is not None and end.nav is not None:
        money_gain = end.nav - start.nav - total_net_cash_flow
    returns = [point.daily_return for point in series if point.daily_return is not None]
    total_return = _total_return(series)
    days = _days_between(start.date, end.date)
    volatility = _volatility(returns)

    return BaselinePerformanceSummary(
        baseline_type=baseline_type,
        label=label,
        start_date=start.date,
        end_date=end.date,
        start_nav=start.nav,
        end_nav=end.nav,
        total_net_cash_flow=_round(total_net_cash_flow),
        money_gain=_round(money_gain),
        total_return=_round(total_return, 8),
        annualized_return=_round(_annualized_return(total_return, days), 8),
        max_drawdown=_round(_max_drawdown([point.return_index for point in series if point.return_index is not None]), 8),
        volatility=_round(volatility, 8),
        sharpe_ratio=_round(_sharpe_ratio(returns, volatility), 8),
        data_quality=_summary_quality(series, limitations),
        data_limitations=limitations,
        metadata=metadata or {},
    )


def missing_baseline_summary(
    *,
    baseline_type: PerformanceBaselineType,
    label: str,
    start_date: str | None,
    end_date: str | None,
    data_limitations: list[str],
    metadata: dict[str, object] | None = None,
) -> BaselinePerformanceSummary:
    return BaselinePerformanceSummary(
        baseline_type=baseline_type,
        label=label,
        start_date=start_date,
        end_date=end_date,
        data_quality="missing",
        data_limitations=_dedupe(data_limitations),
        metadata=metadata or {},
    )


def _total_return(series: list[BaselinePerformancePoint]) -> float | None:
    values = [point.return_index for point in series if point.return_index is not None]
    if len(values) < 2 or values[0] in (None, 0.0):
        return None
    return float(values[-1]) / float(values[0]) - 1.0


def _annualized_return(total_return: float | None, days: int) -> float | None:
    if total_return is None or days <= 0:
        return None
    if total_return <= -1:
        return -1.0
    return (1.0 + total_return) ** (365.0 / days) - 1.0


def _volatility(returns: list[float]) -> float | None:
    if len(returns) < 2:
        return None
    return pstdev(returns) * math.sqrt(TRADING_DAYS_PER_YEAR)


def _sharpe_ratio(returns: list[float], volatility: float | None) -> float | None:
    if not returns or volatility in (None, 0.0):
        return None
    return mean(returns) * TRADING_DAYS_PER_YEAR / volatility


def _max_drawdown(values: list[float]) -> float | None:
    if not values:
        return None
    peak = float(values[0])
    max_drawdown = 0.0
    for value in values:
        current = float(value)
        peak = max(peak, current)
        if peak > 0:
            max_drawdown = min(max_drawdown, current / peak - 1.0)
    return max_drawdown


def _summary_quality(series: list[BaselinePerformancePoint], limitations: list[str]) -> str:
    qualities = {point.data_quality for point in series}
    if "missing" in qualities and "complete" not in qualities and "partial" not in qualities:
        return "missing"
    quality_limitations = [item for item in limitations if not _is_informational_limitation(item)]
    if quality_limitations or "partial" in qualities or "missing" in qualities:
        return "partial"
    return "complete"


def _is_informational_limitation(value: str) -> bool:
    return value == "nav_yesterday_missing" or value.startswith(
        "benchmark_start_price_shifted_to_next_trading_day:"
    ) or value.startswith("start_portfolio_price_shifted_to_next_trading_day:")


def _days_between(start: str, end: str) -> int:
    try:
        return (date.fromisoformat(end) - date.fromisoformat(start)).days
    except ValueError:
        return 0


def _round(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
