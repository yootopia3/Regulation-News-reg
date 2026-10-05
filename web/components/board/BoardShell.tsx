import Image from 'next/image'
import Link from 'next/link'
export default function BoardShell({ children }: { children: React.ReactNode }) {
    return <div className="min-h-screen bg-slate-50 text-slate-900">
        <header className="border-b border-slate-200 bg-white">
            <div className="mx-auto max-w-5xl flex flex-wrap items-center justify-between gap-4 px-5 py-5">
                <Link href="/" className="flex items-center gap-3 font-bold"><Image src="/ibk-icon.svg" width={36} height={36} alt="IBK기업은행" />규제정보 플랫폼</Link>
                <Link href="/" className="text-sm text-blue-800 hover:underline">대시보드로 돌아가기</Link>
            </div>
        </header>
        <main className="mx-auto max-w-5xl px-5 py-8 sm:py-10">
            <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
                <div><Link href="/board" className="text-3xl font-bold tracking-tight">게시판</Link><p className="mt-2 text-sm text-slate-600">업무 안내와 규제 관련 자료를 함께 나누는 공간입니다.</p></div>
                <a href="/api/daily-report" className="text-sm font-medium text-blue-800 underline underline-offset-4">아침에 읽는 규제변화 ↗</a>
            </div>
            {children}
        </main>
    </div>
}
