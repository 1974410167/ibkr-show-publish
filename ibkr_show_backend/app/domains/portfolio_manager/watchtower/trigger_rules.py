from __future__ import annotations

from app.domains.portfolio_manager.universe.schemas import UniverseSymbol
from app.domains.portfolio_manager.watchtower.schemas import (
    DecisionTypeHint,
    WatchtowerItemStatus,
    WatchtowerMetrics,
    WatchtowerNextStep,
    WatchtowerSeverity,
    WatchtowerTriggerReason,
)

STATUS_RANK: dict[WatchtowerItemStatus, int] = {
    "normal": 0,
    "watch": 1,
    "attention_required": 2,
    "decision_required": 3,
}
SEVERITY_RANK: dict[WatchtowerSeverity, int] = {
    "none": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
}


def evaluate_watchtower_triggers(
    *,
    universe_item: UniverseSymbol,
    metrics: WatchtowerMetrics,
) -> tuple[WatchtowerItemStatus, WatchtowerSeverity, list[WatchtowerTriggerReason], WatchtowerNextStep, bool, DecisionTypeHint | None]:
    reasons: list[WatchtowerTriggerReason] = []
    is_holding = universe_item.universe_type == "holding"
    is_watch_candidate = universe_item.universe_type in {"watchlist", "candidate"}

    _rule_consecutive_down_days(reasons, is_holding=is_holding, is_watch_candidate=is_watch_candidate, metrics=metrics)
    _rule_consecutive_up_days(reasons, is_holding=is_holding, is_watch_candidate=is_watch_candidate, metrics=metrics)
    _rule_drawdown_from_high(reasons, is_holding=is_holding, is_watch_candidate=is_watch_candidate, metrics=metrics)
    _rule_abnormal_return(reasons, is_holding=is_holding, metrics=metrics)
    if is_holding:
        _rule_large_unrealized_gain(reasons, metrics)
        _rule_large_unrealized_loss(reasons, metrics)
        _rule_position_weight_high(reasons, metrics)
    if is_watch_candidate:
        _rule_watchlist_pullback_candidate(reasons, universe_item, metrics)
    _rule_ai_theme_misalignment(reasons, universe_item)

    status = _max_status(reasons)
    severity = _max_severity(reasons)
    decision_candidate = status == "decision_required"
    decision_type_hint = _decision_type_hint(reasons, universe_item, decision_candidate)
    suggested_next_step = _suggested_next_step(status)
    return status, severity, reasons, suggested_next_step, decision_candidate, decision_type_hint


def _rule_consecutive_down_days(
    reasons: list[WatchtowerTriggerReason],
    *,
    is_holding: bool,
    is_watch_candidate: bool,
    metrics: WatchtowerMetrics,
) -> None:
    days = metrics.consecutive_down_days
    if is_holding:
        if days >= 7:
            _add(reasons, "consecutive_down_days", "high", "decision_required", f"已连续下跌 {days} 天，需要单标的深度复核", days, 7, "holding_decision")
        elif days >= 5:
            _add(reasons, "consecutive_down_days", "medium", "attention_required", f"已连续下跌 {days} 天，需要关注风险", days, 5)
        elif days >= 3:
            _add(reasons, "consecutive_down_days", "low", "watch", f"已连续下跌 {days} 天，进入观察", days, 3)
    elif is_watch_candidate:
        if days >= 7 and _le(metrics.drawdown_from_20d_high, -0.12):
            _add(reasons, "consecutive_down_days", "high", "decision_required", f"观察标的连续下跌 {days} 天且 20D 回撤明显", days, 7, "entry_decision")
        elif days >= 7:
            _add(reasons, "consecutive_down_days", "medium", "attention_required", f"观察标的连续下跌 {days} 天，需要关注", days, 7)
        elif days >= 5:
            _add(reasons, "consecutive_down_days", "low", "watch", f"观察标的连续下跌 {days} 天", days, 5)


def _rule_consecutive_up_days(
    reasons: list[WatchtowerTriggerReason],
    *,
    is_holding: bool,
    is_watch_candidate: bool,
    metrics: WatchtowerMetrics,
) -> None:
    days = metrics.consecutive_up_days
    if is_holding:
        high_gain = metrics.unrealized_pnl_pct is not None and metrics.unrealized_pnl_pct >= 1.0
        high_weight = metrics.position_weight is not None and metrics.position_weight >= 0.15
        if days >= 8 and (high_gain or high_weight):
            _add(reasons, "consecutive_up_days", "high", "decision_required", f"已连续上涨 {days} 天且浮盈或仓位较高，需要持仓复核", days, 8, "holding_decision")
        elif days >= 8:
            _add(reasons, "consecutive_up_days", "medium", "attention_required", f"已连续上涨 {days} 天，需要关注过热风险", days, 8)
        elif days >= 5:
            _add(reasons, "consecutive_up_days", "low", "watch", f"已连续上涨 {days} 天", days, 5)
    elif is_watch_candidate and days >= 5:
        _add(reasons, "consecutive_up_days", "low", "watch", f"观察标的连续上涨 {days} 天，避免无纪律追高", days, 5)


def _rule_drawdown_from_high(
    reasons: list[WatchtowerTriggerReason],
    *,
    is_holding: bool,
    is_watch_candidate: bool,
    metrics: WatchtowerMetrics,
) -> None:
    dd20 = metrics.drawdown_from_20d_high
    dd60 = metrics.drawdown_from_60d_high
    if is_holding:
        if _le(dd60, -0.25):
            _add(reasons, "drawdown_from_high", "high", "decision_required", "60D 高点回撤超过 25%，需要持仓深度复核", dd60, -0.25, "holding_decision")
        elif _le(dd20, -0.15):
            _add(reasons, "drawdown_from_high", "medium", "attention_required", "20D 高点回撤超过 15%", dd20, -0.15)
        elif _le(dd20, -0.10):
            _add(reasons, "drawdown_from_high", "low", "watch", "20D 高点回撤超过 10%", dd20, -0.10)
    elif is_watch_candidate:
        if _le(dd60, -0.20):
            _add(reasons, "drawdown_from_high", "high", "decision_required", "观察标的 60D 高点回撤超过 20%，可能进入建仓复核区", dd60, -0.20, "entry_decision")
        elif _le(dd20, -0.12):
            _add(reasons, "drawdown_from_high", "medium", "attention_required", "观察标的 20D 高点回撤超过 12%，可能进入观察买点", dd20, -0.12)


def _rule_abnormal_return(reasons: list[WatchtowerTriggerReason], *, is_holding: bool, metrics: WatchtowerMetrics) -> None:
    r1 = metrics.return_1d
    r5 = metrics.return_5d
    r20 = metrics.return_20d
    if _le(r20, -0.20):
        _add(reasons, "abnormal_return", "high", "decision_required", "20D 跌幅超过 20%，需要深度复核", r20, -0.20, "holding_decision" if is_holding else "entry_decision")
    elif _ge(r20, 0.30):
        status: WatchtowerItemStatus = "decision_required" if is_holding and _ge(metrics.unrealized_pnl_pct, 1.0) else "attention_required"
        _add(reasons, "abnormal_return", "high" if status == "decision_required" else "medium", status, "20D 涨幅超过 30%，需要关注过热与执行纪律", r20, 0.30, "holding_decision" if status == "decision_required" else None)
    if _le(r1, -0.06):
        _add(reasons, "abnormal_return", "medium", "attention_required", "1D 跌幅超过 6%", r1, -0.06)
    if _ge(r1, 0.08):
        _add(reasons, "abnormal_return", "medium", "attention_required", "1D 涨幅超过 8%", r1, 0.08)
    if _le(r5, -0.10):
        _add(reasons, "abnormal_return", "medium", "attention_required", "5D 跌幅超过 10%", r5, -0.10)
    if _ge(r5, 0.15):
        _add(reasons, "abnormal_return", "medium", "attention_required", "5D 涨幅超过 15%", r5, 0.15)


def _rule_large_unrealized_gain(reasons: list[WatchtowerTriggerReason], metrics: WatchtowerMetrics) -> None:
    pnl = metrics.unrealized_pnl_pct
    if _ge(pnl, 2.0):
        _add(reasons, "large_unrealized_gain", "high", "decision_required", "持仓浮盈超过 200%，上涨不是卖出理由，但需要止盈/继续持有复核", pnl, 2.0, "holding_decision")
    elif _ge(pnl, 1.0):
        _add(reasons, "large_unrealized_gain", "medium", "attention_required", "持仓浮盈超过 100%，需要关注止盈和仓位纪律", pnl, 1.0)


def _rule_large_unrealized_loss(reasons: list[WatchtowerTriggerReason], metrics: WatchtowerMetrics) -> None:
    pnl = metrics.unrealized_pnl_pct
    if _le(pnl, -0.35):
        _add(reasons, "large_unrealized_loss", "high", "decision_required", "持仓浮亏超过 35%，下跌不是卖出理由，但需要 thesis / 风险复核", pnl, -0.35, "holding_decision")
    elif _le(pnl, -0.20):
        _add(reasons, "large_unrealized_loss", "medium", "attention_required", "持仓浮亏超过 20%，需要关注 thesis 和风险", pnl, -0.20)


def _rule_position_weight_high(reasons: list[WatchtowerTriggerReason], metrics: WatchtowerMetrics) -> None:
    weight = metrics.position_weight
    if _ge(weight, 0.15):
        _add(reasons, "position_weight_high", "high", "decision_required", "单标的仓位超过 15%，需要风险预算复核", weight, 0.15, "holding_decision")
    elif _ge(weight, 0.10):
        _add(reasons, "position_weight_high", "medium", "attention_required", "单标的仓位超过 10%，接近默认风险阈值", weight, 0.10)


def _rule_watchlist_pullback_candidate(reasons: list[WatchtowerTriggerReason], item: UniverseSymbol, metrics: WatchtowerMetrics) -> None:
    if item.ai_theme_role in {"fake_ai_story", "non_ai"}:
        return
    if _le(metrics.return_20d, -0.18) or _le(metrics.drawdown_from_60d_high, -0.25):
        _add(reasons, "watchlist_pullback_candidate", "high", "decision_required", "观察标的出现较深回撤，可能进入建仓决策复核区", metrics.return_20d, -0.18, "entry_decision")
    elif _le(metrics.return_5d, -0.08) or _le(metrics.return_20d, -0.12):
        _add(reasons, "watchlist_pullback_candidate", "medium", "attention_required", "观察标的回调进入潜在买点观察区", metrics.return_5d if _le(metrics.return_5d, -0.08) else metrics.return_20d, -0.08)


def _rule_ai_theme_misalignment(reasons: list[WatchtowerTriggerReason], item: UniverseSymbol) -> None:
    if item.universe_type not in {"watchlist", "candidate"} or not item.enabled:
        return
    if item.ai_theme_role == "fake_ai_story":
        _add(reasons, "ai_theme_misalignment", "medium", "attention_required", "该标的被标记为 fake_ai_story，不应反复消耗研究资源", "fake_ai_story", "not_fake_ai_story")
    elif item.ai_theme_role == "non_ai":
        _add(reasons, "ai_theme_misalignment", "low", "watch", "该标的被标记为 non_ai，与 AI 主线存在偏离", "non_ai", "ai_aligned")


def _add(
    reasons: list[WatchtowerTriggerReason],
    code: str,
    severity: WatchtowerSeverity,
    status: WatchtowerItemStatus,
    message: str,
    value: float | int | str | None,
    threshold: float | int | str | None,
    decision_type_hint: DecisionTypeHint | None = None,
) -> None:
    reasons.append(
        WatchtowerTriggerReason(
            code=code,
            severity=severity,
            status=status,
            message=message,
            value=value,
            threshold=threshold,
            decision_type_hint=decision_type_hint,
        )
    )


def _max_status(reasons: list[WatchtowerTriggerReason]) -> WatchtowerItemStatus:
    if not reasons:
        return "normal"
    return max((reason.status or "normal" for reason in reasons), key=lambda status: STATUS_RANK[status])


def _max_severity(reasons: list[WatchtowerTriggerReason]) -> WatchtowerSeverity:
    if not reasons:
        return "none"
    return max((reason.severity for reason in reasons), key=lambda severity: SEVERITY_RANK[severity])


def _decision_type_hint(
    reasons: list[WatchtowerTriggerReason],
    item: UniverseSymbol,
    decision_candidate: bool,
) -> DecisionTypeHint | None:
    for reason in reasons:
        if reason.decision_type_hint:
            return reason.decision_type_hint
    if not decision_candidate:
        return None
    return "holding_decision" if item.universe_type == "holding" else "entry_decision"


def _suggested_next_step(status: WatchtowerItemStatus) -> WatchtowerNextStep:
    return {
        "normal": "no_action",
        "watch": "keep_watch",
        "attention_required": "review_manually",
        "decision_required": "trigger_trade_decision",
    }[status]


def _le(value: float | int | None, threshold: float) -> bool:
    return value is not None and float(value) <= threshold


def _ge(value: float | int | None, threshold: float) -> bool:
    return value is not None and float(value) >= threshold

