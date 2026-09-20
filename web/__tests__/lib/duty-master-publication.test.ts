import { describe, expect, it } from 'vitest'
import ExcelJS from 'exceljs'
import { initialReport, publicReport, validatePublication, reportBasisNotice, DUTY_MASTER_NOTICE } from '@/lib/publication'
import { reportWorkbook } from '@/lib/publication-export'
import type { InspectionDraft } from '@/lib/inspection-ui'

const draft: InspectionDraft = {
    analysis_basis: 'duty_master', master_version: 'fixture-v1', master_fingerprint: 'a'.repeat(64),
    findings: [{ id: 'F1', title: '공개 지적', summary: '확인절차 누락', evidence: [{ page: 1, quote: '공개 원문 근거' }] }],
    matches: [{ finding_id: 'F1', department: '합성통제부', rationale: '검토 후보', related_work: '경보 후속관리',
        duty_ids: ['HQ-001'], duty_basis: 'inferred', evidence: [{ ref: 'HQ-001', quote: '합성 내부원장에만 있는 설명으로 검토기록을 구성한다' }],
        checks: [{ question: '접수된 경보의 처리를 끝까지 추적하는가?', evidence_to_request: '처리 이력' }] }], unmatched_finding_ids: [],
}

describe('duty master publication contract', () => {
    it('carries the version, duty basis and per-check department through the public projection', () => {
        const report = publicReport(initialReport(draft))
        expect(report.master_version).toBe('fixture-v1')
        expect(report.items[0].department_basis).toEqual([{ department: '합성통제부', duty_ids: ['HQ-001'], basis: 'inferred' }])
        expect(report.items[0].checks[0].department).toBe('합성통제부')
        expect(() => validatePublication(report, draft, [])).not.toThrow()
        expect(JSON.stringify(report)).not.toContain(draft.matches[0].evidence[0].quote)
        expect(reportBasisNotice(report)).toBe(DUTY_MASTER_NOTICE)
    })
    it('rejects missing basis, upgraded certainty, invented duties and different master versions', () => {
        const report = publicReport(initialReport(draft))
        expect(() => publicReport({ ...report, master_version: undefined })).toThrow()
        expect(() => publicReport({ ...report, items: [{ ...report.items[0], department_basis: undefined }] })).toThrow()
        for (const patch of [{ basis: 'explicit' as const }, { duty_ids: ['HQ-999'] }, { department: '가상영업점' }]) {
            const edited = structuredClone(report)
            Object.assign(edited.items[0].department_basis![0], patch)
            expect(() => validatePublication(edited, draft, [])).toThrow()
        }
        expect(() => validatePublication({ ...report, master_fingerprint: 'b'.repeat(64) }, draft, [])).toThrow('master_version_mismatch')
    })
    it('binds every question to a retained, matched headquarters department', () => {
        const report = publicReport(initialReport(draft))
        report.items[0].checks[0].department = '가상영업점'
        expect(() => validatePublication(report, draft, [])).toThrow('invalid_department')
        const missing = initialReport(draft)
        missing.items[0].departments = []
        expect(() => validatePublication(missing, draft, [])).toThrow('master_basis_mismatch')
    })
    it('exports the same duty basis and per-question owner without internal text', async () => {
        const data = await reportWorkbook(initialReport(draft))
        const book = new ExcelJS.Workbook(); await book.xlsx.load(data as unknown as Parameters<typeof book.xlsx.load>[0])
        const sheet = book.worksheets[0]
        expect(sheet.getCell('H2').value).toBe('합성통제부')
        expect(sheet.getCell('I2').value).toBe('업무 귀속 추정')
        expect(sheet.getCell('J2').value).toBe('HQ-001')
        expect(JSON.stringify(sheet.getSheetValues())).toContain(DUTY_MASTER_NOTICE)
        expect(JSON.stringify(sheet.getSheetValues())).not.toContain(draft.matches[0].evidence[0].quote)
    })
})
