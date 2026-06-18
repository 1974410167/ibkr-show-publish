from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PortfolioActionAlertStatus = Literal["pending", "sent", "skipped", "failed"]
PortfolioActionAlertType = Literal["add_position_review", "entry_position_review", "reduce_position_review", "risk_review"]
PortfolioActionDirection = Literal["consider_add", "consider_entry", "consider_reduce", "review_risk"]
PortfolioActionAlertUrgency = Literal["low", "medium", "high"]
PortfolioActionAlertConfidence = Literal["low", "medium", "high"]


class PortfolioActionAlertCreate(BaseModel):
    run_date: str
    alert_type: PortfolioActionAlertType
    symbol: str
    display_symbol: str
    title: str
    action_direction: PortfolioActionDirection
    urgency: PortfolioActionAlertUrgency = "medium"
    confidence: PortfolioActionAlertConfidence = "medium"
    reason_summary: list[str] = Field(default_factory=list)
    decision_summary: dict = Field(default_factory=dict)
    portfolio_context: dict = Field(default_factory=dict)
    linked_ids: dict = Field(default_factory=dict)
    suggested_user_action: str
    not_an_order: bool = True


class PortfolioActionAlert(PortfolioActionAlertCreate):
    id: str
    status: PortfolioActionAlertStatus = "pending"
    email_subject: str | None = None
    email_sent_at: str | None = None
    email_error: str | None = None
    created_at: str
    updated_at: str


class PortfolioActionAlertRunResult(BaseModel):
    daily_loop_run_id: str
    run_date: str | None = None
    alerts_created: int = 0
    alerts_sent: int = 0
    alerts_skipped: int = 0
    alerts_failed: int = 0
    email_enabled: bool = False
    data_limitations: list[str] = Field(default_factory=list)


class PortfolioActionAlertListResponse(BaseModel):
    items: list[PortfolioActionAlert]
