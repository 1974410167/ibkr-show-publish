from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domains.portfolio_manager.evaluation.schemas import PortfolioEvaluationHorizon

PortfolioDailyLoopRunType = Literal["manual", "scheduled", "backfill"]
PortfolioDailyLoopStatus = Literal["success", "partial_success", "failed", "running", "cancelled"]
PortfolioDailyLoopStepName = Literal["sync_holdings", "watchtower", "auto_decision", "portfolio_report", "evaluation", "improvement"]
PortfolioDailyLoopStepStatus = Literal["success", "skipped", "failed", "running"]

DEFAULT_DAILY_LOOP_EVALUATION_HORIZONS: list[PortfolioEvaluationHorizon] = ["1d", "5d", "20d"]
DEFAULT_DAILY_LOOP_IMPROVEMENT_HORIZONS: list[PortfolioEvaluationHorizon] = ["5d", "20d", "60d"]


class PortfolioDailyLoopOptions(BaseModel):
    sync_holdings: bool = True
    run_watchtower: bool = True
    run_auto_decision: bool = True
    generate_portfolio_report: bool = True
    run_evaluation: bool = False
    generate_improvement_report: bool = False
    dry_run_auto_decision: bool = False
    max_auto_decisions: int = Field(default=5, ge=0, le=100)
    force_refresh_auto_decision: bool = False
    evaluation_horizons: list[PortfolioEvaluationHorizon] = Field(default_factory=lambda: list(DEFAULT_DAILY_LOOP_EVALUATION_HORIZONS))
    evaluation_lookback_days: int = Field(default=180, ge=1, le=3650)
    improvement_horizons: list[PortfolioEvaluationHorizon] = Field(default_factory=lambda: list(DEFAULT_DAILY_LOOP_IMPROVEMENT_HORIZONS))
    improvement_lookback_days: int = Field(default=180, ge=1, le=3650)
    improvement_min_sample_size: int = Field(default=5, ge=1, le=1000)


class PortfolioDailyLoopStep(BaseModel):
    step: PortfolioDailyLoopStepName
    status: PortfolioDailyLoopStepStatus
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int | None = None
    summary: dict = Field(default_factory=dict)
    run_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class PortfolioDailyLoopRunCreate(BaseModel):
    run_date: str | None = None
    run_type: PortfolioDailyLoopRunType = "manual"
    sync_holdings: bool = True
    run_watchtower: bool = True
    run_auto_decision: bool = True
    generate_portfolio_report: bool = True
    run_evaluation: bool = False
    generate_improvement_report: bool = False
    dry_run_auto_decision: bool = False
    max_auto_decisions: int = Field(default=5, ge=0, le=100)
    force_refresh_auto_decision: bool = False
    evaluation_horizons: list[PortfolioEvaluationHorizon] | None = None
    evaluation_lookback_days: int = Field(default=180, ge=1, le=3650)
    improvement_horizons: list[PortfolioEvaluationHorizon] | None = None
    improvement_lookback_days: int = Field(default=180, ge=1, le=3650)
    improvement_min_sample_size: int = Field(default=5, ge=1, le=1000)
    background: bool = True


class PortfolioDailyLoopRun(BaseModel):
    id: str
    run_date: str
    run_type: PortfolioDailyLoopRunType
    status: PortfolioDailyLoopStatus
    task_id: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int | None = None
    options: PortfolioDailyLoopOptions
    steps: list[PortfolioDailyLoopStep] = Field(default_factory=list)
    linked_run_ids: dict = Field(default_factory=dict)
    summary: dict = Field(default_factory=dict)
    data_limitations: list[str] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str


class PortfolioDailyLoopRunListResponse(BaseModel):
    items: list[PortfolioDailyLoopRun]


class PortfolioDailyLoopRunResponse(BaseModel):
    task_id: str | None = None
    run_id: str
    background: bool
    run: PortfolioDailyLoopRun | None = None
    message: str


class PortfolioDailyLoopScheduleStatus(BaseModel):
    enabled: bool
    schedule_time: str
    schedule_timezone: str
    next_run_hint: str | None = None
    max_auto_decisions: int
    dry_run_auto_decision: bool
    force_refresh_auto_decision: bool
    run_evaluation: bool
    generate_improvement_report: bool


class PortfolioDailyLoopScheduledRunRequest(BaseModel):
    run_date: str | None = None
    force: bool = False
    background: bool = True


class PortfolioDailyLoopScheduledRunResponse(BaseModel):
    skipped: bool = False
    reason: str | None = None
    existing_run_id: str | None = None
    task_id: str | None = None
    run_id: str | None = None
    background: bool = True
    run: PortfolioDailyLoopRun | None = None
    message: str
