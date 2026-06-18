from __future__ import annotations

from app.domains.portfolio_manager.constitution.default_policy import default_constitution_document
from app.domains.portfolio_manager.constitution.schemas import InvestmentConstitution
from app.domains.portfolio_manager.portfolio_review.allocation_analyzer import PortfolioAllocationAnalyzer
from app.domains.portfolio_manager.portfolio_review.exposure_analyzer import PortfolioExposureAnalyzer
from app.domains.portfolio_manager.portfolio_review.report_composer import PortfolioReportComposer
from app.domains.portfolio_manager.portfolio_review.service import PortfolioReviewService
from app.domains.portfolio_manager.universe.schemas import UniverseSymbol
from app.schemas.account import AccountOverviewResponse
from app.schemas.positions import PositionItem, PositionListResponse
from app.utils.pagination import build_pagination_info


class FakeRepository:
    def __init__(self) -> None:
        self.reports: dict[str, dict] = {}

    def create_report(self, report_doc: dict) -> dict:
        stored = {**report_doc, "created_at": "2026-06-15T00:00:00+00:00", "updated_at": "2026-06-15T00:00:00+00:00"}
        self.reports[stored["id"]] = stored
        return stored

    def get_report(self, report_id: str) -> dict | None:
        return self.reports.get(report_id)

    def list_reports(self, **_kwargs) -> list[dict]:
        return list(self.reports.values())

    def get_latest_report(self) -> dict | None:
        return next(reversed(self.reports.values())) if self.reports else None


class FakeConstitutionService:
    def get_current(self):
        return InvestmentConstitution.model_validate({**default_constitution_document(), "created_at": "2026-06-15T00:00:00+00:00", "updated_at": "2026-06-15T00:00:00+00:00"})


class FakeUniverseService:
    def list_symbols(self, universe_type: str | None = None, **_kwargs):
        item = UniverseSymbol(id="universe:AMD", symbol="AMD", display_symbol="AMD", name="AMD", universe_type="holding", theme_tags=["AI"], ai_theme_role="semiconductor", priority="high", enabled=True, scan_frequency="daily", decision_frequency="event_driven", max_llm_runs_per_week=3, source="manual", notes="", created_at="2026-06-15T00:00:00+00:00", updated_at="2026-06-15T00:00:00+00:00")
        return [item] if universe_type == "holding" else []


class FakePositionService:
    def __init__(self, positions: list[PositionItem]) -> None:
        self.positions = positions

    def list_positions(self, **_kwargs):
        return PositionListResponse(items=self.positions, pagination=build_pagination_info(1, 1000, len(self.positions)))


class FakeAccountService:
    def get_overview(self):
        return AccountOverviewResponse(account_id="U1", report_date="2026-06-15", total_equity=90000, cash=10000)


class FakeWatchtowerService:
    class Repo:
        def get_latest_run(self):
            return None

    repository = Repo()


class FakeAutoDecisionService:
    class Repo:
        def get_latest_run(self):
            return None

    repository = Repo()


def _service(positions: list[PositionItem]) -> tuple[PortfolioReviewService, FakeRepository]:
    repo = FakeRepository()
    return (
        PortfolioReviewService(
            repository=repo,
            constitution_service=FakeConstitutionService(),
            universe_service=FakeUniverseService(),
            watchtower_service=FakeWatchtowerService(),
            auto_decision_service=FakeAutoDecisionService(),
            position_service=FakePositionService(positions),
            account_service=FakeAccountService(),
            exposure_analyzer=PortfolioExposureAnalyzer(),
            allocation_analyzer=PortfolioAllocationAnalyzer(),
            report_composer=PortfolioReportComposer(),
        ),
        repo,
    )


def test_service_generate_report_saves_and_queries_with_missing_runs() -> None:
    service, _repo = _service([PositionItem(account_id="U1", report_date="2026-06-15", symbol="AMD", position_value=18000)])

    report = service.generate_report(report_date="2026-06-15")

    assert report.status == "partial_success"
    assert "watchtower_run_missing" in report.data_limitations
    assert "auto_decision_run_missing" in report.data_limitations
    assert service.get_report(report.id).id == report.id
    assert service.get_latest_report().id == report.id
    assert service.list_reports()[0].id == report.id


def test_service_empty_positions_still_generates_partial_report_with_universe() -> None:
    service, _repo = _service([])

    report = service.generate_report(report_date="2026-06-15")

    assert report.status == "partial_success"
    assert report.portfolio_health_score < 100
