from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

UniverseType = Literal["holding", "watchlist", "candidate", "excluded"]
AIThemeRole = Literal[
    "core_compute",
    "semiconductor",
    "data_center",
    "cloud_platform",
    "ai_infrastructure",
    "ai_application",
    "power_and_cooling",
    "memory_and_networking",
    "indirect_beneficiary",
    "non_ai",
    "fake_ai_story",
    "unknown",
]
UniversePriority = Literal["high", "medium", "low"]
ScanFrequency = Literal["daily", "weekly", "monthly", "disabled"]
DecisionFrequency = Literal["event_driven", "daily_if_triggered", "weekly", "monthly", "manual_only", "disabled"]
UniverseSource = Literal["manual", "ibkr_holding_sync", "system_candidate"]


class UniverseSymbolBase(BaseModel):
    symbol: str
    display_symbol: str | None = None
    name: str = ""
    universe_type: UniverseType = "watchlist"
    theme_tags: list[str] = Field(default_factory=list)
    ai_theme_role: AIThemeRole = "unknown"
    priority: UniversePriority = "medium"
    enabled: bool = True
    scan_frequency: ScanFrequency = "weekly"
    decision_frequency: DecisionFrequency = "event_driven"
    max_llm_runs_per_week: int = Field(default=3, ge=0)
    source: UniverseSource = "manual"
    notes: str = ""
    excluded_reason: str | None = None


class UniverseSymbolUpsert(UniverseSymbolBase):
    pass


class UniverseSymbolExcludeRequest(BaseModel):
    excluded_reason: str | None = None
    notes: str | None = None


class UniverseSymbol(UniverseSymbolBase):
    id: str
    created_at: str
    updated_at: str


class UniverseSymbolListResponse(BaseModel):
    items: list[UniverseSymbol]


class UniverseSyncHoldingsResponse(BaseModel):
    synced: list[UniverseSymbol]
    skipped: list[str] = Field(default_factory=list)
    message: str

