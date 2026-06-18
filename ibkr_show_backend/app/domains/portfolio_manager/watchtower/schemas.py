from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domains.portfolio_manager.universe.schemas import AIThemeRole, UniversePriority, UniverseType

WatchtowerRunType = Literal["manual", "scheduled", "backfill"]
WatchtowerRunStatus = Literal["success", "partial_success", "failed"]
WatchtowerItemStatus = Literal["normal", "watch", "attention_required", "decision_required"]
WatchtowerSeverity = Literal["none", "low", "medium", "high"]
WatchtowerNextStep = Literal["no_action", "keep_watch", "review_manually", "trigger_trade_decision"]
DecisionTypeHint = Literal["holding_decision", "entry_decision"]


class WatchtowerTriggerReason(BaseModel):
    code: str
    severity: WatchtowerSeverity
    message: str
    value: float | int | str | None = None
    threshold: float | int | str | None = None
    status: WatchtowerItemStatus | None = None
    decision_type_hint: DecisionTypeHint | None = None


class WatchtowerMetrics(BaseModel):
    last_price: float | None = None
    return_1d: float | None = None
    return_5d: float | None = None
    return_20d: float | None = None
    consecutive_up_days: int = 0
    consecutive_down_days: int = 0
    drawdown_from_20d_high: float | None = None
    drawdown_from_60d_high: float | None = None
    distance_to_52w_high: float | None = None
    distance_to_52w_low: float | None = None
    position_quantity: float | None = None
    position_value: float | None = None
    position_weight: float | None = None
    unrealized_pnl_pct: float | None = None
    data_points: int = 0


class PortfolioWatchtowerRunCreate(BaseModel):
    run_date: str | None = None
    run_type: WatchtowerRunType = "manual"
    universe_types: list[UniverseType] | None = None
    force_refresh: bool = False


class PortfolioWatchtowerItem(BaseModel):
    id: str
    run_id: str
    run_date: str
    symbol: str
    display_symbol: str
    name: str = ""
    universe_type: UniverseType
    priority: UniversePriority
    enabled: bool
    ai_theme_role: AIThemeRole
    theme_tags: list[str] = Field(default_factory=list)
    status: WatchtowerItemStatus
    severity: WatchtowerSeverity
    trigger_reasons: list[WatchtowerTriggerReason] = Field(default_factory=list)
    metrics: WatchtowerMetrics
    suggested_next_step: WatchtowerNextStep
    decision_candidate: bool = False
    decision_type_hint: DecisionTypeHint | None = None
    scan_snapshot: dict = Field(default_factory=dict)
    data_limitations: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class PortfolioWatchtowerRun(BaseModel):
    id: str
    run_date: str
    run_type: WatchtowerRunType
    status: WatchtowerRunStatus
    constitution_version: str
    universe_snapshot: dict = Field(default_factory=dict)
    summary: dict[str, int] = Field(default_factory=dict)
    top_attention_symbols: list[str] = Field(default_factory=list)
    data_limitations: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class PortfolioWatchtowerRunDetail(PortfolioWatchtowerRun):
    items: list[PortfolioWatchtowerItem] = Field(default_factory=list)


class PortfolioWatchtowerRunListResponse(BaseModel):
    items: list[PortfolioWatchtowerRun]


class PortfolioWatchtowerSymbolHistoryResponse(BaseModel):
    items: list[PortfolioWatchtowerItem]

