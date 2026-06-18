from __future__ import annotations

from app.domains.portfolio_manager.improvement.pattern_detector import PortfolioImprovementPatternDetector


def _doc(
    idx: int,
    *,
    source_type: str = "watchtower_item",
    label: str = "false_positive",
    action: str | None = None,
    status: str = "decision_required",
    horizon: str = "20d",
    price_status: str = "ok",
    trigger_code: str = "consecutive_down_days",
) -> dict:
    snapshot = {"trigger_reasons": [{"code": trigger_code}]} if source_type == "watchtower_item" else {}
    return {
        "id": f"portfolio_eval:{source_type}:{idx}:{horizon}",
        "evaluation_date": "2026-07-01",
        "source_type": source_type,
        "source_id": f"{source_type}:{idx}",
        "source_status": status,
        "source_action": action,
        "source_snapshot": snapshot,
        "horizon": horizon,
        "price_data_status": price_status,
        "evaluation_label": label,
    }


def _detect(docs: list[dict], min_sample_size: int = 5):
    return PortfolioImprovementPatternDetector().detect_patterns(
        evaluation_results=docs,
        evaluation_summary={},
        lookback_days=180,
        horizons=["5d", "20d", "60d"],
        min_sample_size=min_sample_size,
    )


def test_sample_size_below_three_does_not_generate_pattern() -> None:
    patterns, limitations = _detect([_doc(1), _doc(2)])

    assert patterns == []
    assert "evaluation_sample_too_small" in limitations


def test_sample_size_below_minimum_is_ignored() -> None:
    patterns, limitations = _detect([_doc(i) for i in range(4)])

    assert patterns == []
    assert any(item.startswith("ignored_pattern_below_min_sample") for item in limitations)


def test_watchtower_false_positive_high_pattern() -> None:
    patterns, _ = _detect([_doc(i, label="false_positive") for i in range(5)])

    assert [item.pattern_type for item in patterns] == ["watchtower_false_positive_high"]
    assert patterns[0].affected_module == "watchtower"
    assert patterns[0].confidence == "low"


def test_watchtower_useful_attention_effective_pattern() -> None:
    patterns, _ = _detect([_doc(i, label="useful_attention") for i in range(5)])

    assert patterns[0].pattern_type == "watchtower_rule_effective"
    assert patterns[0].severity == "low"


def test_auto_decision_add_like_bad_action_high_pattern() -> None:
    docs = [_doc(i, source_type="auto_decision_item", label="bad_action", action="add_on_pullback") for i in range(5)]
    patterns, _ = _detect(docs)

    assert patterns[0].pattern_type == "auto_decision_add_like_bad_action_high"
    assert patterns[0].severity == "high"


def test_auto_decision_hold_like_missed_opportunity_high_pattern() -> None:
    docs = [_doc(i, source_type="auto_decision_item", label="missed_opportunity", action="hold") for i in range(5)]
    patterns, _ = _detect(docs)

    assert patterns[0].pattern_type == "auto_decision_hold_like_missed_opportunity_high"


def test_auto_decision_reduce_like_too_early_pattern() -> None:
    docs = [_doc(i, source_type="auto_decision_item", label="bad_action", action="reduce") for i in range(5)]
    patterns, _ = _detect(docs)

    assert patterns[0].pattern_type == "auto_decision_reduce_like_too_early"


def test_portfolio_report_false_positive_pattern() -> None:
    docs = [_doc(i, source_type="portfolio_report", label="false_positive", action="manual_review", status="top_attention") for i in range(5)]
    patterns, _ = _detect(docs)

    assert patterns[0].pattern_type == "portfolio_report_attention_false_positive_high"


def test_data_quality_missing_high_pattern() -> None:
    docs = [_doc(i, source_type="auto_decision_item", label="pending", action="hold", price_status="missing") for i in range(5)]
    patterns, _ = _detect(docs)

    assert any(item.pattern_type == "data_quality_price_missing_high" for item in patterns)


def test_single_result_never_generates_strong_conclusion() -> None:
    patterns, limitations = _detect([_doc(1)])

    assert patterns == []
    assert "evaluation_sample_too_small" in limitations
