/**
 * Utility for tracking "NEW" articles based on last visit time.
 * Uses localStorage to persist the last visit timestamp.
 */

const LAST_VISIT_KEY = 'regulation_news_last_visit';

/**
 * Get the last visit timestamp from localStorage.
 * Returns null if never visited before.
 */
export function getLastVisitTime(): Date | null {
    if (typeof window === 'undefined') return null;

    const stored = localStorage.getItem(LAST_VISIT_KEY);
    if (!stored) return null;

    const timestamp = parseInt(stored, 10);
    if (isNaN(timestamp)) return null;

    return new Date(timestamp);
}

/**
 * Update the last visit time to now.
 * Call this when user views the dashboard.
 */
export function updateLastVisitTime(): void {
    if (typeof window === 'undefined') return;

    localStorage.setItem(LAST_VISIT_KEY, Date.now().toString());
}

/**
 * Check if an article is "new" based on its created_at time.
 * An article is new if it was created after the user's last visit.
 * 
 * @param articleCreatedAt - The article's created_at timestamp (ISO string)
 * @param lastVisit - The user's last visit time
 * @returns true if the article is new
 */
export function isArticleNew(articleCreatedAt: string, lastVisit: Date | null): boolean {
    // If no last visit, nothing is "new" (first visit shows everything)
    if (!lastVisit) return false;

    const articleDate = new Date(articleCreatedAt);
    return articleDate > lastVisit;
}

/**
 * Count how many articles are new in a list.
 */
export function countNewArticles(
    articles: Array<{ created_at?: string; published_at: string }>,
    lastVisit: Date | null
): number {
    if (!lastVisit) return 0;

    return articles.filter(a => {
        const dateStr = a.created_at || a.published_at;
        return isArticleNew(dateStr, lastVisit);
    }).length;
}
