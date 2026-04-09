'use client'

import React from 'react'
import AgencyIcon from './AgencyIcon'
import {
    agencyOrder,
    regAgencyOrder,
    sanctionAgencyOrder,
    agencyNames,
    regAgencyNames,
    sanctionAgencyNames,
    DashboardCategory,
} from './constants'

export type SidebarProps = {
    // Open/close
    isMenuOpen: boolean
    onCloseMenu: () => void

    // Selection state
    currentCategory: DashboardCategory
    selectedAgency: string | null

    // Selection handlers
    onSelectHome: () => void
    onSelectPress: (agency: string | null) => void
    onSelectReg: (agency: string | null) => void
    onSelectSanction: (agency: string | null) => void

    // Expansion state
    isAgencyExpanded: boolean
    isRegExpanded: boolean
    isFSSRegGroupExpanded: boolean
    isSanctionExpanded: boolean

    // Expansion toggles
    onToggleAgency: () => void
    onToggleReg: () => void
    onToggleFSSRegGroup: () => void
    onToggleSanction: () => void

    // NEW badges
    hasNewPress: boolean
    hasNewReg: boolean
    hasNewSanction: boolean
}

export default function Sidebar(props: SidebarProps): React.ReactElement {
    const {
        isMenuOpen,
        onCloseMenu,
        currentCategory,
        selectedAgency,
        onSelectHome,
        onSelectPress,
        onSelectReg,
        onSelectSanction,
        isAgencyExpanded,
        isRegExpanded,
        isFSSRegGroupExpanded,
        isSanctionExpanded,
        onToggleAgency,
        onToggleReg,
        onToggleFSSRegGroup,
        onToggleSanction,
        hasNewPress,
        hasNewReg,
        hasNewSanction,
    } = props

    return (
        <>
            {/* Mobile Backdrop */}
            {isMenuOpen && (
                <div
                    className="fixed inset-0 bg-black/40 z-50 transition-opacity duration-300 md:hidden"
                    onClick={() => onCloseMenu()}
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
                            onClick={() => onSelectHome()}
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
                            onClick={() => onToggleAgency()}
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
                                    onClick={() => onSelectPress(null)}
                                    className={`flex items-center gap-3 w-full text-left px-4 py-2.5 rounded-xl transition-all ${currentCategory === 'press_release' && selectedAgency === null ? 'text-white bg-[#3B82F6]' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
                                >
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 12h16M4 18h16" /></svg>
                                    <span className="text-sm">전체</span>
                                </button>

                                {agencyOrder.map((code) => (
                                    <button
                                        key={code}
                                        onClick={() => onSelectPress(code)}
                                        className={`flex items-center gap-3 w-full text-left px-4 py-2.5 rounded-xl transition-all ${currentCategory === 'press_release' && selectedAgency === code ? 'text-white bg-[#3B82F6]' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
                                    >
                                        <AgencyIcon code={code} />
                                        <span className="text-sm">{agencyNames[code]}</span>
                                    </button>
                                ))}
                            </div>
                        )}

                        {/* Regulation Section */}
                        <div className="my-2 border-t border-white/5"></div>
                        <button
                            onClick={() => onToggleReg()}
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
                                    onClick={() => onSelectReg(null)}
                                    className={`flex items-center gap-3 w-full text-left px-4 py-2.5 rounded-xl transition-all ${currentCategory === 'regulation_notice' && selectedAgency === null ? 'text-white bg-[#3B82F6]' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
                                >
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 12h16M4 18h16" /></svg>
                                    <span className="text-sm">전체</span>
                                </button>

                                {/* 2. FSC (Regulation) */}
                                <button
                                    onClick={() => onSelectReg('FSC_REG')}
                                    className={`flex items-center gap-3 w-full text-left px-4 py-2.5 rounded-xl transition-all ${currentCategory === 'regulation_notice' && selectedAgency === 'FSC_REG' ? 'text-white bg-[#3B82F6]' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
                                >
                                    <AgencyIcon code="FSC_REG" />
                                    <span className="text-sm">금융위원회</span>
                                </button>

                                {/* 3. FSS (Group) */}
                                <div className="mt-1">
                                    <button
                                        onClick={() => onToggleFSSRegGroup()}
                                        className={`flex items-center justify-between w-full px-4 py-2.5 rounded-xl transition-all text-gray-400 hover:text-white hover:bg-white/5`}
                                    >
                                        <div className="flex items-center gap-3">
                                            <AgencyIcon code="FSS" />
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
                                                onClick={() => onSelectReg('FSS_REG')}
                                                className={`flex items-center gap-2 w-full text-left px-3 py-2 rounded-lg transition-all text-xs ${currentCategory === 'regulation_notice' && selectedAgency === 'FSS_REG' ? 'text-white bg-white/10' : 'text-gray-500 hover:text-gray-300'}`}
                                            >
                                                <span>세칙 제개정 예고</span>
                                            </button>
                                            <button
                                                onClick={() => onSelectReg('FSS_REG_INFO')}
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
                            onClick={() => onToggleSanction()}
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
                                    onClick={() => onSelectSanction(null)}
                                    className={`flex items-center gap-3 w-full text-left px-4 py-2.5 rounded-xl transition-all ${currentCategory === 'sanction_notice' && selectedAgency === null ? 'text-white bg-[#3B82F6]' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
                                >
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 12h16M4 18h16" /></svg>
                                    <span className="text-sm">전체</span>
                                </button>

                                {sanctionAgencyOrder.map((code) => (
                                    <button
                                        key={code}
                                        onClick={() => onSelectSanction(code)}
                                        className={`flex items-center gap-3 w-full text-left px-4 py-2.5 rounded-xl transition-all ${currentCategory === 'sanction_notice' && selectedAgency === code ? 'text-white bg-[#3B82F6]' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
                                    >
                                        <AgencyIcon code={code} />
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
}
