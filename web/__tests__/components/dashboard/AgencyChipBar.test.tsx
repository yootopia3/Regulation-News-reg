import { describe, it, expect } from 'vitest'

describe('chipLabels', () => {
    it('maps all press agencies to Korean short names', async () => {
        const { chipLabels, pressAgencies } = await import('@/components/dashboard/constants')
        for (const code of pressAgencies) {
            expect(chipLabels[code]).toBeDefined()
        }
        expect(chipLabels['MOEF']).toBe('기재부')
        expect(chipLabels['FSC']).toBe('금융위')
        expect(chipLabels['FSS']).toBe('금감원')
        expect(chipLabels['BOK']).toBe('한은')
        expect(chipLabels['MAFRA']).toBe('농식품부')
    })

    it('maps all regulation agencies to Korean short names', async () => {
        const { chipLabels, regulationAgencies } = await import('@/components/dashboard/constants')
        for (const code of regulationAgencies) {
            expect(chipLabels[code]).toBeDefined()
        }
        expect(chipLabels['FSC_REG']).toBe('금융위')
        expect(chipLabels['FSS_REG']).toBe('금감원(세칙)')
        expect(chipLabels['FSS_REG_INFO']).toBe('금감원(제개정)')
    })

    it('maps all sanction agencies to Korean short names', async () => {
        const { chipLabels, sanctionAgencies } = await import('@/components/dashboard/constants')
        for (const code of sanctionAgencies) {
            expect(chipLabels[code]).toBeDefined()
        }
        expect(chipLabels['FSS_SANCTION']).toBe('제재')
        expect(chipLabels['FSS_MGMT_NOTICE']).toBe('경영유의')
    })
})
