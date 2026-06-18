from __future__ import annotations

DEFAULT_INVESTMENT_CONSTITUTION: dict = {
    "id": "default",
    "constitution_version": "portfolio_constitution_v1",
    "target_account_value_usd": 1500000,
    "target_date": "2035-12-31",
    "starting_capital_usd": 90000,
    "primary_theme": "AI",
    "primary_theme_description": "未来十年投资主线围绕人工智能、AI 算力、AI 基础设施、AI 平台、AI 应用及其确定性受益链条。",
    "primary_theme_buckets": [
        "ai_compute",
        "semiconductor",
        "data_center",
        "cloud_platform",
        "ai_infrastructure",
        "ai_application",
        "power_and_cooling",
        "memory_and_networking",
    ],
    "allow_future_deposits": True,
    "deposits_count_as_primary_driver": False,
    "core_time_horizon_years": 10,
    "short_term_volatility_policy": "中短期波动只作为风险、买点和仓位管理信号，不作为偏离长期主线的充分理由。",
    "decision_principles": [
        "long_term_compounding",
        "ai_theme_alignment",
        "risk_budget_control",
        "evidence_based_actions",
        "market_feedback_evaluation",
        "behavior_discipline",
    ],
    "forbidden_behaviors": [
        "panic_sell_core_ai_assets",
        "chase_fake_ai_story",
        "over_concentrate_without_risk_budget",
        "optimize_for_short_term_win_rate",
        "ignore_market_feedback",
        "treat_deposits_as_primary_growth_driver",
        "auto_change_rules_without_human_approval",
    ],
    "risk_constraints": {
        "no_automatic_order_execution": True,
        "human_approval_required_for_rule_changes": True,
        "market_feedback_is_noisy": True,
        "do_not_define_correctness_by_price_only": True,
    },
    "enabled": True,
}

INVESTMENT_CONSTITUTION_DISCLAIMER = "投资宪法是系统最高层长期约束，不代表收益承诺，不构成投资建议。"


def default_constitution_document() -> dict:
    return dict(DEFAULT_INVESTMENT_CONSTITUTION)

