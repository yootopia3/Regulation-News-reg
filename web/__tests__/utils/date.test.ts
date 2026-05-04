import { describe, it, expect } from 'vitest'
import { formatKSTTime, getArticleDisplayTime } from '@/utils/date'

describe('formatKSTTime', () => {
    it('formats a UTC ISO string as KST HH:mm', () => {
        expect(formatKSTTime('2026-05-04T00:05:00.000Z')).toBe('09:05')
    })

    it('returns an empty string for invalid or missing dates', () => {
        expect(formatKSTTime('not-a-date')).toBe('')
        expect(formatKSTTime(null)).toBe('')
        expect(formatKSTTime()).toBe('')
    })
})

describe('getArticleDisplayTime', () => {
    it('uses published_at for source rows', () => {
        expect(getArticleDisplayTime({
            published_at: '2026-05-04T01:30:00.000Z',
            created_at: '2026-05-04T03:00:00.000Z',
            published_at_source: 'source',
        })).toEqual({
            timeText: '10:30',
            source: 'published',
        })
    })

    it('uses created_at for collected fallback rows', () => {
        expect(getArticleDisplayTime({
            published_at: '2026-05-04T01:30:00.000Z',
            created_at: '2026-05-04T03:15:00.000Z',
            published_at_source: 'collected_fallback',
        })).toEqual({
            timeText: '12:15',
            source: 'collected',
        })
    })

    it('retries published_at when collected fallback created_at is invalid', () => {
        expect(getArticleDisplayTime({
            published_at: '2026-05-04T04:20:00.000Z',
            created_at: 'not-a-date',
            published_at_source: 'collected_fallback',
        })).toEqual({
            timeText: '13:20',
            source: 'collected',
        })
    })

    it('returns unknown when collected fallback dates are both invalid', () => {
        expect(getArticleDisplayTime({
            published_at: 'not-a-date',
            created_at: 'also-not-a-date',
            published_at_source: 'collected_fallback',
        })).toEqual({
            timeText: '',
            source: 'unknown',
        })
    })

    it('uses created_at for legacy rows whose published_at is KST midnight', () => {
        expect(getArticleDisplayTime({
            published_at: '2026-05-03T15:00:00.000Z',
            created_at: '2026-05-04T03:00:00.000Z',
            published_at_source: null,
        })).toEqual({
            timeText: '12:00',
            source: 'collected',
        })
    })

    it('treats unknown published_at_source values as legacy published rows', () => {
        expect(getArticleDisplayTime({
            published_at: '2026-05-04T05:45:00.000Z',
            created_at: '2026-05-04T08:00:00.000Z',
            published_at_source: 'unexpected',
        })).toEqual({
            timeText: '14:45',
            source: 'published',
        })
    })
})
