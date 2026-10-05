'use client'
import { useEffect, useRef, type ReactNode } from 'react'
import Sidebar, { type SidebarProps } from './Sidebar'

/** Shared desktop sidebar, mobile drawer and content viewport. */
export default function DashboardFrame({ sidebar, header, children, overlay, contentKey }: {
    sidebar: SidebarProps; header: ReactNode; children: ReactNode; overlay?: ReactNode; contentKey?: string | null
}) {
    const viewport = useRef<HTMLDivElement>(null)
    useEffect(() => { if (viewport.current) viewport.current.scrollTop = 0 }, [contentKey])
    return <div className="h-screen overflow-hidden bg-[#F5F7FA] text-gray-900 font-sans selection:bg-blue-500/40 lg:flex">
        <Sidebar {...sidebar} />
        <div ref={viewport} className={`flex-1 flex h-screen min-w-0 flex-col overflow-y-auto transition-all duration-300 ${sidebar.isMenuOpen ? 'md:pl-[260px] lg:pl-0' : ''}`}>
            {header}
            <main className="flex-1 p-4 md:p-8 max-w-5xl mx-auto w-full">{children}</main>
        </div>
        {overlay}
    </div>
}
