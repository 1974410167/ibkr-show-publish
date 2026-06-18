import {
  buildEquityCurveRangeParams,
  type EquityCurveRangeKey,
} from '@/views/equityCurveRange'

export function buildPerformanceBenchmarkRangeParams(
  latestReportDate: string | null | undefined,
  range: EquityCurveRangeKey,
): {
  start_date?: string
  end_date?: string
  base_index: number
} {
  return {
    ...buildEquityCurveRangeParams(latestReportDate, range),
    base_index: 100,
  }
}

export function shouldReloadForLatestReportDateChange(
  previousDate: string | null | undefined,
  nextDate: string | null | undefined,
  range: EquityCurveRangeKey,
): boolean {
  return range !== 'all' && !previousDate && Boolean(nextDate)
}
