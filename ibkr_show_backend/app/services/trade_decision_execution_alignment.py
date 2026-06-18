from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from statistics import mean
from typing import Any

from app.clients.es_client import ESIndexNotFoundError, ElasticsearchClient
from app.core.config import Settings
from app.schemas.trade_decision import (
    TradeDecisionExecutionAlignmentItem,
    TradeDecisionExecutionAlignmentListResponse,
    TradeDecisionExecutionAlignmentSummary,
    TradeDecisionMatchedRealTrade,
)
from app.services.longbridge_service import normalize_longbridge_symbol
from app.services.trade_decision_outcome_replay import ADD_LIKE_ACTIONS, HOLD_LIKE_ACTIONS, REDUCE_LIKE_ACTIONS, action_group_for
from app.services.trade_decision_repository import TradeDecisionRepository
from app.services.trade_decision_shadow_backtest import TradeDecisionShadowBacktestService


@dataclass(frozen=True)
class AlignmentPriceBar:
    report_date: date
    close_price: float


class TradeDecisionExecutionAlignmentService:
    def __init__(
        self,
        repository: TradeDecisionRepository,
        es_client: ElasticsearchClient,
        settings: Settings,
        shadow_backtest_service: TradeDecisionShadowBacktestService | None = None,
    ) -> None:
        self.repository = repository
        self.es_client = es_client
        self.settings = settings
        self.shadow_backtest_service = shadow_backtest_service
        self.data_limitations: Counter[str] = Counter()

    def build_alignment(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        days: int = 180,
        symbol: str | None = None,
        decision_type: str | None = None,
        match_window_days: int = 5,
        include_same_day: bool = True,
        alignment_label: str | None = None,
        behavior_tag: str | None = None,
        limit: int = 1000,
    ) -> TradeDecisionExecutionAlignmentListResponse:
        end_date = end_date or datetime.now(timezone.utc).date()
        start_date = start_date or (end_date - timedelta(days=days))
        normalized_symbol = normalize_longbridge_symbol(symbol) if symbol else None
        decisions = self.repository.list_decisions_for_backtest(
            start_date=f"{start_date.isoformat()}T00:00:00+00:00",
            end_date=f"{end_date.isoformat()}T23:59:59+00:00",
            symbol=normalized_symbol,
            decision_type=decision_type,
            limit=limit,
        )
        trade_lookup = self._fetch_trade_lookup(
            start_date=start_date,
            end_date=end_date + timedelta(days=max(match_window_days + 20, 30)),
            symbols={str(doc.get("symbol") or "") for doc in decisions if str(doc.get("symbol") or "")},
        )
        price_cache: dict[str, list[AlignmentPriceBar]] = {}
        items = [
            self.evaluate_decision(
                doc,
                trade_lookup=trade_lookup,
                price_cache=price_cache,
                match_window_days=match_window_days,
                include_same_day=include_same_day,
                start_date=start_date,
                end_date=end_date,
            )
            for doc in decisions
        ]
        if alignment_label:
            items = [item for item in items if item.alignment_label == alignment_label]
        if behavior_tag:
            items = [item for item in items if behavior_tag in item.behavior_tags]
        summary = summarize_alignment(
            items,
            data_limitations=[key for key, _ in self.data_limitations.most_common(12)],
            shadow_summary=self._shadow_summary(
                start_date=start_date,
                end_date=end_date,
                days=days,
                symbol=symbol,
                decision_type=decision_type,
            ),
            real_account_return=self._real_account_return(start_date, end_date),
        )
        return TradeDecisionExecutionAlignmentListResponse(items=items, summary=summary)

    def get_alignment(self, decision_id: str, *, match_window_days: int = 5, include_same_day: bool = True) -> TradeDecisionExecutionAlignmentItem | None:
        doc = self.repository.get_decision(decision_id)
        if doc is None:
            return None
        decision_date = _decision_date(str(doc.get("created_at") or ""))
        start_date = decision_date or datetime.now(timezone.utc).date()
        trade_lookup = self._fetch_trade_lookup(
            start_date=start_date,
            end_date=start_date + timedelta(days=max(match_window_days + 20, 30)),
            symbols={str(doc.get("symbol") or "")},
        )
        return self.evaluate_decision(
            doc,
            trade_lookup=trade_lookup,
            price_cache={},
            match_window_days=match_window_days,
            include_same_day=include_same_day,
            start_date=start_date,
            end_date=start_date + timedelta(days=max(match_window_days + 20, 30)),
        )

    def evaluate_decision(
        self,
        doc: dict,
        *,
        trade_lookup: dict[str, list[dict]],
        price_cache: dict[str, list[AlignmentPriceBar]],
        match_window_days: int,
        include_same_day: bool,
        start_date: date,
        end_date: date,
    ) -> TradeDecisionExecutionAlignmentItem:
        symbol = str(doc.get("symbol") or "")
        decision_date = _decision_date(str(doc.get("created_at") or ""))
        final_action = str(doc.get("final_action") or doc.get("action") or "").strip().lower()
        action_group = action_group_for(final_action)
        price_bars = self._price_bars(symbol, start_date, end_date + timedelta(days=30), price_cache)
        window_dates = _trading_window(price_bars, decision_date, match_window_days, include_same_day)
        real_trades = _trades_in_window(trade_lookup, symbol, window_dates)
        aggregate = _aggregate_trades(real_trades)
        position_advice = _dict(doc.get("position_advice"))
        ai_assessment = _dict(doc.get("ai_policy_assessment"))
        suggested_cash = _float(position_advice.get("suggested_cash_amount"))
        suggested_target = _float(position_advice.get("suggested_target_position_pct"))
        suggested_adjustment = _float(position_advice.get("adjustment_pct"))
        fallback_notional = _fallback_notional(suggested_cash)
        return_5d = _forward_return(price_bars, decision_date, 5)
        return_20d = _forward_return(price_bars, decision_date, 20)
        label = _alignment_label(action_group, aggregate, fallback_notional)
        tags = _behavior_tags(
            label,
            action_group,
            final_action,
            aggregate,
            fallback_notional,
            return_20d,
        )
        estimates = _estimated_values(action_group, label, aggregate, fallback_notional, return_20d)
        first_trade_date = aggregate["first_trade_date"]
        delay = _execution_delay(price_bars, decision_date, first_trade_date)
        explanation = _explain(label, action_group, final_action, aggregate, delay)
        matched = [_matched_trade(item) for item in real_trades]
        return TradeDecisionExecutionAlignmentItem(
            decision_id=str(doc.get("id") or ""),
            symbol=symbol,
            decision_date=decision_date.isoformat() if decision_date else None,
            final_action=final_action or None,
            action_group=action_group,
            ai_position_stance=_str_or_none(ai_assessment.get("ai_position_stance")),
            ai_recommended_action_bias=_str_or_none(ai_assessment.get("recommended_action_bias")),
            suggested_target_position_pct=suggested_target,
            suggested_adjustment_pct=suggested_adjustment,
            suggested_cash_amount=suggested_cash,
            real_trade_side=aggregate["real_trade_side"],
            real_trade_count=aggregate["real_trade_count"],
            real_buy_notional=round(aggregate["real_buy_notional"], 6),
            real_sell_notional=round(aggregate["real_sell_notional"], 6),
            real_net_notional=round(aggregate["real_net_notional"], 6),
            real_weighted_avg_price=_round(aggregate["real_weighted_avg_price"]),
            first_real_trade_date=first_trade_date.isoformat() if first_trade_date else None,
            execution_delay_trading_days=delay,
            alignment_label=label,
            behavior_tags=tags,
            return_5d=return_5d,
            return_20d=return_20d,
            estimated_opportunity_cost=estimates["estimated_opportunity_cost"],
            estimated_avoided_loss=estimates["estimated_avoided_loss"],
            estimated_bad_override_cost=estimates["estimated_bad_override_cost"],
            estimated_good_override_value=estimates["estimated_good_override_value"],
            explanation=explanation,
            matched_trades=matched,
            data_limitations=[] if price_bars else [f"price_missing:{symbol}"],
        )

    def _fetch_trade_lookup(self, *, start_date: date, end_date: date, symbols: set[str]) -> dict[str, list[dict]]:
        if not symbols:
            return {}
        variants = sorted({variant for symbol in symbols for variant in _symbol_variants(symbol)})
        try:
            response = self.es_client.search(
                index=self.settings.es_trade_index,
                body={
                    "query": {
                        "bool": {
                            "filter": [
                                {"terms": {"symbol": variants}},
                                {"range": {"trade_date": {"gte": start_date.isoformat(), "lte": end_date.isoformat()}}},
                            ]
                        }
                    },
                    "sort": [{"trade_date": {"order": "asc"}}, {"date_time": {"order": "asc", "missing": "_last"}}],
                    "size": 10000,
                    "_source": [
                        "trade_date",
                        "date_time",
                        "symbol",
                        "buy_sell",
                        "quantity",
                        "trade_price",
                        "proceeds",
                        "ib_commission",
                        "fifo_pnl_realized",
                        "trade_id",
                        "transaction_id",
                    ],
                },
            )
        except ESIndexNotFoundError:
            self.data_limitations["real_trade_index_missing"] += 1
            return {}
        lookup: dict[str, list[dict]] = defaultdict(list)
        for hit in response.get("hits", {}).get("hits", []):
            source = _dict(hit.get("_source"))
            for variant in _symbol_variants(str(source.get("symbol") or "")):
                lookup[variant].append(source)
        return lookup

    def _price_bars(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        cache: dict[str, list[AlignmentPriceBar]],
    ) -> list[AlignmentPriceBar]:
        key = normalize_longbridge_symbol(symbol) if symbol else symbol
        if key in cache:
            return cache[key]
        for candidate in _symbol_variants(symbol):
            try:
                response = self.es_client.search(
                    index=self.settings.es_price_history_index,
                    body={
                        "query": {
                            "bool": {
                                "filter": [
                                    {"term": {"symbol": candidate}},
                                    {"range": {"report_date": {"gte": start_date.isoformat(), "lte": end_date.isoformat()}}},
                                ]
                            }
                        },
                        "sort": [{"report_date": {"order": "asc"}}],
                        "size": 10000,
                        "_source": ["report_date", "close_price"],
                    },
                )
            except ESIndexNotFoundError:
                self.data_limitations["price_history_index_missing"] += 1
                cache[key] = []
                return []
            bars = []
            for hit in response.get("hits", {}).get("hits", []):
                source = _dict(hit.get("_source"))
                report_date = _parse_date(source.get("report_date"))
                close = _float(source.get("close_price"))
                if report_date and close is not None and close > 0:
                    bars.append(AlignmentPriceBar(report_date=report_date, close_price=close))
            if bars:
                cache[key] = bars
                return bars
        self.data_limitations[f"price_missing:{symbol}"] += 1
        cache[key] = []
        return []

    def _real_account_return(self, start_date: date, end_date: date) -> float | None:
        try:
            response = self.es_client.search(
                index=self.settings.es_account_index,
                body={
                    "query": {"bool": {"filter": [{"range": {"report_date": {"gte": start_date.isoformat(), "lte": end_date.isoformat()}}}]}},
                    "sort": [{"report_date": {"order": "asc"}}],
                    "size": 10000,
                    "_source": ["report_date", "total_equity"],
                },
            )
        except ESIndexNotFoundError:
            self.data_limitations["real_account_nav_unavailable"] += 1
            return None
        values = [_float(hit.get("_source", {}).get("total_equity")) for hit in response.get("hits", {}).get("hits", [])]
        values = [item for item in values if item is not None and item > 0]
        if len(values) < 2:
            self.data_limitations["real_account_nav_unavailable"] += 1
            return None
        return _round(values[-1] / values[0] - 1.0)

    def _shadow_summary(
        self,
        *,
        start_date: date,
        end_date: date,
        days: int,
        symbol: str | None,
        decision_type: str | None,
    ) -> dict:
        if self.shadow_backtest_service is None:
            return {}
        try:
            response = self.shadow_backtest_service.run_backtest(
                start_date=start_date,
                end_date=end_date,
                days=days,
                symbol=symbol,
                decision_type=decision_type,
                include_detail=False,
            )
        except Exception:
            self.data_limitations["shadow_backtest_unavailable"] += 1
            return {}
        return response.summary.model_dump()


def summarize_alignment(
    items: list[TradeDecisionExecutionAlignmentItem],
    *,
    data_limitations: list[str],
    shadow_summary: dict | None,
    real_account_return: float | None,
) -> TradeDecisionExecutionAlignmentSummary:
    labels = Counter(item.alignment_label for item in items)
    symbols = Counter(item.symbol for item in items)
    actions = Counter(item.final_action or "unknown" for item in items)
    groups = Counter(item.action_group for item in items)
    biases = Counter(item.ai_recommended_action_bias or "unknown" for item in items)
    tags = Counter(tag for item in items for tag in item.behavior_tags)
    delays = [item.execution_delay_trading_days for item in items if item.execution_delay_trading_days is not None]
    evaluated = [item for item in items if item.alignment_label != "unknown"]
    aligned_count = labels["followed"] + labels["partially_followed"] + labels["no_trade_expected"]
    opportunity = sum(item.estimated_opportunity_cost for item in items)
    avoided = sum(item.estimated_avoided_loss for item in items)
    bad_override = sum(item.estimated_bad_override_cost for item in items)
    good_override = sum(item.estimated_good_override_value for item in items)
    net_behavior_value = good_override + avoided - opportunity - bad_override
    shadow_summary = shadow_summary or {}
    shadow_total_return = _float(shadow_summary.get("total_return"))
    behavior_gap = _round(shadow_total_return - real_account_return) if shadow_total_return is not None and real_account_return is not None else None
    if real_account_return is None and "real_account_nav_unavailable" not in data_limitations:
        data_limitations.append("real_account_nav_unavailable")
    return TradeDecisionExecutionAlignmentSummary(
        version="trade_decision_execution_alignment_v1",
        total_decisions=len(items),
        matched_decisions=sum(1 for item in items if item.real_trade_count > 0),
        evaluated_decisions=len(evaluated),
        followed_count=labels["followed"],
        partially_followed_count=labels["partially_followed"],
        ignored_count=labels["ignored"],
        contradicted_count=labels["contradicted"],
        over_executed_count=labels["over_executed"],
        no_trade_expected_count=labels["no_trade_expected"],
        alignment_rate=_rate(aligned_count, len(evaluated)),
        contradiction_rate=_rate(labels["contradicted"], len(evaluated)),
        ignored_add_signal_count=tags["ignored_add_signal"],
        ignored_reduce_signal_count=tags["ignored_reduce_signal"],
        manual_override_count=tags["manual_contrarian_buy"] + tags["manual_contrarian_sell"],
        good_override_count=tags["good_override"],
        bad_override_count=tags["bad_override"],
        estimated_opportunity_cost_total=round(opportunity, 6),
        estimated_avoided_loss_total=round(avoided, 6),
        estimated_bad_override_cost_total=round(bad_override, 6),
        estimated_good_override_value_total=round(good_override, 6),
        net_behavior_value=round(net_behavior_value, 6),
        avg_execution_delay_days=round(mean(delays), 4) if delays else None,
        shadow_total_return=shadow_total_return,
        shadow_max_drawdown=_float(shadow_summary.get("max_drawdown")),
        shadow_sharpe=_float(shadow_summary.get("sharpe_ratio")),
        real_account_return_estimate=real_account_return,
        behavior_gap_estimate=behavior_gap,
        execution_gap_summary={
            "shadow_vs_real_return_gap": behavior_gap,
            "net_behavior_value": round(net_behavior_value, 6),
        },
        by_symbol=_top(symbols),
        by_final_action=_top(actions),
        by_action_group=_top(groups),
        by_ai_recommended_action_bias=_top(biases),
        by_behavior_tag=_top(tags),
        top_missed_opportunities=sorted(items, key=lambda item: item.estimated_opportunity_cost, reverse=True)[:5],
        top_bad_overrides=sorted(items, key=lambda item: item.estimated_bad_override_cost, reverse=True)[:5],
        top_good_overrides=sorted(items, key=lambda item: item.estimated_good_override_value, reverse=True)[:5],
        top_good_discipline=[item for item in items if "good_discipline" in item.behavior_tags][:5],
        top_agent_bad_follow=[item for item in items if "bad_follow" in item.behavior_tags][:5],
        generated_at=datetime.now(timezone.utc).isoformat(),
        data_limitations=data_limitations,
    )


def _alignment_label(action_group: str, aggregate: dict, suggested_notional: float) -> str:
    buy = aggregate["real_buy_notional"]
    sell = aggregate["real_sell_notional"]
    if action_group == "add_like":
        if sell > 0 and sell >= buy:
            return "contradicted"
        if buy <= 0:
            return "ignored"
        if suggested_notional > 0 and buy < suggested_notional * 0.3:
            return "partially_followed"
        if suggested_notional > 0 and buy > suggested_notional * 1.5:
            return "over_executed"
        return "followed"
    if action_group == "reduce_like":
        if buy > 0 and buy >= sell:
            return "contradicted"
        if sell <= 0:
            return "ignored"
        if suggested_notional > 0 and sell < suggested_notional * 0.3:
            return "partially_followed"
        if suggested_notional > 0 and sell > suggested_notional * 1.5:
            return "over_executed"
        return "followed"
    if action_group == "hold_like":
        if buy <= 0 and sell <= 0:
            return "no_trade_expected"
        return "contradicted"
    return "unknown"


def _behavior_tags(
    label: str,
    action_group: str,
    final_action: str,
    aggregate: dict,
    suggested_notional: float,
    return_20d: float | None,
) -> list[str]:
    tags: list[str] = []
    if label == "ignored" and action_group == "add_like":
        tags.append("ignored_add_signal")
    if label == "ignored" and action_group == "reduce_like":
        tags.append("ignored_reduce_signal")
    if label == "contradicted" and aggregate["real_buy_notional"] > aggregate["real_sell_notional"]:
        tags.append("manual_contrarian_buy")
    if label == "contradicted" and aggregate["real_sell_notional"] >= aggregate["real_buy_notional"] and aggregate["real_sell_notional"] > 0:
        tags.append("manual_contrarian_sell")
    if label == "over_executed":
        tags.append("over_sized_execution")
    if label == "partially_followed":
        tags.append("under_sized_execution")
    if label in {"followed", "partially_followed"} and return_20d is not None:
        if (action_group == "add_like" and return_20d > 0) or (action_group == "reduce_like" and return_20d < 0):
            tags.append("good_discipline")
        elif (action_group == "add_like" and return_20d < 0) or (action_group == "reduce_like" and return_20d > 0):
            tags.append("bad_follow")
    if label == "contradicted" and return_20d is not None:
        buy_override = aggregate["real_buy_notional"] > aggregate["real_sell_notional"]
        sell_override = aggregate["real_sell_notional"] > aggregate["real_buy_notional"]
        if (buy_override and return_20d > 0) or (sell_override and return_20d < 0):
            tags.append("good_override")
        if (buy_override and return_20d < 0) or (sell_override and return_20d > 0):
            tags.append("bad_override")
    if final_action == "panic_blocked" and aggregate["real_sell_notional"] > 0:
        tags.append("panic_sell_against_gate")
    if action_group in {"add_like", "hold_like"} and aggregate["real_sell_notional"] > 0 and return_20d is not None and return_20d > 0:
        tags.append("premature_trim")
    return tags


def _estimated_values(action_group: str, label: str, aggregate: dict, fallback_notional: float, return_20d: float | None) -> dict[str, float]:
    result = {
        "estimated_opportunity_cost": 0.0,
        "estimated_avoided_loss": 0.0,
        "estimated_bad_override_cost": 0.0,
        "estimated_good_override_value": 0.0,
    }
    if return_20d is None:
        return result
    if action_group == "add_like" and label == "ignored":
        if return_20d > 0:
            result["estimated_opportunity_cost"] = round(fallback_notional * return_20d, 6)
        elif return_20d < 0:
            result["estimated_avoided_loss"] = round(fallback_notional * abs(return_20d), 6)
    if action_group == "reduce_like" and label == "ignored" and return_20d < 0:
        result["estimated_opportunity_cost"] = round(fallback_notional * abs(return_20d), 6)
    if action_group == "hold_like" and label == "contradicted" and aggregate["real_buy_notional"] > 0:
        if return_20d < 0:
            result["estimated_bad_override_cost"] = round(aggregate["real_buy_notional"] * abs(return_20d), 6)
        elif return_20d > 0:
            result["estimated_good_override_value"] = round(aggregate["real_buy_notional"] * return_20d, 6)
    return result


def _aggregate_trades(trades: list[dict]) -> dict:
    buy_notional = 0.0
    sell_notional = 0.0
    buy_qty = 0.0
    sell_qty = 0.0
    first_date: date | None = None
    for trade in trades:
        side = _trade_side(trade.get("buy_sell"))
        quantity = abs(_float(trade.get("quantity")) or 0.0)
        price = _float(trade.get("trade_price")) or 0.0
        notional = abs(_float(trade.get("proceeds")) or quantity * price)
        trade_date = _parse_date(trade.get("trade_date"))
        if first_date is None or (trade_date and trade_date < first_date):
            first_date = trade_date
        if side == "buy":
            buy_notional += notional
            buy_qty += quantity
        elif side == "sell":
            sell_notional += notional
            sell_qty += quantity
    weighted_notional = buy_notional + sell_notional
    weighted_qty = buy_qty + sell_qty
    real_side = "none"
    if buy_notional > 0 and sell_notional > 0:
        real_side = "mixed"
    elif buy_notional > 0:
        real_side = "buy"
    elif sell_notional > 0:
        real_side = "sell"
    return {
        "real_trade_count": len(trades),
        "real_trade_side": real_side,
        "real_buy_notional": buy_notional,
        "real_sell_notional": sell_notional,
        "real_net_notional": buy_notional - sell_notional,
        "real_weighted_avg_price": weighted_notional / weighted_qty if weighted_qty > 0 else None,
        "first_trade_date": first_date,
    }


def _matched_trade(trade: dict) -> TradeDecisionMatchedRealTrade:
    quantity = abs(_float(trade.get("quantity")) or 0.0)
    price = _float(trade.get("trade_price"))
    notional = abs(_float(trade.get("proceeds")) or quantity * (price or 0.0))
    return TradeDecisionMatchedRealTrade(
        trade_date=_str_or_none(trade.get("trade_date")),
        date_time=_str_or_none(trade.get("date_time")),
        symbol=str(trade.get("symbol") or ""),
        side=_trade_side(trade.get("buy_sell")),
        quantity=quantity,
        trade_price=price,
        notional=round(notional, 6),
        commission=_float(trade.get("ib_commission")),
        fifo_pnl_realized=_float(trade.get("fifo_pnl_realized")),
        trade_id=_str_or_none(trade.get("trade_id") or trade.get("transaction_id")),
    )


def _trades_in_window(lookup: dict[str, list[dict]], symbol: str, window_dates: set[date]) -> list[dict]:
    trades = []
    for variant in _symbol_variants(symbol):
        for trade in lookup.get(variant, []):
            trade_date = _parse_date(trade.get("trade_date"))
            if trade_date in window_dates:
                trades.append(trade)
    seen = set()
    unique = []
    for trade in trades:
        key = (trade.get("trade_id"), trade.get("transaction_id"), trade.get("date_time"), trade.get("buy_sell"), trade.get("quantity"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(trade)
    return unique


def _trading_window(bars: list[AlignmentPriceBar], decision_date: date | None, window_days: int, include_same_day: bool) -> set[date]:
    if decision_date is None:
        return set()
    if not bars:
        natural_start = 0 if include_same_day else 1
        return {decision_date + timedelta(days=offset) for offset in range(natural_start, window_days + 1)}
    eligible = [bar.report_date for bar in bars if (bar.report_date >= decision_date if include_same_day else bar.report_date > decision_date)]
    return set(eligible[: max(1, window_days + (1 if include_same_day else 0))])


def _forward_return(bars: list[AlignmentPriceBar], decision_date: date | None, horizon: int) -> float | None:
    if decision_date is None or not bars:
        return None
    future = [bar for bar in bars if bar.report_date >= decision_date]
    if len(future) <= horizon:
        return None
    start = future[0].close_price
    end = future[horizon].close_price
    return _round(end / start - 1.0) if start > 0 else None


def _execution_delay(bars: list[AlignmentPriceBar], decision_date: date | None, first_trade_date: date | None) -> int | None:
    if decision_date is None or first_trade_date is None:
        return None
    if bars:
        sequence = [bar.report_date for bar in bars if decision_date <= bar.report_date <= first_trade_date]
        return max(0, len(sequence) - 1)
    return max(0, (first_trade_date - decision_date).days)


def _trade_side(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text in {"BUY", "BOT", "B"}:
        return "buy"
    if text in {"SELL", "SLD", "S"}:
        return "sell"
    return "unknown"


def _symbol_variants(symbol: str) -> set[str]:
    raw = str(symbol or "").strip().upper()
    variants = {raw} if raw else set()
    if raw:
        try:
            variants.add(normalize_longbridge_symbol(raw))
        except ValueError:
            pass
        if "." in raw:
            variants.add(raw.split(".", 1)[0])
        else:
            variants.add(f"{raw}.US")
    return {item for item in variants if item}


def _fallback_notional(suggested_cash: float | None) -> float:
    return suggested_cash if suggested_cash is not None and suggested_cash > 0 else 2000.0


def _explain(label: str, action_group: str, final_action: str, aggregate: dict, delay: int | None) -> str:
    if label == "followed":
        return f"Agent action={final_action}，真实交易方向一致，延迟 {delay if delay is not None else '--'} 个交易日。"
    if label == "partially_followed":
        return "真实交易方向一致，但执行金额明显低于建议。"
    if label == "over_executed":
        return "真实交易方向一致，但执行金额明显高于建议。"
    if label == "ignored":
        return f"Agent 给出 {action_group} 信号，但匹配窗口内未发现对应真实交易。"
    if label == "contradicted":
        return f"真实交易方向与 Agent 的 {action_group} 建议相反或不一致。"
    if label == "no_trade_expected":
        return "Agent 建议不交易，匹配窗口内也没有真实交易。"
    return "数据不足，无法判断执行对齐。"


def _top(counter: Counter[str], limit: int = 20) -> list[dict]:
    return [{"key": key, "count": count} for key, count in counter.most_common(limit)]


def _decision_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return _parse_date(value[:10])


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: float | None) -> float | None:
    return round(value, 6) if value is not None else None


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None
