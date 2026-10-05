import { pressAgencies, regulationAgencies, sanctionAgencies, type DashboardCategory } from './constants'
const categoryAgencies: Record<DashboardCategory, readonly string[]> = {
    press_release: pressAgencies, regulation_notice: regulationAgencies, sanction_notice: sanctionAgencies,
}
export function dashboardSelection(category?: string | string[], agency?: string | string[]) {
    const selectedCategory: DashboardCategory = typeof category === 'string' && Object.hasOwn(categoryAgencies, category) ? category as DashboardCategory : 'press_release'
    return { category: selectedCategory, agency: typeof agency === 'string' && categoryAgencies[selectedCategory].includes(agency) ? agency : null }
}
export function dashboardHref(category: DashboardCategory, agency: string | null = null) {
    const selection = dashboardSelection(category, agency || undefined)
    const params = new URLSearchParams({ category: selection.category })
    if (selection.agency) params.set('agency', selection.agency)
    return `/?${params}`
}
