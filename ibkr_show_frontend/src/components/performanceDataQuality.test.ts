import { describe, expect, it } from 'vitest'

import {
  affectedBaselineLabels,
  mapPerformanceLimitation,
  visiblePerformanceQualityMessages,
} from '@/components/performanceDataQuality'

describe('performanceDataQuality', () => {
  it('classifies nav_yesterday_missing as informational', () => {
    expect(mapPerformanceLimitation('nav_yesterday_missing')).toMatchObject({
      severity: 'info',
      message: '起始日没有前一日 NAV，这是收益率计算的正常边界。',
    })
    expect(visiblePerformanceQualityMessages(['nav_yesterday_missing'])).toEqual([])
  })

  it('turns benchmark missing diagnostics into user-facing warning messages', () => {
    expect(mapPerformanceLimitation('benchmark_price_history_not_found:SPY')).toMatchObject({
      severity: 'warning',
      message: '本地价格库没有找到 SPY 的历史价格，因此该基准暂不可用。',
    })
  })

  it('turns holding price missing diagnostics into start-portfolio warning messages', () => {
    expect(mapPerformanceLimitation('benchmark_price_history_not_found:AAPL')).toMatchObject({
      severity: 'warning',
      message: '本地价格库没有找到起始持仓 AAPL 的历史价格，因此起始组合买入并持有基准可能不完整。',
    })
  })

  it('lists affected baseline labels', () => {
    expect(
      affectedBaselineLabels([
        {
          baseline_type: 'spy_cashflow_matched',
          label: 'SPY 同现金流基准',
          start_date: null,
          end_date: null,
          start_nav: null,
          end_nav: null,
          total_net_cash_flow: 0,
          money_gain: null,
          total_return: null,
          annualized_return: null,
          max_drawdown: null,
          volatility: null,
          sharpe_ratio: null,
          data_quality: 'missing',
          data_limitations: [],
        },
      ]),
    ).toEqual(['SPY 同现金流基准'])
  })
})
