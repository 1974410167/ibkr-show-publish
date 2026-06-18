import { request } from './http'
import type {
  AccountPerformanceSummary,
  BenchmarkPriceBackfillResult,
  BenchmarkPriceStatusResponse,
  PerformanceBaselineType,
  PerformanceComparisonSeriesResponse,
  PerformanceComparisonSummary,
  PerformancePriceEnsureResult,
  PerformanceSeriesResponse,
} from '@/types/performance'

export interface PerformanceQueryParams {
  start_date?: string
  end_date?: string
  base_index?: number
  baselines?: PerformanceBaselineType[]
}

export interface BenchmarkPriceQueryParams {
  symbols?: string[]
  start_date?: string
  end_date?: string
  force?: boolean
}

function buildQuery(params: PerformanceQueryParams = {}): string {
  const searchParams = new URLSearchParams()
  if (params.start_date) searchParams.set('start_date', params.start_date)
  if (params.end_date) searchParams.set('end_date', params.end_date)
  if (params.base_index !== undefined) searchParams.set('base_index', String(params.base_index))
  if (params.baselines?.length) searchParams.set('baselines', params.baselines.join(','))
  const query = searchParams.toString()
  return query ? `?${query}` : ''
}

function buildBenchmarkPriceQuery(params: BenchmarkPriceQueryParams = {}, includeForce = false): string {
  const searchParams = new URLSearchParams()
  if (params.symbols?.length) searchParams.set('symbols', params.symbols.join(','))
  if (params.start_date) searchParams.set('start_date', params.start_date)
  if (params.end_date) searchParams.set('end_date', params.end_date)
  if (includeForce && params.force !== undefined) searchParams.set('force', String(params.force))
  const query = searchParams.toString()
  return query ? `?${query}` : ''
}

export function fetchAccountPerformanceSeries(params: PerformanceQueryParams = {}): Promise<PerformanceSeriesResponse> {
  return request<PerformanceSeriesResponse>(`/api/performance/account/series${buildQuery(params)}`)
}

export function fetchAccountPerformanceSummary(params: PerformanceQueryParams = {}): Promise<AccountPerformanceSummary> {
  return request<AccountPerformanceSummary>(`/api/performance/account/summary${buildQuery(params)}`)
}

export function fetchPerformanceBaselineSeries(params: PerformanceQueryParams = {}): Promise<PerformanceComparisonSeriesResponse> {
  return request<PerformanceComparisonSeriesResponse>(`/api/performance/baselines/series${buildQuery(params)}`)
}

export function fetchPerformanceBaselineSummary(params: PerformanceQueryParams = {}): Promise<PerformanceComparisonSummary> {
  return request<PerformanceComparisonSummary>(`/api/performance/baselines/summary${buildQuery(params)}`)
}

export function backfillBenchmarkPrices(params: BenchmarkPriceQueryParams = {}): Promise<BenchmarkPriceBackfillResult> {
  return request<BenchmarkPriceBackfillResult>(`/api/performance/benchmark-prices/backfill${buildBenchmarkPriceQuery(params, true)}`, {
    method: 'POST',
  })
}

export function fetchBenchmarkPriceStatus(params: BenchmarkPriceQueryParams = {}): Promise<BenchmarkPriceStatusResponse> {
  return request<BenchmarkPriceStatusResponse>(`/api/performance/benchmark-prices/status${buildBenchmarkPriceQuery(params)}`)
}

export function ensurePerformanceBaselinePrices(params: BenchmarkPriceQueryParams = {}): Promise<PerformancePriceEnsureResult> {
  return request<PerformancePriceEnsureResult>(`/api/performance/prices/ensure-for-baselines${buildBenchmarkPriceQuery(params, true)}`, {
    method: 'POST',
  })
}
