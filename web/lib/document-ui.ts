export const DOCUMENT_STATUS: Record<string, string> = {
    uploading: '업로드 확인 필요', queued: '추출 대기', processing: '추출 중', review: '검토 대기',
    active: '활성', retired: '이전 버전', failed: '추출 실패', deleting: '삭제 처리 중', delete_failed: '삭제 실패 · 다시 요청 가능', deleted: '삭제 완료',
}
export const DOCUMENT_ERRORS: Record<string, string> = {
    review_conflict: '다른 수정 또는 규정 변경이 있습니다. 새로고침 후 다시 검토해 주세요.',
    publication_review_required: '지적사항·공개 페이지 또는 내부 내용 포함 여부를 다시 확인해 주세요.',
    invalid_request: '필수 항목과 입력 길이를 확인해 주세요.',
    no_active_documents: '검토를 마친 업무규정을 먼저 활성화해 주세요.', invalid_article: '분석할 수 있는 제재공시가 아닙니다.',
    disabled: '문서 관리가 비활성화되어 있습니다.', not_configured: '관리자 문서 관리 설정이 필요합니다.',
    unauthorized: '로그인이 만료되었습니다. 다시 로그인해주세요.', forbidden: '관리자 권한이 필요합니다.',
    duplicate_document: '동일한 파일이 이미 등록되어 있습니다.', too_large: '파일은 2MB 이하로 등록해주세요.',
    invalid_hwp: 'HWP 형식을 확인해주세요.', state_conflict: '문서가 변경되었거나 검토가 완료되지 않았습니다. 새로고침 후 확인해주세요.',
    invalid_upload: 'HWP 파일과 문서 정보를 확인해주세요.', invalid_input: '입력 내용을 확인해주세요.',
    rate_limited: '요청이 많습니다. 잠시 후 다시 시도해주세요.',
}
export async function documentRequest(path: string, init?: RequestInit) {
    const response = await fetch(path, { ...init, cache: 'no-store' })
    const data = await response.json()
    if (!response.ok) throw new Error(DOCUMENT_ERRORS[data.error] || '처리하지 못했습니다. 상태를 새로고침한 후 다시 시도해주세요.')
    return data
}
