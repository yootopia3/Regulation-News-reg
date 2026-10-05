
import DashboardV2 from '@/components/dashboard/DashboardV2'
import { dashboardSelection } from '@/components/dashboard/navigation'

export const revalidate = 60

export default async function Home({ searchParams }: { searchParams: Promise<{ category?: string | string[]; agency?: string | string[] }> }) {
  const params = await searchParams
  const selection = dashboardSelection(params.category, params.agency)
  return <DashboardV2 key={`${selection.category}:${selection.agency}`} initialCategory={selection.category} initialAgency={selection.agency}
    isCategoryNavigation={params.category === selection.category} />
}
