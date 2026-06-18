from __future__ import annotations

from app.domains.portfolio_manager.improvement.schemas import (
    DEFAULT_AFFECTED_VERSIONS,
    PortfolioImprovementCandidate,
    PortfolioImprovementEvidenceSummary,
    PortfolioImprovementPattern,
)
from app.domains.portfolio_manager.watchtower.repository import utc_now_iso


class PortfolioImprovementRecommendationBuilder:
    def build_candidates(
        self,
        *,
        patterns: list[PortfolioImprovementPattern],
        evaluation_summary: dict,
        report_id: str,
    ) -> list[PortfolioImprovementCandidate]:
        del evaluation_summary
        now = utc_now_iso()
        candidates: list[PortfolioImprovementCandidate] = []
        for pattern in patterns:
            spec = _candidate_spec(pattern)
            candidates.append(
                PortfolioImprovementCandidate(
                    id=f"candidate:{report_id}:{pattern.pattern_type}:{_slug(pattern.group_key)}",
                    candidate_type=spec["candidate_type"],
                    title=spec["title"],
                    severity=pattern.severity,
                    confidence=pattern.confidence,
                    requires_human_approval=True,
                    status="proposed",
                    affected_module=pattern.affected_module,
                    affected_rule_or_component=pattern.affected_rule_or_component,
                    affected_versions=dict(DEFAULT_AFFECTED_VERSIONS),
                    evidence_summary=PortfolioImprovementEvidenceSummary(
                        sample_size=pattern.sample_size,
                        horizons=pattern.horizons,
                        source_type=pattern.source_type,
                        labels=pattern.labels,
                        metrics=pattern.metrics,
                        example_result_ids=pattern.evidence_result_ids[:10],
                    ),
                    suggested_change=spec["suggested_change"],
                    expected_impact=spec["expected_impact"],
                    risk_of_change=spec["risk_of_change"],
                    human_review_notes="",
                    created_at=now,
                    updated_at=now,
                )
            )
        return candidates


def _candidate_spec(pattern: PortfolioImprovementPattern) -> dict:
    component = pattern.affected_rule_or_component
    if pattern.pattern_type == "watchtower_false_positive_high":
        return {
            "candidate_type": "watchtower_trigger_rule",
            "title": f"Watchtower {component} 可能过于敏感",
            "suggested_change": f"建议人工复核 Watchtower {component} 的 attention/decision 阈值；可以考虑提高阈值，或要求同时满足 5D 跌幅、20D 回撤、相对 benchmark 走弱等组合条件，并先做 shadow 验证。",
            "expected_impact": "减少 false positive，降低 Auto Decision 预算浪费，让每日巡检更聚焦。",
            "risk_of_change": "阈值提高可能漏掉早期风险信号，需要用后续 forward evaluation 观察。",
        }
    if pattern.pattern_type == "watchtower_rule_effective":
        return {
            "candidate_type": "watchtower_trigger_rule",
            "title": f"Watchtower {component} 当前有效，建议保留",
            "suggested_change": f"建议保留 Watchtower {component} 当前逻辑，并把该样本作为后续规则版本对照证据；暂不建议削弱。",
            "expected_impact": "保留有效提醒能力，避免把有价值的 attention 信号误删。",
            "risk_of_change": "过度依赖历史样本可能忽略市场 regime 变化，仍需继续观察。",
        }
    if pattern.pattern_type == "auto_decision_add_like_bad_action_high":
        return {
            "candidate_type": "auto_decision_selector",
            "title": "Auto Decision add-like 触发后 bad_action 偏高",
            "suggested_change": "建议人工复核 add-like 触发链路：检查 Watchtower 是否过早触发，考虑在 Auto Decision selector 中增加 benchmark_relative_return、max_drawdown 或 pullback confirmation 的历史约束，并 shadow 观察。",
            "expected_impact": "降低过早加仓和预算浪费，提高 add-like 决策的风险收益质量。",
            "risk_of_change": "增强确认条件可能错过部分快速反弹机会，尤其是 AI 主线资产。",
        }
    if pattern.pattern_type == "auto_decision_hold_like_missed_opportunity_high":
        return {
            "candidate_type": "trade_decision_prompt_context",
            "title": "Auto Decision hold-like 后 missed_opportunity 偏高",
            "suggested_change": "建议人工复核 Trade Decision prompt context 中对 add_small、add_on_pullback、hold_no_add 的区分，考虑强调 2035 长期目标下对 AI 主线优质回调的捕捉，但先 shadow 验证。",
            "expected_impact": "提高对主线资产回调机会的捕捉，减少过度保守导致的机会损失。",
            "risk_of_change": "降低保守性可能增加短期回撤和仓位集中风险。",
        }
    if pattern.pattern_type == "auto_decision_reduce_like_too_early":
        return {
            "candidate_type": "risk_gate_review",
            "title": "Auto Decision reduce-like 可能过早",
            "suggested_change": "建议人工复核 risk gate 和 Trade Decision prompt context 是否过度鼓励止盈；可以考虑强调 2035 长期目标、AI 主线持仓纪律，以及“上涨本身不是卖出理由”。",
            "expected_impact": "降低过早止盈或减仓，减少长期主线资产被过早卖飞的概率。",
            "risk_of_change": "减弱减仓约束可能放大集中度和回撤，必须配合组合级风险预算观察。",
        }
    if pattern.pattern_type == "portfolio_report_attention_false_positive_high":
        return {
            "candidate_type": "portfolio_review_rule",
            "title": "Portfolio Report attention queue 可能过宽",
            "suggested_change": "建议人工复核 Portfolio Review action_queue / top_attention 入队阈值，考虑提高 attention 条件或要求组合风险、仓位偏离和后续波动证据同时满足。",
            "expected_impact": "减少组合报告噪音，让人工复核集中在更重要的标的。",
            "risk_of_change": "入队阈值提高可能漏掉早期组合风险或小仓位机会。",
        }
    if pattern.pattern_type == "portfolio_report_attention_effective":
        return {
            "candidate_type": "portfolio_review_rule",
            "title": "Portfolio Report attention queue 当前有效",
            "suggested_change": "建议保留当前 Portfolio Review attention queue 逻辑，并继续用后续 forward evaluation 验证；暂不建议削弱。",
            "expected_impact": "保留组合层面的有效关注排序能力。",
            "risk_of_change": "有效性可能受样本结构影响，需要持续观察不同 source_type 和 horizon。",
        }
    if pattern.pattern_type == "data_quality_price_missing_high":
        return {
            "candidate_type": "data_quality",
            "title": "价格历史或 benchmark 数据质量影响评测",
            "suggested_change": "建议人工检查 price_history index、symbol normalization 和 benchmark SPY 数据覆盖；重点查看 missing/partial/pending 样本中的 symbol 和 source_type。",
            "expected_impact": "提高 Market Evaluation 覆盖率，减少 pending 和 inconclusive 对改进闭环的干扰。",
            "risk_of_change": "数据修复可能改变历史评测口径，需要记录修复批次和重新评测范围。",
        }
    return {
        "candidate_type": "evaluation_design",
        "title": pattern.description,
        "suggested_change": f"建议人工复核该 pattern：{pattern.suggested_direction}",
        "expected_impact": "让系统改进建议更贴近长期样本证据。",
        "risk_of_change": "样本结构可能存在偏差，不能直接据此改规则。",
    }


def _slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value.lower()).strip("_")[:80] or "unknown"
