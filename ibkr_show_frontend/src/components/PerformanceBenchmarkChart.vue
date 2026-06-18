<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import { use, init, format, type ComposeOption, type EChartsType } from 'echarts/core'
import { LineChart, type LineSeriesOption } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
  type GridComponentOption,
  type LegendComponentOption,
  type TooltipComponentOption,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

import type { AccountPerformancePoint, BaselinePerformancePoint, PerformanceBaselineType } from '@/types/performance'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

type ChartOption = ComposeOption<LineSeriesOption | GridComponentOption | TooltipComponentOption | LegendComponentOption>

const props = defineProps<{
  series: Partial<Record<PerformanceBaselineType, AccountPerformancePoint[] | BaselinePerformancePoint[]>>
}>()

const chartRef = ref<HTMLDivElement | null>(null)
const chartInstance = shallowRef<EChartsType | null>(null)
let resizeObserver: ResizeObserver | null = null

const labels: Record<PerformanceBaselineType, string> = {
  actual_account: '真实账户',
  spy_cashflow_matched: 'SPY 同现金流',
  qqq_cashflow_matched: 'QQQ 同现金流',
  start_portfolio_buy_and_hold: '起始组合持有',
}

const colors: Record<PerformanceBaselineType, string> = {
  actual_account: '#56d5ff',
  spy_cashflow_matched: '#b7e11d',
  qqq_cashflow_matched: '#ffb454',
  start_portfolio_buy_and_hold: '#8b7cff',
}

const hasData = computed(() => chartSeries.value.length > 0)

const chartSeries = computed(() => {
  const order: PerformanceBaselineType[] = [
    'actual_account',
    'spy_cashflow_matched',
    'qqq_cashflow_matched',
    'start_portfolio_buy_and_hold',
  ]
  return order.flatMap((key) => {
    const points = props.series[key] ?? []
    const data = points.flatMap((point) => {
      const value = key === 'actual_account'
        ? (point as AccountPerformancePoint).twr_index
        : (point as BaselinePerformancePoint).return_index
      return value === null || value === undefined ? [] : [[point.date, value] as [string, number]]
    })
    if (!data.length) return []
    return [
      {
        name: labels[key],
        type: 'line' as const,
        showSymbol: false,
        smooth: true,
        data,
        lineStyle: { width: key === 'actual_account' ? 3 : 2, color: colors[key] },
        itemStyle: { color: colors[key] },
        emphasis: { focus: 'series' as const },
      },
    ]
  })
})

function renderChart(): void {
  if (!chartInstance.value) return
  const option: ChartOption = {
    animationDuration: 600,
    backgroundColor: 'transparent',
    grid: { top: 52, right: 36, bottom: 42, left: 42 },
    legend: {
      top: 8,
      textStyle: { color: '#9aa9c8' },
      itemWidth: 18,
      itemHeight: 8,
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(6, 12, 24, 0.96)',
      borderColor: 'rgba(129, 160, 207, 0.22)',
      textStyle: { color: '#e6eefc' },
      padding: 12,
      extraCssText: 'box-shadow: 0 18px 36px rgba(2, 10, 24, 0.45); border-radius: 12px;',
      formatter(params: unknown) {
        const entries = Array.isArray(params) ? params : [params]
        const first = entries[0] as { axisValueLabel?: string } | undefined
        const lines = [`<div style="margin-bottom:8px;color:#9aa9c8">${first?.axisValueLabel ?? '--'}</div>`]
        entries.forEach((entry) => {
          const point = entry as { seriesName: string; color: string; value: [string, number] }
          lines.push(
            `<div style="display:flex;justify-content:space-between;gap:24px;min-width:210px">` +
              `<span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${point.color};margin-right:8px"></span>${point.seriesName}</span>` +
              `<strong>${point.value[1].toFixed(2)}</strong>` +
            `</div>`,
          )
        })
        return lines.join('')
      },
    },
    xAxis: {
      type: 'time',
      axisLabel: {
        color: '#6d7d9d',
        formatter(value: number) {
          return format.formatTime('yyyy-MM', value)
        },
      },
      axisLine: { lineStyle: { color: 'rgba(129, 160, 207, 0.16)' } },
      axisTick: { show: false },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      name: '收益指数',
      nameTextStyle: { color: '#6d7d9d' },
      axisLabel: { color: '#6d7d9d' },
      axisTick: { show: false },
      axisLine: { show: false },
      splitLine: { lineStyle: { color: 'rgba(129, 160, 207, 0.11)', type: 'dashed' } },
    },
    series: chartSeries.value,
  }
  chartInstance.value.setOption(option, true)
}

onMounted(() => {
  if (!chartRef.value) return
  chartInstance.value = init(chartRef.value)
  renderChart()
  resizeObserver = new ResizeObserver(() => chartInstance.value?.resize())
  resizeObserver.observe(chartRef.value)
})

watch(() => props.series, renderChart, { deep: true })

onUnmounted(() => {
  resizeObserver?.disconnect()
  chartInstance.value?.dispose()
})
</script>

<template>
  <div class="benchmark-chart">
    <div v-if="!hasData" class="empty-state">暂无可绘制的收益指数曲线</div>
    <div ref="chartRef" class="benchmark-chart__canvas" :class="{ 'is-empty': !hasData }" />
  </div>
</template>

<style scoped>
.benchmark-chart {
  min-height: 320px;
  position: relative;
}

.benchmark-chart__canvas {
  height: 320px;
  width: 100%;
}

.benchmark-chart__canvas.is-empty {
  visibility: hidden;
}
</style>
