from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domains.portfolio_manager.evaluation.schemas import PortfolioEvaluationHorizon

PortfolioImprovementReportType = Literal["manual", "scheduled", "backfill"]
PortfolioImprovementReportStatus = Literal["success", "partial_success", "failed"]
PortfolioImprovementSeverity = Literal["low", "medium", "high"]
PortfolioImprovementConfidence = Literal["low", "medium", "high"]
PortfolioImprovementCandidateStatus = Literal["proposed", "accepted", "rejected", "implemented", "archived"]
PortfolioImprovementCandidateType = Literal[
    "watchtower_trigger_rule",
    "auto_decision_selector",
    "portfolio_review_rule",
    "data_quality",
    "trade_decision_prompt_context",
    "risk_gate_review",
    "universe_management",
    "evaluation_design",
]

DEFAULT_IMPROVEMENT_HORIZONS: list[PortfolioEvaluationHorizon] = ["5d", "20d", "60d"]
DEFAULT_AFFECTED_VERSIONS = {
    "portfolio_manager_version": "unknown",
    "watchtower_version": "unknown",
    "auto_decision_version": "unknown",
    "portfolio_review_version": "unknown",
    "evaluation_version": "unknown",
}


class PortfolioImprovementGenerateRequest(BaseModel):
    report_date: str | None = None
    report_type: PortfolioImprovementReportType = "manual"
    lookback_days: int = Field(default=180, ge=1, le=3650)
    horizons: list[PortfolioEvaluationHorizon] | None = None
    min_sample_size: int = Field(default=5, ge=1, le=1000)


class PortfolioImprovementPattern(BaseModel):
    pattern_type: str
    source_type: str
    group_key: str
    affected_module: str
    affected_rule_or_component: str
    severity: PortfolioImprovementSeverity
    confidence: PortfolioImprovementConfidence
    sample_size: int
    horizons: list[str] = Field(default_factory=list)
    labels: dict[str, int] = Field(default_factory=dict)
    metrics: dict[str, float | int | str | None] = Field(default_factory=dict)
    evidence_result_ids: list[str] = Field(default_factory=list)
    description: str
    suggested_direction: str


class PortfolioImprovementEvidenceSummary(BaseModel):
    sample_size: int
    horizons: list[str] = Field(default_factory=list)
    source_type: str
    labels: dict[str, int] = Field(default_factory=dict)
    metrics: dict[str, float | int | str | None] = Field(default_factory=dict)
    example_result_ids: list[str] = Field(default_factory=list)


class PortfolioImprovementCandidate(BaseModel):
    id: str
    candidate_type: PortfolioImprovementCandidateType
    title: str
    severity: PortfolioImprovementSeverity
    confidence: PortfolioImprovementConfidence
    requires_human_approval: bool = True
    status: PortfolioImprovementCandidateStatus = "proposed"
    affected_module: str
    affected_rule_or_component: str
    affected_versions: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_AFFECTED_VERSIONS))
    evidence_summary: PortfolioImprovementEvidenceSummary
    suggested_change: str
    expected_impact: str
    risk_of_change: str
    human_review_notes: str = ""
    created_at: str
    updated_at: str


class PortfolioImprovementReport(BaseModel):
    id: str
    report_date: str
    report_type: PortfolioImprovementReportType
    status: PortfolioImprovementReportStatus
    lookback_days: int
    horizons: list[PortfolioEvaluationHorizon] = Field(default_factory=list)
    source_evaluation_summary: dict = Field(default_factory=dict)
    pattern_summary: dict = Field(default_factory=dict)
    improvement_candidates: list[PortfolioImprovementCandidate] = Field(default_factory=list)
    recommendation_summary: str
    data_limitations: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class PortfolioImprovementReportListResponse(BaseModel):
    items: list[PortfolioImprovementReport]
