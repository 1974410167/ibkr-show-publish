from typing import Literal

from pydantic import BaseModel, Field


AccountPerformanceDataQuality = Literal["complete", "partial", "missing"]


class AccountPerformancePoint(BaseModel):
    date: str
    nav: float | None = None
    net_cash_flow: float = 0.0
    investment_pnl: float | None = None
    daily_return: float | None = None
    twr_index: float | None = None
    data_quality: AccountPerformanceDataQuality = "complete"
    data_limitations: list[str] = Field(default_factory=list)


class AccountPerformanceSummary(BaseModel):
    start_date: str | None = None
    end_date: str | None = None
    start_nav: float | None = None
    end_nav: float | None = None
    total_net_cash_flow: float = 0.0
    money_gain: float | None = None
    twr_total_return: float | None = None
    annualized_return: float | None = None
    max_drawdown: float | None = None
    volatility: float | None = None
    sharpe_ratio: float | None = None
    data_quality: AccountPerformanceDataQuality = "complete"
    data_limitations: list[str] = Field(default_factory=list)


class PerformanceMethodology(BaseModel):
    return_method: str = "time_weighted_return"
    cashflow_adjusted: bool = True
    base_index: float = 100.0


class PerformanceSeriesResponse(BaseModel):
    summary: AccountPerformanceSummary
    series: list[AccountPerformancePoint]
    methodology: PerformanceMethodology
