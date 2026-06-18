from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domains.portfolio_manager.universe.schemas import AIThemeRole, UniversePriority, UniverseType
from app.domains.portfolio_manager.watchtower.schemas import (
    DecisionTypeHint,
    WatchtowerItemStatus,
    WatchtowerSeverity,
    WatchtowerTriggerReason,
)

AutoDecisionRunType = Literal["manual", "scheduled", "backfill"]
AutoDecisionRunStatus = Literal["success", "partial_success", "failed", "skipped"]
AutoDecisionSelectionStatus = Literal["selected", "skipped", "completed", "failed"]
AutoDecisionSkipReason = Literal[
    "not_decision_required",
    "not_decision_candidate",
    "missing_decision_type_hint",
    "universe_disabled",
    "excluded_universe",
    "scan_disabled",
    "decision_disabled",
    "weekly_llm_budget_zero",
    "ai_theme_not_allowed_for_auto_entry",
    "decision_type_not_allowed",
    "duplicate_recent_auto_decision",
    "budget_exceeded",
]


class PortfolioAutoDecisionBudget(BaseModel):
    max_decisions: int = 5
    used_decisions: int = 0
    skipped_by_budget: int = 0


class PortfolioAutoDecisionSummary(BaseModel):
    selected: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0


class PortfolioAutoDecisionRunCreate(BaseModel):
    watchtower_run_id: str
    run_date: str | None = None
    run_type: AutoDecisionRunType = "manual"
    max_decisions: int = Field(default=5, ge=0, le=50)
    force_refresh: bool = False
    dry_run: bool = False


class PortfolioAutoDecisionRun(BaseModel):
    id: str
    run_date: str
    run_type: AutoDecisionRunType
    source_watchtower_run_id: str
    status: AutoDecisionRunStatus
    constitution_version: str
    budget: PortfolioAutoDecisionBudget
    summary: PortfolioAutoDecisionSummary
    selected_symbols: list[str] = Field(default_factory=list)
    skipped_symbols: list[str] = Field(default_factory=list)
    data_limitations: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class PortfolioAutoDecisionItem(BaseModel):
    id: str
    run_id: str
    run_date: str
    source_watchtower_run_id: str
    source_watchtower_item_id: str
    symbol: str
    display_symbol: str
    universe_type: UniverseType
    ai_theme_role: AIThemeRole
    priority: UniversePriority
    watchtower_status: WatchtowerItemStatus
    watchtower_severity: WatchtowerSeverity
    trigger_reasons: list[WatchtowerTriggerReason] = Field(default_factory=list)
    selection_status: AutoDecisionSelectionStatus
    skip_reason: AutoDecisionSkipReason | None = None
    decision_type: DecisionTypeHint | None = None
    decision_request: dict = Field(default_factory=dict)
    decision_id: str | None = None
    decision_summary: dict = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    scan_snapshot: dict = Field(default_factory=dict)
    created_at: str
    updated_at: str


class PortfolioAutoDecisionRunDetail(PortfolioAutoDecisionRun):
    items: list[PortfolioAutoDecisionItem] = Field(default_factory=list)


class PortfolioAutoDecisionRunListResponse(BaseModel):
    items: list[PortfolioAutoDecisionRun]


class PortfolioAutoDecisionSymbolHistoryResponse(BaseModel):
    items: list[PortfolioAutoDecisionItem]


class AutoDecisionCandidate(BaseModel):
    source_watchtower_item_id: str
    source_watchtower_run_id: str
    run_date: str
    symbol: str
    display_symbol: str
    universe_type: UniverseType
    ai_theme_role: AIThemeRole
    priority: UniversePriority
    watchtower_status: WatchtowerItemStatus
    watchtower_severity: WatchtowerSeverity
    trigger_reasons: list[WatchtowerTriggerReason] = Field(default_factory=list)
    decision_type: DecisionTypeHint
    decision_request: dict = Field(default_factory=dict)
    scan_snapshot: dict = Field(default_factory=dict)
    selection_status: Literal["selected", "skipped"] = "selected"
    skip_reason: AutoDecisionSkipReason | None = None
    selection_reasons: list[str] = Field(default_factory=list)


class AutoDecisionSelectionResult(BaseModel):
    selected: list[AutoDecisionCandidate] = Field(default_factory=list)
    skipped: list[AutoDecisionCandidate] = Field(default_factory=list)
    budget: PortfolioAutoDecisionBudget


class AutoDecisionExecutionResult(BaseModel):
    ok: bool
    decision_id: str | None = None
    decision_summary: dict = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
