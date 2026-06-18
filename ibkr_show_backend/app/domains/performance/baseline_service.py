from app.domains.performance.baseline_schemas import (
    BaselinePerformanceSummary,
    PerformanceBaselineType,
    PerformanceComparisonMethodology,
    PerformanceComparisonSeriesResponse,
    PerformanceComparisonSummary,
)
from app.domains.performance.benchmark_price_provider import BenchmarkPriceProvider
from app.domains.performance.buy_and_hold_baseline import StartPortfolioBuyAndHoldBaselineCalculator
from app.domains.performance.cashflow_matched_baseline import CashFlowMatchedBaselineCalculator
from app.domains.performance.repository import AccountPerformanceRepository
from app.domains.performance.service import AccountPerformanceService

DEFAULT_BASELINES = [
    PerformanceBaselineType.SPY_CASHFLOW_MATCHED,
    PerformanceBaselineType.QQQ_CASHFLOW_MATCHED,
    PerformanceBaselineType.START_PORTFOLIO_BUY_AND_HOLD,
]

BENCHMARK_SYMBOL_BY_BASELINE = {
    PerformanceBaselineType.SPY_CASHFLOW_MATCHED: "SPY",
    PerformanceBaselineType.QQQ_CASHFLOW_MATCHED: "QQQ",
}


class PerformanceBaselineService:
    def __init__(
        self,
        account_performance_service: AccountPerformanceService,
        repository: AccountPerformanceRepository,
        price_provider: BenchmarkPriceProvider,
        cashflow_matched_calculator: CashFlowMatchedBaselineCalculator | None = None,
        buy_and_hold_calculator: StartPortfolioBuyAndHoldBaselineCalculator | None = None,
    ) -> None:
        self.account_performance_service = account_performance_service
        self.repository = repository
        self.price_provider = price_provider
        self.cashflow_matched_calculator = cashflow_matched_calculator or CashFlowMatchedBaselineCalculator()
        self.buy_and_hold_calculator = buy_and_hold_calculator or StartPortfolioBuyAndHoldBaselineCalculator()

    def get_series(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        base_index: float = 100.0,
        baselines: list[PerformanceBaselineType] | None = None,
    ) -> PerformanceComparisonSeriesResponse:
        selected = baselines or list(DEFAULT_BASELINES)
        actual_response = self.account_performance_service.get_series(
            start_date=start_date,
            end_date=end_date,
            base_index=base_index,
        )
        actual_series = actual_response.series
        effective_start = actual_response.summary.start_date
        effective_end = actual_response.summary.end_date

        series: dict = {PerformanceBaselineType.ACTUAL_ACCOUNT: actual_series}
        baseline_summaries: list[BaselinePerformanceSummary] = []
        if actual_series and effective_start and effective_end:
            for baseline_type in selected:
                if baseline_type in BENCHMARK_SYMBOL_BY_BASELINE:
                    baseline_series, summary = self._cashflow_matched(
                        baseline_type=baseline_type,
                        start_date=effective_start,
                        end_date=effective_end,
                        base_index=base_index,
                        actual_series=actual_series,
                    )
                elif baseline_type == PerformanceBaselineType.START_PORTFOLIO_BUY_AND_HOLD:
                    baseline_series, summary = self._buy_and_hold(
                        start_date=effective_start,
                        end_date=effective_end,
                        base_index=base_index,
                        actual_series=actual_series,
                    )
                else:
                    continue
                series[baseline_type] = baseline_series
                baseline_summaries.append(summary)

        summary = self._comparison_summary(
            actual=actual_response.summary,
            baselines=baseline_summaries,
        )
        return PerformanceComparisonSeriesResponse(
            summary=summary,
            series=series,
            methodology=PerformanceComparisonMethodology(base_index=base_index),
        )

    def get_summary(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        base_index: float = 100.0,
        baselines: list[PerformanceBaselineType] | None = None,
    ) -> PerformanceComparisonSummary:
        return self.get_series(
            start_date=start_date,
            end_date=end_date,
            base_index=base_index,
            baselines=baselines,
        ).summary

    def _cashflow_matched(
        self,
        *,
        baseline_type: PerformanceBaselineType,
        start_date: str,
        end_date: str,
        base_index: float,
        actual_series: list,
    ):
        symbol = BENCHMARK_SYMBOL_BY_BASELINE[baseline_type]
        prices, limitations = self.price_provider.get_close_prices(symbol, start_date=start_date, end_date=end_date)
        return self.cashflow_matched_calculator.build(
            baseline_type=baseline_type,
            actual_series=actual_series,
            prices_by_date=prices,
            base_index=base_index,
            benchmark_symbol=symbol,
            provider_limitations=limitations,
        )

    def _buy_and_hold(
        self,
        *,
        start_date: str,
        end_date: str,
        base_index: float,
        actual_series: list,
    ):
        limitations: list[str] = []
        position_date = self.repository.latest_position_report_date_on_or_before(start_date)
        holdings = self.repository.list_positions_for_report_date(position_date) if position_date else []
        if position_date and position_date != start_date:
            limitations.append("start_portfolio_snapshot_lookback_used")
        symbols = sorted({str(item.get("symbol") or "").upper() for item in holdings if item.get("symbol")})
        prices_by_symbol, price_limitations = self.price_provider.get_close_prices_for_symbols(
            symbols,
            start_date=start_date,
            end_date=end_date,
        )
        start_cash = _estimate_start_cash(actual_series[0].nav, holdings, prices_by_symbol, start_date)
        return self.buy_and_hold_calculator.build(
            actual_series=actual_series,
            holdings=holdings,
            prices_by_symbol=prices_by_symbol,
            base_index=base_index,
            start_cash=start_cash,
            provider_limitations=[*limitations, *price_limitations],
        )

    def _comparison_summary(
        self,
        *,
        actual,
        baselines: list[BaselinePerformanceSummary],
    ) -> PerformanceComparisonSummary:
        excess_returns: dict[str, float | None] = {}
        value_added: dict[str, float | None] = {}
        for baseline in baselines:
            suffix = baseline.baseline_type.value
            actual_return = actual.twr_total_return
            excess_returns[f"vs_{suffix}"] = _diff(actual_return, baseline.total_return)
            value_added[f"vs_{suffix}"] = _diff(actual.end_nav, baseline.end_nav)

        limitations = _dedupe([*actual.data_limitations, *[item for baseline in baselines for item in baseline.data_limitations]])
        effective_qualities = {
            _effective_quality(actual.data_quality, actual.data_limitations),
            *[_effective_quality(baseline.data_quality, baseline.data_limitations) for baseline in baselines],
        }
        quality_limitations = [item for item in limitations if not _is_informational_limitation(item)]
        if "complete" in effective_qualities and len(effective_qualities) == 1 and not quality_limitations:
            data_quality = "complete"
        elif effective_qualities == {"missing"}:
            data_quality = "missing"
        else:
            data_quality = "partial"

        return PerformanceComparisonSummary(
            start_date=actual.start_date,
            end_date=actual.end_date,
            actual=actual,
            baselines=baselines,
            excess_returns=excess_returns,
            value_added=value_added,
            data_quality=data_quality,
            data_limitations=limitations,
        )


def parse_baseline_types(value: list[str] | None) -> list[PerformanceBaselineType] | None:
    if not value:
        return None
    raw_items: list[str] = []
    for item in value:
        raw_items.extend(part.strip() for part in item.split(",") if part.strip())
    if not raw_items:
        return None
    parsed: list[PerformanceBaselineType] = []
    for item in raw_items:
        baseline_type = PerformanceBaselineType(item)
        if baseline_type == PerformanceBaselineType.ACTUAL_ACCOUNT:
            continue
        parsed.append(baseline_type)
    return list(dict.fromkeys(parsed))


def _diff(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return round(float(left) - float(right), 6)


def _estimate_start_cash(
    start_nav: float | None,
    holdings: list[dict],
    prices_by_symbol: dict[str, dict[str, float]],
    start_date: str,
) -> float:
    if start_nav is None:
        return 0.0
    positions_value = 0.0
    has_price = False
    for holding in holdings:
        symbol = str(holding.get("symbol") or "").upper()
        quantity = _to_float(holding.get("quantity")) or 0.0
        price = prices_by_symbol.get(symbol, {}).get(start_date)
        if price is None or price <= 0:
            price = _nearest_price_on_or_after(start_date, prices_by_symbol.get(symbol, {}))
        if price is None or price <= 0:
            continue
        has_price = True
        positions_value += quantity * price
    if not has_price:
        return 0.0
    return float(start_nav) - positions_value


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _nearest_price_on_or_after(start_date: str, prices_by_date: dict[str, float]) -> float | None:
    candidates = [
        (report_date, price)
        for report_date, price in prices_by_date.items()
        if report_date >= start_date and price > 0
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda item: item[0])[1]


def _effective_quality(data_quality: str, limitations: list[str]) -> str:
    if data_quality != "partial":
        return data_quality
    if limitations and all(_is_informational_limitation(item) for item in limitations):
        return "complete"
    return data_quality


def _is_informational_limitation(value: str) -> bool:
    return value == "nav_yesterday_missing" or value.startswith(
        "benchmark_start_price_shifted_to_next_trading_day:"
    ) or value.startswith("start_portfolio_price_shifted_to_next_trading_day:")
