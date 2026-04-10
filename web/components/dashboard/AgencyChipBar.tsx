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

    const activeClass = 'bg-gray-900 text-white shadow-md'
    const inactiveClass = 'text-gray-500 hover:text-gray-900 bg-transparent'

    return (
        <div className="sticky top-[88px] z-40 h-[52px] bg-white/95 backdrop-blur-sm border-b border-gray-100 flex items-center gap-2 px-4 overflow-x-auto scrollbar-hide">
            <button
                onClick={() => handleChipClick(null)}
                className={`whitespace-nowrap rounded-full px-4 py-2 text-sm font-bold transition-all duration-200 flex-shrink-0 ${selectedAgency === null ? activeClass : inactiveClass}`}
            >
                전체
            </button>
            {agencies.map(code => (
                <button
                    key={code}
                    onClick={() => handleChipClick(code)}
                    className={`whitespace-nowrap rounded-full px-4 py-2 text-sm font-bold transition-all duration-200 flex-shrink-0 ${selectedAgency === code ? activeClass : inactiveClass}`}
                >
                    {chipLabels[code] ?? code}
                </button>
            ))}
        </div>
    )
}
