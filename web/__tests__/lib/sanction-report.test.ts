import { describe, expect, it } from 'vitest'
import { filterSanctionSources, publicSanctionUrl, sanctionDate, sanctionSources } from '@/lib/sanction-report'

const article = { id: 'one', title: '토스뱅크 제재', agency: 'FSS_SANCTION', category: 'sanction_notice', published_at: '2026-09-09T16:00:00Z', link: 'https://www.fss.or.kr/fss/notice', analysis_result: { summary: ['공개 요약'], internal_text: 'PRIVATE_CANARY' }, internal_document: 'PRIVATE_CANARY' }

describe('sanction report sources', () => {
    it('keeps only sanction categories and agencies and projects explicit public fields', () => {
        const rows = sanctionSources({ articles: [article, { ...article, id: 'two', agency: 'FSS' }, { ...article, id: 'three', category: 'press_release' }, { ...article, id: 'four', published_at: 'invalid' }] })
        expect(rows).toHaveLength(1)
        expect(rows[0].summary).toEqual(['공개 요약'])
        expect(JSON.stringify(rows)).not.toContain('PRIVATE_CANARY')
        expect(filterSanctionSources(rows, ' 토스 ', '')).toHaveLength(1)
        expect(filterSanctionSources(rows, '', 'FSS_MGMT_NOTICE')).toHaveLength(0)
        expect(filterSanctionSources(rows, '없는은행', '')).toHaveLength(0)
    })
    it('deduplicates and sorts by latest timestamp, displaying KST', () => {
        const rows = sanctionSources({ articles: [{ ...article, id: 'old', published_at: '2026-09-01' }, article, article] })
        expect(rows.map(row => row.id)).toEqual(['one', 'old'])
        expect(sanctionDate(article.published_at)).toContain('09. 10.')
    })
    it('rejects malformed envelopes instead of showing an empty success', () => {
        expect(() => sanctionSources({ error: 'failed' })).toThrow()
    })
    it.each(['javascript:alert(1)', 'https://www.fss.or.kr.evil.example/a', 'https://user@www.fss.or.kr/a', 'https://localhost/a', 'https://www.fss.or.kr:444/a', '/admin/documents'])('rejects unsafe original URL %s', url => {
        expect(publicSanctionUrl(url)).toBeNull()
    })
})
