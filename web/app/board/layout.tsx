import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'
import { verifySession } from '@/lib/auth'
import BoardShell from '@/components/board/BoardShell'
export const dynamic = 'force-dynamic'
export default async function BoardLayout({ children }: { children: React.ReactNode }) {
    if (!await verifySession((await cookies()).get('mp_session')?.value)) redirect('/login')
    return <BoardShell>{children}</BoardShell>
}
