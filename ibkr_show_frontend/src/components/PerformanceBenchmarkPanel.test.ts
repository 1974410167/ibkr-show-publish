import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const source = readFileSync(
  fileURLToPath(new URL('./PerformanceBenchmarkPanel.vue', import.meta.url)),
  'utf8',
)

describe('PerformanceBenchmarkPanel source contract', () => {
  it('uses equity-curve-like surface panel and range button styles', () => {
    expect(source).toContain('surface-panel benchmark-curves-panel')
    expect(source).toContain('class="eyebrow"')
    expect(source).toContain('curve-range-button')
    expect(source).toContain('benchmark-chart-well')
  })

  it('uses compact data quality indicator instead of large warning list', () => {
    expect(source).toContain('PerformanceDataQualityIndicator')
    expect(source).not.toContain('benchmark-warning')
    expect(source).not.toContain('请结合 data limitations 解读。')
  })

  it('exposes benchmark price backfill entry and refreshes after sync', () => {
    expect(source).toContain('同步基准价格')
    expect(source).toContain('同步持仓价格')
    expect(source).toContain('backfillBenchmarkPrices')
    expect(source).toContain('await loadData()')
    expect(source).toContain('同步失败，请检查 Longbridge OpenAPI 配置')
  })

  it('ensures baseline prices before fetching series by default', () => {
    expect(source).toContain('autoEnsurePrices?: boolean')
    expect(source).toContain('autoEnsurePrices: true')
    expect(source).toContain('ensurePerformanceBaselinePrices(params)')
    expect(source).toContain('props.autoEnsurePrices !== false')
    expect(source).toContain('fetchPerformanceBaselineSeries(params)')
    expect(source).toContain('ensurePerformanceBaselinePricesOnce')
    expect(source).toContain('sessionStorage')
    expect(source).toContain('ENSURE_CACHE_TTL_MS')
  })

  it('keeps loading baseline series when automatic ensure fails', () => {
    expect(source).toContain('部分历史价格自动补齐失败，已使用本地已有数据计算。')
    expect(source).toContain('priceEnsureError')
    expect(source).toContain('已自动补齐历史价格')
  })

  it('shows detailed benchmark price status in baseline lab mode', () => {
    expect(source).toContain('fetchBenchmarkPriceStatus')
    expect(source).toContain('Benchmark Price Status')
    expect(source).toContain('benchmarkPriceStatus.per_symbol')
  })

  it('maps internal server errors to friendly Chinese copy', () => {
    expect(source).toContain('formatLoadError')
    expect(source).toContain('收益基准对比加载失败，请稍后重试或查看后端日志。')
    expect(source).toContain("message.includes('Internal Server Error')")
    expect(source).not.toContain("errorMessage.value = error instanceof Error ? error.message")
  })

  it('adds start portfolio holdings as hover text on the buy-and-hold metric', () => {
    expect(source).toContain('start_portfolio_holdings')
    expect(source).toContain('startPortfolioTooltip')
    expect(source).toContain(':title="card.title"')
  })
})
