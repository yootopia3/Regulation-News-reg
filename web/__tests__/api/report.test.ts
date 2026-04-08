import { describe, it, expect, vi, beforeEach } from 'vitest'

const supabaseState: {
  fetchSingle: { data: any; error: any }
  updateResult: { error: any }
} = {
  fetchSingle: { data: null, error: null },
  updateResult: { error: null },
}

const generateContentMock = vi.fn()
const updateMock = vi.fn()

vi.mock('@supabase/supabase-js', () => {
  const createClient = vi.fn(() => {
    const chain: any = {}
    chain.from = vi.fn(() => chain)
    chain.select = vi.fn(() => chain)
    chain.eq = vi.fn(() => chain)
    chain.single = vi.fn(() => Promise.resolve(supabaseState.fetchSingle))
    chain.update = vi.fn((...args: any[]) => {
      updateMock(...args)
      return chain
    })
    // Make chain awaitable for the `update().eq()` path.
    chain.then = (resolve: (v: any) => any) => resolve(supabaseState.updateResult)
    return chain
  })
  return { createClient }
})

vi.mock('@google/generative-ai', () => ({
  GoogleGenerativeAI: vi.fn().mockImplementation(() => ({
    getGenerativeModel: vi.fn().mockReturnValue({
      generateContent: generateContentMock,
    }),
  })),
}))

beforeEach(() => {
  process.env.NEXT_PUBLIC_SUPABASE_URL_V2 = 'https://test.supabase.co'
  process.env.SUPABASE_SERVICE_ROLE_KEY = 'test-service-key'
  process.env.GEMINI_API_KEY = 'test-gemini-key'
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
