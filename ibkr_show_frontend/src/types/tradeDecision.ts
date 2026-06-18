export interface TradeDecisionHealth {
  enabled: boolean
  llm_configured: boolean
  longbridge_configured: boolean
  mcp_enabled: boolean
  mcp_available: boolean
  mcp_auth_status: string
  mcp_last_error: string
  sdk_fallback_available: boolean
  longbridge_sdk_configured: boolean
  public_data_mode: string
  trade_review_available: boolean
  account_data_source: string
  public_market_data_source: string
  message: string
}

export interface TradeDecisionScoreItem {
  score: number
  max_score: number
  reason: string
}

export interface TradeDecisionPositionAdvice {
  current_position_pct: number | null
  suggested_target_position_pct: number | null
  max_position_pct: number | null
  suggested_cash_amount: number | null
  position_size_label: string
  adjustment_pct?: number | null
}

export interface TradeDecisionExecutionPlan {
  should_act_now: boolean
  plan: Array<Record<string, unknown>>
  invalid_conditions: string[]
  recheck_triggers: string[]
}

export interface AgentRunTraceItem {
  event: string
  tool?: string | null
  tool_call_id?: string | null
  round?: number | null
  arguments?: Record<string, unknown> | null
  steps?: string[] | null
  ok?: boolean | null
  summary?: string | null
  latency_ms?: number | null
  created_at_ms?: number | null
}

export interface TradeDecisionQualityCheck {
  passed?: boolean
  hard_failures?: string[]
  warnings?: string[]
  flags?: string[]
  [key: string]: unknown
}

export interface TradeDecisionQuality {
  version?: string
  score?: number
  level?: 'excellent' | 'good' | 'warning' | 'poor' | string
  passed?: boolean
  hard_failures?: string[]
  warnings?: string[]
  flags?: string[]
  checks?: Record<string, TradeDecisionQualityCheck>
  summary?: string
  fallback_used?: boolean
  fallback_reason?: string | null
}

export interface TradeDecisionQualityTopItem {
  key: string
  count: number
}

export interface TradeDecisionQualityTrendItem {
  id: string
  symbol: string
  created_at: string
  score: number | null
  level: string
  passed: boolean | null
  action: string
}

export interface TradeDecisionQualitySummary {
  version: string
  total_count: number
  evaluated_count: number
  unevaluated_count: number
  pass_count: number
  fail_count: number
  pass_rate: number | null
  average_score: number | null
  level_distribution: Record<string, number>
  risk_gate: Record<string, unknown>
  structured_output: Record<string, unknown>
  action_consistency: Record<string, unknown>
  ai_policy_assessment: Record<string, unknown>
  action_calibration: Record<string, unknown>
  top_hard_failures: TradeDecisionQualityTopItem[]
  top_warnings: TradeDecisionQualityTopItem[]
  top_flags: TradeDecisionQualityTopItem[]
  recent_trend: TradeDecisionQualityTrendItem[]
  generated_at: string
  data_limitations: string[]
}

export interface PersonalBehaviorReminder {
  type: string
  severity: 'low' | 'medium' | 'high' | string
  message: string
  related_action: string
  source: string
}

export interface TradeDecisionBehaviorProfileCompactSummary {
  status: string
  lookback_days?: number | null
  scope?: string | null
  symbol?: string | null
  behavior_risk_level: 'low' | 'medium' | 'high' | 'unknown' | string
  dominant_behavior_patterns: string[]
  top_symbols_with_bias?: Array<TradeDecisionQualityTopItem & { estimated_cost?: number; top_tags?: TradeDecisionQualityTopItem[] }>
  net_behavior_value?: number | null
  reminder_enabled: boolean
  data_limitations: string[]
  source?: string
}

export interface TradeDecisionOutcomeItem {
  decision_id: string
  symbol: string
  decision_type: string
  created_at: string
  decision_date: string | null
  draft_action: string | null
  risk_adjusted_action: string | null
  final_action: string | null
  action_group: string
  ai_position_stance: string | null
  ai_recommended_action_bias: string | null
  ai_recommended_target_position_pct: number | null
  ai_recommended_max_position_pct: number | null
  user_preferred_target_position_pct: number | null
  decision_price: number | null
  price_after_1d: number | null
  price_after_5d: number | null
  price_after_20d: number | null
  return_1d: number | null
  return_5d: number | null
  return_20d: number | null
  max_drawdown_20d: number | null
  max_runup_20d: number | null
  price_data_status: string
  outcome_label: string
  outcome_reason: string
  data_limitations: string[]
}

export interface TradeDecisionOutcomeSummary {
  version: string
  total_count: number
  evaluated_count: number
  pending_count: number
  missing_price_count: number
  add_like_count: number
  hold_like_count: number
  reduce_like_count: number
  add_like_avg_return_1d: number | null
  add_like_avg_return_5d: number | null
  add_like_avg_return_20d: number | null
  hold_like_avg_return_1d: number | null
  hold_like_avg_return_5d: number | null
  hold_like_avg_return_20d: number | null
  reduce_like_avg_return_1d: number | null
  reduce_like_avg_return_5d: number | null
  reduce_like_avg_return_20d: number | null
  add_like_win_rate_5d: number
  add_like_win_rate_20d: number
  bad_add_count: number
  missed_upside_count: number
  avoided_loss_count: number
  sold_too_early_count: number
  missed_ai_add_opportunity_count: number
  calibrated_action_success_count: number
  risk_gate_avoided_loss_count: number
  risk_gate_missed_upside_count: number
  action_value_score: number | null
  outcome_label_distribution: TradeDecisionQualityTopItem[]
  action_group_distribution: TradeDecisionQualityTopItem[]
  by_symbol: TradeDecisionQualityTopItem[]
  by_final_action: TradeDecisionQualityTopItem[]
  by_ai_recommended_action_bias: TradeDecisionQualityTopItem[]
  by_ai_position_stance: TradeDecisionQualityTopItem[]
  top_good_decisions: TradeDecisionOutcomeItem[]
  top_bad_decisions: TradeDecisionOutcomeItem[]
  top_missed_upside_decisions: TradeDecisionOutcomeItem[]
  generated_at: string
  data_limitations: string[]
}

export interface TradeDecisionOutcomeListResponse {
  items: TradeDecisionOutcomeItem[]
  summary: TradeDecisionOutcomeSummary
}

export interface TradeDecisionBacktestSummary {
  start_date: string | null
  end_date: string | null
  initial_cash: number
  final_equity: number
  total_return: number | null
  annualized_return: number | null
  max_drawdown: number | null
  sharpe_ratio: number | null
  volatility: number | null
  win_rate: number
  trade_count: number
  buy_count: number
  sell_count: number
  hold_count: number
  skipped_count: number
  turnover: number | null
  avg_cash_ratio: number | null
  max_single_position_pct: number | null
  benchmark_return: number | null
  excess_return: number | null
  calibrated_action_success_pnl: number
  missed_ai_add_opportunity_estimated_cost: number
  risk_gate_avoided_loss_estimated_value: number
  bad_add_realized_or_mark_pnl: number
  sold_too_early_estimated_cost: number
}

export interface TradeDecisionBacktestDailyPoint {
  date: string
  cash: number
  positions_value: number
  equity: number
  daily_return: number | null
  cumulative_return: number | null
  drawdown: number | null
  benchmark_value: number | null
  benchmark_return: number | null
  positions: Record<string, {
    quantity: number
    price: number
    market_value: number
    weight: number | null
  }>
}

export interface TradeDecisionBacktestTrade {
  decision_id: string
  decision_date: string | null
  execution_date: string | null
  symbol: string
  final_action: string
  action_group: string
  side: string
  quantity: number
  execution_price: number | null
  notional: number
  commission: number
  target_position_pct: number | null
  max_position_pct: number | null
  realized_pnl: number | null
  mark_pnl: number | null
  reason: string
}

export interface TradeDecisionBacktestPosition {
  symbol: string
  quantity: number
  avg_cost: number
  last_price: number | null
  market_value: number
  weight: number | null
  unrealized_pnl: number
  realized_pnl: number
}

export interface TradeDecisionBacktestGroupStat {
  key: string
  trade_count: number
  avg_trade_return: number | null
  win_rate: number
  total_notional: number
  contribution_pnl: number
  avg_holding_days: number | null
}

export interface TradeDecisionBacktestResponse {
  version: string
  params: Record<string, unknown>
  summary: TradeDecisionBacktestSummary
  equity_curve: TradeDecisionBacktestDailyPoint[]
  trades: TradeDecisionBacktestTrade[]
  positions: TradeDecisionBacktestPosition[]
  symbol_contributions: TradeDecisionBacktestGroupStat[]
  action_stats: TradeDecisionBacktestGroupStat[]
  data_limitations: string[]
}

export interface TradeDecisionMatchedRealTrade {
  trade_date: string | null
  date_time: string | null
  symbol: string
  side: string
  quantity: number
  trade_price: number | null
  notional: number
  commission: number | null
  fifo_pnl_realized: number | null
  trade_id: string | null
}

export interface TradeDecisionExecutionAlignmentItem {
  decision_id: string
  symbol: string
  decision_date: string | null
  final_action: string | null
  action_group: string
  ai_position_stance: string | null
  ai_recommended_action_bias: string | null
  suggested_target_position_pct: number | null
  suggested_adjustment_pct: number | null
  suggested_cash_amount: number | null
  real_trade_side: string
  real_trade_count: number
  real_buy_notional: number
  real_sell_notional: number
  real_net_notional: number
  real_weighted_avg_price: number | null
  first_real_trade_date: string | null
  execution_delay_trading_days: number | null
  alignment_label: string
  behavior_tags: string[]
  return_5d: number | null
  return_20d: number | null
  estimated_opportunity_cost: number
  estimated_avoided_loss: number
  estimated_bad_override_cost: number
  estimated_good_override_value: number
  explanation: string
  matched_trades: TradeDecisionMatchedRealTrade[]
  data_limitations: string[]
}

export interface TradeDecisionExecutionAlignmentSummary {
  version: string
  total_decisions: number
  matched_decisions: number
  evaluated_decisions: number
  followed_count: number
  partially_followed_count: number
  ignored_count: number
  contradicted_count: number
  over_executed_count: number
  no_trade_expected_count: number
  alignment_rate: number
  contradiction_rate: number
  ignored_add_signal_count: number
  ignored_reduce_signal_count: number
  manual_override_count: number
  good_override_count: number
  bad_override_count: number
  estimated_opportunity_cost_total: number
  estimated_avoided_loss_total: number
  estimated_bad_override_cost_total: number
  estimated_good_override_value_total: number
  net_behavior_value: number
  avg_execution_delay_days: number | null
  shadow_total_return: number | null
  shadow_max_drawdown: number | null
  shadow_sharpe: number | null
  real_account_return_estimate: number | null
  behavior_gap_estimate: number | null
  execution_gap_summary: Record<string, unknown>
  by_symbol: TradeDecisionQualityTopItem[]
  by_final_action: TradeDecisionQualityTopItem[]
  by_action_group: TradeDecisionQualityTopItem[]
  by_ai_recommended_action_bias: TradeDecisionQualityTopItem[]
  by_behavior_tag: TradeDecisionQualityTopItem[]
  top_missed_opportunities: TradeDecisionExecutionAlignmentItem[]
  top_bad_overrides: TradeDecisionExecutionAlignmentItem[]
  top_good_overrides: TradeDecisionExecutionAlignmentItem[]
  top_good_discipline: TradeDecisionExecutionAlignmentItem[]
  top_agent_bad_follow: TradeDecisionExecutionAlignmentItem[]
  generated_at: string
  data_limitations: string[]
}

export interface TradeDecisionExecutionAlignmentListResponse {
  items: TradeDecisionExecutionAlignmentItem[]
  summary: TradeDecisionExecutionAlignmentSummary
}

export type OverrideReasonCategory =
  | 'emotion'
  | 'capital_constraint'
  | 'external_information'
  | 'disagree_with_agent'
  | 'risk_control'
  | 'forgot'
  | 'execution_issue'
  | 'tax_or_cashflow'
  | 'other'

export type OverrideConfidence = 'high' | 'medium' | 'low'

export interface TradeDecisionOverrideAnnotationPayload {
  override_type: string
  reason_category: OverrideReasonCategory
  reason_text: string
  confidence: OverrideConfidence
  was_intentional: boolean
  was_emotional: boolean
  should_remind_next_time: boolean
  lesson: string
  tags: string[]
}

export interface TradeDecisionOverrideAnnotation extends TradeDecisionOverrideAnnotationPayload {
  id: string
  decision_id: string
  symbol: string
  decision_date: string | null
  alignment_label: string | null
  behavior_tags: string[]
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface TradeDecisionOverrideAnnotationListResponse {
  items: TradeDecisionOverrideAnnotation[]
}

export interface TradeDecisionBehaviorInsight {
  pattern: string
  severity: 'low' | 'medium' | 'high'
  count: number
  rate: number
  estimated_cost: number
  symbols: string[]
  description: string
  suggestion: string
}

export interface TradeDecisionBehaviorCoachingHint {
  pattern: string
  severity: 'low' | 'medium' | 'high'
  message: string
  symbols: string[]
  source: string
  annotation_decision_id: string | null
}

export interface TradeDecisionBehaviorProfileItem {
  decision_id: string
  symbol: string
  decision_date: string | null
  final_action: string | null
  alignment_label: string
  behavior_tags: string[]
  estimated_opportunity_cost: number
  estimated_avoided_loss: number
  estimated_bad_override_cost: number
  estimated_good_override_value: number
  profile_contribution: number
  annotation: TradeDecisionOverrideAnnotation | null
}

export interface TradeDecisionBehaviorProfileSummary {
  version: string
  start_date: string | null
  end_date: string | null
  total_decisions: number
  evaluated_decisions: number
  alignment_rate: number
  manual_override_rate: number
  ignored_add_signal_rate: number
  ignored_reduce_signal_rate: number
  contradiction_rate: number
  over_execution_rate: number
  under_execution_rate: number
  premature_trim_rate: number
  good_override_rate: number
  bad_override_rate: number
  net_behavior_value: number
  estimated_opportunity_cost_total: number
  estimated_bad_override_cost_total: number
  estimated_good_override_value_total: number
  top_behavior_tags: TradeDecisionQualityTopItem[]
  top_reason_categories: TradeDecisionQualityTopItem[]
  top_symbols_with_bias: Array<TradeDecisionQualityTopItem & { estimated_cost?: number; top_tags?: TradeDecisionQualityTopItem[] }>
  behavior_risk_level: 'low' | 'medium' | 'high'
  dominant_behavior_patterns: TradeDecisionBehaviorInsight[]
  coaching_hints: TradeDecisionBehaviorCoachingHint[]
  generated_at: string
  data_limitations: string[]
}

export interface TradeDecisionBehaviorProfileResponse {
  summary: TradeDecisionBehaviorProfileSummary
  insights: TradeDecisionBehaviorInsight[]
  coaching_hints: TradeDecisionBehaviorCoachingHint[]
  items: TradeDecisionBehaviorProfileItem[]
}

export interface UserInvestmentPolicySummary {
  source: 'user_config' | 'default_template' | 'fallback' | string
  asset_role: string
  conviction: string
  user_preferred_min_position_pct: number | null
  user_preferred_target_position_pct: number | null
  user_preferred_max_position_pct: number | null
  current_position_pct: number | null
  gap_to_user_preferred_target_pct: number | null
  gap_to_user_preferred_max_pct: number | null
  user_preference_gap_label?: string
  enabled: boolean
  add_rules: string[]
  no_add_triggers: string[]
  sell_triggers: string[]
  hard_constraints: string[]
  soft_preferences: string[]
  notes: string
  ai_review_status: string
  ai_review_summary: string | null
  disclaimer: string
}

export interface AiPolicyAssessment {
  status?: 'evaluated' | 'fallback' | 'not_evaluated' | string
  ai_assessed_asset_role?: string | null
  ai_role_confidence?: string | null
  ai_recommended_min_position_pct?: number | null
  ai_recommended_target_position_pct?: number | null
  ai_recommended_max_position_pct?: number | null
  ai_recommended_target_position_range_pct?: number[] | null
  ai_position_stance?: string | null
  current_position_pct?: number | null
  gap_to_ai_target_pct?: number | null
  gap_to_ai_max_pct?: number | null
  challenge_level?: string | null
  challenge_reason?: string | null
  preference_alignment_summary?: string | null
  recommended_action_bias?: string | null
  risk_budget?: Record<string, unknown>
  key_reasons?: string[]
  key_risks?: string[]
  data_limitations?: string[]
  prompt_key?: string
  prompt_source?: string
  prompt_version?: string | null
}

export interface TradeDecisionResult {
  id: string
  decision_type: string
  symbol: string
  user_question: string | null
  overall_score: number
  rating: string
  action: string
  draft_action?: string | null
  risk_adjusted_action?: string | null
  final_action?: string | null
  action_change_reason?: string | null
  action_downgrade_chain?: Array<Record<string, unknown>>
  confidence: string
  decision_summary: string
  score_detail: Record<string, TradeDecisionScoreItem>
  position_advice: TradeDecisionPositionAdvice
  execution_plan: TradeDecisionExecutionPlan
  key_reasons: string[]
  major_risks: string[]
  review_warnings: string[]
  data_limitations: string[]
  evidence_used: string[]
  data_source_summary: Record<string, string>
  card_pack?: Record<string, unknown>
  asset_debate?: Record<string, unknown>
  trade_plan?: Record<string, unknown>
  risk_gate?: Record<string, unknown>
  user_investment_policy_summary?: UserInvestmentPolicySummary | null
  ai_policy_assessment?: AiPolicyAssessment
  behavior_profile_summary?: TradeDecisionBehaviorProfileCompactSummary | null
  personal_behavior_reminders?: PersonalBehaviorReminder[]
  decision_quality?: TradeDecisionQuality
  run_trace: AgentRunTraceItem[]
  metadata: Record<string, unknown>
  evidence_summary: Record<string, unknown>
  run_trace_summary: Record<string, unknown>
  fallback_used?: boolean
  fallback_reason?: string | null
  created_at: string
  updated_at: string
}

export interface TradeDecisionListResponse {
  items: TradeDecisionResult[]
}

export interface TradeDecisionHoldingItem {
  symbol: string
  normalized_symbol: string
  quantity: number | null
  avg_cost: number | null
  current_price: number | null
  market_value: number | null
  position_pct: number | null
  unrealized_pnl: number | null
  unrealized_pnl_pct: number | null
  latest_review_score: number | null
  latest_decision: string | null
  data_source: string
}

export interface TradeDecisionHoldingsResponse {
  items: TradeDecisionHoldingItem[]
}
