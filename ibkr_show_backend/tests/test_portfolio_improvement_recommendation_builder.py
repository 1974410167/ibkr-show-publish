from __future__ import annotations

from app.domains.portfolio_manager.improvement.recommendation_builder import PortfolioImprovementRecommendationBuilder
from app.domains.portfolio_manager.improvement.schemas import PortfolioImprovementPattern


def _pattern(pattern_type: str = "watchtower_false_positive_high") -> PortfolioImprovementPattern:
    return PortfolioImprovementPattern(
        pattern_type=pattern_type,
        source_type="watchtower_item",
        group_key="trigger:consecutive_down_days",
        affected_module="watchtower",
        affected_rule_or_component="consecutive_down_days",
        severity="medium",
        confidence="medium",
        sample_size=8,
        horizons=["20d", "60d"],
        labels={"false_positive": 5, "inconclusive": 3},
        metrics={"false_positive_rate": 0.625, "useful_attention_rate": 0},
        evidence_result_ids=[f"portfolio_eval:{idx}" for idx in range(12)],
        description="description",
        suggested_direction="direction",
    )


def test_builder_candidates_are_human_approval_proposed_with_evidence() -> None:
    candidates = PortfolioImprovementRecommendationBuilder().build_candidates(
        patterns=[_pattern()],
        evaluation_summary={},
        report_id="portfolio_improvement_report:test",
    )

    candidate = candidates[0]
    assert candidate.requires_human_approval is True
    assert candidate.status == "proposed"
    assert candidate.evidence_summary.sample_size == 8
    assert candidate.evidence_summary.labels["false_positive"] == 5
    assert len(candidate.evidence_summary.example_result_ids) == 10
    assert candidate.affected_versions["portfolio_manager_version"] == "unknown"
    assert "建议人工复核" in candidate.suggested_change
    assert candidate.risk_of_change


def test_builder_maps_data_quality_to_data_quality_candidate() -> None:
    pattern = _pattern("data_quality_price_missing_high")
    pattern.affected_module = "data_quality"
    pattern.affected_rule_or_component = "price_history"

    candidate = PortfolioImprovementRecommendationBuilder().build_candidates(patterns=[pattern], evaluation_summary={}, report_id="r")[0]

    assert candidate.candidate_type == "data_quality"
    assert "symbol normalization" in candidate.suggested_change
