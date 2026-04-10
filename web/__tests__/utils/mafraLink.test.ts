import { describe, it, expect } from 'vitest'
import { getMafraDisplayLink } from '@/utils/mafraLink'

describe('getMafraDisplayLink', () => {
  it('rewrites MAFRA /bbs/ link to enc deep-link', () => {
    const input = 'https://www.mafra.go.kr/bbs/home/792/577574/artclView.do'
    const result = getMafraDisplayLink(input, 'MAFRA')

    expect(result).toMatch(/^https:\/\/www\.mafra\.go\.kr\/home\/5109\/subview\.do\?enc=/)
    // Decode and verify structure
    const enc = decodeURIComponent(result.split('enc=')[1])
    const raw = atob(enc)
    expect(raw).toContain('fnct1|@@|')
    expect(raw).toContain('577574')
  })

  it('passes non-MAFRA links through unchanged', () => {
    const fscLink = 'https://www.fsc.go.kr/no010101/86686'
    expect(getMafraDisplayLink(fscLink, 'FSC')).toBe(fscLink)
  })

  it('passes MAFRA links that do not match /bbs/ pattern through unchanged', () => {
    const oddLink = 'https://www.mafra.go.kr/some/other/path'
    expect(getMafraDisplayLink(oddLink, 'MAFRA')).toBe(oddLink)
  })
})
