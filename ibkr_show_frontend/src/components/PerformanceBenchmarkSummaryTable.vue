<script setup lang="ts">
import type { BaselinePerformanceSummary, PerformanceComparisonSummary } from '@/types/performance'

const props = defineProps<{
  summary: PerformanceComparisonSummary
}>()

type Row = {
  key: string
  label: string
  totalReturn: number | null
  annualizedReturn: number | null
  maxDrawdown: number | null
  volatility: number | null
  sharpeRatio: number | null
  endNav: number | null
  valueAdded: number | null
}

function baselineValueAdded(item: BaselinePerformanceSummary): number | null {
  return props.summary.value_added[`vs_${item.baseline_type}`] ?? null
}

function rows(): Row[] {
  return [
    {
      key: 'actual_account',
      label: '真实账户',
      totalReturn: props.summary.actual.twr_total_return,
      annualizedReturn: props.summary.actual.annualized_return,
      maxDrawdown: props.summary.actual.max_drawdown,
      volatility: props.summary.actual.volatility,
      sharpeRatio: props.summary.actual.sharpe_ratio,
      endNav: props.summary.actual.end_nav,
      valueAdded: null,
    },
    ...props.summary.baselines.map((item) => ({
      key: item.baseline_type,
      label: item.label,
      totalReturn: item.total_return,
      annualizedReturn: item.annualized_return,
      maxDrawdown: item.max_drawdown,
      volatility: item.volatility,
      sharpeRatio: item.sharpe_ratio,
      endNav: item.end_nav,
      valueAdded: baselineValueAdded(item),
    })),
  ]
}

function formatPercent(value: number | null): string {
  if (value === null || value === undefined) return '--'
  return `${(value * 100).toFixed(2)}%`
}

function formatNumber(value: number | null): string {
  if (value === null || value === undefined) return '--'
  return value.toFixed(2)
}

function formatCurrency(value: number | null): string {
  if (value === null || value === undefined) return '--'
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value)
}

function formatSignedCurrency(value: number | null): string {
  if (value === null || value === undefined) return '--'
  const formatted = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(Math.abs(value))
  return `${value >= 0 ? '多赚 +' : '少赚 -'}${formatted.replace('$', '$')}`
}

function tone(value: number | null): string {
  if (value === null || value === 0) return 'neutral'
  return value > 0 ? 'positive' : 'negative'
}
</script>

<template>
  <div class="benchmark-table-wrap">
    <table class="benchmark-table">
      <thead>
        <tr>
          <th>基准</th>
          <th>总收益率</th>
          <th>年化收益率</th>
          <th>最大回撤</th>
          <th>波动率</th>
          <th>夏普率</th>
          <th>期末价值</th>
          <th>真实账户差额</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows()" :key="row.key">
          <td>{{ row.label }}</td>
          <td>{{ formatPercent(row.totalReturn) }}</td>
          <td>{{ formatPercent(row.annualizedReturn) }}</td>
          <td>{{ formatPercent(row.maxDrawdown) }}</td>
          <td>{{ formatPercent(row.volatility) }}</td>
          <td>{{ formatNumber(row.sharpeRatio) }}</td>
          <td>{{ formatCurrency(row.endNav) }}</td>
          <td :class="tone(row.valueAdded)">{{ row.valueAdded === null ? '真实账户' : formatSignedCurrency(row.valueAdded) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.benchmark-table-wrap {
  overflow-x: auto;
}

.benchmark-table {
  border-collapse: collapse;
  min-width: 920px;
  width: 100%;
}

.benchmark-table th,
.benchmark-table td {
  border-bottom: 1px solid rgba(129, 160, 207, 0.14);
  padding: 0.75rem;
  text-align: left;
}

.benchmark-table th {
  color: var(--text-muted);
  font-size: 0.78rem;
  font-weight: 600;
}

.positive {
  color: var(--color-positive);
}

.negative {
  color: var(--color-negative);
}

.neutral {
  color: var(--text-muted);
}
</style>
