<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Tag from 'primevue/tag'

import { backfillBenchmarkPrices, ensurePerformanceBaselinePrices, fetchBenchmarkPriceStatus, fetchPerformanceBaselineSeries } from '@/api/performance'
import ErrorBlock from '@/components/ErrorBlock.vue'
import LoadingBlock from '@/components/LoadingBlock.vue'
import PerformanceDataQualityIndicator from '@/components/PerformanceDataQualityIndicator.vue'
import PerformanceBenchmarkChart from '@/components/PerformanceBenchmarkChart.vue'
import PerformanceBenchmarkMethodology from '@/components/PerformanceBenchmarkMethodology.vue'
import PerformanceBenchmarkSummaryTable from '@/components/PerformanceBenchmarkSummaryTable.vue'
import {
  buildPerformanceBenchmarkRangeParams,
  shouldReloadForLatestReportDateChange,
} from '@/components/performanceBenchmarkRange'
import type { BaselinePerformanceSummary, BenchmarkPriceStatusResponse, PerformanceComparisonSeriesResponse } from '@/types/performance'
import type { EquityCurveRangeKey } from '@/views/equityCurveRange'

const ENSURE_CACHE_PREFIX = 'performance-baseline-price-ensure'
const ENSURE_CACHE_TTL_MS = 6 * 60 * 60 * 1000

const props = withDefaults(defineProps<{
  latestReportDate?: string | null
  detailed?: boolean
  autoEnsurePrices?: boolean
}>(), {
  latestReportDate: null,
  detailed: false,
  autoEnsurePrices: true,
})

const rangeOptions: Array<{ key: EquityCurveRangeKey; label: string }> = [
  { key: '1m', label: '1M' },
  { key: '3m', label: '3M' },
  { key: 'ytd', label: 'YTD' },
  { key: '1y', label: '1Y' },
  { key: 'all', label: 'ALL' },
]

const selectedRange = ref<EquityCurveRangeKey>('ytd')
const response = ref<PerformanceComparisonSeriesResponse | null>(null)
const benchmarkPriceStatus = ref<BenchmarkPriceStatusResponse | null>(null)
const loading = ref(false)
const statusLoading = ref(false)
const backfillLoading = ref(false)
const errorMessage = ref('')
const backfillMessage = ref('')
const backfillError = ref('')
const priceEnsureMessage = ref('')
const priceEnsureError = ref('')

const summary = computed(() => response.value?.summary ?? null)
const methodology = computed(() => response.value?.methodology ?? null)
const limitations = computed(() => summary.value?.data_limitations ?? [])

const spySummary = computed(() => findBaseline('spy_cashflow_matched'))
const qqqSummary = computed(() => findBaseline('qqq_cashflow_matched'))
const buyHoldSummary = computed(() => findBaseline('start_portfolio_buy_and_hold'))
const startPortfolioHoldings = computed(() => {
  const raw = buyHoldSummary.value?.metadata?.start_portfolio_holdings
  if (!Array.isArray(raw)) return []
  return raw
    .map((item) => {
      if (!item || typeof item !== 'object') return null
      const payload = item as Record<string, unknown>
      const symbol = typeof payload.symbol === 'string' ? payload.symbol : ''
      const quantity = typeof payload.quantity === 'number' ? payload.quantity : Number(payload.quantity)
      if (!symbol || !Number.isFinite(quantity)) return null
      return { symbol, quantity }
    })
    .filter((item): item is { symbol: string; quantity: number } => item !== null)
})
const startPortfolioTooltip = computed(() => {
  if (!startPortfolioHoldings.value.length) return '起始组合持仓暂无可展示标的'
  return `起始组合：${startPortfolioHoldings.value
    .map((item) => `${item.symbol} ${formatQuantity(item.quantity)}`)
    .join('，')}`
})
const missingBenchmarkPrices = computed(() => {
  const missingFromLimitations = limitations.value.some((item) => (
    item === 'benchmark_price_history_not_found:SPY' || item === 'benchmark_price_history_not_found:QQQ'
  ))
  const missingFromSummary = [spySummary.value, qqqSummary.value].some((item) => item?.data_quality === 'missing')
  return missingFromLimitations || missingFromSummary
})
const missingHoldingSymbols = computed(() => {
  const benchmarkSymbols = new Set(['SPY', 'QQQ'])
  return limitations.value
    .filter((item) => item.startsWith('benchmark_price_history_not_found:'))
    .map((item) => item.split(':')[1] || '')
    .filter((symbol) => symbol && !benchmarkSymbols.has(symbol))
})
const missingHoldingPrices = computed(() => missingHoldingSymbols.value.length > 0 || buyHoldSummary.value?.data_quality === 'partial')

const metricCards = computed(() => {
  const payload = summary.value
  if (!payload) return []
  return [
    {
      label: '真实账户收益率',
      value: formatPercent(payload.actual.twr_total_return),
      helper: `${payload.start_date ?? '--'} 至 ${payload.end_date ?? '--'}`,
      tone: toneByValue(payload.actual.twr_total_return),
    },
    {
      label: 'vs SPY 超额收益',
      value: formatOutperformance(payload.excess_returns.vs_spy_cashflow_matched),
      helper: formatSignedPercent(payload.excess_returns.vs_spy_cashflow_matched),
      tone: toneByValue(payload.excess_returns.vs_spy_cashflow_matched),
    },
    {
      label: 'vs QQQ 超额收益',
      value: formatOutperformance(payload.excess_returns.vs_qqq_cashflow_matched),
      helper: formatSignedPercent(payload.excess_returns.vs_qqq_cashflow_matched),
      tone: toneByValue(payload.excess_returns.vs_qqq_cashflow_matched),
    },
    {
      label: 'vs 起始持有',
      value: formatOutperformance(payload.excess_returns.vs_start_portfolio_buy_and_hold),
      helper: formatSignedPercent(payload.excess_returns.vs_start_portfolio_buy_and_hold),
      tone: toneByValue(payload.excess_returns.vs_start_portfolio_buy_and_hold),
      title: startPortfolioTooltip.value,
    },
    {
      label: 'vs QQQ 金额差',
      value: formatValueAdded(payload.value_added.vs_qqq_cashflow_matched),
      helper: '真实账户期末价值 - QQQ 同现金流',
      tone: toneByValue(payload.value_added.vs_qqq_cashflow_matched),
    },
    {
      label: '最大回撤',
      value: formatPercent(payload.actual.max_drawdown),
      helper: '基于真实账户 TWR 指数',
      tone: toneByValue(payload.actual.max_drawdown),
    },
    {
      label: '夏普率',
      value: formatNumber(payload.actual.sharpe_ratio),
      helper: 'risk_free_rate=0',
      tone: 'neutral',
    },
  ]
})

function findBaseline(type: BaselinePerformanceSummary['baseline_type']): BaselinePerformanceSummary | null {
  return summary.value?.baselines.find((item) => item.baseline_type === type) ?? null
}

function rangeParams(): { start_date?: string; end_date?: string; base_index: number } {
  return buildPerformanceBenchmarkRangeParams(props.latestReportDate, selectedRange.value)
}

async function loadData(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  priceEnsureMessage.value = ''
  priceEnsureError.value = ''
  try {
    const params = rangeParams()
    if (props.autoEnsurePrices !== false) {
      try {
        const ensureResult = await ensurePerformanceBaselinePricesOnce(params)
        priceEnsureMessage.value = ensureResult ? buildEnsureMessage(ensureResult) : ''
      } catch {
        priceEnsureError.value = '部分历史价格自动补齐失败，已使用本地已有数据计算。'
      }
    }
    response.value = await fetchPerformanceBaselineSeries(params)
    if (props.detailed) {
      await loadBenchmarkPriceStatus()
    }
  } catch (error) {
    errorMessage.value = formatLoadError(error)
  } finally {
    loading.value = false
  }
}

async function loadBenchmarkPriceStatus(): Promise<void> {
  statusLoading.value = true
  try {
    const params = rangeParams()
    benchmarkPriceStatus.value = await fetchBenchmarkPriceStatus({
      symbols: ['SPY', 'QQQ'],
      start_date: params.start_date,
      end_date: params.end_date,
    })
  } catch {
    benchmarkPriceStatus.value = null
  } finally {
    statusLoading.value = false
  }
}

async function syncBenchmarkPrices(): Promise<void> {
  backfillLoading.value = true
  backfillMessage.value = ''
  backfillError.value = ''
  try {
    const params = rangeParams()
    const result = await backfillBenchmarkPrices({
      symbols: ['SPY', 'QQQ'],
      start_date: params.start_date,
      end_date: params.end_date,
      force: false,
    })
    clearEnsureCache(params)
    backfillMessage.value = `同步完成：新增 ${result.inserted}，更新 ${result.updated}，跳过 ${result.skipped}`
    await loadData()
  } catch {
    backfillError.value = '同步失败，请检查 Longbridge OpenAPI 配置'
  } finally {
    backfillLoading.value = false
  }
}

async function syncHoldingPrices(): Promise<void> {
  backfillLoading.value = true
  backfillMessage.value = ''
  backfillError.value = ''
  try {
    const params = rangeParams()
    const result = await ensurePerformanceBaselinePrices({
      ...params,
      symbols: missingHoldingSymbols.value.length ? missingHoldingSymbols.value : undefined,
      force: false,
    })
    rememberEnsureCache(params)
    backfillMessage.value = buildEnsureMessage(result)
    await loadData()
  } catch {
    backfillError.value = '同步失败，请检查 Longbridge OpenAPI 配置'
  } finally {
    backfillLoading.value = false
  }
}

function selectRange(range: EquityCurveRangeKey): void {
  if (selectedRange.value === range) return
  selectedRange.value = range
}

function buildEnsureMessage(result: { inserted: number; updated: number; skipped: number }): string {
  if (result.inserted === 0 && result.updated === 0 && result.skipped === 0) return ''
  return `已自动补齐历史价格：新增 ${result.inserted}，更新 ${result.updated}，跳过 ${result.skipped}。`
}

async function ensurePerformanceBaselinePricesOnce(params: ReturnType<typeof rangeParams>): Promise<{ inserted: number; updated: number; skipped: number } | null> {
  if (hasFreshEnsureCache(params)) return null
  const result = await ensurePerformanceBaselinePrices(params)
  rememberEnsureCache(params)
  return result
}

function ensureCacheKey(params: ReturnType<typeof rangeParams>): string {
  return [
    ENSURE_CACHE_PREFIX,
    params.start_date ?? 'all',
    params.end_date ?? 'latest',
    params.base_index,
  ].join(':')
}

function hasFreshEnsureCache(params: ReturnType<typeof rangeParams>): boolean {
  try {
    const raw = window.sessionStorage.getItem(ensureCacheKey(params))
    if (!raw) return false
    const cached = JSON.parse(raw) as { checkedAt?: number }
    return typeof cached.checkedAt === 'number' && Date.now() - cached.checkedAt < ENSURE_CACHE_TTL_MS
  } catch {
    return false
  }
}

function rememberEnsureCache(params: ReturnType<typeof rangeParams>): void {
  try {
    window.sessionStorage.setItem(ensureCacheKey(params), JSON.stringify({ checkedAt: Date.now() }))
  } catch {
    // sessionStorage can be unavailable in private or constrained browser contexts.
  }
}

function clearEnsureCache(params: ReturnType<typeof rangeParams>): void {
  try {
    window.sessionStorage.removeItem(ensureCacheKey(params))
  } catch {
    // Best-effort cache invalidation only.
  }
}

function formatLoadError(error: unknown): string {
  const message = error instanceof Error ? error.message : ''
  if (message.includes('Internal Server Error') || message.includes('500')) {
    return '收益基准对比加载失败，请稍后重试或查看后端日志。'
  }
  return message || '加载收益基准对比失败'
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--'
  return `${(value * 100).toFixed(2)}%`
}

function formatSignedPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--'
  return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(2)}%`
}

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--'
  return value.toFixed(2)
}

function formatQuantity(value: number): string {
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 4 }).format(value)
}

function formatSignedCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--'
  const abs = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(Math.abs(value))
  return `${value >= 0 ? '+' : '-'}${abs}`
}

function formatValueAdded(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--'
  return value >= 0 ? `多赚 ${formatSignedCurrency(value)}` : `少赚 ${formatSignedCurrency(value)}`
}

function formatOutperformance(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--'
  return value >= 0 ? '跑赢' : '跑输'
}

function toneByValue(value: number | null | undefined): 'positive' | 'negative' | 'neutral' {
  if (value === null || value === undefined || value === 0) return 'neutral'
  return value > 0 ? 'positive' : 'negative'
}

onMounted(() => {
  void loadData()
})

watch(selectedRange, () => {
  void loadData()
})

watch(
  () => props.latestReportDate,
  (nextDate, previousDate) => {
    if (shouldReloadForLatestReportDateChange(previousDate, nextDate, selectedRange.value)) {
      void loadData()
    }
  },
)
</script>

<template>
  <section class="surface-panel benchmark-curves-panel">
    <div class="surface-panel__content">
      <div class="benchmark-curves-panel__header">
        <div>
          <p class="eyebrow">Benchmark</p>
          <h2 class="panel-title benchmark-curves-panel__title">收益基准对比</h2>
          <p class="panel-subtitle benchmark-curves-panel__subtitle">入金出金校正后的真实账户收益率，与 SPY、QQQ、起始组合买入并持有基准对比。</p>
        </div>
        <div class="benchmark-header-actions">
          <Tag v-if="summary" class="p-tag" :severity="summary.data_quality === 'complete' ? 'success' : summary.data_quality === 'partial' ? 'warn' : 'danger'">
            {{ summary.data_quality }}
          </Tag>
          <PerformanceDataQualityIndicator
            v-if="summary"
            :data-quality="summary.data_quality"
            :limitations="limitations"
            :baseline-summaries="summary.baselines"
          />
          <Button
            v-if="summary && missingBenchmarkPrices"
            icon="pi pi-download"
            label="同步基准价格"
            class="p-button-sm p-button-outlined"
            :loading="backfillLoading"
            @click="syncBenchmarkPrices"
          />
          <Button
            v-if="summary && missingHoldingPrices"
            icon="pi pi-database"
            label="同步持仓价格"
            class="p-button-sm p-button-outlined"
            :loading="backfillLoading"
            @click="syncHoldingPrices"
          />
          <Button icon="pi pi-refresh" label="刷新" class="p-button-text" :loading="loading" @click="loadData" />
        </div>
      </div>

      <div class="curve-range-switcher" aria-label="Benchmark range presets">
        <button
          v-for="option in rangeOptions"
          :key="option.key"
          type="button"
          class="curve-range-button"
          :class="{ 'curve-range-button--active': selectedRange === option.key }"
          @click="selectRange(option.key)"
        >
          {{ option.label }}
        </button>
      </div>

      <LoadingBlock v-if="loading && !response" />
      <ErrorBlock v-else-if="errorMessage" :message="errorMessage" />
      <template v-else-if="response && summary">
        <p v-if="priceEnsureError" class="benchmark-sync-note error">{{ priceEnsureError }}</p>
        <p v-else-if="priceEnsureMessage" class="benchmark-sync-note success">{{ priceEnsureMessage }}</p>
        <p v-if="backfillLoading" class="benchmark-sync-note">正在同步历史价格...</p>
        <p v-else-if="backfillError" class="benchmark-sync-note error">{{ backfillError }}</p>
        <p v-else-if="backfillMessage" class="benchmark-sync-note success">{{ backfillMessage }}</p>

        <section class="curve-series-switcher benchmark-metrics" aria-label="Benchmark key metrics">
          <article v-for="card in metricCards" :key="card.label" class="benchmark-metric" :class="card.tone" :title="card.title">
            <span class="curve-series-button__line" :class="card.tone"></span>
            <span class="curve-series-button__text">
              <strong>{{ card.value }}</strong>
              <small>{{ card.label }} · {{ card.helper }}</small>
            </span>
          </article>
        </section>

        <div class="benchmark-chart-well">
          <PerformanceBenchmarkChart :series="response.series" />
        </div>

        <div class="baseline-status">
          <span>SPY: {{ spySummary?.data_quality ?? 'missing' }}</span>
          <span>QQQ: {{ qqqSummary?.data_quality ?? 'missing' }}</span>
          <span>起始持有: {{ buyHoldSummary?.data_quality ?? 'missing' }}</span>
        </div>

        <div v-if="detailed" class="benchmark-price-status">
          <strong>Benchmark Price Status</strong>
          <span v-if="statusLoading">正在检查价格覆盖...</span>
          <template v-else-if="benchmarkPriceStatus">
            <span
              v-for="symbol in benchmarkPriceStatus.symbols"
              :key="symbol"
            >
              {{ symbol }}:
              {{ benchmarkPriceStatus.per_symbol[symbol]?.count ?? 0 }} 条，
              {{ benchmarkPriceStatus.per_symbol[symbol]?.first_date ?? '--' }}
              至
              {{ benchmarkPriceStatus.per_symbol[symbol]?.last_date ?? '--' }}
            </span>
          </template>
          <span v-else>暂无价格覆盖状态</span>
        </div>

        <PerformanceBenchmarkSummaryTable :summary="summary" />

        <PerformanceBenchmarkMethodology v-if="detailed && methodology" :methodology="methodology" />
      </template>
      <div v-else class="empty-state">暂无收益基准对比数据</div>
    </div>
  </section>
</template>

<style scoped>
.benchmark-curves-panel {
  margin-bottom: var(--space-5);
}

.benchmark-curves-panel__header {
  align-items: flex-start;
  display: flex;
  gap: 1rem;
  justify-content: space-between;
  margin-bottom: var(--space-4);
}

.benchmark-curves-panel__title {
  font-size: 1.45rem;
}

.benchmark-curves-panel__subtitle {
  max-width: 52rem;
}

.benchmark-header-actions {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: space-between;
}

.curve-range-switcher {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: var(--space-4);
}

.curve-range-button {
  border: 1px solid rgba(129, 160, 207, 0.12);
  background: rgba(15, 26, 45, 0.72);
  color: var(--color-text-secondary);
  border-radius: 999px;
  padding: 8px 14px;
  cursor: pointer;
  transition:
    border-color 160ms ease,
    background-color 160ms ease,
    color 160ms ease,
    transform 160ms ease;
}

.curve-range-button:hover,
.curve-range-button--active {
  border-color: rgba(86, 213, 255, 0.42);
  background: rgba(86, 213, 255, 0.12);
  color: var(--color-text-primary);
  transform: translateY(-1px);
}

.benchmark-metrics {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  margin-bottom: 1rem;
}

.benchmark-metric {
  align-items: center;
  background: rgba(9, 16, 29, 0.72);
  border: 1px solid rgba(129, 160, 207, 0.12);
  border-radius: 8px;
  cursor: default;
  display: flex;
  gap: 12px;
  padding: 12px 14px;
}

.curve-series-button__line {
  border-radius: 999px;
  display: inline-block;
  height: 36px;
  width: 4px;
  background: #56d5ff;
}

.curve-series-button__line.positive {
  background: var(--color-positive);
}

.curve-series-button__line.negative {
  background: var(--color-negative);
}

.curve-series-button__text {
  display: grid;
  gap: 2px;
}

.curve-series-button__text strong {
  color: var(--color-text-primary);
  font-size: 1.08rem;
}

.curve-series-button__text small {
  color: var(--color-text-secondary);
}

.benchmark-metric.positive .curve-series-button__text strong {
  color: var(--color-positive);
}

.benchmark-metric.negative .curve-series-button__text strong {
  color: var(--color-negative);
}

.benchmark-chart-well {
  background:
    linear-gradient(180deg, rgba(13, 22, 38, 0.92), rgba(8, 13, 23, 0.96)),
    rgba(9, 16, 29, 0.72);
  border: 1px solid rgba(129, 160, 207, 0.12);
  border-radius: 8px;
  padding: 10px;
}

.baseline-status {
  color: var(--text-muted);
  display: flex;
  flex-wrap: wrap;
  gap: 0.8rem;
  margin: 0.75rem 0 1rem;
}

.benchmark-sync-note {
  color: var(--color-text-secondary);
  margin: 0 0 0.75rem;
}

.benchmark-sync-note.error {
  color: var(--color-negative);
}

.benchmark-sync-note.success {
  color: var(--color-positive);
}

.benchmark-price-status {
  background: rgba(9, 16, 29, 0.54);
  border: 1px solid rgba(129, 160, 207, 0.12);
  border-radius: 8px;
  color: var(--color-text-secondary);
  display: flex;
  flex-wrap: wrap;
  gap: 0.7rem 1rem;
  margin: 0 0 1rem;
  padding: 0.75rem 0.9rem;
}

.benchmark-price-status strong {
  color: var(--color-text-primary);
}

@media (max-width: 720px) {
  .benchmark-panel__title-row,
  .benchmark-panel__toolbar {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
