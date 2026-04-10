/**
 * MAFRA article deep-link generator.
 *
 * The MAFRA CMS serves /bbs/home/792/{id}/artclView.do as a raw content
 * page without site navigation. The user-facing URL requires an `enc`
 * query parameter built from a base64-encoded form payload. Non-MAFRA
 * links pass through unchanged.
 */

const MAFRA_BBS_RE = /\/bbs\/home\/792\/(\d+)\/artclView\.do/

const DEFAULT_QS =
  'rgsEnddeStr=&srchColumn=&rgsBgndeStr=&bbsClSeq=&isViewMine=false&page=1&row=10&bbsOpenWrdSeq=&srchWrd=&'

export function getMafraDisplayLink(link: string, agency: string): string {
  if (agency !== 'MAFRA') return link

  const match = link.match(MAFRA_BBS_RE)
  if (!match) return link

  const id = match[1]
  const path = `/bbs/home/792/${id}/artclView.do?${DEFAULT_QS}`
  const raw = `fnct1|@@|${encodeURIComponent(path)}`
  const enc = btoa(raw)
  return `https://www.mafra.go.kr/home/5109/subview.do?enc=${encodeURIComponent(enc)}`
}
