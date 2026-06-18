from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.schemas.trade_decision import (
    TradeDecisionBehaviorCoachingHint,
    TradeDecisionBehaviorInsight,
    TradeDecisionBehaviorProfileItem,
    TradeDecisionBehaviorProfileResponse,
    TradeDecisionBehaviorProfileSummary,
    TradeDecisionExecutionAlignmentItem,
    TradeDecisionOverrideAnnotation,
)
from app.services.longbridge_service import normalize_longbridge_symbol
from app.services.trade_decision_execution_alignment import TradeDecisionExecutionAlignmentService
from app.services.trade_decision_override_annotation_repository import TradeDecisionOverrideAnnotationRepository


class TradeDecisionBehaviorProfileService:
    def __init__(
        self,
        alignment_service: TradeDecisionExecutionAlignmentService,
        annotation_repository: TradeDecisionOverrideAnnotationRepository,
    ) -> None:
        self.alignment_service = alignment_service
        self.annotation_repository = annotation_repository

    def build_profile(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        days: int = 180,
        symbol: str | None = None,
        decision_type: str | None = None,
        behavior_tag: str | None = None,
        reason_category: str | None = None,
        min_count: int = 1,
        limit: int = 1000,
    ) -> TradeDecisionBehaviorProfileResponse:
        end_date = end_date or datetime.now(timezone.utc).date()
        start_date = start_date or (end_date - timedelta(days=days))
        normalized_symbol = normalize_longbridge_symbol(symbol) if symbol else None
        alignment = self.alignment_service.build_alignment(
            start_date=start_date,
            end_date=end_date,
            days=days,
            symbol=normalized_symbol,
            decision_type=decision_type,
            limit=limit,
        )
        annotations = self.annotation_repository.list_annotations(
            symbol=normalized_symbol,
            reason_category=reason_category,
            days=days,
            limit=limit,
        )
        annotation_by_decision = {
            str(annotation.get("decision_id") or ""): TradeDecisionOverrideAnnotation(**annotation)
            for annotation in annotations
            if annotation.get("decision_id")
        }
        items: list[TradeDecisionBehaviorProfileItem] = []
        for item in alignment.items:
            annotation = annotation_by_decision.get(item.decision_id)
            if reason_category and annotation is None:
                continue
            merged_tags = _merged_behavior_tags(item, annotation)
            if behavior_tag and behavior_tag not in merged_tags:
                continue
            items.append(_profile_item(item, merged_tags, annotation))

        summary = _summarize_profile(
            items,
            start_date=start_date,
            end_date=end_date,
            total_decisions=alignment.summary.total_decisions,
            evaluated_decisions=alignment.summary.evaluated_decisions,
            alignment_rate=alignment.summary.alignment_rate,
            data_limitations=alignment.summary.data_limitations,
            min_count=min_count,
        )
        return TradeDecisionBehaviorProfileResponse(
            summary=summary,
            insights=summary.dominant_behavior_patterns,
            coaching_hints=summary.coaching_hints,
            items=items[:limit],
        )

    def get_recent_profile_context(self, *, days: int = 180, symbol: str | None = None) -> dict:
        profile = self.build_profile(days=days, symbol=symbol, limit=300)
        summary = profile.summary
        dominant_patterns = [item.pattern for item in profile.insights[:5]]
        recent_lessons = [hint.message for hint in profile.coaching_hints if hint.source == "manual_annotation"][:5]
        coaching_hints = [
            {
                "pattern": hint.pattern,
                "severity": hint.severity,
                "message": hint.message,
                "symbols": hint.symbols[:5],
                "source": hint.source,
            }
            for hint in profile.coaching_hints[:5]
        ]
        reminder_enabled = bool(dominant_patterns or recent_lessons or coaching_hints)
        return {
            "status": "available",
            "lookback_days": days,
            "scope": "symbol" if symbol else "global",
            "symbol": symbol,
            "behavior_risk_level": summary.behavior_risk_level,
            "dominant_behavior_patterns": dominant_patterns,
            "recent_lessons": recent_lessons,
            "coaching_hints": coaching_hints,
            "top_symbols_with_bias": summary.top_symbols_with_bias[:5],
            "net_behavior_value": summary.net_behavior_value,
            "reminder_enabled": reminder_enabled,
            "data_limitations": summary.data_limitations[:8],
            "source": "behavior_profile_service",
        }


def _profile_item(
    item: TradeDecisionExecutionAlignmentItem,
    behavior_tags: list[str],
    annotation: TradeDecisionOverrideAnnotation | None,
) -> TradeDecisionBehaviorProfileItem:
    contribution = (
        item.estimated_good_override_value
        + item.estimated_avoided_loss
        - item.estimated_opportunity_cost
        - item.estimated_bad_override_cost
    )
    return TradeDecisionBehaviorProfileItem(
        decision_id=item.decision_id,
        symbol=item.symbol,
        decision_date=item.decision_date,
        final_action=item.final_action,
        alignment_label=item.alignment_label,
        behavior_tags=behavior_tags,
        estimated_opportunity_cost=item.estimated_opportunity_cost,
        estimated_avoided_loss=item.estimated_avoided_loss,
        estimated_bad_override_cost=item.estimated_bad_override_cost,
        estimated_good_override_value=item.estimated_good_override_value,
        profile_contribution=round(contribution, 6),
        annotation=annotation,
    )


def _merged_behavior_tags(item: TradeDecisionExecutionAlignmentItem, annotation: TradeDecisionOverrideAnnotation | None) -> list[str]:
    tags = list(dict.fromkeys(item.behavior_tags))
    if annotation:
        for tag in annotation.behavior_tags:
            if tag not in tags:
                tags.append(tag)
        if annotation.override_type and annotation.override_type not in tags:
            tags.append(annotation.override_type)
        if annotation.was_emotional and "emotion_driven_trading" not in tags:
            tags.append("emotion_driven_trading")
    return tags


def _summarize_profile(
    items: list[TradeDecisionBehaviorProfileItem],
    *,
    start_date: date,
    end_date: date,
    total_decisions: int,
    evaluated_decisions: int,
    alignment_rate: float,
    data_limitations: list[str],
    min_count: int,
) -> TradeDecisionBehaviorProfileSummary:
    denominator = max(evaluated_decisions or len(items), 1)
    tag_counter = Counter(tag for item in items for tag in item.behavior_tags)
    reason_counter = Counter(item.annotation.reason_category for item in items if item.annotation)
    manual_override_count = sum(
        1
        for item in items
        if item.annotation or "manual_contrarian_buy" in item.behavior_tags or "manual_contrarian_sell" in item.behavior_tags
    )
    opportunity = sum(item.estimated_opportunity_cost for item in items)
    bad_override_cost = sum(item.estimated_bad_override_cost for item in items)
    good_override_value = sum(item.estimated_good_override_value for item in items)
    net_value = sum(item.profile_contribution for item in items)
    symbol_bias = _symbol_bias(items)
    insights = _build_insights(items, tag_counter, reason_counter, denominator, min_count)
    hints = _build_coaching_hints(insights, items)
    risk_level = _risk_level(insights, net_value, _rate(tag_counter["bad_override"], denominator))
    return TradeDecisionBehaviorProfileSummary(
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        total_decisions=total_decisions,
        evaluated_decisions=evaluated_decisions,
        alignment_rate=alignment_rate,
        manual_override_rate=_rate(manual_override_count, denominator),
        ignored_add_signal_rate=_rate(tag_counter["ignored_add_signal"], denominator),
        ignored_reduce_signal_rate=_rate(tag_counter["ignored_reduce_signal"], denominator),
        contradiction_rate=_rate(sum(1 for item in items if item.alignment_label == "contradicted"), denominator),
        over_execution_rate=_rate(tag_counter["over_sized_execution"], denominator),
        under_execution_rate=_rate(tag_counter["under_sized_execution"], denominator),
        premature_trim_rate=_rate(tag_counter["premature_trim"], denominator),
        good_override_rate=_rate(tag_counter["good_override"], denominator),
        bad_override_rate=_rate(tag_counter["bad_override"], denominator),
        net_behavior_value=round(net_value, 6),
        estimated_opportunity_cost_total=round(opportunity, 6),
        estimated_bad_override_cost_total=round(bad_override_cost, 6),
        estimated_good_override_value_total=round(good_override_value, 6),
        top_behavior_tags=_top(tag_counter),
        top_reason_categories=_top(reason_counter),
        top_symbols_with_bias=symbol_bias,
        behavior_risk_level=risk_level,
        dominant_behavior_patterns=insights,
        coaching_hints=hints,
        generated_at=datetime.now(timezone.utc).isoformat(),
        data_limitations=data_limitations,
    )


def _build_insights(
    items: list[TradeDecisionBehaviorProfileItem],
    tag_counter: Counter[str],
    reason_counter: Counter[str],
    denominator: int,
    min_count: int,
) -> list[TradeDecisionBehaviorInsight]:
    insights: list[TradeDecisionBehaviorInsight] = []
    if _rate(tag_counter["ignored_add_signal"], denominator) > 0.20 and tag_counter["ignored_add_signal"] >= min_count:
        insights.append(_tag_insight(
            "ignored_add_signal",
            "medium" if _rate(tag_counter["ignored_add_signal"], denominator) <= 0.35 else "high",
            tag_counter["ignored_add_signal"],
            denominator,
            items,
            "你经常在 Agent 建议加仓且后续上涨的场景没有执行。",
            "下次出现 underweight + allow_add 时，至少执行 1/3 建议金额，避免完全错过。",
        ))
    if tag_counter["bad_override"] > tag_counter["good_override"] and tag_counter["bad_override"] >= max(3, min_count):
        insights.append(_tag_insight(
            "harmful_manual_override",
            "high",
            tag_counter["bad_override"],
            denominator,
            [item for item in items if "bad_override" in item.behavior_tags],
            "你的反向操作近期效果弱于有利 override，且坏 override 样本已经形成重复模式。",
            "反向操作前强制写下原因，并等待至少一个非情绪证据确认。",
        ))
    if _rate(tag_counter["premature_trim"], denominator) > 0.10 and tag_counter["premature_trim"] >= min_count:
        insights.append(_tag_insight(
            "premature_trim",
            "medium",
            tag_counter["premature_trim"],
            denominator,
            items,
            "你有偏早卖出的倾向，尤其在 Agent 未建议卖出时。",
            "减仓前先确认原始 thesis 是否破坏，而不只看短线波动。",
        ))
    if _rate(tag_counter["under_sized_execution"], denominator) > 0.25 and tag_counter["under_sized_execution"] >= min_count:
        insights.append(_tag_insight(
            "under_sized_execution",
            "medium",
            tag_counter["under_sized_execution"],
            denominator,
            items,
            "你经常执行方向正确但金额过小，导致收益暴露不足。",
            "把 add_small / reduce_small 作为最低执行单位，避免只有象征性交易。",
        ))
    if _rate(tag_counter["over_sized_execution"], denominator) > 0.10 and tag_counter["over_sized_execution"] >= min_count:
        insights.append(_tag_insight(
            "over_sized_execution",
            "high",
            tag_counter["over_sized_execution"],
            denominator,
            items,
            "你有超额执行倾向，可能放大单一标的风险。",
            "执行前复核 max_position_pct 和现金储备，超过计划时拆成下一次复查。",
        ))
    contrarian_buy_loss_items = [item for item in items if "manual_contrarian_buy" in item.behavior_tags and item.estimated_bad_override_cost > 0]
    if len(contrarian_buy_loss_items) >= min_count and sum(item.estimated_bad_override_cost for item in contrarian_buy_loss_items) > 0:
        insights.append(_tag_insight(
            "contrarian_buy_loss",
            "high",
            len(contrarian_buy_loss_items),
            denominator,
            contrarian_buy_loss_items,
            "你在系统不建议买入时手动买入，近期代价较高。",
            "逆向买入前先检查 Risk Gate 和估值/事件证据，避免只凭反弹预期出手。",
        ))
    emotion_count = reason_counter["emotion"] + tag_counter["emotion_driven_trading"]
    if _rate(emotion_count, max(sum(reason_counter.values()), 1)) > 0.30 and emotion_count >= min_count:
        insights.append(TradeDecisionBehaviorInsight(
            pattern="emotion_driven_trading",
            severity="high" if emotion_count >= 3 else "medium",
            count=emotion_count,
            rate=_rate(emotion_count, max(sum(reason_counter.values()), 1)),
            estimated_cost=round(sum(item.estimated_bad_override_cost for item in items if item.annotation and item.annotation.reason_category == "emotion"), 6),
            symbols=_symbols_for(items, "emotion_driven_trading"),
            description="情绪类 override 占比较高，可能让交易偏离原计划。",
            suggestion="交易前增加冷静期，并把情绪原因和客观证据分开记录。",
        ))
    return insights


def _tag_insight(
    pattern: str,
    severity: str,
    count: int,
    denominator: int,
    items: list[TradeDecisionBehaviorProfileItem],
    description: str,
    suggestion: str,
) -> TradeDecisionBehaviorInsight:
    relevant = [item for item in items if pattern in item.behavior_tags or pattern == "harmful_manual_override"]
    if not relevant:
        relevant = items
    estimated_cost = sum(item.estimated_opportunity_cost + item.estimated_bad_override_cost for item in relevant)
    return TradeDecisionBehaviorInsight(
        pattern=pattern,
        severity=severity,
        count=count,
        rate=_rate(count, denominator),
        estimated_cost=round(estimated_cost, 6),
        symbols=_top_symbols(relevant),
        description=description,
        suggestion=suggestion,
    )


def _build_coaching_hints(
    insights: list[TradeDecisionBehaviorInsight],
    items: list[TradeDecisionBehaviorProfileItem],
) -> list[TradeDecisionBehaviorCoachingHint]:
    hints = [
        TradeDecisionBehaviorCoachingHint(
            pattern=insight.pattern,
            severity=insight.severity,
            message=insight.suggestion,
            symbols=insight.symbols,
        )
        for insight in insights
    ]
    for item in items:
        annotation = item.annotation
        if annotation and annotation.should_remind_next_time and annotation.lesson:
            hints.append(TradeDecisionBehaviorCoachingHint(
                pattern=annotation.override_type or annotation.reason_category,
                severity="medium",
                message=annotation.lesson,
                symbols=[item.symbol],
                source="manual_annotation",
                annotation_decision_id=item.decision_id,
            ))
    return hints[:12]


def _risk_level(insights: list[TradeDecisionBehaviorInsight], net_value: float, bad_override_rate: float) -> str:
    high_count = sum(1 for item in insights if item.severity == "high")
    if high_count >= 2 or bad_override_rate > 0.15 or net_value < -5000:
        return "high"
    if insights or net_value < 0:
        return "medium"
    return "low"


def _symbol_bias(items: list[TradeDecisionBehaviorProfileItem]) -> list[dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"key": "", "count": 0, "estimated_cost": 0.0, "tags": Counter()})
    bias_tags = {
        "ignored_add_signal",
        "ignored_reduce_signal",
        "manual_contrarian_buy",
        "manual_contrarian_sell",
        "bad_override",
        "premature_trim",
        "under_sized_execution",
        "over_sized_execution",
    }
    for item in items:
        tags = [tag for tag in item.behavior_tags if tag in bias_tags]
        if not tags:
            continue
        entry = stats[item.symbol]
        entry["key"] = item.symbol
        entry["count"] += 1
        entry["estimated_cost"] += item.estimated_opportunity_cost + item.estimated_bad_override_cost
        entry["tags"].update(tags)
    result = []
    for entry in stats.values():
        result.append({
            "key": entry["key"],
            "count": entry["count"],
            "estimated_cost": round(entry["estimated_cost"], 6),
            "top_tags": _top(entry["tags"], limit=5),
        })
    return sorted(result, key=lambda item: (item["estimated_cost"], item["count"]), reverse=True)[:10]


def _symbols_for(items: list[TradeDecisionBehaviorProfileItem], tag: str) -> list[str]:
    return _top_symbols([item for item in items if tag in item.behavior_tags])


def _top_symbols(items: list[TradeDecisionBehaviorProfileItem]) -> list[str]:
    return [item["key"] for item in _top(Counter(item.symbol for item in items), limit=5)]


def _top(counter: Counter[str], *, limit: int = 10) -> list[dict[str, Any]]:
    return [{"key": key, "count": count} for key, count in counter.most_common(limit)]


def _rate(numerator: int | float, denominator: int | float) -> float:
    if denominator <= 0:
        return 0.0
    return round(float(numerator) / float(denominator), 6)
