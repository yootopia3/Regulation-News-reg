import { DUTY_BASIS_LABELS, type PublicationReport } from '@/lib/publication'

export default function DutyBasis({ item }: { item: PublicationReport['items'][number] }) {
    if (!item.department_basis) return null
    return <ul aria-label="부서별 업무 근거" className="mt-3 flex flex-wrap gap-2">
        {item.department_basis.map(b => <li key={b.department} className="rounded-lg bg-slate-100 px-3 py-2 text-xs text-slate-700">
            <strong>{b.department}</strong> · {DUTY_BASIS_LABELS[b.basis]}
        </li>)}
    </ul>
}
