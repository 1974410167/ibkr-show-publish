export type UniverseType = 'holding' | 'watchlist' | 'candidate' | 'excluded'
export type AIThemeRole =
  | 'core_compute'
  | 'semiconductor'
  | 'data_center'
  | 'cloud_platform'
  | 'ai_infrastructure'
  | 'ai_application'
  | 'power_and_cooling'
  | 'memory_and_networking'
  | 'indirect_beneficiary'
  | 'non_ai'
  | 'fake_ai_story'
  | 'unknown'
export type UniversePriority = 'high' | 'medium' | 'low'
export type ScanFrequency = 'daily' | 'weekly' | 'monthly' | 'disabled'
export type DecisionFrequency = 'event_driven' | 'daily_if_triggered' | 'weekly' | 'monthly' | 'manual_only' | 'disabled'
export type UniverseSource = 'manual' | 'ibkr_holding_sync' | 'system_candidate'

export interface InvestmentConstitution {
  id: string
  constitution_version: string
  target_account_value_usd: number
  target_date: string
  starting_capital_usd: number
  primary_theme: string
  primary_theme_description: string
  primary_theme_buckets: string[]
  allow_future_deposits: boolean
  deposits_count_as_primary_driver: boolean
  core_time_horizon_years: number
  short_term_volatility_policy: string
  decision_principles: string[]
  forbidden_behaviors: string[]
  risk_constraints: Record<string, boolean>
  enabled: boolean
  created_at: string
  updated_at: string
  disclaimer: string
}

export type InvestmentConstitutionPayload = Omit<InvestmentConstitution, 'id' | 'created_at' | 'updated_at' | 'disclaimer'>

export interface UniverseSymbol {
  id: string
  symbol: string
  display_symbol: string
  name: string
  universe_type: UniverseType
  theme_tags: string[]
  ai_theme_role: AIThemeRole
  priority: UniversePriority
  enabled: boolean
  scan_frequency: ScanFrequency
  decision_frequency: DecisionFrequency
  max_llm_runs_per_week: number
  source: UniverseSource
  notes: string
  excluded_reason: string | null
  created_at: string
  updated_at: string
}

export type UniverseSymbolPayload = Omit<UniverseSymbol, 'id' | 'created_at' | 'updated_at'>

export interface UniverseSymbolListResponse {
  items: UniverseSymbol[]
}

export interface UniverseSyncHoldingsResponse {
  synced: UniverseSymbol[]
  skipped: string[]
  message: string
}

export interface UniverseListFilters {
  universe_type?: string
  enabled?: boolean | null
  priority?: string
  ai_theme_role?: string
  theme_tag?: string
  source?: string
}

export type WatchtowerRunType = 'manual' | 'scheduled' | 'backfill'
export type WatchtowerRunStatus = 'success' | 'partial_success' | 'failed'
export type WatchtowerItemStatus = 'normal' | 'watch' | 'attention_required' | 'decision_required'
export type WatchtowerSeverity = 'none' | 'low' | 'medium' | 'high'
export type WatchtowerNextStep = 'no_action' | 'keep_watch' | 'review_manually' | 'trigger_trade_decision'
export type WatchtowerDecisionTypeHint = 'holding_decision' | 'entry_decision'

export interface WatchtowerTriggerReason {
  code: string
  severity: WatchtowerSeverity
  message: string
  value: number | string | null
  threshold: number | string | null
  status: WatchtowerItemStatus | null
  decision_type_hint: WatchtowerDecisionTypeHint | null
}

export interface WatchtowerMetrics {
  last_price: number | null
  return_1d: number | null
  return_5d: number | null
  return_20d: number | null
  consecutive_up_days: number
  consecutive_down_days: number
  drawdown_from_20d_high: number | null
  drawdown_from_60d_high: number | null
  distance_to_52w_high: number | null
  distance_to_52w_low: number | null
  position_quantity: number | null
  position_value: number | null
  position_weight: number | null
  unrealized_pnl_pct: number | null
  data_points: number
}

export interface PortfolioWatchtowerItem {
  id: string
  run_id: string
  run_date: string
  symbol: string
  display_symbol: string
  name: string
  universe_type: UniverseType
  priority: UniversePriority
  enabled: boolean
  ai_theme_role: AIThemeRole
  theme_tags: string[]
  status: WatchtowerItemStatus
  severity: WatchtowerSeverity
  trigger_reasons: WatchtowerTriggerReason[]
  metrics: WatchtowerMetrics
  suggested_next_step: WatchtowerNextStep
  decision_candidate: boolean
  decision_type_hint: WatchtowerDecisionTypeHint | null
  scan_snapshot: Record<string, unknown>
  data_limitations: string[]
  created_at: string
  updated_at: string
}

export interface PortfolioWatchtowerRun {
  id: string
  run_date: string
  run_type: WatchtowerRunType
  status: WatchtowerRunStatus
  constitution_version: string
  universe_snapshot: Record<string, number>
  summary: Record<WatchtowerItemStatus, number>
  top_attention_symbols: string[]
  data_limitations: string[]
  created_at: string
  updated_at: string
}

export interface PortfolioWatchtowerRunDetail extends PortfolioWatchtowerRun {
  items: PortfolioWatchtowerItem[]
}

export interface PortfolioWatchtowerRunCreate {
  run_date?: string | null
  run_type: WatchtowerRunType
  universe_types?: UniverseType[] | null
  force_refresh: boolean
}

export interface PortfolioWatchtowerRunListResponse {
  items: PortfolioWatchtowerRun[]
}

export interface PortfolioWatchtowerSymbolHistoryResponse {
  items: PortfolioWatchtowerItem[]
}

export type AutoDecisionRunType = 'manual' | 'scheduled' | 'backfill'
export type AutoDecisionRunStatus = 'success' | 'partial_success' | 'failed' | 'skipped'
export type AutoDecisionSelectionStatus = 'selected' | 'skipped' | 'completed' | 'failed'

export interface PortfolioAutoDecisionBudget {
  max_decisions: number
  used_decisions: number
  skipped_by_budget: number
}

export interface PortfolioAutoDecisionSummary {
  selected: number
  completed: number
  failed: number
  skipped: number
}

export interface PortfolioAutoDecisionRun {
  id: string
  run_date: string
  run_type: AutoDecisionRunType
  source_watchtower_run_id: string
  status: AutoDecisionRunStatus
  constitution_version: string
  budget: PortfolioAutoDecisionBudget
  summary: PortfolioAutoDecisionSummary
  selected_symbols: string[]
  skipped_symbols: string[]
  data_limitations: string[]
  created_at: string
  updated_at: string
}

export interface PortfolioAutoDecisionItem {
  id: string
  run_id: string
  run_date: string
  source_watchtower_run_id: string
  source_watchtower_item_id: string
  symbol: string
  display_symbol: string
  universe_type: UniverseType
  ai_theme_role: AIThemeRole
  priority: UniversePriority
  watchtower_status: WatchtowerItemStatus
  watchtower_severity: WatchtowerSeverity
  trigger_reasons: WatchtowerTriggerReason[]
  selection_status: AutoDecisionSelectionStatus
  skip_reason: string | null
  decision_type: WatchtowerDecisionTypeHint | null
  decision_request: Record<string, unknown>
  decision_id: string | null
  decision_summary: Record<string, unknown>
  error_code: string | null
  error_message: string | null
  scan_snapshot: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface PortfolioAutoDecisionRunDetail extends PortfolioAutoDecisionRun {
  items: PortfolioAutoDecisionItem[]
}

export interface PortfolioAutoDecisionRunCreate {
  watchtower_run_id: string
  run_date?: string | null
  run_type: AutoDecisionRunType
  max_decisions: number
  force_refresh: boolean
  dry_run: boolean
}

export interface PortfolioAutoDecisionRunListResponse {
  items: PortfolioAutoDecisionRun[]
}

export interface PortfolioAutoDecisionSymbolHistoryResponse {
  items: PortfolioAutoDecisionItem[]
}

export type PortfolioReportType = 'manual' | 'scheduled' | 'backfill'
export type PortfolioReportStatus = 'success' | 'partial_success' | 'failed'
export type PortfolioHealthLevel = 'healthy' | 'watch' | 'attention_required' | 'high_risk'

export interface PortfolioGoalTracking {
  target_account_value_usd: number
  target_date: string
  current_total_equity_usd: number | null
  remaining_years: number | null
  required_annual_return: number | null
  current_path_status: 'on_track' | 'stretched' | 'off_track' | 'unknown'
  summary: string
}

export interface PortfolioAIThemeExposure {
  total_ai_exposure_pct: number | null
  core_ai_exposure_pct: number | null
  infrastructure_exposure_pct: number | null
  non_ai_exposure_pct: number | null
  unknown_exposure_pct: number | null
  fake_ai_story_exposure_pct: number | null
  assessment: 'aligned' | 'partially_aligned' | 'misaligned' | 'unknown'
}

export interface PortfolioConcentrationRisk {
  top1_weight: number | null
  top3_weight: number | null
  top5_weight: number | null
  single_name_risk_symbols: string[]
  assessment: 'low' | 'medium' | 'high'
}

export interface PortfolioCashStatus {
  cash_value: number | null
  cash_pct: number | null
  assessment: 'too_low' | 'reasonable' | 'too_high' | 'unknown'
  summary: string
}

export interface PortfolioAllocationGap {
  symbol: string
  display_symbol: string
  position_weight: number | null
  ai_theme_role: AIThemeRole
  gap_type: 'underweight' | 'overweight' | 'near_target' | 'unknown'
  gap_reason: string
  priority: UniversePriority
}

export interface PortfolioAttentionSymbol {
  symbol: string
  reason: string
  priority: UniversePriority
  next_step: 'review_trade_decision' | 'monitor' | 'wait' | 'manual_review' | 'no_action'
}

export interface PortfolioActionQueueItem {
  symbol: string
  queue_type: 'review_trade_decision' | 'monitor' | 'wait' | 'manual_review' | 'no_action'
  priority: UniversePriority
  reason: string
  linked_decision_id: string | null
}

export interface PortfolioManagerReport {
  id: string
  report_date: string
  report_type: PortfolioReportType
  status: PortfolioReportStatus
  constitution_version: string
  source_watchtower_run_id: string | null
  source_auto_decision_run_id: string | null
  portfolio_health_score: number
  portfolio_health_level: PortfolioHealthLevel
  goal_tracking: PortfolioGoalTracking
  ai_theme_exposure: PortfolioAIThemeExposure
  concentration_risk: PortfolioConcentrationRisk
  cash_status: PortfolioCashStatus
  allocation_gaps: PortfolioAllocationGap[]
  top_attention_symbols: PortfolioAttentionSymbol[]
  action_queue: PortfolioActionQueueItem[]
  summary: string
  next_steps: string[]
  data_limitations: string[]
  created_at: string
  updated_at: string
}

export interface PortfolioManagerReportGenerateRequest {
  report_date?: string | null
  report_type: PortfolioReportType
  watchtower_run_id?: string | null
  auto_decision_run_id?: string | null
}

export interface PortfolioManagerReportListResponse {
  items: PortfolioManagerReport[]
}

export type PortfolioEvaluationSourceType = 'watchtower_item' | 'auto_decision_item' | 'portfolio_report'
export type PortfolioEvaluationHorizon = '1d' | '5d' | '20d' | '60d' | '120d' | '1y'
export type PortfolioPriceDataStatus = 'ok' | 'partial' | 'missing' | 'pending'
export type PortfolioEvaluationLabel =
  | 'useful_attention'
  | 'false_positive'
  | 'missed_opportunity'
  | 'good_action'
  | 'bad_action'
  | 'risk_avoided'
  | 'pending'
  | 'inconclusive'

export interface PortfolioEvaluationResult {
  id: string
  evaluation_date: string
  source_type: PortfolioEvaluationSourceType
  source_id: string
  source_run_id: string | null
  symbol: string | null
  display_symbol: string | null
  horizon: PortfolioEvaluationHorizon
  horizon_days: number
  source_date: string
  source_status: string | null
  source_action: string | null
  source_snapshot: Record<string, unknown>
  price_data_status: PortfolioPriceDataStatus
  start_price: number | null
  end_price: number | null
  forward_return: number | null
  max_drawdown: number | null
  max_runup: number | null
  benchmark_symbol: string
  benchmark_return: number | null
  benchmark_relative_return: number | null
  evaluation_label: PortfolioEvaluationLabel
  evaluation_reason: string
  metric_summary: Record<string, unknown>
  data_limitations: string[]
  created_at: string
  updated_at: string
}

export interface PortfolioEvaluationSummary {
  generated_at: string
  lookback_days: number
  horizons: PortfolioEvaluationHorizon[]
  total_results: number
  pending: number
  completed: number
  by_source_type: Record<string, number>
  by_label: Record<string, number>
  watchtower: Record<string, number>
  auto_decision: Record<string, number>
  portfolio_report: Record<string, number>
  data_limitations: string[]
}

export interface PortfolioEvaluationRunRequest {
  evaluation_date?: string | null
  source_types?: PortfolioEvaluationSourceType[] | null
  horizons?: PortfolioEvaluationHorizon[] | null
  lookback_days: number
  benchmark_symbol: string
  limit: number
}

export interface PortfolioEvaluationRunResponse {
  created_or_updated_count: number
  pending_count: number
  completed_count: number
  summary: PortfolioEvaluationSummary
  data_limitations: string[]
}

export interface PortfolioEvaluationResultListResponse {
  items: PortfolioEvaluationResult[]
}

export interface PortfolioEvaluationSymbolHistoryResponse {
  items: PortfolioEvaluationResult[]
}

export type PortfolioImprovementReportType = 'manual' | 'scheduled' | 'backfill'
export type PortfolioImprovementReportStatus = 'success' | 'partial_success' | 'failed'
export type PortfolioImprovementSeverity = 'low' | 'medium' | 'high'
export type PortfolioImprovementConfidence = 'low' | 'medium' | 'high'
export type PortfolioImprovementCandidateStatus = 'proposed' | 'accepted' | 'rejected' | 'implemented' | 'archived'
export type PortfolioImprovementCandidateType =
  | 'watchtower_trigger_rule'
  | 'auto_decision_selector'
  | 'portfolio_review_rule'
  | 'data_quality'
  | 'trade_decision_prompt_context'
  | 'risk_gate_review'
  | 'universe_management'
  | 'evaluation_design'

export interface PortfolioImprovementEvidenceSummary {
  sample_size: number
  horizons: string[]
  source_type: string
  labels: Record<string, number>
  metrics: Record<string, number | string | null>
  example_result_ids: string[]
}

export interface PortfolioImprovementCandidate {
  id: string
  candidate_type: PortfolioImprovementCandidateType
  title: string
  severity: PortfolioImprovementSeverity
  confidence: PortfolioImprovementConfidence
  requires_human_approval: boolean
  status: PortfolioImprovementCandidateStatus
  affected_module: string
  affected_rule_or_component: string
  affected_versions: Record<string, string>
  evidence_summary: PortfolioImprovementEvidenceSummary
  suggested_change: string
  expected_impact: string
  risk_of_change: string
  human_review_notes: string
  created_at: string
  updated_at: string
}

export interface PortfolioImprovementReport {
  id: string
  report_date: string
  report_type: PortfolioImprovementReportType
  status: PortfolioImprovementReportStatus
  lookback_days: number
  horizons: PortfolioEvaluationHorizon[]
  source_evaluation_summary: Record<string, unknown>
  pattern_summary: Record<string, number>
  improvement_candidates: PortfolioImprovementCandidate[]
  recommendation_summary: string
  data_limitations: string[]
  created_at: string
  updated_at: string
}

export interface PortfolioImprovementGenerateRequest {
  report_date?: string | null
  report_type: PortfolioImprovementReportType
  lookback_days: number
  horizons?: PortfolioEvaluationHorizon[] | null
  min_sample_size: number
}

export interface PortfolioImprovementReportListResponse {
  items: PortfolioImprovementReport[]
}

export type PortfolioDailyLoopRunType = 'manual' | 'scheduled' | 'backfill'
export type PortfolioDailyLoopStatus = 'success' | 'partial_success' | 'failed' | 'running' | 'cancelled'
export type PortfolioDailyLoopStepName = 'sync_holdings' | 'watchtower' | 'auto_decision' | 'portfolio_report' | 'evaluation' | 'improvement'
export type PortfolioDailyLoopStepStatus = 'success' | 'skipped' | 'failed' | 'running'

export interface PortfolioDailyLoopOptions {
  sync_holdings: boolean
  run_watchtower: boolean
  run_auto_decision: boolean
  generate_portfolio_report: boolean
  run_evaluation: boolean
  generate_improvement_report: boolean
  dry_run_auto_decision: boolean
  max_auto_decisions: number
  force_refresh_auto_decision: boolean
  evaluation_horizons: PortfolioEvaluationHorizon[]
  evaluation_lookback_days: number
  improvement_horizons: PortfolioEvaluationHorizon[]
  improvement_lookback_days: number
  improvement_min_sample_size: number
}

export interface PortfolioDailyLoopStep {
  step: PortfolioDailyLoopStepName
  status: PortfolioDailyLoopStepStatus
  started_at: string | null
  completed_at: string | null
  duration_ms: number | null
  summary: Record<string, unknown>
  run_id: string | null
  error_code: string | null
  error_message: string | null
}

export interface PortfolioDailyLoopRun {
  id: string
  run_date: string
  run_type: PortfolioDailyLoopRunType
  status: PortfolioDailyLoopStatus
  task_id: string | null
  started_at: string | null
  completed_at: string | null
  duration_ms: number | null
  options: PortfolioDailyLoopOptions
  steps: PortfolioDailyLoopStep[]
  linked_run_ids: Record<string, unknown>
  summary: Record<string, unknown>
  data_limitations: string[]
  error_code: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface PortfolioDailyLoopRunCreate extends Partial<PortfolioDailyLoopOptions> {
  run_date?: string | null
  run_type: PortfolioDailyLoopRunType
  background: boolean
}

export interface PortfolioDailyLoopRunResponse {
  task_id: string | null
  run_id: string
  background: boolean
  run: PortfolioDailyLoopRun | null
  message: string
}

export interface PortfolioDailyLoopRunListResponse {
  items: PortfolioDailyLoopRun[]
}

export interface PortfolioDailyLoopScheduleStatus {
  enabled: boolean
  schedule_time: string
  schedule_timezone: string
  next_run_hint: string | null
  max_auto_decisions: number
  dry_run_auto_decision: boolean
  force_refresh_auto_decision: boolean
  run_evaluation: boolean
  generate_improvement_report: boolean
}

export interface PortfolioDailyLoopScheduledRunRequest {
  run_date?: string | null
  force?: boolean
  background?: boolean
}

export interface PortfolioDailyLoopScheduledRunResponse {
  skipped: boolean
  reason: string | null
  existing_run_id: string | null
  task_id: string | null
  run_id: string | null
  background: boolean
  run: PortfolioDailyLoopRun | null
  message: string
}

export type PortfolioActionAlertStatus = 'pending' | 'sent' | 'skipped' | 'failed'
export type PortfolioActionAlertType = 'add_position_review' | 'entry_position_review' | 'reduce_position_review' | 'risk_review'
export type PortfolioActionDirection = 'consider_add' | 'consider_entry' | 'consider_reduce' | 'review_risk'
export type PortfolioActionAlertUrgency = 'low' | 'medium' | 'high'
export type PortfolioActionAlertConfidence = 'low' | 'medium' | 'high'

export interface PortfolioActionAlert {
  id: string
  run_date: string
  status: PortfolioActionAlertStatus
  alert_type: PortfolioActionAlertType
  symbol: string
  display_symbol: string
  title: string
  action_direction: PortfolioActionDirection
  urgency: PortfolioActionAlertUrgency
  confidence: PortfolioActionAlertConfidence
  reason_summary: string[]
  decision_summary: Record<string, unknown>
  portfolio_context: Record<string, unknown>
  linked_ids: Record<string, unknown>
  suggested_user_action: string
  not_an_order: boolean
  email_subject: string | null
  email_sent_at: string | null
  email_error: string | null
  created_at: string
  updated_at: string
}

export interface PortfolioActionAlertListResponse {
  items: PortfolioActionAlert[]
}

export interface PortfolioActionAlertRunResult {
  daily_loop_run_id: string
  run_date: string | null
  alerts_created: number
  alerts_sent: number
  alerts_skipped: number
  alerts_failed: number
  email_enabled: boolean
  data_limitations: string[]
}
