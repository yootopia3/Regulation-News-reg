import { NextResponse } from 'next/server'

const WORKFLOW_FILE = 'news_collector_v2_active.yml'

type WorkflowRun = {
    status: string
    conclusion: string | null
    html_url: string
}

export async function GET() {
    try {
        const githubToken = process.env.GITHUB_TOKEN

        if (!githubToken) {
            return NextResponse.json({ error: 'GitHub token not configured' }, { status: 500 })
        }

        // Get recent runs (check for in_progress first)
        const response = await fetch(
            `https://api.github.com/repos/orbzodiac84/Regulation-News-reg/actions/workflows/${WORKFLOW_FILE}/runs?per_page=5`,
            {
                headers: {
                    'Accept': 'application/vnd.github.v3+json',
                    'Authorization': `Bearer ${githubToken}`,
                },
                cache: 'no-store'
            }
        )

        const data = await response.json()
        const workflowRuns: WorkflowRun[] = Array.isArray(data.workflow_runs) ? data.workflow_runs : []

        if (workflowRuns.length > 0) {
            // First, check if any run is in_progress or queued
            const inProgressRun = workflowRuns.find(
                (run) => run.status === 'in_progress' || run.status === 'queued'
            )

            if (inProgressRun) {
                return NextResponse.json({
                    status: inProgressRun.status, // in_progress or queued
                    conclusion: null,
                    url: inProgressRun.html_url
                })
            }

            // No in-progress runs, return the latest completed
            const latestRun = workflowRuns[0]
            return NextResponse.json({
                status: latestRun.status,
                conclusion: latestRun.conclusion,
                url: latestRun.html_url
            })
        }

        return NextResponse.json({ status: 'unknown' })
    } catch (error) {
        console.error('Check status error:', error)
        return NextResponse.json({ error: 'Failed to check status' }, { status: 500 })
    }
}
