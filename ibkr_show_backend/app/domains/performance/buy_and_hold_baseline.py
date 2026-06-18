from app.domains.performance.baseline_metrics import build_baseline_summary, missing_baseline_summary
from app.domains.performance.baseline_schemas import (
    BaselinePerformancePoint,
    BaselinePerformanceSummary,
    PerformanceBaselineType,
)
from app.domains.performance.schemas import AccountPerformancePoint


class StartPortfolioBuyAndHoldBaselineCalculator:
    def build(
        self,
        *,
        actual_series: list[AccountPerformancePoint],
        holdings: list[dict],
        prices_by_symbol: dict[str, dict[str, float]],
        base_index: float = 100.0,
        start_cash: float = 0.0,
        provider_limitations: list[str] | None = None,
    ) -> tuple[list[BaselinePerformancePoint], BaselinePerformanceSummary]:
        baseline_type = PerformanceBaselineType.START_PORTFOLIO_BUY_AND_HOLD
        label = "起始组合买入并持有基准"
        limitations = list(provider_limitations or [])
        metadata: dict[str, object] = {}
        if not actual_series:
            return [], missing_baseline_summary(
                baseline_type=baseline_type,
                label=label,
                start_date=None,
                end_date=None,
                data_limitations=[*limitations, "actual_account_series_missing"],
            )
        if not holdings:
            return [], missing_baseline_summary(
                baseline_type=baseline_type,
                label=label,
                start_date=actual_series[0].date,
                end_date=actual_series[-1].date,
                data_limitations=[*limitations, "start_portfolio_holdings_missing"],
            )

        normalized_holdings = [
            {"symbol": str(item.get("symbol") or "").upper(), "quantity": _to_float(item.get("quantity")) or 0.0}
            for item in holdings
            if str(item.get("symbol") or "").strip() and (_to_float(item.get("quantity")) or 0.0) != 0
        ]
        metadata = _holdings_metadata(normalized_holdings)
        if not normalized_holdings:
            return [], missing_baseline_summary(
                baseline_type=baseline_type,
                label=label,
                start_date=actual_series[0].date,
                end_date=actual_series[-1].date,
                data_limitations=[*limitations, "start_portfolio_holdings_missing"],
                metadata=metadata,
            )

        cash = float(start_cash)
        return_index = float(base_index)
        previous_nav: float | None = None
        last_prices, shifted_start_symbols = _initial_prices_from_next_available_date(
            prices_by_symbol,
            [item["symbol"] for item in normalized_holdings],
            actual_series[0].date,
            limitations,
        )
        missing_prices = 0
        series: list[BaselinePerformancePoint] = []

        for index, actual in enumerate(actual_series):
            data_limitations: list[str] = []
            data_quality = "complete"
            positions_value = 0.0
            for holding in normalized_holdings:
                symbol = holding["symbol"]
                price = prices_by_symbol.get(symbol, {}).get(actual.date)
                if price is None or price <= 0:
                    price = last_prices.get(symbol)
                    if price is not None and not (index == 0 and symbol in shifted_start_symbols):
                        missing_prices += 1
                        data_quality = "partial"
                        data_limitations.append(f"price_forward_filled:{symbol}")
                else:
                    last_prices[symbol] = price
                if price is None or price <= 0:
                    data_quality = "missing"
                    data_limitations.append(f"price_missing:{symbol}")
                    continue
                positions_value += holding["quantity"] * price

            if index > 0 and actual.net_cash_flow:
                cash += actual.net_cash_flow
                if cash < 0:
                    data_quality = "partial"
                    data_limitations.append("buy_hold_cash_insufficient_for_withdrawal")

            nav = positions_value + cash
            daily_return = None
            if index > 0:
                if previous_nav is None or previous_nav <= 0:
                    data_quality = "missing"
                    data_limitations.append("buy_hold_nav_yesterday_missing")
                else:
                    daily_return = (nav - previous_nav - actual.net_cash_flow) / previous_nav
                    return_index *= 1.0 + daily_return

            series.append(
                BaselinePerformancePoint(
                    date=actual.date,
                    baseline_type=baseline_type,
                    nav=_round(nav),
                    net_cash_flow=_round(actual.net_cash_flow),
                    daily_return=_round(daily_return, 8),
                    return_index=_round(return_index),
                    benchmark_price=None,
                    units=None,
                    cash=_round(cash) or 0.0,
                    data_quality=data_quality,
                    data_limitations=_dedupe(data_limitations),
                )
            )
            previous_nav = nav

        if missing_prices / max(len(actual_series) * len(normalized_holdings), 1) > 0.2:
            limitations.append("buy_hold_price_missing_high")
        summary = build_baseline_summary(
            baseline_type=baseline_type,
            label=label,
            series=series,
            data_limitations=limitations,
            metadata=metadata,
        )
        return series, summary


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _round(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _holdings_metadata(holdings: list[dict[str, object]]) -> dict[str, object]:
    return {
        "start_portfolio_symbols": [str(item["symbol"]) for item in holdings],
        "start_portfolio_holdings": [
            {"symbol": str(item["symbol"]), "quantity": float(item["quantity"])}
            for item in holdings
        ],
    }


def _initial_prices_from_next_available_date(
    prices_by_symbol: dict[str, dict[str, float]],
    symbols: list[str],
    start_date: str,
    limitations: list[str],
) -> tuple[dict[str, float], set[str]]:
    initial: dict[str, float] = {}
    shifted_symbols: set[str] = set()
    for symbol in symbols:
        if prices_by_symbol.get(symbol, {}).get(start_date):
            continue
        shifted = _nearest_available_price_on_or_after(start_date, prices_by_symbol.get(symbol, {}))
        if shifted is None:
            continue
        shifted_date, price = shifted
        initial[symbol] = price
        shifted_symbols.add(symbol)
        limitations.append(f"start_portfolio_price_shifted_to_next_trading_day:{symbol}:{shifted_date}")
    return initial, shifted_symbols


def _nearest_available_price_on_or_after(start_date: str, prices_by_date: dict[str, float]) -> tuple[str, float] | None:
    candidates = [
        (report_date, price)
        for report_date, price in prices_by_date.items()
        if report_date >= start_date and price > 0
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda item: item[0])


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
