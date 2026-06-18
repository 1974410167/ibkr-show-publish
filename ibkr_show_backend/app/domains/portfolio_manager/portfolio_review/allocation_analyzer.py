from __future__ import annotations

from datetime import date, datetime, timezone

from app.domains.portfolio_manager.constitution.schemas import InvestmentConstitution
from app.domains.portfolio_manager.decision_orchestrator.schemas import PortfolioAutoDecisionRunDetail
from app.domains.portfolio_manager.portfolio_review.exposure_analyzer import AI_ALIGNED_ROLES
from app.domains.portfolio_manager.portfolio_review.schemas import (
    PortfolioActionQueueItem,
    PortfolioAllocationAnalysis,
    PortfolioAllocationGap,
    PortfolioAttentionSymbol,
    PortfolioCashStatus,
    PortfolioGoalTracking,
    PortfolioPositionExposureItem,
)
from app.domains.portfolio_manager.universe.repository import normalize_universe_symbol
from app.domains.portfolio_manager.universe.schemas import UniverseSymbol
from app.domains.portfolio_manager.watchtower.schemas import PortfolioWatchtowerRunDetail

ADD_LIKE_ACTIONS = {"add", "buy", "add_on_pullback", "accumulate", "increase", "build_position"}
ATTENTION_ACTIONS = ADD_LIKE_ACTIONS | {"reduce", "sell", "trim"}


class PortfolioAllocationAnalyzer:
    def analyze(
        self,
        *,
        constitution: InvestmentConstitution,
        position_exposure_items: list[PortfolioPositionExposureItem],
        universe_items: list[UniverseSymbol],
        watchtower_run: PortfolioWatchtowerRunDetail | None = None,
        auto_decision_run: PortfolioAutoDecisionRunDetail | None = None,
        total_equity: float | None = None,
        cash_value: float | None = None,
        as_of_date: str | None = None,
    ) -> PortfolioAllocationAnalysis:
        universe_by_symbol = {normalize_universe_symbol(item.symbol): item for item in universe_items}
        exposure_by_symbol = {item.symbol: item for item in position_exposure_items}
        gaps = _allocation_gaps(position_exposure_items, universe_items, auto_decision_run)
        attention = _top_attention_symbols(position_exposure_items, universe_by_symbol, watchtower_run, auto_decision_run)
        action_queue = _action_queue(universe_by_symbol, watchtower_run, auto_decision_run)
        limitations: list[str] = []
        cash_status = _cash_status(total_equity=total_equity, cash_value=cash_value, limitations=limitations)
        goal_tracking = _goal_tracking(constitution=constitution, total_equity=total_equity, as_of_date=as_of_date, limitations=limitations)
        return PortfolioAllocationAnalysis(
            goal_tracking=goal_tracking,
            cash_status=cash_status,
            allocation_gaps=gaps,
            top_attention_symbols=attention,
            action_queue=action_queue,
            data_limitations=_dedupe(limitations),
        )


def _allocation_gaps(
    position_items: list[PortfolioPositionExposureItem],
    universe_items: list[UniverseSymbol],
    auto_decision_run: PortfolioAutoDecisionRunDetail | None,
) -> list[PortfolioAllocationGap]:
    gaps: list[PortfolioAllocationGap] = []
    for item in position_items:
        if item.position_weight >= 0.15:
            gaps.append(_gap(item.symbol, item.display_symbol, item.position_weight, item.ai_theme_role, "overweight", "单标的仓位达到 15% 以上，需要组合层面复核集中度。", "high"))
        elif item.position_weight >= 0.10:
            gaps.append(_gap(item.symbol, item.display_symbol, item.position_weight, item.ai_theme_role, "overweight", "单标的仓位达到 10% 以上，需要观察集中度。", "medium"))
        elif item.ai_theme_role in AI_ALIGNED_ROLES and item.position_weight <= 0.03:
            gaps.append(_gap(item.symbol, item.display_symbol, item.position_weight, item.ai_theme_role, "underweight", "高优先级 AI 主线持仓仓位较低，可进入复核队列。", "medium"))

    universe_by_symbol = {normalize_universe_symbol(item.symbol): item for item in universe_items}
    for auto_item in auto_decision_run.items if auto_decision_run else []:
        final_action = str(auto_item.decision_summary.get("final_action") or "").lower()
        universe = universe_by_symbol.get(normalize_universe_symbol(auto_item.symbol))
        if final_action in ADD_LIKE_ACTIONS and universe and universe.ai_theme_role in AI_ALIGNED_ROLES:
            gaps.append(_gap(auto_item.symbol, auto_item.display_symbol, None, auto_item.ai_theme_role, "underweight", "Auto Decision 摘要显示进入 add-like 复核方向，应优先查看单标的决策结果。", "high"))
        if universe and universe.ai_theme_role in {"fake_ai_story", "non_ai"}:
            gaps.append(_gap(auto_item.symbol, auto_item.display_symbol, None, auto_item.ai_theme_role, "unknown", "fake_ai_story / non_ai 不应由组合报告推荐加仓。", "low"))
    return _dedupe_gaps(gaps)[:50]


def _top_attention_symbols(
    position_items: list[PortfolioPositionExposureItem],
    universe_by_symbol: dict[str, UniverseSymbol],
    watchtower_run: PortfolioWatchtowerRunDetail | None,
    auto_decision_run: PortfolioAutoDecisionRunDetail | None,
) -> list[PortfolioAttentionSymbol]:
    items: list[PortfolioAttentionSymbol] = []
    for auto_item in auto_decision_run.items if auto_decision_run else []:
        if auto_item.selection_status == "failed":
            items.append(_attention(auto_item.symbol, "Auto Decision failed，需要人工复核失败原因。", "high", "manual_review"))
        elif auto_item.selection_status == "completed":
            action = str(auto_item.decision_summary.get("final_action") or "").lower()
            if action in ATTENTION_ACTIONS:
                items.append(_attention(auto_item.symbol, "Auto Decision completed 且 action 摘要需要复核。", "high", "review_trade_decision"))

    for watch_item in watchtower_run.items if watchtower_run else []:
        if watch_item.status == "decision_required":
            items.append(_attention(watch_item.symbol, "Watchtower decision_required。", "high", "manual_review"))
        elif watch_item.status == "attention_required":
            items.append(_attention(watch_item.symbol, "Watchtower attention_required。", "medium", "monitor"))

    for item in position_items:
        if item.position_weight >= 0.15:
            priority = universe_by_symbol.get(item.symbol).priority if universe_by_symbol.get(item.symbol) else "high"
            items.append(_attention(item.symbol, "position_weight high，需要集中度复核。", priority, "manual_review"))
    return _dedupe_attention(items)[:20]


def _action_queue(
    universe_by_symbol: dict[str, UniverseSymbol],
    watchtower_run: PortfolioWatchtowerRunDetail | None,
    auto_decision_run: PortfolioAutoDecisionRunDetail | None,
) -> list[PortfolioActionQueueItem]:
    queue: list[PortfolioActionQueueItem] = []
    auto_by_symbol = {}
    for item in auto_decision_run.items if auto_decision_run else []:
        auto_by_symbol[normalize_universe_symbol(item.symbol)] = item
        if item.decision_id:
            queue.append(
                PortfolioActionQueueItem(
                    symbol=item.symbol,
                    queue_type="review_trade_decision",
                    priority="high",
                    reason="Auto Decision 已生成交易决策，组合层面只要求查看和复核，不构成下单指令。",
                    linked_decision_id=item.decision_id,
                )
            )
        elif item.selection_status == "failed":
            queue.append(PortfolioActionQueueItem(symbol=item.symbol, queue_type="manual_review", priority="high", reason="Auto Decision failed，需要人工复核。"))

    for item in watchtower_run.items if watchtower_run else []:
        symbol = normalize_universe_symbol(item.symbol)
        universe = universe_by_symbol.get(symbol)
        if universe and universe.universe_type in {"watchlist", "candidate"} and universe.ai_theme_role in {"fake_ai_story", "non_ai"}:
            queue.append(PortfolioActionQueueItem(symbol=item.symbol, queue_type="wait", priority="low", reason="fake_ai_story / non_ai 不允许自动进入新建仓决策。"))
        elif item.status == "decision_required" and symbol not in auto_by_symbol:
            queue.append(PortfolioActionQueueItem(symbol=item.symbol, queue_type="manual_review", priority="high", reason="watchtower_required_but_no_auto_decision"))
        elif item.status == "attention_required":
            queue.append(PortfolioActionQueueItem(symbol=item.symbol, queue_type="monitor", priority="medium", reason="Watchtower attention_required，进入观察。"))
    return _dedupe_queue(queue)[:30]


def _cash_status(*, total_equity: float | None, cash_value: float | None, limitations: list[str]) -> PortfolioCashStatus:
    if cash_value is None or total_equity is None or total_equity <= 0:
        limitations.append("cash_unavailable")
        return PortfolioCashStatus(cash_value=cash_value, cash_pct=None, assessment="unknown", summary="现金数据不可用，暂无法判断现金缓冲。")
    cash_pct = cash_value / total_equity
    if cash_pct < 0.05:
        assessment = "too_low"
        summary = "现金比例偏低，遇到回撤或新增机会时弹性不足。"
    elif cash_pct > 0.30:
        assessment = "too_high"
        summary = "现金比例偏高，可能拖累长期复利，需要结合机会质量复核。"
    else:
        assessment = "reasonable"
        summary = "现金比例处于可接受区间，可支持短期机会和风险缓冲。"
    return PortfolioCashStatus(cash_value=round(cash_value, 2), cash_pct=round(cash_pct, 6), assessment=assessment, summary=summary)


def _goal_tracking(
    *,
    constitution: InvestmentConstitution,
    total_equity: float | None,
    as_of_date: str | None,
    limitations: list[str],
) -> PortfolioGoalTracking:
    target = float(constitution.target_account_value_usd)
    if total_equity is None or total_equity <= 0:
        limitations.append("total_equity_unavailable")
        return PortfolioGoalTracking(target_account_value_usd=target, target_date=constitution.target_date, summary="账户总权益不可用，暂无法评估 2035 目标路径。")
    remaining_years = _remaining_years(as_of_date, constitution.target_date)
    if remaining_years is None or remaining_years <= 0:
        limitations.append("target_date_unavailable")
        return PortfolioGoalTracking(target_account_value_usd=target, target_date=constitution.target_date, current_total_equity_usd=total_equity, summary="目标日期不可用或已到期，暂无法计算所需年化收益。")
    required = (target / total_equity) ** (1.0 / remaining_years) - 1.0
    status = "on_track" if required <= 0.20 else "stretched" if required <= 0.35 else "off_track"
    summary = f"当前距离 {constitution.target_date} 的 {target:,.0f} 美元目标仍需要约 {required:.1%} 的长期年化复合收益。"
    return PortfolioGoalTracking(
        target_account_value_usd=target,
        target_date=constitution.target_date,
        current_total_equity_usd=round(total_equity, 2),
        remaining_years=round(remaining_years, 3),
        required_annual_return=round(required, 6),
        current_path_status=status,
        summary=summary,
    )


def _remaining_years(as_of_date: str | None, target_date: str) -> float | None:
    try:
        start = date.fromisoformat(as_of_date) if as_of_date else datetime.now(timezone.utc).date()
        end = date.fromisoformat(target_date)
    except ValueError:
        return None
    return max((end - start).days / 365.25, 0.0)


def _gap(symbol, display_symbol, weight, role, gap_type, reason, priority) -> PortfolioAllocationGap:
    return PortfolioAllocationGap(symbol=symbol, display_symbol=display_symbol, position_weight=weight, ai_theme_role=role, gap_type=gap_type, gap_reason=reason, priority=priority)


def _attention(symbol, reason, priority, next_step) -> PortfolioAttentionSymbol:
    return PortfolioAttentionSymbol(symbol=symbol, reason=reason, priority=priority, next_step=next_step)


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in values if item))


def _dedupe_gaps(items: list[PortfolioAllocationGap]) -> list[PortfolioAllocationGap]:
    seen: set[tuple[str, str]] = set()
    result = []
    for item in items:
        key = (item.symbol, item.gap_type)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _dedupe_attention(items: list[PortfolioAttentionSymbol]) -> list[PortfolioAttentionSymbol]:
    seen: set[str] = set()
    result = []
    for item in items:
        if item.symbol not in seen:
            seen.add(item.symbol)
            result.append(item)
    return result


def _dedupe_queue(items: list[PortfolioActionQueueItem]) -> list[PortfolioActionQueueItem]:
    seen: set[tuple[str, str]] = set()
    result = []
    for item in items:
        key = (item.symbol, item.queue_type)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
