'use client'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useState } from 'react'
import DashboardFrame from '@/components/dashboard/DashboardFrame'
import Header from '@/components/dashboard/Header'
import { dashboardHref } from '@/components/dashboard/navigation'
import type { DashboardCategory } from '@/components/dashboard/constants'

export default function BoardShell({ children }: { children: React.ReactNode }) {
    const [isMenuOpen, setMenuOpen] = useState(false)
    const router = useRouter()
    const pathname = usePathname()
    const pageTitle = pathname === '/board/new' ? '글쓰기' : pathname?.endsWith('/edit') ? '글 수정·삭제' : pathname === '/board' ? null : '글 상세'
    function selectCategory(category: DashboardCategory, agency: string | null = null) {
        setMenuOpen(false)
        router.push(dashboardHref(category, agency))
    }
    return <DashboardFrame
        contentKey={pathname}
        sidebar={{
            isMenuOpen, onCloseMenu: () => setMenuOpen(false), currentCategory: null, selectedAgency: null, isBoardActive: true,
            onSelectHome: () => { setMenuOpen(false); router.push('/') },
            onSelectPress: agency => selectCategory('press_release', agency),
            onSelectReg: agency => selectCategory('regulation_notice', agency),
            onSelectSanction: agency => selectCategory('sanction_notice', agency),
            isAgencyExpanded: false, isRegExpanded: false, isFSSRegGroupExpanded: false, isSanctionExpanded: false,
            onToggleAgency: () => selectCategory('press_release'), onToggleReg: () => selectCategory('regulation_notice'),
            onToggleFSSRegGroup: () => selectCategory('regulation_notice', 'FSS_REG'), onToggleSanction: () => selectCategory('sanction_notice'),
            hasNewPress: false, hasNewReg: false, hasNewSanction: false,
        }}
        header={<Header onMenuClick={() => setMenuOpen(open => !open)} isMenuOpen={isMenuOpen}>
            <nav aria-label="현재 위치" className="flex items-center gap-2 text-sm text-slate-500">
                <Link href="/board" className="font-semibold text-blue-900">게시판</Link>
                {pageTitle && <><span aria-hidden="true">/</span><span>{pageTitle}</span></>}
            </nav>
        </Header>}
    >
        <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
            <div><h1 className="text-2xl font-bold tracking-tight text-slate-900">게시판</h1><p className="mt-2 text-sm text-slate-500">업무 안내와 규제 관련 자료를 함께 나누는 공간입니다.</p></div>
            <a href="/api/daily-report" className="text-xs font-medium text-blue-800 underline underline-offset-4">아침에 읽는 규제변화 ↗</a>
        </div>
        {children}
    </DashboardFrame>
}
