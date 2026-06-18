from __future__ import annotations

from pydantic import BaseModel, Field

from app.domains.portfolio_manager.constitution.default_policy import INVESTMENT_CONSTITUTION_DISCLAIMER


class InvestmentConstitutionBase(BaseModel):
    constitution_version: str = "portfolio_constitution_v1"
    target_account_value_usd: float = Field(gt=0)
    target_date: str
    starting_capital_usd: float = Field(gt=0)
    primary_theme: str
    primary_theme_description: str
    primary_theme_buckets: list[str] = Field(default_factory=list)
    allow_future_deposits: bool = True
    deposits_count_as_primary_driver: bool = False
    core_time_horizon_years: int = Field(gt=0)
    short_term_volatility_policy: str
    decision_principles: list[str] = Field(default_factory=list)
    forbidden_behaviors: list[str] = Field(default_factory=list)
    risk_constraints: dict[str, bool] = Field(default_factory=dict)
    enabled: bool = True


class InvestmentConstitutionUpdate(InvestmentConstitutionBase):
    pass


class InvestmentConstitution(InvestmentConstitutionBase):
    id: str = "default"
    created_at: str
    updated_at: str
    disclaimer: str = INVESTMENT_CONSTITUTION_DISCLAIMER


class InvestmentConstitutionListResponse(BaseModel):
    items: list[InvestmentConstitution]

