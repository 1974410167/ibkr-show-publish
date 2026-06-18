import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const source = readFileSync(
  fileURLToPath(new URL('./PortfolioManagerView.vue', import.meta.url)),
  'utf8',
)

describe('PortfolioManagerView baseline lab wiring', () => {
  it('loads account overview and passes latest report date to PerformanceBenchmarkPanel', () => {
    expect(source).toContain("import { useAccountOverviewData } from '@/composables/accountOverview'")
    expect(source).toContain('ensureAccountOverviewLoaded')
    expect(source).toContain(':latest-report-date="accountOverview?.report_date ?? null"')
  })
})
