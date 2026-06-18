import type { AccountPerformanceDataQuality, BaselinePerformanceSummary } from '@/types/performance'

export type DataQualitySeverity = 'info' | 'warning' | 'error'

export interface DataQualityMessage {
  raw: string
  message: string
  severity: DataQualitySeverity
}

export function mapPerformanceLimitation(raw: string): DataQualityMessage {
  if (raw === 'nav_yesterday_missing') {
    return {
      raw,
      message: '起始日没有前一日 NAV，这是收益率计算的正常边界。',
      severity: 'info',
    }
  }
  if (raw.startsWith('benchmark_price_history_not_found:')) {
    const symbol = raw.split(':')[1] || 'benchmark'
    if (!['SPY', 'QQQ'].includes(symbol)) {
      return {
        raw,
        message: `本地价格库没有找到起始持仓 ${symbol} 的历史价格，因此起始组合买入并持有基准可能不完整。`,
        severity: 'warning',
      }
    }
    return {
      raw,
      message: `本地价格库没有找到 ${symbol} 的历史价格，因此该基准暂不可用。`,
      severity: 'warning',
    }
  }
  if (raw.startsWith('benchmark_start_price_shifted_to_next_trading_day:')) {
    const parts = raw.split(':')
    return {
      raw,
      message: `${parts[1] || '基准'} 起始日不是交易日，已使用 ${parts[2] || '后续最近交易日'} 的价格作为起点。`,
      severity: 'info',
    }
  }
  if (raw.startsWith('start_portfolio_price_shifted_to_next_trading_day:')) {
    const parts = raw.split(':')
    return {
      raw,
      message: `${parts[1] || '起始持仓'} 起始日不是交易日，已使用 ${parts[2] || '后续最近交易日'} 的价格作为起点。`,
      severity: 'info',
    }
  }
  if (raw.includes('forward_filled')) {
    return {
      raw,
      message: '部分价格缺失，已使用最近可用价格延续显示。结果已标记为 partial。',
      severity: 'info',
    }
  }
  if (raw.includes('missing') || raw.includes('not_found')) {
    return {
      raw,
      message: raw,
      severity: 'warning',
    }
  }
  return {
    raw,
    message: raw,
    severity: 'info',
  }
}

export function visiblePerformanceQualityMessages(limitations: string[]): DataQualityMessage[] {
  return limitations.map(mapPerformanceLimitation).filter((item) => item.severity !== 'info').slice(0, 5)
}

export function performanceQualityTone(dataQuality: AccountPerformanceDataQuality): 'success' | 'warning' | 'error' {
  if (dataQuality === 'complete') return 'success'
  if (dataQuality === 'missing') return 'error'
  return 'warning'
}

export function affectedBaselineLabels(baselines: BaselinePerformanceSummary[] = []): string[] {
  return baselines
    .filter((item) => item.data_quality !== 'complete')
    .map((item) => item.label)
}
