from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from app.clients.es_client import ESIndexNotFoundError, ElasticsearchClient
from app.core.config import Settings
from app.domains.portfolio_manager.decision_orchestrator.schemas import PortfolioAutoDecisionItem
from app.domains.portfolio_manager.evaluation.schemas import ForwardPriceMetrics, HORIZON_DAYS
from app.domains.portfolio_manager.universe.repository import normalize_universe_symbol
from app.domains.portfolio_manager.watchtower.scanner import symbol_candidates

ADD_LIKE_ACTIONS = {"add", "add_small", "add_batch", "add_on_pullback", "add_right_side", "buy", "build_position", "accumulate"}
REDUCE_LIKE_ACTIONS = {"reduce", "reduce_batch", "reduce_now", "trim_on_rebound", "sell", "sell_thesis_broken"}
HOLD_LIKE_ACTIONS = {"hold", "hold_no_add", "wait", "watchlist", "avoid", "panic_blocked", "no_action"}


@dataclass(frozen=True)
class ForwardPriceBar:
    symbol: str
    report_date: date
    close_price: float
    high_price: float | None = None
    low_price: float | None = None


class PriceForwardReturnProvider:
    def __init__(self, es_client: ElasticsearchClient, settings: Settings) -> None:
        self.es_client = es_client
        self.settings = settings

    def evaluate_forward_return(
        self,
        *,
        symbol: str,
        display_symbol: str | None,
        source_date: str,
        horizon: str,
        benchmark_symbol: str = "SPY",
    ) -> ForwardPriceMetrics:
        horizon_days = HORIZON_DAYS[horizon]
        limitations: list[str] = []
        source_dt = _parse_date(source_date)
        if source_dt is None:
            return ForwardPriceMetrics(price_data_status="missing", benchmark_symbol=benchmark_symbol, data_limitations=["source_date_invalid"])
        bars, symbol_limitations = self._bars_for_symbol(symbol, display_symbol, source_dt, horizon_days)
        limitations.extend(symbol_limitations)
        if not bars:
            return ForwardPriceMetrics(price_data_status="missing", benchmark_symbol=benchmark_symbol, data_limitations=limitations)
        metrics = _metrics_from_bars(bars, source_dt, horizon_days, horizon, limitations)
        bench_bars, bench_limitations = self._bars_for_symbol(benchmark_symbol, benchmark_symbol, source_dt, horizon_days)
        if bench_bars:
            benchmark = _metrics_from_bars(bench_bars, source_dt, horizon_days, horizon, [])
            metrics.benchmark_return = benchmark.forward_return
            if metrics.forward_return is not None and benchmark.forward_return is not None:
                metrics.benchmark_relative_return = round(metrics.forward_return - benchmark.forward_return, 6)
        else:
            metrics.data_limitations.extend(bench_limitations or [f"benchmark_price_missing:{benchmark_symbol}"])
            if metrics.price_data_status == "ok":
                metrics.price_data_status = "partial"
        metrics.benchmark_symbol = benchmark_symbol
        metrics.data_limitations = _dedupe(metrics.data_limitations)
        return metrics

    def _bars_for_symbol(self, symbol: str, display_symbol: str | None, source_date: date, horizon_days: int) -> tuple[list[ForwardPriceBar], list[str]]:
        end = source_date + timedelta(days=max(370, horizon_days * 3 + 30))
        for candidate in symbol_candidates(symbol, display_symbol):
            bars = self._fetch_bars(candidate, source_date, end)
            if bars:
                return bars, []
        normalized = normalize_universe_symbol(symbol) or symbol
        return [], [f"price_history_missing:{normalized}"]

    def _fetch_bars(self, symbol: str, start_date: date, end_date: date) -> list[ForwardPriceBar]:
        try:
            response = self.es_client.search(
                index=self.settings.es_price_history_index,
                body={
                    "query": {"bool": {"filter": [{"term": {"symbol": symbol}}, {"range": {"report_date": {"gte": start_date.isoformat(), "lte": end_date.isoformat()}}}]}},
                    "sort": [{"report_date": {"order": "asc", "missing": "_last"}}],
                    "size": 400,
                    "_source": ["symbol", "report_date", "close_price", "high_price", "low_price"],
                },
            )
        except ESIndexNotFoundError:
            return []
        bars: list[ForwardPriceBar] = []
        for hit in response.get("hits", {}).get("hits", []):
            source = dict(hit.get("_source") or {})
            report_date = _parse_date(source.get("report_date"))
            close = _float(source.get("close_price"))
            if report_date is None or close is None or close <= 0:
                continue
            bars.append(ForwardPriceBar(symbol=str(source.get("symbol") or symbol), report_date=report_date, close_price=close, high_price=_float(source.get("high_price")), low_price=_float(source.get("low_price"))))
        return bars


class PortfolioAutoDecisionOutcomeEvaluator:
    def evaluate(
        self,
        *,
        item: PortfolioAutoDecisionItem,
        horizon: str,
        price_metrics: ForwardPriceMetrics,
        evaluation_date: str,
    ) -> dict:
        action = str(item.decision_summary.get("final_action") or "").lower()
        result = _base_result(
            evaluation_date=evaluation_date,
            source_type="auto_decision_item",
            source_id=item.id,
            source_run_id=item.run_id,
            symbol=item.symbol,
            display_symbol=item.display_symbol,
            horizon=horizon,
            source_date=item.run_date,
            source_status=item.selection_status,
            source_action=action or None,
            source_snapshot=item.scan_snapshot,
            price_metrics=price_metrics,
        )
        if item.selection_status == "failed":
            result.update(evaluation_label="inconclusive", evaluation_reason="Auto Decision failed，不能做市场表现强归因。")
            result["data_limitations"] = _dedupe([*result["data_limitations"], "auto_decision_failed"])
            return result
        if item.selection_status != "completed" or not item.decision_id or not action:
            result.update(evaluation_label="inconclusive", evaluation_reason="Auto Decision 缺少 completed decision_id 或 final_action，暂不归因。")
            return result
        if price_metrics.price_data_status in {"pending", "missing"}:
            result.update(evaluation_label="pending", evaluation_reason="价格数据不足，等待未来窗口完成。")
            return result
        forward = price_metrics.forward_return
        relative = price_metrics.benchmark_relative_return
        drawdown = price_metrics.max_drawdown
        label, reason = _auto_label(action, forward, relative, drawdown)
        result.update(evaluation_label=label, evaluation_reason=reason)
        return result


def _metrics_from_bars(bars: list[ForwardPriceBar], source_date: date, horizon_days: int, horizon: str, limitations: list[str]) -> ForwardPriceMetrics:
    data_limitations = list(limitations)
    start = bars[0]
    if start.report_date != source_date:
        data_limitations.append(f"source_date_price_shifted:{source_date.isoformat()}->{start.report_date.isoformat()}")
    if start.close_price <= 0:
        return ForwardPriceMetrics(price_data_status="missing", benchmark_symbol="SPY", data_limitations=[*data_limitations, "start_price_invalid"])
    if len(bars) <= horizon_days:
        return ForwardPriceMetrics(price_data_status="pending", start_price=start.close_price, benchmark_symbol="SPY", data_limitations=[*data_limitations, f"insufficient_forward_price_history:{horizon}"])
    window = bars[: horizon_days + 1]
    end = window[-1]
    highs = [(bar.high_price if bar.high_price is not None else bar.close_price) for bar in window]
    lows = [(bar.low_price if bar.low_price is not None else bar.close_price) for bar in window]
    forward_return = (end.close_price / start.close_price) - 1.0
    max_runup = (max(highs) / start.close_price) - 1.0
    max_drawdown = (min(lows) / start.close_price) - 1.0
    return ForwardPriceMetrics(
        price_data_status="ok",
        start_price=round(start.close_price, 6),
        end_price=round(end.close_price, 6),
        forward_return=round(forward_return, 6),
        max_drawdown=round(max_drawdown, 6),
        max_runup=round(max_runup, 6),
        benchmark_symbol="SPY",
        data_limitations=data_limitations,
    )


def _auto_label(action: str, forward: float | None, relative: float | None, drawdown: float | None) -> tuple[str, str]:
    forward = forward or 0.0
    relative = relative or 0.0
    drawdown = drawdown or 0.0
    if action in ADD_LIKE_ACTIONS:
        if relative > 0 and drawdown > -0.10:
            return "good_action", "add-like 摘要后跑赢 benchmark 且回撤可控。"
        if forward <= -0.08 or drawdown <= -0.12:
            return "bad_action", "add-like 摘要后出现大跌或较大回撤。"
    elif action in REDUCE_LIKE_ACTIONS:
        if relative <= -0.05 or forward < -0.05:
            return "risk_avoided", "reduce-like 摘要后标的走弱，说明风险复核有价值。"
        if forward >= 0.08 and relative > 0.05:
            return "bad_action", "reduce-like 摘要后显著上涨，可能过早减仓/卖出。"
    elif action in HOLD_LIKE_ACTIONS:
        if forward >= 0.10 and relative > 0.05:
            return "missed_opportunity", "hold-like 摘要后显著上涨，可能错过机会。"
        if forward <= -0.08 or drawdown <= -0.12:
            return "risk_avoided", "hold-like 摘要后下跌或回撤，保守处理有风险控制价值。"
    return "inconclusive", "市场反馈不构成强结论，需要结合更多 horizon 和组合上下文。"


def _base_result(**kwargs) -> dict:
    price_metrics: ForwardPriceMetrics = kwargs.pop("price_metrics")
    horizon = kwargs["horizon"]
    return {
        **kwargs,
        "id": evaluation_result_id(kwargs["source_type"], kwargs["source_id"], kwargs.get("symbol"), horizon),
        "horizon_days": HORIZON_DAYS[horizon],
        "price_data_status": price_metrics.price_data_status,
        "start_price": price_metrics.start_price,
        "end_price": price_metrics.end_price,
        "forward_return": price_metrics.forward_return,
        "max_drawdown": price_metrics.max_drawdown,
        "max_runup": price_metrics.max_runup,
        "benchmark_symbol": price_metrics.benchmark_symbol,
        "benchmark_return": price_metrics.benchmark_return,
        "benchmark_relative_return": price_metrics.benchmark_relative_return,
        "evaluation_label": "inconclusive",
        "evaluation_reason": "",
        "metric_summary": metric_summary(price_metrics),
        "data_limitations": list(price_metrics.data_limitations),
    }


def evaluation_result_id(source_type: str, source_id: str, symbol: str | None, horizon: str) -> str:
    return f"portfolio_eval:{source_type}:{source_id}:{symbol or 'none'}:{horizon}"


def metric_summary(metrics: ForwardPriceMetrics) -> dict[str, float | None]:
    abs_forward = abs(metrics.forward_return) if metrics.forward_return is not None else None
    volatility = max(abs(metrics.max_drawdown or 0.0), abs(metrics.max_runup or 0.0)) if metrics.price_data_status in {"ok", "partial"} else None
    attention_score = round(min(100.0, (volatility or 0.0) * 600 + (abs_forward or 0.0) * 400), 2) if volatility is not None else None
    return {"volatility_after_signal": volatility, "abs_forward_return": abs_forward, "attention_value_score": attention_score}


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    try:
        return float(value) if value not in {None, ""} else None
    except (TypeError, ValueError):
        return None


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
