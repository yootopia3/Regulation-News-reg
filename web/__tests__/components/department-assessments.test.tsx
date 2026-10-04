import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, it, expect } from 'vitest'
import DepartmentAssessments from '@/components/DepartmentAssessments'
import { initialReport, publicReport } from '@/lib/publication'
import type { InspectionDraft } from '@/lib/inspection-ui'

afterEach(cleanup)

const records: NonNullable<InspectionDraft['department_assessments']> = [
    { finding_id:'F1', department:'합성지원부', duty_ids:['HQ-002'], decision:'excluded',
      applicability:'관리자 전용 적용대상', role:'지원 역할', reason:'관리자 전용 제외 이유',
      public_evidence:[{page:2,quote:'공개 공시 근거 문장'}] },
    { finding_id:'F1', department:'합성통제부', duty_ids:['HQ-001'], decision:'included',
      applicability:'고객 확인', role:'기준 관리', reason:'관련 통제 검토',public_evidence:[] },
    { finding_id:'F1', department:'합성기획부', duty_ids:['HQ-003'], decision:'uncertain',
      applicability:'확인 필요', role:'정책', reason:'자료 부족',public_evidence:[] },
]

describe('private department assessments', () => {
    it('shows inclusion/exclusion/uncertainty and source in admin detail', () => {
        render(<DepartmentAssessments assessments={records} />)
        expect(screen.getByText('검토 업무: HQ-002 · 제외')).toBeInTheDocument()
        expect(screen.getByText('검토 업무: HQ-001 · 포함')).toBeInTheDocument()
        expect(screen.getByText('검토 업무: HQ-003 · 판단 유보')).toBeInTheDocument()
        expect(screen.getByText('공시 2쪽: 공개 공시 근거 문장')).toBeInTheDocument()
    })
    it('keeps legacy drafts renderable', () => {
        const { container }=render(<DepartmentAssessments assessments={undefined} />)
        expect(container).toBeEmptyDOMElement()
    })
    it('groups different duty decisions under one department', () => {
        render(<DepartmentAssessments assessments={[records[1], {...records[2],department:'합성통제부'}]} />)
        expect(screen.getAllByRole('heading',{name:'합성통제부'})).toHaveLength(1)
        expect(screen.getByText('검토 업무: HQ-001 · 포함')).toBeInTheDocument()
        expect(screen.getByText('검토 업무: HQ-003 · 판단 유보')).toBeInTheDocument()
    })
    it('does not copy private assessment fields into publication', () => {
        const draft: InspectionDraft = { analysis_basis:'duty_master',master_version:'test',master_fingerprint:'a'.repeat(64),
            findings:[{id:'F1',title:'공개 제목',summary:'공개 요약',evidence:[{page:1,quote:'공개 근거 문장'}]}],
            matches:[{finding_id:'F1',department:'합성통제부',rationale:'비공개 판단',related_work:'예방 점검',
                duty_ids:['HQ-001'],duty_basis:'inferred',evidence:[],checks:[{question:'확인하는가?',evidence_to_request:'처리 기록'}]}],
            unmatched_finding_ids:[],department_assessments:records }
        const text=JSON.stringify(publicReport(initialReport(draft)))
        expect(text).not.toContain('department_assessments')
        expect(text).not.toContain('관리자 전용')
        expect(text).not.toContain('합성지원부')
    })
})
