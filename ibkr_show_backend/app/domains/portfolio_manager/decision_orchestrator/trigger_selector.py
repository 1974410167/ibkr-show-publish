from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol

from app.domains.portfolio_manager.decision_orchestrator.schemas import (
    AutoDecisionCandidate,
    AutoDecisionSelectionResult,
    PortfolioAutoDecisionBudget,
)
from app.domains.portfolio_manager.universe.repository import normalize_universe_symbol
from app.domains.portfolio_manager.universe.schemas import UniverseSymbol
from app.domains.portfolio_manager.watchtower.schemas import PortfolioWatchtowerItem, PortfolioWatchtowerRunDetail

PRIORITY_RANK = {"high": 3, "medium": 2, "low": 1}
SEVERITY_RANK = {"high": 4, "medium": 3, "low": 2, "none": 1}
ENTRY_BLOCKED_AI_ROLES = {"fake_ai_story", "non_ai"}
RECENT_DUPLICATE_WINDOW_HOURS = 24


class RecentDecisionLookup(Protocol):
    def find_recent_completed(self, symbol: str, since_datetime: datetime) -> dict | None:
        ...


class PortfolioAutoDecisionTriggerSelector:
    def select(
        self,
        *,
        watchtower_run: PortfolioWatchtowerRunDetail,
        universe_items: list[UniverseSymbol],
        constitution: object,
        recent_decision_lookup: RecentDecisionLookup | None = None,
        max_decisions: int = 5,
        allowed_universe_types: list[str] | None = None,
        force_refresh: bool = False,
        now: datetime | None = None,
    ) -> AutoDecisionSelectionResult:
        del constitution
        allowed_types = set(allowed_universe_types or ["holding", "watchlist", "candidate"])
        universe_by_symbol = {normalize_universe_symbol(item.symbol): item for item in universe_items}
        current_time = now or datetime.now(timezone.utc)
        duplicate_since = current_time - timedelta(hours=RECENT_DUPLICATE_WINDOW_HOURS)

        prelim_selected: list[AutoDecisionCandidate] = []
        skipped: list[AutoDecisionCandidate] = []
        for item in watchtower_run.items:
            universe_item = universe_by_symbol.get(normalize_universe_symbol(item.symbol))
            candidate = self._candidate_from_item(item)
            skip_reason = self._skip_reason(
                item=item,
                universe_item=universe_item,
                allowed_universe_types=allowed_types,
                recent_decision_lookup=recent_decision_lookup,
                duplicate_since=duplicate_since,
                force_refresh=force_refresh,
            )
            if skip_reason:
                skipped.append(candidate.model_copy(update={"selection_status": "skipped", "skip_reason": skip_reason}))
                continue
            prelim_selected.append(candidate)

        ranked = sorted(prelim_selected, key=_candidate_rank)
        selected = ranked[: max(0, max_decisions)]
        budget_skipped = ranked[max(0, max_decisions) :]
        skipped.extend(
            candidate.model_copy(update={"selection_status": "skipped", "skip_reason": "budget_exceeded"})
            for candidate in budget_skipped
        )
        return AutoDecisionSelectionResult(
            selected=selected,
            skipped=skipped,
            budget=PortfolioAutoDecisionBudget(
                max_decisions=max_decisions,
                used_decisions=len(selected),
                skipped_by_budget=len(budget_skipped),
            ),
        )

    def _skip_reason(
        self,
        *,
        item: PortfolioWatchtowerItem,
        universe_item: UniverseSymbol | None,
        allowed_universe_types: set[str],
        recent_decision_lookup: RecentDecisionLookup | None,
        duplicate_since: datetime,
        force_refresh: bool,
    ) -> str | None:
        if item.status != "decision_required":
            return "not_decision_required"
        if not item.decision_candidate:
            return "not_decision_candidate"
        if not item.decision_type_hint:
            return "missing_decision_type_hint"
        if universe_item is not None:
            if not universe_item.enabled:
                return "universe_disabled"
            if universe_item.universe_type == "excluded":
                return "excluded_universe"
            if universe_item.scan_frequency == "disabled":
                return "scan_disabled"
            if universe_item.decision_frequency == "disabled":
                return "decision_disabled"
            if universe_item.max_llm_runs_per_week <= 0:
                return "weekly_llm_budget_zero"
        if item.universe_type == "excluded":
            return "excluded_universe"
        if item.universe_type not in allowed_universe_types:
            return "decision_type_not_allowed"
        if item.universe_type == "holding" and item.decision_type_hint != "holding_decision":
            return "decision_type_not_allowed"
        if item.universe_type in {"watchlist", "candidate"}:
            if item.decision_type_hint != "entry_decision":
                return "decision_type_not_allowed"
            if item.ai_theme_role in ENTRY_BLOCKED_AI_ROLES:
                return "ai_theme_not_allowed_for_auto_entry"
        if not force_refresh and recent_decision_lookup is not None:
            recent = recent_decision_lookup.find_recent_completed(item.symbol, duplicate_since)
            if recent is not None:
                return "duplicate_recent_auto_decision"
        return None

    def _candidate_from_item(self, item: PortfolioWatchtowerItem) -> AutoDecisionCandidate:
        decision_type = item.decision_type_hint or ("holding_decision" if item.universe_type == "holding" else "entry_decision")
        reason_codes = [reason.code for reason in item.trigger_reasons]
        selection_reasons = ["watchtower_decision_required"]
        if item.universe_type == "holding" and item.ai_theme_role == "fake_ai_story":
            selection_reasons.append("high_caution_fake_ai_story_holding")
        return AutoDecisionCandidate(
            source_watchtower_item_id=item.id,
            source_watchtower_run_id=item.run_id,
            run_date=item.run_date,
            symbol=item.symbol,
            display_symbol=item.display_symbol,
            universe_type=item.universe_type,
            ai_theme_role=item.ai_theme_role,
            priority=item.priority,
            watchtower_status=item.status,
            watchtower_severity=item.severity,
            trigger_reasons=item.trigger_reasons,
            decision_type=decision_type,
            decision_request={
                "symbol": item.symbol,
                "decision_type": decision_type,
                "source": "portfolio_watchtower",
                "source_run_id": item.run_id,
                "source_watchtower_item_id": item.id,
                "trigger_reason_codes": reason_codes,
            },
            scan_snapshot=item.scan_snapshot,
            selection_reasons=selection_reasons,
        )


def _candidate_rank(candidate: AutoDecisionCandidate) -> tuple[int, int, int, int, int, str]:
    return (
        -SEVERITY_RANK.get(candidate.watchtower_severity, 0),
        -1 if candidate.watchtower_status == "decision_required" else 0,
        -PRIORITY_RANK.get(candidate.priority, 0),
        -1 if candidate.universe_type == "holding" else 0,
        -len(candidate.trigger_reasons),
        candidate.symbol,
    )
