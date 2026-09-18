import { describe, expect, it } from 'vitest'
import ExcelJS from 'exceljs'
import { initialReport, publicReport, validatePublication, ORGANIZATION_INFERENCE_NOTICE } from '@/lib/publication'
import { reportWorkbook } from '@/lib/publication-export'
import type { InspectionDraft } from '@/lib/inspection-ui'
import { DocumentAction } from '@/lib/internal-documents'
const draft: InspectionDraft = {
 analysis_basis: 'organization',
 findings: [{ id:'F1',title:'공개 사고',summary:'공개된 점검 결과',evidence:[{page:1,quote:'공개 원문 내용'}]}],
 matches:[{finding_id:'F1',department:'합성검토조직관리부',related_work:'승인 절차 점검',rationale:'후보 추정',evidence:[{ref:'org:6',quote:'조직에는 합성검토조직관리부가 있다.'}],checks:[{question:'승인 내역을 확인했는가?',evidence_to_request:'승인 기록'}]}],
 unmatched_finding_ids:[]
}
describe('organization publication',()=>{
 it('preserves inference marker without exposing private evidence',()=>{
  const report=publicReport(initialReport(draft))
  expect(report.analysis_basis).toBe('organization')
  expect(JSON.stringify(report)).not.toContain('org:6')
  expect(()=>validatePublication(report,draft,[])).not.toThrow()
  expect(()=>validatePublication({items:report.items},draft,[])).toThrow('analysis_basis_mismatch')
 })
 it('rejects publication departments outside the validated candidates',()=>{
  const report=initialReport(draft)
  report.items[0].departments=['가상부서']
  expect(()=>validatePublication(report,draft,[])).toThrow('invalid_department')
 })
 it('allows the selected organization name while still blocking copied clauses',()=>{
  const nameOnly={...draft,matches:[{...draft.matches[0],evidence:[{ref:'org:6',quote:draft.matches[0].department}]}]}
  expect(()=>validatePublication(initialReport(nameOnly),nameOnly,[])).not.toThrow()
  const report=initialReport(draft)
  report.items[0].related_work=draft.matches[0].evidence[0].quote
  expect(()=>validatePublication(report,draft,[])).toThrow('private_content_detected')
 })
 it('permits multiple validated roster names without treating the roster as leaked prose',()=>{
  const names=['CreditRiskTeam','LoanReviewTeam']
  const roster={...draft,matches:names.map(department=>({...draft.matches[0],department,evidence:[{ref:'org:6',quote:department}]}))}
  expect(()=>validatePublication(initialReport(roster),roster,[names.join(', ')])).not.toThrow()
  const copy=initialReport(roster)
  copy.items[0].related_work=names.join(', ')
  expect(()=>validatePublication(copy,roster,[names.join(', ')])).toThrow('private_content_detected')
 })
 it('includes inference notice even in manually published Excel',async()=>{
  const bytes=await reportWorkbook(initialReport(draft))
  const book=new ExcelJS.Workbook()
  await book.xlsx.load(Buffer.from(bytes))
  expect(JSON.stringify(book.worksheets[0].getSheetValues())).toContain(ORGANIZATION_INFERENCE_NOTICE)
 })
 it('rejects blank roster names at the admin input boundary',()=>{
  const edit={action:'review',revision:1,units:[{article_key:'6',department:'',reviewed:true,organization_names:['\t\t']}],warnings_acknowledged:true}
  expect(DocumentAction.safeParse(edit).success).toBe(false)
 })
})
