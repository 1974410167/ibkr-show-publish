from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PortfolioEvaluationSourceType = Literal["watchtower_item", "auto_decision_item", "portfolio_report"]
PortfolioEvaluationHorizon = Literal["1d", "5d", "20d", "60d", "120d", "1y"]
PortfolioPriceDataStatus = Literal["ok", "partial", "missing", "pending"]
PortfolioEvaluationLabel = Literal[
    "useful_attention",
    "false_positive",
    "missed_opportunity",
    "good_action",
    "bad_action",
    "risk_avoided",
    "pending",
    "inconclusive",
]

HORIZON_DAYS: dict[str, int] = {"1d": 1, "5d": 5, "20d": 20, "60d": 60, "120d": 120, "1y": 252}
DEFAULT_EVALUATION_HORIZONS: list[PortfolioEvaluationHorizon] = ["1d", "5d", "20d", "60d", "120d", "1y"]
DEFAULT_EVALUATION_SOURCE_TYPES: list[PortfolioEvaluationSourceType] = ["watchtower_item", "auto_decision_item", "portfolio_report"]


class ForwardPriceMetrics(BaseModel):
    price_data_status: PortfolioPriceDataStatus
    start_price: float | None = None
    end_price: float | None = None
    forward_return: float | None = None
    max_drawdown: float | None = None
    max_runup: float | None = None
    benchmark_symbol: str
    benchmark_return: float | None = None
    benchmark_relative_return: float | None = None
    data_limitations: list[str] = Field(default_factory=list)


class PortfolioEvaluationResult(BaseModel):
    id: str
    evaluation_date: str
    source_type: PortfolioEvaluationSourceType
    source_id: str
    source_run_id: str | None = None
    symbol: str | None = None
    display_symbol: str | None = None
    horizon: PortfolioEvaluationHorizon
    horizon_days: int
    source_date: str
    source_status: str | None = None
    source_action: str | None = None
    source_snapshot: dict = Field(default_factory=dict)
    price_data_status: PortfolioPriceDataStatus
    start_price: float | None = None
    end_price: float | None = None
    forward_return: float | None = None
    max_drawdown: float | None = None
    max_runup: float | None = None
    benchmark_symbol: str = "SPY"
    benchmark_return: float | None = None
    benchmark_relative_return: float | None = None
    evaluation_label: PortfolioEvaluationLabel
    evaluation_reason: str
    metric_summary: dict = Field(default_factory=dict)
    data_limitations: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class PortfolioEvaluationSummary(BaseModel):
    generated_at: str
    lookback_days: int
    horizons: list[PortfolioEvaluationHorizon] = Field(default_factory=list)
    total_results: int = 0
    pending: int = 0
    completed: int = 0
    by_source_type: dict[str, int] = Field(default_factory=dict)
    by_label: dict[str, int] = Field(default_factory=dict)
    watchtower: dict = Field(default_factory=dict)
    auto_decision: dict = Field(default_factory=dict)
    portfolio_report: dict = Field(default_factory=dict)
    data_limitations: list[str] = Field(default_factory=list)


class PortfolioEvaluationRunRequest(BaseModel):
    evaluation_date: str | None = None
    source_types: list[PortfolioEvaluationSourceType] | None = None
    horizons: list[PortfolioEvaluationHorizon] | None = None
    lookback_days: int = Field(default=180, ge=1, le=3650)
    benchmark_symbol: str = "SPY"
    limit: int = Field(default=1000, ge=1, le=5000)


class PortfolioEvaluationRunResponse(BaseModel):
    created_or_updated_count: int
    pending_count: int
    completed_count: int
    summary: PortfolioEvaluationSummary
    data_limitations: list[str] = Field(default_factory=list)


class PortfolioEvaluationResultListResponse(BaseModel):
    items: list[PortfolioEvaluationResult]


class PortfolioEvaluationSymbolHistoryResponse(BaseModel):
    items: list[PortfolioEvaluationResult]
