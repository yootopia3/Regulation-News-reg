
'use client'

import React, { useEffect, useState, useMemo } from 'react'
import { toKSTDate } from '@/utils/date' // Use new utils
import { supabase } from '@/utils/supabase/client'
import { getLastVisitTime, updateLastVisitTime, isArticleNew, countNewArticles } from '@/utils/newArticleTracker'
import Header from './Header'
import SearchBar from './SearchBar'
import DateSection from './DateSection'
import ReportModal from '@/components/ReportModal' // Reuse existing modal
import NewsCard, { Article } from './NewsCard'

export default function DashboardV2() {
    const pressAgencies = ['MOEF', 'FSC', 'FSS', 'BOK']
    const regulationAgencies = ['FSC_REG', 'FSS_REG', 'FSS_REG_INFO']
    const sanctionAgencies = ['FSS_SANCTION', 'FSS_MGMT_NOTICE']

    const [articles, setArticles] = useState<Article[]>([])
    const [loading, setLoading] = useState(true)
    const [searchQuery, setSearchQuery] = useState('')
    const [selectedAgency, setSelectedAgency] = useState<string | null>(null) // Agency filter
    const [currentCategory, setCurrentCategory] = useState<'press_release' | 'regulation_notice' | 'sanction_notice'>('press_release') // Category filter

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
    const hasNewPress = useMemo(() => {
        return articles.some(a =>
            (a.category === 'press_release' || !a.category) &&
            isArticleNew(a.created_at || a.published_at, lastVisitTime)
        )
    }, [articles, lastVisitTime])

    const hasNewReg = useMemo(() => {
        return articles.some(a =>
            a.category === 'regulation_notice' &&
            isArticleNew(a.created_at || a.published_at, lastVisitTime)
        )
    }, [articles, lastVisitTime])

    const hasNewSanction = useMemo(() => {
        return articles.some(a =>
            a.category === 'sanction_notice' &&
            isArticleNew(a.created_at || a.published_at, lastVisitTime)
        )
    }, [articles, lastVisitTime])

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

    // Agency Mapping (EN -> KR) - Reordered: MOEF, FSC, FSS, BOK
    const agencyOrder = pressAgencies
    const agencyNames: Record<string, string> = {
        'MOEF': '기획재정부',
        'FSC': '금융위원회',
        'FSS': '금융감독원',
        'BOK': '한국은행'
    }

    // Regulation Agencies (FSS has two sub-categories)
    const regAgencyOrder = regulationAgencies
    const regAgencyNames: Record<string, string> = {
        'FSC_REG': '금융위원회',
        'FSS_REG': '금감원 - 세칙 제개정 예고',
        'FSS_REG_INFO': '금감원 - 최근 제개정 정보'
    }

    // Sanction Agencies
    const sanctionAgencyOrder = sanctionAgencies
    const sanctionAgencyNames: Record<string, string> = {
        'FSS_SANCTION': '검사결과 제재',
        'FSS_MGMT_NOTICE': '경영유의사항'
    }

    // Agency Icon Mapping (FSC = Gavel + Coin icon)
    const agencyIcons: Record<string, React.ReactNode> = {
        'MOEF': <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" /></svg>,
        'FSC': <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /><circle cx="17" cy="17" r="4" strokeWidth={1.5} /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 15.5v3M15.5 17h3" /></svg>,
        'FSS': <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>,
        'BOK': <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 14v3m4-3v3m4-3v3M3 21h18M3 10h18M3 7l9-4 9 4M4 10h16v11H4V10z" /></svg>,
        'FSC_REG': <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /><circle cx="17" cy="17" r="4" strokeWidth={1.5} /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 15.5v3M15.5 17h3" /></svg>,
        'FSS_REG': <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>,
        'FSS_REG_INFO': <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>,
        'FSS_SANCTION': <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>,
        'FSS_MGMT_NOTICE': <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" /></svg>,
    }

    // Sidebar Content (StockEasy Style: Dark Theme)
    // Desktop: Always visible | Mobile: Slide-in drawer
    const Sidebar = () => (
        <>
            {/* Mobile Backdrop */}
            {isMenuOpen && (
                <div
                    className="fixed inset-0 bg-black/40 z-50 transition-opacity duration-300 md:hidden"
                    onClick={() => setIsMenuOpen(false)}
                />
            )}

            {/* Drawer - Always visible on lg:, slide-in on mobile */}
            <aside className={`
                fixed inset-y-0 left-0 w-[260px] bg-[#1E1E1E]/80 backdrop-blur-md text-white z-[60] 
                transform transition-transform duration-300 shadow-2xl
                lg:translate-x-0 lg:static lg:z-auto
                ${isMenuOpen ? 'translate-x-0' : '-translate-x-full'}
            `}>
                <div className="p-6 h-full flex flex-col">
                    {/* Brand Logo */}
                    <div className="mb-10 flex items-center gap-1">
                        <img src="/logo_perfect.png" alt="RegBrief" className="w-14 h-14 object-contain" />
                        <h2 className="text-3xl font-bold tracking-wide leading-none pb-1">
                            <span className="bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">Reg</span>
                            <span className="bg-gradient-to-br from-white to-gray-400 bg-clip-text text-transparent ml-0.5">Brief</span>
                        </h2>
                    </div>

                    {/* Menu Items */}
                    <nav className="flex-1 space-y-2">
                        <button
                            onClick={() => {
                                setCurrentCategory('press_release')
                                setSelectedAgency(null)
                            }}
                            className={`flex items-center gap-3 w-full text-left px-4 py-3 rounded-xl transition-all ${currentCategory === 'press_release' && !selectedAgency ? 'text-white bg-white/10' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" /></svg>
                            <span className="font-medium">홈</span>
                        </button>
                        <button className="flex items-center gap-3 w-full text-left px-4 py-3 text-gray-400 hover:text-white hover:bg-white/5 rounded-xl transition-all">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" /></svg>
                            <span className="font-medium">스크랩 보관함</span>
                        </button>

                        <div className="my-6 border-t border-white/10"></div>

                        {/* Collapsible Agency Section (Press Release) */}
                        <button
                            onClick={() => {
                                setIsAgencyExpanded(!isAgencyExpanded)
                                setCurrentCategory('press_release')
                                setSelectedAgency(null)
                            }}
                            className="flex items-center justify-between w-full px-4 py-3 text-gray-300 hover:text-white hover:bg-white/5 rounded-xl transition-all relative"
                        >
                            <div className="flex items-center gap-2">
                                <span className="font-medium">보도자료</span>
                                {hasNewPress && (
                                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-red-500/20 text-red-500 border border-red-500/30 animate-pulse">
                                        NEW
                                    </span>
                                )}
                            </div>
                            <svg
                                className={`w-4 h-4 transition-transform duration-200 ${isAgencyExpanded ? 'rotate-180' : ''}`}
                                fill="none" stroke="currentColor" viewBox="0 0 24 24"
                            >
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                        </button>

                        {isAgencyExpanded && (
                            <div className="mt-2 space-y-1 pl-2">
                                <button
                                    onClick={() => {
                                        setCurrentCategory('press_release')
                                        setSelectedAgency(null)
                                    }}
                                    className={`flex items-center gap-3 w-full text-left px-4 py-2.5 rounded-xl transition-all ${currentCategory === 'press_release' && selectedAgency === null ? 'text-white bg-[#3B82F6]' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
                                >
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 12h16M4 18h16" /></svg>
                                    <span className="text-sm">전체</span>
                                </button>

                                {agencyOrder.map((code) => (
                                    <button
                                        key={code}
                                        onClick={() => {
                                            setCurrentCategory('press_release')
                                            setSelectedAgency(code)
                                        }}
                                        className={`flex items-center gap-3 w-full text-left px-4 py-2.5 rounded-xl transition-all ${currentCategory === 'press_release' && selectedAgency === code ? 'text-white bg-[#3B82F6]' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
                                    >
                                        {agencyIcons[code]}
                                        <span className="text-sm">{agencyNames[code]}</span>
                                    </button>
                                ))}
                            </div>
                        )}

                        {/* Regulation Section */}
                        <div className="my-2 border-t border-white/5"></div>
                        <button
                            onClick={() => {
                                setIsRegExpanded(!isRegExpanded)
                                setCurrentCategory('regulation_notice')
                                setSelectedAgency(null)
                            }}
                            className="flex items-center justify-between w-full px-4 py-3 text-gray-300 hover:text-white hover:bg-white/5 rounded-xl transition-all"
                        >
                            <div className="flex items-center gap-2">
                                <span className="font-medium">규제개정</span>
                                {hasNewReg && (
                                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-red-500/20 text-red-500 border border-red-500/30 animate-pulse">
                                        NEW
                                    </span>
                                )}
                            </div>
                            <svg
                                className={`w-4 h-4 transition-transform duration-200 ${isRegExpanded ? 'rotate-180' : ''}`}
                                fill="none" stroke="currentColor" viewBox="0 0 24 24"
                            >
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                        </button>

                        {isRegExpanded && (
                            <div className="mt-2 space-y-1 pl-2">
                                {/* 1. ALL */}
                                <button
                                    onClick={() => {
                                        setCurrentCategory('regulation_notice')
                                        setSelectedAgency(null)
                                    }}
                                    className={`flex items-center gap-3 w-full text-left px-4 py-2.5 rounded-xl transition-all ${currentCategory === 'regulation_notice' && selectedAgency === null ? 'text-white bg-[#3B82F6]' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
                                >
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 12h16M4 18h16" /></svg>
                                    <span className="text-sm">전체</span>
                                </button>

                                {/* 2. FSC (Regulation) */}
                                <button
                                    onClick={() => {
                                        setCurrentCategory('regulation_notice')
                                        setSelectedAgency('FSC_REG')
                                    }}
                                    className={`flex items-center gap-3 w-full text-left px-4 py-2.5 rounded-xl transition-all ${currentCategory === 'regulation_notice' && selectedAgency === 'FSC_REG' ? 'text-white bg-[#3B82F6]' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
                                >
                                    {agencyIcons['FSC_REG']}
                                    <span className="text-sm">금융위원회</span>
                                </button>

                                {/* 3. FSS (Group) */}
                                <div className="mt-1">
                                    <button
                                        onClick={() => setIsFSSRegGroupExpanded(!isFSSRegGroupExpanded)}
                                        className={`flex items-center justify-between w-full px-4 py-2.5 rounded-xl transition-all text-gray-400 hover:text-white hover:bg-white/5`}
                                    >
                                        <div className="flex items-center gap-3">
                                            {agencyIcons['FSS']}
                                            <span className="text-sm">금융감독원</span>
                                        </div>
                                        <svg
                                            className={`w-3 h-3 transition-transform duration-200 ${isFSSRegGroupExpanded ? 'rotate-180' : ''}`}
                                            fill="none" stroke="currentColor" viewBox="0 0 24 24"
                                        >
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                        </svg>
                                    </button>

                                    {/* FSS Sub-menu */}
                                    {isFSSRegGroupExpanded && (
                                        <div className="mt-1 ml-4 border-l border-white/10 pl-2 space-y-1">
                                            <button
                                                onClick={() => {
                                                    setCurrentCategory('regulation_notice')
                                                    setSelectedAgency('FSS_REG')
                                                }}
                                                className={`flex items-center gap-2 w-full text-left px-3 py-2 rounded-lg transition-all text-xs ${currentCategory === 'regulation_notice' && selectedAgency === 'FSS_REG' ? 'text-white bg-white/10' : 'text-gray-500 hover:text-gray-300'}`}
                                            >
                                                <span>세칙 제개정 예고</span>
                                            </button>
                                            <button
                                                onClick={() => {
                                                    setCurrentCategory('regulation_notice')
                                                    setSelectedAgency('FSS_REG_INFO')
                                                }}
                                                className={`flex items-center gap-2 w-full text-left px-3 py-2 rounded-lg transition-all text-xs ${currentCategory === 'regulation_notice' && selectedAgency === 'FSS_REG_INFO' ? 'text-white bg-white/10' : 'text-gray-500 hover:text-gray-300'}`}
                                            >
                                                <span>최근 제개정 정보</span>
                                            </button>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* Sanction Notice Section */}
                        <div className="my-2 border-t border-white/5"></div>
                        <button
                            onClick={() => {
                                setIsSanctionExpanded(!isSanctionExpanded)
                                setCurrentCategory('sanction_notice')
                                setSelectedAgency(null)
                            }}
                            className="flex items-center justify-between w-full px-4 py-3 text-gray-300 hover:text-white hover:bg-white/5 rounded-xl transition-all"
                        >
                            <div className="flex items-center gap-2">
                                <span className="font-medium">제재 공시</span>
                                {hasNewSanction && (
                                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-red-500/20 text-red-500 border border-red-500/30 animate-pulse">
                                        NEW
                                    </span>
                                )}
                            </div>
                            <svg
                                className={`w-4 h-4 transition-transform duration-200 ${isSanctionExpanded ? 'rotate-180' : ''}`}
                                fill="none" stroke="currentColor" viewBox="0 0 24 24"
                            >
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                        </button>

                        {isSanctionExpanded && (
                            <div className="mt-2 space-y-1 pl-2">
                                <button
                                    onClick={() => {
                                        setCurrentCategory('sanction_notice')
                                        setSelectedAgency(null)
                                    }}
                                    className={`flex items-center gap-3 w-full text-left px-4 py-2.5 rounded-xl transition-all ${currentCategory === 'sanction_notice' && selectedAgency === null ? 'text-white bg-[#3B82F6]' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
                                >
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 12h16M4 18h16" /></svg>
                                    <span className="text-sm">전체</span>
                                </button>

                                {sanctionAgencyOrder.map((code) => (
                                    <button
                                        key={code}
                                        onClick={() => {
                                            setCurrentCategory('sanction_notice')
                                            setSelectedAgency(code)
                                        }}
                                        className={`flex items-center gap-3 w-full text-left px-4 py-2.5 rounded-xl transition-all ${currentCategory === 'sanction_notice' && selectedAgency === code ? 'text-white bg-[#3B82F6]' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
                                    >
                                        {agencyIcons[code]}
                                        <span className="text-sm">{sanctionAgencyNames[code]}</span>
                                    </button>
                                ))}
                            </div>
                        )}
                    </nav>

                    {/* Footer */}
                    <div className="text-xs text-gray-600 mt-auto flex items-center gap-2">
                        <svg className="w-3 h-3 text-[#3B82F6]" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2L15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2z" /></svg>
                        v2.0.0 (Beta)
                    </div>
                </div>
            </aside>
        </>
    )

    return (
        <div className="min-h-screen bg-[#F5F7FA] text-gray-900 font-sans selection:bg-blue-500/40 lg:flex">
            <Sidebar />

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
                    article={selectedArticle as any}
                />
            )}
        </div>
    )
}
