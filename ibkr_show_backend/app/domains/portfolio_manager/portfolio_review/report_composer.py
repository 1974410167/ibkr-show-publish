from __future__ import annotations

from app.domains.portfolio_manager.constitution.schemas import InvestmentConstitution
from app.domains.portfolio_manager.portfolio_review.schemas import (
    PortfolioAllocationAnalysis,
    PortfolioExposureAnalysis,
    PortfolioHealthLevel,
)


class PortfolioReportComposer:
    def compose(
        self,
        *,
        report_id: str,
        report_date: str,
        report_type: str,
        constitution: InvestmentConstitution,
        exposure: PortfolioExposureAnalysis,
        allocation: PortfolioAllocationAnalysis,
        source_watchtower_run_id: str | None,
        source_auto_decision_run_id: str | None,
        watchtower_decision_required_count: int = 0,
        auto_decision_failed_count: int = 0,
        data_limitations: list[str] | None = None,
    ) -> dict:
        limitations = _dedupe([*(data_limitations or []), *exposure.data_limitations, *allocation.data_limitations])
        score = _health_score(
            exposure=exposure,
            allocation=allocation,
            watchtower_decision_required_count=watchtower_decision_required_count,
            auto_decision_failed_count=auto_decision_failed_count,
            data_limitations=limitations,
        )
        level = _health_level(score)
        return {
            "id": report_id,
            "report_date": report_date,
            "report_type": report_type,
            "status": "partial_success" if limitations else "success",
            "constitution_version": constitution.constitution_version,
            "source_watchtower_run_id": source_watchtower_run_id,
            "source_auto_decision_run_id": source_auto_decision_run_id,
            "portfolio_health_score": score,
            "portfolio_health_level": level,
            "goal_tracking": allocation.goal_tracking.model_dump(),
            "ai_theme_exposure": exposure.ai_theme_exposure.model_dump(),
            "concentration_risk": exposure.concentration_risk.model_dump(),
            "cash_status": allocation.cash_status.model_dump(),
            "allocation_gaps": [item.model_dump() for item in allocation.allocation_gaps],
            "top_attention_symbols": [item.model_dump() for item in allocation.top_attention_symbols],
            "action_queue": [item.model_dump() for item in allocation.action_queue],
            "summary": _summary(level, exposure, allocation),
            "next_steps": _next_steps(allocation),
            "data_limitations": limitations,
        }


def _health_score(
    *,
    exposure: PortfolioExposureAnalysis,
    allocation: PortfolioAllocationAnalysis,
    watchtower_decision_required_count: int,
    auto_decision_failed_count: int,
    data_limitations: list[str],
) -> int:
    score = 100
    if exposure.concentration_risk.assessment == "high":
        score -= 20
    elif exposure.concentration_risk.assessment == "medium":
        score -= 10
    if exposure.ai_theme_exposure.assessment == "misaligned":
        score -= 20
    elif exposure.ai_theme_exposure.assessment == "partially_aligned":
        score -= 10
    if allocation.cash_status.assessment == "too_low":
        score -= 10
    elif allocation.cash_status.assessment == "too_high":
        score -= 5
    if watchtower_decision_required_count >= 3:
        score -= 15
    if auto_decision_failed_count >= 1:
        score -= 10
    if (exposure.ai_theme_exposure.fake_ai_story_exposure_pct or 0.0) > 0:
        score -= 10
    missing_penalty = min(15, 5 * len([item for item in data_limitations if "unavailable" in item or "missing" in item]))
    score -= missing_penalty
    return max(0, min(100, int(score)))


def _health_level(score: int) -> PortfolioHealthLevel:
    if score >= 80:
        return "healthy"
    if score >= 60:
        return "watch"
    if score >= 40:
        return "attention_required"
    return "high_risk"


def _summary(level: str, exposure: PortfolioExposureAnalysis, allocation: PortfolioAllocationAnalysis) -> str:
    return (
        f"组合健康等级为 {level}，AI 主线暴露评估为 {exposure.ai_theme_exposure.assessment}，"
        f"集中度风险为 {exposure.concentration_risk.assessment}，现金状态为 {allocation.cash_status.assessment}。"
        "本组合报告只提供组合级排序和复核队列，不是买卖指令。"
    )


def _next_steps(allocation: PortfolioAllocationAnalysis) -> list[str]:
    steps: list[str] = []
    for item in allocation.action_queue[:5]:
        if item.queue_type == "review_trade_decision":
            steps.append(f"优先查看 {item.symbol} 的 Trade Decision 结果并人工确认。")
        elif item.queue_type == "manual_review":
            steps.append(f"人工复核 {item.symbol} 的组合风险和 Watchtower 触发原因。")
        elif item.queue_type == "monitor":
            steps.append(f"继续观察 {item.symbol}，等待更明确的组合级信号。")
        elif item.queue_type == "wait":
            steps.append(f"{item.symbol} 暂不消耗自动决策预算，等待人工确认或更强证据。")
    if not steps:
        steps.append("保持组合级监控，等待 Watchtower 或 Auto Decision 产生新的复核信号。")
    steps.append("单标的最终动作仍以 Trade Decision Agent 输出和人工确认结果为准；不会自动下单。")
    return steps


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
