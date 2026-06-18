from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from app.domains.portfolio_manager.evaluation.outcome_evaluator import ADD_LIKE_ACTIONS, HOLD_LIKE_ACTIONS, REDUCE_LIKE_ACTIONS
from app.domains.portfolio_manager.improvement.schemas import PortfolioImprovementPattern


class PortfolioImprovementPatternDetector:
    def detect_patterns(
        self,
        *,
        evaluation_results: list[dict],
        evaluation_summary: dict,
        lookback_days: int,
        horizons: list[str],
        min_sample_size: int = 5,
    ) -> tuple[list[PortfolioImprovementPattern], list[str]]:
        del evaluation_summary, lookback_days
        limitations: list[str] = []
        selected = [item for item in evaluation_results if not horizons or str(item.get("horizon") or "") in horizons]
        if len(selected) < 3:
            limitations.append("evaluation_sample_too_small")
            return [], limitations

        patterns: list[PortfolioImprovementPattern] = []
        patterns.extend(self._watchtower_patterns(selected, min_sample_size, limitations))
        patterns.extend(self._auto_decision_patterns(selected, min_sample_size, limitations))
        patterns.extend(self._portfolio_report_patterns(selected, min_sample_size, limitations))
        patterns.extend(self._data_quality_patterns(selected, min_sample_size, limitations))
        return patterns, _dedupe(limitations)

    def _watchtower_patterns(self, docs: list[dict], min_sample_size: int, limitations: list[str]) -> list[PortfolioImprovementPattern]:
        groups = _group_by([item for item in docs if item.get("source_type") == "watchtower_item"], _watchtower_group_key)
        patterns: list[PortfolioImprovementPattern] = []
        for key, items in groups.items():
            if len(items) < 3:
                limitations.append(f"ignored_pattern_sample_too_small:{key}")
                continue
            if len(items) < min_sample_size:
                limitations.append(f"ignored_pattern_below_min_sample:{key}")
                continue
            metrics = _label_metrics(items)
            false_positive_rate = float(metrics.get("false_positive_rate") or 0.0)
            useful_attention_rate = float(metrics.get("useful_attention_rate") or 0.0)
            if false_positive_rate >= 0.45 and useful_attention_rate <= 0.35:
                patterns.append(_pattern(items, "watchtower_false_positive_high", "watchtower", _component_from_key(key), "watchtower", key, _severity(false_positive_rate, high_at=0.65), "Watchtower 触发规则在多个评测窗口里 false_positive 偏高。", "规则可能过于敏感，需要人工复核阈值或增加组合条件。", metrics))
            elif useful_attention_rate >= 0.60:
                patterns.append(_pattern(items, "watchtower_rule_effective", "watchtower", _component_from_key(key), "watchtower", key, "low", "Watchtower 触发规则在多个评测窗口里 useful_attention 偏高。", "当前规则有保留价值，暂不建议削弱，可作为后续规则版本证据。", metrics))
        return patterns

    def _auto_decision_patterns(self, docs: list[dict], min_sample_size: int, limitations: list[str]) -> list[PortfolioImprovementPattern]:
        auto_docs = [item for item in docs if item.get("source_type") == "auto_decision_item"]
        grouped = _group_by(auto_docs, _auto_group_key)
        patterns: list[PortfolioImprovementPattern] = []
        for key, items in grouped.items():
            if len(items) < 3:
                limitations.append(f"ignored_pattern_sample_too_small:{key}")
                continue
            if len(items) < min_sample_size:
                limitations.append(f"ignored_pattern_below_min_sample:{key}")
                continue
            metrics = _label_metrics(items)
            action_group = str(metrics.get("action_group") or "")
            bad_action_rate = float(metrics.get("bad_action_rate") or 0.0)
            missed_opportunity_rate = float(metrics.get("missed_opportunity_rate") or 0.0)
            if action_group == "add_like" and bad_action_rate >= 0.35:
                patterns.append(_pattern(items, "auto_decision_add_like_bad_action_high", "auto_decision", "add_like_actions", "auto_decision_item", key, "high", "Auto Decision add-like 动作后 bad_action 偏高。", "需要人工复核触发是否太早、AI 主线标的是否过度激进，以及 risk/reward 或 pullback confirmation 是否足够。", metrics))
            elif action_group == "hold_like" and missed_opportunity_rate >= 0.35:
                patterns.append(_pattern(items, "auto_decision_hold_like_missed_opportunity_high", "trade_decision_prompt_context", "hold_like_actions", "auto_decision_item", key, _severity(missed_opportunity_rate, high_at=0.55), "Auto Decision hold-like 动作后 missed_opportunity 偏高。", "可能存在过度保守，需要人工复核 add_on_pullback 或 small add 的上下文表达。", metrics))
            elif action_group == "reduce_like" and bad_action_rate >= 0.30:
                patterns.append(_pattern(items, "auto_decision_reduce_like_too_early", "risk_gate_review", "reduce_like_actions", "auto_decision_item", key, "high", "Auto Decision reduce-like 动作后 bad_action 偏高。", "可能存在过早止盈或减仓，需要人工复核是否与 2035 长期目标和 AI 主线冲突。", metrics))
        return patterns

    def _portfolio_report_patterns(self, docs: list[dict], min_sample_size: int, limitations: list[str]) -> list[PortfolioImprovementPattern]:
        grouped = _group_by([item for item in docs if item.get("source_type") == "portfolio_report"], lambda item: f"portfolio_report:{item.get('source_status') or 'attention'}:{item.get('source_action') or 'unknown'}")
        patterns: list[PortfolioImprovementPattern] = []
        for key, items in grouped.items():
            if len(items) < 3:
                limitations.append(f"ignored_pattern_sample_too_small:{key}")
                continue
            if len(items) < min_sample_size:
                limitations.append(f"ignored_pattern_below_min_sample:{key}")
                continue
            metrics = _label_metrics(items)
            false_positive_rate = float(metrics.get("false_positive_rate") or 0.0)
            useful_attention_rate = float(metrics.get("useful_attention_rate") or 0.0)
            if false_positive_rate >= 0.45:
                patterns.append(_pattern(items, "portfolio_report_attention_false_positive_high", "portfolio_review", "attention_queue", "portfolio_report", key, "medium", "Portfolio Report attention 后 false_positive 偏高。", "action_queue / top_attention 可能过宽，需要人工复核入队阈值。", metrics))
            elif useful_attention_rate >= 0.60:
                patterns.append(_pattern(items, "portfolio_report_attention_effective", "portfolio_review", "attention_queue", "portfolio_report", key, "low", "Portfolio Report attention 后 useful_attention 偏高。", "当前组合报告 attention queue 有价值，暂不建议削弱。", metrics))
        return patterns

    def _data_quality_patterns(self, docs: list[dict], min_sample_size: int, limitations: list[str]) -> list[PortfolioImprovementPattern]:
        grouped = _group_by(docs, lambda item: f"data_quality:{item.get('source_type') or 'unknown'}")
        patterns: list[PortfolioImprovementPattern] = []
        for key, items in grouped.items():
            if len(items) < 3:
                limitations.append(f"ignored_pattern_sample_too_small:{key}")
                continue
            if len(items) < min_sample_size:
                limitations.append(f"ignored_pattern_below_min_sample:{key}")
                continue
            metrics = _label_metrics(items)
            pending_or_missing = sum(1 for item in items if item.get("evaluation_label") == "pending" or item.get("price_data_status") in {"missing", "partial", "pending"})
            rate = round(pending_or_missing / len(items), 6)
            if rate >= 0.50:
                metrics["pending_or_price_issue_rate"] = rate
                patterns.append(_pattern(items, "data_quality_price_missing_high", "data_quality", "price_history", str(items[0].get("source_type") or "unknown"), key, "high", "评测样本中 pending 或 price_data_status missing/partial/pending 占比偏高。", "需要人工检查价格历史、symbol normalization 和 benchmark SPY 数据覆盖。", metrics))
        return patterns


def _group_by(items: list[dict], key_fn) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        groups[key_fn(item)].append(item)
    return groups


def _watchtower_group_key(item: dict) -> str:
    trigger_code = _first_trigger_code(item.get("source_snapshot") or {})
    if trigger_code:
        return f"trigger:{trigger_code}"
    return f"status:{item.get('source_status') or 'unknown'}:action:{item.get('source_action') or 'unknown'}"


def _first_trigger_code(snapshot: dict) -> str | None:
    candidates: list[Any] = []
    for key in ("trigger_reasons", "triggers"):
        value = snapshot.get(key)
        if isinstance(value, list):
            candidates.extend(value)
    nested = snapshot.get("source") if isinstance(snapshot.get("source"), dict) else {}
    if nested:
        value = nested.get("trigger_reasons")
        if isinstance(value, list):
            candidates.extend(value)
    for item in candidates:
        if isinstance(item, dict) and item.get("code"):
            return str(item["code"])
    return None


def _auto_group_key(item: dict) -> str:
    action = str(item.get("source_action") or "").lower()
    return f"action_group:{_action_group(action)}:action:{action or 'unknown'}"


def _action_group(action: str) -> str:
    if action in ADD_LIKE_ACTIONS:
        return "add_like"
    if action in HOLD_LIKE_ACTIONS:
        return "hold_like"
    if action in REDUCE_LIKE_ACTIONS:
        return "reduce_like"
    return "other"


def _label_metrics(items: list[dict]) -> dict[str, float | int | str]:
    labels = Counter(str(item.get("evaluation_label") or "unknown") for item in items)
    total = len(items)
    completed = max(1, total - labels.get("pending", 0))
    action_groups = Counter(_action_group(str(item.get("source_action") or "").lower()) for item in items)
    metrics: dict[str, float | int | str] = {
        "sample_size": total,
        "completed_sample_size": completed,
        "false_positive_rate": round(labels.get("false_positive", 0) / completed, 6),
        "useful_attention_rate": round(labels.get("useful_attention", 0) / completed, 6),
        "bad_action_rate": round(labels.get("bad_action", 0) / completed, 6),
        "missed_opportunity_rate": round(labels.get("missed_opportunity", 0) / completed, 6),
        "pending_rate": round(labels.get("pending", 0) / total, 6),
    }
    if action_groups:
        metrics["action_group"] = action_groups.most_common(1)[0][0]
    return metrics


def _pattern(
    items: list[dict],
    pattern_type: str,
    affected_module: str,
    affected_rule_or_component: str,
    source_type: str,
    group_key: str,
    severity: str,
    description: str,
    suggested_direction: str,
    metrics: dict,
) -> PortfolioImprovementPattern:
    labels = Counter(str(item.get("evaluation_label") or "unknown") for item in items)
    horizons = sorted({str(item.get("horizon") or "") for item in items if item.get("horizon")})
    confidence = _confidence(len(items))
    if len(items) < 5:
        confidence = "low"
    return PortfolioImprovementPattern(
        pattern_type=pattern_type,
        source_type=source_type,
        group_key=group_key,
        affected_module=affected_module,
        affected_rule_or_component=affected_rule_or_component,
        severity=severity,  # type: ignore[arg-type]
        confidence=confidence,  # type: ignore[arg-type]
        sample_size=len(items),
        horizons=horizons,
        labels=dict(labels),
        metrics=metrics,
        evidence_result_ids=[str(item.get("id")) for item in items if item.get("id")][:10],
        description=description,
        suggested_direction=suggested_direction,
    )


def _component_from_key(key: str) -> str:
    if key.startswith("trigger:"):
        return key.removeprefix("trigger:")
    return key


def _severity(rate: float, *, high_at: float) -> str:
    return "high" if rate >= high_at else "medium"


def _confidence(sample_size: int) -> str:
    if sample_size >= 20:
        return "high"
    if sample_size >= 8:
        return "medium"
    return "low"


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
