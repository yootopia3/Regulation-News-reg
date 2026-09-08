const DEFAULT_GITHUB_REPOSITORY = 'orbzodiac84/Regulation-News-reg'

function getRepositoryParts(): { owner: string; repo: string } {
  const repository = (process.env.GITHUB_REPOSITORY || DEFAULT_GITHUB_REPOSITORY).trim()
  const parts = repository.split('/')

  if (parts.length !== 2 || !parts[0] || !parts[1]) {
    throw new Error('GITHUB_REPOSITORY must be in "owner/repo" format')
  }

  return {
    owner: encodeURIComponent(parts[0]),
    repo: encodeURIComponent(parts[1]),
  }
}

export function getWorkflowDispatchUrl(workflowFile: string): string {
  const { owner, repo } = getRepositoryParts()
  return `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${encodeURIComponent(workflowFile)}/dispatches`
}

export function getWorkflowRunsUrl(workflowFile: string, perPage = 5): string {
  const { owner, repo } = getRepositoryParts()
  return `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${encodeURIComponent(workflowFile)}/runs?per_page=${perPage}`
}
