import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

afterEach(cleanup)

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

describe('AgencyChipBar rendering', () => {
    it('renders "전체" + 4 press agency chips for press_release category', async () => {
        const AgencyChipBar = (await import('@/components/dashboard/AgencyChipBar')).default
        render(
            <AgencyChipBar
                currentCategory="press_release"
                selectedAgency={null}
                onSelectAgency={() => {}}
            />
        )
        expect(screen.getByText('전체')).toBeInTheDocument()
        expect(screen.getByText('금융위')).toBeInTheDocument()
        expect(screen.getByText('금감원')).toBeInTheDocument()
        expect(screen.getByText('기재부')).toBeInTheDocument()
        expect(screen.getByText('한은')).toBeInTheDocument()
        expect(screen.queryByText('농식품부')).not.toBeInTheDocument()
        expect(screen.getAllByRole('button')).toHaveLength(5)
    })

    it('renders "전체" + 3 regulation chips for regulation_notice category', async () => {
        const AgencyChipBar = (await import('@/components/dashboard/AgencyChipBar')).default
        render(
            <AgencyChipBar
                currentCategory="regulation_notice"
                selectedAgency={null}
                onSelectAgency={() => {}}
            />
        )
        expect(screen.getByText('전체')).toBeInTheDocument()
        expect(screen.getAllByRole('button')).toHaveLength(4)
    })

    it('renders "전체" + 2 sanction chips for sanction_notice category', async () => {
        const AgencyChipBar = (await import('@/components/dashboard/AgencyChipBar')).default
        render(
            <AgencyChipBar
                currentCategory="sanction_notice"
                selectedAgency={null}
                onSelectAgency={() => {}}
            />
        )
        expect(screen.getByText('전체')).toBeInTheDocument()
        expect(screen.getAllByRole('button')).toHaveLength(3)
    })
})

describe('AgencyChipBar toggle logic', () => {
    it('calls onSelectAgency with agency code when a chip is clicked', async () => {
        const onSelectAgency = vi.fn()
        const AgencyChipBar = (await import('@/components/dashboard/AgencyChipBar')).default
        render(
            <AgencyChipBar
                currentCategory="press_release"
                selectedAgency={null}
                onSelectAgency={onSelectAgency}
            />
        )
        await userEvent.click(screen.getByText('금융위'))
        expect(onSelectAgency).toHaveBeenCalledWith('FSC')
    })

    it('calls onSelectAgency(null) when the same chip is clicked again (toggle off)', async () => {
        const onSelectAgency = vi.fn()
        const AgencyChipBar = (await import('@/components/dashboard/AgencyChipBar')).default
        render(
            <AgencyChipBar
                currentCategory="press_release"
                selectedAgency="FSC"
                onSelectAgency={onSelectAgency}
            />
        )
        await userEvent.click(screen.getByText('금융위'))
        expect(onSelectAgency).toHaveBeenCalledWith(null)
    })

    it('calls onSelectAgency(null) when "전체" chip is clicked', async () => {
        const onSelectAgency = vi.fn()
        const AgencyChipBar = (await import('@/components/dashboard/AgencyChipBar')).default
        render(
            <AgencyChipBar
                currentCategory="press_release"
                selectedAgency="FSC"
                onSelectAgency={onSelectAgency}
            />
        )
        await userEvent.click(screen.getByText('전체'))
        expect(onSelectAgency).toHaveBeenCalledWith(null)
    })
})

describe('AgencyChipBar active state', () => {
    it('applies active class to the selected agency chip', async () => {
        const AgencyChipBar = (await import('@/components/dashboard/AgencyChipBar')).default
        render(
            <AgencyChipBar
                currentCategory="press_release"
                selectedAgency="FSC"
                onSelectAgency={() => {}}
            />
        )
        const fscButton = screen.getByText('금융위')
        expect(fscButton.className).toContain('border-gray-900')
        const allButton = screen.getByText('전체')
        expect(allButton.className).not.toContain('border-gray-900')
    })

    it('applies active class to "전체" when selectedAgency is null', async () => {
        const AgencyChipBar = (await import('@/components/dashboard/AgencyChipBar')).default
        render(
            <AgencyChipBar
                currentCategory="press_release"
                selectedAgency={null}
                onSelectAgency={() => {}}
            />
        )
        const allButton = screen.getByText('전체')
        expect(allButton.className).toContain('border-gray-900')
    })
})
