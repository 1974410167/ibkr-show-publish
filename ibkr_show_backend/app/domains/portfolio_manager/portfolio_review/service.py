from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.domains.portfolio_manager.constitution.service import PortfolioConstitutionService
from app.domains.portfolio_manager.decision_orchestrator.service import PortfolioAutoDecisionService
from app.domains.portfolio_manager.portfolio_review.allocation_analyzer import PortfolioAllocationAnalyzer
from app.domains.portfolio_manager.portfolio_review.exposure_analyzer import PortfolioExposureAnalyzer
from app.domains.portfolio_manager.portfolio_review.report_composer import PortfolioReportComposer
from app.domains.portfolio_manager.portfolio_review.repository import PortfolioReviewRepository
from app.domains.portfolio_manager.portfolio_review.schemas import PortfolioManagerReport
from app.domains.portfolio_manager.universe.service import PortfolioUniverseService
from app.domains.portfolio_manager.watchtower.service import PortfolioWatchtowerService
from app.services.account_service import AccountService
from app.services.position_service import PositionService


class PortfolioReviewError(ValueError):
    """Raised when a portfolio manager report request cannot be fulfilled."""


class PortfolioReviewService:
    def __init__(
        self,
        *,
        repository: PortfolioReviewRepository,
        constitution_service: PortfolioConstitutionService,
        universe_service: PortfolioUniverseService,
        watchtower_service: PortfolioWatchtowerService,
        auto_decision_service: PortfolioAutoDecisionService,
        position_service: PositionService,
        account_service: AccountService,
        exposure_analyzer: PortfolioExposureAnalyzer,
        allocation_analyzer: PortfolioAllocationAnalyzer,
        report_composer: PortfolioReportComposer,
    ) -> None:
        self.repository = repository
        self.constitution_service = constitution_service
        self.universe_service = universe_service
        self.watchtower_service = watchtower_service
        self.auto_decision_service = auto_decision_service
        self.position_service = position_service
        self.account_service = account_service
        self.exposure_analyzer = exposure_analyzer
        self.allocation_analyzer = allocation_analyzer
        self.report_composer = report_composer

    def generate_report(
        self,
        *,
        report_date: str | None = None,
        report_type: str = "manual",
        watchtower_run_id: str | None = None,
        auto_decision_run_id: str | None = None,
    ) -> PortfolioManagerReport:
        effective_date = report_date or datetime.now(timezone.utc).date().isoformat()
        limitations: list[str] = []
        constitution = self.constitution_service.get_current()
        positions, position_limitations = self._positions()
        limitations.extend(position_limitations)
        account, account_limitations = self._account()
        limitations.extend(account_limitations)
        universe_items = []
        for universe_type in ("holding", "watchlist", "candidate", "excluded"):
            universe_items.extend(self.universe_service.list_symbols(universe_type=universe_type, enabled=None))
        if not positions and not universe_items:
            limitations.append("positions_and_universe_unavailable")

        watchtower_run = self._watchtower_run(watchtower_run_id, limitations)
        auto_decision_run = self._auto_decision_run(auto_decision_run_id, limitations)
        total_equity = float(account.total_equity) if account and account.total_equity is not None else None
        cash_value = float(account.cash) if account and account.cash is not None else None
        exposure = self.exposure_analyzer.analyze(
            positions=positions,
            universe_items=universe_items,
            constitution=constitution,
            total_equity=total_equity,
        )
        allocation = self.allocation_analyzer.analyze(
            constitution=constitution,
            position_exposure_items=exposure.position_exposure_items,
            universe_items=universe_items,
            watchtower_run=watchtower_run,
            auto_decision_run=auto_decision_run,
            total_equity=total_equity,
            cash_value=cash_value,
            as_of_date=effective_date,
        )
        report_doc = self.report_composer.compose(
            report_id=self._new_report_id(effective_date, report_type),
            report_date=effective_date,
            report_type=report_type,
            constitution=constitution,
            exposure=exposure,
            allocation=allocation,
            source_watchtower_run_id=watchtower_run.id if watchtower_run else None,
            source_auto_decision_run_id=auto_decision_run.id if auto_decision_run else None,
            watchtower_decision_required_count=sum(1 for item in (watchtower_run.items if watchtower_run else []) if item.status == "decision_required"),
            auto_decision_failed_count=sum(1 for item in (auto_decision_run.items if auto_decision_run else []) if item.selection_status == "failed"),
            data_limitations=limitations,
        )
        if not positions and universe_items:
            report_doc["status"] = "partial_success"
        if not positions and not universe_items:
            report_doc["status"] = "failed"
        stored = self.repository.create_report(report_doc)
        return PortfolioManagerReport.model_validate(stored)

    def list_reports(self, *, limit: int = 20, report_date: str | None = None) -> list[PortfolioManagerReport]:
        return [PortfolioManagerReport.model_validate(item) for item in self.repository.list_reports(limit=limit, report_date=report_date)]

    def get_report(self, report_id: str) -> PortfolioManagerReport:
        report = self.repository.get_report(report_id)
        if report is None:
            raise PortfolioReviewError(f"Portfolio report not found: {report_id}")
        return PortfolioManagerReport.model_validate(report)

    def get_latest_report(self) -> PortfolioManagerReport:
        report = self.repository.get_latest_report()
        if report is None:
            raise PortfolioReviewError("Portfolio report not found")
        return PortfolioManagerReport.model_validate(report)

    def _positions(self):
        try:
            response = self.position_service.list_positions(
                report_date=None,
                symbol=None,
                asset_class=None,
                sort_by="position_value",
                sort_order="desc",
                page=1,
                page_size=1000,
                include_summary=False,
            )
            return list(response.items), []
        except Exception as exc:
            return [], [f"positions_unavailable:{type(exc).__name__}"]

    def _account(self):
        try:
            account = self.account_service.get_overview()
            return account, [] if account else ["account_overview_unavailable"]
        except Exception as exc:
            return None, [f"account_overview_unavailable:{type(exc).__name__}"]

    def _watchtower_run(self, watchtower_run_id: str | None, limitations: list[str]):
        try:
            if watchtower_run_id:
                return self.watchtower_service.get_run_detail(watchtower_run_id)
            latest = self.watchtower_service.repository.get_latest_run()
            if not latest:
                limitations.append("watchtower_run_missing")
                return None
            return self.watchtower_service.get_run_detail(latest["id"])
        except Exception as exc:
            limitations.append(f"watchtower_run_unavailable:{type(exc).__name__}")
            return None

    def _auto_decision_run(self, auto_decision_run_id: str | None, limitations: list[str]):
        try:
            if auto_decision_run_id:
                return self.auto_decision_service.get_run_detail(auto_decision_run_id)
            latest = self.auto_decision_service.repository.get_latest_run()
            if not latest:
                limitations.append("auto_decision_run_missing")
                return None
            return self.auto_decision_service.get_run_detail(latest["id"])
        except Exception as exc:
            limitations.append(f"auto_decision_run_unavailable:{type(exc).__name__}")
            return None

    @staticmethod
    def _new_report_id(report_date: str, report_type: str) -> str:
        return f"portfolio_report:{report_date}:{report_type}:{uuid4().hex[:12]}"
