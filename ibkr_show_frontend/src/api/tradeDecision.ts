import { request } from './http'
import type {
  TradeDecisionBehaviorInsight,
  TradeDecisionBehaviorProfileResponse,
  TradeDecisionExecutionAlignmentListResponse,
  TradeDecisionExecutionAlignmentSummary,
  TradeDecisionBacktestResponse,
  TradeDecisionHealth,
  TradeDecisionHoldingsResponse,
  TradeDecisionListResponse,
  TradeDecisionOutcomeListResponse,
  TradeDecisionOutcomeSummary,
  TradeDecisionOverrideAnnotation,
  TradeDecisionOverrideAnnotationListResponse,
  TradeDecisionOverrideAnnotationPayload,
  TradeDecisionQualitySummary,
  TradeDecisionResult,
} from '@/types/tradeDecision'
import type { AgentTask, AgentTaskListResponse } from '@/types/agentTasks'

function toQueryString(params: Record<string, string | number | undefined | null>): string {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      searchParams.set(key, String(value))
    }
  })
  const queryString = searchParams.toString()
  return queryString ? `?${queryString}` : ''
}

export function fetchTradeDecisionHealth(): Promise<TradeDecisionHealth> {
  return request<TradeDecisionHealth>('/api/agent/trade-decision/health')
}

export function fetchTradeDecisionHoldings(): Promise<TradeDecisionHoldingsResponse> {
  return request<TradeDecisionHoldingsResponse>('/api/agent/trade-decision/holdings')
}

export function startTradeDecisionTask(payload: {
  symbol: string
  force_refresh?: boolean
}): Promise<AgentTask> {
  return request<AgentTask>('/api/agent/trade-decision/tasks', {
    method: 'POST',
    body: JSON.stringify({
      symbol: payload.symbol,
      force_refresh: Boolean(payload.force_refresh),
    }),
  })
}

export function startHoldingDecisionTask(payload: {
  symbol: string
  question?: string
  force_refresh?: boolean
}): Promise<AgentTask> {
  return request<AgentTask>(`/api/agent/trade-decision/holding/${encodeURIComponent(payload.symbol)}/tasks`, {
    method: 'POST',
    body: JSON.stringify({
      question: payload.question || undefined,
      force_refresh: Boolean(payload.force_refresh),
    }),
  })
}

export function analyzeEntryDecision(payload: {
  symbol: string
  question?: string
  force_refresh?: boolean
}): Promise<TradeDecisionResult> {
  return request<TradeDecisionResult>('/api/agent/trade-decision/entry/analyze', {
    method: 'POST',
    body: JSON.stringify({
      symbol: payload.symbol,
      question: payload.question || undefined,
      force_refresh: Boolean(payload.force_refresh),
    }),
  })
}

export function startEntryDecisionTask(payload: {
  symbol: string
  question?: string
  force_refresh?: boolean
}): Promise<AgentTask> {
  return request<AgentTask>('/api/agent/trade-decision/entry/tasks', {
    method: 'POST',
    body: JSON.stringify({
      symbol: payload.symbol,
      question: payload.question || undefined,
      force_refresh: Boolean(payload.force_refresh),
    }),
  })
}

export async function fetchTradeDecisionTasks(limit = 20): Promise<AgentTask[]> {
  const response = await request<AgentTaskListResponse>(`/api/agent/trade-decision/tasks${toQueryString({ limit })}`)
  return response.items
}

export function fetchTradeDecisionTask(taskId: string): Promise<AgentTask> {
  return request<AgentTask>(`/api/agent/trade-decision/tasks/${encodeURIComponent(taskId)}`)
}

export async function fetchRecentTradeDecisions(params: { limit?: number; decision_type?: string } = {}): Promise<TradeDecisionResult[]> {
  const response = await request<TradeDecisionListResponse>(`/api/agent/trade-decision/recent${toQueryString(params)}`)
  return response.items
}

export function fetchTradeDecisionQualitySummary(params: {
  limit?: number
  days?: number
} = {}): Promise<TradeDecisionQualitySummary> {
  return request<TradeDecisionQualitySummary>(
    `/api/agent/trade-decision/quality/summary${toQueryString(params)}`,
  )
}

export function fetchTradeDecisionOutcomeSummary(params: {
  limit?: number
  days?: number
  symbol?: string
  decision_type?: string
  horizons?: string
  action_group?: string
  outcome_label?: string
} = {}): Promise<TradeDecisionOutcomeSummary> {
  return request<TradeDecisionOutcomeSummary>(
    `/api/agent/trade-decision/outcome/summary${toQueryString(params)}`,
  )
}

export function fetchTradeDecisionOutcomeList(params: {
  limit?: number
  days?: number
  symbol?: string
  decision_type?: string
  horizons?: string
  action_group?: string
  outcome_label?: string
} = {}): Promise<TradeDecisionOutcomeListResponse> {
  return request<TradeDecisionOutcomeListResponse>(
    `/api/agent/trade-decision/outcome/list${toQueryString(params)}`,
  )
}

export function fetchTradeDecisionBacktestSummary(params: {
  start_date?: string
  end_date?: string
  days?: number
  initial_cash?: number
  symbol?: string
  decision_type?: string
  benchmark_symbol?: string
  execution_timing?: string
  commission_bps?: number
  min_commission?: number
  include_costs?: string | number
  mode?: string
  limit?: number
} = {}): Promise<TradeDecisionBacktestResponse> {
  return request<TradeDecisionBacktestResponse>(
    `/api/agent/trade-decision/backtest/summary${toQueryString(params)}`,
  )
}

export function fetchTradeDecisionBacktestDetail(params: {
  start_date?: string
  end_date?: string
  days?: number
  initial_cash?: number
  symbol?: string
  decision_type?: string
  benchmark_symbol?: string
  execution_timing?: string
  commission_bps?: number
  min_commission?: number
  include_costs?: string | number
  mode?: string
  limit?: number
} = {}): Promise<TradeDecisionBacktestResponse> {
  return request<TradeDecisionBacktestResponse>(
    `/api/agent/trade-decision/backtest/detail${toQueryString(params)}`,
  )
}

export function fetchTradeDecisionAlignmentSummary(params: {
  start_date?: string
  end_date?: string
  days?: number
  symbol?: string
  decision_type?: string
  match_window_days?: number
  include_same_day?: string | number
  alignment_label?: string
  behavior_tag?: string
  limit?: number
} = {}): Promise<TradeDecisionExecutionAlignmentSummary> {
  return request<TradeDecisionExecutionAlignmentSummary>(
    `/api/agent/trade-decision/alignment/summary${toQueryString(params)}`,
  )
}

export function fetchTradeDecisionAlignmentList(params: {
  start_date?: string
  end_date?: string
  days?: number
  symbol?: string
  decision_type?: string
  match_window_days?: number
  include_same_day?: string | number
  alignment_label?: string
  behavior_tag?: string
  limit?: number
} = {}): Promise<TradeDecisionExecutionAlignmentListResponse> {
  return request<TradeDecisionExecutionAlignmentListResponse>(
    `/api/agent/trade-decision/alignment/list${toQueryString(params)}`,
  )
}

export function fetchTradeDecisionBehaviorProfile(params: {
  start_date?: string
  end_date?: string
  days?: number
  symbol?: string
  decision_type?: string
  behavior_tag?: string
  reason_category?: string
  min_count?: number
  limit?: number
} = {}): Promise<TradeDecisionBehaviorProfileResponse> {
  return request<TradeDecisionBehaviorProfileResponse>(
    `/api/agent/trade-decision/behavior/profile${toQueryString(params)}`,
  )
}

export function fetchTradeDecisionBehaviorInsights(params: {
  start_date?: string
  end_date?: string
  days?: number
  symbol?: string
  decision_type?: string
  behavior_tag?: string
  reason_category?: string
  min_count?: number
  limit?: number
} = {}): Promise<TradeDecisionBehaviorInsight[]> {
  return request<TradeDecisionBehaviorInsight[]>(
    `/api/agent/trade-decision/behavior/insights${toQueryString(params)}`,
  )
}

export function fetchTradeDecisionOverrideAnnotations(params: {
  symbol?: string
  reason_category?: string
  behavior_tag?: string
  days?: number
  limit?: number
} = {}): Promise<TradeDecisionOverrideAnnotationListResponse> {
  return request<TradeDecisionOverrideAnnotationListResponse>(
    `/api/agent/trade-decision/behavior/annotations${toQueryString(params)}`,
  )
}

export function fetchTradeDecisionOverrideAnnotation(decisionId: string): Promise<TradeDecisionOverrideAnnotation> {
  return request<TradeDecisionOverrideAnnotation>(
    `/api/agent/trade-decision/behavior/annotations/${encodeURIComponent(decisionId)}`,
  )
}

export function saveTradeDecisionOverrideAnnotation(
  decisionId: string,
  payload: TradeDecisionOverrideAnnotationPayload,
): Promise<TradeDecisionOverrideAnnotation> {
  return request<TradeDecisionOverrideAnnotation>(
    `/api/agent/trade-decision/behavior/annotations/${encodeURIComponent(decisionId)}`,
    {
      method: 'PUT',
      body: JSON.stringify(payload),
    },
  )
}

export function deleteTradeDecisionOverrideAnnotation(decisionId: string): Promise<TradeDecisionOverrideAnnotation> {
  return request<TradeDecisionOverrideAnnotation>(
    `/api/agent/trade-decision/behavior/annotations/${encodeURIComponent(decisionId)}`,
    { method: 'DELETE' },
  )
}

export async function fetchSymbolTradeDecisions(symbol: string, limit = 10): Promise<TradeDecisionResult[]> {
  const response = await request<TradeDecisionListResponse>(
    `/api/agent/trade-decision/symbol/${encodeURIComponent(symbol)}${toQueryString({ limit })}`,
  )
  return response.items
}

export function fetchTradeDecisionDetail(decisionId: string): Promise<TradeDecisionResult> {
  return request<TradeDecisionResult>(`/api/agent/trade-decision/${encodeURIComponent(decisionId)}`)
}
