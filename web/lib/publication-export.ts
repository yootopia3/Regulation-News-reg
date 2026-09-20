import ExcelJS from 'exceljs'
import { publicReport, reportBasisNotice, DUTY_BASIS_LABELS, type PublicationSource } from './publication'

export async function reportWorkbook(value: unknown, source?: PublicationSource, automatic = false) {
    const report = publicReport(value)
    const book = new ExcelJS.Workbook()
    const sheet = book.addWorksheet('사고예방 점검표')
    sheet.columns = [
        { header: '지적사항', key: 'title', width: 28 }, { header: '요약', key: 'summary', width: 50 },
        { header: '소관부서', key: 'departments', width: 25 }, { header: '관련 업무', key: 'work', width: 40 },
        { header: '점검 질문', key: 'question', width: 55 }, { header: '요청 증빙', key: 'evidence', width: 40 },
        { header: '공개 PDF 쪽', key: 'pages', width: 16 },
        ...(source ? [{ header: '공시 제목', key: 'source_title', width: 40 }, { header: '공시일', key: 'source_date', width: 24 }, { header: '금감원 원문', key: 'source_url', width: 60 }] : []),
        ...(report.analysis_basis === 'duty_master' ? [{ header: '점검 담당 후보', key: 'check_department', width: 25 }, { header: '업무 근거 수준', key: 'duty_basis', width: 30 }, { header: '원장 업무ID', key: 'duty_ids', width: 25 }] : []),
    ]
    for (const item of report.items) for (const check of item.checks) {
        // Strings only: ExcelJS formula/hyperlink objects are never accepted.
        sheet.addRow([item.title, item.summary, item.departments.join(', ') || '검토 필요', item.related_work,
            check.question, check.evidence_to_request, item.source_pages.join(', '), ...(source ? [source.title, source.published_at, source.url || '원문 링크 확인 필요'] : []),
            ...(report.analysis_basis === 'duty_master' ? [check.department || '',
                item.department_basis?.filter(b => b.department === check.department).map(b => DUTY_BASIS_LABELS[b.basis]).join(', ') || '',
                item.department_basis?.filter(b => b.department === check.department).flatMap(b => b.duty_ids).join(', ') || ''] : [])])
    }
    sheet.getRow(1).font = { bold: true, color: { argb: 'FFFFFFFF' } }
    sheet.getRow(1).fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF17365D' } }
    sheet.eachRow(row => { row.alignment = { wrapText: true, vertical: 'top' }; row.height = 48 })
    sheet.views = [{ state: 'frozen', ySplit: 1 }]
    sheet.autoFilter = { from: 'A1', to: report.analysis_basis === 'duty_master' ? (source ? 'M1' : 'J1') : (source ? 'J1' : 'G1') }
    if (reportBasisNotice(report)) sheet.addRow([reportBasisNotice(report)])
    if (report.master_version) sheet.addRow(['업무원장 기준: ' + report.master_version])
    if (automatic) sheet.addRow(['AI 자동 분석 · 담당자 확인 필요'])
    return new Uint8Array(await book.xlsx.writeBuffer())
}
