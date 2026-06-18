from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from uuid import uuid4

from app.domains.portfolio_manager.constitution.service import PortfolioConstitutionService
from app.domains.portfolio_manager.universe.repository import normalize_universe_symbol
from app.domains.portfolio_manager.universe.schemas import UniverseSymbol, UniverseType
from app.domains.portfolio_manager.universe.service import PortfolioUniverseService
from app.domains.portfolio_manager.watchtower.repository import PortfolioWatchtowerRepository, utc_now_iso
from app.domains.portfolio_manager.watchtower.scanner import PortfolioWatchtowerScanner, WatchtowerScanResult
from app.domains.portfolio_manager.watchtower.schemas import (
    PortfolioWatchtowerItem,
    PortfolioWatchtowerRun,
    PortfolioWatchtowerRunDetail,
    WatchtowerItemStatus,
    WatchtowerSeverity,
)
from app.domains.portfolio_manager.watchtower.trigger_rules import SEVERITY_RANK, STATUS_RANK, evaluate_watchtower_triggers
from app.schemas.positions import PositionItem
from app.services.position_service import PositionService

DEFAULT_WATCHTOWER_UNIVERSE_TYPES: list[UniverseType] = ["holding", "watchlist", "candidate"]
WATCHTOWER_SUMMARY_KEYS: list[WatchtowerItemStatus] = ["normal", "watch", "attention_required", "decision_required"]


class PortfolioWatchtowerError(ValueError):
    """Raised when a Portfolio Watchtower request cannot be fulfilled."""


class PortfolioWatchtowerService:
    def __init__(
        self,
        *,
        repository: PortfolioWatchtowerRepository,
        universe_service: PortfolioUniverseService,
        constitution_service: PortfolioConstitutionService,
        position_service: PositionService,
        scanner: PortfolioWatchtowerScanner,
    ) -> None:
        self.repository = repository
        self.universe_service = universe_service
        self.constitution_service = constitution_service
        self.position_service = position_service
        self.scanner = scanner

    def run_watchtower(
        self,
        *,
        run_date: str | None = None,
        run_type: str = "manual",
        universe_types: list[str] | None = None,
        force_refresh: bool = False,
    ) -> PortfolioWatchtowerRunDetail:
        del force_refresh
        effective_run_date = run_date or datetime.now(timezone.utc).date().isoformat()
        selected_types = [item for item in (universe_types or DEFAULT_WATCHTOWER_UNIVERSE_TYPES) if item != "excluded"]
        constitution = self.constitution_service.get_current()
        universe_items = self._enabled_universe_items(selected_types)
        positions, position_limitations = self._current_positions()
        positions_by_symbol = _positions_by_symbol(positions)
        position_value_total = sum(float(item.position_value or 0.0) for item in positions if item.position_value is not None) or None

        item_documents: list[dict] = []
        run_limitations: list[str] = list(position_limitations)
        for item in universe_items:
            position = positions_by_symbol.get(item.symbol)
            price_bars, price_limitations = self.scanner.fetch_price_bars(item, run_date=effective_run_date)
            scan = self.scanner.scan(
                universe_item=item,
                position=position,
                price_bars=price_bars,
                constitution=constitution.model_dump(),
                total_equity=None,
                position_value_denominator=position_value_total,
                price_limitations=price_limitations,
            )
            if scan.data_limitations:
                run_limitations.extend([f"{item.symbol}:{value}" for value in scan.data_limitations])
            item_documents.append(
                self._build_item_document(
                    run_id=self._placeholder_run_id(effective_run_date, run_type),
                    run_date=effective_run_date,
                    item=item,
                    scan=scan,
                )
            )

        run_id = self._new_run_id(effective_run_date, run_type)
        for item_doc in item_documents:
            item_doc["run_id"] = run_id
            item_doc["id"] = self._item_id(run_id, item_doc["symbol"])

        summary = _summary(item_documents)
        status = _run_status(item_documents, run_limitations)
        run_doc = {
            "id": run_id,
            "run_date": effective_run_date,
            "run_type": run_type,
            "status": status,
            "constitution_version": constitution.constitution_version,
            "universe_snapshot": _universe_snapshot(universe_items),
            "summary": summary,
            "top_attention_symbols": _top_attention_symbols(item_documents),
            "data_limitations": _dedupe(run_limitations)[:200],
        }
        stored_run = self.repository.create_run(run_doc)
        stored_items = self.repository.bulk_create_items(item_documents)
        return PortfolioWatchtowerRunDetail.model_validate({**stored_run, "items": stored_items})

    def list_runs(self, *, limit: int = 20, run_date: str | None = None) -> list[PortfolioWatchtowerRun]:
        return [PortfolioWatchtowerRun.model_validate(item) for item in self.repository.list_runs(limit=limit, run_date=run_date)]

    def get_run_detail(self, run_id: str) -> PortfolioWatchtowerRunDetail:
        run = self.repository.get_run(run_id)
        if run is None:
            raise PortfolioWatchtowerError(f"Watchtower run not found: {run_id}")
        items = self.repository.list_items(run_id)
        return PortfolioWatchtowerRunDetail.model_validate({**run, "items": items})

    def list_symbol_history(self, symbol: str, *, limit: int = 30) -> list[PortfolioWatchtowerItem]:
        normalized = normalize_universe_symbol(symbol)
        if not normalized:
            raise PortfolioWatchtowerError("symbol is required")
        return [PortfolioWatchtowerItem.model_validate(item) for item in self.repository.list_symbol_history(normalized, limit=limit)]

    def _enabled_universe_items(self, universe_types: list[str]) -> list[UniverseSymbol]:
        items: list[UniverseSymbol] = []
        for universe_type in universe_types:
            items.extend(self.universe_service.list_symbols(universe_type=universe_type, enabled=True))
        deduped: dict[str, UniverseSymbol] = {}
        for item in items:
            if item.universe_type == "excluded" or not item.enabled:
                continue
            deduped[item.symbol] = item
        return sorted(deduped.values(), key=lambda item: (item.universe_type, item.symbol))

    def _current_positions(self) -> tuple[list[PositionItem], list[str]]:
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

    def _build_item_document(
        self,
        *,
        run_id: str,
        run_date: str,
        item: UniverseSymbol,
        scan: WatchtowerScanResult,
    ) -> dict:
        status, severity, reasons, next_step, decision_candidate, decision_type_hint = evaluate_watchtower_triggers(
            universe_item=item,
            metrics=scan.metrics,
        )
        now = utc_now_iso()
        return {
            "id": self._item_id(run_id, item.symbol),
            "run_id": run_id,
            "run_date": run_date,
            "symbol": item.symbol,
            "display_symbol": item.display_symbol or item.symbol,
            "name": item.name,
            "universe_type": item.universe_type,
            "priority": item.priority,
            "enabled": item.enabled,
            "ai_theme_role": item.ai_theme_role,
            "theme_tags": list(item.theme_tags),
            "status": status,
            "severity": severity,
            "trigger_reasons": [reason.model_dump() for reason in reasons],
            "metrics": scan.metrics.model_dump(),
            "suggested_next_step": next_step,
            "decision_candidate": decision_candidate,
            "decision_type_hint": decision_type_hint,
            "scan_snapshot": scan.scan_snapshot,
            "data_limitations": scan.data_limitations,
            "created_at": now,
            "updated_at": now,
        }

    @staticmethod
    def _new_run_id(run_date: str, run_type: str) -> str:
        return f"watchtower_run:{run_date}:{run_type}:{uuid4().hex[:12]}"

    @staticmethod
    def _placeholder_run_id(run_date: str, run_type: str) -> str:
        return f"watchtower_run:{run_date}:{run_type}:pending"

    @staticmethod
    def _item_id(run_id: str, symbol: str) -> str:
        return f"watchtower_item:{run_id}:{symbol}"


def _positions_by_symbol(positions: list[PositionItem]) -> dict[str, PositionItem]:
    result: dict[str, PositionItem] = {}
    for position in positions:
        normalized = normalize_universe_symbol(position.symbol)
        if normalized:
            result[normalized] = position
    return result


def _universe_snapshot(items: list[UniverseSymbol]) -> dict:
    counts = Counter(item.universe_type for item in items)
    return {
        "total": len(items),
        "holding": counts.get("holding", 0),
        "watchlist": counts.get("watchlist", 0),
        "candidate": counts.get("candidate", 0),
        "excluded": counts.get("excluded", 0),
        "enabled": sum(1 for item in items if item.enabled),
    }


def _summary(items: list[dict]) -> dict[str, int]:
    counts = Counter(str(item.get("status") or "normal") for item in items)
    return {key: counts.get(key, 0) for key in WATCHTOWER_SUMMARY_KEYS}


def _run_status(items: list[dict], limitations: list[str]) -> str:
    if not items:
        return "failed"
    missing_count = sum(1 for item in items if item.get("data_limitations"))
    if limitations or missing_count:
        return "partial_success"
    return "success"


def _top_attention_symbols(items: list[dict], limit: int = 10) -> list[str]:
    ranked = sorted(
        [item for item in items if STATUS_RANK.get(item.get("status"), 0) > 0],
        key=lambda item: (
            STATUS_RANK.get(item.get("status"), 0),
            SEVERITY_RANK.get(item.get("severity"), 0),
            1 if item.get("priority") == "high" else 0,
            item.get("symbol") or "",
        ),
        reverse=True,
    )
    return [str(item.get("symbol")) for item in ranked[:limit] if item.get("symbol")]


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result

