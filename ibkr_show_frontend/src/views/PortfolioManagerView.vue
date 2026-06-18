<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Tag from 'primevue/tag'

import {
  disablePortfolioUniverseSymbol,
  excludePortfolioUniverseSymbol,
  fetchInvestmentConstitution,
  fetchPortfolioActionAlert,
  fetchPortfolioActionAlerts,
  fetchPortfolioAutoDecisionRun,
  fetchPortfolioAutoDecisionRuns,
  fetchPortfolioDailyLoopRun,
  fetchPortfolioDailyLoopRuns,
  fetchPortfolioDailyLoopScheduleStatus,
  fetchPortfolioUniverse,
  fetchPortfolioWatchtowerRun,
  fetchPortfolioWatchtowerRuns,
  fetchPortfolioManagerReport,
  fetchPortfolioManagerReports,
  fetchPortfolioEvaluationResults,
  fetchPortfolioEvaluationSummary,
  fetchPortfolioEvaluationSymbolHistory,
  fetchPortfolioImprovementReport,
  fetchPortfolioImprovementReports,
  generatePortfolioManagerReport,
  generatePortfolioImprovementReport,
  resetInvestmentConstitution,
  runPortfolioAutoDecisions,
  runPortfolioDailyLoop,
  runPortfolioDailyLoopScheduled,
  runPortfolioEvaluation,
  runPortfolioWatchtower,
  sendPortfolioActionAlertsForDailyLoop,
  syncPortfolioUniverseHoldings,
  updateInvestmentConstitution,
  upsertPortfolioUniverseSymbol,
} from '@/api/portfolioManager'
import ErrorBlock from '@/components/ErrorBlock.vue'
import LoadingBlock from '@/components/LoadingBlock.vue'
import PerformanceBenchmarkPanel from '@/components/PerformanceBenchmarkPanel.vue'
import { useAccountOverviewData } from '@/composables/accountOverview'
import type {
  AIThemeRole,
  AutoDecisionRunStatus,
  AutoDecisionSelectionStatus,
  DecisionFrequency,
  InvestmentConstitution,
  InvestmentConstitutionPayload,
  PortfolioActionAlert,
  PortfolioActionAlertRunResult,
  PortfolioAutoDecisionItem,
  PortfolioAutoDecisionRun,
  PortfolioAutoDecisionRunDetail,
  PortfolioDailyLoopRun,
  PortfolioDailyLoopScheduleStatus,
  PortfolioManagerReport,
  PortfolioEvaluationHorizon,
  PortfolioEvaluationResult,
  PortfolioEvaluationSourceType,
  PortfolioEvaluationSummary,
  PortfolioImprovementReport,
  PortfolioWatchtowerRun,
  PortfolioWatchtowerRunDetail,
  PortfolioWatchtowerItem,
  ScanFrequency,
  UniversePriority,
  UniverseSymbol,
  UniverseSymbolPayload,
  UniverseType,
  WatchtowerItemStatus,
  WatchtowerSeverity,
} from '@/types/portfolioManager'

type PortfolioTab = 'dailyLoop' | 'constitution' | 'universe' | 'watchtower' | 'autoDecision' | 'portfolioReport' | 'actionAlerts' | 'marketEvaluation' | 'systemImprovement' | 'baselineLab'

const activeTab = ref<PortfolioTab>('dailyLoop')
const { overview: accountOverview, ensureLoaded: ensureAccountOverviewLoaded } = useAccountOverviewData()
const loading = ref(true)
const saving = ref(false)
const syncing = ref(false)
const errorMessage = ref('')
const noticeMessage = ref('')
const constitution = ref<InvestmentConstitution | null>(null)
const universe = ref<UniverseSymbol[]>([])
const watchtowerRuns = ref<PortfolioWatchtowerRun[]>([])
const selectedWatchtowerRun = ref<PortfolioWatchtowerRunDetail | null>(null)
const watchtowerLoading = ref(false)
const watchtowerRunDate = ref('')
const autoDecisionRuns = ref<PortfolioAutoDecisionRun[]>([])
const selectedAutoDecisionRun = ref<PortfolioAutoDecisionRunDetail | null>(null)
const autoDecisionLoading = ref(false)
const autoDecisionWatchtowerRunId = ref('')
const autoDecisionRunDate = ref('')
const autoDecisionMaxDecisions = ref(5)
const autoDecisionDryRun = ref(true)
const autoDecisionForceRefresh = ref(false)
const portfolioReports = ref<PortfolioManagerReport[]>([])
const selectedPortfolioReport = ref<PortfolioManagerReport | null>(null)
const portfolioReportLoading = ref(false)
const portfolioReportDate = ref('')
const portfolioReportWatchtowerRunId = ref('')
const portfolioReportAutoDecisionRunId = ref('')
const evaluationLoading = ref(false)
const evaluationResults = ref<PortfolioEvaluationResult[]>([])
const evaluationSummary = ref<PortfolioEvaluationSummary | null>(null)
const evaluationHorizons = ref('1d,5d,20d,60d,120d,1y')
const evaluationSourceTypes = ref('watchtower_item,auto_decision_item,portfolio_report')
const evaluationLookbackDays = ref(180)
const evaluationBenchmarkSymbol = ref('SPY')
const evaluationDate = ref('')
const evaluationSymbol = ref('')
const evaluationSymbolHistory = ref<PortfolioEvaluationResult[]>([])
const improvementLoading = ref(false)
const improvementReports = ref<PortfolioImprovementReport[]>([])
const selectedImprovementReport = ref<PortfolioImprovementReport | null>(null)
const improvementReportDate = ref('')
const improvementLookbackDays = ref(180)
const improvementHorizons = ref('5d,20d,60d')
const improvementMinSampleSize = ref(5)
const dailyLoopLoading = ref(false)
const dailyLoopRuns = ref<PortfolioDailyLoopRun[]>([])
const selectedDailyLoopRun = ref<PortfolioDailyLoopRun | null>(null)
const dailyLoopRunDate = ref('')
const dailyLoopMaxAutoDecisions = ref(5)
const dailyLoopDryRunAutoDecision = ref(false)
const dailyLoopForceRefreshAutoDecision = ref(false)
const dailyLoopRunEvaluation = ref(false)
const dailyLoopGenerateImprovement = ref(false)
const dailyLoopBackground = ref(true)
const dailyLoopTaskId = ref('')
const dailyLoopScheduleStatus = ref<PortfolioDailyLoopScheduleStatus | null>(null)
const dailyLoopScheduleForce = ref(false)
const dailyLoopScheduleBackground = ref(true)
const actionAlertsLoading = ref(false)
const actionAlerts = ref<PortfolioActionAlert[]>([])
const selectedActionAlert = ref<PortfolioActionAlert | null>(null)
const actionAlertRunDate = ref('')
const actionAlertSymbol = ref('')
const actionAlertStatus = ref('')
const actionAlertType = ref('')
const actionAlertDailyLoopRunId = ref('')
const actionAlertSendResult = ref<PortfolioActionAlertRunResult | null>(null)
const showSymbolForm = ref(false)
const editingSymbol = ref('')

const universeTypes: UniverseType[] = ['holding', 'watchlist', 'candidate', 'excluded']
const aiThemeRoles: AIThemeRole[] = [
  'core_compute',
  'semiconductor',
  'data_center',
  'cloud_platform',
  'ai_infrastructure',
  'ai_application',
  'power_and_cooling',
  'memory_and_networking',
  'indirect_beneficiary',
  'non_ai',
  'fake_ai_story',
  'unknown',
]
const priorities: UniversePriority[] = ['high', 'medium', 'low']
const scanFrequencies: ScanFrequency[] = ['daily', 'weekly', 'monthly', 'disabled']
const decisionFrequencies: DecisionFrequency[] = ['event_driven', 'daily_if_triggered', 'weekly', 'monthly', 'manual_only', 'disabled']

const constitutionForm = reactive({
  constitution_version: '',
  target_account_value_usd: 1500000,
  target_date: '2035-12-31',
  starting_capital_usd: 90000,
  primary_theme: 'AI',
  primary_theme_description: '',
  primary_theme_buckets: '',
  allow_future_deposits: true,
  deposits_count_as_primary_driver: false,
  core_time_horizon_years: 10,
  short_term_volatility_policy: '',
  decision_principles: '',
  forbidden_behaviors: '',
  risk_constraints: '',
  enabled: true,
})

const filters = reactive({
  universe_type: '',
  enabled: '',
  priority: '',
  ai_theme_role: '',
})

const symbolForm = reactive({
  symbol: '',
  display_symbol: '',
  name: '',
  universe_type: 'watchlist' as UniverseType,
  theme_tags: 'AI',
  ai_theme_role: 'unknown' as AIThemeRole,
  priority: 'medium' as UniversePriority,
  enabled: true,
  scan_frequency: 'weekly' as ScanFrequency,
  decision_frequency: 'event_driven' as DecisionFrequency,
  max_llm_runs_per_week: 3,
  source: 'manual' as const,
  notes: '',
  excluded_reason: '',
})

const enabledCount = computed(() => universe.value.filter((item) => item.enabled).length)
const latestWatchtowerRun = computed(() => watchtowerRuns.value[0] || null)
const watchtowerItems = computed<PortfolioWatchtowerItem[]>(() => selectedWatchtowerRun.value?.items || [])
const latestAutoDecisionRun = computed(() => autoDecisionRuns.value[0] || null)
const autoDecisionItems = computed<PortfolioAutoDecisionItem[]>(() => selectedAutoDecisionRun.value?.items || [])
const latestPortfolioReport = computed(() => portfolioReports.value[0] || null)
const latestImprovementReport = computed(() => improvementReports.value[0] || null)
const latestDailyLoopRun = computed(() => dailyLoopRuns.value[0] || null)
const dailyLoopScheduleEnabledLabel = computed(() => dailyLoopScheduleStatus.value?.enabled ? 'enabled' : 'disabled')
const latestActionAlert = computed(() => actionAlerts.value[0] || null)

function linesToList(value: string): string[] {
  return value
    .split('\n')
    .flatMap((line) => line.split(','))
    .map((item) => item.trim())
    .filter(Boolean)
}

function listToLines(value: string[]): string {
  return value.join('\n')
}

function formatDateTime(value: string): string {
  if (!value) return '--'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function applyConstitution(value: InvestmentConstitution): void {
  constitution.value = value
  constitutionForm.constitution_version = value.constitution_version
  constitutionForm.target_account_value_usd = value.target_account_value_usd
  constitutionForm.target_date = value.target_date
  constitutionForm.starting_capital_usd = value.starting_capital_usd
  constitutionForm.primary_theme = value.primary_theme
  constitutionForm.primary_theme_description = value.primary_theme_description
  constitutionForm.primary_theme_buckets = listToLines(value.primary_theme_buckets)
  constitutionForm.allow_future_deposits = value.allow_future_deposits
  constitutionForm.deposits_count_as_primary_driver = value.deposits_count_as_primary_driver
  constitutionForm.core_time_horizon_years = value.core_time_horizon_years
  constitutionForm.short_term_volatility_policy = value.short_term_volatility_policy
  constitutionForm.decision_principles = listToLines(value.decision_principles)
  constitutionForm.forbidden_behaviors = listToLines(value.forbidden_behaviors)
  constitutionForm.risk_constraints = Object.entries(value.risk_constraints)
    .map(([key, enabled]) => `${key}: ${enabled ? 'true' : 'false'}`)
    .join('\n')
  constitutionForm.enabled = value.enabled
}

function parseRiskConstraints(value: string): Record<string, boolean> {
  const result: Record<string, boolean> = {}
  linesToList(value).forEach((line) => {
    const [key, rawValue] = line.split(':').map((item) => item.trim())
    if (key) {
      result[key] = !['false', '0', 'no'].includes((rawValue || 'true').toLowerCase())
    }
  })
  return result
}

async function loadData(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    try {
      await ensureAccountOverviewLoaded()
    } catch {
      // Baseline Lab can fall back to all-time data if account overview is unavailable.
    }
    const [constitutionResponse, universeResponse] = await Promise.all([
      fetchInvestmentConstitution(),
      fetchPortfolioUniverse(),
    ])
    applyConstitution(constitutionResponse)
    universe.value = universeResponse
    await loadDailyLoopScheduleStatus()
    await loadDailyLoopRuns()
    await loadActionAlerts()
    await loadWatchtowerRuns()
    await loadAutoDecisionRuns()
    await loadPortfolioReports()
    await loadEvaluation()
    await loadImprovementReports()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载组合经理配置失败'
  } finally {
    loading.value = false
  }
}

async function saveConstitution(): Promise<void> {
  saving.value = true
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const payload: InvestmentConstitutionPayload = {
      constitution_version: constitutionForm.constitution_version.trim(),
      target_account_value_usd: Number(constitutionForm.target_account_value_usd),
      target_date: constitutionForm.target_date.trim(),
      starting_capital_usd: Number(constitutionForm.starting_capital_usd),
      primary_theme: constitutionForm.primary_theme.trim(),
      primary_theme_description: constitutionForm.primary_theme_description.trim(),
      primary_theme_buckets: linesToList(constitutionForm.primary_theme_buckets),
      allow_future_deposits: constitutionForm.allow_future_deposits,
      deposits_count_as_primary_driver: constitutionForm.deposits_count_as_primary_driver,
      core_time_horizon_years: Number(constitutionForm.core_time_horizon_years),
      short_term_volatility_policy: constitutionForm.short_term_volatility_policy.trim(),
      decision_principles: linesToList(constitutionForm.decision_principles),
      forbidden_behaviors: linesToList(constitutionForm.forbidden_behaviors),
      risk_constraints: parseRiskConstraints(constitutionForm.risk_constraints),
      enabled: constitutionForm.enabled,
    }
    applyConstitution(await updateInvestmentConstitution(payload))
    noticeMessage.value = '投资宪法已保存'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '保存投资宪法失败'
  } finally {
    saving.value = false
  }
}

async function restoreDefaultConstitution(): Promise<void> {
  saving.value = true
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    applyConstitution(await resetInvestmentConstitution())
    noticeMessage.value = '已恢复默认投资宪法'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '恢复默认投资宪法失败'
  } finally {
    saving.value = false
  }
}

async function loadUniverse(): Promise<void> {
  errorMessage.value = ''
  try {
    universe.value = await fetchPortfolioUniverse({
      universe_type: filters.universe_type,
      enabled: filters.enabled === '' ? null : filters.enabled === 'true',
      priority: filters.priority,
      ai_theme_role: filters.ai_theme_role,
    })
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载股票池失败'
  }
}

function resetSymbolForm(): void {
  editingSymbol.value = ''
  symbolForm.symbol = ''
  symbolForm.display_symbol = ''
  symbolForm.name = ''
  symbolForm.universe_type = 'watchlist'
  symbolForm.theme_tags = 'AI'
  symbolForm.ai_theme_role = 'unknown'
  symbolForm.priority = 'medium'
  symbolForm.enabled = true
  symbolForm.scan_frequency = 'weekly'
  symbolForm.decision_frequency = 'event_driven'
  symbolForm.max_llm_runs_per_week = 3
  symbolForm.notes = ''
  symbolForm.excluded_reason = ''
}

function openCreateSymbolForm(): void {
  resetSymbolForm()
  showSymbolForm.value = true
}

function openEditSymbolForm(item: UniverseSymbol): void {
  editingSymbol.value = item.symbol
  symbolForm.symbol = item.symbol
  symbolForm.display_symbol = item.display_symbol
  symbolForm.name = item.name
  symbolForm.universe_type = item.universe_type
  symbolForm.theme_tags = item.theme_tags.join('\n')
  symbolForm.ai_theme_role = item.ai_theme_role
  symbolForm.priority = item.priority
  symbolForm.enabled = item.enabled
  symbolForm.scan_frequency = item.scan_frequency
  symbolForm.decision_frequency = item.decision_frequency
  symbolForm.max_llm_runs_per_week = item.max_llm_runs_per_week
  symbolForm.notes = item.notes
  symbolForm.excluded_reason = item.excluded_reason || ''
  showSymbolForm.value = true
}

async function saveSymbol(): Promise<void> {
  saving.value = true
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const symbol = (editingSymbol.value || symbolForm.symbol).trim().toUpperCase()
    const payload: UniverseSymbolPayload = {
      symbol: symbolForm.symbol.trim().toUpperCase(),
      display_symbol: symbolForm.display_symbol.trim() || symbolForm.symbol.trim().toUpperCase(),
      name: symbolForm.name.trim(),
      universe_type: symbolForm.universe_type,
      theme_tags: linesToList(symbolForm.theme_tags),
      ai_theme_role: symbolForm.ai_theme_role,
      priority: symbolForm.priority,
      enabled: symbolForm.enabled,
      scan_frequency: symbolForm.scan_frequency,
      decision_frequency: symbolForm.decision_frequency,
      max_llm_runs_per_week: Number(symbolForm.max_llm_runs_per_week),
      source: 'manual',
      notes: symbolForm.notes.trim(),
      excluded_reason: symbolForm.excluded_reason.trim() || null,
    }
    await upsertPortfolioUniverseSymbol(symbol, payload)
    showSymbolForm.value = false
    noticeMessage.value = `${symbol} 已保存`
    await loadUniverse()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '保存股票池标的失败'
  } finally {
    saving.value = false
  }
}

async function disableSymbol(item: UniverseSymbol): Promise<void> {
  saving.value = true
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    await disablePortfolioUniverseSymbol(item.symbol)
    noticeMessage.value = `${item.symbol} 已禁用`
    await loadUniverse()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '禁用标的失败'
  } finally {
    saving.value = false
  }
}

async function excludeSymbol(item: UniverseSymbol): Promise<void> {
  const reason = window.prompt(`请输入排除 ${item.symbol} 的原因`, item.excluded_reason || '')
  if (reason === null) return
  saving.value = true
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    await excludePortfolioUniverseSymbol(item.symbol, reason, item.notes)
    noticeMessage.value = `${item.symbol} 已标记为 excluded`
    await loadUniverse()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '标记 excluded 失败'
  } finally {
    saving.value = false
  }
}

async function syncHoldings(): Promise<void> {
  syncing.value = true
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const result = await syncPortfolioUniverseHoldings()
    noticeMessage.value = result.message
    await loadUniverse()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '同步当前持仓失败'
  } finally {
    syncing.value = false
  }
}

async function loadWatchtowerRuns(): Promise<void> {
  watchtowerLoading.value = true
  errorMessage.value = ''
  try {
    watchtowerRuns.value = await fetchPortfolioWatchtowerRuns({ limit: 20 })
    if (watchtowerRuns.value.length) {
      selectedWatchtowerRun.value = await fetchPortfolioWatchtowerRun(watchtowerRuns.value[0].id)
      if (!autoDecisionWatchtowerRunId.value) autoDecisionWatchtowerRunId.value = watchtowerRuns.value[0].id
      if (!portfolioReportWatchtowerRunId.value) portfolioReportWatchtowerRunId.value = watchtowerRuns.value[0].id
    } else {
      selectedWatchtowerRun.value = null
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载每日巡检失败'
  } finally {
    watchtowerLoading.value = false
  }
}

async function loadAutoDecisionRuns(): Promise<void> {
  autoDecisionLoading.value = true
  errorMessage.value = ''
  try {
    autoDecisionRuns.value = await fetchPortfolioAutoDecisionRuns({ limit: 20 })
    if (autoDecisionRuns.value.length) {
      selectedAutoDecisionRun.value = await fetchPortfolioAutoDecisionRun(autoDecisionRuns.value[0].id)
    } else {
      selectedAutoDecisionRun.value = null
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载自动决策失败'
  } finally {
    autoDecisionLoading.value = false
  }
}

async function loadPortfolioReports(): Promise<void> {
  portfolioReportLoading.value = true
  errorMessage.value = ''
  try {
    portfolioReports.value = await fetchPortfolioManagerReports({ limit: 20 })
    if (portfolioReports.value.length) {
      selectedPortfolioReport.value = await fetchPortfolioManagerReport(portfolioReports.value[0].id)
    } else {
      selectedPortfolioReport.value = null
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载组合报告失败'
  } finally {
    portfolioReportLoading.value = false
  }
}

async function loadDailyLoopRuns(): Promise<void> {
  dailyLoopLoading.value = true
  errorMessage.value = ''
  try {
    await loadDailyLoopScheduleStatus()
    dailyLoopRuns.value = await fetchPortfolioDailyLoopRuns({ limit: 20 })
    selectedDailyLoopRun.value = dailyLoopRuns.value.length ? await fetchPortfolioDailyLoopRun(dailyLoopRuns.value[0].id) : null
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载每日闭环失败'
  } finally {
    dailyLoopLoading.value = false
  }
}

async function loadDailyLoopScheduleStatus(): Promise<void> {
  try {
    dailyLoopScheduleStatus.value = await fetchPortfolioDailyLoopScheduleStatus()
  } catch (error) {
    dailyLoopScheduleStatus.value = null
    throw error
  }
}

async function loadActionAlerts(): Promise<void> {
  actionAlertsLoading.value = true
  errorMessage.value = ''
  try {
    actionAlerts.value = await fetchPortfolioActionAlerts({
      limit: 50,
      run_date: actionAlertRunDate.value.trim() || undefined,
      symbol: actionAlertSymbol.value.trim().toUpperCase() || undefined,
      status: actionAlertStatus.value || undefined,
      alert_type: actionAlertType.value || undefined,
    })
    selectedActionAlert.value = actionAlerts.value.length ? await fetchPortfolioActionAlert(actionAlerts.value[0].id) : null
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载行动提醒失败'
  } finally {
    actionAlertsLoading.value = false
  }
}

function parseEvaluationHorizons(): PortfolioEvaluationHorizon[] {
  return evaluationHorizons.value.split(',').map((item) => item.trim()).filter(Boolean) as PortfolioEvaluationHorizon[]
}

function parseEvaluationSourceTypes(): PortfolioEvaluationSourceType[] {
  return evaluationSourceTypes.value.split(',').map((item) => item.trim()).filter(Boolean) as PortfolioEvaluationSourceType[]
}

function parseImprovementHorizons(): PortfolioEvaluationHorizon[] {
  return improvementHorizons.value.split(',').map((item) => item.trim()).filter(Boolean) as PortfolioEvaluationHorizon[]
}

async function loadEvaluation(): Promise<void> {
  evaluationLoading.value = true
  errorMessage.value = ''
  try {
    const horizons = parseEvaluationHorizons().join(',')
    const [summary, results] = await Promise.all([
      fetchPortfolioEvaluationSummary({ lookback_days: Number(evaluationLookbackDays.value), horizons }),
      fetchPortfolioEvaluationResults({ limit: 100 }),
    ])
    evaluationSummary.value = summary
    evaluationResults.value = results
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载市场评测失败'
  } finally {
    evaluationLoading.value = false
  }
}

async function runMarketEvaluation(): Promise<void> {
  evaluationLoading.value = true
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await runPortfolioEvaluation({
      evaluation_date: evaluationDate.value.trim() || null,
      source_types: parseEvaluationSourceTypes(),
      horizons: parseEvaluationHorizons(),
      lookback_days: Number(evaluationLookbackDays.value),
      benchmark_symbol: evaluationBenchmarkSymbol.value.trim() || 'SPY',
      limit: 1000,
    })
    evaluationSummary.value = response.summary
    evaluationResults.value = await fetchPortfolioEvaluationResults({ limit: 100 })
    noticeMessage.value = `市场评测完成：${response.created_or_updated_count} 条，completed ${response.completed_count}，pending ${response.pending_count}`
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '运行市场评测失败'
  } finally {
    evaluationLoading.value = false
  }
}

async function loadEvaluationSymbolHistory(): Promise<void> {
  if (!evaluationSymbol.value.trim()) return
  evaluationLoading.value = true
  errorMessage.value = ''
  try {
    evaluationSymbolHistory.value = await fetchPortfolioEvaluationSymbolHistory(evaluationSymbol.value.trim().toUpperCase(), 100)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载 symbol 评测历史失败'
  } finally {
    evaluationLoading.value = false
  }
}

async function runTodayWatchtower(): Promise<void> {
  watchtowerLoading.value = true
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    selectedWatchtowerRun.value = await runPortfolioWatchtower({
      run_date: watchtowerRunDate.value.trim() || null,
      run_type: 'manual',
      universe_types: ['holding', 'watchlist', 'candidate'],
      force_refresh: false,
    })
    watchtowerRuns.value = await fetchPortfolioWatchtowerRuns({ limit: 20 })
    autoDecisionWatchtowerRunId.value = selectedWatchtowerRun.value.id
    portfolioReportWatchtowerRunId.value = selectedWatchtowerRun.value.id
    noticeMessage.value = `巡检完成：${selectedWatchtowerRun.value.summary.decision_required || 0} 个标的需要深度决策`
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '运行每日巡检失败'
  } finally {
    watchtowerLoading.value = false
  }
}

async function openWatchtowerRun(run: PortfolioWatchtowerRun): Promise<void> {
  watchtowerLoading.value = true
  errorMessage.value = ''
  try {
    selectedWatchtowerRun.value = await fetchPortfolioWatchtowerRun(run.id)
    autoDecisionWatchtowerRunId.value = run.id
    portfolioReportWatchtowerRunId.value = run.id
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载巡检详情失败'
  } finally {
    watchtowerLoading.value = false
  }
}

async function runAutoDecision(): Promise<void> {
  const sourceRunId = autoDecisionWatchtowerRunId.value.trim() || latestWatchtowerRun.value?.id || ''
  if (!sourceRunId) {
    errorMessage.value = '请先输入 watchtower_run_id，或先运行一次每日巡检'
    return
  }
  autoDecisionLoading.value = true
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    selectedAutoDecisionRun.value = await runPortfolioAutoDecisions({
      watchtower_run_id: sourceRunId,
      run_date: autoDecisionRunDate.value.trim() || null,
      run_type: 'manual',
      max_decisions: Number(autoDecisionMaxDecisions.value),
      force_refresh: autoDecisionForceRefresh.value,
      dry_run: autoDecisionDryRun.value,
    })
    autoDecisionRuns.value = await fetchPortfolioAutoDecisionRuns({ limit: 20 })
    portfolioReportAutoDecisionRunId.value = selectedAutoDecisionRun.value.id
    noticeMessage.value = `自动决策完成：completed ${selectedAutoDecisionRun.value.summary.completed} / failed ${selectedAutoDecisionRun.value.summary.failed} / skipped ${selectedAutoDecisionRun.value.summary.skipped}`
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '运行自动决策失败'
  } finally {
    autoDecisionLoading.value = false
  }
}

async function openAutoDecisionRun(run: PortfolioAutoDecisionRun): Promise<void> {
  autoDecisionLoading.value = true
  errorMessage.value = ''
  try {
    selectedAutoDecisionRun.value = await fetchPortfolioAutoDecisionRun(run.id)
    portfolioReportAutoDecisionRunId.value = run.id
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载自动决策详情失败'
  } finally {
    autoDecisionLoading.value = false
  }
}

async function generatePortfolioReport(): Promise<void> {
  portfolioReportLoading.value = true
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    selectedPortfolioReport.value = await generatePortfolioManagerReport({
      report_date: portfolioReportDate.value.trim() || null,
      report_type: 'manual',
      watchtower_run_id: portfolioReportWatchtowerRunId.value.trim() || latestWatchtowerRun.value?.id || null,
      auto_decision_run_id: portfolioReportAutoDecisionRunId.value.trim() || latestAutoDecisionRun.value?.id || null,
    })
    portfolioReports.value = await fetchPortfolioManagerReports({ limit: 20 })
    noticeMessage.value = `组合报告已生成：健康分 ${selectedPortfolioReport.value.portfolio_health_score} / ${selectedPortfolioReport.value.portfolio_health_level}`
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '生成组合报告失败'
  } finally {
    portfolioReportLoading.value = false
  }
}

async function openPortfolioReport(report: PortfolioManagerReport): Promise<void> {
  portfolioReportLoading.value = true
  errorMessage.value = ''
  try {
    selectedPortfolioReport.value = await fetchPortfolioManagerReport(report.id)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载组合报告详情失败'
  } finally {
    portfolioReportLoading.value = false
  }
}

async function runDailyLoop(): Promise<void> {
  dailyLoopLoading.value = true
  errorMessage.value = ''
  noticeMessage.value = ''
  dailyLoopTaskId.value = ''
  try {
    const response = await runPortfolioDailyLoop({
      run_date: dailyLoopRunDate.value.trim() || null,
      run_type: 'manual',
      sync_holdings: true,
      run_watchtower: true,
      run_auto_decision: true,
      generate_portfolio_report: true,
      run_evaluation: dailyLoopRunEvaluation.value,
      generate_improvement_report: dailyLoopGenerateImprovement.value,
      dry_run_auto_decision: dailyLoopDryRunAutoDecision.value,
      max_auto_decisions: Number(dailyLoopMaxAutoDecisions.value),
      force_refresh_auto_decision: dailyLoopForceRefreshAutoDecision.value,
      evaluation_horizons: ['1d', '5d', '20d'],
      evaluation_lookback_days: 180,
      improvement_horizons: ['5d', '20d', '60d'],
      improvement_lookback_days: 180,
      improvement_min_sample_size: 5,
      background: dailyLoopBackground.value,
    })
    dailyLoopTaskId.value = response.task_id || ''
    if (response.run) selectedDailyLoopRun.value = response.run
    dailyLoopRuns.value = await fetchPortfolioDailyLoopRuns({ limit: 20 })
    if (!response.run && response.run_id) {
      selectedDailyLoopRun.value = await fetchPortfolioDailyLoopRun(response.run_id)
    }
    noticeMessage.value = response.background
      ? `每日闭环任务已启动：${response.task_id}`
      : `每日闭环完成：${response.run?.status || 'unknown'}`
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '运行每日闭环失败'
  } finally {
    dailyLoopLoading.value = false
  }
}

async function runScheduledDailyLoop(): Promise<void> {
  dailyLoopLoading.value = true
  errorMessage.value = ''
  noticeMessage.value = ''
  dailyLoopTaskId.value = ''
  try {
    const response = await runPortfolioDailyLoopScheduled({
      run_date: dailyLoopRunDate.value.trim() || null,
      force: dailyLoopScheduleForce.value,
      background: dailyLoopScheduleBackground.value,
    })
    dailyLoopTaskId.value = response.task_id || ''
    if (response.run) selectedDailyLoopRun.value = response.run
    dailyLoopRuns.value = await fetchPortfolioDailyLoopRuns({ limit: 20 })
    if (!response.run && response.run_id) {
      selectedDailyLoopRun.value = await fetchPortfolioDailyLoopRun(response.run_id)
    }
    noticeMessage.value = response.skipped
      ? `调度 run 已跳过：${response.reason || 'dedupe'}，existing_run_id=${response.existing_run_id || response.run_id}`
      : response.background
        ? `调度每日闭环任务已启动：${response.task_id}`
        : `调度每日闭环完成：${response.run?.status || 'unknown'}`
    await loadDailyLoopScheduleStatus()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '运行调度每日闭环失败'
  } finally {
    dailyLoopLoading.value = false
  }
}

async function openDailyLoopRun(run: PortfolioDailyLoopRun): Promise<void> {
  dailyLoopLoading.value = true
  errorMessage.value = ''
  try {
    selectedDailyLoopRun.value = await fetchPortfolioDailyLoopRun(run.id)
    dailyLoopTaskId.value = selectedDailyLoopRun.value.task_id || ''
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载每日闭环详情失败'
  } finally {
    dailyLoopLoading.value = false
  }
}

async function openActionAlert(alert: PortfolioActionAlert): Promise<void> {
  actionAlertsLoading.value = true
  errorMessage.value = ''
  try {
    selectedActionAlert.value = await fetchPortfolioActionAlert(alert.id)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载行动提醒详情失败'
  } finally {
    actionAlertsLoading.value = false
  }
}

async function sendActionAlertsForDailyLoop(): Promise<void> {
  const runId = actionAlertDailyLoopRunId.value.trim() || latestDailyLoopRun.value?.id || ''
  if (!runId) {
    errorMessage.value = '请输入 daily_loop_run_id，或先选择最近 Daily Loop'
    return
  }
  actionAlertsLoading.value = true
  errorMessage.value = ''
  noticeMessage.value = ''
  actionAlertSendResult.value = null
  try {
    actionAlertSendResult.value = await sendPortfolioActionAlertsForDailyLoop(runId)
    actionAlerts.value = await fetchPortfolioActionAlerts({ limit: 50 })
    if (actionAlerts.value.length) selectedActionAlert.value = await fetchPortfolioActionAlert(actionAlerts.value[0].id)
    noticeMessage.value = `行动提醒处理完成：created ${actionAlertSendResult.value.alerts_created} / sent ${actionAlertSendResult.value.alerts_sent} / failed ${actionAlertSendResult.value.alerts_failed}`
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '发送本次行动提醒失败'
  } finally {
    actionAlertsLoading.value = false
  }
}

async function loadImprovementReports(): Promise<void> {
  improvementLoading.value = true
  errorMessage.value = ''
  try {
    improvementReports.value = await fetchPortfolioImprovementReports({ limit: 20 })
    selectedImprovementReport.value = improvementReports.value.length ? await fetchPortfolioImprovementReport(improvementReports.value[0].id) : null
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载系统改进报告失败'
  } finally {
    improvementLoading.value = false
  }
}

async function generateImprovementReport(): Promise<void> {
  improvementLoading.value = true
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    selectedImprovementReport.value = await generatePortfolioImprovementReport({
      report_date: improvementReportDate.value.trim() || null,
      report_type: 'manual',
      lookback_days: Number(improvementLookbackDays.value),
      horizons: parseImprovementHorizons(),
      min_sample_size: Number(improvementMinSampleSize.value),
    })
    improvementReports.value = await fetchPortfolioImprovementReports({ limit: 20 })
    noticeMessage.value = `系统改进报告已生成：${selectedImprovementReport.value.improvement_candidates.length} 条候选建议，全部需要人工确认`
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '生成系统改进报告失败'
  } finally {
    improvementLoading.value = false
  }
}

async function openImprovementReport(report: PortfolioImprovementReport): Promise<void> {
  improvementLoading.value = true
  errorMessage.value = ''
  try {
    selectedImprovementReport.value = await fetchPortfolioImprovementReport(report.id)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载系统改进报告详情失败'
  } finally {
    improvementLoading.value = false
  }
}

function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--'
  return `${(value * 100).toFixed(1)}%`
}

function statusClass(status: WatchtowerItemStatus | WatchtowerRunStatusLike | string): string {
  if (status === 'decision_required' || status === 'failed') return 'p-tag--negative'
  if (status === 'attention_required' || status === 'partial_success' || status === 'skipped' || status === 'running') return 'p-tag--warning'
  if (status === 'watch' || status === 'cancelled') return 'p-tag--accent'
  if (status === 'success') return 'p-tag--positive'
  return ''
}

function severityClass(severity: WatchtowerSeverity): string {
  if (severity === 'high') return 'p-tag--negative'
  if (severity === 'medium') return 'p-tag--warning'
  if (severity === 'low') return 'p-tag--accent'
  return ''
}

function autoSelectionClass(status: AutoDecisionSelectionStatus | AutoDecisionRunStatus): string {
  if (status === 'failed') return 'p-tag--negative'
  if (status === 'skipped' || status === 'partial_success' || status === 'selected') return 'p-tag--warning'
  if (status === 'completed' || status === 'success') return 'p-tag--positive'
  return ''
}

function decisionSummaryValue(item: PortfolioAutoDecisionItem, key: string): string {
  const value = item.decision_summary?.[key]
  if (value === null || value === undefined || value === '') return '--'
  if (typeof value === 'number') return key.includes('pct') ? formatPct(value) : String(value)
  return String(value)
}

function money(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--'
  return `$${value.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
}

function objectEntries(value: Record<string, unknown> | undefined): Array<[string, unknown]> {
  return Object.entries(value || {})
}

type WatchtowerRunStatusLike = 'success' | 'partial_success' | 'failed'

onMounted(() => {
  void loadData()
})
</script>

<template>
  <section class="page-section portfolio-manager-page">
    <section class="surface-panel">
      <div class="surface-panel__content">
        <div class="section-header portfolio-manager-page__header">
          <div>
            <p class="eyebrow">PORTFOLIO MANAGER</p>
            <h2 class="panel-title">组合经理</h2>
            <p class="panel-subtitle">围绕 2035 年 150 万美元账户目标和 AI 主线，维护闭环交易系统的长期约束与每日股票池。</p>
          </div>
          <Tag :value="`${enabledCount} ENABLED`" class="p-tag--accent" />
        </div>
      </div>
    </section>

    <LoadingBlock v-if="loading" />
    <ErrorBlock v-else-if="errorMessage" :message="errorMessage" />

    <template v-else>
      <p v-if="noticeMessage" class="portfolio-notice">{{ noticeMessage }}</p>

      <section class="surface-panel">
        <div class="surface-panel__content">
          <div class="portfolio-tabs">
            <Button label="每日闭环" icon="pi pi-sync" class="terminal-nav__button" :class="{ 'is-active': activeTab === 'dailyLoop' }" @click="activeTab = 'dailyLoop'" />
            <Button label="投资宪法" icon="pi pi-shield" class="terminal-nav__button" :class="{ 'is-active': activeTab === 'constitution' }" @click="activeTab = 'constitution'" />
            <Button label="股票池" icon="pi pi-list-check" class="terminal-nav__button" :class="{ 'is-active': activeTab === 'universe' }" @click="activeTab = 'universe'" />
            <Button label="每日巡检" icon="pi pi-eye" class="terminal-nav__button" :class="{ 'is-active': activeTab === 'watchtower' }" @click="activeTab = 'watchtower'" />
            <Button label="自动决策" icon="pi pi-bolt" class="terminal-nav__button" :class="{ 'is-active': activeTab === 'autoDecision' }" @click="activeTab = 'autoDecision'" />
            <Button label="组合报告" icon="pi pi-chart-pie" class="terminal-nav__button" :class="{ 'is-active': activeTab === 'portfolioReport' }" @click="activeTab = 'portfolioReport'" />
            <Button label="行动提醒" icon="pi pi-envelope" class="terminal-nav__button" :class="{ 'is-active': activeTab === 'actionAlerts' }" @click="activeTab = 'actionAlerts'" />
            <Button label="市场评测" icon="pi pi-chart-line" class="terminal-nav__button" :class="{ 'is-active': activeTab === 'marketEvaluation' }" @click="activeTab = 'marketEvaluation'" />
            <Button label="系统改进" icon="pi pi-wrench" class="terminal-nav__button" :class="{ 'is-active': activeTab === 'systemImprovement' }" @click="activeTab = 'systemImprovement'" />
            <Button label="基准实验室" icon="pi pi-chart-bar" class="terminal-nav__button" :class="{ 'is-active': activeTab === 'baselineLab' }" @click="activeTab = 'baselineLab'" />
          </div>
        </div>
      </section>

      <section v-if="activeTab === 'dailyLoop'" class="portfolio-universe-layout">
        <section class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <div>
                <h3 class="panel-title">每日闭环</h3>
                <p class="panel-subtitle">一键串起 Universe Sync、Watchtower、Auto Decision 和 Portfolio Review；不会自动下单，Auto Decision 只生成 Trade Decision 建议，所有最终动作仍需人工确认。</p>
              </div>
              <div class="form-actions">
                <label class="watchtower-run-date"><span>Run date</span><InputText v-model="dailyLoopRunDate" placeholder="YYYY-MM-DD，可空" /></label>
                <label class="watchtower-run-date"><span>Max decisions</span><input v-model.number="dailyLoopMaxAutoDecisions" type="number" min="0" max="100" /></label>
                <label class="checkbox-inline"><input v-model="dailyLoopDryRunAutoDecision" type="checkbox" /> Dry run auto decision</label>
                <label class="checkbox-inline"><input v-model="dailyLoopForceRefreshAutoDecision" type="checkbox" /> Force refresh</label>
                <label class="checkbox-inline"><input v-model="dailyLoopRunEvaluation" type="checkbox" /> Run evaluation</label>
                <label class="checkbox-inline"><input v-model="dailyLoopGenerateImprovement" type="checkbox" /> Generate improvement</label>
                <label class="checkbox-inline"><input v-model="dailyLoopBackground" type="checkbox" /> Background</label>
                <Button label="运行一键闭环" icon="pi pi-play" class="p-button--accent" :loading="dailyLoopLoading" @click="runDailyLoop" />
                <Button label="刷新" icon="pi pi-refresh" severity="secondary" :loading="dailyLoopLoading" @click="loadDailyLoopRuns" />
              </div>
            </div>
            <div class="reason-list">
              <span>不会自动下单</span>
              <span>不会自动修改规则</span>
              <span>Improvement 只生成待人工确认建议</span>
              <span v-if="dailyLoopTaskId">task_id: {{ dailyLoopTaskId }}</span>
            </div>
          </div>
        </section>

        <section class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <div>
                <h3 class="panel-title">Scheduled Daily Loop</h3>
                <p class="panel-subtitle">调度入口使用后端默认配置串起 Universe Sync、Watchtower、Auto Decision 和 Portfolio Review；默认不跑 Evaluation / Improvement，且不会自动下单或自动应用系统规则。</p>
              </div>
              <div class="form-actions">
                <label class="checkbox-inline"><input v-model="dailyLoopScheduleForce" type="checkbox" /> Force scheduled rerun</label>
                <label class="checkbox-inline"><input v-model="dailyLoopScheduleBackground" type="checkbox" /> Background</label>
                <Button label="触发调度闭环" icon="pi pi-calendar-clock" class="p-button--accent" :loading="dailyLoopLoading" @click="runScheduledDailyLoop" />
                <Button label="刷新调度状态" icon="pi pi-refresh" severity="secondary" :loading="dailyLoopLoading" @click="loadDailyLoopScheduleStatus" />
              </div>
            </div>
            <div v-if="dailyLoopScheduleStatus" class="portfolio-report-grid daily-loop-schedule-grid">
              <div>
                <h4>Schedule</h4>
                <p>{{ dailyLoopScheduleEnabledLabel }}</p>
                <small>{{ dailyLoopScheduleStatus.schedule_time }} · {{ dailyLoopScheduleStatus.schedule_timezone }}</small>
              </div>
              <div>
                <h4>Next Run</h4>
                <p>{{ dailyLoopScheduleStatus.next_run_hint || '--' }}</p>
                <small>由外部 cron / internal API 触发</small>
              </div>
              <div>
                <h4>Auto Decision</h4>
                <p>{{ dailyLoopScheduleStatus.max_auto_decisions }}</p>
                <small>dry_run {{ dailyLoopScheduleStatus.dry_run_auto_decision ? 'on' : 'off' }} · force_refresh {{ dailyLoopScheduleStatus.force_refresh_auto_decision ? 'on' : 'off' }}</small>
              </div>
              <div>
                <h4>Optional</h4>
                <p>{{ dailyLoopScheduleStatus.run_evaluation ? 'evaluation on' : 'evaluation off' }}</p>
                <small>{{ dailyLoopScheduleStatus.generate_improvement_report ? 'improvement on' : 'improvement off' }}</small>
              </div>
            </div>
            <div class="reason-list daily-loop-schedule-notes">
              <span>scheduled run 会按 run_date + run_type=scheduled 去重；已有 running / success / partial_success 时默认跳过</span>
              <span>Force scheduled rerun 只绕过去重，不改变自动下单和人工确认边界</span>
              <span>内部触发需要配置 X-Internal-Token；未配置 token 时匿名内部调用会被拒绝</span>
            </div>
          </div>
        </section>

        <section class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <h3 class="panel-title">Daily Loop Runs</h3>
              <Tag v-if="latestDailyLoopRun" :value="latestDailyLoopRun.status" :class="statusClass(latestDailyLoopRun.status)" />
            </div>
            <div class="portfolio-table-wrap">
              <table class="portfolio-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Status</th>
                    <th>Task</th>
                    <th>Watchtower</th>
                    <th>Auto Decision</th>
                    <th>Portfolio Report</th>
                    <th>Health</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="run in dailyLoopRuns" :key="run.id" class="clickable-row" @click="openDailyLoopRun(run)">
                    <td>{{ run.run_date }}</td>
                    <td><Tag :value="run.status" :class="statusClass(run.status)" /></td>
                    <td>{{ run.task_id || '--' }}</td>
                    <td>{{ run.linked_run_ids.watchtower_run_id || '--' }}</td>
                    <td>{{ run.summary.auto_decision_completed || 0 }} / {{ run.summary.auto_decision_failed || 0 }}</td>
                    <td>{{ run.linked_run_ids.portfolio_report_id || '--' }}</td>
                    <td>{{ run.summary.portfolio_health_score ?? '--' }}<small>{{ run.summary.portfolio_health_level || '--' }}</small></td>
                    <td>{{ formatDateTime(run.created_at) }}</td>
                  </tr>
                </tbody>
              </table>
              <div v-if="!dailyLoopRuns.length" class="empty-state">暂无每日闭环 run</div>
            </div>
          </div>
        </section>

        <section v-if="selectedDailyLoopRun" class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <div>
                <h3 class="panel-title">Run Detail</h3>
                <p class="panel-subtitle">{{ selectedDailyLoopRun.id }}</p>
              </div>
              <Tag :value="selectedDailyLoopRun.status" :class="statusClass(selectedDailyLoopRun.status)" />
            </div>
            <div class="portfolio-report-grid">
              <div>
                <h4>Watchtower</h4>
                <p>{{ selectedDailyLoopRun.summary.watchtower_decision_required || 0 }}</p>
                <small>{{ selectedDailyLoopRun.linked_run_ids.watchtower_run_id || 'no run id' }}</small>
              </div>
              <div>
                <h4>Auto Decision</h4>
                <p>{{ selectedDailyLoopRun.summary.auto_decision_completed || 0 }} / {{ selectedDailyLoopRun.summary.auto_decision_failed || 0 }}</p>
                <small>{{ selectedDailyLoopRun.linked_run_ids.auto_decision_run_id || 'no run id' }}</small>
              </div>
              <div>
                <h4>Portfolio</h4>
                <p>{{ selectedDailyLoopRun.summary.portfolio_health_score ?? '--' }}</p>
                <small>{{ selectedDailyLoopRun.summary.portfolio_health_level || '--' }}</small>
              </div>
              <div>
                <h4>Optional</h4>
                <p>{{ selectedDailyLoopRun.summary.evaluation_results_updated || 0 }} / {{ selectedDailyLoopRun.summary.improvement_candidates || 0 }}</p>
                <small>evaluation / improvement</small>
              </div>
            </div>

            <div class="portfolio-table-wrap">
              <table class="portfolio-table evaluation-results-table">
                <thead>
                  <tr>
                    <th>Step</th>
                    <th>Status</th>
                    <th>Duration</th>
                    <th>Run ID</th>
                    <th>Summary</th>
                    <th>Error</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="step in selectedDailyLoopRun.steps" :key="step.step">
                    <td>{{ step.step }}</td>
                    <td><Tag :value="step.status" :class="statusClass(step.status)" /></td>
                    <td>{{ step.duration_ms ?? 0 }} ms</td>
                    <td>{{ step.run_id || '--' }}</td>
                    <td>
                      <small v-for="[key, value] in objectEntries(step.summary)" :key="`${step.step}-${key}`">{{ key }}: {{ value }}</small>
                    </td>
                    <td>{{ step.error_message || '--' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="portfolio-report-columns">
              <div>
                <h4>Linked Run IDs</h4>
                <div class="reason-list">
                  <span v-for="[key, value] in objectEntries(selectedDailyLoopRun.linked_run_ids)" :key="`loop-link-${key}`">{{ key }}: {{ value }}</span>
                </div>
              </div>
              <div>
                <h4>Data Limitations</h4>
                <div class="reason-list">
                  <span v-for="item in selectedDailyLoopRun.data_limitations" :key="item">{{ item }}</span>
                  <span v-if="!selectedDailyLoopRun.data_limitations.length">none</span>
                </div>
              </div>
            </div>
          </div>
        </section>
      </section>

      <section v-else-if="activeTab === 'constitution'" class="surface-panel">
        <div class="surface-panel__content">
          <div class="section-header">
            <div>
              <h3 class="panel-title">投资宪法</h3>
              <p class="panel-subtitle">系统最高层长期约束，用于约束组合经理和交易 Agent 不偏离长期目标；不是收益承诺，不构成投资建议。</p>
            </div>
            <Tag :value="constitutionForm.enabled ? 'ENABLED' : 'DISABLED'" :class="constitutionForm.enabled ? 'p-tag--positive' : 'p-tag--negative'" />
          </div>

          <form class="portfolio-form" @submit.prevent="saveConstitution">
            <label><span>目标账户资产 USD</span><input v-model.number="constitutionForm.target_account_value_usd" type="number" /></label>
            <label><span>目标日期</span><InputText v-model="constitutionForm.target_date" /></label>
            <label><span>起始本金 USD</span><input v-model.number="constitutionForm.starting_capital_usd" type="number" /></label>
            <label><span>主线</span><InputText v-model="constitutionForm.primary_theme" /></label>
            <label class="portfolio-form__wide"><span>主线描述</span><textarea v-model="constitutionForm.primary_theme_description" rows="3" /></label>
            <label><span>核心年限</span><input v-model.number="constitutionForm.core_time_horizon_years" type="number" /></label>
            <label><span>宪法版本</span><InputText v-model="constitutionForm.constitution_version" /></label>
            <label class="checkbox-row"><input v-model="constitutionForm.allow_future_deposits" type="checkbox" />允许未来入金</label>
            <label class="checkbox-row"><input v-model="constitutionForm.deposits_count_as_primary_driver" type="checkbox" />把入金作为主要驱动</label>
            <label class="checkbox-row"><input v-model="constitutionForm.enabled" type="checkbox" />启用</label>
            <label class="portfolio-form__wide"><span>短期波动政策</span><textarea v-model="constitutionForm.short_term_volatility_policy" rows="2" /></label>
            <label><span>AI 主线桶</span><textarea v-model="constitutionForm.primary_theme_buckets" rows="8" /></label>
            <label><span>决策原则</span><textarea v-model="constitutionForm.decision_principles" rows="8" /></label>
            <label><span>禁止行为</span><textarea v-model="constitutionForm.forbidden_behaviors" rows="8" /></label>
            <label><span>风险约束</span><textarea v-model="constitutionForm.risk_constraints" rows="8" /></label>

            <div class="form-actions portfolio-form__wide">
              <Button type="submit" label="保存" icon="pi pi-save" class="p-button--accent" :loading="saving" />
              <Button type="button" label="恢复默认" icon="pi pi-refresh" severity="secondary" :loading="saving" @click="restoreDefaultConstitution" />
              <span class="portfolio-disclaimer">{{ constitution?.disclaimer }}</span>
            </div>
          </form>
        </div>
      </section>

      <section v-else-if="activeTab === 'universe'" class="portfolio-universe-layout">
        <section class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <div>
                <h3 class="panel-title">股票池</h3>
                <p class="panel-subtitle">维护 holding / watchlist / candidate / excluded，为后续 Watchtower 和自动决策编排提供每日扫描范围。</p>
              </div>
              <div class="form-actions">
                <Button label="同步当前持仓" icon="pi pi-sync" class="p-button--accent" :loading="syncing" @click="syncHoldings" />
                <Button label="添加观察股" icon="pi pi-plus" severity="secondary" @click="openCreateSymbolForm" />
              </div>
            </div>

            <div class="portfolio-filters">
              <label><span>Type</span><select v-model="filters.universe_type" @change="loadUniverse"><option value="">全部</option><option v-for="item in universeTypes" :key="item" :value="item">{{ item }}</option></select></label>
              <label><span>Enabled</span><select v-model="filters.enabled" @change="loadUniverse"><option value="">全部</option><option value="true">true</option><option value="false">false</option></select></label>
              <label><span>Priority</span><select v-model="filters.priority" @change="loadUniverse"><option value="">全部</option><option v-for="item in priorities" :key="item" :value="item">{{ item }}</option></select></label>
              <label><span>AI role</span><select v-model="filters.ai_theme_role" @change="loadUniverse"><option value="">全部</option><option v-for="item in aiThemeRoles" :key="item" :value="item">{{ item }}</option></select></label>
            </div>

            <div class="portfolio-table-wrap">
              <table class="portfolio-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Type</th>
                    <th>AI theme role</th>
                    <th>Priority</th>
                    <th>Enabled</th>
                    <th>Scan</th>
                    <th>Decision</th>
                    <th>Source</th>
                    <th>Notes</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in universe" :key="item.id">
                    <td><strong>{{ item.display_symbol || item.symbol }}</strong><small>{{ item.name || '--' }}</small></td>
                    <td>{{ item.universe_type }}</td>
                    <td>{{ item.ai_theme_role }}</td>
                    <td>{{ item.priority }}</td>
                    <td><Tag :value="String(item.enabled)" :class="item.enabled ? 'p-tag--positive' : 'p-tag--negative'" /></td>
                    <td>{{ item.scan_frequency }}</td>
                    <td>{{ item.decision_frequency }}</td>
                    <td>{{ item.source }}</td>
                    <td>{{ item.notes || item.excluded_reason || '--' }}</td>
                    <td class="portfolio-table__actions">
                      <Button icon="pi pi-pencil" text rounded title="编辑" @click="openEditSymbolForm(item)" />
                      <Button icon="pi pi-ban" text rounded title="标记 excluded" @click="excludeSymbol(item)" />
                      <Button icon="pi pi-times" text rounded severity="danger" title="禁用" @click="disableSymbol(item)" />
                    </td>
                  </tr>
                </tbody>
              </table>
              <div v-if="!universe.length" class="empty-state">暂无股票池记录</div>
            </div>
          </div>
        </section>

        <section v-if="showSymbolForm" class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <h3 class="panel-title">{{ editingSymbol ? `编辑 ${editingSymbol}` : '添加观察股' }}</h3>
              <Button icon="pi pi-times" text rounded @click="showSymbolForm = false" />
            </div>
            <form class="portfolio-form" @submit.prevent="saveSymbol">
              <label><span>Symbol</span><InputText v-model="symbolForm.symbol" /></label>
              <label><span>Display symbol</span><InputText v-model="symbolForm.display_symbol" /></label>
              <label><span>Name</span><InputText v-model="symbolForm.name" /></label>
              <label><span>Type</span><select v-model="symbolForm.universe_type"><option v-for="item in universeTypes" :key="item" :value="item">{{ item }}</option></select></label>
              <label><span>AI theme role</span><select v-model="symbolForm.ai_theme_role"><option v-for="item in aiThemeRoles" :key="item" :value="item">{{ item }}</option></select></label>
              <label><span>Priority</span><select v-model="symbolForm.priority"><option v-for="item in priorities" :key="item" :value="item">{{ item }}</option></select></label>
              <label><span>Scan frequency</span><select v-model="symbolForm.scan_frequency"><option v-for="item in scanFrequencies" :key="item" :value="item">{{ item }}</option></select></label>
              <label><span>Decision frequency</span><select v-model="symbolForm.decision_frequency"><option v-for="item in decisionFrequencies" :key="item" :value="item">{{ item }}</option></select></label>
              <label><span>Max LLM runs/week</span><input v-model.number="symbolForm.max_llm_runs_per_week" type="number" /></label>
              <label class="checkbox-row"><input v-model="symbolForm.enabled" type="checkbox" />启用</label>
              <label><span>Theme tags</span><textarea v-model="symbolForm.theme_tags" rows="4" /></label>
              <label><span>Notes</span><textarea v-model="symbolForm.notes" rows="4" /></label>
              <label><span>Excluded reason</span><textarea v-model="symbolForm.excluded_reason" rows="4" /></label>
              <div class="form-actions portfolio-form__wide">
                <Button type="submit" label="保存标的" icon="pi pi-save" class="p-button--accent" :loading="saving" />
              </div>
            </form>
          </div>
        </section>
      </section>

      <section v-else-if="activeTab === 'watchtower'" class="portfolio-universe-layout">
        <section class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <div>
                <h3 class="panel-title">每日巡检</h3>
                <p class="panel-subtitle">Watchtower 只做轻量异常发现和 trigger_reason 记录，不给最终买卖建议；PR3 才会基于 decision_required 自动触发 Trade Decision Agent。</p>
              </div>
              <div class="form-actions">
                <label class="watchtower-run-date"><span>Run date</span><InputText v-model="watchtowerRunDate" placeholder="YYYY-MM-DD，可空" /></label>
                <Button label="运行今日巡检" icon="pi pi-play" class="p-button--accent" :loading="watchtowerLoading" @click="runTodayWatchtower" />
                <Button label="刷新" icon="pi pi-refresh" severity="secondary" :loading="watchtowerLoading" @click="loadWatchtowerRuns" />
              </div>
            </div>

            <div v-if="latestWatchtowerRun" class="watchtower-latest">
              <span>最近 run</span>
              <strong>{{ latestWatchtowerRun.run_date }}</strong>
              <Tag :value="latestWatchtowerRun.status" :class="statusClass(latestWatchtowerRun.status)" />
              <span>normal {{ latestWatchtowerRun.summary.normal || 0 }}</span>
              <span>watch {{ latestWatchtowerRun.summary.watch || 0 }}</span>
              <span>attention {{ latestWatchtowerRun.summary.attention_required || 0 }}</span>
              <span>decision {{ latestWatchtowerRun.summary.decision_required || 0 }}</span>
            </div>
          </div>
        </section>

        <section class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <h3 class="panel-title">最近巡检 Runs</h3>
            </div>
            <div class="portfolio-table-wrap">
              <table class="portfolio-table">
                <thead>
                  <tr>
                    <th>Run date</th>
                    <th>Status</th>
                    <th>Summary</th>
                    <th>Top attention</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="run in watchtowerRuns" :key="run.id" class="clickable-row" @click="openWatchtowerRun(run)">
                    <td><strong>{{ run.run_date }}</strong><small>{{ run.run_type }}</small></td>
                    <td><Tag :value="run.status" :class="statusClass(run.status)" /></td>
                    <td>normal {{ run.summary.normal || 0 }} / watch {{ run.summary.watch || 0 }} / attention {{ run.summary.attention_required || 0 }} / decision {{ run.summary.decision_required || 0 }}</td>
                    <td>{{ run.top_attention_symbols.join(', ') || '--' }}</td>
                    <td>{{ formatDateTime(run.created_at) }}</td>
                  </tr>
                </tbody>
              </table>
              <div v-if="!watchtowerRuns.length" class="empty-state">暂无巡检 run</div>
            </div>
          </div>
        </section>

        <section class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <div>
                <h3 class="panel-title">当前 Run Items</h3>
                <p class="panel-subtitle">{{ selectedWatchtowerRun ? `${selectedWatchtowerRun.run_date} · ${selectedWatchtowerRun.id}` : '选择或运行一次巡检后查看明细' }}</p>
              </div>
            </div>
            <div class="portfolio-table-wrap">
              <table class="portfolio-table watchtower-items-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Type</th>
                    <th>AI role</th>
                    <th>Status</th>
                    <th>Severity</th>
                    <th>1D</th>
                    <th>5D</th>
                    <th>20D</th>
                    <th>Up / Down</th>
                    <th>20D DD</th>
                    <th>Weight</th>
                    <th>Unrealized</th>
                    <th>Reasons</th>
                    <th>Next</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in watchtowerItems" :key="item.id" :class="`watchtower-row--${item.status}`">
                    <td><strong>{{ item.display_symbol || item.symbol }}</strong><small>{{ item.name || '--' }}</small></td>
                    <td>{{ item.universe_type }}</td>
                    <td>{{ item.ai_theme_role }}</td>
                    <td><Tag :value="item.status" :class="statusClass(item.status)" /></td>
                    <td><Tag :value="item.severity" :class="severityClass(item.severity)" /></td>
                    <td>{{ formatPct(item.metrics.return_1d) }}</td>
                    <td>{{ formatPct(item.metrics.return_5d) }}</td>
                    <td>{{ formatPct(item.metrics.return_20d) }}</td>
                    <td>{{ item.metrics.consecutive_up_days }} / {{ item.metrics.consecutive_down_days }}</td>
                    <td>{{ formatPct(item.metrics.drawdown_from_20d_high) }}</td>
                    <td>{{ formatPct(item.metrics.position_weight) }}</td>
                    <td>{{ formatPct(item.metrics.unrealized_pnl_pct) }}</td>
                    <td>
                      <div v-if="item.trigger_reasons.length" class="reason-list">
                        <span v-for="reason in item.trigger_reasons" :key="`${item.id}-${reason.code}-${reason.message}`">{{ reason.code }}: {{ reason.message }}</span>
                      </div>
                      <span v-else>--</span>
                    </td>
                    <td><strong>{{ item.suggested_next_step }}</strong><small>{{ item.decision_type_hint || '--' }}</small></td>
                  </tr>
                </tbody>
              </table>
              <div v-if="!watchtowerItems.length" class="empty-state">暂无巡检 item</div>
            </div>
          </div>
        </section>
      </section>

      <section v-else-if="activeTab === 'autoDecision'" class="portfolio-universe-layout">
        <section class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <div>
                <h3 class="panel-title">自动决策</h3>
                <p class="panel-subtitle">Auto Decision Orchestrator 只调度现有 Trade Decision Agent、记录预算与追溯信息；不会自动下单，也不会把 Watchtower trigger 直接变成买卖建议。</p>
              </div>
              <div class="form-actions">
                <label class="watchtower-run-date auto-decision-run-id"><span>Watchtower run</span><InputText v-model="autoDecisionWatchtowerRunId" placeholder="默认使用最近 Watchtower run" /></label>
                <label class="watchtower-run-date"><span>Run date</span><InputText v-model="autoDecisionRunDate" placeholder="YYYY-MM-DD，可空" /></label>
                <label class="watchtower-run-date"><span>Max decisions</span><input v-model.number="autoDecisionMaxDecisions" type="number" min="0" max="50" /></label>
                <label class="checkbox-row"><input v-model="autoDecisionDryRun" type="checkbox" />Dry run</label>
                <label class="checkbox-row"><input v-model="autoDecisionForceRefresh" type="checkbox" />Force refresh</label>
                <Button label="运行自动决策" icon="pi pi-play" class="p-button--accent" :loading="autoDecisionLoading" @click="runAutoDecision" />
                <Button label="刷新" icon="pi pi-refresh" severity="secondary" :loading="autoDecisionLoading" @click="loadAutoDecisionRuns" />
              </div>
            </div>

            <div class="watchtower-latest">
              <span>规则</span>
              <strong>fake_ai_story / non_ai 不自动触发 entry_decision</strong>
              <span>同一 symbol 最近 24 小时 completed 默认去重</span>
              <span>系统规则变更仍需人工确认</span>
            </div>
            <div v-if="latestAutoDecisionRun" class="watchtower-latest auto-decision-latest">
              <span>最近 run</span>
              <strong>{{ latestAutoDecisionRun.run_date }}</strong>
              <Tag :value="latestAutoDecisionRun.status" :class="autoSelectionClass(latestAutoDecisionRun.status)" />
              <span>selected {{ latestAutoDecisionRun.summary.selected }}</span>
              <span>completed {{ latestAutoDecisionRun.summary.completed }}</span>
              <span>failed {{ latestAutoDecisionRun.summary.failed }}</span>
              <span>skipped {{ latestAutoDecisionRun.summary.skipped }}</span>
            </div>
          </div>
        </section>

        <section class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <h3 class="panel-title">最近自动决策 Runs</h3>
            </div>
            <div class="portfolio-table-wrap">
              <table class="portfolio-table auto-decision-runs-table">
                <thead>
                  <tr>
                    <th>Run date</th>
                    <th>Status</th>
                    <th>Source Watchtower</th>
                    <th>Summary</th>
                    <th>Budget</th>
                    <th>Selected</th>
                    <th>Skipped</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="run in autoDecisionRuns" :key="run.id" class="clickable-row" @click="openAutoDecisionRun(run)">
                    <td><strong>{{ run.run_date }}</strong><small>{{ run.run_type }}</small></td>
                    <td><Tag :value="run.status" :class="autoSelectionClass(run.status)" /></td>
                    <td><small>{{ run.source_watchtower_run_id }}</small></td>
                    <td>selected {{ run.summary.selected }} / completed {{ run.summary.completed }} / failed {{ run.summary.failed }} / skipped {{ run.summary.skipped }}</td>
                    <td>{{ run.budget.used_decisions }} / {{ run.budget.max_decisions }}<small>budget skipped {{ run.budget.skipped_by_budget }}</small></td>
                    <td>{{ run.selected_symbols.join(', ') || '--' }}</td>
                    <td>{{ run.skipped_symbols.join(', ') || '--' }}</td>
                    <td>{{ formatDateTime(run.created_at) }}</td>
                  </tr>
                </tbody>
              </table>
              <div v-if="!autoDecisionRuns.length" class="empty-state">暂无自动决策 run</div>
            </div>
          </div>
        </section>

        <section class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <div>
                <h3 class="panel-title">当前自动决策 Items</h3>
                <p class="panel-subtitle">{{ selectedAutoDecisionRun ? `${selectedAutoDecisionRun.run_date} · ${selectedAutoDecisionRun.id}` : '运行或选择一次自动决策后查看明细' }}</p>
              </div>
            </div>
            <div class="portfolio-table-wrap">
              <table class="portfolio-table auto-decision-items-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Type</th>
                    <th>AI role</th>
                    <th>Watchtower</th>
                    <th>Selection</th>
                    <th>Skip reason</th>
                    <th>Decision type</th>
                    <th>Decision ID</th>
                    <th>Final action</th>
                    <th>Target pct</th>
                    <th>Max pct</th>
                    <th>Error</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in autoDecisionItems" :key="item.id" :class="`auto-decision-row--${item.selection_status}`">
                    <td><strong>{{ item.display_symbol || item.symbol }}</strong><small>{{ item.priority }}</small></td>
                    <td>{{ item.universe_type }}</td>
                    <td>{{ item.ai_theme_role }}</td>
                    <td><Tag :value="item.watchtower_status" :class="statusClass(item.watchtower_status)" /><small>{{ item.watchtower_severity }}</small></td>
                    <td><Tag :value="item.selection_status" :class="autoSelectionClass(item.selection_status)" /></td>
                    <td>{{ item.skip_reason || '--' }}</td>
                    <td>{{ item.decision_type || '--' }}</td>
                    <td><span class="mono-id">{{ item.decision_id || '--' }}</span></td>
                    <td>{{ decisionSummaryValue(item, 'final_action') }}</td>
                    <td>{{ decisionSummaryValue(item, 'target_position_pct') }}</td>
                    <td>{{ decisionSummaryValue(item, 'max_position_pct') }}</td>
                    <td>{{ item.error_message || '--' }}</td>
                  </tr>
                </tbody>
              </table>
              <div v-if="!autoDecisionItems.length" class="empty-state">暂无自动决策 item</div>
            </div>
          </div>
        </section>
      </section>

      <section v-else-if="activeTab === 'portfolioReport'" class="portfolio-universe-layout">
        <section class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <div>
                <h3 class="panel-title">组合报告</h3>
                <p class="panel-subtitle">Portfolio Review 只做组合级事实分析、风险排序和复核队列；单标的最终动作仍以 Trade Decision Agent 和人工确认为准，不会自动下单。</p>
              </div>
              <div class="form-actions">
                <label class="watchtower-run-date"><span>Report date</span><InputText v-model="portfolioReportDate" placeholder="YYYY-MM-DD，可空" /></label>
                <label class="watchtower-run-date auto-decision-run-id"><span>Watchtower run</span><InputText v-model="portfolioReportWatchtowerRunId" placeholder="默认最新" /></label>
                <label class="watchtower-run-date auto-decision-run-id"><span>Auto decision run</span><InputText v-model="portfolioReportAutoDecisionRunId" placeholder="默认最新" /></label>
                <Button label="生成组合报告" icon="pi pi-play" class="p-button--accent" :loading="portfolioReportLoading" @click="generatePortfolioReport" />
                <Button label="刷新" icon="pi pi-refresh" severity="secondary" :loading="portfolioReportLoading" @click="loadPortfolioReports" />
              </div>
            </div>
            <div v-if="latestPortfolioReport" class="watchtower-latest">
              <span>最近报告</span>
              <strong>{{ latestPortfolioReport.report_date }}</strong>
              <Tag :value="latestPortfolioReport.status" :class="statusClass(latestPortfolioReport.status)" />
              <span>health {{ latestPortfolioReport.portfolio_health_score }}</span>
              <span>{{ latestPortfolioReport.portfolio_health_level }}</span>
            </div>
          </div>
        </section>

        <section class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <h3 class="panel-title">最近组合报告</h3>
            </div>
            <div class="portfolio-table-wrap">
              <table class="portfolio-table portfolio-report-runs-table">
                <thead>
                  <tr>
                    <th>Report date</th>
                    <th>Status</th>
                    <th>Health</th>
                    <th>Watchtower</th>
                    <th>Auto Decision</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="report in portfolioReports" :key="report.id" class="clickable-row" @click="openPortfolioReport(report)">
                    <td><strong>{{ report.report_date }}</strong><small>{{ report.report_type }}</small></td>
                    <td><Tag :value="report.status" :class="statusClass(report.status)" /></td>
                    <td>{{ report.portfolio_health_score }}<small>{{ report.portfolio_health_level }}</small></td>
                    <td><small>{{ report.source_watchtower_run_id || '--' }}</small></td>
                    <td><small>{{ report.source_auto_decision_run_id || '--' }}</small></td>
                    <td>{{ formatDateTime(report.created_at) }}</td>
                  </tr>
                </tbody>
              </table>
              <div v-if="!portfolioReports.length" class="empty-state">暂无组合报告</div>
            </div>
          </div>
        </section>

        <section v-if="selectedPortfolioReport" class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <div>
                <h3 class="panel-title">报告详情</h3>
                <p class="panel-subtitle">{{ selectedPortfolioReport.summary }}</p>
              </div>
              <Tag :value="`${selectedPortfolioReport.portfolio_health_score} · ${selectedPortfolioReport.portfolio_health_level}`" :class="statusClass(selectedPortfolioReport.status)" />
            </div>

            <div class="portfolio-report-grid">
              <div>
                <h4>2035 目标追踪</h4>
                <p>{{ selectedPortfolioReport.goal_tracking.summary }}</p>
                <small>当前权益 {{ money(selectedPortfolioReport.goal_tracking.current_total_equity_usd) }} · 所需年化 {{ formatPct(selectedPortfolioReport.goal_tracking.required_annual_return) }} · {{ selectedPortfolioReport.goal_tracking.current_path_status }}</small>
              </div>
              <div>
                <h4>AI 主线暴露</h4>
                <p>{{ selectedPortfolioReport.ai_theme_exposure.assessment }}</p>
                <small>AI {{ formatPct(selectedPortfolioReport.ai_theme_exposure.total_ai_exposure_pct) }} · core {{ formatPct(selectedPortfolioReport.ai_theme_exposure.core_ai_exposure_pct) }} · fake {{ formatPct(selectedPortfolioReport.ai_theme_exposure.fake_ai_story_exposure_pct) }}</small>
              </div>
              <div>
                <h4>集中度风险</h4>
                <p>{{ selectedPortfolioReport.concentration_risk.assessment }}</p>
                <small>Top1 {{ formatPct(selectedPortfolioReport.concentration_risk.top1_weight) }} · Top3 {{ formatPct(selectedPortfolioReport.concentration_risk.top3_weight) }} · Top5 {{ formatPct(selectedPortfolioReport.concentration_risk.top5_weight) }}</small>
              </div>
              <div>
                <h4>现金状态</h4>
                <p>{{ selectedPortfolioReport.cash_status.summary }}</p>
                <small>{{ money(selectedPortfolioReport.cash_status.cash_value) }} · {{ formatPct(selectedPortfolioReport.cash_status.cash_pct) }} · {{ selectedPortfolioReport.cash_status.assessment }}</small>
              </div>
            </div>

            <div class="portfolio-report-columns">
              <div>
                <h4>Top Attention</h4>
                <div v-if="selectedPortfolioReport.top_attention_symbols.length" class="reason-list">
                  <span v-for="item in selectedPortfolioReport.top_attention_symbols" :key="`attention-${item.symbol}-${item.reason}`"><strong>{{ item.symbol }}</strong> · {{ item.priority }} · {{ item.reason }}</span>
                </div>
                <span v-else class="empty-state">暂无重点关注</span>
              </div>
              <div>
                <h4>Next Steps</h4>
                <div class="reason-list">
                  <span v-for="step in selectedPortfolioReport.next_steps" :key="step">{{ step }}</span>
                </div>
              </div>
            </div>

            <div class="portfolio-table-wrap">
              <table class="portfolio-table portfolio-report-detail-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Gap</th>
                    <th>Weight</th>
                    <th>AI role</th>
                    <th>Priority</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="gap in selectedPortfolioReport.allocation_gaps" :key="`gap-${gap.symbol}-${gap.gap_type}`">
                    <td><strong>{{ gap.display_symbol || gap.symbol }}</strong></td>
                    <td>{{ gap.gap_type }}</td>
                    <td>{{ formatPct(gap.position_weight) }}</td>
                    <td>{{ gap.ai_theme_role }}</td>
                    <td>{{ gap.priority }}</td>
                    <td>{{ gap.gap_reason }}</td>
                  </tr>
                </tbody>
              </table>
              <div v-if="!selectedPortfolioReport.allocation_gaps.length" class="empty-state">暂无 allocation gap</div>
            </div>

            <div class="portfolio-table-wrap">
              <table class="portfolio-table portfolio-report-detail-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Queue</th>
                    <th>Priority</th>
                    <th>Decision ID</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in selectedPortfolioReport.action_queue" :key="`queue-${item.symbol}-${item.queue_type}`">
                    <td><strong>{{ item.symbol }}</strong></td>
                    <td>{{ item.queue_type }}</td>
                    <td>{{ item.priority }}</td>
                    <td><span class="mono-id">{{ item.linked_decision_id || '--' }}</span></td>
                    <td>{{ item.reason }}</td>
                  </tr>
                </tbody>
              </table>
              <div v-if="!selectedPortfolioReport.action_queue.length" class="empty-state">暂无 action queue</div>
            </div>

            <div v-if="selectedPortfolioReport.data_limitations.length" class="reason-list">
              <span v-for="item in selectedPortfolioReport.data_limitations" :key="item">data limitation: {{ item }}</span>
            </div>
          </div>
        </section>
      </section>

      <section v-else-if="activeTab === 'actionAlerts'" class="portfolio-universe-layout">
        <section class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <div>
                <h3 class="panel-title">行动提醒</h3>
                <p class="panel-subtitle">这里只展示和股票加仓、建仓、减仓、风险复核有关的提醒。它不是系统运行日志，也不是买卖指令。</p>
              </div>
              <div class="form-actions">
                <label class="watchtower-run-date"><span>Run date</span><InputText v-model="actionAlertRunDate" placeholder="YYYY-MM-DD" /></label>
                <label class="watchtower-run-date"><span>Symbol</span><InputText v-model="actionAlertSymbol" placeholder="AMD" /></label>
                <label class="watchtower-run-date"><span>Status</span>
                  <select v-model="actionAlertStatus">
                    <option value="">all</option>
                    <option value="pending">pending</option>
                    <option value="sent">sent</option>
                    <option value="skipped">skipped</option>
                    <option value="failed">failed</option>
                  </select>
                </label>
                <label class="watchtower-run-date"><span>Alert type</span>
                  <select v-model="actionAlertType">
                    <option value="">all</option>
                    <option value="add_position_review">add_position_review</option>
                    <option value="entry_position_review">entry_position_review</option>
                    <option value="reduce_position_review">reduce_position_review</option>
                    <option value="risk_review">risk_review</option>
                  </select>
                </label>
                <Button label="筛选" icon="pi pi-filter" class="p-button--accent" :loading="actionAlertsLoading" @click="loadActionAlerts" />
              </div>
            </div>
            <div class="reason-list daily-loop-schedule-notes">
              <span>不会自动下单，不会自动修改规则，不会调用 LLM 生成新决策</span>
              <span>不会发送 Daily Loop 成功/失败、partial_success、price_history pending 等工程状态噪音</span>
            </div>
          </div>
        </section>

        <section class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <div>
                <h3 class="panel-title">手动补发</h3>
                <p class="panel-subtitle">对某次 Daily Loop 重新提取 actionable alerts 并发送一封 digest 邮件；去重会避免重复发送同一 symbol / alert_type / decision_id。</p>
              </div>
              <div class="form-actions">
                <label class="watchtower-run-date auto-decision-run-id"><span>daily_loop_run_id</span><InputText v-model="actionAlertDailyLoopRunId" :placeholder="latestDailyLoopRun?.id || 'portfolio_daily_loop:...'" /></label>
                <Button label="发送本次行动提醒邮件" icon="pi pi-send" class="p-button--accent" :loading="actionAlertsLoading" @click="sendActionAlertsForDailyLoop" />
              </div>
            </div>
            <div v-if="actionAlertSendResult" class="reason-list daily-loop-schedule-notes">
              <span>created: {{ actionAlertSendResult.alerts_created }} / sent: {{ actionAlertSendResult.alerts_sent }} / skipped: {{ actionAlertSendResult.alerts_skipped }} / failed: {{ actionAlertSendResult.alerts_failed }}</span>
              <span>{{ actionAlertSendResult.email_enabled ? '交易行动提醒邮件已启用' : 'email_disabled：请到邮件设置中开启交易行动提醒邮件' }}</span>
              <span v-for="item in actionAlertSendResult.data_limitations" :key="item">data limitation: {{ item }}</span>
            </div>
          </div>
        </section>

        <section class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <h3 class="panel-title">Action Alerts</h3>
              <Tag v-if="latestActionAlert" :value="latestActionAlert.status" :class="statusClass(latestActionAlert.status)" />
            </div>
            <div class="portfolio-table-wrap">
              <table class="portfolio-table action-alerts-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Symbol</th>
                    <th>Type</th>
                    <th>Title</th>
                    <th>Direction</th>
                    <th>Urgency</th>
                    <th>Confidence</th>
                    <th>Status</th>
                    <th>Email Sent</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="alert in actionAlerts" :key="alert.id" class="clickable-row" @click="openActionAlert(alert)">
                    <td>{{ alert.run_date }}</td>
                    <td>{{ alert.display_symbol }}</td>
                    <td>{{ alert.alert_type }}</td>
                    <td>{{ alert.title }}</td>
                    <td>{{ alert.action_direction }}</td>
                    <td><Tag :value="alert.urgency" :class="severityClass(alert.urgency)" /></td>
                    <td>{{ alert.confidence }}</td>
                    <td><Tag :value="alert.status" :class="statusClass(alert.status)" /></td>
                    <td>{{ alert.email_sent_at ? formatDateTime(alert.email_sent_at) : '--' }}</td>
                  </tr>
                </tbody>
              </table>
              <div v-if="!actionAlerts.length" class="empty-state">暂无行动提醒；没有 actionable alert 时不会发送“今日无提醒”邮件</div>
            </div>
          </div>
        </section>

        <section v-if="selectedActionAlert" class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <div>
                <h3 class="panel-title">提醒详情</h3>
                <p class="panel-subtitle">{{ selectedActionAlert.id }}</p>
              </div>
              <Tag :value="selectedActionAlert.status" :class="statusClass(selectedActionAlert.status)" />
            </div>
            <div class="portfolio-report-grid">
              <div>
                <h4>Action</h4>
                <p>{{ selectedActionAlert.action_direction }}</p>
                <small>{{ selectedActionAlert.alert_type }}</small>
              </div>
              <div>
                <h4>Signal</h4>
                <p>{{ selectedActionAlert.urgency }} / {{ selectedActionAlert.confidence }}</p>
                <small>urgency / confidence</small>
              </div>
              <div>
                <h4>Email</h4>
                <p>{{ selectedActionAlert.email_sent_at ? 'sent' : selectedActionAlert.status }}</p>
                <small>{{ selectedActionAlert.email_error || selectedActionAlert.email_subject || '--' }}</small>
              </div>
              <div>
                <h4>Safety</h4>
                <p>{{ selectedActionAlert.not_an_order ? 'not an order' : 'invalid' }}</p>
                <small>需要人工确认</small>
              </div>
            </div>
            <div class="portfolio-report-columns">
              <div>
                <h4>Reasons</h4>
                <div class="reason-list">
                  <span v-for="item in selectedActionAlert.reason_summary" :key="item">{{ item }}</span>
                  <span v-if="!selectedActionAlert.reason_summary.length">none</span>
                </div>
              </div>
              <div>
                <h4>Suggested User Action</h4>
                <p>{{ selectedActionAlert.suggested_user_action }}</p>
              </div>
            </div>
            <div class="portfolio-report-columns">
              <div>
                <h4>Decision Summary</h4>
                <div class="reason-list">
                  <span v-for="[key, value] in objectEntries(selectedActionAlert.decision_summary)" :key="`alert-decision-${key}`">{{ key }}: {{ value }}</span>
                </div>
              </div>
              <div>
                <h4>Portfolio Context</h4>
                <div class="reason-list">
                  <span v-for="[key, value] in objectEntries(selectedActionAlert.portfolio_context)" :key="`alert-context-${key}`">{{ key }}: {{ value }}</span>
                </div>
              </div>
            </div>
            <div>
              <h4>Linked IDs</h4>
              <div class="reason-list daily-loop-schedule-notes">
                <span v-for="[key, value] in objectEntries(selectedActionAlert.linked_ids)" :key="`alert-link-${key}`">{{ key }}: {{ value }}</span>
              </div>
            </div>
          </div>
        </section>
      </section>

      <section v-else-if="activeTab === 'marketEvaluation'" class="portfolio-universe-layout">
        <section class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <div>
                <h3 class="panel-title">市场评测</h3>
                <p class="panel-subtitle">市场反馈不是标准答案；这里只把未来表现按 horizon 结构化成评测信号，不会自动修改规则，也不会自动下单。</p>
              </div>
              <div class="form-actions">
                <label class="watchtower-run-date"><span>Evaluation date</span><InputText v-model="evaluationDate" placeholder="YYYY-MM-DD，可空" /></label>
                <label class="watchtower-run-date auto-decision-run-id"><span>Horizons</span><InputText v-model="evaluationHorizons" /></label>
                <label class="watchtower-run-date auto-decision-run-id"><span>Source types</span><InputText v-model="evaluationSourceTypes" /></label>
                <label class="watchtower-run-date"><span>Lookback</span><input v-model.number="evaluationLookbackDays" type="number" min="1" max="3650" /></label>
                <label class="watchtower-run-date"><span>Benchmark</span><InputText v-model="evaluationBenchmarkSymbol" /></label>
                <Button label="运行市场评测" icon="pi pi-play" class="p-button--accent" :loading="evaluationLoading" @click="runMarketEvaluation" />
                <Button label="刷新" icon="pi pi-refresh" severity="secondary" :loading="evaluationLoading" @click="loadEvaluation" />
              </div>
            </div>
          </div>
        </section>

        <section class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <h3 class="panel-title">评测 Summary</h3>
            </div>
            <div v-if="evaluationSummary" class="portfolio-report-grid">
              <div>
                <h4>Overall</h4>
                <p>{{ evaluationSummary.completed }} / {{ evaluationSummary.total_results }}</p>
                <small>pending {{ evaluationSummary.pending }} · lookback {{ evaluationSummary.lookback_days }}d</small>
              </div>
              <div>
                <h4>Watchtower</h4>
                <p>{{ formatPct(evaluationSummary.watchtower.useful_attention_rate) }}</p>
                <small>false positive {{ formatPct(evaluationSummary.watchtower.false_positive_rate) }} · decision {{ evaluationSummary.watchtower.decision_required_count || 0 }}</small>
              </div>
              <div>
                <h4>Auto Decision</h4>
                <p>{{ formatPct(evaluationSummary.auto_decision.good_action_rate) }}</p>
                <small>bad {{ formatPct(evaluationSummary.auto_decision.bad_action_rate) }} · pending {{ formatPct(evaluationSummary.auto_decision.pending_rate) }}</small>
              </div>
              <div>
                <h4>Portfolio Report</h4>
                <p>{{ formatPct(evaluationSummary.portfolio_report.attention_symbol_hit_rate) }}</p>
                <small>attention symbol hit rate</small>
              </div>
            </div>
            <div v-if="evaluationSummary" class="portfolio-report-columns">
              <div>
                <h4>By Source</h4>
                <div class="reason-list">
                  <span v-for="[key, value] in objectEntries(evaluationSummary.by_source_type)" :key="`source-${key}`">{{ key }}: {{ value }}</span>
                </div>
              </div>
              <div>
                <h4>By Label</h4>
                <div class="reason-list">
                  <span v-for="[key, value] in objectEntries(evaluationSummary.by_label)" :key="`label-${key}`">{{ key }}: {{ value }}</span>
                </div>
              </div>
            </div>
            <div v-if="!evaluationSummary" class="empty-state">暂无市场评测 summary</div>
          </div>
        </section>

        <section class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <h3 class="panel-title">评测 Results</h3>
            </div>
            <div class="portfolio-table-wrap">
              <table class="portfolio-table evaluation-results-table">
                <thead>
                  <tr>
                    <th>Source</th>
                    <th>Symbol</th>
                    <th>Horizon</th>
                    <th>Source date</th>
                    <th>Status / Action</th>
                    <th>Forward</th>
                    <th>Drawdown</th>
                    <th>Rel Benchmark</th>
                    <th>Label</th>
                    <th>Price</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in evaluationResults" :key="item.id">
                    <td>{{ item.source_type }}</td>
                    <td><strong>{{ item.display_symbol || item.symbol || '--' }}</strong></td>
                    <td>{{ item.horizon }}</td>
                    <td>{{ item.source_date }}</td>
                    <td>{{ item.source_status || '--' }}<small>{{ item.source_action || '--' }}</small></td>
                    <td>{{ formatPct(item.forward_return) }}</td>
                    <td>{{ formatPct(item.max_drawdown) }}</td>
                    <td>{{ formatPct(item.benchmark_relative_return) }}</td>
                    <td><Tag :value="item.evaluation_label" :class="autoSelectionClass(item.evaluation_label === 'pending' ? 'selected' : item.evaluation_label === 'bad_action' ? 'failed' : 'completed')" /></td>
                    <td>{{ item.price_data_status }}</td>
                    <td>{{ item.evaluation_reason }}<small>{{ item.data_limitations.join(', ') }}</small></td>
                  </tr>
                </tbody>
              </table>
              <div v-if="!evaluationResults.length" class="empty-state">暂无评测结果</div>
            </div>
          </div>
        </section>

        <section class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <h3 class="panel-title">Symbol History</h3>
              <div class="form-actions">
                <InputText v-model="evaluationSymbol" placeholder="AMD" />
                <Button label="查询" icon="pi pi-search" severity="secondary" :loading="evaluationLoading" @click="loadEvaluationSymbolHistory" />
              </div>
            </div>
            <div class="portfolio-table-wrap">
              <table class="portfolio-table evaluation-results-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Source</th>
                    <th>Horizon</th>
                    <th>Forward</th>
                    <th>Label</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in evaluationSymbolHistory" :key="`history-${item.id}`">
                    <td>{{ item.evaluation_date }}</td>
                    <td>{{ item.source_type }}</td>
                    <td>{{ item.horizon }}</td>
                    <td>{{ formatPct(item.forward_return) }}</td>
                    <td>{{ item.evaluation_label }}</td>
                    <td>{{ item.evaluation_reason }}</td>
                  </tr>
                </tbody>
              </table>
              <div v-if="!evaluationSymbolHistory.length" class="empty-state">暂无 symbol 评测历史</div>
            </div>
          </div>
        </section>
      </section>

      <section v-else-if="activeTab === 'systemImprovement'" class="portfolio-universe-layout">
        <section class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <div>
                <h3 class="panel-title">系统改进</h3>
                <p class="panel-subtitle">改进报告只把 Market Evaluation 的长期样本转成待人工审核建议；不会自动修改规则，不会调用 LLM，不会自动下单，也不会根据单次结果改系统。</p>
              </div>
              <div class="form-actions">
                <label class="watchtower-run-date"><span>Report date</span><InputText v-model="improvementReportDate" placeholder="YYYY-MM-DD，可空" /></label>
                <label class="watchtower-run-date"><span>Lookback</span><input v-model.number="improvementLookbackDays" type="number" min="1" max="3650" /></label>
                <label class="watchtower-run-date auto-decision-run-id"><span>Horizons</span><InputText v-model="improvementHorizons" /></label>
                <label class="watchtower-run-date"><span>Min sample</span><input v-model.number="improvementMinSampleSize" type="number" min="1" max="1000" /></label>
                <Button label="生成改进报告" icon="pi pi-play" class="p-button--accent" :loading="improvementLoading" @click="generateImprovementReport" />
                <Button label="刷新" icon="pi pi-refresh" severity="secondary" :loading="improvementLoading" @click="loadImprovementReports" />
              </div>
            </div>
            <div class="reason-list">
              <span>所有 candidates 默认 requires_human_approval=true / status=proposed</span>
              <span>建议应先经过 shadow / forward evaluation 验证</span>
            </div>
          </div>
        </section>

        <section class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <h3 class="panel-title">Improvement Reports</h3>
              <Tag v-if="latestImprovementReport" :value="latestImprovementReport.status" :class="statusClass(latestImprovementReport.status)" />
            </div>
            <div class="portfolio-table-wrap">
              <table class="portfolio-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Status</th>
                    <th>Lookback</th>
                    <th>Horizons</th>
                    <th>Patterns</th>
                    <th>High / Med / Low</th>
                    <th>Candidates</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="report in improvementReports" :key="report.id" class="clickable-row" @click="openImprovementReport(report)">
                    <td>{{ report.report_date }}</td>
                    <td><Tag :value="report.status" :class="statusClass(report.status)" /></td>
                    <td>{{ report.lookback_days }}d</td>
                    <td>{{ report.horizons.join(', ') }}</td>
                    <td>{{ report.pattern_summary.total_patterns || 0 }}</td>
                    <td>{{ report.pattern_summary.high_severity_patterns || 0 }} / {{ report.pattern_summary.medium_severity_patterns || 0 }} / {{ report.pattern_summary.low_severity_patterns || 0 }}</td>
                    <td>{{ report.improvement_candidates.length }}</td>
                    <td>{{ formatDateTime(report.created_at) }}</td>
                  </tr>
                </tbody>
              </table>
              <div v-if="!improvementReports.length" class="empty-state">暂无系统改进报告</div>
            </div>
          </div>
        </section>

        <section v-if="selectedImprovementReport" class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <div>
                <h3 class="panel-title">报告详情</h3>
                <p class="panel-subtitle">{{ selectedImprovementReport.recommendation_summary }}</p>
              </div>
              <Tag :value="selectedImprovementReport.status" :class="statusClass(selectedImprovementReport.status)" />
            </div>
            <div class="portfolio-report-grid">
              <div>
                <h4>Patterns</h4>
                <p>{{ selectedImprovementReport.pattern_summary.total_patterns || 0 }}</p>
                <small>high {{ selectedImprovementReport.pattern_summary.high_severity_patterns || 0 }} · medium {{ selectedImprovementReport.pattern_summary.medium_severity_patterns || 0 }} · low {{ selectedImprovementReport.pattern_summary.low_severity_patterns || 0 }}</small>
              </div>
              <div>
                <h4>Candidates</h4>
                <p>{{ selectedImprovementReport.improvement_candidates.length }}</p>
                <small>全部需要人工确认</small>
              </div>
              <div>
                <h4>Evaluation Results</h4>
                <p>{{ selectedImprovementReport.source_evaluation_summary.total_results || 0 }}</p>
                <small>completed {{ selectedImprovementReport.source_evaluation_summary.completed || 0 }} · pending {{ selectedImprovementReport.source_evaluation_summary.pending || 0 }}</small>
              </div>
              <div>
                <h4>Horizons</h4>
                <p>{{ selectedImprovementReport.horizons.join(', ') }}</p>
                <small>min sample {{ improvementMinSampleSize }}</small>
              </div>
            </div>
            <div class="portfolio-report-columns">
              <div>
                <h4>By Source</h4>
                <div class="reason-list">
                  <span v-for="[key, value] in objectEntries(selectedImprovementReport.source_evaluation_summary.by_source_type as Record<string, unknown>)" :key="`improve-source-${key}`">{{ key }}: {{ value }}</span>
                </div>
              </div>
              <div>
                <h4>By Label</h4>
                <div class="reason-list">
                  <span v-for="[key, value] in objectEntries(selectedImprovementReport.source_evaluation_summary.by_label as Record<string, unknown>)" :key="`improve-label-${key}`">{{ key }}: {{ value }}</span>
                </div>
              </div>
            </div>
            <div v-if="selectedImprovementReport.data_limitations.length" class="reason-list">
              <span v-for="item in selectedImprovementReport.data_limitations" :key="item">data limitation: {{ item }}</span>
            </div>
          </div>
        </section>

        <section v-if="selectedImprovementReport" class="surface-panel">
          <div class="surface-panel__content">
            <div class="section-header">
              <h3 class="panel-title">Improvement Candidates</h3>
            </div>
            <div class="portfolio-table-wrap">
              <table class="portfolio-table evaluation-results-table">
                <thead>
                  <tr>
                    <th>Candidate</th>
                    <th>Severity</th>
                    <th>Confidence</th>
                    <th>Module</th>
                    <th>Evidence</th>
                    <th>Approval</th>
                    <th>Suggested Change</th>
                    <th>Impact / Risk</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="candidate in selectedImprovementReport.improvement_candidates" :key="candidate.id">
                    <td><strong>{{ candidate.title }}</strong><small>{{ candidate.candidate_type }} · {{ candidate.status }}</small></td>
                    <td><Tag :value="candidate.severity" :class="severityClass(candidate.severity)" /></td>
                    <td>{{ candidate.confidence }}</td>
                    <td>{{ candidate.affected_module }}<small>{{ candidate.affected_rule_or_component }}</small></td>
                    <td>
                      sample {{ candidate.evidence_summary.sample_size }}
                      <small>{{ candidate.evidence_summary.horizons.join(', ') }} · {{ candidate.evidence_summary.source_type }}</small>
                      <small v-for="[key, value] in objectEntries(candidate.evidence_summary.metrics)" :key="`${candidate.id}-${key}`">{{ key }}: {{ value }}</small>
                    </td>
                    <td>{{ candidate.requires_human_approval ? 'requires human approval' : 'invalid' }}</td>
                    <td>{{ candidate.suggested_change }}</td>
                    <td>{{ candidate.expected_impact }}<small>risk: {{ candidate.risk_of_change }}</small></td>
                  </tr>
                </tbody>
              </table>
              <div v-if="!selectedImprovementReport.improvement_candidates.length" class="empty-state">暂无候选改进建议；样本不足时不会生成强结论</div>
            </div>
          </div>
        </section>
      </section>

      <section v-else-if="activeTab === 'baselineLab'" class="surface-panel">
        <div class="surface-panel__content">
          <div class="section-heading">
            <div>
              <p class="section-kicker">Baseline Lab</p>
              <h2>基准实验室</h2>
              <p class="section-description">本页面用于判断真实账户和 Agent 决策系统是否跑赢简单基准。它不是交易建议，也不会自动下单。</p>
            </div>
          </div>
          <PerformanceBenchmarkPanel detailed :latest-report-date="accountOverview?.report_date ?? null" />
        </div>
      </section>
    </template>
  </section>
</template>

<style scoped>
.portfolio-tabs,
.portfolio-filters,
.form-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
}

.portfolio-notice {
  margin: 0;
  color: var(--color-positive);
}

.portfolio-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.portfolio-form label,
.portfolio-filters label,
.watchtower-run-date {
  display: grid;
  gap: 0.35rem;
  color: var(--color-text-muted);
  font-size: 0.82rem;
}

.portfolio-form__wide {
  grid-column: 1 / -1;
}

.portfolio-form input,
.portfolio-form textarea,
.portfolio-form select,
.portfolio-filters select {
  width: 100%;
}

.portfolio-form textarea,
.portfolio-form select,
.portfolio-filters select {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: rgba(10, 15, 23, 0.72);
  color: var(--color-text);
  padding: 0.7rem 0.8rem;
}

.checkbox-row {
  display: flex !important;
  grid-template-columns: none !important;
  gap: 0.5rem !important;
  align-items: center;
  color: var(--color-text);
}

.checkbox-row input {
  width: auto;
}

.portfolio-disclaimer {
  color: var(--color-text-muted);
  font-size: 0.85rem;
}

.portfolio-universe-layout {
  display: grid;
  gap: 1rem;
}

.portfolio-table-wrap {
  overflow-x: auto;
}

.portfolio-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 980px;
}

.portfolio-table th,
.portfolio-table td {
  border-bottom: 1px solid var(--color-border);
  padding: 0.75rem 0.6rem;
  text-align: left;
  vertical-align: top;
}

.portfolio-table th {
  color: var(--color-text-muted);
  font-size: 0.78rem;
  text-transform: uppercase;
}

.portfolio-table td small {
  display: block;
  color: var(--color-text-muted);
  margin-top: 0.2rem;
}

.portfolio-table__actions {
  white-space: nowrap;
}

.watchtower-latest {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
  color: var(--color-text-muted);
  font-size: 0.9rem;
}

.clickable-row {
  cursor: pointer;
}

.clickable-row:hover {
  background: rgba(93, 220, 255, 0.06);
}

.watchtower-items-table {
  min-width: 1360px;
}

.auto-decision-runs-table {
  min-width: 1280px;
}

.auto-decision-items-table {
  min-width: 1420px;
}

.portfolio-report-runs-table {
  min-width: 1120px;
}

.action-alerts-table {
  min-width: 1260px;
}

.portfolio-report-detail-table {
  min-width: 980px;
  margin-top: 1rem;
}

.evaluation-results-table {
  min-width: 1360px;
}

.portfolio-report-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1rem;
}

.portfolio-report-grid h4,
.portfolio-report-columns h4 {
  margin: 0 0 0.45rem;
}

.portfolio-report-grid p,
.portfolio-report-columns p {
  margin: 0 0 0.35rem;
}

.portfolio-report-grid small {
  color: var(--color-text-muted);
  line-height: 1.35;
}

.daily-loop-schedule-grid {
  margin-top: 1rem;
}

.daily-loop-schedule-notes {
  max-width: none;
  margin-top: 1rem;
}

.portfolio-report-columns {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}

.auto-decision-run-id {
  min-width: 320px;
}

.auto-decision-latest {
  margin-top: 0.75rem;
}

.mono-id {
  font-family: var(--font-mono);
  font-size: 0.8rem;
}

.watchtower-row--decision_required {
  background: rgba(255, 87, 87, 0.08);
}

.watchtower-row--attention_required {
  background: rgba(255, 196, 87, 0.07);
}

.watchtower-row--normal {
  opacity: 0.82;
}

.auto-decision-row--failed {
  background: rgba(255, 87, 87, 0.08);
}

.auto-decision-row--skipped,
.auto-decision-row--selected {
  background: rgba(255, 196, 87, 0.06);
}

.reason-list {
  display: grid;
  gap: 0.3rem;
  max-width: 360px;
}

.reason-list span {
  color: var(--color-text-muted);
  line-height: 1.35;
}

@media (max-width: 820px) {
  .portfolio-form {
    grid-template-columns: 1fr;
  }

  .portfolio-report-grid,
  .portfolio-report-columns {
    grid-template-columns: 1fr;
  }
}
</style>
