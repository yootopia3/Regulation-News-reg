
import React, { useState } from 'react'
import { Search, X } from 'lucide-react'

interface SearchBarProps {
    onSearch: (query: string) => void;
}

export default function SearchBar({ onSearch }: SearchBarProps) {
    const [query, setQuery] = useState('')

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        onSearch(query)
    }

    const clearSearch = () => {
        setQuery('')
        onSearch('')
    }

    return (
        <div className="bg-white px-4 py-3 border-b border-gray-100 sticky top-14 z-40">
            <form onSubmit={handleSubmit} className="relative">
                <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="키워드 검색 (예: 가계부채, 금리)"
                    className="w-full h-10 pl-10 pr-10 bg-gray-50 border-none rounded-xl text-sm text-gray-800 placeholder-gray-400 focus:ring-2 focus:ring-[#5B4BFF]/20 focus:bg-white transition-all"
                />
                <Search
                    size={18}
                    className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
                />
                {query && (
                    <button
                        type="button"
                        onClick={clearSearch}
                        className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600 rounded-full"
                    >
                        <X size={16} />
                    </button>
                )}
            </form>
        </div>
    )
}
