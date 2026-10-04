import { DEPARTMENT_DECISIONS, groupDepartmentAssessments, type InspectionDraft } from '@/lib/inspection-ui'

// Private admin detail only; never include this in publication projections.
export default function DepartmentAssessments({ assessments }: { assessments: InspectionDraft['department_assessments'] }) {
    if (!assessments?.length) return null
    return <details className="mt-4 border rounded p-4 text-sm">
        <summary className="font-semibold">부서 포함·제외 검토 · 관리자 전용</summary>
        <p className="mt-3 text-slate-600">AI가 검토한 후보의 판단 기록입니다. 원장상 업무 근거, 공시와의 관련성 추정, 당행의 실제 위반 여부를 구분해 확인하세요.</p>
        {groupDepartmentAssessments(assessments).map(group => <section key={`${group.finding_id}-${group.department}`} className="mt-4 border-t pt-3">
            <h4 className="font-semibold">{group.department}</h4>
            {group.items.map(a => <div key={a.duty_ids.join(',')} className="mt-3">
            <p className="mt-1 text-slate-600">검토 업무: {a.duty_ids.join(', ')} · {DEPARTMENT_DECISIONS[a.decision]}</p>
            <p className="mt-2">적용대상: {a.applicability}</p>
            <p className="mt-2">역할과 경계: {a.role}</p>
            <p className="mt-2">판단 이유: {a.reason}</p>
            {a.public_evidence.map((e, i) => <p key={i} className="mt-2 text-slate-500">공시 {e.page}쪽: {e.quote}</p>)}
            </div>)}
        </section>)}
    </details>
}
