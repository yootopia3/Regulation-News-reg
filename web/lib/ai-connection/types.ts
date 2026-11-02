export const AI_PROTOCOLS = { responses: 'OpenAI Responses', chat_completions: 'OpenAI 호환 (Chat Completions)' } as const
export type AIProtocol = keyof typeof AI_PROTOCOLS
export type ConnectionForm = { base_url: string; protocol: AIProtocol; model: string; api_key: string; revision: number }
export type ConnectionView = Omit<ConnectionForm, 'api_key'> & { configured: boolean; available: boolean; key_last4: string; updated_at: string | null }
export const CONNECTION_ERRORS: Record<string, string> = {
    connection_not_configured: 'AI 연결 설정의 최초 서버 설정이 필요합니다.',
    connection_conflict: '다른 관리자가 설정을 변경했습니다. 새로고침 후 다시 확인해 주세요.',
    connection_key_required: '처음 등록하거나 연결 주소를 바꿀 때는 해당 서버의 API 키를 입력해 주세요.',
    connection_test_required: '입력값을 변경했다면 연결 시험을 다시 진행해 주세요. 시험 결과는 10분간 유효합니다.',
    unsafe_ai_url: '연결 주소를 확인해 주세요. 기본은 공개 HTTPS 주소이며 사내 주소는 서버에서 별도 허용이 필요합니다.',
    provider_auth_failed: 'API 키 또는 해당 모델의 사용 권한을 확인해 주세요.',
    provider_failed: '서버에 연결하지 못했습니다. 주소·모델·API 호환 방식을 확인해 주세요.',
    invalid_response: '서버가 필요한 JSON 응답을 반환하지 않았습니다. 호환 방식과 모델을 확인해 주세요.',
    response_limit: '서버 응답이 허용 크기를 초과했습니다.',
    rate_limited: 'API 요청 한도에 도달했습니다. 잠시 후 다시 시도해 주세요.',
    invalid_request: '연결 주소, 모델 이름, API 키의 입력값을 확인해 주세요.',
    unauthorized: '관리자 로그인이 만료되었습니다. 다시 로그인해 주세요.',
    forbidden: '관리자 권한이 필요합니다.',
}
export async function connectionRequest(path: string, input?: object) {
    const response = await fetch(`/api/admin/ai-connection${path}`, { cache: 'no-store', ...(input ? {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(input),
    } : {}) })
    const data = await response.json()
    if (!response.ok) throw new Error(CONNECTION_ERRORS[data.error] || '처리하지 못했습니다. 설정을 새로고침한 뒤 다시 시도해 주세요.')
    return data
}
