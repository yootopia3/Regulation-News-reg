
'use client'

import React, { useEffect, useState, useMemo } from 'react'
import { toKSTDate } from '@/utils/date' // Use new utils
import { supabase } from '@/utils/supabase/client'
import { getLastVisitTime, updateLastVisitTime, isArticleNew } from '@/utils/newArticleTracker'
import Header from './Header'
import SearchBar from './SearchBar'
import DateSection from './DateSection'
import ReportModal from '@/components/ReportModal' // Reuse existing modal
import NewsCard, { Article } from './NewsCard'
import Sidebar from './Sidebar'
import AgencyChipBar from './AgencyChipBar'
import {
    pressAgencies,
    regulationAgencies,
    sanctionAgencies,
    DashboardCategory,
} from './constants'
import { useHasNewByCategory } from './useHasNewByCategory'

export default function DashboardV2() {
    const [articles, setArticles] = useState<Article[]>([])
    const [loading, setLoading] = useState(true)
    const [searchQuery, setSearchQuery] = useState('')
    const [selectedAgency, setSelectedAgency] = useState<string | null>(null) // Agency filter
    const [currentCategory, setCurrentCategory] = useState<DashboardCategory>('press_release') // Category filter

    // UI State
    const [isAgencyExpanded, setIsAgencyExpanded] = useState(false) // Collapsible agency section (Press Release)
    const [isRegExpanded, setIsRegExpanded] = useState(false) // Collapsible regulation section
    const [isFSSRegGroupExpanded, setIsFSSRegGroupExpanded] = useState(false) // Nested collapsible FSS section in Regulation
    const [isReportModalOpen, setIsReportModalOpen] = useState(false)
    const [isMenuOpen, setIsMenuOpen] = useState(false) // Sidebar toggle
    const [isSanctionExpanded, setIsSanctionExpanded] = useState(false) // Collapsible sanction section
    const [viewMode, setViewMode] = useState<'date' | 'list'>('date') // View Toggle State
    const [selectedArticle, setSelectedArticle] = useState<Article | null>(null)
    const [lastVisitTime, setLastVisitTime] = useState<Date | null>(null) // For NEW badge tracking

    // Track NEW status for main menus (Dependent on lastVisitTime)
    const { hasNewPress, hasNewReg, hasNewSanction } = useHasNewByCategory(articles, lastVisitTime)

    const fetchArticles = async () => {
        setLoading(true)

        const [pressResult, regulationResult, sanctionResult] = await Promise.all([
            supabase
                .from('articles')
                .select('*')
                .in('agency', pressAgencies)
                .or('category.eq.press_release,category.is.null')
                .order('published_at', { ascending: false })
                .limit(1000),
            supabase
                .from('articles')
                .select('*')
                .in('agency', regulationAgencies)
                .eq('category', 'regulation_notice')
                .order('published_at', { ascending: false })
                .limit(1000),
            supabase
                .from('articles')
                .select('*')
                .in('agency', sanctionAgencies)
                .eq('category', 'sanction_notice')
                .order('published_at', { ascending: false })
                .limit(1000)
        ])

        const errors = [pressResult.error, regulationResult.error, sanctionResult.error].filter(Boolean)
        if (errors.length > 0) {
            console.error('Error fetching articles:', errors)
        }

        const mergedArticles = [
            ...(pressResult.data || []),
            ...(regulationResult.data || []),
            ...(sanctionResult.data || [])
        ]

        const dedupedArticles = Array.from(
            new Map(mergedArticles.map(article => [article.id, article])).values()
        ).sort((a, b) => new Date(b.published_at).getTime() - new Date(a.published_at).getTime())

        setArticles(dedupedArticles)
        setLoading(false)
    }

    // 1. Fetch Data & Track Visit
    useEffect(() => {
        // Get last visit time BEFORE updating (to show NEW badges correctly)
        const lastVisit = getLastVisitTime();
        setLastVisitTime(lastVisit);

        fetchArticles();

        // Update last visit time AFTER a short delay (so user sees NEW badges first)
        const timer = setTimeout(() => {
            updateLastVisitTime();
        }, 3000); // 3 second delay before marking as "visited"

        // Auto-open sidebar on mobile for first impression
        if (typeof window !== 'undefined' && window.innerWidth < 768) {
            // Small delay to ensure render cycle completes
            setTimeout(() => setIsMenuOpen(true), 100);
        }

        return () => clearTimeout(timer);
    }, [])

    // 2. Filter & Group Data
    const processedData = useMemo(() => {
        // A. Filter by Category & Agency
        let filtered = articles.filter(a => (a.category || 'press_release') === currentCategory)

        if (selectedAgency) {
            filtered = filtered.filter(a => a.agency === selectedAgency)
        }

        // B. Filter by Search Query
        if (searchQuery) {
            const lowerQ = searchQuery.toLowerCase()
            filtered = filtered.filter(a =>
                a.title.toLowerCase().includes(lowerQ) ||
                (a.analysis_result?.keywords || []).some((k: string) => k.toLowerCase().includes(lowerQ))
            )
        }

        // C. Add isNew flag to each article
        const articlesWithNewFlag = filtered.map(article => ({
            ...article,
            isNew: isArticleNew(article.created_at || article.published_at, lastVisitTime)
        }));

        // D. Group by Date
        const grouped: Record<string, Article[]> = {}
        articlesWithNewFlag.forEach(article => {
            const kstDate = toKSTDate(article.published_at)
            const dateKey = `${kstDate.getUTCFullYear()}. ${kstDate.getUTCMonth() + 1}. ${kstDate.getUTCDate()}`

            // Add Day of Week
            const weekDays = ['일', '월', '화', '수', '목', '금', '토']
            const fullDateTitle = `${dateKey} (${weekDays[kstDate.getUTCDay()]})`

            if (!grouped[fullDateTitle]) grouped[fullDateTitle] = []
            grouped[fullDateTitle].push(article)
        })

        return grouped
    }, [articles, searchQuery, selectedAgency, lastVisitTime, currentCategory])

    // 3. Handlers
    const handleGenerateReport = (article: Article) => {
        setSelectedArticle(article)
        setIsReportModalOpen(true)
    }

    // Sidebar handlers
    const handleCloseMenu = () => setIsMenuOpen(false)
    const handleSelectHome = () => { setCurrentCategory('press_release'); setSelectedAgency(null) }
    const handleSelectPress = (agency: string | null) => { setCurrentCategory('press_release'); setSelectedAgency(agency) }
    const handleSelectReg = (agency: string | null) => { setCurrentCategory('regulation_notice'); setSelectedAgency(agency) }
    const handleSelectSanction = (agency: string | null) => { setCurrentCategory('sanction_notice'); setSelectedAgency(agency) }
    const handleToggleAgency = () => { setIsAgencyExpanded(!isAgencyExpanded); setCurrentCategory('press_release'); setSelectedAgency(null) }
    const handleToggleReg = () => { setIsRegExpanded(!isRegExpanded); setCurrentCategory('regulation_notice'); setSelectedAgency(null) }
    const handleToggleFSSRegGroup = () => setIsFSSRegGroupExpanded(!isFSSRegGroupExpanded)
    const handleToggleSanction = () => { setIsSanctionExpanded(!isSanctionExpanded); setCurrentCategory('sanction_notice'); setSelectedAgency(null) }

    return (
        <div className="min-h-screen bg-[#F5F7FA] text-gray-900 font-sans selection:bg-blue-500/40 lg:flex">
            <Sidebar
                isMenuOpen={isMenuOpen}
                onCloseMenu={handleCloseMenu}
                currentCategory={currentCategory} selectedAgency={selectedAgency}
                onSelectHome={handleSelectHome} onSelectPress={handleSelectPress}
                onSelectReg={handleSelectReg} onSelectSanction={handleSelectSanction}
                isAgencyExpanded={isAgencyExpanded} isRegExpanded={isRegExpanded}
                isFSSRegGroupExpanded={isFSSRegGroupExpanded} isSanctionExpanded={isSanctionExpanded}
                onToggleAgency={handleToggleAgency} onToggleReg={handleToggleReg}
                onToggleFSSRegGroup={handleToggleFSSRegGroup} onToggleSanction={handleToggleSanction}
                hasNewPress={hasNewPress} hasNewReg={hasNewReg} hasNewSanction={hasNewSanction}
            />

            {/* Main Content Area - Push effect on md+ screens */}
            <div className={`flex-1 flex flex-col min-h-screen transition-all duration-300 ${isMenuOpen ? 'md:pl-[260px] lg:pl-0' : ''}`}>
                <Header
                    onMenuClick={() => setIsMenuOpen(prev => !prev)}
                    searchQuery={searchQuery}
                    setSearchQuery={setSearchQuery}
                />

                <main className="flex-1 p-4 md:p-8 max-w-5xl mx-auto w-full">
                    {/* Search Result Feedback */}
                    {searchQuery && (
                        <div className="mb-4 flex items-center justify-between bg-blue-50/50 p-3 rounded-lg border border-blue-100">
                            <div className="text-sm font-medium text-blue-900">
                                '<span className="font-bold">{searchQuery}</span>' 검색 결과: <span className="font-bold">{processedData ? Object.values(processedData).flat().length : 0}</span>건
                            </div>
                            <button
                                onClick={() => setSearchQuery('')}
                                className="text-xs text-blue-500 hover:text-blue-700 underline flex items-center gap-1"
                            >
                                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                                검색어 지우기
                            </button>
                        </div>
                    )}

                    {/* View Toggle (Centered, Black Active) */}
                    <div className="flex justify-center mb-6">
                        <div className="bg-white p-1 rounded-full flex items-center border border-gray-200 shadow-sm">
                            <button
                                onClick={() => setViewMode('date')}
                                className={`flex items-center gap-2 px-5 py-2 rounded-full text-sm font-bold transition-all duration-200 ${viewMode === 'date' ? 'bg-gray-900 text-white shadow-md' : 'text-gray-500 hover:text-gray-900'}`}
                            >
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                                날짜별
                            </button>
                            <button
                                onClick={() => setViewMode('list')}
                                className={`flex items-center gap-2 px-5 py-2 rounded-full text-sm font-bold transition-all duration-200 ${viewMode === 'list' ? 'bg-gray-900 text-white shadow-md' : 'text-gray-500 hover:text-gray-900'}`}
                            >
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h7" /></svg>
                                리스트
                            </button>
                        </div>
                    </div>

                    {/* Agency Chip Bar (sticky filter) */}
                    <AgencyChipBar
                        currentCategory={currentCategory}
                        selectedAgency={selectedAgency}
                        onSelectAgency={setSelectedAgency}
                    />

                    {loading ? (
                        <div className="flex flex-col items-center justify-center py-20 space-y-4">
                            <div className="w-8 h-8 border-4 border-[#3B82F6]/30 border-t-[#3B82F6] rounded-full animate-spin"></div>
                            <div className="text-sm text-gray-400 font-medium">데이터를 불러오는 중...</div>
                        </div>
                    ) : (
                        viewMode === 'date' ? (
                            // DATE VIEW
                            Object.entries(processedData)
                                .sort((a, b) => new Date(b[1][0].published_at).getTime() - new Date(a[1][0].published_at).getTime())
                                .map(([dateTitle, dayArticles], idx) => (
                                    <DateSection
                                        key={dateTitle}
                                        dateTitle={dateTitle}
                                        articles={dayArticles}
                                        defaultExpanded={false} // All collapsed by default
                                        onGenerateReport={handleGenerateReport}
                                        newCount={dayArticles.filter(a => a.isNew).length}
                                    />
                                ))
                        ) : (
                            // LIST VIEW
                            <div className="space-y-3 px-4">
                                {Object.values(processedData).flat()
                                    .sort((a, b) => {
                                        // 1. Date Desc
                                        const dateDiff = new Date(b.published_at).getTime() - new Date(a.published_at).getTime();
                                        if (dateDiff !== 0) return dateDiff;
                                        // 2. Score Desc
                                        return (b.analysis_result?.importance_score || 0) - (a.analysis_result?.importance_score || 0);
                                    })
                                    .map(article => (
                                        <NewsCard
                                            key={article.id}
                                            article={article}
                                            onGenerateReport={handleGenerateReport}
                                        />
                                    ))
                                }
                            </div>
                        )
                    )}

                    {!loading && Object.keys(processedData).length === 0 && (
                        <div className="flex flex-col items-center justify-center py-20 text-center px-6">
                            <p className="text-lg font-bold text-gray-400 mb-2">검색 결과가 없습니다.</p>
                            <p className="text-sm text-gray-400">다른 키워드로 검색해보세요.</p>
                            <button
                                onClick={() => setSearchQuery('')}
                                className="mt-6 px-6 py-2 bg-white border border-gray-300 rounded-full text-sm font-medium hover:bg-gray-50"
                            >
                                목록 초기화
                            </button>
                        </div>
                    )}
                </main>
            </div>

            {/* Report Modal (Legacy) */}
            {isReportModalOpen && selectedArticle && (
                <ReportModal
                    isOpen={isReportModalOpen}
                    onClose={() => setIsReportModalOpen(false)}
                    article={selectedArticle}
                />
            )}
        </div>
    )
}
