import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'
import { ADMIN_COOKIE, verifyAdmin } from '@/lib/admin-auth'

export const dynamic = 'force-dynamic'
export default async function DocumentsLayout({ children }: { children: React.ReactNode }) {
    const token = (await cookies()).get(ADMIN_COOKIE)?.value
    let permitted = false
    try { await verifyAdmin(token); permitted = true } catch { /* Redirect without exposing provider errors. */ }
    if (!permitted) redirect('/admin/login')
    return children
}
