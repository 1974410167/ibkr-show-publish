from enum import StrEnum

from pydantic import BaseModel, Field

from app.domains.performance.schemas import AccountPerformanceDataQuality, AccountPerformancePoint, AccountPerformanceSummary


class PerformanceBaselineType(StrEnum):
    ACTUAL_ACCOUNT = "actual_account"
    SPY_CASHFLOW_MATCHED = "spy_cashflow_matched"
    QQQ_CASHFLOW_MATCHED = "qqq_cashflow_matched"
    START_PORTFOLIO_BUY_AND_HOLD = "start_portfolio_buy_and_hold"


class BaselinePerformancePoint(BaseModel):
    date: str
    baseline_type: PerformanceBaselineType
    nav: float | None = None
    net_cash_flow: float = 0.0
    daily_return: float | None = None
    return_index: float | None = None
    benchmark_price: float | None = None
    units: float | None = None
    cash: float = 0.0
    data_quality: AccountPerformanceDataQuality = "complete"
    data_limitations: list[str] = Field(default_factory=list)


class BaselinePerformanceSummary(BaseModel):
    baseline_type: PerformanceBaselineType
    label: str
    start_date: str | None = None
    end_date: str | None = None
    start_nav: float | None = None
    end_nav: float | None = None
    total_net_cash_flow: float = 0.0
    money_gain: float | None = None
    total_return: float | None = None
    annualized_return: float | None = None
    max_drawdown: float | None = None
    volatility: float | None = None
    sharpe_ratio: float | None = None
    data_quality: AccountPerformanceDataQuality = "complete"
    data_limitations: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class PerformanceComparisonSummary(BaseModel):
    start_date: str | None = None
    end_date: str | None = None
    actual: AccountPerformanceSummary
    baselines: list[BaselinePerformanceSummary]
    excess_returns: dict[str, float | None] = Field(default_factory=dict)
    value_added: dict[str, float | None] = Field(default_factory=dict)
    data_quality: AccountPerformanceDataQuality = "complete"
    data_limitations: list[str] = Field(default_factory=list)


class PerformanceComparisonMethodology(BaseModel):
    return_method: str = "time_weighted_return"
    cashflow_adjusted: bool = True
    base_index: float = 100.0
    benchmark_price_field: str = "close_price"


class PerformanceComparisonSeriesResponse(BaseModel):
    summary: PerformanceComparisonSummary
    series: dict[PerformanceBaselineType, list[AccountPerformancePoint] | list[BaselinePerformancePoint]]
    methodology: PerformanceComparisonMethodology
