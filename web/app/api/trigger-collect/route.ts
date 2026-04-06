import { NextResponse } from 'next/server'

const WORKFLOW_FILE = 'news_collector_v2_active.yml'

export async function POST() {
    try {
        // Get GitHub token from environment
        const githubToken = process.env.GITHUB_TOKEN

        if (!githubToken) {
            return NextResponse.json(
                { error: 'GitHub token not configured' },
                { status: 500 }
            )
        }

        // Trigger GitHub Actions workflow
        const response = await fetch(
            `https://api.github.com/repos/orbzodiac84/Regulation-News-reg/actions/workflows/${WORKFLOW_FILE}/dispatches`,
            {
                method: 'POST',
                headers: {
                    'Accept': 'application/vnd.github.v3+json',
                    'Authorization': `Bearer ${githubToken}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    ref: 'main'
                })
            }
        )

        if (response.status === 204) {
            // Success - GitHub returns 204 No Content for successful dispatch
            return NextResponse.json({
                success: true,
                message: 'Data collection triggered successfully! It may take a few minutes to complete.'
            })
        }

        const errorData = await response.text()
        console.error('GitHub API error:', response.status, errorData)

        return NextResponse.json(
            { error: `GitHub API error: ${response.status}` },
            { status: response.status }
        )
    } catch (error) {
        console.error('Trigger collect error:', error)
        return NextResponse.json(
            { error: 'Failed to trigger data collection' },
            { status: 500 }
        )
    }
}
