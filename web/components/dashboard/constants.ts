// Category codes used throughout the dashboard sidebar/feed.
export const pressAgencies = ['MOEF', 'FSC', 'FSS', 'BOK', 'MAFRA'] as const
export const regulationAgencies = ['FSC_REG', 'FSS_REG', 'FSS_REG_INFO'] as const
export const sanctionAgencies = ['FSS_SANCTION', 'FSS_MGMT_NOTICE'] as const

// Order arrays — kept as aliases to the base tuples to preserve callsite
// semantics ("which list to iterate in which section").
export const agencyOrder = pressAgencies
export const regAgencyOrder = regulationAgencies
export const sanctionAgencyOrder = sanctionAgencies

export const agencyNames: Record<string, string> = {
  'MOEF': '기획재정부',
  'FSC': '금융위원회',
  'FSS': '금융감독원',
  'BOK': '한국은행',
  'MAFRA': '농식품부',
}

export const regAgencyNames: Record<string, string> = {
  'FSC_REG': '금융위원회',
  'FSS_REG': '금감원 - 세칙 제개정 예고',
  'FSS_REG_INFO': '금감원 - 최근 제개정 정보',
}

export const sanctionAgencyNames: Record<string, string> = {
  'FSS_SANCTION': '검사결과 제재',
  'FSS_MGMT_NOTICE': '경영유의사항',
}

export type DashboardCategory = 'press_release' | 'regulation_notice' | 'sanction_notice'
