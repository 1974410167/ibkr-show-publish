from __future__ import annotations

from app.domains.portfolio_manager.universe.repository import normalize_universe_symbol
from app.domains.portfolio_manager.universe.schemas import UniverseSymbolUpsert


def build_holding_sync_document(position: object, existing: dict | None = None) -> UniverseSymbolUpsert | None:
    symbol = normalize_universe_symbol(getattr(position, "symbol", None))
    if not symbol:
        return None
    quantity = getattr(position, "quantity", None)
    if quantity is not None and float(quantity) == 0:
        return None
    existing = existing or {}
    existing_tags = existing.get("theme_tags") or []
    existing_role = existing.get("ai_theme_role") or "unknown"
    return UniverseSymbolUpsert(
        symbol=symbol,
        display_symbol=existing.get("display_symbol") or getattr(position, "symbol", None) or symbol,
        name=existing.get("name") or getattr(position, "description", None) or "",
        universe_type="holding",
        theme_tags=existing_tags if existing_tags else ["AI"],
        ai_theme_role=existing_role if existing_role != "unknown" else "unknown",
        priority=existing.get("priority") or "high",
        enabled=True,
        scan_frequency=existing.get("scan_frequency") or "daily",
        decision_frequency=existing.get("decision_frequency") or "event_driven",
        max_llm_runs_per_week=existing.get("max_llm_runs_per_week") if existing.get("max_llm_runs_per_week") is not None else 3,
        source="ibkr_holding_sync",
        notes=existing.get("notes") or "",
        excluded_reason=existing.get("excluded_reason"),
    )

