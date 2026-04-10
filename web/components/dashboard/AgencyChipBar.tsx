import {
    pressAgencies,
    regulationAgencies,
    sanctionAgencies,
    chipLabels,
    DashboardCategory,
} from './constants'

interface AgencyChipBarProps {
    currentCategory: DashboardCategory
    selectedAgency: string | null
    onSelectAgency: (agency: string | null) => void
}

const agenciesByCategory: Record<DashboardCategory, readonly string[]> = {
    press_release: pressAgencies,
    regulation_notice: regulationAgencies,
    sanction_notice: sanctionAgencies,
}

export default function AgencyChipBar({ currentCategory, selectedAgency, onSelectAgency }: AgencyChipBarProps) {
    const agencies = agenciesByCategory[currentCategory]

    const handleChipClick = (agency: string | null) => {
        if (agency === null || agency === selectedAgency) {
            onSelectAgency(null)
        } else {
            onSelectAgency(agency)
        }
    }

    const activeClass = 'text-gray-900 font-bold border-b-2 border-gray-900'
    const inactiveClass = 'text-gray-400 font-medium hover:text-gray-600'

    return (
        <div className="sticky top-[88px] z-40 h-[44px] bg-[#F5F7FA] border-b border-gray-200 flex items-center px-4 gap-5 overflow-x-auto scrollbar-hide">
            <button
                onClick={() => handleChipClick(null)}
                className={`whitespace-nowrap pb-2 pt-1 text-sm transition-all duration-200 flex-shrink-0 ${selectedAgency === null ? activeClass : inactiveClass}`}
            >
                전체
            </button>
            {agencies.map(code => (
                <button
                    key={code}
                    onClick={() => handleChipClick(code)}
                    className={`whitespace-nowrap pb-2 pt-1 text-sm transition-all duration-200 flex-shrink-0 ${selectedAgency === code ? activeClass : inactiveClass}`}
                >
                    {chipLabels[code] ?? code}
                </button>
            ))}
        </div>
    )
}
