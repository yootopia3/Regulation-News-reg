import { beforeEach, describe, expect, it } from 'vitest'

beforeEach(() => {
  delete process.env.GITHUB_REPOSITORY
})

describe('GitHub workflow API URLs', () => {
  it('uses the original repository as a backward-compatible default', async () => {
    const { getWorkflowDispatchUrl, getWorkflowRunsUrl } = await import('@/lib/github')

    expect(getWorkflowDispatchUrl('news_collector_v2_active.yml')).toBe(
      'https://api.github.com/repos/orbzodiac84/Regulation-News-reg/actions/workflows/news_collector_v2_active.yml/dispatches',
    )
    expect(getWorkflowRunsUrl('news_collector_v2_active.yml')).toBe(
      'https://api.github.com/repos/orbzodiac84/Regulation-News-reg/actions/workflows/news_collector_v2_active.yml/runs?per_page=5',
    )
  })

  it('uses GITHUB_REPOSITORY for forked personal deployments', async () => {
    process.env.GITHUB_REPOSITORY = 'my-user/my-reg-brief'
    const { getWorkflowDispatchUrl, getWorkflowRunsUrl } = await import('@/lib/github')

    expect(getWorkflowDispatchUrl('news_collector_v2_active.yml')).toBe(
      'https://api.github.com/repos/my-user/my-reg-brief/actions/workflows/news_collector_v2_active.yml/dispatches',
    )
    expect(getWorkflowRunsUrl('news_collector_v2_active.yml', 10)).toBe(
      'https://api.github.com/repos/my-user/my-reg-brief/actions/workflows/news_collector_v2_active.yml/runs?per_page=10',
    )
  })

  it('rejects invalid repository values', async () => {
    process.env.GITHUB_REPOSITORY = 'missing-repo-name'
    const { getWorkflowDispatchUrl } = await import('@/lib/github')

    expect(() => getWorkflowDispatchUrl('news_collector_v2_active.yml')).toThrow(
      'GITHUB_REPOSITORY must be in "owner/repo" format',
    )
  })
})
