from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from uuid import uuid4

from app.domains.portfolio_manager.constitution.service import PortfolioConstitutionService
from app.domains.portfolio_manager.decision_orchestrator.repository import PortfolioAutoDecisionRepository
from app.domains.portfolio_manager.decision_orchestrator.runner import PortfolioAutoDecisionRunner
from app.domains.portfolio_manager.decision_orchestrator.schemas import (
    AutoDecisionCandidate,
    AutoDecisionSelectionResult,
    PortfolioAutoDecisionItem,
    PortfolioAutoDecisionRun,
    PortfolioAutoDecisionRunDetail,
    PortfolioAutoDecisionSummary,
)
from app.domains.portfolio_manager.decision_orchestrator.trigger_selector import PortfolioAutoDecisionTriggerSelector
from app.domains.portfolio_manager.universe.repository import normalize_universe_symbol
from app.domains.portfolio_manager.universe.service import PortfolioUniverseService
from app.domains.portfolio_manager.watchtower.repository import utc_now_iso
from app.domains.portfolio_manager.watchtower.service import PortfolioWatchtowerService


class PortfolioAutoDecisionError(ValueError):
    """Raised when an auto decision orchestration request cannot be fulfilled."""


class PortfolioAutoDecisionService:
    def __init__(
        self,
        *,
        repository: PortfolioAutoDecisionRepository,
        watchtower_service: PortfolioWatchtowerService,
        constitution_service: PortfolioConstitutionService,
        universe_service: PortfolioUniverseService,
        trigger_selector: PortfolioAutoDecisionTriggerSelector,
        runner: PortfolioAutoDecisionRunner,
    ) -> None:
        self.repository = repository
        self.watchtower_service = watchtower_service
        self.constitution_service = constitution_service
        self.universe_service = universe_service
        self.trigger_selector = trigger_selector
        self.runner = runner

    def run_auto_decisions(
        self,
        *,
        watchtower_run_id: str,
        run_date: str | None = None,
        run_type: str = "manual",
        max_decisions: int = 5,
        force_refresh: bool = False,
        dry_run: bool = False,
    ) -> PortfolioAutoDecisionRunDetail:
        if not watchtower_run_id:
            raise PortfolioAutoDecisionError("watchtower_run_id is required")
        constitution = self.constitution_service.get_current()
        watchtower_run = self.watchtower_service.get_run_detail(watchtower_run_id)
        effective_run_date = run_date or watchtower_run.run_date or datetime.now(timezone.utc).date().isoformat()
        universe_items = []
        for universe_type in ("holding", "watchlist", "candidate", "excluded"):
            universe_items.extend(self.universe_service.list_symbols(universe_type=universe_type, enabled=None))

        selection = self.trigger_selector.select(
            watchtower_run=watchtower_run,
            universe_items=universe_items,
            constitution=constitution,
            recent_decision_lookup=self.repository,
            max_decisions=max_decisions,
            force_refresh=force_refresh,
        )
        run_id = self._new_run_id(effective_run_date, run_type)
        initial_items = [
            self._item_document(run_id=run_id, run_date=effective_run_date, candidate=candidate)
            for candidate in [*selection.selected, *selection.skipped]
        ]
        stored_items = self.repository.bulk_create_items(initial_items)
        selected_symbols = [candidate.symbol for candidate in selection.selected]
        skipped_symbols = [candidate.symbol for candidate in selection.skipped]
        run_doc = {
            "id": run_id,
            "run_date": effective_run_date,
            "run_type": run_type,
            "source_watchtower_run_id": watchtower_run_id,
            "status": "skipped",
            "constitution_version": constitution.constitution_version,
            "budget": selection.budget.model_dump(),
            "summary": _summary(stored_items),
            "selected_symbols": selected_symbols,
            "skipped_symbols": skipped_symbols,
            "data_limitations": list(watchtower_run.data_limitations or []),
        }
        stored_run = self.repository.create_run(run_doc)

        if dry_run:
            stored_run = self.repository.update_run(
                run_id,
                {"status": _run_status(stored_items, dry_run=True), "summary": _summary(stored_items)},
            ) or stored_run
            return PortfolioAutoDecisionRunDetail.model_validate({**stored_run, "items": self.repository.list_items(run_id)})

        for candidate in selection.selected:
            item_id = self._item_id(run_id, candidate.symbol)
            result = self.runner.run_trade_decision_for_item(candidate)
            patch = (
                {
                    "selection_status": "completed",
                    "decision_id": result.decision_id,
                    "decision_summary": result.decision_summary,
                    "error_code": None,
                    "error_message": None,
                }
                if result.ok
                else {
                    "selection_status": "failed",
                    "error_code": result.error_code,
                    "error_message": result.error_message,
                }
            )
            self.repository.update_item(item_id, patch)

        final_items = self.repository.list_items(run_id)
        stored_run = self.repository.update_run(
            run_id,
            {
                "status": _run_status(final_items, dry_run=False),
                "summary": _summary(final_items),
                "budget": {**selection.budget.model_dump(), "used_decisions": _count_status(final_items, "completed")},
            },
        ) or stored_run
        return PortfolioAutoDecisionRunDetail.model_validate({**stored_run, "items": final_items})

    def list_runs(self, *, limit: int = 20, run_date: str | None = None) -> list[PortfolioAutoDecisionRun]:
        return [PortfolioAutoDecisionRun.model_validate(item) for item in self.repository.list_runs(limit=limit, run_date=run_date)]

    def get_run_detail(self, run_id: str) -> PortfolioAutoDecisionRunDetail:
        run = self.repository.get_run(run_id)
        if run is None:
            raise PortfolioAutoDecisionError(f"Auto decision run not found: {run_id}")
        return PortfolioAutoDecisionRunDetail.model_validate({**run, "items": self.repository.list_items(run_id)})

    def list_symbol_history(self, symbol: str, *, limit: int = 30) -> list[PortfolioAutoDecisionItem]:
        normalized = normalize_universe_symbol(symbol)
        if not normalized:
            raise PortfolioAutoDecisionError("symbol is required")
        return [PortfolioAutoDecisionItem.model_validate(item) for item in self.repository.list_symbol_history(normalized, limit=limit)]

    def _item_document(self, *, run_id: str, run_date: str, candidate: AutoDecisionCandidate) -> dict:
        now = utc_now_iso()
        return {
            "id": self._item_id(run_id, candidate.symbol),
            "run_id": run_id,
            "run_date": run_date,
            "source_watchtower_run_id": candidate.source_watchtower_run_id,
            "source_watchtower_item_id": candidate.source_watchtower_item_id,
            "symbol": candidate.symbol,
            "display_symbol": candidate.display_symbol,
            "universe_type": candidate.universe_type,
            "ai_theme_role": candidate.ai_theme_role,
            "priority": candidate.priority,
            "watchtower_status": candidate.watchtower_status,
            "watchtower_severity": candidate.watchtower_severity,
            "trigger_reasons": [reason.model_dump() for reason in candidate.trigger_reasons],
            "selection_status": candidate.selection_status,
            "skip_reason": candidate.skip_reason,
            "decision_type": candidate.decision_type,
            "decision_request": candidate.decision_request,
            "decision_id": None,
            "decision_summary": {},
            "error_code": None,
            "error_message": None,
            "scan_snapshot": candidate.scan_snapshot,
            "created_at": now,
            "updated_at": now,
        }

    @staticmethod
    def _new_run_id(run_date: str, run_type: str) -> str:
        return f"auto_decision_run:{run_date}:{run_type}:{uuid4().hex[:12]}"

    @staticmethod
    def _item_id(run_id: str, symbol: str) -> str:
        return f"auto_decision_item:{run_id}:{symbol}"


def _summary(items: list[dict]) -> dict:
    counts = Counter(str(item.get("selection_status") or "skipped") for item in items)
    return PortfolioAutoDecisionSummary(
        selected=counts.get("selected", 0),
        completed=counts.get("completed", 0),
        failed=counts.get("failed", 0),
        skipped=counts.get("skipped", 0),
    ).model_dump()


def _count_status(items: list[dict], status: str) -> int:
    return sum(1 for item in items if item.get("selection_status") == status)


def _run_status(items: list[dict], *, dry_run: bool) -> str:
    if not items:
        return "skipped"
    selected = _count_status(items, "selected")
    completed = _count_status(items, "completed")
    failed = _count_status(items, "failed")
    skipped = _count_status(items, "skipped")
    if dry_run:
        return "success" if selected else "skipped"
    if completed and failed:
        return "partial_success"
    if completed and skipped:
        return "partial_success"
    if completed:
        return "success"
    if failed:
        return "failed"
    if selected:
        return "success"
    return "skipped"
