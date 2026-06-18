from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domains.portfolio_manager.universe.schemas import AIThemeRole, UniversePriority, UniverseType

PortfolioReportType = Literal["manual", "scheduled", "backfill"]
PortfolioReportStatus = Literal["success", "partial_success", "failed"]
PortfolioHealthLevel = Literal["healthy", "watch", "attention_required", "high_risk"]
GoalPathStatus = Literal["on_track", "stretched", "off_track", "unknown"]
AIThemeAssessment = Literal["aligned", "partially_aligned", "misaligned", "unknown"]
ConcentrationAssessment = Literal["low", "medium", "high"]
CashAssessment = Literal["too_low", "reasonable", "too_high", "unknown"]
AllocationGapType = Literal["underweight", "overweight", "near_target", "unknown"]
ActionQueueType = Literal["review_trade_decision", "monitor", "wait", "manual_review", "no_action"]


class PortfolioManagerReportGenerateRequest(BaseModel):
    report_date: str | None = None
    report_type: PortfolioReportType = "manual"
    watchtower_run_id: str | None = None
    auto_decision_run_id: str | None = None


class PortfolioGoalTracking(BaseModel):
    target_account_value_usd: float
    target_date: str
    current_total_equity_usd: float | None = None
    remaining_years: float | None = None
    required_annual_return: float | None = None
    current_path_status: GoalPathStatus = "unknown"
    summary: str


class PortfolioAIThemeExposure(BaseModel):
    total_ai_exposure_pct: float | None = None
    core_ai_exposure_pct: float | None = None
    infrastructure_exposure_pct: float | None = None
    non_ai_exposure_pct: float | None = None
    unknown_exposure_pct: float | None = None
    fake_ai_story_exposure_pct: float | None = None
    assessment: AIThemeAssessment = "unknown"


class PortfolioConcentrationRisk(BaseModel):
    top1_weight: float | None = None
    top3_weight: float | None = None
    top5_weight: float | None = None
    single_name_risk_symbols: list[str] = Field(default_factory=list)
    assessment: ConcentrationAssessment = "low"


class PortfolioCashStatus(BaseModel):
    cash_value: float | None = None
    cash_pct: float | None = None
    assessment: CashAssessment = "unknown"
    summary: str


class PortfolioPositionExposureItem(BaseModel):
    symbol: str
    display_symbol: str
    position_value: float
    position_weight: float
    ai_theme_role: AIThemeRole
    theme_tags: list[str] = Field(default_factory=list)
    universe_type: UniverseType = "holding"
    exposure_bucket: str


class PortfolioAllocationGap(BaseModel):
    symbol: str
    display_symbol: str
    position_weight: float | None = None
    ai_theme_role: AIThemeRole
    gap_type: AllocationGapType
    gap_reason: str
    priority: UniversePriority


class PortfolioAttentionSymbol(BaseModel):
    symbol: str
    reason: str
    priority: UniversePriority
    next_step: ActionQueueType


class PortfolioActionQueueItem(BaseModel):
    symbol: str
    queue_type: ActionQueueType
    priority: UniversePriority
    reason: str
    linked_decision_id: str | None = None


class PortfolioExposureAnalysis(BaseModel):
    ai_theme_exposure: PortfolioAIThemeExposure
    concentration_risk: PortfolioConcentrationRisk
    position_exposure_items: list[PortfolioPositionExposureItem] = Field(default_factory=list)
    data_limitations: list[str] = Field(default_factory=list)


class PortfolioAllocationAnalysis(BaseModel):
    goal_tracking: PortfolioGoalTracking
    cash_status: PortfolioCashStatus
    allocation_gaps: list[PortfolioAllocationGap] = Field(default_factory=list)
    top_attention_symbols: list[PortfolioAttentionSymbol] = Field(default_factory=list)
    action_queue: list[PortfolioActionQueueItem] = Field(default_factory=list)
    data_limitations: list[str] = Field(default_factory=list)


class PortfolioManagerReport(BaseModel):
    id: str
    report_date: str
    report_type: PortfolioReportType
    status: PortfolioReportStatus
    constitution_version: str
    source_watchtower_run_id: str | None = None
    source_auto_decision_run_id: str | None = None
    portfolio_health_score: int
    portfolio_health_level: PortfolioHealthLevel
    goal_tracking: PortfolioGoalTracking
    ai_theme_exposure: PortfolioAIThemeExposure
    concentration_risk: PortfolioConcentrationRisk
    cash_status: PortfolioCashStatus
    allocation_gaps: list[PortfolioAllocationGap] = Field(default_factory=list)
    top_attention_symbols: list[PortfolioAttentionSymbol] = Field(default_factory=list)
    action_queue: list[PortfolioActionQueueItem] = Field(default_factory=list)
    summary: str
    next_steps: list[str] = Field(default_factory=list)
    data_limitations: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class PortfolioManagerReportListResponse(BaseModel):
    items: list[PortfolioManagerReport]
