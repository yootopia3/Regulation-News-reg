export const BOARD_CATEGORIES = { general: '업무관련', notice: '공지사항', resources: '자료실' } as const
export type BoardCategory = keyof typeof BOARD_CATEGORIES
export type BoardStatus = 'draft' | 'published'
export const MAX_ATTACHMENTS = 3
export const MAX_ATTACHMENT_BYTES = 3 * 1024 * 1024
export const BOARD_PAGE_SIZE = 20
export const BOARD_FILE_ACCEPT = '.pdf,.hwp,.hwpx,.doc,.docx,.xls,.xlsx'
export type BoardAttachment = { id: string; name: string; size: number }
export type BoardPost = {
    id: string; author_name: string; title: string; body: string; category: BoardCategory
    status: BoardStatus; is_pinned: boolean; revision: number
    created_at: string; updated_at: string; published_at: string | null; attachments: BoardAttachment[]
}
export type BoardListItem = Omit<BoardPost, 'body'>
export const BOARD_ERRORS: Record<string, string> = {
    unauthorized: '플랫폼 로그인이 필요합니다. 다시 로그인해주세요.',
    forbidden: '관리자 권한이 필요합니다.',
    invalid_password: '글 비밀번호가 올바르지 않습니다.',
    invalid_request: '입력 내용을 확인해주세요. 이름 40자, 제목 150자, 본문 20,000자 이내이며 비밀번호는 8~128자입니다.',
    invalid_credentials: '관리자 계정 정보를 확인해주세요.',
    invalid_origin: '요청을 확인할 수 없습니다. 화면을 새로고침해주세요.',
    rate_limited: '요청이 너무 많습니다. 잠시 후 다시 시도해주세요.',
    not_found: '게시글을 찾을 수 없습니다. 임시저장 글은 관리 링크에서 비밀번호로 열어주세요.',
    conflict: '다른 수정이 먼저 저장되었습니다. 작성 내용을 복사해 둔 뒤 최신 글을 다시 열어주세요.',
    too_large: '첨부파일은 최대 3개, 합계 3MB까지 등록할 수 있습니다.',
    invalid_file: 'PDF·HWP·HWPX·Word·Excel 문서만 첨부할 수 있습니다. 파일 형식과 내용을 확인해주세요.',
    disabled: '게시판을 준비 중입니다. 잠시 후 다시 확인해주세요.',
    not_configured: '게시판 연결을 준비 중입니다. 관리자에게 문의해주세요.',
    request_failed: '처리하지 못했습니다. 잠시 후 다시 시도해주세요.',
}
