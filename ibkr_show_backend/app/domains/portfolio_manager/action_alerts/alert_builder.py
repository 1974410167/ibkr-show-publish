from __future__ import annotations

from app.domains.portfolio_manager.action_alerts.schemas import PortfolioActionAlertCreate
from app.domains.portfolio_manager.daily_loop.schemas import PortfolioDailyLoopRun
from app.domains.portfolio_manager.decision_orchestrator.schemas import PortfolioAutoDecisionItem, PortfolioAutoDecisionRunDetail
from app.domains.portfolio_manager.portfolio_review.schemas import PortfolioManagerReport
from app.domains.portfolio_manager.watchtower.schemas import PortfolioWatchtowerRunDetail

ADD_LIKE = {"add", "add_small", "add_batch", "add_on_pullback", "add_right_side", "buy", "build_position", "accumulate"}
REDUCE_LIKE = {"reduce", "reduce_batch", "reduce_now", "trim_on_rebound", "sell", "sell_thesis_broken"}
ENTRY_BLOCKED_AI_ROLES = {"fake_ai_story", "non_ai"}
RISK_WORDS = ("concentration", "risk", "overweight", "集中", "风险", "超配")


class PortfolioActionAlertBuilder:
    def build(
        self,
        *,
        daily_loop_run: PortfolioDailyLoopRun,
        auto_decision_run: PortfolioAutoDecisionRunDetail | None,
        portfolio_report: PortfolioManagerReport | None,
        watchtower_run: PortfolioWatchtowerRunDetail | None = None,
    ) -> list[PortfolioActionAlertCreate]:
        if auto_decision_run is None or portfolio_report is None:
            return []
        if daily_loop_run.options.dry_run_auto_decision:
            return []

        alerts: list[PortfolioActionAlertCreate] = []
        watchtower_by_item_id = {item.id: item for item in (watchtower_run.items if watchtower_run else [])}
        for item in auto_decision_run.items:
            if item.selection_status != "completed":
                continue
            action = _decision_action(item.decision_summary)
            if item.universe_type == "holding" and item.decision_type == "holding_decision" and action in ADD_LIKE:
                if _blocks_add_or_entry(portfolio_report, item.symbol):
                    continue
                alerts.append(self._decision_alert(daily_loop_run, item, portfolio_report, "add_position_review", "consider_add", f"{item.display_symbol} 进入加仓复核区", watchtower_by_item_id.get(item.source_watchtower_item_id)))
            if item.universe_type in {"watchlist", "candidate"} and item.decision_type == "entry_decision" and action in ADD_LIKE:
                if item.ai_theme_role in ENTRY_BLOCKED_AI_ROLES or _blocks_add_or_entry(portfolio_report, item.symbol):
                    continue
                alerts.append(self._decision_alert(daily_loop_run, item, portfolio_report, "entry_position_review", "consider_entry", f"{item.display_symbol} 出现建仓复核机会", watchtower_by_item_id.get(item.source_watchtower_item_id)))
            if item.universe_type == "holding" and action in REDUCE_LIKE:
                alerts.append(self._decision_alert(daily_loop_run, item, portfolio_report, "reduce_position_review", "consider_reduce", f"{item.display_symbol} 进入减仓复核区", watchtower_by_item_id.get(item.source_watchtower_item_id)))
            if _item_has_high_risk(item):
                alerts.append(self._risk_alert(daily_loop_run, item, portfolio_report, ["Trade Decision 风险等级为 high"]))

        existing_risk_symbols = {alert.symbol for alert in alerts if alert.alert_type == "risk_review"}
        for symbol, reasons in _portfolio_risk_symbols(portfolio_report).items():
            if symbol in existing_risk_symbols:
                continue
            item = _find_item(auto_decision_run.items, symbol)
            if item and item.selection_status == "completed":
                alerts.append(self._risk_alert(daily_loop_run, item, portfolio_report, reasons))

        return _dedupe_alerts(alerts)

    def _decision_alert(
        self,
        daily_loop_run: PortfolioDailyLoopRun,
        item: PortfolioAutoDecisionItem,
        report: PortfolioManagerReport,
        alert_type: str,
        action_direction: str,
        title: str,
        watchtower_item,
    ) -> PortfolioActionAlertCreate:
        reasons = _base_reasons(item, report, watchtower_item)
        if alert_type == "reduce_position_review":
            reasons.append("这是减仓复核，不是卖出指令")
        return PortfolioActionAlertCreate(
            run_date=daily_loop_run.run_date,
            alert_type=alert_type,
            symbol=item.symbol,
            display_symbol=item.display_symbol,
            title=title,
            action_direction=action_direction,
            urgency=_urgency(item, report),
            confidence=_confidence(item),
            reason_summary=reasons,
            decision_summary=_decision_summary(item.decision_summary),
            portfolio_context=_portfolio_context(report),
            linked_ids=_linked_ids(daily_loop_run, item, report),
            suggested_user_action=_suggested_action(alert_type),
        )

    def _risk_alert(self, daily_loop_run: PortfolioDailyLoopRun, item: PortfolioAutoDecisionItem, report: PortfolioManagerReport, reasons: list[str]) -> PortfolioActionAlertCreate:
        return PortfolioActionAlertCreate(
            run_date=daily_loop_run.run_date,
            alert_type="risk_review",
            symbol=item.symbol,
            display_symbol=item.display_symbol,
            title=f"{item.display_symbol} 仓位风险升高，需要复核",
            action_direction="review_risk",
            urgency="high",
            confidence=_confidence(item),
            reason_summary=_dedupe([*reasons, *_base_reasons(item, report, None)]),
            decision_summary=_decision_summary(item.decision_summary),
            portfolio_context=_portfolio_context(report),
            linked_ids=_linked_ids(daily_loop_run, item, report),
            suggested_user_action="打开组合报告和交易决策详情，人工复核该仓位风险与后续加仓优先级。",
        )


def _decision_action(decision_summary: dict) -> str:
    for key in ("risk_adjusted_action", "final_action"):
        value = str(decision_summary.get(key) or "").strip().lower()
        if value:
            return value
    return ""


def _decision_summary(value: dict) -> dict:
    keys = ("final_action", "risk_adjusted_action", "target_position_pct", "max_position_pct", "confidence", "risk_level")
    return {key: value.get(key) for key in keys if key in value}


def _portfolio_context(report: PortfolioManagerReport) -> dict:
    return {
        "portfolio_health_score": report.portfolio_health_score,
        "portfolio_health_level": report.portfolio_health_level,
        "cash_status": report.cash_status.assessment,
        "concentration_risk": report.concentration_risk.assessment,
        "ai_theme_exposure_assessment": report.ai_theme_exposure.assessment,
    }


def _linked_ids(daily_loop_run: PortfolioDailyLoopRun, item: PortfolioAutoDecisionItem, report: PortfolioManagerReport) -> dict:
    return {
        "daily_loop_run_id": daily_loop_run.id,
        "watchtower_run_id": daily_loop_run.linked_run_ids.get("watchtower_run_id") or item.source_watchtower_run_id,
        "auto_decision_run_id": item.run_id,
        "auto_decision_item_id": item.id,
        "decision_id": item.decision_id,
        "portfolio_report_id": report.id,
    }


def _base_reasons(item: PortfolioAutoDecisionItem, report: PortfolioManagerReport, watchtower_item) -> list[str]:
    reasons = []
    if item.watchtower_status == "decision_required":
        reasons.append("Watchtower 触发 decision_required")
    if watchtower_item:
        reasons.extend([f"Watchtower: {reason.message}" for reason in watchtower_item.trigger_reasons[:3]])
    action = _decision_action(item.decision_summary)
    if action:
        reasons.append(f"Trade Decision 建议 {action}")
    if report.portfolio_health_level != "high_risk":
        reasons.append("Portfolio Review 未发现 high_risk 组合阻止")
    if report.concentration_risk.assessment != "high" or item.symbol not in report.concentration_risk.single_name_risk_symbols:
        reasons.append("组合层面未发现阻止该动作的集中度风险")
    return _dedupe(reasons)


def _blocks_add_or_entry(report: PortfolioManagerReport, symbol: str) -> bool:
    if report.portfolio_health_level == "high_risk":
        return True
    return report.concentration_risk.assessment == "high" and symbol in report.concentration_risk.single_name_risk_symbols


def _item_has_high_risk(item: PortfolioAutoDecisionItem) -> bool:
    return str(item.decision_summary.get("risk_level") or "").lower() == "high"


def _portfolio_risk_symbols(report: PortfolioManagerReport) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for item in report.action_queue:
        reason = item.reason or ""
        if item.queue_type == "manual_review" and any(word in reason.lower() for word in RISK_WORDS):
            result.setdefault(item.symbol, []).append(f"Portfolio Report action_queue 标记风险复核：{reason}")
    for gap in report.allocation_gaps:
        if gap.gap_type == "overweight" and gap.priority == "high":
            result.setdefault(gap.symbol, []).append(f"Portfolio Report 标记高优先级 overweight：{gap.gap_reason}")
    if report.concentration_risk.assessment == "high":
        for symbol in report.concentration_risk.single_name_risk_symbols:
            result.setdefault(symbol, []).append("Portfolio Report 集中度风险 assessment=high")
    return result


def _find_item(items: list[PortfolioAutoDecisionItem], symbol: str) -> PortfolioAutoDecisionItem | None:
    return next((item for item in items if item.symbol == symbol), None)


def _urgency(item: PortfolioAutoDecisionItem, report: PortfolioManagerReport) -> str:
    if item.watchtower_severity == "high" or report.portfolio_health_level in {"attention_required", "high_risk"}:
        return "high"
    if item.watchtower_severity == "medium" or report.portfolio_health_level == "watch":
        return "medium"
    return "low"


def _confidence(item: PortfolioAutoDecisionItem) -> str:
    value = str(item.decision_summary.get("confidence") or "").lower()
    return value if value in {"low", "medium", "high"} else "medium"


def _suggested_action(alert_type: str) -> str:
    return {
        "add_position_review": "打开交易决策详情，人工确认是否加仓。",
        "entry_position_review": "打开交易决策详情，人工确认是否建仓。",
        "reduce_position_review": "打开交易决策详情，人工确认是否减仓或止盈；这不是卖出指令。",
        "risk_review": "打开组合报告和交易决策详情，人工复核仓位风险。",
    }[alert_type]


def _dedupe_alerts(alerts: list[PortfolioActionAlertCreate]) -> list[PortfolioActionAlertCreate]:
    result: list[PortfolioActionAlertCreate] = []
    seen: set[tuple[str, str]] = set()
    for alert in alerts:
        key = (alert.symbol, alert.alert_type)
        if key in seen:
            continue
        seen.add(key)
        result.append(alert)
    return result


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
