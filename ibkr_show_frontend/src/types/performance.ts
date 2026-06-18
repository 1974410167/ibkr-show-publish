export type AccountPerformanceDataQuality = 'complete' | 'partial' | 'missing'

export interface AccountPerformancePoint {
  date: string
  nav: number | null
  net_cash_flow: number
  investment_pnl: number | null
  daily_return: number | null
  twr_index: number | null
  data_quality: AccountPerformanceDataQuality
  data_limitations: string[]
}

export interface AccountPerformanceSummary {
  start_date: string | null
  end_date: string | null
  start_nav: number | null
  end_nav: number | null
  total_net_cash_flow: number
  money_gain: number | null
  twr_total_return: number | null
  annualized_return: number | null
  max_drawdown: number | null
  volatility: number | null
  sharpe_ratio: number | null
  data_quality: AccountPerformanceDataQuality
  data_limitations: string[]
}

export interface PerformanceMethodology {
  return_method: string
  cashflow_adjusted: boolean
  base_index: number
}

export interface PerformanceSeriesResponse {
  summary: AccountPerformanceSummary
  series: AccountPerformancePoint[]
  methodology: PerformanceMethodology
}

export type PerformanceBaselineType =
  | 'actual_account'
  | 'spy_cashflow_matched'
  | 'qqq_cashflow_matched'
  | 'start_portfolio_buy_and_hold'

export interface BaselinePerformancePoint {
  date: string
  baseline_type: PerformanceBaselineType
  nav: number | null
  net_cash_flow: number
  daily_return: number | null
  return_index: number | null
  benchmark_price: number | null
  units: number | null
  cash: number
  data_quality: AccountPerformanceDataQuality
  data_limitations: string[]
}

export interface BaselinePerformanceSummary {
  baseline_type: PerformanceBaselineType
  label: string
  start_date: string | null
  end_date: string | null
  start_nav: number | null
  end_nav: number | null
  total_net_cash_flow: number
  money_gain: number | null
  total_return: number | null
  annualized_return: number | null
  max_drawdown: number | null
  volatility: number | null
  sharpe_ratio: number | null
  data_quality: AccountPerformanceDataQuality
  data_limitations: string[]
  metadata?: Record<string, unknown>
}

export interface PerformanceComparisonSummary {
  start_date: string | null
  end_date: string | null
  actual: AccountPerformanceSummary
  baselines: BaselinePerformanceSummary[]
  excess_returns: Record<string, number | null>
  value_added: Record<string, number | null>
  data_quality: AccountPerformanceDataQuality
  data_limitations: string[]
}

export interface PerformanceComparisonMethodology {
  return_method: string
  cashflow_adjusted: boolean
  base_index: number
  benchmark_price_field: string
}

export interface PerformanceComparisonSeriesResponse {
  summary: PerformanceComparisonSummary
  series: Partial<Record<PerformanceBaselineType, AccountPerformancePoint[] | BaselinePerformancePoint[]>>
  methodology: PerformanceComparisonMethodology
}

export interface BenchmarkPriceBackfillSymbolResult {
  requested_symbol: string
  source_symbol: string
  fetched: number
  inserted: number
  updated: number
  skipped: number
  failed: number
  first_date: string | null
  last_date: string | null
  data_limitations: string[]
}

export interface BenchmarkPriceBackfillResult {
  symbols: string[]
  start_date: string
  end_date: string
  inserted: number
  updated: number
  skipped: number
  failed: number
  per_symbol: Record<string, BenchmarkPriceBackfillSymbolResult>
  data_limitations: string[]
}

export interface BenchmarkPriceStatusItem {
  count: number
  first_date: string | null
  last_date: string | null
  has_data: boolean
}

export interface BenchmarkPriceStatusResponse {
  symbols: string[]
  start_date: string
  end_date: string
  per_symbol: Record<string, BenchmarkPriceStatusItem>
  data_quality: AccountPerformanceDataQuality
  data_limitations: string[]
}

export interface PerformancePriceEnsureSymbolResult {
  symbol: string
  source_symbol: string | null
  has_existing_data: boolean
  fetched: number
  inserted: number
  updated: number
  skipped: number
  failed: number
  first_date: string | null
  last_date: string | null
  data_limitations: string[]
}

export interface PerformancePriceEnsureResult {
  start_date: string
  end_date: string
  symbols: string[]
  inserted: number
  updated: number
  skipped: number
  failed: number
  missing_symbols: string[]
  per_symbol: Record<string, PerformancePriceEnsureSymbolResult>
  data_limitations: string[]
}
