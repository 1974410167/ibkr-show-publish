from app.domains.performance.baseline_metrics import build_baseline_summary, missing_baseline_summary
from app.domains.performance.baseline_schemas import (
    BaselinePerformancePoint,
    BaselinePerformanceSummary,
    PerformanceBaselineType,
)
from app.domains.performance.schemas import AccountPerformancePoint

BASELINE_LABELS = {
    PerformanceBaselineType.SPY_CASHFLOW_MATCHED: "SPY 同现金流基准",
    PerformanceBaselineType.QQQ_CASHFLOW_MATCHED: "QQQ 同现金流基准",
}


class CashFlowMatchedBaselineCalculator:
    def build(
        self,
        *,
        baseline_type: PerformanceBaselineType,
        actual_series: list[AccountPerformancePoint],
        prices_by_date: dict[str, float],
        base_index: float = 100.0,
        benchmark_symbol: str,
        provider_limitations: list[str] | None = None,
    ) -> tuple[list[BaselinePerformancePoint], BaselinePerformanceSummary]:
        label = BASELINE_LABELS[baseline_type]
        limitations = list(provider_limitations or [])
        if not actual_series:
            return [], missing_baseline_summary(
                baseline_type=baseline_type,
                label=label,
                start_date=None,
                end_date=None,
                data_limitations=[*limitations, "actual_account_series_missing"],
            )

        start = actual_series[0]
        start_price = prices_by_date.get(start.date)
        shifted_start_date: str | None = None
        if start_price is None or start_price <= 0:
            shifted = _nearest_available_start_price(start.date, prices_by_date)
            if shifted is not None:
                shifted_date, start_price = shifted
                shifted_start_date = shifted_date
                limitations.append(f"benchmark_start_price_shifted_to_next_trading_day:{benchmark_symbol}:{shifted_date}")
        if start.nav is None or start_price is None or start_price <= 0:
            return [], missing_baseline_summary(
                baseline_type=baseline_type,
                label=label,
                start_date=start.date,
                end_date=actual_series[-1].date,
                data_limitations=[*limitations, f"benchmark_start_price_missing_after_trading_day_shift:{benchmark_symbol}"],
            )

        units = start.nav / start_price
        return_index = float(base_index)
        previous_price = start_price
        series: list[BaselinePerformancePoint] = []
        missing_count = 0

        for index, actual in enumerate(actual_series):
            data_limitations: list[str] = []
            data_quality = "complete"
            price = prices_by_date.get(actual.date)
            if price is None or price <= 0:
                if index == 0 and shifted_start_date is not None:
                    price = start_price
                else:
                    missing_count += 1
                    price = previous_price
                    data_quality = "partial"
                    data_limitations.append("benchmark_price_forward_filled")
            if price is None or price <= 0:
                series.append(
                    BaselinePerformancePoint(
                        date=actual.date,
                        baseline_type=baseline_type,
                        nav=None,
                        net_cash_flow=actual.net_cash_flow,
                        return_index=return_index,
                        data_quality="missing",
                        data_limitations=["benchmark_price_missing"],
                    )
                )
                continue

            if index > 0 and actual.net_cash_flow:
                units += actual.net_cash_flow / price
                if units < 0:
                    data_quality = "partial"
                    data_limitations.append("benchmark_units_insufficient_for_withdrawal")
                    units = 0.0

            daily_return = None if index == 0 or previous_price <= 0 else price / previous_price - 1.0
            if daily_return is not None:
                return_index *= 1.0 + daily_return
            nav = units * price
            series.append(
                BaselinePerformancePoint(
                    date=actual.date,
                    baseline_type=baseline_type,
                    nav=_round(nav),
                    net_cash_flow=_round(actual.net_cash_flow),
                    daily_return=_round(daily_return, 8),
                    return_index=_round(return_index),
                    benchmark_price=_round(price),
                    units=_round(units),
                    cash=0.0,
                    data_quality=data_quality,
                    data_limitations=data_limitations,
                )
            )
            previous_price = price

        if missing_count / max(len(actual_series), 1) > 0.2:
            limitations.append("benchmark_price_missing_high")
        summary = build_baseline_summary(
            baseline_type=baseline_type,
            label=label,
            series=series,
            data_limitations=limitations,
        )
        return series, summary


def _round(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _nearest_available_start_price(start_date: str, prices_by_date: dict[str, float]) -> tuple[str, float] | None:
    for price_date in sorted(prices_by_date):
        if price_date < start_date:
            continue
        price = prices_by_date.get(price_date)
        if price is not None and price > 0:
            return price_date, price
    for price_date in sorted(prices_by_date, reverse=True):
        if price_date > start_date:
            continue
        price = prices_by_date.get(price_date)
        if price is not None and price > 0:
            return price_date, price
    return None
