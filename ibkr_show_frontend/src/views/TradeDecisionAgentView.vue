<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import SymbolInput from '@/components/SymbolInput.vue'
import { formatLocalDateTime } from '@/utils/dateTime'

import {
  deleteTradeDecisionOverrideAnnotation,
  fetchTradeDecisionBehaviorProfile,
  fetchTradeDecisionDetail,
  fetchTradeDecisionAlignmentList,
  fetchTradeDecisionBacktestDetail,
  fetchTradeDecisionHoldings,
  fetchTradeDecisionOverrideAnnotation,
  fetchRecentTradeDecisions,
  fetchTradeDecisionHealth,
  fetchTradeDecisionOutcomeList,
  fetchTradeDecisionQualitySummary,
  fetchTradeDecisionTasks,
  saveTradeDecisionOverrideAnnotation,
  startTradeDecisionTask,
} from '@/api/tradeDecision'
import AgentEvidencePanel from '@/components/AgentEvidencePanel.vue'
import AgentTaskGraph from '@/components/AgentTaskGraph.vue'
import ErrorBlock from '@/components/ErrorBlock.vue'
import LoadingBlock from '@/components/LoadingBlock.vue'
import SymbolAnalysisPanel from '@/components/SymbolAnalysisPanel.vue'
import SymbolAnalysisResults from '@/components/SymbolAnalysisResults.vue'
import type { AgentTask } from '@/types/agentTasks'
import type { SymbolAnalysisSnapshot, SymbolAnalysisTask } from '@/types/symbolAnalysis'
import type {
  AiPolicyAssessment,
  OverrideConfidence,
  OverrideReasonCategory,
  TradeDecisionBehaviorProfileResponse,
  TradeDecisionExecutionAlignmentListResponse,
  TradeDecisionExecutionAlignmentItem,
  TradeDecisionBacktestResponse,
  TradeDecisionHoldingItem,
  TradeDecisionHealth,
  TradeDecisionOutcomeListResponse,
  TradeDecisionQuality,
  TradeDecisionQualityCheck,
  TradeDecisionQualitySummary,
  TradeDecisionResult,
  UserInvestmentPolicySummary,
} from '@/types/tradeDecision'

const loading = ref(true)
const errorMessage = ref('')
const generatingKey = ref('')
const health = ref<TradeDecisionHealth | null>(null)
const currentHoldings = ref<TradeDecisionHoldingItem[]>([])
const recentDecisions = ref<TradeDecisionResult[]>([])
const qualitySummary = ref<TradeDecisionQualitySummary | null>(null)
const qualitySummaryLoading = ref(false)
const qualitySummaryError = ref('')
const outcomeReplay = ref<TradeDecisionOutcomeListResponse | null>(null)
const outcomeReplayLoading = ref(false)
const outcomeReplayError = ref('')
const backtest = ref<TradeDecisionBacktestResponse | null>(null)
const backtestLoading = ref(false)
const backtestError = ref('')
const alignment = ref<TradeDecisionExecutionAlignmentListResponse | null>(null)
const alignmentLoading = ref(false)
const alignmentError = ref('')
const behaviorProfile = ref<TradeDecisionBehaviorProfileResponse | null>(null)
const behaviorProfileLoading = ref(false)
const behaviorProfileError = ref('')
const annotationDialogVisible = ref(false)
const annotationDialogError = ref('')
const annotationSaving = ref(false)
const annotationTarget = ref<TradeDecisionExecutionAlignmentItem | null>(null)
const manualAnnotationDecisionIds = ref<Set<string>>(new Set())
const secondaryDecisionPanelsRequested = ref(false)
const selectedDecision = ref<TradeDecisionResult | null>(null)
const taskItems = ref<AgentTask[]>([])
const expandedTaskId = ref<string | null>(null)
const showAllRecentDecisions = ref(false)
const now = ref(Date.now())
const activeWorkspace = ref<'decision' | 'research'>('decision')
const symbolAnalysisTask = ref<SymbolAnalysisTask | null>(null)
const symbolAnalysisState = ref<SymbolAnalysisSnapshot>({
  loading: false,
  errorMessage: '',
  singleFinancials: null,
  comparison: null,
  aiAdvice: null,
  aiAdviceLoading: false,
  aiAdviceError: '',
})
let taskTimer: number | undefined

const entryForm = reactive({
  symbol: '',
})

const backtestForm = reactive({
  days: 180,
  initial_cash: 100000,
  benchmark_symbol: 'SPY',
  execution_timing: 'next_close',
  include_costs: true,
})

const annotationForm = reactive({
  override_type: 'manual_override',
  reason_category: 'other' as OverrideReasonCategory,
  reason_text: '',
  confidence: 'medium' as OverrideConfidence,
  was_intentional: true,
  was_emotional: false,
  should_remind_next_time: false,
  lesson: '',
  tags_text: '',
})

const scoreDimensions: readonly { key: string; label: string; fullWidth?: boolean }[] = [
  { key: 'fundamental_quality_score', label: '公司质量' },
  { key: 'valuation_score', label: '估值质量' },
  { key: 'trend_score', label: '趋势强度' },
  { key: 'account_fit_score', label: '账户适配' },
  { key: 'risk_reward_score', label: '风险收益' },
  { key: 'review_constraint_score', label: '复盘约束' },
  { key: 'event_catalyst_score', label: '事件催化', fullWidth: true },
]

const actionLabels: Record<string, string> = {
  add: '加仓',
  add_small: '小幅加仓',
  add_batch: '分批加仓',
  hold: '持有',
  reduce: '减仓',
  reduce_batch: '分批减仓',
  sell: '清仓',
  wait: '等待',
  avoid: '回避',
  watchlist: '观察',
  hold_no_add: '持有不加仓',
  add_on_pullback: '回调加仓',
  add_right_side: '右侧加仓',
  trim_on_rebound: '反弹减仓',
  reduce_now: '立即减仓',
  sell_thesis_broken: '假设破坏清仓',
  panic_blocked: '恐慌交易拦截',
}

const ratingLabels: Record<string, string> = {
  strong_buy_or_hold: '强买/强持',
  positive: '积极',
  neutral: '中性',
  negative: '谨慎',
}

const decisionTypeLabels: Record<string, string> = {
  trade_decision: '交易决策',
  entry_decision: '未持仓标的',
  holding_decision: '已有持仓标的',
}

const qualityCheckLabels: Record<string, string> = {
  graph_integrity: '图结构完整性',
  data_source_integrity: '数据来源边界',
  structured_output_health: '结构化输出健康度',
  asset_action_consistency: '标的观点/动作一致性',
  position_consistency: '仓位一致性',
  risk_gate_integrity: 'Risk Gate 完整性',
  risk_reward_source_integrity: '风险收益来源',
  evidence_card_completeness: '证据卡完整性',
  output_contract_integrity: '输出契约完整性',
}

const healthTone = computed(() => (health.value?.llm_configured ? 'p-tag--positive' : 'p-tag--negative'))
const visibleTasks = computed(() => {
  const active = taskItems.value.filter((t) => t.status === 'queued' || t.status === 'running')
  const done = taskItems.value.filter((t) => t.status === 'completed' || t.status === 'failed')
  return [...active, ...done.slice(0, 2)]
})
const activeTaskCount = computed(() => taskItems.value.filter((task) => task.status === 'queued' || task.status === 'running').length)
const isGenerating = computed(() => activeTaskCount.value > 0 || generatingKey.value !== '')
const hasRunnerItems = computed(() => visibleTasks.value.length > 0 || Boolean(symbolAnalysisTask.value))
const recentDecisionVisibleLimit = 6
const visibleRecentDecisions = computed(() => (showAllRecentDecisions.value ? recentDecisions.value : recentDecisions.value.slice(0, recentDecisionVisibleLimit)))
const hiddenRecentDecisionCount = computed(() => Math.max(0, recentDecisions.value.length - recentDecisionVisibleLimit))
const qualityDistributionKeys = ['excellent', 'good', 'warning', 'poor', 'unknown']
const recentQualityTrend = computed(() => (qualitySummary.value?.recent_trend || []).slice(-10).reverse())
const outcomeSummary = computed(() => outcomeReplay.value?.summary || null)
const outcomeItems = computed(() => (outcomeReplay.value?.items || []).slice(0, 12))
const backtestSummary = computed(() => backtest.value?.summary || null)
const alignmentSummary = computed(() => alignment.value?.summary || null)
const alignmentItems = computed(() => (alignment.value?.items || []).slice(0, 12))
const behaviorProfileSummary = computed(() => behaviorProfile.value?.summary || null)
const behaviorProfileItems = computed(() => behaviorProfile.value?.items || [])
const behaviorAnnotationByDecision = computed(() => {
  const lookup = new Map<string, boolean>()
  behaviorProfileItems.value.forEach((item) => {
    if (item.annotation) lookup.set(item.decision_id, true)
  })
  return lookup
})
const hasAnnotationForDecision = (decisionId: string): boolean => behaviorAnnotationByDecision.value.has(decisionId) || manualAnnotationDecisionIds.value.has(decisionId)
const behaviorReminderHints = computed(() => (behaviorProfile.value?.coaching_hints || []).filter((item) => item.source === 'manual_annotation').slice(0, 5))
const backtestCurvePreview = computed(() => {
  const curve = backtest.value?.equity_curve || []
  if (curve.length <= 16) return curve
  const step = Math.ceil(curve.length / 16)
  return curve.filter((_, index) => index % step === 0).slice(0, 16)
})

function hasPosition(symbol: string): TradeDecisionHoldingItem | undefined {
  return currentHoldings.value.find((h) => h.symbol === symbol.trim().toUpperCase())
}

function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return '--'
  return new Intl.NumberFormat('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value)
}

function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--'
  return `${formatNumber(value * 100, 2)}%`
}

function formatSignedPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--'
  if (value === 0) return '0.00%'
  return `${value > 0 ? '+' : ''}${formatNumber(value * 100, 2)}%`
}

function formatMoney(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--'
  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value)
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function actionLabel(value: string | null | undefined): string {
  if (!value) return '--'
  return actionLabels[value] ?? value
}

function ratingLabel(value: string): string {
  return ratingLabels[value] ?? value
}

function decisionTypeLabel(value: string): string {
  return decisionTypeLabels[value] ?? value
}

function stanceLabel(value: unknown): string {
  const labels: Record<string, string> = {
    bullish: '看多',
    neutral: '中性',
    bearish: '看空',
    insufficient_data: '数据不足',
  }
  return labels[String(value || '')] ?? '--'
}

function winnerLabel(value: unknown): string {
  const labels: Record<string, string> = {
    bull: '多头占优',
    bear: '空头占优',
    balanced: '多空均衡',
    insufficient_data: '证据不足',
  }
  return labels[String(value || '')] ?? '--'
}

function reasonTypeLabel(value: unknown): string {
  const labels: Record<string, string> = {
    asset_view: '标的观点',
    asset_view_and_account_fit: '标的观点与账户适配',
    portfolio_risk_constraint: '组合风险约束',
    insufficient_data: '数据不足',
    event_risk_window: '事件风险窗口',
    thesis_broken: '假设破坏',
    panic_blocked: '恐慌交易拦截',
    no_action: '无需行动',
  }
  return labels[String(value || '')] ?? '--'
}

function policySourceLabel(value: string | undefined): string {
  const labels: Record<string, string> = {
    user_config: '用户配置',
    default_template: '默认模板',
    fallback: 'fallback 模板',
  }
  return labels[String(value || '')] ?? (value || '--')
}

function userPreferenceGapLabel(value: string | undefined): string {
  const labels: Record<string, string> = {
    below_user_preference: '低于我的偏好目标',
    near_user_preference: '接近我的偏好目标',
    above_user_preference: '高于我的偏好目标',
    unknown: '偏好目标未知',
  }
  return labels[String(value || '')] ?? (value || '--')
}

function aiPolicyStatusLabel(value: string | undefined | null): string {
  const labels: Record<string, string> = {
    evaluated: '已评估',
    fallback: '评估失败 fallback',
    not_evaluated: '未评估',
  }
  return labels[String(value || '')] ?? (value || '--')
}

function aiPositionStanceLabel(value: string | undefined | null): string {
  const labels: Record<string, string> = {
    no_position: '未持仓',
    underweight: '低于 AI 目标',
    near_target: '接近 AI 目标',
    overweight: '高于 AI 目标',
    over_limit: '超过 AI 上限',
    forbidden: '不应持有',
    unknown: '未知',
  }
  return labels[String(value || '')] ?? (value || '--')
}

function aiChallengeLabel(value: string | undefined | null): string {
  const labels: Record<string, string> = {
    agree: '认可用户偏好',
    mild_disagreement: '温和反驳',
    strong_disagreement: '强烈反驳',
    risk_warning: '风险警告',
    not_evaluated: '未评估',
  }
  return labels[String(value || '')] ?? (value || '--')
}

function actionBiasLabel(value: string | undefined | null): string {
  const labels: Record<string, string> = {
    allow_add: '允许加仓',
    prefer_pullback_add: '偏好回调加仓',
    hold_no_add: '持有不加仓',
    prefer_reduce: '偏好减仓',
    avoid: '回避',
    unknown: '未知',
  }
  return labels[String(value || '')] ?? (value || '--')
}

function actionGroupLabel(value: string | undefined | null): string {
  const labels: Record<string, string> = {
    add_like: '加仓类',
    hold_like: '持有/等待类',
    reduce_like: '减仓类',
    unknown: '未知',
  }
  return labels[String(value || '')] ?? (value || '--')
}

function outcomeLabel(value: string | undefined | null): string {
  const labels: Record<string, string> = {
    good_action: '有效动作',
    bad_add: '加仓后承压',
    missed_upside: '错过上涨',
    avoided_loss: '避开下跌',
    sold_too_early: '卖早了',
    neutral_add: '中性加仓',
    neutral_hold: '中性持有',
    neutral_reduce: '中性减仓',
    pending: '等待数据',
  }
  return labels[String(value || '')] ?? (value || '--')
}

function outcomeClass(value: string | undefined | null): string {
  if (['good_action', 'avoided_loss'].includes(String(value || ''))) return 'p-tag--positive'
  if (['bad_add', 'missed_upside', 'sold_too_early'].includes(String(value || ''))) return 'p-tag--negative'
  if (String(value || '') === 'pending') return 'p-tag--warning'
  return 'p-tag--accent'
}

function executionTimingLabel(value: string | undefined | null): string {
  const labels: Record<string, string> = {
    next_close: '次日收盘',
    same_close: '当日收盘',
    next_open: '次日开盘',
  }
  return labels[String(value || '')] ?? (value || '--')
}

function tradeSideLabel(value: string | undefined | null): string {
  const labels: Record<string, string> = {
    buy: '买入',
    sell: '卖出',
    none: '未交易',
  }
  return labels[String(value || '')] ?? (value || '--')
}

function alignmentLabel(value: string | undefined | null): string {
  const labels: Record<string, string> = {
    followed: '已跟随',
    partially_followed: '部分跟随',
    ignored: '忽略建议',
    contradicted: '反向/冲突',
    over_executed: '执行过重',
    no_trade_expected: '符合不交易',
    unknown: '未知',
  }
  return labels[String(value || '')] ?? (value || '--')
}

function alignmentClass(value: string | undefined | null): string {
  if (['followed', 'no_trade_expected'].includes(String(value || ''))) return 'p-tag--positive'
  if (['ignored', 'partially_followed', 'over_executed'].includes(String(value || ''))) return 'p-tag--warning'
  if (String(value || '') === 'contradicted') return 'p-tag--negative'
  return 'p-tag--accent'
}

function behaviorTagLabel(value: string): string {
  const labels: Record<string, string> = {
    ignored_add_signal: '忽略加仓信号',
    ignored_reduce_signal: '忽略减仓信号',
    manual_contrarian_buy: '逆建议买入',
    manual_contrarian_sell: '逆建议卖出',
    over_sized_execution: '执行过重',
    under_sized_execution: '执行偏轻',
    panic_sell_against_gate: '恐慌卖出',
    premature_trim: '过早卖出',
    good_override: '好 override',
    bad_override: '坏 override',
    good_discipline: '纪律执行有效',
    bad_follow: '跟随但结果差',
    emotion_driven_trading: '情绪驱动交易',
    harmful_manual_override: '有害 override',
    contrarian_buy_loss: '逆向买入亏损',
  }
  return labels[value] ?? value
}

function reasonCategoryLabel(value: string): string {
  const labels: Record<string, string> = {
    emotion: '情绪',
    capital_constraint: '资金限制',
    external_information: '外部信息',
    disagree_with_agent: '不同意 Agent',
    risk_control: '主动风控',
    forgot: '忘记执行',
    execution_issue: '执行问题',
    tax_or_cashflow: '税务/现金流',
    other: '其他',
  }
  return labels[value] ?? value
}

function behaviorRiskLabel(value: string | undefined | null): string {
  const labels: Record<string, string> = {
    low: '低',
    medium: '中',
    high: '高',
  }
  return labels[String(value || '')] ?? '--'
}

function behaviorRiskClass(value: string | undefined | null): string {
  if (value === 'low') return 'p-tag--positive'
  if (value === 'high') return 'p-tag--negative'
  return 'p-tag--warning'
}

function reminderSeverityClass(value: string | undefined | null): string {
  if (value === 'high') return 'p-tag--negative'
  if (value === 'medium') return 'p-tag--warning'
  return 'p-tag--accent'
}

function statKeyLabel(value: string): string {
  return value
    .replace('final_action:', '动作：')
    .replace('action_group:', '分组：')
    .replace('add_like', '加仓类')
    .replace('hold_like', '持有/等待类')
    .replace('reduce_like', '减仓类')
}

function curvePointHeight(value: number | null | undefined): string {
  if (value === null || value === undefined) return '4px'
  const pct = Math.max(6, Math.min(100, 50 + value * 240))
  return `${pct}%`
}

function finalActionAlignmentLabel(decision: TradeDecisionResult | null, assessment: AiPolicyAssessment | null): string {
  if (!decision || !assessment || assessment.status !== 'evaluated') return '未评估'
  const finalAction = decision.final_action || decision.action
  const bias = assessment.recommended_action_bias
  if (bias === 'allow_add' && ['add', 'add_small', 'add_batch', 'add_on_pullback', 'add_right_side'].includes(finalAction)) return '一致'
  if (bias === 'prefer_pullback_add' && finalAction === 'add_on_pullback') return '一致'
  if (['hold_no_add', 'avoid'].includes(String(bias)) && ['hold', 'hold_no_add', 'wait', 'watchlist', 'avoid', 'panic_blocked'].includes(finalAction)) return '一致'
  if (decision.action_downgrade_chain?.length) return '被风控降级'
  if (['hold', 'hold_no_add', 'wait', 'watchlist'].includes(finalAction) && ['underweight', 'no_position'].includes(String(assessment.ai_position_stance))) return '过度保守待复核'
  return '需复核'
}

function formatPctRange(value: number[] | null | undefined): string {
  if (!Array.isArray(value) || value.length < 2) return '--'
  return `${formatPct(value[0])} - ${formatPct(value[1])}`
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function asStringList(value: unknown, limit = 8): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean).slice(0, limit) : []
}

function nestedRecord(record: Record<string, unknown>, key: string): Record<string, unknown> {
  return asRecord(record[key])
}

function assetDebateFor(decision: TradeDecisionResult | null): Record<string, unknown> {
  if (!decision) return {}
  const direct = asRecord(decision.asset_debate)
  if (Object.keys(direct).length) return direct
  return nestedRecord(asRecord(decision.card_pack), 'debate_judge_card')
}

function tradePlanFor(decision: TradeDecisionResult | null): Record<string, unknown> {
  if (!decision) return {}
  const direct = asRecord(decision.trade_plan)
  if (Object.keys(direct).length) return direct
  return nestedRecord(asRecord(decision.card_pack), 'trade_plan_card')
}

function riskGateFor(decision: TradeDecisionResult | null): Record<string, unknown> {
  return asRecord(decision?.risk_gate)
}

function decisionQuality(decision: TradeDecisionResult | null | undefined): TradeDecisionQuality {
  return decision?.decision_quality || {}
}

function hasDecisionQuality(decision: TradeDecisionResult | null | undefined): boolean {
  return Object.keys(decisionQuality(decision)).length > 0
}

function qualityScore(decision: TradeDecisionResult | null | undefined): number | null {
  const score = decisionQuality(decision).score
  return typeof score === 'number' ? score : null
}

function qualityLevelLabel(level: unknown): string {
  const labels: Record<string, string> = {
    excellent: '优秀',
    good: '良好',
    warning: '警告',
    poor: '较差',
  }
  const value = String(level || '')
  return labels[value] ?? value
}

function qualityLevelClass(level: unknown): string {
  const classes: Record<string, string> = {
    excellent: 'p-tag--positive',
    good: 'p-tag--positive',
    warning: 'p-tag--warning',
    poor: 'p-tag--negative',
  }
  return classes[String(level || '')] ?? 'p-tag--accent'
}

function qualityPassedLabel(passed: boolean | null | undefined): string {
  if (passed === true) return '通过'
  if (passed === false) return '未通过'
  return '未评估'
}

function qualityPassedClass(passed: boolean | null | undefined): string {
  if (passed === true) return 'p-tag--positive'
  if (passed === false) return 'p-tag--negative'
  return 'p-tag--accent'
}

function visibleQualityChecks(decision: TradeDecisionResult | null | undefined): Array<[string, TradeDecisionQualityCheck]> {
  return Object.entries(decisionQuality(decision).checks || {}).slice(0, 9)
}

function shortQualityList(items: unknown, limit = 4): string[] {
  return Array.isArray(items) ? items.map((item) => String(item)).filter(Boolean).slice(0, limit) : []
}

function topQualityItems(items: unknown, limit: number): Array<{ key: string; count: number }> {
  return Array.isArray(items)
    ? items
      .map((item) => asRecord(item))
      .map((item) => ({ key: String(item.key || ''), count: asNumber(item.count) ?? 0 }))
      .filter((item) => item.key)
      .slice(0, limit)
    : []
}

function distributionCount(level: string): number {
  return qualitySummary.value?.level_distribution?.[level] ?? 0
}

async function loadQualitySummary(): Promise<void> {
  qualitySummaryLoading.value = true
  qualitySummaryError.value = ''
  try {
    qualitySummary.value = await fetchTradeDecisionQualitySummary({ limit: 200 })
  } catch (error) {
    qualitySummary.value = null
    qualitySummaryError.value = error instanceof Error ? error.message : '加载决策质量看板失败'
  } finally {
    qualitySummaryLoading.value = false
  }
}

async function loadOutcomeReplay(): Promise<void> {
  outcomeReplayLoading.value = true
  outcomeReplayError.value = ''
  try {
    outcomeReplay.value = await fetchTradeDecisionOutcomeList({ limit: 200, days: 180 })
  } catch (error) {
    outcomeReplay.value = null
    outcomeReplayError.value = error instanceof Error ? error.message : '加载回放评估失败'
  } finally {
    outcomeReplayLoading.value = false
  }
}

async function loadBacktest(): Promise<void> {
  backtestLoading.value = true
  backtestError.value = ''
  try {
    backtest.value = await fetchTradeDecisionBacktestDetail({
      days: backtestForm.days,
      initial_cash: backtestForm.initial_cash,
      benchmark_symbol: backtestForm.benchmark_symbol.trim() || 'SPY',
      execution_timing: backtestForm.execution_timing,
      include_costs: backtestForm.include_costs ? 1 : 0,
    })
  } catch (error) {
    backtest.value = null
    backtestError.value = error instanceof Error ? error.message : '加载虚拟组合回测失败'
  } finally {
    backtestLoading.value = false
  }
}

async function loadAlignment(): Promise<void> {
  alignmentLoading.value = true
  alignmentError.value = ''
  try {
    alignment.value = await fetchTradeDecisionAlignmentList({ days: 180, match_window_days: 5, limit: 300 })
  } catch (error) {
    alignment.value = null
    alignmentError.value = error instanceof Error ? error.message : '加载真实执行对齐失败'
  } finally {
    alignmentLoading.value = false
  }
}

async function loadBehaviorProfile(): Promise<void> {
  behaviorProfileLoading.value = true
  behaviorProfileError.value = ''
  try {
    behaviorProfile.value = await fetchTradeDecisionBehaviorProfile({ days: 180, limit: 300 })
  } catch (error) {
    behaviorProfile.value = null
    behaviorProfileError.value = error instanceof Error ? error.message : '加载交易行为画像失败'
  } finally {
    behaviorProfileLoading.value = false
  }
}

function resetAnnotationForm(): void {
  annotationForm.override_type = 'manual_override'
  annotationForm.reason_category = 'other'
  annotationForm.reason_text = ''
  annotationForm.confidence = 'medium'
  annotationForm.was_intentional = true
  annotationForm.was_emotional = false
  annotationForm.should_remind_next_time = false
  annotationForm.lesson = ''
  annotationForm.tags_text = ''
}

async function openAnnotationDialog(item: TradeDecisionExecutionAlignmentItem): Promise<void> {
  annotationTarget.value = item
  annotationDialogVisible.value = true
  annotationDialogError.value = ''
  resetAnnotationForm()
  try {
    const annotation = await fetchTradeDecisionOverrideAnnotation(item.decision_id)
    manualAnnotationDecisionIds.value = new Set([...manualAnnotationDecisionIds.value, item.decision_id])
    annotationForm.override_type = annotation.override_type || 'manual_override'
    annotationForm.reason_category = annotation.reason_category
    annotationForm.reason_text = annotation.reason_text || ''
    annotationForm.confidence = annotation.confidence
    annotationForm.was_intentional = annotation.was_intentional
    annotationForm.was_emotional = annotation.was_emotional
    annotationForm.should_remind_next_time = annotation.should_remind_next_time
    annotationForm.lesson = annotation.lesson || ''
    annotationForm.tags_text = annotation.tags.join(', ')
  } catch (error) {
    const message = error instanceof Error ? error.message : ''
    if (message && !message.includes('404') && !message.includes('not found')) {
      annotationDialogError.value = message
    }
  }
}

function alignmentItemFromDecision(decision: TradeDecisionResult): TradeDecisionExecutionAlignmentItem {
  const finalAction = decision.final_action || decision.action || null
  return {
    decision_id: decision.id,
    symbol: decision.symbol,
    decision_date: decision.created_at ? decision.created_at.slice(0, 10) : null,
    final_action: finalAction,
    action_group: 'unknown',
    ai_position_stance: selectedAiPolicyAssessment.value?.ai_position_stance || null,
    ai_recommended_action_bias: selectedAiPolicyAssessment.value?.recommended_action_bias || null,
    suggested_target_position_pct: decision.position_advice.suggested_target_position_pct ?? null,
    suggested_adjustment_pct: positionAdjustmentPct(decision),
    suggested_cash_amount: decision.position_advice.suggested_cash_amount ?? null,
    real_trade_side: 'none',
    real_trade_count: 0,
    real_buy_notional: 0,
    real_sell_notional: 0,
    real_net_notional: 0,
    real_weighted_avg_price: null,
    first_real_trade_date: null,
    execution_delay_trading_days: null,
    alignment_label: 'unknown',
    behavior_tags: [],
    return_5d: null,
    return_20d: null,
    estimated_opportunity_cost: 0,
    estimated_avoided_loss: 0,
    estimated_bad_override_cost: 0,
    estimated_good_override_value: 0,
    explanation: '从交易决策详情页手动标注，暂未匹配真实执行对齐数据。',
    matched_trades: [],
    data_limitations: ['decision_detail_annotation_without_alignment_snapshot'],
  }
}

async function openDecisionAnnotationDialog(decision: TradeDecisionResult): Promise<void> {
  await openAnnotationDialog(alignmentItemFromDecision(decision))
}

function closeAnnotationDialog(): void {
  annotationDialogVisible.value = false
  annotationTarget.value = null
  annotationDialogError.value = ''
  resetAnnotationForm()
}

function annotationTags(): string[] {
  return annotationForm.tags_text
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 20)
}

async function saveAnnotation(): Promise<void> {
  if (!annotationTarget.value) return
  annotationSaving.value = true
  annotationDialogError.value = ''
  try {
    await saveTradeDecisionOverrideAnnotation(annotationTarget.value.decision_id, {
      override_type: annotationForm.override_type.trim() || 'manual_override',
      reason_category: annotationForm.reason_category,
      reason_text: annotationForm.reason_text.trim(),
      confidence: annotationForm.confidence,
      was_intentional: annotationForm.was_intentional,
      was_emotional: annotationForm.was_emotional,
      should_remind_next_time: annotationForm.should_remind_next_time,
      lesson: annotationForm.lesson.trim(),
      tags: annotationTags(),
    })
    manualAnnotationDecisionIds.value = new Set([...manualAnnotationDecisionIds.value, annotationTarget.value.decision_id])
    closeAnnotationDialog()
    await loadBehaviorProfile()
  } catch (error) {
    annotationDialogError.value = error instanceof Error ? error.message : '保存标注失败'
  } finally {
    annotationSaving.value = false
  }
}

async function deleteAnnotation(): Promise<void> {
  if (!annotationTarget.value) return
  annotationSaving.value = true
  annotationDialogError.value = ''
  try {
    await deleteTradeDecisionOverrideAnnotation(annotationTarget.value.decision_id)
    const next = new Set(manualAnnotationDecisionIds.value)
    next.delete(annotationTarget.value.decision_id)
    manualAnnotationDecisionIds.value = next
    closeAnnotationDialog()
    await loadBehaviorProfile()
  } catch (error) {
    annotationDialogError.value = error instanceof Error ? error.message : '删除标注失败'
  } finally {
    annotationSaving.value = false
  }
}

function loadDecisionSecondaryPanels(): void {
  if (secondaryDecisionPanelsRequested.value) return
  secondaryDecisionPanelsRequested.value = true
  void loadQualitySummary()
  void loadOutcomeReplay()
  void loadBacktest()
  void loadAlignment()
  void loadBehaviorProfile()
}

function activateDecisionWorkspace(): void {
  activeWorkspace.value = 'decision'
  loadDecisionSecondaryPanels()
}

function activateResearchWorkspace(): void {
  activeWorkspace.value = 'research'
}

const selectedAssetDebate = computed(() => assetDebateFor(selectedDecision.value))
const selectedTradePlan = computed(() => tradePlanFor(selectedDecision.value))
const selectedTradePlanAssessment = computed(() => nestedRecord(selectedTradePlan.value, 'risk_reward_assessment'))
const selectedRiskGate = computed(() => riskGateFor(selectedDecision.value))
const selectedUserInvestmentPolicy = computed<UserInvestmentPolicySummary | null>(() => selectedDecision.value?.user_investment_policy_summary || null)
const selectedAiPolicyAssessment = computed<AiPolicyAssessment | null>(() => selectedDecision.value?.ai_policy_assessment || null)
const selectedBehaviorProfileSummary = computed(() => selectedDecision.value?.behavior_profile_summary || null)
const selectedPersonalBehaviorReminders = computed(() => selectedDecision.value?.personal_behavior_reminders || [])
const hasSelectedAssetDebate = computed(() => Object.keys(selectedAssetDebate.value).length > 0)
const hasSelectedTradePlan = computed(() => Object.keys(selectedTradePlan.value).length > 0)
const hasSelectedRiskGate = computed(() => Object.keys(selectedRiskGate.value).length > 0)
const selectedAiRiskBudget = computed(() => asRecord(selectedAiPolicyAssessment.value?.risk_budget))
const selectedActionDowngradeChain = computed(() => selectedDecision.value?.action_downgrade_chain || [])

function positionAdjustmentPct(decision: TradeDecisionResult): number | null {
  const advice = decision.position_advice
  if (advice.current_position_pct === null || advice.current_position_pct === undefined) return null
  if (advice.suggested_target_position_pct === null || advice.suggested_target_position_pct === undefined) return null
  return advice.suggested_target_position_pct - advice.current_position_pct
}

function stepTargetPositionPct(step: Record<string, unknown>): number | null {
  const raw = step.target_position_pct
  return typeof raw === 'number' ? raw : null
}

function formatDateTime(value: string): string {
  return formatLocalDateTime(value) || '--'
}

async function loadPage(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const [healthResponse, holdingsResponse, decisionsResponse, tasksResponse] = await Promise.all([
      fetchTradeDecisionHealth(),
      fetchTradeDecisionHoldings(),
      fetchRecentTradeDecisions({ limit: 10 }),
      fetchTradeDecisionTasks(20),
    ])
    health.value = healthResponse
    currentHoldings.value = holdingsResponse.items
    recentDecisions.value = decisionsResponse
    taskItems.value = tasksResponse
    generatingKey.value = tasksResponse.some((task) => task.status === 'queued' || task.status === 'running') ? 'trade_decision' : ''
    selectedDecision.value = decisionsResponse[0] ?? null
    if (decisionsResponse[0]) {
      void selectDecisionById(decisionsResponse[0].id)
    }
    if (activeWorkspace.value === 'decision') {
      loadDecisionSecondaryPanels()
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载 AI 决策失败'
  } finally {
    loading.value = false
  }
}

async function refreshRecent(): Promise<void> {
  recentDecisions.value = await fetchRecentTradeDecisions({ limit: 10 })
}

async function selectDecisionById(decisionId: string): Promise<void> {
  selectedDecision.value = await fetchTradeDecisionDetail(decisionId)
}

async function generateDecision(): Promise<void> {
  activateDecisionWorkspace()
  const symbol = entryForm.symbol.trim().toUpperCase()
  if (!symbol) return

  generatingKey.value = 'trade_decision'
  errorMessage.value = ''

  try {
    const task = await startTradeDecisionTask({ symbol })
    taskItems.value = [task, ...taskItems.value.filter((item) => item.id !== task.id)].slice(0, 20)
    await pollTasks()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '生成交易建议失败'
    generatingKey.value = ''
  }
}

function symbolTaskElapsedSeconds(task: SymbolAnalysisTask): number {
  const start = Date.parse(task.started_at)
  const end = task.completed_at ? Date.parse(task.completed_at) : now.value
  return Math.max(0, Math.floor((end - start) / 1000))
}

function localTaskStatusLabel(status: SymbolAnalysisTask['status']): string {
  if (status === 'queued') return 'QUEUED'
  if (status === 'running') return 'RUNNING'
  if (status === 'completed') return 'DONE'
  return 'FAILED'
}

function localTaskStatusClass(status: SymbolAnalysisTask['status']): string {
  if (status === 'failed') return 'p-tag--negative'
  if (status === 'completed') return 'p-tag--positive'
  return 'p-tag--accent'
}

function setSymbolAnalysisState(state: SymbolAnalysisSnapshot): void {
  symbolAnalysisState.value = state
}

function setSymbolAnalysisTask(task: SymbolAnalysisTask | null): void {
  symbolAnalysisTask.value = task
}

function taskElapsedSeconds(task: AgentTask): number {
  const start = Date.parse(task.started_at || task.created_at)
  const end = task.completed_at ? Date.parse(task.completed_at) : now.value
  return Math.max(0, Math.floor((end - start) / 1000))
}

function taskStage(task: AgentTask): string {
  if (task.status === 'completed') return '已完成'
  if (task.status === 'failed') return task.error_message || '运行失败'
  const elapsed = taskElapsedSeconds(task)
  if (elapsed < 5) return '排队并构建账户上下文'
  if (elapsed < 20) return '拉取公开市场数据和重点事件'
  if (elapsed < 45) return '运行多空辩论与交易计划'
  return '保存结果并刷新列表'
}

function taskStatusLabel(status: AgentTask['status']): string {
  if (status === 'queued') return 'QUEUED'
  if (status === 'running') return 'RUNNING'
  if (status === 'completed') return 'DONE'
  return 'FAILED'
}

function toggleTask(task: AgentTask): void {
  expandedTaskId.value = expandedTaskId.value === task.id ? null : task.id
}

function mergeTaskGraphSnapshot(taskId: string, snapshot: AgentTask['graph_snapshot']): void {
  taskItems.value = taskItems.value.map((task) => (task.id === taskId ? { ...task, graph_snapshot: snapshot } : task))
}

async function viewTaskResult(task: AgentTask): Promise<void> {
  if (!task.result_id) return
  selectedDecision.value = await fetchTradeDecisionDetail(task.result_id)
}

async function pollTasks(): Promise<void> {
  try {
    const tasks = await fetchTradeDecisionTasks(20)
    taskItems.value = tasks
    const latestCompleted = tasks.find((task) => task.status === 'completed' && task.result_id)
    if (latestCompleted?.result_id && selectedDecision.value?.id !== latestCompleted.result_id) {
      const decision = await fetchTradeDecisionDetail(latestCompleted.result_id)
      selectedDecision.value = decision
      await refreshRecent()
      if (activeWorkspace.value === 'decision') {
        await loadQualitySummary()
      }
    }
    generatingKey.value = tasks.some((task) => task.status === 'queued' || task.status === 'running') ? generatingKey.value : ''
  } catch {
    // Keep the last visible task state; the next poll can recover.
  }
}

onMounted(() => {
  taskTimer = window.setInterval(() => {
    now.value = Date.now()
    if (activeTaskCount.value) {
      void pollTasks()
    }
  }, 2000)
  void loadPage()
})

onBeforeUnmount(() => {
  if (taskTimer) {
    window.clearInterval(taskTimer)
  }
})
</script>

<template>
  <section class="page-section trade-decision-page">
    <section class="surface-panel">
      <div class="surface-panel__content">
        <div class="section-header">
          <div>
            <p class="eyebrow">AGENT</p>
            <h2 class="trade-decision-title">AI 交易决策</h2>
            <p class="panel-subtitle">输入股票代码，系统会基于 IBKR 账户事实、公开市场数据、重点事件、多空辩论和交易计划，生成建仓、加仓、减仓、持有或观察建议。</p>
          </div>
          <div class="decision-health">
            <Tag :value="health?.llm_configured ? 'LLM READY' : 'LLM MISSING'" :class="healthTone" />
            <Tag :value="health?.longbridge_configured ? 'LONGBRIDGE READY' : 'LONGBRIDGE LIMITED'" :class="health?.longbridge_configured ? 'p-tag--positive' : 'p-tag--accent'" />
            <Tag
              :value="health?.mcp_auth_status === 'connected' || health?.mcp_auth_status === 'static_token' ? 'MCP CONNECTED' : 'MCP AUTH REQUIRED'"
              :class="health?.mcp_auth_status === 'connected' || health?.mcp_auth_status === 'static_token' ? 'p-tag--positive' : 'p-tag--negative'"
            />
          </div>
        </div>
      </div>
    </section>

    <LoadingBlock v-if="loading" />
    <ErrorBlock v-else-if="errorMessage && !selectedDecision" :message="errorMessage" />

    <template v-else>
      <ErrorBlock v-if="errorMessage" :message="errorMessage" />

      <section class="decision-action-grid">
        <section
          class="surface-panel decision-composer decision-mode-card"
          :class="{ 'is-active': activeWorkspace === 'decision' }"
          role="button"
          tabindex="0"
          @click="activateDecisionWorkspace"
          @focusin="activateDecisionWorkspace"
        >
          <div class="surface-panel__content">
            <div class="section-header">
              <div>
                <h3 class="panel-title">生成交易决策</h3>
                <p class="panel-subtitle">只需输入股票代码，系统会自动结合是否已有持仓和账户风险，不需要手动选择建仓或持仓管理。</p>
              </div>
            </div>

            <form class="entry-form" @submit.prevent="generateDecision">
              <label class="field-stack">
                <span class="field-stack__label">Symbol</span>
                <SymbolInput v-model="entryForm.symbol" required placeholder="AAPL / MSFT / NVDA" />
              </label>
              <div class="entry-form__actions">
                <Button
                  :label="isGenerating ? '任务运行中' : '生成交易建议'"
                  :icon="isGenerating ? 'pi pi-spin pi-spinner' : 'pi pi-send'"
                  class="p-button p-button--accent entry-generate-button"
                  type="submit"
                  :disabled="isGenerating"
                />
              </div>
            </form>

            <div v-if="entryForm.symbol && hasPosition(entryForm.symbol.toUpperCase())" class="holding-hint">
              <Tag value="已有持仓" class="p-tag--accent" />
              <span>检测到已有持仓，本次将结合当前持仓、账户风险和多空观点生成加仓 / 减仓 / 持有建议</span>
            </div>
            <div v-else-if="entryForm.symbol" class="holding-hint">
              <Tag value="无持仓" class="p-tag--warning" />
              <span>当前无持仓，本次将结合账户现金、风险约束和多空观点生成建仓 / 观察建议</span>
            </div>
          </div>
        </section>

        <section
          class="surface-panel decision-research decision-mode-card"
          :class="{ 'is-active': activeWorkspace === 'research' }"
          role="button"
          tabindex="0"
          @click="activateResearchWorkspace"
          @focusin="activateResearchWorkspace"
        >
          <div class="surface-panel__content">
            <SymbolAnalysisPanel
              :show-results="false"
              @activate="activateResearchWorkspace"
              @state-change="setSymbolAnalysisState"
              @task-change="setSymbolAnalysisTask"
            />
          </div>
        </section>
      </section>

      <section v-if="hasRunnerItems" class="surface-panel decision-runner-panel">
        <div class="surface-panel__content">
          <div class="section-header">
            <div>
              <h3 class="panel-title">后台任务</h3>
              <p class="panel-subtitle">交易决策任务会在后端继续运行；标的分析任务在当前页面内展示进度和结果。</p>
            </div>
          </div>
          <div class="runner-list">
            <div
              v-if="symbolAnalysisTask"
              class="runner-item"
              :class="`runner-item--${symbolAnalysisTask.status}`"
            >
              <button type="button" class="runner-item__summary" @click="expandedTaskId = expandedTaskId === symbolAnalysisTask.id ? null : symbolAnalysisTask.id">
                <span class="runner-item__dot" aria-hidden="true"></span>
                <div class="runner-item__main">
                  <strong>{{ symbolAnalysisTask.label }}</strong>
                  <span>{{ symbolAnalysisTask.stage }}</span>
                </div>
                <div class="runner-item__meta">
                  <Tag :value="localTaskStatusLabel(symbolAnalysisTask.status)" :class="localTaskStatusClass(symbolAnalysisTask.status)" />
                  <span>{{ symbolTaskElapsedSeconds(symbolAnalysisTask) }}s</span>
                  <span class="pi" :class="expandedTaskId === symbolAnalysisTask.id ? 'pi-chevron-up' : 'pi-chevron-down'" />
                </div>
              </button>
              <div v-if="expandedTaskId === symbolAnalysisTask.id" class="local-task-steps">
                <div
                  v-for="step in symbolAnalysisTask.steps"
                  :key="step.id"
                  class="local-task-step"
                  :class="`local-task-step--${step.status}`"
                >
                  <span class="runner-item__dot" aria-hidden="true"></span>
                  <span>{{ step.label }}</span>
                  <Tag :value="localTaskStatusLabel(step.status)" :class="localTaskStatusClass(step.status)" />
                </div>
                <div v-if="symbolAnalysisTask.status === 'failed' && symbolAnalysisTask.error_message" class="holding-hint holding-hint--warning">
                  <Tag value="失败" class="p-tag--warning" />
                  <span>{{ symbolAnalysisTask.error_message }}</span>
                </div>
                <div class="runner-item__actions">
                  <Button type="button" label="查看标的分析结果" size="small" severity="secondary" @click.stop="activateResearchWorkspace" />
                </div>
              </div>
            </div>

            <div
              v-for="task in visibleTasks"
              :key="task.id"
              class="runner-item"
              :class="`runner-item--${task.status}`"
            >
              <button type="button" class="runner-item__summary" @click="toggleTask(task)">
                <span class="runner-item__dot" aria-hidden="true"></span>
                <div class="runner-item__main">
                  <strong>{{ task.label }}</strong>
                  <span>{{ taskStage(task) }}</span>
                </div>
                <div class="runner-item__meta">
                  <Tag :value="taskStatusLabel(task.status)" :class="task.status === 'failed' ? 'p-tag--negative' : task.status === 'completed' ? 'p-tag--positive' : 'p-tag--accent'" />
                  <span>{{ taskElapsedSeconds(task) }}s</span>
                  <span class="pi" :class="expandedTaskId === task.id ? 'pi-chevron-up' : 'pi-chevron-down'" />
                </div>
              </button>
              <AgentTaskGraph
                v-if="expandedTaskId === task.id"
                :task="task"
                :expanded="expandedTaskId === task.id"
                @snapshot="mergeTaskGraphSnapshot"
              />
              <div v-if="expandedTaskId === task.id && task.result_id" class="runner-item__actions">
                <Button type="button" label="查看结果" size="small" severity="secondary" @click.stop="viewTaskResult(task)" />
              </div>
            </div>
          </div>
        </div>
      </section>

      <section v-if="activeWorkspace === 'research'" class="surface-panel symbol-analysis-detail-panel">
        <div class="surface-panel__content">
          <div class="section-header">
            <div>
              <h3 class="panel-title">标的分析结果</h3>
              <p class="panel-subtitle">财报、估值、横向对比和 AI 加仓/建仓判断统一在这里展开，不再撑高上方入口卡片。</p>
            </div>
          </div>
          <SymbolAnalysisResults :state="symbolAnalysisState" />
        </div>
      </section>

      <section v-else class="decision-layout">
        <section class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <div>
                <h3 class="panel-title">最近决策</h3>
                <p class="panel-subtitle">每次生成都会保存一条历史记录。</p>
              </div>
            </div>
            <div v-if="recentDecisions.length" class="decision-list">
              <button v-for="item in visibleRecentDecisions" :key="item.id" type="button" :class="{ 'is-active': selectedDecision?.id === item.id }" @click="selectDecisionById(item.id)">
                <strong>{{ item.symbol }}</strong>
                <span>{{ decisionTypeLabel(item.decision_type) }}</span>
                <span>{{ item.overall_score }}/100 · {{ actionLabel(item.action) }}</span>
                <div v-if="hasDecisionQuality(item)" class="decision-list__quality">
                  <span v-if="qualityScore(item) !== null">质量 {{ qualityScore(item) }}/100 · {{ qualityLevelLabel(decisionQuality(item).level) }}</span>
                  <span v-else>质量未评估</span>
                  <Tag v-if="decisionQuality(item).passed === false" value="质量未通过" class="p-tag--negative" />
                </div>
                <small>{{ item.decision_summary }}</small>
              </button>
              <button v-if="hiddenRecentDecisionCount" type="button" class="list-toggle-button" @click="showAllRecentDecisions = !showAllRecentDecisions">
                {{ showAllRecentDecisions ? '收起' : `展开其余 ${hiddenRecentDecisionCount} 条` }}
              </button>
            </div>
            <div v-else class="empty-state">暂无 AI 决策</div>
          </div>
        </section>

        <section v-if="selectedDecision" class="surface-panel">
          <div class="surface-panel__content">
            <div class="decision-detail-header">
              <div>
                <p class="eyebrow">交易决策 · {{ decisionTypeLabel(selectedDecision.decision_type) }}</p>
                <h3>{{ selectedDecision.overall_score }}<span>/100</span></h3>
                <p class="panel-subtitle">{{ selectedDecision.decision_summary }}</p>
              </div>
              <div class="decision-tags">
                <Tag :value="actionLabel(selectedDecision.action)" class="p-tag--accent" />
                <Tag :value="ratingLabel(selectedDecision.rating)" :class="selectedDecision.overall_score >= 70 ? 'p-tag--positive' : selectedDecision.overall_score < 50 ? 'p-tag--negative' : 'p-tag--accent'" />
                <Tag :value="selectedDecision.confidence === 'high' ? '高置信' : selectedDecision.confidence === 'medium' ? '中置信' : '低置信'" class="p-tag--accent" />
              </div>
            </div>

            <section v-if="hasSelectedAssetDebate" class="detail-card">
              <div class="detail-card__head">
                <h4>标的观点</h4>
                <div class="detail-tags">
                  <Tag :value="stanceLabel(selectedAssetDebate.asset_stance)" class="p-tag--accent" />
                  <Tag :value="winnerLabel(selectedAssetDebate.winner)" class="p-tag--accent" />
                  <Tag :value="String(selectedAssetDebate.conviction || '--')" class="p-tag--accent" />
                </div>
              </div>
              <p>{{ selectedAssetDebate.reasoning_summary || '暂无观点摘要' }}</p>
              <div v-if="asStringList(selectedAssetDebate.key_uncertainties, 4).length" class="detail-list">
                <span>关键不确定性</span>
                <ul>
                  <li v-for="item in asStringList(selectedAssetDebate.key_uncertainties, 4)" :key="item">{{ item }}</li>
                </ul>
              </div>
            </section>

            <section class="score-grid">
              <div
                v-for="item in scoreDimensions"
                :key="item.key"
                class="score-card"
                :class="{ 'score-card--full': item.fullWidth }"
              >
                <div class="score-card__head">
                  <span>{{ item.label }}</span>
                  <strong>{{ selectedDecision.score_detail[item.key]?.score ?? 0 }}/{{ selectedDecision.score_detail[item.key]?.max_score ?? 0 }}</strong>
                </div>
                <div class="score-card__reason-wrap">
                  <p class="score-card__reason">{{ selectedDecision.score_detail[item.key]?.reason ?? '暂无说明' }}</p>
                  <div class="score-card__tooltip">{{ selectedDecision.score_detail[item.key]?.reason ?? '暂无说明' }}</div>
                </div>
              </div>
            </section>

            <section class="advice-grid">
              <div v-if="selectedUserInvestmentPolicy" class="advice-card">
                <h4>我的投资偏好</h4>
                <span>配置来源：{{ policySourceLabel(selectedUserInvestmentPolicy.source) }}</span>
                <span>股票定位：{{ selectedUserInvestmentPolicy.asset_role }}</span>
                <span>信心等级：{{ selectedUserInvestmentPolicy.conviction }}</span>
                <span>我希望保留的最低仓位：{{ formatPct(selectedUserInvestmentPolicy.user_preferred_min_position_pct) }}</span>
                <span>我偏好的目标仓位：{{ formatPct(selectedUserInvestmentPolicy.user_preferred_target_position_pct) }}</span>
                <span>我能接受的最大仓位：{{ formatPct(selectedUserInvestmentPolicy.user_preferred_max_position_pct) }}</span>
                <span>当前仓位：{{ formatPct(selectedUserInvestmentPolicy.current_position_pct) }}</span>
                <span>相对我偏好目标的差距：{{ formatSignedPct(selectedUserInvestmentPolicy.gap_to_user_preferred_target_pct) }}</span>
                <span>偏好差距标签：{{ userPreferenceGapLabel(selectedUserInvestmentPolicy.user_preference_gap_label) }}</span>
                <span>AI 审查状态：{{ selectedUserInvestmentPolicy.ai_review_status || 'unknown' }}</span>
                <p class="policy-disclaimer">{{ selectedUserInvestmentPolicy.disclaimer || '这是你的主观偏好，不是 AI 最终建议；AI 会基于市场数据重新评估。' }}</p>
                <div v-if="selectedUserInvestmentPolicy.add_rules.length" class="detail-list">
                  <span>加仓偏好规则</span>
                  <ul><li v-for="item in selectedUserInvestmentPolicy.add_rules" :key="item">{{ item }}</li></ul>
                </div>
                <div v-if="selectedUserInvestmentPolicy.no_add_triggers.length" class="detail-list">
                  <span>不加仓条件</span>
                  <ul><li v-for="item in selectedUserInvestmentPolicy.no_add_triggers" :key="item">{{ item }}</li></ul>
                </div>
                <div v-if="selectedUserInvestmentPolicy.sell_triggers.length" class="detail-list">
                  <span>卖出触发条件</span>
                  <ul><li v-for="item in selectedUserInvestmentPolicy.sell_triggers" :key="item">{{ item }}</li></ul>
                </div>
                <div v-if="selectedUserInvestmentPolicy.hard_constraints.length" class="detail-list">
                  <span>硬约束</span>
                  <ul><li v-for="item in selectedUserInvestmentPolicy.hard_constraints" :key="item">{{ item }}</li></ul>
                </div>
                <div v-if="selectedUserInvestmentPolicy.soft_preferences.length" class="detail-list">
                  <span>软偏好</span>
                  <ul><li v-for="item in selectedUserInvestmentPolicy.soft_preferences" :key="item">{{ item }}</li></ul>
                </div>
              </div>
              <div v-if="selectedAiPolicyAssessment" class="advice-card">
                <h4>AI 仓位评估</h4>
                <span>状态：{{ aiPolicyStatusLabel(selectedAiPolicyAssessment.status) }}</span>
                <span>AI 定位：{{ selectedAiPolicyAssessment.ai_assessed_asset_role || '--' }}</span>
                <span>定位置信度：{{ selectedAiPolicyAssessment.ai_role_confidence || '--' }}</span>
                <span>AI 目标区间：{{ formatPctRange(selectedAiPolicyAssessment.ai_recommended_target_position_range_pct || null) }}</span>
                <span>AI 目标仓位：{{ formatPct(selectedAiPolicyAssessment.ai_recommended_target_position_pct) }}</span>
                <span>AI 最大仓位：{{ formatPct(selectedAiPolicyAssessment.ai_recommended_max_position_pct) }}</span>
                <span>当前仓位：{{ formatPct(selectedAiPolicyAssessment.current_position_pct) }}</span>
                <span>相对 AI 目标差距：{{ formatSignedPct(selectedAiPolicyAssessment.gap_to_ai_target_pct) }}</span>
                <span>AI 仓位状态：{{ aiPositionStanceLabel(selectedAiPolicyAssessment.ai_position_stance) }}</span>
                <span>反驳级别：{{ aiChallengeLabel(selectedAiPolicyAssessment.challenge_level) }}</span>
                <span>动作倾向：{{ actionBiasLabel(selectedAiPolicyAssessment.recommended_action_bias) }}</span>
                <span>Prompt 来源：{{ selectedAiPolicyAssessment.prompt_source || '--' }}</span>
                <p class="policy-disclaimer">{{ selectedAiPolicyAssessment.preference_alignment_summary || 'AI 仓位评估与用户偏好分开展示；最终动作仍由交易计划和 Risk Gate 决定。' }}</p>
                <p v-if="selectedAiPolicyAssessment.challenge_reason" class="policy-disclaimer">反驳说明：{{ selectedAiPolicyAssessment.challenge_reason }}</p>
                <div class="detail-list">
                  <span>风险预算</span>
                  <ul>
                    <li>预估下行：{{ formatPct(asNumber(selectedAiRiskBudget.estimated_downside_pct)) }}</li>
                    <li>账户最大损失：{{ formatPct(asNumber(selectedAiRiskBudget.max_account_loss_pct)) }}</li>
                    <li>{{ String(selectedAiRiskBudget.reason || '暂无说明') }}</li>
                  </ul>
                </div>
                <div v-if="asStringList(selectedAiPolicyAssessment.key_reasons, 4).length" class="detail-list">
                  <span>AI 理由</span>
                  <ul><li v-for="item in asStringList(selectedAiPolicyAssessment.key_reasons, 4)" :key="item">{{ item }}</li></ul>
                </div>
                <div v-if="asStringList(selectedAiPolicyAssessment.key_risks, 4).length" class="detail-list">
                  <span>AI 风险</span>
                  <ul><li v-for="item in asStringList(selectedAiPolicyAssessment.key_risks, 4)" :key="item">{{ item }}</li></ul>
                </div>
                <div v-if="asStringList(selectedAiPolicyAssessment.data_limitations, 4).length" class="detail-list">
                  <span>数据限制</span>
                  <ul><li v-for="item in asStringList(selectedAiPolicyAssessment.data_limitations, 4)" :key="item">{{ item }}</li></ul>
                </div>
              </div>
              <div class="advice-card behavior-reminder-card">
                <div class="advice-card__head">
                  <h4>个人行为提醒</h4>
                  <Button
                    type="button"
                    size="small"
                    severity="secondary"
                    :label="hasAnnotationForDecision(selectedDecision.id) ? '编辑标注' : '标注本次执行/不执行原因'"
                    @click="openDecisionAnnotationDialog(selectedDecision)"
                  />
                </div>
                <template v-if="selectedBehaviorProfileSummary">
                  <div class="source-row source-row--left">
                    <Tag :value="`行为风险：${behaviorRiskLabel(selectedBehaviorProfileSummary.behavior_risk_level)}`" :class="behaviorRiskClass(selectedBehaviorProfileSummary.behavior_risk_level)" />
                    <Tag
                      v-for="pattern in selectedBehaviorProfileSummary.dominant_behavior_patterns.slice(0, 5)"
                      :key="pattern"
                      :value="behaviorTagLabel(pattern)"
                      class="p-tag--accent"
                    />
                  </div>
                  <ul v-if="selectedPersonalBehaviorReminders.length" class="behavior-reminder-list">
                    <li v-for="item in selectedPersonalBehaviorReminders" :key="`${item.type}-${item.message}`">
                      <Tag :value="item.severity || 'low'" :class="reminderSeverityClass(item.severity)" />
                      <span>{{ item.message }}</span>
                    </li>
                  </ul>
                  <p v-else class="policy-disclaimer">暂无需要特别提醒的历史行为模式，本次保持空提醒。</p>
                  <p class="policy-disclaimer">这些提醒只用于复盘和执行纪律，不会自动改变 Agent 动作；estimated cost/value 是模型估算，不是真实账户 PnL；人工标注不会强制 Agent。</p>
                  <div v-if="selectedBehaviorProfileSummary.data_limitations.length" class="detail-list">
                    <span>数据限制</span>
                    <ul><li v-for="item in selectedBehaviorProfileSummary.data_limitations.slice(0, 4)" :key="item">{{ item }}</li></ul>
                  </div>
                </template>
                <p v-else class="policy-disclaimer">暂无行为画像上下文，个人行为提醒暂不生成。</p>
              </div>
              <div class="advice-card">
                <h4>仓位建议</h4>
                <span>当前仓位：{{ formatPct(selectedDecision.position_advice.current_position_pct) }}</span>
                <span>目标仓位：{{ formatPct(selectedDecision.position_advice.suggested_target_position_pct) }}</span>
                <span>调整幅度：{{ formatSignedPct(positionAdjustmentPct(selectedDecision)) }}</span>
                <span>最大仓位：{{ formatPct(selectedDecision.position_advice.max_position_pct) }}</span>
                <span>建议金额：{{ formatNumber(selectedDecision.position_advice.suggested_cash_amount) }}</span>
                <span>仓位标签：{{ selectedDecision.position_advice.position_size_label }}</span>
              </div>
              <div class="advice-card">
                <h4>执行建议</h4>
                <span>是否现在行动：{{ selectedDecision.execution_plan.should_act_now ? '是' : '否' }}</span>
                <ul>
                  <li v-for="(step, index) in selectedDecision.execution_plan.plan" :key="index">
                    {{ step.condition ?? '条件' }}：{{ actionLabel(String(step.action || '')) }}
                    {{ stepTargetPositionPct(step) !== null ? `· 目标仓位 ${formatPct(stepTargetPositionPct(step))}` : '' }}
                    {{ step.amount ? `· ${formatNumber(Number(step.amount))}` : '' }}
                    {{ step.note ?? '' }}
                  </li>
                </ul>
                <div v-if="selectedDecision.execution_plan.invalid_conditions.length" class="detail-list">
                  <span>失效条件</span>
                  <ul><li v-for="item in selectedDecision.execution_plan.invalid_conditions" :key="item">{{ item }}</li></ul>
                </div>
                <div v-if="selectedDecision.execution_plan.recheck_triggers.length" class="detail-list">
                  <span>复查触发</span>
                  <ul><li v-for="item in selectedDecision.execution_plan.recheck_triggers" :key="item">{{ item }}</li></ul>
                </div>
              </div>
            </section>

            <section class="advice-grid">
              <div v-if="hasSelectedTradePlan" class="advice-card">
                <h4>交易计划</h4>
                <span>原始计划动作：{{ actionLabel(String(selectedTradePlan.portfolio_action || '')) }}</span>
                <span>动作原因：{{ reasonTypeLabel(selectedTradePlan.action_reason_type) }}</span>
                <span>事件/风险窗口：{{ selectedTradePlanAssessment.event_risk_window || '--' }}</span>
                <span>等待回调：{{ selectedTradePlanAssessment.wait_for_pullback ? '是' : '否' }}</span>
                <p>{{ selectedTradePlan.summary || '暂无计划摘要' }}</p>
                <div v-if="asStringList(selectedTradePlan.invalidation_conditions, 4).length" class="detail-list">
                  <span>失效条件</span>
                  <ul><li v-for="item in asStringList(selectedTradePlan.invalidation_conditions, 4)" :key="item">{{ item }}</li></ul>
                </div>
                <div v-if="asStringList(selectedTradePlan.recheck_triggers, 4).length" class="detail-list">
                  <span>复查触发</span>
                  <ul><li v-for="item in asStringList(selectedTradePlan.recheck_triggers, 4)" :key="item">{{ item }}</li></ul>
                </div>
              </div>
              <div class="advice-card">
                <h4>动作校准</h4>
                <span>Trade Plan 原始动作：{{ actionLabel(selectedDecision.draft_action || String(selectedTradePlan.portfolio_action || '')) }}</span>
                <span>Risk Gate 后动作：{{ actionLabel(selectedDecision.risk_adjusted_action || String(selectedRiskGate.final_action || selectedDecision.action)) }}</span>
                <span>最终动作：{{ actionLabel(selectedDecision.final_action || selectedDecision.action) }}</span>
                <span>是否发生降级：{{ selectedActionDowngradeChain.length ? '是' : '否' }}</span>
                <span>AI 与最终动作：{{ finalActionAlignmentLabel(selectedDecision, selectedAiPolicyAssessment) }}</span>
                <p v-if="selectedDecision.action_change_reason" class="policy-disclaimer">主要变化原因：{{ selectedDecision.action_change_reason }}</p>
                <div v-if="selectedActionDowngradeChain.length" class="detail-list">
                  <span>降级链路</span>
                  <ul>
                    <li v-for="(item, index) in selectedActionDowngradeChain" :key="index">
                      {{ actionLabel(String(item.from || '')) }} → {{ actionLabel(String(item.to || '')) }}
                      · {{ String(item.by || '--') }} · {{ String(item.reason || '--') }}
                    </li>
                  </ul>
                </div>
              </div>
              <div v-if="hasSelectedRiskGate" class="advice-card">
                <h4>Risk Gate</h4>
                <span>原始动作：{{ actionLabel(String(selectedRiskGate.original_action || '')) }}</span>
                <span>最终动作：{{ actionLabel(String(selectedRiskGate.final_action || selectedDecision.action)) }}</span>
                <span>是否降级：{{ selectedRiskGate.downgraded ? '是' : '否' }}</span>
                <span>是否拦截：{{ selectedRiskGate.blocked ? '是' : '否' }}</span>
                <div v-if="asStringList(selectedRiskGate.gate_reasons, 6).length" class="detail-list">
                  <span>约束原因</span>
                  <ul><li v-for="item in asStringList(selectedRiskGate.gate_reasons, 6)" :key="item">{{ item }}</li></ul>
                </div>
                <div v-if="asStringList(selectedRiskGate.risk_flags, 6).length" class="detail-list">
                  <span>风险标签</span>
                  <ul><li v-for="item in asStringList(selectedRiskGate.risk_flags, 6)" :key="item">{{ item }}</li></ul>
                </div>
              </div>
            </section>

            <section class="detail-card quality-panel">
              <div class="detail-card__head">
                <h4>决策质量</h4>
                <div v-if="hasDecisionQuality(selectedDecision)" class="detail-tags">
                  <Tag
                    :value="qualityLevelLabel(decisionQuality(selectedDecision).level) || '未评估'"
                    :class="qualityLevelClass(decisionQuality(selectedDecision).level)"
                  />
                  <Tag
                    :value="qualityPassedLabel(decisionQuality(selectedDecision).passed)"
                    :class="qualityPassedClass(decisionQuality(selectedDecision).passed)"
                  />
                  <Tag v-if="decisionQuality(selectedDecision).fallback_used" value="评估 fallback" class="p-tag--warning" />
                </div>
              </div>

              <div v-if="hasDecisionQuality(selectedDecision)" class="quality-panel__body">
                <div class="quality-summary">
                  <div class="quality-summary__score">
                    <span>质量分</span>
                    <strong>{{ qualityScore(selectedDecision) ?? '--' }}<small>/100</small></strong>
                  </div>
                  <div class="quality-summary__text">
                    <span>等级：{{ qualityLevelLabel(decisionQuality(selectedDecision).level) || '未评估' }}</span>
                    <span>是否通过：{{ qualityPassedLabel(decisionQuality(selectedDecision).passed) }}</span>
                    <p>{{ decisionQuality(selectedDecision).summary || '暂无质量评估摘要' }}</p>
                    <small v-if="decisionQuality(selectedDecision).fallback_reason">fallback 原因：{{ decisionQuality(selectedDecision).fallback_reason }}</small>
                  </div>
                </div>

                <div v-if="shortQualityList(decisionQuality(selectedDecision).hard_failures).length" class="quality-list quality-list--danger">
                  <span>硬性问题</span>
                  <ul>
                    <li v-for="item in shortQualityList(decisionQuality(selectedDecision).hard_failures)" :key="item">{{ item }}</li>
                  </ul>
                </div>

                <div v-if="shortQualityList(decisionQuality(selectedDecision).warnings).length" class="quality-list quality-list--warning">
                  <span>警告</span>
                  <ul>
                    <li v-for="item in shortQualityList(decisionQuality(selectedDecision).warnings)" :key="item">{{ item }}</li>
                  </ul>
                </div>

                <div v-if="shortQualityList(decisionQuality(selectedDecision).flags, 8).length" class="quality-flags">
                  <span>质量标签</span>
                  <div>
                    <Tag v-for="item in shortQualityList(decisionQuality(selectedDecision).flags, 8)" :key="item" :value="item" class="p-tag--accent" />
                  </div>
                </div>

                <div v-if="visibleQualityChecks(selectedDecision).length" class="quality-grid">
                  <div v-for="[key, check] in visibleQualityChecks(selectedDecision)" :key="key" class="quality-check-card">
                    <div class="quality-check-card__head">
                      <strong>{{ qualityCheckLabels[key] ?? key }}</strong>
                      <Tag :value="qualityPassedLabel(check.passed)" :class="qualityPassedClass(check.passed)" />
                    </div>
                    <span>硬性问题：{{ check.hard_failures?.length ?? 0 }}</span>
                    <span>警告：{{ check.warnings?.length ?? 0 }}</span>
                    <span>标签：{{ check.flags?.length ?? 0 }}</span>
                  </div>
                </div>
              </div>

              <p v-else class="panel-subtitle">该历史决策暂无质量评估数据。</p>
            </section>

            <section class="insight-grid">
              <div class="insight-block">
                <h4>关键理由</h4>
                <ul><li v-for="item in selectedDecision.key_reasons" :key="item">{{ item }}</li></ul>
              </div>
              <div class="insight-block">
                <h4>主要风险</h4>
                <ul><li v-for="item in selectedDecision.major_risks" :key="item">{{ item }}</li></ul>
              </div>
              <div class="insight-block">
                <h4>复盘约束</h4>
                <ul><li v-for="item in selectedDecision.review_warnings" :key="item">{{ item }}</li></ul>
              </div>
              <div v-if="selectedDecision.data_limitations && selectedDecision.data_limitations.length > 0" class="insight-block">
                <h4>数据限制</h4>
                <ul>
                  <li
                    v-for="item in selectedDecision.data_limitations"
                    :key="item"
                    :class="item.startsWith('valuation_not_applicable') ? 'limitation-info' : ''"
                  >{{ item.startsWith('valuation_not_applicable') ? item.replace('valuation_not_applicable: ', '') : item }}</li>
                </ul>
              </div>
            </section>

            <div class="source-row">
              <Tag value="账户/持仓/交易：IBKR" class="p-tag--positive" />
              <Tag value="公开市场数据：Longbridge" class="p-tag--accent" />
              <Tag value="决策生成：LLMService" class="p-tag--accent" />
            </div>
          </div>
        </section>

        <AgentEvidencePanel
          v-if="selectedDecision"
          :metadata="selectedDecision.metadata"
          :evidence-summary="selectedDecision.evidence_summary"
          :run-trace-summary="selectedDecision.run_trace_summary"
        />
      </section>

      <section v-if="activeWorkspace === 'decision'" class="surface-panel quality-dashboard behavior-profile-panel">
        <div class="surface-panel__content">
          <div class="section-header">
            <div>
              <h3 class="panel-title">交易行为画像</h3>
              <p class="panel-subtitle">用于复盘你的执行偏差和 override 原因；估算成本/价值不是真实 PnL，人工标注也不会强制覆盖 Agent 决策。</p>
            </div>
            <Tag v-if="behaviorProfileLoading" value="LOADING" class="p-tag--accent" />
            <Tag v-else-if="behaviorProfileError" value="加载失败" class="p-tag--warning" />
            <Tag v-else-if="behaviorProfileSummary" :value="`风险 ${behaviorRiskLabel(behaviorProfileSummary.behavior_risk_level)}`" :class="behaviorRiskClass(behaviorProfileSummary.behavior_risk_level)" />
          </div>

          <ErrorBlock v-if="behaviorProfileError" :message="behaviorProfileError" />
          <LoadingBlock v-else-if="behaviorProfileLoading && !behaviorProfile" />
          <div v-else-if="behaviorProfile && behaviorProfileSummary" class="quality-dashboard__body">
            <div class="quality-dashboard-grid">
              <div class="quality-metric-card">
                <span>跟随率</span>
                <strong>{{ formatPct(behaviorProfileSummary.alignment_rate) }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>手动 override 率</span>
                <strong>{{ formatPct(behaviorProfileSummary.manual_override_rate) }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>忽略加仓率</span>
                <strong>{{ formatPct(behaviorProfileSummary.ignored_add_signal_rate) }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>坏 override 率</span>
                <strong>{{ formatPct(behaviorProfileSummary.bad_override_rate) }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>行为净值估算</span>
                <strong>{{ formatMoney(behaviorProfileSummary.net_behavior_value) }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>行为风险</span>
                <strong>{{ behaviorRiskLabel(behaviorProfileSummary.behavior_risk_level) }}</strong>
              </div>
            </div>

            <div class="quality-dashboard-grid quality-dashboard-grid--secondary">
              <div class="quality-top-list">
                <h4>主要行为模式</h4>
                <ul v-if="behaviorProfileSummary.dominant_behavior_patterns.length">
                  <li v-for="item in behaviorProfileSummary.dominant_behavior_patterns.slice(0, 5)" :key="item.pattern">
                    <span>{{ behaviorTagLabel(item.pattern) }} · {{ item.description }}</span>
                    <strong>{{ item.count }} / {{ formatMoney(item.estimated_cost) }}</strong>
                  </li>
                </ul>
                <p v-else>暂无明显重复偏差。</p>
              </div>

              <div class="quality-top-list">
                <h4>Override 原因分布</h4>
                <ul v-if="behaviorProfileSummary.top_reason_categories.length">
                  <li v-for="item in behaviorProfileSummary.top_reason_categories" :key="item.key">
                    <span>{{ reasonCategoryLabel(item.key) }}</span>
                    <strong>{{ item.count }}</strong>
                  </li>
                </ul>
                <p v-else>还没有人工标注原因。</p>
              </div>

              <div class="quality-top-list">
                <h4>标的偏差</h4>
                <ul v-if="behaviorProfileSummary.top_symbols_with_bias.length">
                  <li v-for="item in behaviorProfileSummary.top_symbols_with_bias.slice(0, 5)" :key="item.key">
                    <span>{{ item.key }} · {{ (item.top_tags || []).map((tag) => behaviorTagLabel(tag.key)).join(' / ') }}</span>
                    <strong>{{ item.count }} / {{ formatMoney(item.estimated_cost) }}</strong>
                  </li>
                </ul>
                <p v-else>暂无明显标的偏差。</p>
              </div>

              <div class="quality-top-list">
                <h4>下次提醒</h4>
                <ul v-if="behaviorReminderHints.length">
                  <li v-for="item in behaviorReminderHints" :key="`${item.annotation_decision_id}-${item.message}`">
                    <span>{{ item.symbols.join(', ') || '全局' }} · {{ item.message }}</span>
                    <strong>{{ behaviorTagLabel(item.pattern) }}</strong>
                  </li>
                </ul>
                <p v-else>暂无需要下次提醒的经验教训。</p>
              </div>
            </div>

            <div v-if="behaviorProfileSummary.dominant_behavior_patterns.length" class="behavior-insight-list">
              <div v-for="item in behaviorProfileSummary.dominant_behavior_patterns.slice(0, 4)" :key="`hint-${item.pattern}`" class="holding-hint">
                <Tag :value="item.severity.toUpperCase()" :class="item.severity === 'high' ? 'p-tag--negative' : 'p-tag--warning'" />
                <span>{{ item.suggestion }}</span>
              </div>
            </div>
          </div>
          <div v-else class="empty-state">暂无行为画像数据。</div>
        </div>
      </section>

      <section v-if="activeWorkspace === 'decision'" class="surface-panel quality-dashboard">
        <div class="surface-panel__content">
          <div class="section-header">
            <div>
              <h3 class="panel-title">决策质量看板</h3>
              <p class="panel-subtitle">基于最近 200 条交易决策的 deterministic 质量评估聚合，不影响交易建议。</p>
            </div>
            <Tag v-if="qualitySummaryLoading" value="LOADING" class="p-tag--accent" />
            <Tag v-else-if="qualitySummaryError" value="加载失败" class="p-tag--warning" />
            <Tag v-else-if="qualitySummary" :value="`${qualitySummary.evaluated_count}/${qualitySummary.total_count} 已评估`" class="p-tag--accent" />
          </div>

          <ErrorBlock v-if="qualitySummaryError" :message="qualitySummaryError" />
          <LoadingBlock v-else-if="qualitySummaryLoading && !qualitySummary" />
          <div v-else-if="qualitySummary && qualitySummary.total_count > 0" class="quality-dashboard__body">
            <div class="quality-dashboard-grid">
              <div class="quality-metric-card">
                <span>平均质量分</span>
                <strong>{{ qualitySummary.average_score ?? '--' }}<small>/100</small></strong>
              </div>
              <div class="quality-metric-card">
                <span>通过率</span>
                <strong>{{ formatPct(qualitySummary.pass_rate) }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>已评估 / 总数</span>
                <strong>{{ qualitySummary.evaluated_count }}<small>/{{ qualitySummary.total_count }}</small></strong>
              </div>
              <div class="quality-metric-card">
                <span>Risk Gate 降级率</span>
                <strong>{{ formatPct(asNumber(qualitySummary.risk_gate.downgrade_rate)) }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>动作不一致率</span>
                <strong>{{ formatPct(asNumber(qualitySummary.action_consistency.trade_plan_final_mismatch_rate)) }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>结构化 fallback</span>
                <strong>{{ asNumber(qualitySummary.structured_output.fallback_count) ?? 0 }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>Add-like 比率</span>
                <strong>{{ formatPct(asNumber(qualitySummary.action_calibration.add_like_rate)) }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>Hold-like 比率</span>
                <strong>{{ formatPct(asNumber(qualitySummary.action_calibration.hold_like_rate)) }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>Draft→Final 降级率</span>
                <strong>{{ formatPct(asNumber(qualitySummary.action_calibration.draft_to_final_downgrade_rate)) }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>AI 低配但持有数</span>
                <strong>{{ asNumber(qualitySummary.action_calibration.ai_underweight_but_hold_count) ?? 0 }}</strong>
              </div>
            </div>

            <div class="quality-dashboard-grid quality-dashboard-grid--secondary">
              <div class="quality-distribution">
                <h4>等级分布</h4>
                <div v-for="level in qualityDistributionKeys" :key="level" class="quality-distribution__item">
                  <span>{{ qualityLevelLabel(level) || '未知' }}</span>
                  <strong>{{ distributionCount(level) }}</strong>
                </div>
              </div>

              <div class="quality-top-list">
                <h4>Top flags</h4>
                <ul v-if="topQualityItems(qualitySummary.top_flags, 8).length">
                  <li v-for="item in topQualityItems(qualitySummary.top_flags, 8)" :key="item.key">
                    <span>{{ item.key }}</span>
                    <strong>{{ item.count }}</strong>
                  </li>
                </ul>
                <p v-else>暂无质量标签</p>
              </div>

              <div class="quality-top-list">
                <h4>Top warnings</h4>
                <ul v-if="topQualityItems(qualitySummary.top_warnings, 5).length">
                  <li v-for="item in topQualityItems(qualitySummary.top_warnings, 5)" :key="item.key">
                    <span>{{ item.key }}</span>
                    <strong>{{ item.count }}</strong>
                  </li>
                </ul>
                <p v-else>暂无警告</p>
              </div>

              <div class="quality-top-list">
                <h4>动作降级原因</h4>
                <ul v-if="topQualityItems(qualitySummary.action_calibration.risk_gate_downgrade_reason_distribution, 6).length">
                  <li v-for="item in topQualityItems(qualitySummary.action_calibration.risk_gate_downgrade_reason_distribution, 6)" :key="item.key">
                    <span>{{ item.key }}</span>
                    <strong>{{ item.count }}</strong>
                  </li>
                </ul>
                <p v-else>暂无降级原因</p>
              </div>
            </div>

            <div v-if="recentQualityTrend.length" class="quality-trend-list">
              <h4>最近质量趋势</h4>
              <div
                v-for="item in recentQualityTrend"
                :key="item.id"
                class="quality-trend-item"
              >
                <strong>{{ item.symbol }}</strong>
                <span>{{ item.score ?? '--' }}/100 · {{ qualityLevelLabel(item.level) }}</span>
                <Tag :value="qualityPassedLabel(item.passed)" :class="qualityPassedClass(item.passed)" />
                <span>{{ actionLabel(item.action) }}</span>
                <small>{{ formatDateTime(item.created_at) }}</small>
              </div>
            </div>

            <div v-if="qualitySummary.data_limitations.length" class="holding-hint holding-hint--warning">
              <Tag value="数据提示" class="p-tag--warning" />
              <span>{{ qualitySummary.data_limitations.join(' · ') }}</span>
            </div>
          </div>
          <div v-else class="empty-state">暂无可聚合的交易决策质量数据。</div>
        </div>
      </section>

      <section v-if="activeWorkspace === 'decision'" class="surface-panel quality-dashboard">
        <div class="surface-panel__content">
          <div class="section-header">
            <div>
              <h3 class="panel-title">回放评估</h3>
              <p class="panel-subtitle">把历史交易决策与后续 1 / 5 / 20 个交易日价格对齐，评估建议质量，不代表真实账户收益。</p>
            </div>
            <Tag v-if="outcomeReplayLoading" value="LOADING" class="p-tag--accent" />
            <Tag v-else-if="outcomeReplayError" value="加载失败" class="p-tag--warning" />
            <Tag v-else-if="outcomeSummary" :value="`${outcomeSummary.evaluated_count}/${outcomeSummary.total_count} 已回放`" class="p-tag--accent" />
          </div>

          <ErrorBlock v-if="outcomeReplayError" :message="outcomeReplayError" />
          <LoadingBlock v-else-if="outcomeReplayLoading && !outcomeReplay" />
          <div v-else-if="outcomeSummary && outcomeSummary.total_count > 0" class="quality-dashboard__body">
            <div class="quality-dashboard-grid">
              <div class="quality-metric-card">
                <span>已评估 / 总数</span>
                <strong>{{ outcomeSummary.evaluated_count }}<small>/{{ outcomeSummary.total_count }}</small></strong>
              </div>
              <div class="quality-metric-card">
                <span>动作价值分</span>
                <strong>{{ outcomeSummary.action_value_score ?? '--' }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>Add-like 20D 均值</span>
                <strong>{{ formatSignedPct(outcomeSummary.add_like_avg_return_20d) }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>错过上涨</span>
                <strong>{{ outcomeSummary.missed_upside_count }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>避开下跌</span>
                <strong>{{ outcomeSummary.avoided_loss_count }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>加仓后承压</span>
                <strong>{{ outcomeSummary.bad_add_count }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>校准成功</span>
                <strong>{{ outcomeSummary.calibrated_action_success_count }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>Risk Gate 错过上涨</span>
                <strong>{{ outcomeSummary.risk_gate_missed_upside_count }}</strong>
              </div>
            </div>

            <div class="quality-dashboard-grid quality-dashboard-grid--secondary">
              <div class="quality-top-list">
                <h4>Action Group vs 20D</h4>
                <ul>
                  <li>
                    <span>加仓类</span>
                    <strong>{{ formatSignedPct(outcomeSummary.add_like_avg_return_20d) }}</strong>
                  </li>
                  <li>
                    <span>持有/等待类</span>
                    <strong>{{ formatSignedPct(outcomeSummary.hold_like_avg_return_20d) }}</strong>
                  </li>
                  <li>
                    <span>减仓类</span>
                    <strong>{{ formatSignedPct(outcomeSummary.reduce_like_avg_return_20d) }}</strong>
                  </li>
                </ul>
              </div>

              <div class="quality-top-list">
                <h4>Outcome 分布</h4>
                <ul v-if="topQualityItems(outcomeSummary.outcome_label_distribution, 8).length">
                  <li v-for="item in topQualityItems(outcomeSummary.outcome_label_distribution, 8)" :key="item.key">
                    <span>{{ outcomeLabel(item.key) }}</span>
                    <strong>{{ item.count }}</strong>
                  </li>
                </ul>
                <p v-else>暂无 outcome</p>
              </div>

              <div class="quality-top-list">
                <h4>Top 错过上涨</h4>
                <ul v-if="outcomeSummary.top_missed_upside_decisions.length">
                  <li v-for="item in outcomeSummary.top_missed_upside_decisions" :key="item.decision_id">
                    <span>{{ item.symbol }} · {{ actionLabel(item.final_action) }}</span>
                    <strong>{{ formatSignedPct(item.return_20d) }}</strong>
                  </li>
                </ul>
                <p v-else>暂无明显错过上涨</p>
              </div>

              <div class="quality-top-list">
                <h4>Top 承压/过早卖出</h4>
                <ul v-if="outcomeSummary.top_bad_decisions.length">
                  <li v-for="item in outcomeSummary.top_bad_decisions" :key="item.decision_id">
                    <span>{{ item.symbol }} · {{ outcomeLabel(item.outcome_label) }}</span>
                    <strong>{{ formatSignedPct(item.return_20d) }}</strong>
                  </li>
                </ul>
                <p v-else>暂无明显负面样本</p>
              </div>
            </div>

            <div class="outcome-table">
              <h4>最近回放明细</h4>
              <div class="outcome-table__header">
                <span>标的</span>
                <span>日期</span>
                <span>动作</span>
                <span>AI</span>
                <span>1D</span>
                <span>5D</span>
                <span>20D</span>
                <span>回撤</span>
                <span>Outcome</span>
              </div>
              <button
                v-for="item in outcomeItems"
                :key="item.decision_id"
                type="button"
                class="outcome-table__row"
                @click="selectDecisionById(item.decision_id)"
              >
                <strong>{{ item.symbol }}</strong>
                <span>{{ item.decision_date || '--' }}</span>
                <span>{{ actionLabel(item.final_action) }}</span>
                <span>{{ aiPositionStanceLabel(item.ai_position_stance) }} · {{ actionBiasLabel(item.ai_recommended_action_bias) }}</span>
                <span>{{ formatSignedPct(item.return_1d) }}</span>
                <span>{{ formatSignedPct(item.return_5d) }}</span>
                <span>{{ formatSignedPct(item.return_20d) }}</span>
                <span>{{ formatSignedPct(item.max_drawdown_20d) }}</span>
                <Tag :value="outcomeLabel(item.outcome_label)" :class="outcomeClass(item.outcome_label)" />
              </button>
            </div>

            <div v-if="outcomeSummary.data_limitations.length" class="holding-hint holding-hint--warning">
              <Tag value="数据提示" class="p-tag--warning" />
              <span>{{ outcomeSummary.data_limitations.join(' · ') }}</span>
            </div>
          </div>
          <div v-else class="empty-state">暂无可回放的交易决策或价格数据。</div>
        </div>
      </section>

      <section v-if="activeWorkspace === 'decision'" class="surface-panel quality-dashboard">
        <div class="surface-panel__content">
          <div class="section-header">
            <div>
              <h3 class="panel-title">虚拟组合回测</h3>
              <p class="panel-subtitle">假设按 final_action 用虚拟资金执行，不影响真实 IBKR 账户；默认 next close 成交，交易成本为估算。</p>
            </div>
            <Tag v-if="backtestLoading" value="LOADING" class="p-tag--accent" />
            <Tag v-else-if="backtestError" value="加载失败" class="p-tag--warning" />
            <Tag v-else-if="backtestSummary" :value="`${backtestSummary.trade_count} 笔虚拟交易`" class="p-tag--accent" />
          </div>

          <div class="backtest-controls">
            <label>
              <span>回看天数</span>
              <input v-model.number="backtestForm.days" type="number" min="1" max="3650" />
            </label>
            <label>
              <span>初始资金</span>
              <input v-model.number="backtestForm.initial_cash" type="number" min="1000" step="1000" />
            </label>
            <label>
              <span>Benchmark</span>
              <input v-model="backtestForm.benchmark_symbol" type="text" />
            </label>
            <label>
              <span>成交时点</span>
              <select v-model="backtestForm.execution_timing">
                <option value="next_close">次日收盘</option>
                <option value="same_close">当日收盘</option>
                <option value="next_open">次日开盘</option>
              </select>
            </label>
            <label class="backtest-controls__check">
              <input v-model="backtestForm.include_costs" type="checkbox" />
              <span>包含交易成本</span>
            </label>
            <Button label="运行回测" size="small" :loading="backtestLoading" @click="loadBacktest" />
          </div>

          <ErrorBlock v-if="backtestError" :message="backtestError" />
          <LoadingBlock v-else-if="backtestLoading && !backtest" />
          <div v-else-if="backtest && backtestSummary" class="quality-dashboard__body">
            <div class="quality-dashboard-grid">
              <div class="quality-metric-card">
                <span>总收益</span>
                <strong>{{ formatSignedPct(backtestSummary.total_return) }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>年化收益</span>
                <strong>{{ formatSignedPct(backtestSummary.annualized_return) }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>最大回撤</span>
                <strong>{{ formatSignedPct(backtestSummary.max_drawdown) }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>Sharpe</span>
                <strong>{{ backtestSummary.sharpe_ratio ?? '--' }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>胜率</span>
                <strong>{{ formatPct(backtestSummary.win_rate) }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>交易次数</span>
                <strong>{{ backtestSummary.trade_count }}<small> 笔</small></strong>
              </div>
              <div class="quality-metric-card">
                <span>换手率</span>
                <strong>{{ formatPct(backtestSummary.turnover) }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>超额收益</span>
                <strong>{{ formatSignedPct(backtestSummary.excess_return) }}</strong>
              </div>
            </div>

            <div class="backtest-chart">
              <div class="backtest-chart__head">
                <h4>权益曲线预览</h4>
                <span>{{ backtestSummary.start_date }} - {{ backtestSummary.end_date }} · {{ executionTimingLabel(String(backtest.params.execution_timing || '')) }}</span>
              </div>
              <div class="backtest-sparkline">
                <div
                  v-for="point in backtestCurvePreview"
                  :key="point.date"
                  class="backtest-sparkline__bar"
                  :style="{ height: curvePointHeight(point.cumulative_return) }"
                  :title="`${point.date} ${formatSignedPct(point.cumulative_return)}`"
                />
              </div>
            </div>

            <div class="quality-dashboard-grid quality-dashboard-grid--secondary">
              <div class="quality-top-list">
                <h4>最终持仓</h4>
                <ul v-if="backtest.positions.length">
                  <li v-for="item in backtest.positions" :key="item.symbol">
                    <span>{{ item.symbol }} · {{ formatPct(item.weight) }}</span>
                    <strong>{{ formatMoney(item.market_value) }}</strong>
                  </li>
                </ul>
                <p v-else>期末无虚拟持仓</p>
              </div>

              <div class="quality-top-list">
                <h4>Symbol Contribution</h4>
                <ul v-if="backtest.symbol_contributions.length">
                  <li v-for="item in backtest.symbol_contributions.slice(0, 8)" :key="item.key">
                    <span>{{ item.key }} · {{ item.trade_count }} 笔</span>
                    <strong>{{ formatMoney(item.contribution_pnl) }}</strong>
                  </li>
                </ul>
                <p v-else>暂无贡献统计</p>
              </div>

              <div class="quality-top-list">
                <h4>Action Stats</h4>
                <ul v-if="backtest.action_stats.length">
                  <li v-for="item in backtest.action_stats.slice(0, 8)" :key="item.key">
                    <span>{{ statKeyLabel(item.key) }} · 胜率 {{ formatPct(item.win_rate) }}</span>
                    <strong>{{ formatMoney(item.contribution_pnl) }}</strong>
                  </li>
                </ul>
                <p v-else>暂无动作统计</p>
              </div>

              <div class="quality-top-list">
                <h4>估算诊断</h4>
                <ul>
                  <li><span>校准成功 PnL</span><strong>{{ formatMoney(backtestSummary.calibrated_action_success_pnl) }}</strong></li>
                  <li><span>错过 AI 加仓成本</span><strong>{{ formatMoney(backtestSummary.missed_ai_add_opportunity_estimated_cost) }}</strong></li>
                  <li><span>Risk Gate 避险价值</span><strong>{{ formatMoney(backtestSummary.risk_gate_avoided_loss_estimated_value) }}</strong></li>
                </ul>
              </div>
            </div>

            <div class="outcome-table backtest-trade-table">
              <h4>虚拟交易明细</h4>
              <div class="outcome-table__header backtest-trade-table__header">
                <span>日期</span>
                <span>标的</span>
                <span>动作</span>
                <span>方向</span>
                <span>价格</span>
                <span>金额</span>
                <span>成本</span>
                <span>原因</span>
              </div>
              <div
                v-for="item in backtest.trades.slice(0, 20)"
                :key="`${item.decision_id}-${item.execution_date}-${item.side}`"
                class="outcome-table__row backtest-trade-table__row"
              >
                <span>{{ item.execution_date || item.decision_date || '--' }}</span>
                <strong>{{ item.symbol }}</strong>
                <span>{{ actionLabel(item.final_action) }}</span>
                <Tag :value="tradeSideLabel(item.side)" :class="item.side === 'buy' ? 'p-tag--positive' : item.side === 'sell' ? 'p-tag--warning' : 'p-tag--accent'" />
                <span>{{ formatNumber(item.execution_price) }}</span>
                <span>{{ formatMoney(item.notional) }}</span>
                <span>{{ formatMoney(item.commission) }}</span>
                <span>{{ item.reason }}</span>
              </div>
            </div>

            <div v-if="backtest.data_limitations.length" class="holding-hint holding-hint--warning">
              <Tag value="回测说明" class="p-tag--warning" />
              <span>{{ backtest.data_limitations.join(' · ') }}</span>
            </div>
          </div>
          <div v-else class="empty-state">暂无可运行的虚拟组合回测数据。</div>
        </div>
      </section>

      <section v-if="activeWorkspace === 'decision'" class="surface-panel quality-dashboard">
        <div class="surface-panel__content">
          <div class="section-header">
            <div>
              <h3 class="panel-title">真实执行对齐</h3>
              <p class="panel-subtitle">对齐 Agent 建议、IBKR 真实交易和 Shadow Backtest，估算行为偏差，不代表真实账户 PnL。</p>
            </div>
            <Tag v-if="alignmentLoading" value="LOADING" class="p-tag--accent" />
            <Tag v-else-if="alignmentError" value="加载失败" class="p-tag--warning" />
            <Tag v-else-if="alignmentSummary" :value="`${alignmentSummary.evaluated_decisions}/${alignmentSummary.total_decisions} 已对齐`" class="p-tag--accent" />
          </div>

          <ErrorBlock v-if="alignmentError" :message="alignmentError" />
          <LoadingBlock v-else-if="alignmentLoading && !alignment" />
          <div v-else-if="alignment && alignmentSummary && alignmentSummary.total_decisions > 0" class="quality-dashboard__body">
            <div class="quality-dashboard-grid">
              <div class="quality-metric-card">
                <span>跟随率</span>
                <strong>{{ formatPct(alignmentSummary.alignment_rate) }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>反向率</span>
                <strong>{{ formatPct(alignmentSummary.contradiction_rate) }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>忽略加仓信号</span>
                <strong>{{ alignmentSummary.ignored_add_signal_count }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>手动 override</span>
                <strong>{{ alignmentSummary.manual_override_count }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>行为净值估算</span>
                <strong>{{ formatMoney(alignmentSummary.net_behavior_value) }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>错过机会估算</span>
                <strong>{{ formatMoney(alignmentSummary.estimated_opportunity_cost_total) }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>坏 override 成本</span>
                <strong>{{ formatMoney(alignmentSummary.estimated_bad_override_cost_total) }}</strong>
              </div>
              <div class="quality-metric-card">
                <span>平均延迟</span>
                <strong>{{ alignmentSummary.avg_execution_delay_days ?? '--' }}<small> 天</small></strong>
              </div>
            </div>

            <div class="quality-dashboard-grid quality-dashboard-grid--secondary">
              <div class="quality-top-list">
                <h4>三方对比</h4>
                <ul>
                  <li><span>Shadow Return</span><strong>{{ formatSignedPct(alignmentSummary.shadow_total_return) }}</strong></li>
                  <li><span>Shadow Max DD</span><strong>{{ formatSignedPct(alignmentSummary.shadow_max_drawdown) }}</strong></li>
                  <li><span>Shadow Sharpe</span><strong>{{ alignmentSummary.shadow_sharpe ?? '--' }}</strong></li>
                  <li><span>真实账户估算</span><strong>{{ formatSignedPct(alignmentSummary.real_account_return_estimate) }}</strong></li>
                  <li><span>行为差距估算</span><strong>{{ formatSignedPct(alignmentSummary.behavior_gap_estimate) }}</strong></li>
                </ul>
              </div>

              <div class="quality-top-list">
                <h4>行为偏差分布</h4>
                <ul v-if="topQualityItems(alignmentSummary.by_behavior_tag, 10).length">
                  <li v-for="item in topQualityItems(alignmentSummary.by_behavior_tag, 10)" :key="item.key">
                    <span>{{ behaviorTagLabel(item.key) }}</span>
                    <strong>{{ item.count }}</strong>
                  </li>
                </ul>
                <p v-else>暂无行为偏差标签</p>
              </div>

              <div class="quality-top-list">
                <h4>Top 错过机会</h4>
                <ul v-if="alignmentSummary.top_missed_opportunities.length">
                  <li v-for="item in alignmentSummary.top_missed_opportunities" :key="item.decision_id">
                    <span>{{ item.symbol }} · {{ actionLabel(item.final_action) }}</span>
                    <strong>{{ formatMoney(item.estimated_opportunity_cost) }}</strong>
                  </li>
                </ul>
                <p v-else>暂无明显错过机会</p>
              </div>

              <div class="quality-top-list">
                <h4>Top Override</h4>
                <ul v-if="alignmentSummary.top_bad_overrides.length || alignmentSummary.top_good_overrides.length">
                  <li v-for="item in alignmentSummary.top_bad_overrides.slice(0, 3)" :key="`bad-${item.decision_id}`">
                    <span>{{ item.symbol }} · 坏 override</span>
                    <strong>{{ formatMoney(item.estimated_bad_override_cost) }}</strong>
                  </li>
                  <li v-for="item in alignmentSummary.top_good_overrides.slice(0, 3)" :key="`good-${item.decision_id}`">
                    <span>{{ item.symbol }} · 好 override</span>
                    <strong>{{ formatMoney(item.estimated_good_override_value) }}</strong>
                  </li>
                </ul>
                <p v-else>暂无 override 样本</p>
              </div>
            </div>

            <div class="outcome-table alignment-table">
              <h4>执行对齐明细</h4>
              <div class="outcome-table__header alignment-table__header">
                <span>日期</span>
                <span>标的</span>
                <span>Agent 动作</span>
                <span>真实动作</span>
                <span>对齐</span>
                <span>标签</span>
                <span>20D</span>
                <span>估算影响</span>
                <span>标注</span>
              </div>
              <div
                v-for="item in alignmentItems"
                :key="item.decision_id"
                role="button"
                tabindex="0"
                class="outcome-table__row alignment-table__row"
                @click="selectDecisionById(item.decision_id)"
              >
                <span>{{ item.decision_date || '--' }}</span>
                <strong>{{ item.symbol }}</strong>
                <span>{{ actionLabel(item.final_action) }}</span>
                <span>{{ tradeSideLabel(item.real_trade_side) }} · {{ item.real_trade_count }} 笔</span>
                <Tag :value="alignmentLabel(item.alignment_label)" :class="alignmentClass(item.alignment_label)" />
                <span>{{ item.behavior_tags.map(behaviorTagLabel).join(' / ') || '--' }}</span>
                <span>{{ formatSignedPct(item.return_20d) }}</span>
                <span>{{ formatMoney(item.estimated_good_override_value + item.estimated_avoided_loss - item.estimated_opportunity_cost - item.estimated_bad_override_cost) }}</span>
                <button type="button" class="annotation-link" @click.stop="openAnnotationDialog(item)">
                  {{ hasAnnotationForDecision(item.decision_id) ? '编辑标注' : '标注原因' }}
                </button>
              </div>
            </div>

            <div v-if="alignmentSummary.data_limitations.length" class="holding-hint holding-hint--warning">
              <Tag value="对齐说明" class="p-tag--warning" />
              <span>{{ alignmentSummary.data_limitations.join(' · ') }}</span>
            </div>
          </div>
          <div v-else class="empty-state">暂无可对齐的交易决策或真实交易数据。</div>
        </div>
      </section>
    </template>

    <div v-if="annotationDialogVisible && annotationTarget" class="annotation-modal" role="dialog" aria-modal="true">
      <div class="annotation-modal__backdrop" @click="closeAnnotationDialog"></div>
      <form class="annotation-modal__panel" @submit.prevent="saveAnnotation">
        <div class="section-header">
          <div>
            <h3 class="panel-title">{{ annotationTarget.symbol }} override 标注</h3>
            <p class="panel-subtitle">{{ annotationTarget.decision_date || '--' }} · {{ alignmentLabel(annotationTarget.alignment_label) }} · 标注用于复盘，不会强制改变 Agent 决策。</p>
          </div>
          <button type="button" class="annotation-modal__close" @click="closeAnnotationDialog">×</button>
        </div>

        <ErrorBlock v-if="annotationDialogError" :message="annotationDialogError" />

        <div class="annotation-form-grid">
          <label>
            <span>Override 类型</span>
            <input v-model="annotationForm.override_type" type="text" maxlength="120" placeholder="manual_contrarian_buy" />
          </label>
          <label>
            <span>原因分类</span>
            <select v-model="annotationForm.reason_category">
              <option value="emotion">情绪</option>
              <option value="capital_constraint">资金限制</option>
              <option value="external_information">外部信息</option>
              <option value="disagree_with_agent">不同意 Agent</option>
              <option value="risk_control">主动风控</option>
              <option value="forgot">忘记执行</option>
              <option value="execution_issue">执行问题</option>
              <option value="tax_or_cashflow">税务/现金流</option>
              <option value="other">其他</option>
            </select>
          </label>
          <label>
            <span>信心</span>
            <select v-model="annotationForm.confidence">
              <option value="high">高</option>
              <option value="medium">中</option>
              <option value="low">低</option>
            </select>
          </label>
          <label>
            <span>标签（逗号分隔，最多 20 个）</span>
            <input v-model="annotationForm.tags_text" type="text" placeholder="追涨, 情绪交易" />
          </label>
        </div>

        <label class="annotation-field">
          <span>当时原因</span>
          <textarea v-model="annotationForm.reason_text" maxlength="2000" rows="4" placeholder="当时为什么没有执行 / 反向执行 / 部分执行？"></textarea>
        </label>

        <div class="annotation-checks">
          <label><input v-model="annotationForm.was_intentional" type="checkbox" /> 有意识 override</label>
          <label><input v-model="annotationForm.was_emotional" type="checkbox" /> 有情绪因素</label>
          <label><input v-model="annotationForm.should_remind_next_time" type="checkbox" /> 下次提醒我</label>
        </div>

        <label class="annotation-field">
          <span>经验教训 / 下次提醒</span>
          <textarea v-model="annotationForm.lesson" maxlength="2000" rows="3" placeholder="例如：不能只因为盘前上涨就追买。"></textarea>
        </label>

        <p class="policy-disclaimer">行为画像用于复盘；estimated cost/value 是模型估算，不是真实账户 PnL；人工标注帮助未来复盘，不会自动下单或强制覆盖 Agent。</p>

        <div class="annotation-modal__actions">
          <Button v-if="hasAnnotationForDecision(annotationTarget.decision_id)" type="button" label="删除标注" severity="secondary" :disabled="annotationSaving" @click="deleteAnnotation" />
          <Button type="button" label="取消" severity="secondary" :disabled="annotationSaving" @click="closeAnnotationDialog" />
          <Button type="submit" :label="annotationSaving ? '保存中…' : '保存标注'" :disabled="annotationSaving" />
        </div>
      </form>
    </div>
  </section>
</template>

<style scoped>
.trade-decision-title {
  margin: 0;
  font-size: 1.55rem;
}

.decision-health,
.decision-tags,
.source-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
  min-width: 0;
}

.decision-health,
.decision-tags {
  max-width: min(420px, 100%);
}

.decision-tags {
  align-content: flex-start;
}

.source-row--left {
  justify-content: flex-start;
}

.holding-hint {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: var(--space-3);
  padding: 10px 14px;
  border-radius: var(--radius-md);
  background: rgba(32, 79, 129, 0.32);
  color: var(--color-text-secondary);
  font-size: 0.9rem;
}

.holding-hint--warning {
  background: rgba(255, 180, 84, 0.12);
}

.score-card,
.advice-card,
.insight-block {
  padding: 16px;
  border: 1px solid rgba(129, 160, 207, 0.12);
  border-radius: var(--radius-md);
  background: rgba(10, 18, 32, 0.58);
}

.advice-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.behavior-reminder-card {
  gap: 12px;
}

.behavior-reminder-list {
  display: grid;
  gap: 10px;
  margin: 10px 0 0;
  padding: 0;
  list-style: none;
}

.behavior-reminder-list li {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  color: var(--color-text-secondary);
}

.decision-list small,
.decision-list__quality,
.score-card p,
.advice-card span,
.insight-block li,
.quality-check-card span,
.quality-summary__text,
.quality-list li {
  color: var(--color-text-secondary);
}

.insight-block li.limitation-info {
  color: var(--color-accent, #81a0cf);
  font-style: italic;
}

.entry-form {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) auto;
  gap: var(--space-3);
  align-items: end;
}

.decision-action-grid {
  display: grid;
  grid-template-columns: minmax(300px, 0.45fr) minmax(0, 1fr);
  gap: var(--space-4);
  align-items: start;
}

.decision-mode-card {
  cursor: pointer;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}

.decision-mode-card:focus-visible,
.decision-mode-card.is-active {
  border-color: rgba(86, 213, 255, 0.44);
  box-shadow: 0 0 0 1px rgba(86, 213, 255, 0.18), var(--color-surface-glow);
}

.decision-mode-card:hover {
  transform: translateY(-1px);
}

.decision-composer {
  display: grid;
  min-width: 0;
}

.decision-composer .surface-panel__content,
.decision-research .surface-panel__content {
  display: grid;
  gap: var(--space-3);
}

.decision-composer .entry-form {
  grid-template-columns: 1fr;
}

.decision-composer .entry-form__actions {
  min-width: 0;
}

.decision-research {
  min-width: 0;
}

.decision-research :deep(.symbol-analysis-page > .surface-panel:first-child),
.decision-research :deep(.symbol-analysis-page > .surface-panel:first-child > .surface-panel__content) {
  overflow: visible;
}

.decision-research :deep(.symbol-analysis-page) {
  gap: var(--space-4);
}

.decision-research :deep(.symbol-analysis-page > .surface-panel:first-child) {
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.decision-research :deep(.symbol-analysis-page > .surface-panel:first-child::after) {
  display: none;
}

.decision-research :deep(.symbol-analysis-page > .surface-panel:first-child > .surface-panel__content) {
  padding: 0;
}

.entry-form__actions {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  min-width: 180px;
  min-height: 46px;
  max-height: 46px;
  overflow: visible;
}

.runner-list {
  display: grid;
  gap: 10px;
}

.runner-item {
  display: block;
  width: 100%;
  padding: 12px 14px;
  border: 1px solid rgba(129, 160, 207, 0.14);
  border-radius: var(--radius-md);
  background: rgba(10, 18, 32, 0.58);
}

.runner-item__summary {
  display: grid;
  grid-template-columns: 12px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  width: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--color-text-primary);
  cursor: pointer;
  text-align: left;
}

.runner-item__dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: var(--color-accent);
}

.runner-item--queued .runner-item__dot,
.runner-item--running .runner-item__dot {
  animation: runner-pulse 1.2s ease-in-out infinite;
}

.runner-item--completed .runner-item__dot {
  background: var(--color-positive);
}

.runner-item--failed .runner-item__dot {
  background: var(--color-negative);
}

.runner-item__main {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.runner-item__main span,
.runner-item__meta span {
  color: var(--color-text-secondary);
}

.runner-item__meta {
  display: flex;
  align-items: center;
  gap: 10px;
}

.runner-item__actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}

.local-task-steps {
  display: grid;
  gap: 10px;
  margin-top: 12px;
}

.local-task-step {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid rgba(129, 160, 207, 0.12);
  border-radius: var(--radius-md);
  background: rgba(10, 18, 32, 0.42);
}

.local-task-step span:nth-child(2) {
  color: var(--color-text-secondary);
  overflow-wrap: anywhere;
}

.local-task-step--completed .runner-item__dot {
  background: var(--color-positive);
}

.local-task-step--failed .runner-item__dot {
  background: var(--color-negative);
}

.local-task-step--queued .runner-item__dot,
.local-task-step--running .runner-item__dot {
  animation: runner-pulse 1.2s ease-in-out infinite;
}

@keyframes runner-pulse {
  0%,
  100% {
    opacity: 0.45;
  }
  50% {
    opacity: 1;
  }
}

:deep(.entry-generate-button) {
  flex: 0 0 auto;
  width: 180px;
  height: 44px;
  min-height: 44px;
  max-height: 44px;
}

.decision-layout {
  display: grid;
  grid-template-columns: minmax(300px, 0.8fr) minmax(0, 1.2fr);
  gap: var(--space-4);
}

.decision-list {
  display: grid;
  gap: 10px;
}

.decision-list button {
  display: grid;
  gap: 6px;
  width: 100%;
  padding: 14px;
  border: 1px solid rgba(129, 160, 207, 0.14);
  border-radius: var(--radius-md);
  background: rgba(10, 18, 32, 0.62);
  color: var(--color-text-primary);
  cursor: pointer;
  text-align: left;
}

.decision-list button:not(.list-toggle-button).is-active,
.decision-list button:not(.list-toggle-button):hover {
  border-color: rgba(86, 213, 255, 0.34);
  background: rgba(19, 42, 70, 0.82);
}

.decision-list__quality {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-size: 0.84rem;
}

.list-toggle-button {
  justify-items: center;
  color: var(--color-accent-strong);
  font-weight: 700;
  text-align: center;
}

.decision-detail-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) max-content;
  align-items: flex-start;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}

.decision-detail-header > div:first-child {
  min-width: 0;
}

.decision-detail-header .panel-subtitle {
  overflow-wrap: anywhere;
}

.decision-detail-header h3 {
  margin: 0;
  font-size: 3rem;
}

.decision-detail-header h3 span {
  font-size: 1.1rem;
  color: var(--color-text-secondary);
}

.score-grid,
.advice-grid,
.insight-grid {
  display: grid;
  gap: var(--space-3);
}

.score-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.detail-card {
  display: grid;
  gap: 10px;
  margin-bottom: var(--space-4);
  padding: 16px;
  border: 1px solid rgba(129, 160, 207, 0.12);
  border-radius: var(--radius-md);
  background: rgba(10, 18, 32, 0.58);
}

.detail-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.detail-card h4,
.detail-card p {
  margin: 0;
}

.detail-card p {
  color: var(--color-text-secondary);
  line-height: 1.7;
}

.quality-panel {
  margin-top: var(--space-4);
}

.quality-dashboard__body,
.quality-panel__body {
  display: grid;
  gap: var(--space-3);
}

.quality-dashboard-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
}

.quality-dashboard-grid--secondary {
  align-items: start;
}

.quality-metric-card,
.quality-distribution,
.quality-top-list,
.quality-trend-list {
  padding: 14px;
  border: 1px solid rgba(129, 160, 207, 0.12);
  border-radius: var(--radius-md);
  background: rgba(10, 18, 32, 0.52);
}

.quality-metric-card {
  display: grid;
  gap: 8px;
  min-height: 96px;
  align-content: center;
}

.quality-metric-card span,
.quality-top-list p,
.quality-trend-item span,
.quality-trend-item small {
  color: var(--color-text-secondary);
}

.quality-metric-card strong {
  font-size: 1.65rem;
  line-height: 1;
}

.quality-metric-card small {
  font-size: 0.95rem;
  color: var(--color-text-secondary);
}

.quality-distribution,
.quality-top-list,
.quality-trend-list {
  display: grid;
  gap: 10px;
}

.quality-distribution h4,
.quality-top-list h4,
.quality-trend-list h4 {
  margin: 0;
}

.quality-distribution__item,
.quality-top-list li,
.quality-trend-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  min-width: 0;
}

.quality-distribution__item span,
.quality-top-list li span {
  color: var(--color-text-secondary);
  overflow-wrap: anywhere;
}

.quality-top-list ul {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.quality-top-list p {
  margin: 0;
}

.quality-trend-list {
  overflow: hidden;
}

.quality-trend-item {
  grid-template-columns: minmax(86px, 0.8fr) minmax(120px, 1fr) auto minmax(100px, 1fr) minmax(140px, 1fr);
  padding: 10px 0;
  border-top: 1px solid rgba(129, 160, 207, 0.1);
}

.quality-trend-item:first-of-type {
  border-top: 0;
}

.quality-trend-item > * {
  min-width: 0;
  overflow-wrap: anywhere;
}

.outcome-table {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.outcome-table h4 {
  margin: 0;
}

.outcome-table__header,
.outcome-table__row {
  display: grid;
  grid-template-columns: 0.8fr 1fr 1fr 1.8fr 0.7fr 0.7fr 0.7fr 0.7fr 1fr;
  gap: 10px;
  align-items: center;
}

.outcome-table__header {
  padding: 0 12px;
  color: var(--color-text-secondary);
  font-size: 0.76rem;
}

.outcome-table__row {
  width: 100%;
  border: 1px solid rgba(129, 160, 207, 0.14);
  border-radius: var(--radius-md);
  padding: 10px 12px;
  color: var(--color-text-secondary);
  background: rgba(10, 18, 32, 0.62);
  text-align: left;
  cursor: pointer;
}

.outcome-table__row:hover {
  border-color: rgba(86, 213, 255, 0.34);
  background: rgba(19, 42, 70, 0.82);
}

.outcome-table__row strong {
  color: var(--color-text-primary);
}

.backtest-controls {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
  align-items: end;
  padding: 12px;
  border: 1px solid rgba(129, 160, 207, 0.14);
  border-radius: var(--radius-md);
  background: rgba(10, 18, 32, 0.48);
}

.backtest-controls label {
  display: grid;
  gap: 6px;
  min-width: 0;
  color: var(--color-text-secondary);
  font-size: 0.82rem;
}

.backtest-controls input,
.backtest-controls select {
  width: 100%;
  border: 1px solid rgba(129, 160, 207, 0.2);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  color: var(--color-text-primary);
  background: rgba(8, 15, 28, 0.9);
}

.backtest-controls__check {
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
}

.backtest-controls__check input {
  width: auto;
}

.backtest-chart {
  display: grid;
  gap: 10px;
  padding: 14px;
  border: 1px solid rgba(129, 160, 207, 0.14);
  border-radius: var(--radius-md);
  background: rgba(10, 18, 32, 0.5);
}

.backtest-chart__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: var(--color-text-secondary);
}

.backtest-chart__head h4 {
  margin: 0;
  color: var(--color-text-primary);
}

.backtest-sparkline {
  display: grid;
  grid-template-columns: repeat(16, minmax(0, 1fr));
  align-items: end;
  gap: 6px;
  height: 120px;
}

.backtest-sparkline__bar {
  min-height: 4px;
  border-radius: 4px 4px 0 0;
  background: linear-gradient(180deg, rgba(86, 213, 255, 0.95), rgba(55, 125, 255, 0.45));
}

.backtest-trade-table__header,
.backtest-trade-table__row {
  grid-template-columns: 1fr 0.8fr 1fr 0.8fr 0.8fr 0.9fr 0.8fr minmax(160px, 1.6fr);
}

.backtest-trade-table__row {
  cursor: default;
}

.alignment-table__header,
.alignment-table__row {
  grid-template-columns: 1fr 0.8fr 1fr 1fr 0.9fr minmax(160px, 1.7fr) 0.7fr 1fr 0.9fr;
}

.behavior-insight-list {
  display: grid;
  gap: 10px;
}

.annotation-link {
  justify-self: start;
  border: 1px solid rgba(86, 213, 255, 0.28);
  border-radius: var(--radius-sm);
  padding: 6px 10px;
  color: var(--color-accent-strong);
  background: rgba(86, 213, 255, 0.08);
  cursor: pointer;
  font-weight: 700;
}

.annotation-link:hover {
  border-color: rgba(86, 213, 255, 0.52);
}

.annotation-modal {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  place-items: center;
  padding: 20px;
}

.annotation-modal__backdrop {
  position: absolute;
  inset: 0;
  background: rgba(2, 8, 18, 0.72);
  backdrop-filter: blur(8px);
}

.annotation-modal__panel {
  position: relative;
  z-index: 1;
  display: grid;
  gap: var(--space-3);
  width: min(760px, 100%);
  max-height: min(86vh, 860px);
  overflow: auto;
  padding: 20px;
  border: 1px solid rgba(129, 160, 207, 0.2);
  border-radius: var(--radius-md);
  background: rgba(8, 15, 28, 0.98);
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.42);
}

.annotation-modal__close {
  width: 36px;
  height: 36px;
  border: 1px solid rgba(129, 160, 207, 0.2);
  border-radius: var(--radius-sm);
  color: var(--color-text-primary);
  background: rgba(10, 18, 32, 0.72);
  cursor: pointer;
  font-size: 1.3rem;
}

.annotation-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.annotation-form-grid label,
.annotation-field {
  display: grid;
  gap: 6px;
  min-width: 0;
  color: var(--color-text-secondary);
  font-size: 0.86rem;
}

.annotation-form-grid input,
.annotation-form-grid select,
.annotation-field textarea {
  width: 100%;
  border: 1px solid rgba(129, 160, 207, 0.2);
  border-radius: var(--radius-sm);
  padding: 9px 10px;
  color: var(--color-text-primary);
  background: rgba(5, 10, 20, 0.9);
}

.annotation-field textarea {
  resize: vertical;
}

.annotation-checks,
.annotation-modal__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.annotation-checks label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--color-text-secondary);
}

.annotation-modal__actions {
  justify-content: flex-end;
}

.quality-summary {
  display: grid;
  grid-template-columns: minmax(110px, 0.28fr) minmax(0, 1fr);
  gap: var(--space-3);
  align-items: stretch;
}

.quality-summary__score {
  display: grid;
  gap: 6px;
  align-content: center;
  padding: 14px;
  border: 1px solid rgba(129, 160, 207, 0.12);
  border-radius: var(--radius-md);
  background: rgba(15, 30, 52, 0.64);
}

.quality-summary__score span,
.quality-flags > span,
.quality-list > span {
  color: var(--color-text-primary);
  font-weight: 700;
}

.quality-summary__score strong {
  font-size: 2rem;
  line-height: 1;
}

.quality-summary__score small {
  font-size: 0.95rem;
  color: var(--color-text-secondary);
}

.quality-summary__text {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.quality-summary__text p,
.quality-summary__text small {
  margin: 0;
  overflow-wrap: anywhere;
}

.quality-list {
  display: grid;
  gap: 8px;
  padding: 12px 14px;
  border: 1px solid rgba(129, 160, 207, 0.12);
  border-radius: var(--radius-md);
  background: rgba(10, 18, 32, 0.42);
}

.quality-list ul {
  display: grid;
  gap: 6px;
  margin: 0;
  padding-left: 18px;
}

.quality-list--danger {
  border-color: rgba(255, 105, 112, 0.24);
  background: rgba(110, 30, 38, 0.16);
}

.quality-list--warning {
  border-color: rgba(255, 180, 84, 0.24);
  background: rgba(123, 79, 20, 0.14);
}

.quality-flags {
  display: grid;
  gap: 8px;
}

.quality-flags > div {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.quality-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
}

.quality-check-card {
  display: grid;
  gap: 8px;
  padding: 14px;
  border: 1px solid rgba(129, 160, 207, 0.12);
  border-radius: var(--radius-md);
  background: rgba(10, 18, 32, 0.46);
}

.quality-check-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.quality-check-card__head strong {
  min-width: 0;
  overflow-wrap: anywhere;
}

.detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.detail-list {
  display: grid;
  gap: 6px;
  color: var(--color-text-secondary);
}

.detail-list > span {
  color: var(--color-text-primary);
  font-weight: 700;
}

.detail-list ul {
  display: grid;
  gap: 6px;
  margin: 0;
  padding-left: 18px;
}

.score-card__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.score-card p {
  margin: 0;
}

.score-card--full {
  grid-column: 1 / -1;
}

.score-card__reason-wrap {
  position: relative;
}

.score-card__reason {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  overflow-wrap: anywhere;
  line-height: 1.6;
  margin: 0;
}

.score-card__tooltip {
  position: absolute;
  left: 0;
  top: calc(100% + 10px);
  z-index: 50;
  display: none;
  width: min(720px, calc(100vw - 80px));
  padding: 12px 14px;
  border: 1px solid rgba(129, 160, 207, 0.28);
  border-radius: var(--radius-md);
  background: rgba(8, 15, 28, 0.98);
  color: var(--color-text-primary);
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.42);
  line-height: 1.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  pointer-events: none;
}

.score-card__reason-wrap:hover .score-card__tooltip {
  display: block;
}

.score-card--full .score-card__tooltip {
  width: min(900px, calc(100vw - 80px));
}

.advice-grid,
.insight-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: var(--space-4);
}

.advice-card {
  display: grid;
  gap: 8px;
}

.advice-card h4,
.insight-block h4 {
  margin: 0 0 8px;
}

.advice-card ul,
.insight-block ul {
  display: grid;
  gap: 8px;
  margin: 0;
  padding-left: 18px;
}

.policy-disclaimer {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: 0.88rem;
  line-height: 1.5;
}

.source-row {
  justify-content: flex-start;
  margin-top: var(--space-4);
}

@media (max-width: 1200px) {
  .decision-layout,
  .decision-action-grid,
  .entry-form {
    grid-template-columns: 1fr;
  }

  .quality-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .quality-dashboard-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .quality-dashboard-grid--secondary,
  .quality-trend-item,
  .backtest-controls,
  .backtest-trade-table__header,
  .backtest-trade-table__row,
  .outcome-table__header,
  .outcome-table__row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .score-grid,
  .advice-grid,
  .insight-grid,
  .quality-grid,
  .quality-dashboard-grid,
  .quality-summary,
  .annotation-form-grid {
    grid-template-columns: 1fr;
  }

  .score-card--full {
    grid-column: auto;
  }

  .score-card__tooltip {
    display: none !important;
  }

  .decision-detail-header {
    display: grid;
    grid-template-columns: 1fr;
  }

  .decision-tags {
    justify-content: flex-start;
  }
}
</style>
