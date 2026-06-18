<script setup lang="ts">
import type { PerformanceComparisonMethodology } from '@/types/performance'

defineProps<{
  methodology: PerformanceComparisonMethodology
}>()
</script>

<template>
  <section class="benchmark-methodology">
    <h3>方法说明</h3>
    <dl>
      <div>
        <dt>收益方法</dt>
        <dd>{{ methodology.return_method }}</dd>
      </div>
      <div>
        <dt>入金出金校正</dt>
        <dd>{{ methodology.cashflow_adjusted ? 'true' : 'false' }}</dd>
      </div>
      <div>
        <dt>价格字段</dt>
        <dd>{{ methodology.benchmark_price_field }}</dd>
      </div>
      <div>
        <dt>指数起点</dt>
        <dd>{{ methodology.base_index }}</dd>
      </div>
    </dl>
    <p>SPY/QQQ 同现金流基准：假设每次真实入金都买入对应 ETF，每次真实出金都卖出对应 ETF。</p>
    <p>起始组合买入并持有：假设从起点起不再交易，只持有当时组合，入金进入现金，出金扣现金。</p>
    <p><strong>value_added</strong> = 真实账户期末价值 - baseline 期末价值；<strong>excess_return</strong> = 真实账户 TWR 收益率 - baseline 收益率。</p>
  </section>
</template>

<style scoped>
.benchmark-methodology {
  color: var(--text-muted);
  display: grid;
  gap: 0.75rem;
}

.benchmark-methodology h3 {
  color: var(--text-primary);
  margin: 0;
}

.benchmark-methodology dl {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  margin: 0;
}

.benchmark-methodology div {
  border: 1px solid rgba(129, 160, 207, 0.14);
  border-radius: 8px;
  padding: 0.75rem;
}

.benchmark-methodology dt {
  color: var(--text-muted);
  font-size: 0.78rem;
}

.benchmark-methodology dd {
  color: var(--text-primary);
  margin: 0.25rem 0 0;
}

.benchmark-methodology p {
  margin: 0;
}
</style>
