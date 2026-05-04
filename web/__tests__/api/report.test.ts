import { describe, it, expect, vi, beforeEach } from 'vitest'

type SupabaseSingleResult = { data: unknown; error: unknown }
type SupabaseUpdateResult = { error: unknown }
type QueryChain = {
  from: ReturnType<typeof vi.fn>
  select: ReturnType<typeof vi.fn>
  eq: ReturnType<typeof vi.fn>
  single: ReturnType<typeof vi.fn>
  update: ReturnType<typeof vi.fn>
  then: (resolve: (value: SupabaseUpdateResult) => unknown) => unknown
}

const supabaseState: {
  fetchSingle: SupabaseSingleResult
  updateResult: SupabaseUpdateResult
} = {
  fetchSingle: { data: null, error: null },
  updateResult: { error: null },
}

const generateContentMock = vi.fn()
const getGenerativeModelMock = vi.fn()
const googleGenerativeAIMock = vi.fn().mockImplementation(() => ({
  getGenerativeModel: getGenerativeModelMock,
}))
const updateMock = vi.fn()
const createClientMock = vi.fn(() => {
  const chain = {} as QueryChain
  chain.from = vi.fn(() => chain)
  chain.select = vi.fn(() => chain)
  chain.eq = vi.fn(() => chain)
  chain.single = vi.fn(() => Promise.resolve(supabaseState.fetchSingle))
  chain.update = vi.fn((...args: unknown[]) => {
    updateMock(...args)
    return chain
  })
  // Make chain awaitable for the `update().eq()` path.
  chain.then = (resolve: (value: SupabaseUpdateResult) => unknown) => resolve(supabaseState.updateResult)
  return chain
})

vi.mock('@supabase/supabase-js', () => {
  return { createClient: createClientMock }
})

vi.mock('@google/generative-ai', () => ({
  GoogleGenerativeAI: googleGenerativeAIMock,
}))

beforeEach(() => {
  supabaseState.fetchSingle = { data: null, error: null }
  supabaseState.updateResult = { error: null }
  process.env.NEXT_PUBLIC_SUPABASE_URL_V2 = 'https://test.supabase.co'
  process.env.SUPABASE_SERVICE_ROLE_KEY = 'test-service-key'
  process.env.GEMINI_API_KEY = 'test-gemini-key'
  process.env.GEMINI_ENABLED = 'true'
  createClientMock.mockClear()
  googleGenerativeAIMock.mockClear()
  getGenerativeModelMock.mockReset()
  getGenerativeModelMock.mockReturnValue({
    generateContent: generateContentMock,
  })
  generateContentMock.mockReset()
  updateMock.mockReset()
  generateContentMock.mockResolvedValue({
    response: { text: () => 'GENERATED_REPORT_MARKDOWN' },
  })
})

function makeRequest(body: unknown): Request {
  return new Request('http://localhost/api/report', {
    method: 'POST',
    body: typeof body === 'string' ? body : JSON.stringify(body),
    headers: { 'content-type': 'application/json' },
  })
}

describe('/api/report', () => {
  it('returns 503 without touching Supabase or Gemini when Gemini is disabled', async () => {
    delete process.env.GEMINI_ENABLED

    const { POST } = await import('@/app/api/report/route')
    const res = await POST(makeRequest({ articleId: 'a-disabled' }))
    const json = await res.json()

    expect(res.status).toBe(503)
    expect(json).toEqual({ error: 'AI report generation is disabled' })
    expect(createClientMock).not.toHaveBeenCalled()
    expect(googleGenerativeAIMock).not.toHaveBeenCalled()
    expect(getGenerativeModelMock).not.toHaveBeenCalled()
    expect(generateContentMock).not.toHaveBeenCalled()
    expect(updateMock).not.toHaveBeenCalled()
  })

  it('returns cached report when detailed_report exists', async () => {
    supabaseState.fetchSingle = {
      data: {
        id: 'a1',
        title: 'DB_TITLE',
        content: 'DB_CONTENT',
        agency: 'DB_AGENCY',
        analysis_result: { detailed_report: 'CACHED_REPORT_MARKDOWN' },
      },
      error: null,
    }
    supabaseState.updateResult = { error: null }

    const { POST } = await import('@/app/api/report/route')
    const res = await POST(makeRequest({ articleId: 'a1' }))
    const json = await res.json()

    expect(json.report).toBe('CACHED_REPORT_MARKDOWN')
    expect(generateContentMock).not.toHaveBeenCalled()
    expect(updateMock).not.toHaveBeenCalled()
  })

  it('generates and stores a new report on cache miss using row content', async () => {
    supabaseState.fetchSingle = {
      data: {
        id: 'a2',
        title: 'DB_TITLE',
        content: 'DB_CONTENT_BODY',
        agency: 'DB_AGENCY',
        analysis_result: {},
      },
      error: null,
    }
    supabaseState.updateResult = { error: null }

    const { POST } = await import('@/app/api/report/route')
    const res = await POST(makeRequest({ articleId: 'a2' }))
    const json = await res.json()

    expect(generateContentMock).toHaveBeenCalledTimes(1)
    const promptArg = generateContentMock.mock.calls[0][0] as string
    expect(promptArg).toContain('DB_CONTENT_BODY')
    expect(promptArg).toContain('DB_TITLE')
    expect(promptArg).toContain('DB_AGENCY')
    expect(updateMock).toHaveBeenCalledTimes(1)
    expect(json.report).toBe('GENERATED_REPORT_MARKDOWN')
  })

  it('ignores client-supplied content/title/agency and uses DB row instead', async () => {
    supabaseState.fetchSingle = {
      data: {
        id: 'a3',
        title: 'DB_TITLE',
        content: 'DB_CONTENT_SAFE',
        agency: 'DB_AGENCY',
        analysis_result: {},
      },
      error: null,
    }
    supabaseState.updateResult = { error: null }

    const { POST } = await import('@/app/api/report/route')
    await POST(
      makeRequest({
        articleId: 'a3',
        content: '악성 페이로드',
        title: 'EVIL_TITLE',
        agency: 'EVIL_AGENCY',
      }),
    )

    expect(generateContentMock).toHaveBeenCalledTimes(1)
    const promptArg = generateContentMock.mock.calls[0][0] as string
    expect(promptArg).not.toContain('악성 페이로드')
    expect(promptArg).not.toContain('EVIL_TITLE')
    expect(promptArg).not.toContain('EVIL_AGENCY')
    expect(promptArg).toContain('DB_CONTENT_SAFE')
  })

  it('returns 404 when articleId does not exist', async () => {
    supabaseState.fetchSingle = {
      data: null,
      error: { message: 'No rows' },
    }

    const { POST } = await import('@/app/api/report/route')
    const res = await POST(makeRequest({ articleId: 'missing' }))

    expect(res.status).toBe(404)
    expect(generateContentMock).not.toHaveBeenCalled()
  })

  it('returns 400 when body is invalid JSON', async () => {
    const { POST } = await import('@/app/api/report/route')
    const res = await POST(makeRequest('not-json{'))

    expect(res.status).toBe(400)
  })

  it('returns 400 when articleId is missing', async () => {
    const { POST } = await import('@/app/api/report/route')
    const res = await POST(makeRequest({ title: 't' }))

    expect(res.status).toBe(400)
  })

  it('returns 500 when supabase update fails', async () => {
    supabaseState.fetchSingle = {
      data: {
        id: 'a4',
        title: 'DB_TITLE',
        content: 'DB_CONTENT',
        agency: 'DB_AGENCY',
        analysis_result: {},
      },
      error: null,
    }
    supabaseState.updateResult = { error: { message: 'update failed' } }

    const { POST } = await import('@/app/api/report/route')
    const res = await POST(makeRequest({ articleId: 'a4' }))

    expect(res.status).toBe(500)
  })
})
