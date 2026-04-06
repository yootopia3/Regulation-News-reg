import React from 'react'
import { Menu, Settings, Search } from 'lucide-react'

interface HeaderProps {
    onMenuClick: () => void;
    searchQuery: string;
    setSearchQuery: (query: string) => void;
}

export default function Header({ onMenuClick, searchQuery, setSearchQuery }: HeaderProps) {
    return (
        <header className="sticky top-0 z-50 bg-white border-b border-gray-100 h-[88px] px-6 pt-5 flex items-center gap-6 justify-between">
            {/* Left: Menu Button */}
            <button
                onClick={onMenuClick}
                className="p-2 -ml-2 text-gray-600 hover:bg-gray-100 rounded-full transition-colors flex-shrink-0"
                aria-label="Menu"
            >
                <Menu size={28} />
            </button>

            {/* Center: Search Bar */}
            <div className="flex-1 max-w-3xl mx-auto relative group">
                <div className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500 group-focus-within:text-blue-500 transition-colors">
                    <Search size={20} />
                </div>
                <input
                    type="text"
                    placeholder="키워드 검색 (예: 가계부채, 금리)"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full h-12 pl-12 pr-4 bg-gray-50 border border-gray-300 rounded-full text-base focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all placeholder:text-gray-400"
                />
            </div>

            {/* Right: Settings */}
            <button
                className="p-2 -mr-2 text-gray-400 hover:text-gray-600 rounded-full transition-colors flex-shrink-0"
                aria-label="Settings"
            >
                <Settings size={28} />
            </button>
        </header>
    )
}
