'use client'

import React from 'react'
import Image from 'next/image'
import Link from 'next/link'
import AgencyIcon from './AgencyIcon'
import {
    agencyOrder,
    sanctionAgencyOrder,
    agencyNames,
    sanctionAgencyNames,
    DashboardCategory,
} from './constants'

export type SidebarProps = {
    // Open/close
    isMenuOpen: boolean
    onCloseMenu: () => void

    // Selection state
    currentCategory: DashboardCategory | null
    isBoardActive?: boolean
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
        isBoardActive = false,
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
                fixed inset-y-0 left-0 h-screen w-[260px] bg-gradient-to-b from-[#004C9B] via-[#0B63CE] to-[#002E6D] text-white z-[60]
                transform transition-transform duration-300 shadow-2xl
                lg:translate-x-0 lg:sticky lg:top-0 lg:z-auto lg:shrink-0
                ${isMenuOpen ? 'translate-x-0' : '-translate-x-full'}
            `}>
                <div className="h-full overflow-y-auto overscroll-contain p-6 flex flex-col">
                    {/* Brand Logo */}
                    <button
                        type="button"
                        onClick={() => {
                            onSelectHome()
                            onCloseMenu()
                        }}
                        className="mb-10 w-full text-left"
                        aria-label="홈으로 이동"
                    >
                        <div className="mb-3 rounded-lg bg-white px-3 py-3 shadow-sm">
                            <Image
                                src="/ibk-regulatory-brand.png"
                                alt="IBK기업은행 by 내부통제총괄부"
                                width={420}
                                height={136}
                                className="h-auto w-full object-contain"
                            />
                        </div>
                        <h2 className="leading-none pb-1">
                            <span className="mt-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-blue-100/80">
                                <Image src="/icons/regbrief-09-32.png" alt="" width={24} height={24} className="rounded-md" />
                                Regulatory News
                            </span>
                        </h2>
                    </button>

                    {/* Menu Items */}
                    <nav aria-label="주 메뉴" className="flex-1 space-y-2">
                        <button
                            onClick={() => onSelectHome()}
                            className={`flex items-center gap-3 w-full text-left px-4 py-3 rounded-xl transition-all ${currentCategory === 'press_release' && !selectedAgency ? 'text-[#003B7A] bg-white shadow-sm' : 'text-blue-100/80 hover:text-white hover:bg-white/10'}`}
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" /></svg>
                            <span className="font-medium">홈</span>
                        </button>

                        <div className="my-6 border-t border-white/15"></div>

                        {/* Collapsible Agency Section (Press Release) */}
                        <button
                            onClick={() => onToggleAgency()}
                            className="flex items-center justify-between w-full px-4 py-3 text-blue-50 hover:text-white hover:bg-white/10 rounded-xl transition-all relative"
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
                                    className={`flex items-center gap-3 w-full text-left px-4 py-2.5 rounded-xl transition-all ${currentCategory === 'press_release' && selectedAgency === null ? 'text-[#003B7A] bg-white shadow-sm' : 'text-blue-100/80 hover:text-white hover:bg-white/10'}`}
                                >
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 12h16M4 18h16" /></svg>
                                    <span className="text-sm">전체</span>
                                </button>

                                {agencyOrder.map((code) => (
                                    <button
                                        key={code}
                                        onClick={() => onSelectPress(code)}
                                        className={`flex items-center gap-3 w-full text-left px-4 py-2.5 rounded-xl transition-all ${currentCategory === 'press_release' && selectedAgency === code ? 'text-[#003B7A] bg-white shadow-sm' : 'text-blue-100/80 hover:text-white hover:bg-white/10'}`}
                                    >
                                        <AgencyIcon code={code} />
                                        <span className="text-sm">{agencyNames[code]}</span>
                                    </button>
                                ))}
                            </div>
                        )}

                        {/* Regulation Section */}
                        <div className="my-2 border-t border-white/15"></div>
                        <button
                            onClick={() => onToggleReg()}
                            className="flex items-center justify-between w-full px-4 py-3 text-blue-50 hover:text-white hover:bg-white/10 rounded-xl transition-all"
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
                                    className={`flex items-center gap-3 w-full text-left px-4 py-2.5 rounded-xl transition-all ${currentCategory === 'regulation_notice' && selectedAgency === null ? 'text-[#003B7A] bg-white shadow-sm' : 'text-blue-100/80 hover:text-white hover:bg-white/10'}`}
                                >
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 12h16M4 18h16" /></svg>
                                    <span className="text-sm">전체</span>
                                </button>

                                {/* 2. FSC (Regulation) */}
                                <button
                                    onClick={() => onSelectReg('FSC_REG')}
                                    className={`flex items-center gap-3 w-full text-left px-4 py-2.5 rounded-xl transition-all ${currentCategory === 'regulation_notice' && selectedAgency === 'FSC_REG' ? 'text-[#003B7A] bg-white shadow-sm' : 'text-blue-100/80 hover:text-white hover:bg-white/10'}`}
                                >
                                    <AgencyIcon code="FSC_REG" />
                                    <span className="text-sm">금융위원회</span>
                                </button>

                                {/* 3. FSS (Group) */}
                                <div className="mt-1">
                                    <button
                                        onClick={() => onToggleFSSRegGroup()}
                                        className={`flex items-center justify-between w-full px-4 py-2.5 rounded-xl transition-all text-blue-100/80 hover:text-white hover:bg-white/10`}
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
                                                className={`flex items-center gap-2 w-full text-left px-3 py-2 rounded-lg transition-all text-xs ${currentCategory === 'regulation_notice' && selectedAgency === 'FSS_REG' ? 'text-white bg-white/15' : 'text-blue-100/70 hover:text-white'}`}
                                            >
                                                <span>세칙 제개정 예고</span>
                                            </button>
                                            <button
                                                onClick={() => onSelectReg('FSS_REG_INFO')}
                                                className={`flex items-center gap-2 w-full text-left px-3 py-2 rounded-lg transition-all text-xs ${currentCategory === 'regulation_notice' && selectedAgency === 'FSS_REG_INFO' ? 'text-white bg-white/15' : 'text-blue-100/70 hover:text-white'}`}
                                            >
                                                <span>최근 제개정 정보</span>
                                            </button>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* Sanction Notice Section */}
                        <div className="my-2 border-t border-white/15"></div>
                        <button
                            onClick={() => onToggleSanction()}
                            className="flex items-center justify-between w-full px-4 py-3 text-blue-50 hover:text-white hover:bg-white/10 rounded-xl transition-all"
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
                                    className={`flex items-center gap-3 w-full text-left px-4 py-2.5 rounded-xl transition-all ${currentCategory === 'sanction_notice' && selectedAgency === null ? 'text-[#003B7A] bg-white shadow-sm' : 'text-blue-100/80 hover:text-white hover:bg-white/10'}`}
                                >
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 12h16M4 18h16" /></svg>
                                    <span className="text-sm">전체</span>
                                </button>

                                {sanctionAgencyOrder.map((code) => (
                                    <button
                                        key={code}
                                        onClick={() => onSelectSanction(code)}
                                        className={`flex items-center gap-3 w-full text-left px-4 py-2.5 rounded-xl transition-all ${currentCategory === 'sanction_notice' && selectedAgency === code ? 'text-[#003B7A] bg-white shadow-sm' : 'text-blue-100/80 hover:text-white hover:bg-white/10'}`}
                                    >
                                        <AgencyIcon code={code} />
                                        <span className="text-sm">{sanctionAgencyNames[code]}</span>
                                    </button>
                                ))}
                            </div>
                        )}

                        {/* Community board */}
                        <div className="my-2 border-t border-white/15"></div>
                        <Link href="/board" onClick={onCloseMenu} aria-current={isBoardActive ? 'page' : undefined}
                            className={`flex items-center gap-3 w-full px-4 py-3 rounded-xl transition-all ${isBoardActive ? 'bg-white text-[#003B7A] shadow-sm' : 'text-blue-50 hover:text-white hover:bg-white/10'}`}>
                            <span className="font-medium">게시판</span>
                        </Link>
                    </nav>

                    {/* Footer */}
                    <div className="text-xs text-blue-100/70 mt-auto flex items-center gap-2">
                        <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2L15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2z" /></svg>
                        v3.0.0 (Beta)
                    </div>
                </div>
            </aside>
        </>
    )
}
