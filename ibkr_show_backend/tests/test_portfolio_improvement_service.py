from __future__ import annotations

from app.domains.portfolio_manager.evaluation.repository import build_summary
from app.domains.portfolio_manager.improvement.pattern_detector import PortfolioImprovementPatternDetector
from app.domains.portfolio_manager.improvement.recommendation_builder import PortfolioImprovementRecommendationBuilder
from app.domains.portfolio_manager.improvement.service import PortfolioImprovementService


def _eval(idx: int, label: str = "false_positive") -> dict:
    return {
        "id": f"portfolio_eval:{idx}",
        "evaluation_date": "2026-07-01",
        "source_type": "watchtower_item",
        "source_id": f"watchtower_item:{idx}",
        "source_status": "decision_required",
        "source_action": None,
        "source_snapshot": {"trigger_reasons": [{"code": "consecutive_down_days"}]},
        "symbol": "AMD",
        "horizon": "20d",
        "price_data_status": "ok",
        "evaluation_label": label,
    }


class ImprovementRepo:
    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}

    def create_report(self, report_doc):
        self.docs[report_doc["id"]] = report_doc
        return report_doc

    def list_reports(self, **_kwargs):
        return list(self.docs.values())

    def get_report(self, report_id):
        return self.docs.get(report_id)

    def get_latest_report(self):
        return next(iter(self.docs.values()), None)


class EvalRepo:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs

    def summarize_results(self, lookback_days=180, horizons=None):
        return build_summary(self.docs, lookback_days=lookback_days, horizons=horizons or [])

    def list_results(self, **_kwargs):
        return self.docs


def _service(docs: list[dict]) -> PortfolioImprovementService:
    return PortfolioImprovementService(
        repository=ImprovementRepo(),
        evaluation_repository=EvalRepo(docs),
        pattern_detector=PortfolioImprovementPatternDetector(),
        recommendation_builder=PortfolioImprovementRecommendationBuilder(),
    )


def test_service_generate_report_from_evaluation_results() -> None:
    report = _service([_eval(i) for i in range(5)]).generate_report(report_date="2026-07-15", lookback_days=365)

    assert report.status == "success"
    assert report.horizons == ["5d", "20d", "60d"]
    assert report.pattern_summary["total_patterns"] == 1
    assert report.improvement_candidates[0].requires_human_approval is True
    assert report.improvement_candidates[0].status == "proposed"


def test_service_empty_results_generates_partial_report_with_limitation() -> None:
    report = _service([]).generate_report(report_date="2026-07-15")

    assert report.status == "partial_success"
    assert report.improvement_candidates == []
    assert "evaluation_results_missing" in report.data_limitations


def test_service_min_sample_size_is_respected() -> None:
    report = _service([_eval(i) for i in range(5)]).generate_report(report_date="2026-07-15", min_sample_size=6)

    assert report.improvement_candidates == []
    assert any(item.startswith("ignored_pattern_below_min_sample") for item in report.data_limitations)
