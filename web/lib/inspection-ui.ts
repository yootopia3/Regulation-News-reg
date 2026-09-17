export const INSPECTION_STATUS: Record<string, string> = {
    queued: '분석 대기', processing: '분석 중', needs_review: '초안 검토 필요', failed: '분석 실패', stale: '규정 변경 · 재분석 필요',
}
export const INSPECTION_ERRORS: Record<string, string> = {
    pdf_missing: '등록된 PDF 주소가 없습니다.', unsafe_pdf_url: '허용된 금감원 HTTPS 주소가 아닙니다.',
    ocr_required: '이미지가 포함되거나 텍스트가 부족한 페이지가 있어 OCR 또는 원문 확인이 필요합니다.',
    encrypted_pdf: '암호화된 PDF입니다.', pdf_limit: 'PDF 처리 범위를 초과했습니다.',
    reference_review_required: '법령 또는 조문 참조를 확인해야 합니다.', context_review_required: '관련 조문 범위를 검토해야 합니다.',
    documents_changed: '업무규정이 변경되었습니다. 다시 분석해 주세요.', lease_expired: '작업 시간이 초과되었습니다. 재실행 전에 worker 상태를 확인해 주세요.',
    rate_limited: 'AI 요청 한도를 초과했습니다. 잠시 후 다시 실행해 주세요.',
}
export type InspectionJob = { automation_status?: string; id: string; article_id: string; status: string; error_code: string | null; result?: InspectionDraft | null; review_revision?: number; review_draft?: import('./publication').PublicationReport | null }
export type InspectionDraft = {
    findings: { id: string; title: string; summary: string; evidence: { page: number; quote: string }[] }[]
    matches: { finding_id: string; department: string; rationale: string; related_work?: string; evidence: { ref: string; quote: string }[]; checks: { question: string; evidence_to_request: string }[] }[]
    unmatched_finding_ids: string[]
}
