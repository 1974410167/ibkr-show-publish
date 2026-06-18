from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from math import sqrt
from statistics import mean, pstdev
from typing import Any

from app.clients.es_client import ESIndexNotFoundError, ElasticsearchClient
from app.core.config import Settings
from app.schemas.trade_decision import (
    TradeDecisionBacktestDailyPoint,
    TradeDecisionBacktestGroupStat,
    TradeDecisionBacktestPosition,
    TradeDecisionBacktestResponse,
    TradeDecisionBacktestSummary,
    TradeDecisionBacktestTrade,
)
from app.services.longbridge_service import normalize_longbridge_symbol
from app.services.trade_decision_outcome_replay import ADD_LIKE_ACTIONS, HOLD_LIKE_ACTIONS, REDUCE_LIKE_ACTIONS, action_group_for
from app.services.trade_decision_repository import TradeDecisionRepository

DEFAULT_MAX_POSITION_PCT = 0.05
DEFAULT_INITIAL_CASH = 100000.0
DEFAULT_COMMISSION_BPS = 2.0
DEFAULT_MIN_COMMISSION = 1.0
TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class PriceBar:
    symbol: str
    report_date: date
    open_price: float | None
    high_price: float | None
    low_price: float | None
    close_price: float


@dataclass
class ShadowPosition:
    symbol: str
    quantity: float = 0.0
    avg_cost: float = 0.0
    realized_pnl: float = 0.0


class ShadowBacktestPriceProvider:
    def __init__(self, es_client: ElasticsearchClient, settings: Settings) -> None:
        self.es_client = es_client
        self.settings = settings
        self.data_limitations: Counter[str] = Counter()

    def get_bars(self, symbol: str, start_date: date, end_date: date) -> list[PriceBar]:
        for candidate in _symbol_candidates(symbol):
            bars = self._fetch_bars(candidate, start_date, end_date)
            if bars:
                return bars
        self.data_limitations[f"price_missing:{symbol}"] += 1
        return []

    def get_next_trading_bar(self, bars: list[PriceBar], decision_date: date, *, include_same_day: bool) -> PriceBar | None:
        for bar in bars:
            if include_same_day and bar.report_date >= decision_date:
                return bar
            if not include_same_day and bar.report_date > decision_date:
                return bar
        return None

    def execution_price(self, bar: PriceBar, execution_timing: str) -> float | None:
        if execution_timing == "next_open":
            return bar.open_price or bar.close_price
        return bar.close_price

    def close_on_or_before(self, bars: list[PriceBar], target_date: date) -> float | None:
        latest: float | None = None
        for bar in bars:
            if bar.report_date > target_date:
                break
            latest = bar.close_price
        if latest is None and bars:
            self.data_limitations[f"carry_forward_unavailable:{bars[0].symbol}:{target_date.isoformat()}"] += 1
        return latest

    def _fetch_bars(self, symbol: str, start_date: date, end_date: date) -> list[PriceBar]:
        try:
            response = self.es_client.search(
                index=self.settings.es_price_history_index,
                body={
                    "query": {
                        "bool": {
                            "filter": [
                                {"term": {"symbol": symbol}},
                                {"range": {"report_date": {"gte": start_date.isoformat(), "lte": end_date.isoformat()}}},
                            ]
                        }
                    },
                    "sort": [{"report_date": {"order": "asc", "missing": "_last"}}],
                    "size": 10000,
                    "_source": ["symbol", "report_date", "open_price", "high_price", "low_price", "close_price"],
                },
            )
        except ESIndexNotFoundError:
            self.data_limitations["price_history_index_missing"] += 1
            return []
        bars: list[PriceBar] = []
        for hit in response.get("hits", {}).get("hits", []):
            source = _dict(hit.get("_source"))
            close_price = _float(source.get("close_price"))
            report_date = _parse_date(source.get("report_date"))
            if close_price is None or close_price <= 0 or report_date is None:
                continue
            bars.append(
                PriceBar(
                    symbol=str(source.get("symbol") or symbol),
                    report_date=report_date,
                    open_price=_float(source.get("open_price")),
                    high_price=_float(source.get("high_price")),
                    low_price=_float(source.get("low_price")),
                    close_price=close_price,
                )
            )
        return bars


class TradeDecisionShadowBacktestService:
    def __init__(self, repository: TradeDecisionRepository, price_provider: ShadowBacktestPriceProvider) -> None:
        self.repository = repository
        self.price_provider = price_provider

    def run_backtest(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        days: int = 180,
        initial_cash: float = DEFAULT_INITIAL_CASH,
        symbol: str | None = None,
        decision_type: str | None = None,
        benchmark_symbol: str = "SPY",
        execution_timing: str = "next_close",
        commission_bps: float = DEFAULT_COMMISSION_BPS,
        min_commission: float = DEFAULT_MIN_COMMISSION,
        include_costs: bool = True,
        mode: str = "signal_only",
        limit: int = 2000,
        include_detail: bool = True,
    ) -> TradeDecisionBacktestResponse:
        end_date = end_date or datetime.now(timezone.utc).date()
        start_date = start_date or (end_date - timedelta(days=days))
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days": days,
            "initial_cash": initial_cash,
            "symbol": symbol,
            "decision_type": decision_type,
            "benchmark_symbol": benchmark_symbol,
            "execution_timing": execution_timing,
            "commission_bps": commission_bps,
            "min_commission": min_commission,
            "include_costs": include_costs,
            "mode": mode,
            "limit": limit,
        }
        if mode != "signal_only":
            return _empty_response(
                params=params,
                initial_cash=initial_cash,
                start_date=start_date,
                end_date=end_date,
                data_limitations=[f"mode_unsupported:{mode}", "account_snapshot_backtest_reserved_for_future_pr"],
            )

        normalized_symbol = normalize_longbridge_symbol(symbol) if symbol else None
        docs = self.repository.list_decisions_for_backtest(
            start_date=f"{start_date.isoformat()}T00:00:00+00:00",
            end_date=f"{end_date.isoformat()}T23:59:59+00:00",
            symbol=normalized_symbol,
            decision_type=decision_type,
            limit=limit,
        )
        if not docs:
            return _empty_response(
                params=params,
                initial_cash=initial_cash,
                start_date=start_date,
                end_date=end_date,
                data_limitations=["no_trade_decisions_for_backtest"],
            )

        symbols = sorted({str(doc.get("symbol") or "") for doc in docs if str(doc.get("symbol") or "")})
        price_end_date = end_date + timedelta(days=10)
        bars_by_symbol = {item: self.price_provider.get_bars(item, start_date, price_end_date) for item in symbols}
        benchmark_bars = self.price_provider.get_bars(benchmark_symbol, start_date, price_end_date)
        calendar = sorted({bar.report_date for bars in bars_by_symbol.values() for bar in bars if start_date <= bar.report_date <= end_date})
        if not calendar:
            return _empty_response(
                params=params,
                initial_cash=initial_cash,
                start_date=start_date,
                end_date=end_date,
                data_limitations=["no_price_calendar_for_backtest", *_top_limitations(self.price_provider.data_limitations)],
            )

        events_by_date: dict[date, list[dict]] = defaultdict(list)
        for doc in docs:
            decision_date = _decision_date(str(doc.get("created_at") or ""))
            if decision_date is None:
                continue
            bars = bars_by_symbol.get(str(doc.get("symbol") or ""), [])
            include_same_day = execution_timing == "same_close"
            execution_bar = self.price_provider.get_next_trading_bar(bars, decision_date, include_same_day=include_same_day)
            if execution_bar is None:
                events_by_date[decision_date].append({"doc": doc, "execution_bar": None, "decision_date": decision_date})
            elif execution_bar.report_date <= end_date:
                events_by_date[execution_bar.report_date].append({"doc": doc, "execution_bar": execution_bar, "decision_date": decision_date})

        cash = float(initial_cash)
        positions: dict[str, ShadowPosition] = {}
        trades: list[TradeDecisionBacktestTrade] = []
        equity_curve: list[TradeDecisionBacktestDailyPoint] = []
        symbol_realized: Counter[str] = Counter()
        previous_equity: float | None = None
        peak_equity = float(initial_cash)
        total_abs_notional = 0.0
        cash_ratios: list[float] = []
        max_single_position_pct = 0.0

        for current_date in calendar:
            for event in events_by_date.get(current_date, []):
                trade = self._execute_decision(
                    event["doc"],
                    decision_date=event["decision_date"],
                    execution_bar=event["execution_bar"],
                    execution_timing=execution_timing,
                    cash=cash,
                    positions=positions,
                    bars_by_symbol=bars_by_symbol,
                    current_date=current_date,
                    initial_cash=initial_cash,
                    commission_bps=commission_bps,
                    min_commission=min_commission,
                    include_costs=include_costs,
                )
                cash += float(trade.get("_cash_delta", 0.0))
                position_delta = _dict(trade.get("_position_delta"))
                if position_delta:
                    position = positions.setdefault(position_delta["symbol"], ShadowPosition(symbol=position_delta["symbol"]))
                    if position_delta["side"] == "buy":
                        old_cost = position.avg_cost * position.quantity
                        position.quantity += position_delta["quantity"]
                        position.avg_cost = (old_cost + position_delta["notional"]) / position.quantity if position.quantity > 0 else 0.0
                    elif position_delta["side"] == "sell":
                        realized = position_delta["realized_pnl"]
                        position.quantity = max(0.0, position.quantity - position_delta["quantity"])
                        position.realized_pnl += realized
                        symbol_realized[position.symbol] += realized
                        if position.quantity <= 1e-9:
                            position.quantity = 0.0
                            position.avg_cost = 0.0
                public_trade = _public_trade(trade)
                trades.append(public_trade)
                total_abs_notional += abs(public_trade.notional)

            positions_snapshot, positions_value = self._mark_positions(positions, bars_by_symbol, current_date)
            equity = cash + positions_value
            peak_equity = max(peak_equity, equity)
            daily_return = (equity / previous_equity - 1.0) if previous_equity and previous_equity > 0 else None
            cumulative_return = equity / initial_cash - 1.0 if initial_cash > 0 else None
            drawdown = equity / peak_equity - 1.0 if peak_equity > 0 else None
            cash_ratio = cash / equity if equity > 0 else 0.0
            cash_ratios.append(cash_ratio)
            if positions_snapshot:
                max_single_position_pct = max(max_single_position_pct, max(_float(item.get("weight")) or 0.0 for item in positions_snapshot.values()))
            equity_curve.append(
                TradeDecisionBacktestDailyPoint(
                    date=current_date.isoformat(),
                    cash=round(cash, 6),
                    positions_value=round(positions_value, 6),
                    equity=round(equity, 6),
                    daily_return=_round(daily_return),
                    cumulative_return=_round(cumulative_return),
                    drawdown=_round(drawdown),
                    benchmark_value=None,
                    benchmark_return=None,
                    positions=positions_snapshot,
                )
            )
            previous_equity = equity

        _apply_benchmark_curve(equity_curve, benchmark_bars, initial_cash)
        final_positions = self._final_positions(positions, bars_by_symbol, calendar[-1], equity_curve[-1].equity if equity_curve else initial_cash)
        final_equity = equity_curve[-1].equity if equity_curve else initial_cash
        daily_returns = [item.daily_return for item in equity_curve if item.daily_return is not None]
        benchmark_return = _benchmark_return(benchmark_bars, start_date, end_date)
        total_return = final_equity / initial_cash - 1.0 if initial_cash > 0 else None
        annualized_return = _annualized_return(total_return, max(1, len(equity_curve)))
        volatility = _volatility(daily_returns)
        sharpe = _round(annualized_return / volatility) if annualized_return is not None and volatility and volatility > 0 else None
        sell_trades = [item for item in trades if item.side == "sell" and item.realized_pnl is not None]
        win_rate = _rate(sum(1 for item in sell_trades if (item.realized_pnl or 0) > 0), len(sell_trades))
        avg_equity = mean([item.equity for item in equity_curve]) if equity_curve else initial_cash
        summary = TradeDecisionBacktestSummary(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            initial_cash=initial_cash,
            final_equity=round(final_equity, 6),
            total_return=_round(total_return),
            annualized_return=annualized_return,
            max_drawdown=min((item.drawdown for item in equity_curve if item.drawdown is not None), default=None),
            sharpe_ratio=sharpe,
            volatility=volatility,
            win_rate=win_rate,
            trade_count=sum(1 for item in trades if item.side in {"buy", "sell"}),
            buy_count=sum(1 for item in trades if item.side == "buy"),
            sell_count=sum(1 for item in trades if item.side == "sell"),
            hold_count=sum(1 for item in trades if item.side == "none" and item.reason.startswith("no_trade")),
            skipped_count=sum(1 for item in trades if item.side == "none" and not item.reason.startswith("no_trade")),
            turnover=_round(total_abs_notional / avg_equity) if avg_equity > 0 else None,
            avg_cash_ratio=_round(mean(cash_ratios)) if cash_ratios else None,
            max_single_position_pct=_round(max_single_position_pct),
            benchmark_return=benchmark_return,
            excess_return=_round(total_return - benchmark_return) if total_return is not None and benchmark_return is not None else None,
            calibrated_action_success_pnl=_round(sum((item.mark_pnl or 0.0) for item in trades if item.final_action in {"add_small", "add_on_pullback"} and (item.mark_pnl or 0.0) > 0)) or 0.0,
            missed_ai_add_opportunity_estimated_cost=_round(_missed_ai_cost(trades, bars_by_symbol, initial_cash)) or 0.0,
            risk_gate_avoided_loss_estimated_value=_round(_risk_gate_value(trades, bars_by_symbol, initial_cash)) or 0.0,
            bad_add_realized_or_mark_pnl=_round(sum((item.realized_pnl if item.realized_pnl is not None else item.mark_pnl or 0.0) for item in trades if item.action_group == "add_like" and ((item.realized_pnl if item.realized_pnl is not None else item.mark_pnl or 0.0) < 0))) or 0.0,
            sold_too_early_estimated_cost=_round(_sold_too_early_cost(trades, bars_by_symbol)) or 0.0,
        )
        data_limitations = _top_limitations(self.price_provider.data_limitations)
        data_limitations.append("shadow_backtest_not_real_account_return")
        if execution_timing in {"next_close", "same_close", "next_open"}:
            data_limitations.append(f"execution_price_simplified:{execution_timing}")
        response = TradeDecisionBacktestResponse(
            version="trade_decision_shadow_backtest_v1",
            params=params,
            summary=summary,
            equity_curve=equity_curve if include_detail else equity_curve[-60:],
            trades=trades if include_detail else trades[-20:],
            positions=final_positions,
            symbol_contributions=_build_symbol_contributions(final_positions, trades, symbol_realized),
            action_stats=_build_action_stats(trades),
            data_limitations=data_limitations,
        )
        return response

    def _execute_decision(
        self,
        doc: dict,
        *,
        decision_date: date,
        execution_bar: PriceBar | None,
        execution_timing: str,
        cash: float,
        positions: dict[str, ShadowPosition],
        bars_by_symbol: dict[str, list[PriceBar]],
        current_date: date,
        initial_cash: float,
        commission_bps: float,
        min_commission: float,
        include_costs: bool,
    ) -> dict:
        symbol = str(doc.get("symbol") or "")
        final_action = str(doc.get("final_action") or doc.get("action") or "").strip().lower()
        action_group = action_group_for(final_action)
        position_advice = _dict(doc.get("position_advice"))
        target_pct = _float(position_advice.get("suggested_target_position_pct"))
        max_pct = _float(position_advice.get("max_position_pct"))
        max_pct = max_pct if max_pct is not None and max_pct > 0 else DEFAULT_MAX_POSITION_PCT
        base = {
            "decision_id": str(doc.get("id") or ""),
            "decision_date": decision_date.isoformat(),
            "execution_date": execution_bar.report_date.isoformat() if execution_bar else None,
            "symbol": symbol,
            "final_action": final_action,
            "action_group": action_group,
            "target_position_pct": target_pct,
            "max_position_pct": max_pct,
            "_cash_delta": 0.0,
            "_position_delta": {},
            "_doc": doc,
        }
        if execution_bar is None:
            return {**base, "side": "none", "quantity": 0.0, "execution_price": None, "notional": 0.0, "commission": 0.0, "reason": "price_missing_for_execution"}
        execution_price = self.price_provider.execution_price(execution_bar, execution_timing)
        if execution_price is None or execution_price <= 0:
            return {**base, "side": "none", "quantity": 0.0, "execution_price": None, "notional": 0.0, "commission": 0.0, "reason": "execution_price_invalid"}
        current_equity = cash + self._positions_value(positions, bars_by_symbol, current_date)
        position = positions.get(symbol, ShadowPosition(symbol=symbol))
        current_value = position.quantity * execution_price

        if final_action in HOLD_LIKE_ACTIONS:
            return {**base, "side": "none", "quantity": 0.0, "execution_price": execution_price, "notional": 0.0, "commission": 0.0, "reason": f"no_trade:{final_action}"}
        if final_action in ADD_LIKE_ACTIONS:
            trigger_reason = self._add_trigger_reason(final_action, doc, execution_bar, bars_by_symbol.get(symbol, []), decision_date)
            if trigger_reason:
                return {**base, "side": "none", "quantity": 0.0, "execution_price": execution_price, "notional": 0.0, "commission": 0.0, "reason": trigger_reason}
            cap_pct = _buy_cap_pct(final_action, doc)
            target_value = min((target_pct if target_pct is not None else current_value / current_equity + cap_pct) * current_equity, max_pct * current_equity)
            desired_notional = max(0.0, target_value - current_value)
            notional = min(desired_notional, current_equity * cap_pct, max(0.0, cash))
            notional = _fit_buy_notional_to_cash(notional, cash, commission_bps, min_commission, include_costs)
            if notional <= 0:
                return {**base, "side": "none", "quantity": 0.0, "execution_price": execution_price, "notional": 0.0, "commission": 0.0, "reason": "buy_notional_too_small_or_cash_insufficient"}
            commission = _commission(notional, commission_bps, min_commission, include_costs)
            quantity = notional / execution_price
            return {
                **base,
                "side": "buy",
                "quantity": quantity,
                "execution_price": execution_price,
                "notional": notional,
                "commission": commission,
                "mark_pnl": _mark_pnl(symbol, quantity, execution_price, bars_by_symbol, current_date),
                "reason": f"final_action={final_action}, target higher than current",
                "_cash_delta": -(notional + commission),
                "_position_delta": {"symbol": symbol, "side": "buy", "quantity": quantity, "notional": notional},
            }
        if final_action in REDUCE_LIKE_ACTIONS:
            sell_fraction = None
            trigger_reason = self._sell_trigger_reason(final_action, doc, execution_bar)
            if trigger_reason:
                return {**base, "side": "none", "quantity": 0.0, "execution_price": execution_price, "notional": 0.0, "commission": 0.0, "reason": trigger_reason}
            if final_action in {"sell", "sell_thesis_broken"}:
                target_value = 0.0
            elif final_action == "trim_on_rebound" and target_pct is None:
                sell_fraction = 0.20
                target_value = current_value * (1 - sell_fraction)
            elif final_action == "reduce_now" and target_pct is None:
                sell_fraction = 0.30
                target_value = current_value * (1 - sell_fraction)
            else:
                target_value = max(0.0, (target_pct or 0.0) * current_equity)
            sell_notional = min(current_value, max(0.0, current_value - target_value))
            if sell_notional <= 0 or position.quantity <= 0:
                return {**base, "side": "none", "quantity": 0.0, "execution_price": execution_price, "notional": 0.0, "commission": 0.0, "reason": "no_position_or_reduce_not_needed"}
            quantity = min(position.quantity, sell_notional / execution_price)
            notional = quantity * execution_price
            commission = _commission(notional, commission_bps, min_commission, include_costs)
            realized_pnl = (execution_price - position.avg_cost) * quantity - commission
            return {
                **base,
                "side": "sell",
                "quantity": quantity,
                "execution_price": execution_price,
                "notional": notional,
                "commission": commission,
                "realized_pnl": realized_pnl,
                "reason": f"final_action={final_action}, reduce virtual position",
                "_cash_delta": notional - commission,
                "_position_delta": {"symbol": symbol, "side": "sell", "quantity": quantity, "notional": notional, "realized_pnl": realized_pnl},
            }
        return {**base, "side": "none", "quantity": 0.0, "execution_price": execution_price, "notional": 0.0, "commission": 0.0, "reason": "action_unsupported"}

    def _add_trigger_reason(self, final_action: str, doc: dict, execution_bar: PriceBar, bars: list[PriceBar], decision_date: date) -> str | None:
        if final_action == "add_on_pullback":
            level = _find_numeric(doc, {"pullback_entry_level", "pullback_level", "entry_level"})
            if level is not None and (execution_bar.low_price is None or execution_bar.low_price > level):
                return "pullback_not_triggered"
        if final_action == "add_right_side":
            decision_bar = self.price_provider.get_next_trading_bar(bars, decision_date, include_same_day=True)
            if decision_bar and execution_bar.close_price < decision_bar.close_price:
                return "right_side_not_confirmed"
        return None

    def _sell_trigger_reason(self, final_action: str, doc: dict, execution_bar: PriceBar) -> str | None:
        if final_action != "trim_on_rebound":
            return None
        level = _find_numeric(doc, {"trim_level", "rebound_trim_level", "rebound_level"})
        if level is not None and (execution_bar.high_price is None or execution_bar.high_price < level):
            return "trim_rebound_not_triggered"
        return None

    def _positions_value(self, positions: dict[str, ShadowPosition], bars_by_symbol: dict[str, list[PriceBar]], current_date: date) -> float:
        total = 0.0
        for symbol, position in positions.items():
            if position.quantity <= 0:
                continue
            price = self.price_provider.close_on_or_before(bars_by_symbol.get(symbol, []), current_date)
            if price is not None:
                total += position.quantity * price
        return total

    def _mark_positions(self, positions: dict[str, ShadowPosition], bars_by_symbol: dict[str, list[PriceBar]], current_date: date) -> tuple[dict, float]:
        total_value = self._positions_value(positions, bars_by_symbol, current_date)
        snapshot: dict[str, dict] = {}
        for symbol, position in positions.items():
            if position.quantity <= 0:
                continue
            price = self.price_provider.close_on_or_before(bars_by_symbol.get(symbol, []), current_date)
            if price is None:
                continue
            value = position.quantity * price
            snapshot[symbol] = {
                "quantity": round(position.quantity, 6),
                "price": round(price, 6),
                "market_value": round(value, 6),
                "weight": _round(value / total_value) if total_value > 0 else None,
            }
        return snapshot, total_value

    def _final_positions(
        self,
        positions: dict[str, ShadowPosition],
        bars_by_symbol: dict[str, list[PriceBar]],
        current_date: date,
        final_equity: float,
    ) -> list[TradeDecisionBacktestPosition]:
        result: list[TradeDecisionBacktestPosition] = []
        for symbol, position in sorted(positions.items()):
            if position.quantity <= 0:
                continue
            price = self.price_provider.close_on_or_before(bars_by_symbol.get(symbol, []), current_date)
            if price is None:
                continue
            market_value = position.quantity * price
            result.append(
                TradeDecisionBacktestPosition(
                    symbol=symbol,
                    quantity=round(position.quantity, 6),
                    avg_cost=round(position.avg_cost, 6),
                    last_price=round(price, 6),
                    market_value=round(market_value, 6),
                    weight=_round(market_value / final_equity) if final_equity > 0 else None,
                    unrealized_pnl=round((price - position.avg_cost) * position.quantity, 6),
                    realized_pnl=round(position.realized_pnl, 6),
                )
            )
        return result


def _empty_response(
    *,
    params: dict,
    initial_cash: float,
    start_date: date,
    end_date: date,
    data_limitations: list[str],
) -> TradeDecisionBacktestResponse:
    summary = TradeDecisionBacktestSummary(
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        initial_cash=initial_cash,
        final_equity=initial_cash,
        total_return=0.0,
        annualized_return=0.0,
        max_drawdown=0.0,
        sharpe_ratio=None,
        volatility=0.0,
        win_rate=0.0,
        trade_count=0,
        buy_count=0,
        sell_count=0,
        hold_count=0,
        skipped_count=0,
        turnover=0.0,
        avg_cash_ratio=1.0,
        max_single_position_pct=0.0,
        benchmark_return=None,
        excess_return=None,
        calibrated_action_success_pnl=0.0,
        missed_ai_add_opportunity_estimated_cost=0.0,
        risk_gate_avoided_loss_estimated_value=0.0,
        bad_add_realized_or_mark_pnl=0.0,
        sold_too_early_estimated_cost=0.0,
    )
    return TradeDecisionBacktestResponse(
        version="trade_decision_shadow_backtest_v1",
        params=params,
        summary=summary,
        equity_curve=[],
        trades=[],
        positions=[],
        symbol_contributions=[],
        action_stats=[],
        data_limitations=data_limitations,
    )


def _symbol_candidates(symbol: str) -> list[str]:
    raw = str(symbol or "").strip().upper()
    candidates = []
    if raw:
        candidates.append(raw)
    try:
        candidates.append(normalize_longbridge_symbol(raw))
    except ValueError:
        pass
    if "." in raw:
        candidates.append(raw.split(".", 1)[0])
    else:
        candidates.append(f"{raw}.US")
    seen = set()
    return [item for item in candidates if item and not (item in seen or seen.add(item))]


def _buy_cap_pct(final_action: str, doc: dict) -> float:
    if final_action == "add_small":
        return 0.02
    if final_action in {"add", "add_batch"}:
        return 0.05
    if final_action == "add_right_side":
        return 0.03
    if final_action == "add_on_pullback" and _find_numeric(doc, {"pullback_entry_level", "pullback_level", "entry_level"}) is None:
        return 0.01
    if final_action == "add_on_pullback":
        return 0.02
    return 0.0


def _fit_buy_notional_to_cash(notional: float, cash: float, bps: float, minimum: float, include_costs: bool) -> float:
    if not include_costs:
        return min(notional, cash)
    if cash <= 0:
        return 0.0
    adjusted = min(notional, max(0.0, cash - minimum))
    for _ in range(4):
        commission = _commission(adjusted, bps, minimum, include_costs)
        if adjusted + commission <= cash + 1e-9:
            return adjusted
        adjusted = max(0.0, cash - commission)
    return 0.0


def _commission(notional: float, bps: float, minimum: float, include_costs: bool) -> float:
    if not include_costs or notional <= 0:
        return 0.0
    return round(max(abs(notional) * bps / 10000.0, minimum), 6)


def _public_trade(raw: dict) -> TradeDecisionBacktestTrade:
    return TradeDecisionBacktestTrade(
        decision_id=str(raw.get("decision_id") or ""),
        decision_date=raw.get("decision_date"),
        execution_date=raw.get("execution_date"),
        symbol=str(raw.get("symbol") or ""),
        final_action=str(raw.get("final_action") or ""),
        action_group=str(raw.get("action_group") or ""),
        side=str(raw.get("side") or "none"),
        quantity=round(float(raw.get("quantity") or 0.0), 6),
        execution_price=_round(_float(raw.get("execution_price"))),
        notional=round(float(raw.get("notional") or 0.0), 6),
        commission=round(float(raw.get("commission") or 0.0), 6),
        target_position_pct=_float(raw.get("target_position_pct")),
        max_position_pct=_float(raw.get("max_position_pct")),
        realized_pnl=_round(_float(raw.get("realized_pnl"))),
        mark_pnl=_round(_float(raw.get("mark_pnl"))),
        reason=str(raw.get("reason") or ""),
    )


def _mark_pnl(symbol: str, quantity: float, execution_price: float, bars_by_symbol: dict[str, list[PriceBar]], current_date: date) -> float | None:
    bars = bars_by_symbol.get(symbol, [])
    future = [bar for bar in bars if bar.report_date > current_date]
    if not future:
        return None
    last_price = future[-1].close_price
    return (last_price - execution_price) * quantity


def _apply_benchmark_curve(points: list[TradeDecisionBacktestDailyPoint], bars: list[PriceBar], initial_cash: float) -> None:
    if not points or not bars:
        return
    start_price = None
    for point in points:
        price = _close_on_or_before_static(bars, _parse_date(point.date))
        if price is not None:
            start_price = price
            break
    if start_price is None or start_price <= 0:
        return
    for point in points:
        price = _close_on_or_before_static(bars, _parse_date(point.date))
        if price is None:
            continue
        point.benchmark_value = round(initial_cash * price / start_price, 6)
        point.benchmark_return = _round(price / start_price - 1.0)


def _benchmark_return(bars: list[PriceBar], start_date: date, end_date: date) -> float | None:
    start = _close_on_or_before_static(bars, start_date)
    end = _close_on_or_before_static(bars, end_date)
    if start is None or end is None or start <= 0:
        return None
    return _round(end / start - 1.0)


def _close_on_or_before_static(bars: list[PriceBar], target_date: date | None) -> float | None:
    if target_date is None:
        return None
    latest = None
    for bar in bars:
        if bar.report_date > target_date:
            break
        latest = bar.close_price
    return latest


def _annualized_return(total_return: float | None, trading_days: int) -> float | None:
    if total_return is None or trading_days <= 0:
        return None
    if total_return <= -1:
        return -1.0
    return _round((1 + total_return) ** (TRADING_DAYS_PER_YEAR / trading_days) - 1)


def _volatility(daily_returns: list[float]) -> float | None:
    if len(daily_returns) < 2:
        return 0.0
    return _round(pstdev(daily_returns) * sqrt(TRADING_DAYS_PER_YEAR))


def _build_symbol_contributions(
    positions: list[TradeDecisionBacktestPosition],
    trades: list[TradeDecisionBacktestTrade],
    realized: Counter[str],
) -> list[TradeDecisionBacktestGroupStat]:
    symbols = sorted({item.symbol for item in positions}.union({item.symbol for item in trades}))
    stats = []
    for symbol in symbols:
        symbol_trades = [item for item in trades if item.symbol == symbol and item.side in {"buy", "sell"}]
        pnl = realized[symbol] + sum((item.unrealized_pnl or 0.0) for item in positions if item.symbol == symbol)
        stats.append(_group_stat(symbol, symbol_trades, pnl))
    return stats


def _build_action_stats(trades: list[TradeDecisionBacktestTrade]) -> list[TradeDecisionBacktestGroupStat]:
    grouped: dict[str, list[TradeDecisionBacktestTrade]] = defaultdict(list)
    for item in trades:
        grouped[f"final_action:{item.final_action}"].append(item)
        grouped[f"action_group:{item.action_group}"].append(item)
    return [_group_stat(key, value, sum((item.realized_pnl if item.realized_pnl is not None else item.mark_pnl or 0.0) for item in value)) for key, value in sorted(grouped.items())]


def _group_stat(key: str, trades: list[TradeDecisionBacktestTrade], contribution_pnl: float) -> TradeDecisionBacktestGroupStat:
    executable = [item for item in trades if item.side in {"buy", "sell"}]
    returns = []
    for item in executable:
        pnl = item.realized_pnl if item.realized_pnl is not None else item.mark_pnl
        if pnl is not None and item.notional:
            returns.append(pnl / item.notional)
    return TradeDecisionBacktestGroupStat(
        key=key,
        trade_count=len(executable),
        avg_trade_return=_round(mean(returns)) if returns else None,
        win_rate=_rate(sum(1 for value in returns if value > 0), len(returns)),
        total_notional=round(sum(abs(item.notional) for item in executable), 6),
        contribution_pnl=round(contribution_pnl, 6),
        avg_holding_days=None,
    )


def _missed_ai_cost(trades: list[TradeDecisionBacktestTrade], bars_by_symbol: dict[str, list[PriceBar]], initial_cash: float) -> float:
    total = 0.0
    for trade in trades:
        if trade.side != "none" or trade.action_group != "hold_like":
            continue
        bars = bars_by_symbol.get(trade.symbol, [])
        execution_date = _parse_date(trade.execution_date or trade.decision_date)
        price = _close_on_or_before_static(bars, execution_date)
        final_price = bars[-1].close_price if bars else None
        if price and final_price and final_price > price:
            total += initial_cash * 0.02 * (final_price / price - 1.0)
    return total


def _risk_gate_value(trades: list[TradeDecisionBacktestTrade], bars_by_symbol: dict[str, list[PriceBar]], initial_cash: float) -> float:
    total = 0.0
    for trade in trades:
        if trade.side != "none" or trade.action_group != "hold_like":
            continue
        bars = bars_by_symbol.get(trade.symbol, [])
        execution_date = _parse_date(trade.execution_date or trade.decision_date)
        price = _close_on_or_before_static(bars, execution_date)
        final_price = bars[-1].close_price if bars else None
        if price and final_price and final_price < price:
            total += abs(initial_cash * 0.02 * (final_price / price - 1.0))
    return total


def _sold_too_early_cost(trades: list[TradeDecisionBacktestTrade], bars_by_symbol: dict[str, list[PriceBar]]) -> float:
    total = 0.0
    for trade in trades:
        if trade.side != "sell" or not trade.execution_price or not trade.quantity:
            continue
        bars = bars_by_symbol.get(trade.symbol, [])
        final_price = bars[-1].close_price if bars else None
        if final_price and final_price > trade.execution_price:
            total += (final_price - trade.execution_price) * trade.quantity
    return total


def _find_numeric(value: Any, keys: set[str]) -> float | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in keys:
                number = _float(item)
                if number is not None:
                    return number
            found = _find_numeric(item, keys)
            if found is not None:
                return found
    if isinstance(value, list):
        for item in value:
            found = _find_numeric(item, keys)
            if found is not None:
                return found
    return None


def _decision_date(value: str) -> date | None:
    if not value:
        return None
    raw = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw).date()
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


def _top_limitations(counter: Counter[str]) -> list[str]:
    return [key for key, _ in counter.most_common(10)]
