import { beforeEach, describe, expect, it, vi } from 'vitest'

import { backfillBenchmarkPrices, ensurePerformanceBaselinePrices, fetchBenchmarkPriceStatus } from '@/api/performance'

describe('performance api benchmark prices', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('posts benchmark price backfill with symbols date range and force flag', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          symbols: ['SPY', 'QQQ'],
          start_date: '2026-01-01',
          end_date: '2026-06-16',
          inserted: 2,
          updated: 0,
          skipped: 0,
          failed: 0,
          per_symbol: {},
          data_limitations: [],
        }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await backfillBenchmarkPrices({
      symbols: ['SPY', 'QQQ'],
      start_date: '2026-01-01',
      end_date: '2026-06-16',
      force: true,
    })

    expect(result.inserted).toBe(2)
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/performance/benchmark-prices/backfill?symbols=SPY%2CQQQ&start_date=2026-01-01&end_date=2026-06-16&force=true',
      expect.objectContaining({ method: 'POST', credentials: 'include' }),
    )
  })

  it('fetches benchmark price status without force flag', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          symbols: ['SPY'],
          start_date: '2026-01-01',
          end_date: '2026-06-16',
          per_symbol: {
            SPY: {
              count: 117,
              first_date: '2026-01-02',
              last_date: '2026-06-16',
              has_data: true,
            },
          },
          data_quality: 'complete',
          data_limitations: [],
        }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await fetchBenchmarkPriceStatus({
      symbols: ['SPY'],
      start_date: '2026-01-01',
      end_date: '2026-06-16',
      force: true,
    })

    expect(result.per_symbol.SPY.count).toBe(117)
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/performance/benchmark-prices/status?symbols=SPY&start_date=2026-01-01&end_date=2026-06-16',
      expect.objectContaining({ credentials: 'include' }),
    )
  })

  it('posts automatic performance baseline price ensure request', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          symbols: ['SPY', 'QQQ', 'AAPL'],
          start_date: '2026-01-01',
          end_date: '2026-06-16',
          inserted: 3,
          updated: 0,
          skipped: 2,
          failed: 0,
          missing_symbols: [],
          per_symbol: {},
          data_limitations: [],
        }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await ensurePerformanceBaselinePrices({
      start_date: '2026-01-01',
      end_date: '2026-06-16',
      force: false,
    })

    expect(result.inserted).toBe(3)
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/performance/prices/ensure-for-baselines?start_date=2026-01-01&end_date=2026-06-16&force=false',
      expect.objectContaining({ method: 'POST', credentials: 'include' }),
    )
  })
})
