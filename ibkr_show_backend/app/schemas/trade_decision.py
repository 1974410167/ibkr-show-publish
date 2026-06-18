from typing import Literal

from pydantic import BaseModel, Field


class TradeDecisionHealthResponse(BaseModel):
    enabled: bool
    llm_configured: bool
    longbridge_configured: bool
    mcp_enabled: bool = False
    mcp_available: bool = False
    mcp_auth_status: str = "disabled"
    mcp_last_error: str = ""
    sdk_fallback_available: bool = False
    longbridge_sdk_configured: bool = False
    public_data_mode: str = "unavailable"
    trade_review_available: bool
    account_data_source: str
    public_market_data_source: str
    agent_mode: str = "trade_decision_langgraph_v1"
    graph_version: str = "trade_decision_graph_v1"
    message: str


class TradeDecisionHoldingItem(BaseModel):
    symbol: str
    normalized_symbol: str
    quantity: float | None = None
    avg_cost: float | None = None
    current_price: float | None = None
    market_value: float | None = None
    position_pct: float | None = None
    unrealized_pnl: float | None = None
    unrealized_pnl_pct: float | None = None
    latest_review_score: float | None = None
    latest_decision: str | None = None
    data_source: str = "IBKR"


class TradeDecisionHoldingsResponse(BaseModel):
    items: list[TradeDecisionHoldingItem]


class TradeDecisionAnalyzeHoldingRequest(BaseModel):
    question: str | None = None
    force_refresh: bool = False


class TradeDecisionAnalyzeEntryRequest(BaseModel):
    symbol: str
    question: str | None = None
    force_refresh: bool = False


class TradeDecisionAnalyzeAutoRequest(BaseModel):
    symbol: str
    force_refresh: bool = False


class TradeDecisionScoreItem(BaseModel):
    score: float
    max_score: float
    reason: str = ""


class TradeDecisionPositionAdvice(BaseModel):
    current_position_pct: float | None = None
    suggested_target_position_pct: float | None = None
    max_position_pct: float | None = None
    suggested_cash_amount: float | None = None
    position_size_label: str


class TradeDecisionExecutionStep(BaseModel):
    step: int | None = None
    condition: str | None = None
    action: str | None = None
    amount: float | None = None
    note: str | None = None


class TradeDecisionExecutionPlan(BaseModel):
    should_act_now: bool
    plan: list[dict] = Field(default_factory=list)
    invalid_conditions: list[str] = Field(default_factory=list)
    recheck_triggers: list[str] = Field(default_factory=list)


class AgentRunTraceItem(BaseModel):
    event: str
    node_name: str | None = None
    tool: str | None = None
    tool_call_id: str | None = None
    round: int | None = None
    arguments: dict | None = None
    steps: list[str] | None = None
    ok: bool | None = None
    summary: str | None = None
    latency_ms: int | None = None
    created_at_ms: int | None = None
    elapsed_ms: int | None = None
    tools_called: list[str] | None = None
    tool_call_count: int | None = None
    tool_calls: list[dict] | None = None
    rounds_used: int | None = None
    fallback_used: bool | None = None
    fallback_reason: str | None = None
    structured_output: dict | None = None


class TradeDecisionResult(BaseModel):
    id: str
    decision_type: str
    symbol: str
    user_question: str | None = None
    overall_score: float
    rating: str
    action: str
    draft_action: str | None = None
    risk_adjusted_action: str | None = None
    final_action: str | None = None
    action_change_reason: str | None = None
    action_downgrade_chain: list[dict] = Field(default_factory=list)
    confidence: str
    decision_summary: str
    score_detail: dict[str, TradeDecisionScoreItem]
    position_advice: TradeDecisionPositionAdvice
    execution_plan: TradeDecisionExecutionPlan
    key_reasons: list[str]
    major_risks: list[str]
    review_warnings: list[str]
    data_limitations: list[str]
    evidence_used: list[str]
    data_source_summary: dict
    card_pack: dict = Field(default_factory=dict)
    asset_debate: dict = Field(default_factory=dict)
    trade_plan: dict = Field(default_factory=dict)
    risk_gate: dict = Field(default_factory=dict)
    user_investment_policy_summary: dict | None = None
    ai_policy_assessment: dict = Field(default_factory=dict)
    behavior_profile_summary: dict | None = None
    personal_behavior_reminders: list[dict] = Field(default_factory=list)
    decision_quality: dict = Field(default_factory=dict)
    run_trace: list[AgentRunTraceItem] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    evidence_summary: dict = Field(default_factory=dict)
    run_trace_summary: dict = Field(default_factory=dict)
    fallback_used: bool = False
    fallback_reason: str | None = None
    llm_error_summary: dict = Field(default_factory=dict)
    created_at: str
    updated_at: str


class TradeDecisionListResponse(BaseModel):
    items: list[TradeDecisionResult]


class TradeDecisionOutcomeItem(BaseModel):
    decision_id: str
    symbol: str
    decision_type: str
    created_at: str
    decision_date: str | None = None
    draft_action: str | None = None
    risk_adjusted_action: str | None = None
    final_action: str | None = None
    action_group: str
    ai_position_stance: str | None = None
    ai_recommended_action_bias: str | None = None
    ai_recommended_target_position_pct: float | None = None
    ai_recommended_max_position_pct: float | None = None
    user_preferred_target_position_pct: float | None = None
    decision_price: float | None = None
    price_after_1d: float | None = None
    price_after_5d: float | None = None
    price_after_20d: float | None = None
    return_1d: float | None = None
    return_5d: float | None = None
    return_20d: float | None = None
    max_drawdown_20d: float | None = None
    max_runup_20d: float | None = None
    price_data_status: str = "unknown"
    outcome_label: str
    outcome_reason: str
    data_limitations: list[str] = Field(default_factory=list)


class TradeDecisionOutcomeSummary(BaseModel):
    version: str
    total_count: int
    evaluated_count: int
    pending_count: int
    missing_price_count: int
    add_like_count: int
    hold_like_count: int
    reduce_like_count: int
    add_like_avg_return_1d: float | None = None
    add_like_avg_return_5d: float | None = None
    add_like_avg_return_20d: float | None = None
    hold_like_avg_return_1d: float | None = None
    hold_like_avg_return_5d: float | None = None
    hold_like_avg_return_20d: float | None = None
    reduce_like_avg_return_1d: float | None = None
    reduce_like_avg_return_5d: float | None = None
    reduce_like_avg_return_20d: float | None = None
    add_like_win_rate_5d: float
    add_like_win_rate_20d: float
    bad_add_count: int
    missed_upside_count: int
    avoided_loss_count: int
    sold_too_early_count: int
    missed_ai_add_opportunity_count: int
    calibrated_action_success_count: int
    risk_gate_avoided_loss_count: int
    risk_gate_missed_upside_count: int
    action_value_score: float | None = None
    outcome_label_distribution: list[dict]
    action_group_distribution: list[dict]
    by_symbol: list[dict]
    by_final_action: list[dict]
    by_ai_recommended_action_bias: list[dict]
    by_ai_position_stance: list[dict]
    top_good_decisions: list[TradeDecisionOutcomeItem]
    top_bad_decisions: list[TradeDecisionOutcomeItem]
    top_missed_upside_decisions: list[TradeDecisionOutcomeItem]
    generated_at: str
    data_limitations: list[str] = Field(default_factory=list)


class TradeDecisionOutcomeListResponse(BaseModel):
    items: list[TradeDecisionOutcomeItem]
    summary: TradeDecisionOutcomeSummary


class TradeDecisionBacktestSummary(BaseModel):
    start_date: str | None = None
    end_date: str | None = None
    initial_cash: float
    final_equity: float
    total_return: float | None = None
    annualized_return: float | None = None
    max_drawdown: float | None = None
    sharpe_ratio: float | None = None
    volatility: float | None = None
    win_rate: float
    trade_count: int
    buy_count: int
    sell_count: int
    hold_count: int
    skipped_count: int
    turnover: float | None = None
    avg_cash_ratio: float | None = None
    max_single_position_pct: float | None = None
    benchmark_return: float | None = None
    excess_return: float | None = None
    calibrated_action_success_pnl: float
    missed_ai_add_opportunity_estimated_cost: float
    risk_gate_avoided_loss_estimated_value: float
    bad_add_realized_or_mark_pnl: float
    sold_too_early_estimated_cost: float


class TradeDecisionBacktestDailyPoint(BaseModel):
    date: str
    cash: float
    positions_value: float
    equity: float
    daily_return: float | None = None
    cumulative_return: float | None = None
    drawdown: float | None = None
    benchmark_value: float | None = None
    benchmark_return: float | None = None
    positions: dict = Field(default_factory=dict)


class TradeDecisionBacktestTrade(BaseModel):
    decision_id: str
    decision_date: str | None = None
    execution_date: str | None = None
    symbol: str
    final_action: str
    action_group: str
    side: str
    quantity: float
    execution_price: float | None = None
    notional: float
    commission: float
    target_position_pct: float | None = None
    max_position_pct: float | None = None
    realized_pnl: float | None = None
    mark_pnl: float | None = None
    reason: str


class TradeDecisionBacktestPosition(BaseModel):
    symbol: str
    quantity: float
    avg_cost: float
    last_price: float | None = None
    market_value: float
    weight: float | None = None
    unrealized_pnl: float
    realized_pnl: float


class TradeDecisionBacktestGroupStat(BaseModel):
    key: str
    trade_count: int
    avg_trade_return: float | None = None
    win_rate: float
    total_notional: float
    contribution_pnl: float
    avg_holding_days: float | None = None


class TradeDecisionBacktestResponse(BaseModel):
    version: str
    params: dict
    summary: TradeDecisionBacktestSummary
    equity_curve: list[TradeDecisionBacktestDailyPoint] = Field(default_factory=list)
    trades: list[TradeDecisionBacktestTrade] = Field(default_factory=list)
    positions: list[TradeDecisionBacktestPosition] = Field(default_factory=list)
    symbol_contributions: list[TradeDecisionBacktestGroupStat] = Field(default_factory=list)
    action_stats: list[TradeDecisionBacktestGroupStat] = Field(default_factory=list)
    data_limitations: list[str] = Field(default_factory=list)


class TradeDecisionMatchedRealTrade(BaseModel):
    trade_date: str | None = None
    date_time: str | None = None
    symbol: str
    side: str
    quantity: float
    trade_price: float | None = None
    notional: float
    commission: float | None = None
    fifo_pnl_realized: float | None = None
    trade_id: str | None = None


class TradeDecisionExecutionAlignmentItem(BaseModel):
    decision_id: str
    symbol: str
    decision_date: str | None = None
    final_action: str | None = None
    action_group: str
    ai_position_stance: str | None = None
    ai_recommended_action_bias: str | None = None
    suggested_target_position_pct: float | None = None
    suggested_adjustment_pct: float | None = None
    suggested_cash_amount: float | None = None
    real_trade_side: str
    real_trade_count: int
    real_buy_notional: float
    real_sell_notional: float
    real_net_notional: float
    real_weighted_avg_price: float | None = None
    first_real_trade_date: str | None = None
    execution_delay_trading_days: int | None = None
    alignment_label: str
    behavior_tags: list[str] = Field(default_factory=list)
    return_5d: float | None = None
    return_20d: float | None = None
    estimated_opportunity_cost: float
    estimated_avoided_loss: float
    estimated_bad_override_cost: float
    estimated_good_override_value: float
    explanation: str
    matched_trades: list[TradeDecisionMatchedRealTrade] = Field(default_factory=list)
    data_limitations: list[str] = Field(default_factory=list)


class TradeDecisionExecutionAlignmentSummary(BaseModel):
    version: str
    total_decisions: int
    matched_decisions: int
    evaluated_decisions: int
    followed_count: int
    partially_followed_count: int
    ignored_count: int
    contradicted_count: int
    over_executed_count: int
    no_trade_expected_count: int
    alignment_rate: float
    contradiction_rate: float
    ignored_add_signal_count: int
    ignored_reduce_signal_count: int
    manual_override_count: int
    good_override_count: int
    bad_override_count: int
    estimated_opportunity_cost_total: float
    estimated_avoided_loss_total: float
    estimated_bad_override_cost_total: float
    estimated_good_override_value_total: float
    net_behavior_value: float
    avg_execution_delay_days: float | None = None
    shadow_total_return: float | None = None
    shadow_max_drawdown: float | None = None
    shadow_sharpe: float | None = None
    real_account_return_estimate: float | None = None
    behavior_gap_estimate: float | None = None
    execution_gap_summary: dict = Field(default_factory=dict)
    by_symbol: list[dict] = Field(default_factory=list)
    by_final_action: list[dict] = Field(default_factory=list)
    by_action_group: list[dict] = Field(default_factory=list)
    by_ai_recommended_action_bias: list[dict] = Field(default_factory=list)
    by_behavior_tag: list[dict] = Field(default_factory=list)
    top_missed_opportunities: list[TradeDecisionExecutionAlignmentItem] = Field(default_factory=list)
    top_bad_overrides: list[TradeDecisionExecutionAlignmentItem] = Field(default_factory=list)
    top_good_overrides: list[TradeDecisionExecutionAlignmentItem] = Field(default_factory=list)
    top_good_discipline: list[TradeDecisionExecutionAlignmentItem] = Field(default_factory=list)
    top_agent_bad_follow: list[TradeDecisionExecutionAlignmentItem] = Field(default_factory=list)
    generated_at: str
    data_limitations: list[str] = Field(default_factory=list)


class TradeDecisionExecutionAlignmentListResponse(BaseModel):
    items: list[TradeDecisionExecutionAlignmentItem]
    summary: TradeDecisionExecutionAlignmentSummary


OverrideReasonCategory = Literal[
    "emotion",
    "capital_constraint",
    "external_information",
    "disagree_with_agent",
    "risk_control",
    "forgot",
    "execution_issue",
    "tax_or_cashflow",
    "other",
]
OverrideConfidence = Literal["high", "medium", "low"]
BehaviorRiskLevel = Literal["low", "medium", "high"]
BehaviorInsightSeverity = Literal["low", "medium", "high"]


class TradeDecisionOverrideAnnotationRequest(BaseModel):
    override_type: str = Field(default="other", max_length=120)
    reason_category: OverrideReasonCategory = "other"
    reason_text: str = Field(default="", max_length=2000)
    confidence: OverrideConfidence = "medium"
    was_intentional: bool = True
    was_emotional: bool = False
    should_remind_next_time: bool = False
    lesson: str = Field(default="", max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=20)


class TradeDecisionOverrideAnnotation(TradeDecisionOverrideAnnotationRequest):
    id: str
    decision_id: str
    symbol: str
    decision_date: str | None = None
    alignment_label: str | None = None
    behavior_tags: list[str] = Field(default_factory=list)
    enabled: bool = True
    created_at: str
    updated_at: str


class TradeDecisionOverrideAnnotationListResponse(BaseModel):
    items: list[TradeDecisionOverrideAnnotation]


class TradeDecisionBehaviorInsight(BaseModel):
    pattern: str
    severity: BehaviorInsightSeverity
    count: int
    rate: float
    estimated_cost: float
    symbols: list[str] = Field(default_factory=list)
    description: str
    suggestion: str


class TradeDecisionBehaviorCoachingHint(BaseModel):
    pattern: str
    severity: BehaviorInsightSeverity = "medium"
    message: str
    symbols: list[str] = Field(default_factory=list)
    source: str = "deterministic_profile"
    annotation_decision_id: str | None = None


class TradeDecisionBehaviorProfileItem(BaseModel):
    decision_id: str
    symbol: str
    decision_date: str | None = None
    final_action: str | None = None
    alignment_label: str
    behavior_tags: list[str] = Field(default_factory=list)
    estimated_opportunity_cost: float
    estimated_avoided_loss: float
    estimated_bad_override_cost: float
    estimated_good_override_value: float
    profile_contribution: float
    annotation: TradeDecisionOverrideAnnotation | None = None


class TradeDecisionBehaviorProfileSummary(BaseModel):
    version: str = "trade_decision_behavior_profile_v1"
    start_date: str | None = None
    end_date: str | None = None
    total_decisions: int
    evaluated_decisions: int
    alignment_rate: float
    manual_override_rate: float
    ignored_add_signal_rate: float
    ignored_reduce_signal_rate: float
    contradiction_rate: float
    over_execution_rate: float
    under_execution_rate: float
    premature_trim_rate: float
    good_override_rate: float
    bad_override_rate: float
    net_behavior_value: float
    estimated_opportunity_cost_total: float
    estimated_bad_override_cost_total: float
    estimated_good_override_value_total: float
    top_behavior_tags: list[dict] = Field(default_factory=list)
    top_reason_categories: list[dict] = Field(default_factory=list)
    top_symbols_with_bias: list[dict] = Field(default_factory=list)
    behavior_risk_level: BehaviorRiskLevel
    dominant_behavior_patterns: list[TradeDecisionBehaviorInsight] = Field(default_factory=list)
    coaching_hints: list[TradeDecisionBehaviorCoachingHint] = Field(default_factory=list)
    generated_at: str
    data_limitations: list[str] = Field(default_factory=list)


class TradeDecisionBehaviorProfileResponse(BaseModel):
    summary: TradeDecisionBehaviorProfileSummary
    insights: list[TradeDecisionBehaviorInsight] = Field(default_factory=list)
    coaching_hints: list[TradeDecisionBehaviorCoachingHint] = Field(default_factory=list)
    items: list[TradeDecisionBehaviorProfileItem] = Field(default_factory=list)
