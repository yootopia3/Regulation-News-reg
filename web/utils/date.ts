
const KST_TIME_FORMATTER = new Intl.DateTimeFormat('ko-KR', {
    timeZone: 'Asia/Seoul',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
})

const PUBLISHED_AT_SOURCE = {
    COLLECTED_FALLBACK: 'collected_fallback',
} as const

export type PublishedAtSource = 'source' | 'collected_fallback' | null | undefined

export type ArticleDisplayTime = {
    timeText: string
    label: '발행' | '수집' | null
    source: 'published' | 'collected' | 'unknown'
}

export const toKSTDate = (dateStr: string): Date => {
    const date = new Date(dateStr)
    // UTC to KST conversion (+9 hours)
    // Server usually returns ISO string in UTC or with offset.
    // Ideally, if string has offset, new Date() handles it.
    // If we want to display KST time explicitly:
    const kstOffset = 9 * 60 * 60 * 1000
    const kstDate = new Date(date.getTime() + kstOffset)
    return kstDate
}

export const formatDateTitle = (dateStr: string): string => {
    const kstDate = toKSTDate(dateStr)
    const year = kstDate.getUTCFullYear()
    const month = kstDate.getUTCMonth() + 1
    const day = kstDate.getUTCDate()
    const weekDays = ['일', '월', '화', '수', '목', '금', '토']
    const weekDay = weekDays[kstDate.getUTCDay()]
    return `${year}. ${month}. ${day} (${weekDay})`
}

export function formatKSTTime(dateStr?: string | null): string {
    if (!dateStr) return ''

    const date = new Date(dateStr)
    if (Number.isNaN(date.getTime())) return ''

    return KST_TIME_FORMATTER.format(date)
}

function unknownDisplayTime(): ArticleDisplayTime {
    return {
        timeText: '',
        label: null,
        source: 'unknown',
    }
}

function publishedDisplayTime(dateStr?: string | null): ArticleDisplayTime {
    const timeText = formatKSTTime(dateStr)
    if (!timeText) return unknownDisplayTime()

    return {
        timeText,
        label: null,
        source: 'published',
    }
}

export function getArticleDisplayTime(article: {
    published_at?: string | null
    created_at?: string | null
    published_at_source?: PublishedAtSource | string
}): ArticleDisplayTime {
    if (article.published_at_source === PUBLISHED_AT_SOURCE.COLLECTED_FALLBACK) {
        const timeText = formatKSTTime(article.created_at) || formatKSTTime(article.published_at)
        if (!timeText) return unknownDisplayTime()

        return {
            timeText,
            label: '수집',
            source: 'collected',
        }
    }

    return publishedDisplayTime(article.published_at)
}
