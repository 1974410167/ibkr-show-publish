import { describe, expect, it } from 'vitest'

import {
  buildPerformanceBenchmarkRangeParams,
  shouldReloadForLatestReportDateChange,
} from '@/components/performanceBenchmarkRange'

describe('performanceBenchmarkRange', () => {
  it('builds ytd params from latest report date', () => {
    expect(buildPerformanceBenchmarkRangeParams('2026-06-16', 'ytd')).toEqual({
      start_date: '2026-01-01',
      end_date: '2026-06-16',
      base_index: 100,
    })
  })

  it('builds 1m, 3m, and 1y params from latest report date', () => {
    expect(buildPerformanceBenchmarkRangeParams('2026-06-16', '1m')).toEqual({
      start_date: '2026-05-16',
      end_date: '2026-06-16',
      base_index: 100,
    })
    expect(buildPerformanceBenchmarkRangeParams('2026-06-16', '3m')).toEqual({
      start_date: '2026-03-16',
      end_date: '2026-06-16',
      base_index: 100,
    })
    expect(buildPerformanceBenchmarkRangeParams('2026-06-16', '1y')).toEqual({
      start_date: '2025-06-16',
      end_date: '2026-06-16',
      base_index: 100,
    })
  })

  it('falls back to all-time params when latest report date is unavailable', () => {
    expect(buildPerformanceBenchmarkRangeParams(null, 'ytd')).toEqual({
      base_index: 100,
    })
  })

  it('reloads when latest report date becomes available for ranged views', () => {
    expect(shouldReloadForLatestReportDateChange(null, '2026-06-16', 'ytd')).toBe(true)
    expect(shouldReloadForLatestReportDateChange(null, '2026-06-16', '1m')).toBe(true)
    expect(shouldReloadForLatestReportDateChange(null, '2026-06-16', 'all')).toBe(false)
    expect(shouldReloadForLatestReportDateChange('2026-06-15', '2026-06-16', 'ytd')).toBe(false)
  })
})
