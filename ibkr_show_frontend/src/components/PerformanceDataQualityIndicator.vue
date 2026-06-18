<script setup lang="ts">
import { computed, ref } from 'vue'

import {
  affectedBaselineLabels,
  performanceQualityTone,
  visiblePerformanceQualityMessages,
} from '@/components/performanceDataQuality'
import type { AccountPerformanceDataQuality, BaselinePerformanceSummary } from '@/types/performance'

const props = defineProps<{
  dataQuality: AccountPerformanceDataQuality
  limitations: string[]
  baselineSummaries?: BaselinePerformanceSummary[]
}>()

const open = ref(false)
const tone = computed(() => performanceQualityTone(props.dataQuality))
const affected = computed(() => affectedBaselineLabels(props.baselineSummaries ?? []))
const visibleMessages = computed(() => visiblePerformanceQualityMessages(props.limitations))
const rawLimitations = computed(() => props.limitations.slice(0, 8))

function toggle(): void {
  open.value = !open.value
}
</script>

<template>
  <div v-if="dataQuality !== 'complete'" class="quality-indicator" @mouseenter="open = true" @mouseleave="open = false">
    <button type="button" class="quality-indicator__button" :class="tone" @click="toggle">
      <i class="pi pi-exclamation-triangle" aria-hidden="true"></i>
      <span>部分数据缺失</span>
    </button>
    <div v-if="open" class="quality-indicator__popover">
      <strong>当前结果为 {{ dataQuality }}</strong>
      <p v-if="affected.length">受影响基准：{{ affected.join('、') }}</p>
      <p v-else>真实账户或基准序列存在轻微边界数据。</p>
      <ul v-if="visibleMessages.length">
        <li v-for="item in visibleMessages" :key="item.raw">{{ item.message }}</li>
      </ul>
      <details v-if="rawLimitations.length">
        <summary>查看原始 data limitations</summary>
        <code v-for="item in rawLimitations" :key="item">{{ item }}</code>
      </details>
    </div>
  </div>
</template>

<style scoped>
.quality-indicator {
  position: relative;
}

.quality-indicator__button {
  align-items: center;
  background: rgba(15, 26, 45, 0.72);
  border: 1px solid rgba(129, 160, 207, 0.14);
  border-radius: 999px;
  color: var(--color-text-secondary);
  cursor: pointer;
  display: inline-flex;
  gap: 0.4rem;
  padding: 0.42rem 0.7rem;
}

.quality-indicator__button.warning {
  border-color: rgba(255, 180, 84, 0.32);
  color: #ffb454;
}

.quality-indicator__button.error {
  border-color: rgba(255, 107, 125, 0.32);
  color: var(--color-negative);
}

.quality-indicator__popover {
  background: rgba(6, 12, 24, 0.98);
  border: 1px solid rgba(129, 160, 207, 0.2);
  border-radius: 8px;
  box-shadow: 0 18px 36px rgba(2, 10, 24, 0.45);
  color: var(--color-text-primary);
  display: grid;
  gap: 0.5rem;
  min-width: min(360px, calc(100vw - 32px));
  padding: 0.85rem;
  position: absolute;
  right: 0;
  top: calc(100% + 8px);
  z-index: 20;
}

.quality-indicator__popover p,
.quality-indicator__popover ul {
  margin: 0;
}

.quality-indicator__popover ul {
  padding-left: 1.1rem;
}

.quality-indicator__popover details {
  color: var(--color-text-secondary);
}

.quality-indicator__popover code {
  display: block;
  margin-top: 0.3rem;
  white-space: normal;
}
</style>
