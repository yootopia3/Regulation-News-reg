import { describe, expect, it } from 'vitest'
import ExcelJS from 'exceljs'
import { publicReport, validatePublication, initialReport } from '@/lib/publication'
import { reportWorkbook } from '@/lib/publication-export'

const draft = { findings: [{ id: 'F1', title: '공개 지적', summary: '공개 요약', evidence: [{ page: 2, quote: '공개 근거' }] }], matches: [{ finding_id: 'F1', department: '검토부', rationale: '비공개 관련성', evidence: [{ ref: 'private-doc:1', quote: '기밀 업무 절차를 외부에 노출하면 안됩니다' }], checks: [{ question: '승인 이력을 확인했는가?', evidence_to_request: '승인 자료' }] }], unmatched_finding_ids: [] }
const report = { items: [{ finding_id: 'F1', title: '공개 지적', summary: '공개 요약', departments: ['검토부'], related_work: '승인 여부 점검', source_pages: [2], checks: [{ question: '승인 이력을 확인했는가?', evidence_to_request: '승인 자료' }] }] }
describe('publication boundary', () => {
    it('seeds editable public fields without copying private refs, rationale or quotes', () => {
        const json = JSON.stringify(initialReport(draft))
        expect(json).not.toMatch(/private-doc|비공개 관련성|기밀 업무 절차/)
        expect(initialReport(draft).items[0].related_work).toBe('')
    })
    it('requires exact fields and full finding coverage', () => {
        expect(() => publicReport({ ...report, internal_quote: 'PRIVATE_CANARY' })).toThrow()
        expect(() => validatePublication({ items: [] }, draft, [])).toThrow('finding_coverage_failed')
        expect(() => validatePublication({ items: [{ ...report.items[0], source_pages: [3] }] }, draft, [])).toThrow('invalid_public_evidence')
        expect(() => validatePublication(report, draft, [])).not.toThrow()
    })
    it('blocks quotes split across fields or obfuscated with punctuation/zero width characters', () => {
        const item = { ...report.items[0], summary: '기밀 업무 절차를', related_work: '외부에 노출하면 안됩니다' }
        expect(() => validatePublication({ items: [item] }, draft, [])).toThrow('private_content_detected')
        item.summary = '기밀.업무.절차를.외부에.노출하면.안됩니다\u200b'
        expect(() => validatePublication({ items: [item] }, draft, [])).toThrow('private_content_detected')
    })
    it('checks uncited document text as well as cited evidence', () => {
        const privateText = '이 문자열은 인용되지 않은 내부 업무분석서의 비공개 절차를 의미하는 합성 내용이다'
        expect(() => validatePublication({ items: [{ ...report.items[0], summary: privateText }] }, draft, [privateText])).toThrow('private_content_detected')
    })
    it('exports only visible public fields as strings, including formula-like input', async () => {
        const data = { items: [{ ...report.items[0], title: '=HYPERLINK("https://example.test")', summary: '+SUM(1,2)' }] }
        const bytes = await reportWorkbook(data, { title: '합성 은행 공시', published_at: '2026-09-09', url: 'https://www.fss.or.kr/fss/notice' })
        const book = new ExcelJS.Workbook()
        await book.xlsx.load(Buffer.from(bytes))
        expect(book.worksheets).toHaveLength(1)
        const sheet = book.worksheets[0]
        expect(sheet.state).toBe('visible')
        expect(sheet.getCell('A2').value).toBe(data.items[0].title)
        expect(sheet.getCell('A2').type).toBe(ExcelJS.ValueType.String)
        expect(sheet.getCell('B2').type).toBe(ExcelJS.ValueType.String)
        expect(sheet.columnCount).toBe(10)
        expect(sheet.getCell('H2').value).toBe('합성 은행 공시')
        expect(sheet.getCell('J2').value).toBe('https://www.fss.or.kr/fss/notice')
        expect(sheet.getCell('J2').type).toBe(ExcelJS.ValueType.String)
        expect(JSON.stringify(sheet.getSheetValues())).not.toMatch(/private-doc|기밀 업무 절차/)
    })
})
