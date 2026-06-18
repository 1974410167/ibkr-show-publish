from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.domains.portfolio_manager.evaluation.repository import PortfolioEvaluationRepository
from app.domains.portfolio_manager.improvement.pattern_detector import PortfolioImprovementPatternDetector
from app.domains.portfolio_manager.improvement.recommendation_builder import PortfolioImprovementRecommendationBuilder
from app.domains.portfolio_manager.improvement.repository import PortfolioImprovementRepository
from app.domains.portfolio_manager.improvement.schemas import (
    DEFAULT_IMPROVEMENT_HORIZONS,
    PortfolioImprovementReport,
)
from app.domains.portfolio_manager.watchtower.repository import utc_now_iso


class PortfolioImprovementError(ValueError):
    """Raised when a Portfolio Improvement report cannot be fulfilled."""


class PortfolioImprovementService:
    def __init__(
        self,
        *,
        repository: PortfolioImprovementRepository,
        evaluation_repository: PortfolioEvaluationRepository,
        pattern_detector: PortfolioImprovementPatternDetector,
        recommendation_builder: PortfolioImprovementRecommendationBuilder,
    ) -> None:
        self.repository = repository
        self.evaluation_repository = evaluation_repository
        self.pattern_detector = pattern_detector
        self.recommendation_builder = recommendation_builder

    def generate_report(
        self,
        *,
        report_date: str | None = None,
        report_type: str = "manual",
        lookback_days: int = 180,
        horizons: list[str] | None = None,
        min_sample_size: int = 5,
    ) -> PortfolioImprovementReport:
        effective_date = report_date or datetime.now(timezone.utc).date().isoformat()
        selected_horizons = horizons or DEFAULT_IMPROVEMENT_HORIZONS
        report_id = f"portfolio_improvement_report:{effective_date}:{report_type}:{uuid4().hex[:8]}"
        summary = self.evaluation_repository.summarize_results(lookback_days=lookback_days, horizons=selected_horizons)
        raw_results = self.evaluation_repository.list_results(limit=5000)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).date().isoformat()
        results = [
            item
            for item in raw_results
            if str(item.get("evaluation_date") or "") >= cutoff and (not selected_horizons or str(item.get("horizon") or "") in selected_horizons)
        ]
        limitations = list(summary.data_limitations)
        if not results:
            limitations.append("evaluation_results_missing")
        patterns, pattern_limitations = self.pattern_detector.detect_patterns(
            evaluation_results=results,
            evaluation_summary=summary.model_dump(),
            lookback_days=lookback_days,
            horizons=selected_horizons,
            min_sample_size=min_sample_size,
        )
        limitations.extend(pattern_limitations)
        candidates = self.recommendation_builder.build_candidates(patterns=patterns, evaluation_summary=summary.model_dump(), report_id=report_id)
        status = "success" if candidates else "partial_success"
        if not results and summary.total_results == 0:
            status = "partial_success"
        now = utc_now_iso()
        report = PortfolioImprovementReport(
            id=report_id,
            report_date=effective_date,
            report_type=report_type,  # type: ignore[arg-type]
            status=status,  # type: ignore[arg-type]
            lookback_days=lookback_days,
            horizons=selected_horizons,  # type: ignore[arg-type]
            source_evaluation_summary=summary.model_dump(),
            pattern_summary=_pattern_summary(patterns),
            improvement_candidates=candidates,
            recommendation_summary="本报告只提供待人工确认的系统改进建议，不会自动修改任何规则；所有建议都应先经过 shadow / forward evaluation 验证。",
            data_limitations=_dedupe(limitations),
            created_at=now,
            updated_at=now,
        )
        stored = self.repository.create_report(report.model_dump())
        return PortfolioImprovementReport.model_validate(stored)

    def list_reports(self, *, limit: int = 20, report_date: str | None = None) -> list[PortfolioImprovementReport]:
        return [PortfolioImprovementReport.model_validate(item) for item in self.repository.list_reports(limit=limit, report_date=report_date)]

    def get_report(self, report_id: str) -> PortfolioImprovementReport:
        report = self.repository.get_report(report_id)
        if report is None:
            raise PortfolioImprovementError(f"Portfolio improvement report not found: {report_id}")
        return PortfolioImprovementReport.model_validate(report)

    def get_latest_report(self) -> PortfolioImprovementReport:
        report = self.repository.get_latest_report()
        if report is None:
            raise PortfolioImprovementError("Portfolio improvement report not found")
        return PortfolioImprovementReport.model_validate(report)


def _pattern_summary(patterns) -> dict:
    return {
        "total_patterns": len(patterns),
        "high_severity_patterns": sum(1 for item in patterns if item.severity == "high"),
        "medium_severity_patterns": sum(1 for item in patterns if item.severity == "medium"),
        "low_severity_patterns": sum(1 for item in patterns if item.severity == "low"),
    }


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
