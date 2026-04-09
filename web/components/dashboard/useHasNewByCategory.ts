import { useMemo } from 'react'
import { isArticleNew } from '@/utils/newArticleTracker'
import { Article } from './NewsCard'

export type HasNewByCategory = {
    hasNewPress: boolean
    hasNewReg: boolean
    hasNewSanction: boolean
}

export function useHasNewByCategory(
    articles: Article[],
    lastVisitTime: Date | null,
): HasNewByCategory {
    return useMemo(() => {
        const hasNewPress = articles.some(a =>
            (a.category === 'press_release' || !a.category) &&
            isArticleNew(a.created_at || a.published_at, lastVisitTime)
        )
        const hasNewReg = articles.some(a =>
            a.category === 'regulation_notice' &&
            isArticleNew(a.created_at || a.published_at, lastVisitTime)
        )
        const hasNewSanction = articles.some(a =>
            a.category === 'sanction_notice' &&
            isArticleNew(a.created_at || a.published_at, lastVisitTime)
        )
        return { hasNewPress, hasNewReg, hasNewSanction }
    }, [articles, lastVisitTime])
}
