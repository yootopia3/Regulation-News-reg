'use client'

import React, { useState } from 'react'
import { ChevronDown, ChevronUp, ExternalLink, Sparkles } from 'lucide-react'
import StarRating from './StarRating'
import { getMafraDisplayLink } from '@/utils/mafraLink'
import { getArticleDisplayTime } from '@/utils/date'

export interface Article {
    id: string
    title: string
    agency: string
    category?: string | null
    published_at: string
    published_at_source?: 'source' | 'collected_fallback' | string | null
    created_at?: string | null
    link: string
    analysis_result?: {
        summary?: string[]
        importance_score?: number
        risk_level?: string
        keywords?: string[]
        pdf_url?: string
    } | null
    view_count?: number | null
    star_rating?: number | null
    isNew?: boolean
}

interface NewsCardProps {
    article: Article
    onGenerateReport: (article: Article) => void
}

const agencyNames: Record<string, string> = {
    FSC: '금융위',
    FSS: '금감원',
    MOEF: '기재부',
    BOK: '한은',
    KFB: '연합회',
    MAFRA: '농식품부',
    FSC_REG: '금융위',
    FSS_REG: '금감원',
    FSS_REG_INFO: '금감원',
    FSS_SANCTION: '검사결과 제재',
    FSS_MGMT_NOTICE: '경영유의사항',
}

function getAgencyColor(agency: string): string {
    if (agency === 'FSS_SANCTION') return 'bg-red-100 text-red-700'
    if (agency === 'FSS_MGMT_NOTICE') return 'bg-orange-100 text-orange-700'
    if (agency.includes('FSS')) return 'bg-blue-100 text-blue-700'
    if (agency.includes('FSC')) return 'bg-green-100 text-green-700'
    if (agency.includes('BOK')) return 'bg-purple-100 text-purple-700'
    if (agency.includes('MOEF')) return 'bg-orange-100 text-orange-700'
    if (agency.includes('KFB')) return 'bg-sky-100 text-sky-700'
    if (agency.includes('MAFRA')) return 'bg-emerald-100 text-emerald-700'
    return 'bg-gray-100 text-gray-600'
}

function getAgencyName(code: string): string {
    return agencyNames[code] || code
}

function getSubCategory(code: string): string | null {
    if (code === 'FSS_REG') return '세칙 제개정 예고'
    if (code === 'FSS_REG_INFO') return '최근 제개정 정보'
    if (code === 'FSC_REG') return '입법/규정'
    return null
}

function getOriginalLink(article: Article): string {
    if (article.agency === 'KFB' && article.analysis_result?.pdf_url) {
        return article.analysis_result.pdf_url
    }
    return getMafraDisplayLink(article.link, article.agency)
}

export default function NewsCard({ article, onGenerateReport }: NewsCardProps) {
    const [isExpanded, setIsExpanded] = useState(false)
    const score = article.star_rating ?? article.analysis_result?.importance_score ?? 3
    const subCat = getSubCategory(article.agency)
    const displayTime = getArticleDisplayTime(article)
    const originalLink = getOriginalLink(article)

    return (
        <div
            onClick={() => setIsExpanded(!isExpanded)}
            className="
                relative bg-white rounded-2xl p-5 border border-gray-100 shadow-sm
                transition-all duration-300
                hover:shadow-lg hover:border-blue-200 hover:-translate-y-[2px] hover:bg-blue-50/30
                cursor-pointer group
            "
        >
            <div className="cursor-pointer">
                <div className="flex justify-between items-start gap-3">
                    <div data-testid="news-card-left" className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                            <span className={`px-2 py-0.5 text-[11px] font-bold rounded-md ${getAgencyColor(article.agency)}`}>
                                {getAgencyName(article.agency)}
                            </span>

                            {subCat && (
                                <span className="px-1.5 py-0.5 text-[10px] text-gray-500 bg-gray-100/50 border border-gray-200 rounded font-medium">
                                    {subCat}
                                </span>
                            )}

                            {article.isNew && (
                                <span className="px-1.5 py-0.5 text-[10px] font-bold text-white bg-gradient-to-r from-red-500 to-orange-500 rounded-md animate-pulse">
                                    NEW
                                </span>
                            )}
                        </div>

                        <h3 className={`text-lg font-bold text-gray-900 leading-snug group-hover:text-blue-600 transition-colors ${isExpanded ? '' : 'line-clamp-2'}`}>
                            {article.title}
                        </h3>
                    </div>

                    <div data-testid="news-card-right" className="flex flex-col items-end gap-2 shrink-0 min-w-[64px]">
                        {displayTime.timeText && (
                            <span data-testid="news-card-time" className="text-xs text-gray-400 font-medium tracking-tight leading-none">
                                {displayTime.timeText}
                            </span>
                        )}
                        <StarRating score={score} size={12} />
                        {isExpanded ? <ChevronUp size={16} className="text-gray-300" /> : <ChevronDown size={16} className="text-gray-300" />}
                    </div>
                </div>
            </div>

            {isExpanded && (
                <div className="px-4 pb-4 pt-0 border-t border-gray-50 bg-gray-50/30">
                    <div className="mt-3 space-y-3">
                        {article.analysis_result?.summary ? (
                            <div className="bg-slate-50/50 p-3.5 rounded-xl border border-gray-200 text-sm text-gray-900 font-medium space-y-1">
                                <div className="flex items-center gap-1.5 text-xs font-bold text-blue-600 mb-2">
                                    <Sparkles size={12} />
                                    AI 3줄 요약
                                </div>
                                <ul className="list-disc list-outside pl-4 space-y-1.5">
                                    {article.analysis_result.summary.map((line, idx) => (
                                        <li key={idx} className="leading-relaxed opacity-90">{line}</li>
                                    ))}
                                </ul>
                            </div>
                        ) : (
                            <p className="text-sm text-gray-400 italic p-2">AI 요약이 아직 생성되지 않았습니다.</p>
                        )}

                        <div className="grid grid-cols-2 gap-2 mt-2">
                            <a
                                href={originalLink}
                                target="_blank"
                                rel="noreferrer"
                                onClick={(event) => event.stopPropagation()}
                                className="flex items-center justify-center gap-2 h-10 px-4 rounded-xl bg-slate-50 border border-slate-200 text-slate-700 text-sm font-bold transition-all hover:bg-slate-100 hover:text-slate-900 hover:border-slate-300 hover:shadow-sm active:scale-95 group"
                            >
                                <ExternalLink size={16} className="text-slate-500 transition-transform group-hover:text-slate-800 group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
                                원문 보기
                            </a>

                            <button
                                onClick={(event) => {
                                    event.stopPropagation()
                                    onGenerateReport(article)
                                }}
                                className="flex items-center justify-center gap-2 h-10 px-4 rounded-xl bg-blue-50 border border-blue-100 text-blue-700 text-sm font-bold transition-all hover:bg-blue-100 hover:text-blue-800 hover:border-blue-200 hover:shadow-sm active:scale-95 group"
                            >
                                <Sparkles size={16} className="text-blue-500 group-hover:text-blue-600 animate-pulse" />
                                AI 심층 보고서
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
