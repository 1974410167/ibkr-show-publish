import { request } from './http'
import type {
  InvestmentConstitution,
  InvestmentConstitutionPayload,
  PortfolioActionAlert,
  PortfolioActionAlertListResponse,
  PortfolioActionAlertRunResult,
  PortfolioAutoDecisionRun,
  PortfolioAutoDecisionRunCreate,
  PortfolioAutoDecisionRunDetail,
  PortfolioAutoDecisionRunListResponse,
  PortfolioAutoDecisionSymbolHistoryResponse,
  PortfolioDailyLoopRun,
  PortfolioDailyLoopRunCreate,
  PortfolioDailyLoopRunListResponse,
  PortfolioDailyLoopRunResponse,
  PortfolioDailyLoopScheduledRunRequest,
  PortfolioDailyLoopScheduledRunResponse,
  PortfolioDailyLoopScheduleStatus,
  PortfolioManagerReport,
  PortfolioManagerReportGenerateRequest,
  PortfolioManagerReportListResponse,
  PortfolioEvaluationResult,
  PortfolioEvaluationResultListResponse,
  PortfolioEvaluationRunRequest,
  PortfolioEvaluationRunResponse,
  PortfolioEvaluationSummary,
  PortfolioEvaluationSymbolHistoryResponse,
  PortfolioImprovementGenerateRequest,
  PortfolioImprovementReport,
  PortfolioImprovementReportListResponse,
  PortfolioWatchtowerRun,
  PortfolioWatchtowerRunCreate,
  PortfolioWatchtowerRunDetail,
  PortfolioWatchtowerRunListResponse,
  PortfolioWatchtowerSymbolHistoryResponse,
  UniverseListFilters,
  UniverseSymbol,
  UniverseSymbolListResponse,
  UniverseSymbolPayload,
  UniverseSyncHoldingsResponse,
} from '@/types/portfolioManager'

function queryString(params: Record<string, string | number | boolean | null | undefined> | UniverseListFilters): string {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      searchParams.set(key, String(value))
    }
  })
  const value = searchParams.toString()
  return value ? `?${value}` : ''
}

export function fetchInvestmentConstitution(): Promise<InvestmentConstitution> {
  return request<InvestmentConstitution>('/api/portfolio-manager/constitution')
}

export function updateInvestmentConstitution(payload: InvestmentConstitutionPayload): Promise<InvestmentConstitution> {
  return request<InvestmentConstitution>('/api/portfolio-manager/constitution', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function resetInvestmentConstitution(): Promise<InvestmentConstitution> {
  return request<InvestmentConstitution>('/api/portfolio-manager/constitution/reset', {
    method: 'POST',
  })
}

export async function fetchPortfolioUniverse(filters: UniverseListFilters = {}): Promise<UniverseSymbol[]> {
  const response = await request<UniverseSymbolListResponse>(`/api/portfolio-manager/universe${queryString(filters)}`)
  return response.items
}

export function upsertPortfolioUniverseSymbol(symbol: string, payload: UniverseSymbolPayload): Promise<UniverseSymbol> {
  return request<UniverseSymbol>(`/api/portfolio-manager/universe/${encodeURIComponent(symbol)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function disablePortfolioUniverseSymbol(symbol: string): Promise<UniverseSymbol> {
  return request<UniverseSymbol>(`/api/portfolio-manager/universe/${encodeURIComponent(symbol)}`, {
    method: 'DELETE',
  })
}

export function excludePortfolioUniverseSymbol(symbol: string, excludedReason: string, notes?: string): Promise<UniverseSymbol> {
  return request<UniverseSymbol>(`/api/portfolio-manager/universe/${encodeURIComponent(symbol)}/exclude`, {
    method: 'POST',
    body: JSON.stringify({ excluded_reason: excludedReason, notes }),
  })
}

export function syncPortfolioUniverseHoldings(): Promise<UniverseSyncHoldingsResponse> {
  return request<UniverseSyncHoldingsResponse>('/api/portfolio-manager/universe/sync-holdings', {
    method: 'POST',
  })
}

export function runPortfolioWatchtower(payload: PortfolioWatchtowerRunCreate): Promise<PortfolioWatchtowerRunDetail> {
  return request<PortfolioWatchtowerRunDetail>('/api/portfolio-manager/watchtower/run', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function fetchPortfolioWatchtowerRuns(params: { limit?: number; run_date?: string } = {}): Promise<PortfolioWatchtowerRun[]> {
  const response = await request<PortfolioWatchtowerRunListResponse>(`/api/portfolio-manager/watchtower/runs${queryString(params)}`)
  return response.items
}

export function fetchPortfolioWatchtowerRun(runId: string): Promise<PortfolioWatchtowerRunDetail> {
  return request<PortfolioWatchtowerRunDetail>(`/api/portfolio-manager/watchtower/runs/${encodeURIComponent(runId)}`)
}

export async function fetchPortfolioWatchtowerSymbolHistory(symbol: string, limit = 30) {
  const response = await request<PortfolioWatchtowerSymbolHistoryResponse>(
    `/api/portfolio-manager/watchtower/symbols/${encodeURIComponent(symbol)}/history${queryString({ limit: String(limit) })}`,
  )
  return response.items
}

export function runPortfolioAutoDecisions(payload: PortfolioAutoDecisionRunCreate): Promise<PortfolioAutoDecisionRunDetail> {
  return request<PortfolioAutoDecisionRunDetail>('/api/portfolio-manager/auto-decisions/run', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function fetchPortfolioAutoDecisionRuns(params: { limit?: number; run_date?: string } = {}): Promise<PortfolioAutoDecisionRun[]> {
  const response = await request<PortfolioAutoDecisionRunListResponse>(`/api/portfolio-manager/auto-decisions/runs${queryString(params)}`)
  return response.items
}

export function fetchPortfolioAutoDecisionRun(runId: string): Promise<PortfolioAutoDecisionRunDetail> {
  return request<PortfolioAutoDecisionRunDetail>(`/api/portfolio-manager/auto-decisions/runs/${encodeURIComponent(runId)}`)
}

export async function fetchPortfolioAutoDecisionSymbolHistory(symbol: string, limit = 30) {
  const response = await request<PortfolioAutoDecisionSymbolHistoryResponse>(
    `/api/portfolio-manager/auto-decisions/symbols/${encodeURIComponent(symbol)}/history${queryString({ limit: String(limit) })}`,
  )
  return response.items
}

export function generatePortfolioManagerReport(payload: PortfolioManagerReportGenerateRequest): Promise<PortfolioManagerReport> {
  return request<PortfolioManagerReport>('/api/portfolio-manager/reports/generate', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function fetchPortfolioManagerReports(params: { limit?: number; report_date?: string } = {}): Promise<PortfolioManagerReport[]> {
  const response = await request<PortfolioManagerReportListResponse>(`/api/portfolio-manager/reports${queryString(params)}`)
  return response.items
}

export function fetchLatestPortfolioManagerReport(): Promise<PortfolioManagerReport> {
  return request<PortfolioManagerReport>('/api/portfolio-manager/reports/latest')
}

export function fetchPortfolioManagerReport(reportId: string): Promise<PortfolioManagerReport> {
  return request<PortfolioManagerReport>(`/api/portfolio-manager/reports/${encodeURIComponent(reportId)}`)
}

export function runPortfolioEvaluation(payload: PortfolioEvaluationRunRequest): Promise<PortfolioEvaluationRunResponse> {
  return request<PortfolioEvaluationRunResponse>('/api/portfolio-manager/evaluation/run', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function fetchPortfolioEvaluationResults(params: {
  limit?: number
  source_type?: string
  symbol?: string
  horizon?: string
  label?: string
  source_id?: string
} = {}): Promise<PortfolioEvaluationResult[]> {
  const response = await request<PortfolioEvaluationResultListResponse>(`/api/portfolio-manager/evaluation/results${queryString(params)}`)
  return response.items
}

export function fetchPortfolioEvaluationResult(resultId: string): Promise<PortfolioEvaluationResult> {
  return request<PortfolioEvaluationResult>(`/api/portfolio-manager/evaluation/results/${encodeURIComponent(resultId)}`)
}

export async function fetchPortfolioEvaluationSymbolHistory(symbol: string, limit = 100): Promise<PortfolioEvaluationResult[]> {
  const response = await request<PortfolioEvaluationSymbolHistoryResponse>(
    `/api/portfolio-manager/evaluation/symbols/${encodeURIComponent(symbol)}/history${queryString({ limit })}`,
  )
  return response.items
}

export function fetchPortfolioEvaluationSummary(params: { lookback_days?: number; horizons?: string } = {}): Promise<PortfolioEvaluationSummary> {
  return request<PortfolioEvaluationSummary>(`/api/portfolio-manager/evaluation/summary${queryString(params)}`)
}

export function runPortfolioDailyLoop(payload: PortfolioDailyLoopRunCreate): Promise<PortfolioDailyLoopRunResponse> {
  return request<PortfolioDailyLoopRunResponse>('/api/portfolio-manager/daily-loop/run', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function fetchPortfolioDailyLoopScheduleStatus(): Promise<PortfolioDailyLoopScheduleStatus> {
  return request<PortfolioDailyLoopScheduleStatus>('/api/portfolio-manager/daily-loop/schedule/status')
}

export function runPortfolioDailyLoopScheduled(payload: PortfolioDailyLoopScheduledRunRequest): Promise<PortfolioDailyLoopScheduledRunResponse> {
  return request<PortfolioDailyLoopScheduledRunResponse>('/api/portfolio-manager/daily-loop/scheduled/run', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function fetchPortfolioDailyLoopRuns(params: { limit?: number; run_date?: string } = {}): Promise<PortfolioDailyLoopRun[]> {
  const response = await request<PortfolioDailyLoopRunListResponse>(`/api/portfolio-manager/daily-loop/runs${queryString(params)}`)
  return response.items
}

export function fetchLatestPortfolioDailyLoopRun(): Promise<PortfolioDailyLoopRun> {
  return request<PortfolioDailyLoopRun>('/api/portfolio-manager/daily-loop/runs/latest')
}

export function fetchPortfolioDailyLoopRun(runId: string): Promise<PortfolioDailyLoopRun> {
  return request<PortfolioDailyLoopRun>(`/api/portfolio-manager/daily-loop/runs/${encodeURIComponent(runId)}`)
}

export async function fetchPortfolioActionAlerts(params: {
  limit?: number
  run_date?: string
  symbol?: string
  status?: string
  alert_type?: string
} = {}): Promise<PortfolioActionAlert[]> {
  const response = await request<PortfolioActionAlertListResponse>(`/api/portfolio-manager/action-alerts${queryString(params)}`)
  return response.items
}

export function fetchPortfolioActionAlert(alertId: string): Promise<PortfolioActionAlert> {
  return request<PortfolioActionAlert>(`/api/portfolio-manager/action-alerts/${encodeURIComponent(alertId)}`)
}

export function sendPortfolioActionAlertsForDailyLoop(dailyLoopRunId: string): Promise<PortfolioActionAlertRunResult> {
  return request<PortfolioActionAlertRunResult>(`/api/portfolio-manager/action-alerts/send-for-daily-loop/${encodeURIComponent(dailyLoopRunId)}`, {
    method: 'POST',
  })
}

export function generatePortfolioImprovementReport(payload: PortfolioImprovementGenerateRequest): Promise<PortfolioImprovementReport> {
  return request<PortfolioImprovementReport>('/api/portfolio-manager/improvement/reports/generate', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function fetchPortfolioImprovementReports(params: { limit?: number; report_date?: string } = {}): Promise<PortfolioImprovementReport[]> {
  const response = await request<PortfolioImprovementReportListResponse>(`/api/portfolio-manager/improvement/reports${queryString(params)}`)
  return response.items
}

export function fetchLatestPortfolioImprovementReport(): Promise<PortfolioImprovementReport> {
  return request<PortfolioImprovementReport>('/api/portfolio-manager/improvement/reports/latest')
}

export function fetchPortfolioImprovementReport(reportId: string): Promise<PortfolioImprovementReport> {
  return request<PortfolioImprovementReport>(`/api/portfolio-manager/improvement/reports/${encodeURIComponent(reportId)}`)
}
