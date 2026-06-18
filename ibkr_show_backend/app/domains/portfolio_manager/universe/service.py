from __future__ import annotations

from app.domains.portfolio_manager.universe.repository import PortfolioUniverseRepository, normalize_universe_symbol
from app.domains.portfolio_manager.universe.schemas import (
    UniverseSymbol,
    UniverseSymbolExcludeRequest,
    UniverseSymbolUpsert,
)
from app.domains.portfolio_manager.universe.sync_holdings import build_holding_sync_document
from app.services.position_service import PositionService


class PortfolioUniverseError(ValueError):
    """Raised when a portfolio universe request cannot be fulfilled."""


class PortfolioUniverseService:
    def __init__(self, repository: PortfolioUniverseRepository, position_service: PositionService | None = None) -> None:
        self.repository = repository
        self.position_service = position_service

    def list_symbols(
        self,
        *,
        universe_type: str | None = None,
        enabled: bool | None = None,
        priority: str | None = None,
        ai_theme_role: str | None = None,
        theme_tag: str | None = None,
        source: str | None = None,
    ) -> list[UniverseSymbol]:
        return [
            UniverseSymbol.model_validate(item)
            for item in self.repository.list_symbols(
                universe_type=universe_type,
                enabled=enabled,
                priority=priority,
                ai_theme_role=ai_theme_role,
                theme_tag=theme_tag,
                source=source,
            )
        ]

    def get_symbol(self, symbol: str) -> UniverseSymbol:
        normalized = self._normalize_required(symbol)
        stored = self.repository.get_symbol(normalized)
        if stored is None:
            raise PortfolioUniverseError(f"Universe symbol not found: {normalized}")
        return UniverseSymbol.model_validate(stored)

    def upsert_symbol(self, symbol: str, payload: UniverseSymbolUpsert) -> UniverseSymbol:
        normalized = self._normalize_required(symbol)
        data = payload.model_dump()
        data["symbol"] = normalized
        if not data.get("display_symbol"):
            data["display_symbol"] = payload.display_symbol or symbol.strip().upper()
        stored = self.repository.upsert_symbol(data)
        return UniverseSymbol.model_validate(stored)

    def add_to_watchlist(self, symbol: str, payload: UniverseSymbolUpsert) -> UniverseSymbol:
        data = payload.model_dump()
        data["universe_type"] = "watchlist"
        data["source"] = data.get("source") or "manual"
        return self.upsert_symbol(symbol, UniverseSymbolUpsert.model_validate(data))

    def mark_excluded(self, symbol: str, payload: UniverseSymbolExcludeRequest) -> UniverseSymbol:
        normalized = self._normalize_required(symbol)
        existing = self.repository.get_symbol(normalized) or {}
        document = {
            **existing,
            "symbol": normalized,
            "display_symbol": existing.get("display_symbol") or symbol.strip().upper(),
            "name": existing.get("name") or "",
            "universe_type": "excluded",
            "theme_tags": existing.get("theme_tags") or [],
            "ai_theme_role": existing.get("ai_theme_role") or "unknown",
            "priority": existing.get("priority") or "low",
            "enabled": False,
            "scan_frequency": "disabled",
            "decision_frequency": "disabled",
            "max_llm_runs_per_week": existing.get("max_llm_runs_per_week") or 0,
            "source": existing.get("source") or "manual",
            "notes": payload.notes if payload.notes is not None else existing.get("notes", ""),
            "excluded_reason": payload.excluded_reason,
        }
        stored = self.repository.upsert_symbol(document)
        return UniverseSymbol.model_validate(stored)

    def disable_symbol(self, symbol: str) -> UniverseSymbol:
        normalized = self._normalize_required(symbol)
        stored = self.repository.disable_symbol(normalized)
        if stored is None:
            raise PortfolioUniverseError(f"Universe symbol not found: {normalized}")
        return UniverseSymbol.model_validate(stored)

    def sync_holdings_from_positions(self) -> tuple[list[UniverseSymbol], list[str]]:
        if self.position_service is None:
            raise PortfolioUniverseError("Position service is not configured")
        positions = self.position_service.list_positions(
            report_date=None,
            symbol=None,
            asset_class=None,
            sort_by="position_value",
            sort_order="desc",
            page=1,
            page_size=1000,
            include_summary=False,
        )
        documents: list[dict] = []
        skipped: list[str] = []
        for position in positions.items:
            normalized = normalize_universe_symbol(position.symbol)
            if not normalized:
                skipped.append(str(position.symbol or ""))
                continue
            existing = self.repository.get_symbol(normalized)
            payload = build_holding_sync_document(position, existing)
            if payload is None:
                skipped.append(normalized)
                continue
            documents.append(payload.model_dump())
        synced = [UniverseSymbol.model_validate(item) for item in self.repository.bulk_upsert(documents)]
        return synced, skipped

    @staticmethod
    def _normalize_required(symbol: str) -> str:
        normalized = normalize_universe_symbol(symbol)
        if not normalized:
            raise PortfolioUniverseError("symbol is required")
        return normalized

