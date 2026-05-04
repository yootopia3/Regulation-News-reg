import { describe, it, expect, vi, beforeEach } from 'vitest'
import { pressAgencies, regulationAgencies, sanctionAgencies } from '@/components/dashboard/constants'

type QueryResult = { data: unknown[] | null; error: unknown; reject?: Error }
type QueryChain = {
  fromTable: string
  select: ReturnType<typeof vi.fn>; in: ReturnType<typeof vi.fn>; or: ReturnType<typeof vi.fn>
  eq: ReturnType<typeof vi.fn>; order: ReturnType<typeof vi.fn>; limit: ReturnType<typeof vi.fn>
}

let queryResults: QueryResult[] = []
let chains: QueryChain[] = []

function emptyResults(): QueryResult[] {
  return [{ data: [], error: null }, { data: [], error: null }, { data: [], error: null }]
}

function makeChain(fromTable: string, result: QueryResult): QueryChain {
  const chain = { fromTable } as QueryChain
  chain.select = vi.fn(() => chain)
  chain.in = vi.fn(() => chain)
  chain.or = vi.fn(() => chain)
  chain.eq = vi.fn(() => chain)
  chain.order = vi.fn(() => chain)
  chain.limit = vi.fn(() => result.reject ? Promise.reject(result.reject) : Promise.resolve(result))
  return chain
}

const createClientMock = vi.fn(() => ({
  from: vi.fn((table: string) => {
    const chain = makeChain(table, queryResults[chains.length] ?? { data: [], error: null })
    chains.push(chain)
    return chain
  }),
}))

vi.mock('@supabase/supabase-js', () => ({ createClient: createClientMock }))

beforeEach(() => {
  queryResults = emptyResults()
  chains = []
  createClientMock.mockClear()
  delete process.env.NEXT_PUBLIC_USE_V2_DB
  delete process.env.SUPABASE_SERVICE_ROLE_KEY
  process.env.NEXT_PUBLIC_SUPABASE_URL = 'https://v1.supabase.co'
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = 'v1-anon'
  process.env.NEXT_PUBLIC_SUPABASE_URL_V2 = 'https://v2.supabase.co'
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY_V2 = 'v2-anon'
})

function makeRow(overrides: Record<string, unknown> = {}) {
  return {
    id: 'a1', title: 'Title', agency: 'FSC', category: 'press_release',
    published_at: '2026-05-04T01:00:00Z', published_at_source: 'source',
    created_at: '2026-05-04T01:01:00Z', link: 'https://example.com/a1',
    view_count: 7, star_rating: 4,
    analysis_result: {
      summary: ['요약'], importance_score: 5, risk_level: 'High', keywords: ['감독'],
    },
    ...overrides,
  }
}

async function callGet() {
  const { GET } = await import('@/app/api/articles/route')
  const res = await GET()
  return { res, json: await res.json() }
}

describe('/api/articles', () => {
  it('returns only safe top-level and analysis fields', async () => {
    queryResults[0].data = [makeRow({ content: 'body', category: 1, view_count: 'bad', analysis_result: {
      summary: ['safe'], importance_score: 3, risk_level: 'Low', keywords: ['safe-keyword'],
      detailed_report: 'hidden', impact_analysis: 'hidden', action_items: ['hidden'], report_generated_at: 'hidden',
    } })]

    const { json } = await callGet()
    const article = json.articles[0]

    expect(article).toEqual({
      id: 'a1',
      title: 'Title',
      agency: 'FSC',
      published_at: '2026-05-04T01:00:00Z',
      published_at_source: 'source',
      created_at: '2026-05-04T01:01:00Z',
      link: 'https://example.com/a1',
      star_rating: 4,
      analysis_result: {
        summary: ['safe'],
        importance_score: 3,
        risk_level: 'Low',
        keywords: ['safe-keyword'],
      },
    })
    expect(article).not.toHaveProperty('content')
    for (const field of ['detailed_report', 'impact_analysis', 'action_items', 'report_generated_at']) {
      expect(article.analysis_result).not.toHaveProperty(field)
    }
  })

  it('drops rows with invalid required fields and omits invalid optional fields', async () => {
    queryResults[0].data = [makeRow({ id: 123 }), makeRow({
      id: 'valid', category: false, published_at_source: 7, created_at: {},
      view_count: 'bad', star_rating: [],
    })]

    const { json } = await callGet()

    expect(json.articles).toHaveLength(1)
    expect(json.articles[0].id).toBe('valid')
    for (const field of ['category', 'published_at_source', 'created_at', 'view_count', 'star_rating']) {
      expect(json.articles[0]).not.toHaveProperty(field)
    }
  })

  it('omits allowed analysis keys with invalid types', async () => {
    queryResults[0].data = [makeRow({
      analysis_result: { summary: 'bad', importance_score: 'bad', risk_level: 1, keywords: [1] },
    })]

    const { json } = await callGet()

    expect(json.articles[0].analysis_result).toBeNull()
  })

  it('keeps the three category query contracts', async () => {
    await callGet()
    const selectedColumns = 'id,title,agency,category,published_at,published_at_source,created_at,link,analysis_result,view_count,star_rating'

    expect(chains.map(chain => chain.fromTable)).toEqual(['articles', 'articles', 'articles'])
    expect(chains.map(chain => chain.select.mock.calls[0][0])).toEqual([selectedColumns, selectedColumns, selectedColumns])
    expect(chains[0].in).toHaveBeenCalledWith('agency', pressAgencies)
    expect(chains[0].or).toHaveBeenCalledWith('category.eq.press_release,category.is.null')
    ;[
      [chains[1], regulationAgencies, 'regulation_notice'],
      [chains[2], sanctionAgencies, 'sanction_notice'],
    ].forEach(([chain, agencies, category]) => {
      expect((chain as QueryChain).in).toHaveBeenCalledWith('agency', agencies)
      expect((chain as QueryChain).eq).toHaveBeenCalledWith('category', category)
    })
    chains.forEach(chain => {
      expect(chain.order).toHaveBeenCalledWith('published_at', { ascending: false })
      expect(chain.limit).toHaveBeenCalledWith(1000)
    })
  })

  it('merges, dedupes by id, and sorts by published_at desc', async () => {
    queryResults[0].data = [
      makeRow({ id: 'old', published_at: '2026-01-01T00:00:00Z' }),
      makeRow({ id: 'dup', title: 'first', published_at: '2026-02-01T00:00:00Z' }),
    ]
    queryResults[1].data = [makeRow({ id: 'dup', title: 'second', published_at: '2026-04-01T00:00:00Z' })]
    queryResults[2].data = [makeRow({ id: 'new', published_at: '2026-05-01T00:00:00Z' })]

    const { json } = await callGet()

    expect(json.articles.map((article: { id: string }) => article.id)).toEqual(['new', 'dup', 'old'])
    expect(json.articles.find((article: { id: string }) => article.id === 'dup').title).toBe('second')
  })

  it('returns 500 when any Supabase query fails', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    queryResults[1].error = { message: 'failed' }

    const { res, json } = await callGet()

    expect(res.status).toBe(500)
    expect(json).toEqual({ error: 'Failed to fetch articles' })
    errorSpy.mockRestore()
  })

  it('returns 500 JSON when Supabase client creation throws', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    createClientMock.mockImplementationOnce(() => {
      throw new Error('Invalid supabaseUrl')
    })

    const { res, json } = await callGet()

    expect(res.status).toBe(500)
    expect(json).toEqual({ error: 'Failed to fetch articles' })
    errorSpy.mockRestore()
  })

  it('returns 500 JSON when a Supabase query promise rejects', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    queryResults[0].reject = new Error('network failed')

    const { res, json } = await callGet()

    expect(res.status).toBe(500)
    expect(json).toEqual({ error: 'Failed to fetch articles' })
    errorSpy.mockRestore()
  })

  it('selects V1/V2 envs and prefers service role over anon fallback', async () => {
    let result = await callGet()
    expect(result.res.status).toBe(200)
    expect(createClientMock).toHaveBeenLastCalledWith('https://v1.supabase.co', 'v1-anon')

    process.env.NEXT_PUBLIC_USE_V2_DB = 'true'
    process.env.SUPABASE_SERVICE_ROLE_KEY = 'service-key'
    result = await callGet()

    expect(result.res.status).toBe(200)
    expect(createClientMock).toHaveBeenLastCalledWith('https://v2.supabase.co', 'service-key')
  })

  it('returns 500 when Supabase config is missing', async () => {
    delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

    const { res, json } = await callGet()

    expect(res.status).toBe(500)
    expect(json.error).toEqual(expect.any(String))
    expect(createClientMock).not.toHaveBeenCalled()
  })
})
