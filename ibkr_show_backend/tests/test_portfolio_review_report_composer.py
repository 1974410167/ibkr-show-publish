from __future__ import annotations

from app.domains.portfolio_manager.constitution.default_policy import default_constitution_document
from app.domains.portfolio_manager.constitution.schemas import InvestmentConstitution
from app.domains.portfolio_manager.portfolio_review.report_composer import PortfolioReportComposer
from app.domains.portfolio_manager.portfolio_review.schemas import (
    PortfolioAIThemeExposure,
    PortfolioAllocationAnalysis,
    PortfolioCashStatus,
    PortfolioConcentrationRisk,
    PortfolioExposureAnalysis,
    PortfolioGoalTracking,
)


def _constitution() -> InvestmentConstitution:
    return InvestmentConstitution.model_validate({**default_constitution_document(), "created_at": "2026-06-15T00:00:00+00:00", "updated_at": "2026-06-15T00:00:00+00:00"})


def test_report_composer_scores_health_and_generates_safe_text() -> None:
    exposure = PortfolioExposureAnalysis(
        ai_theme_exposure=PortfolioAIThemeExposure(total_ai_exposure_pct=0.3, fake_ai_story_exposure_pct=0.05, assessment="misaligned"),
        concentration_risk=PortfolioConcentrationRisk(top1_weight=0.25, top3_weight=0.6, top5_weight=0.8, single_name_risk_symbols=["AMD"], assessment="high"),
        data_limitations=["total_equity_unavailable"],
    )
    allocation = PortfolioAllocationAnalysis(
        goal_tracking=PortfolioGoalTracking(target_account_value_usd=1500000, target_date="2035-12-31", summary="unknown"),
        cash_status=PortfolioCashStatus(cash_value=1000, cash_pct=0.01, assessment="too_low", summary="low"),
        data_limitations=["cash_unavailable"],
    )

    report = PortfolioReportComposer().compose(
        report_id="portfolio_report:test",
        report_date="2026-06-15",
        report_type="manual",
        constitution=_constitution(),
        exposure=exposure,
        allocation=allocation,
        source_watchtower_run_id=None,
        source_auto_decision_run_id=None,
        watchtower_decision_required_count=3,
        auto_decision_failed_count=1,
    )

    assert report["portfolio_health_score"] == 5
    assert report["portfolio_health_level"] == "high_risk"
    assert "不是买卖指令" in report["summary"]
    assert any("不会自动下单" in item for item in report["next_steps"])
    assert report["status"] == "partial_success"
