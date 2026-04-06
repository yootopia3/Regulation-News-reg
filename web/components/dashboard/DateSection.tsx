
import React from 'react'
import NewsCard, { Article } from './NewsCard'

interface DateSectionProps {
    dateTitle: string;
    articles: Article[];
    onGenerateReport: (article: Article) => void;
    defaultExpanded?: boolean;
    newCount?: number;  // Number of new articles in this section
}

export default function DateSection({ dateTitle, articles, onGenerateReport, defaultExpanded = false, newCount = 0 }: DateSectionProps) {
    const [isExpanded, setIsExpanded] = React.useState(defaultExpanded);

    // Calculate agency counts for this date
    const agencyCounts = React.useMemo(() => {
        const counts: Record<string, number> = {};
        articles.forEach(a => {
            counts[a.agency] = (counts[a.agency] || 0) + 1;
        });
        return counts;
    }, [articles]);

    // Agency Styling Config (Unified with NewsCard)
    const agencyConfig: Record<string, { name: string, className: string }> = {
        'FSS': { name: '금감원', className: 'bg-blue-100 text-blue-700' },
        'FSC': { name: '금융위', className: 'bg-green-100 text-green-700' },
        'BOK': { name: '한은', className: 'bg-purple-100 text-purple-700' },
        'MOEF': { name: '기재부', className: 'bg-orange-100 text-orange-700' },
        'FSS_REG': { name: '금감원', className: 'bg-blue-100 text-blue-700' },
        'FSC_REG': { name: '금융위', className: 'bg-green-100 text-green-700' },
        'FSS_REG_INFO': { name: '금감원', className: 'bg-blue-100 text-blue-700' },
        'FSS_SANCTION': { name: '검사결과 제재', className: 'bg-red-100 text-red-700' },
        'FSS_MGMT_NOTICE': { name: '경영유의사항', className: 'bg-orange-100 text-orange-700' },
    };

    return (
        <section className="mb-2">
            {/* Sticky Date Header (Clickable Accordion - Card Style) */}
            <div
                onClick={() => setIsExpanded(!isExpanded)}
                className="sticky top-28 z-30 mb-3 cursor-pointer select-none group"
            >
                <div className={`
                    relative flex items-center justify-between px-6 py-4 
                    bg-white rounded-xl border border-gray-100 shadow-sm 
                    transition-all duration-200 
                    ${isExpanded ? 'shadow-md border-blue-100 translate-y-0' : 'hover:translate-y-[-2px] hover:shadow-md'}
                `}>
                    {/* Left Accent Bar */}
                    <div className={`absolute left-0 top-3 bottom-3 w-1.5 rounded-r-md transition-colors ${isExpanded ? 'bg-[#3B82F6]' : 'bg-gray-300 group-hover:bg-[#3B82F6]/70'}`}></div>

                    <div className="flex flex-col gap-2">
                        {/* Row 1: Date Title + Total Count + NEW Badge */}
                        <div className="flex items-center gap-3">
                            <h2 className="text-xl font-bold tracking-tight text-slate-900">
                                {dateTitle}
                            </h2>
                            <span className="px-2.5 py-1 text-xs font-bold text-slate-500 bg-slate-100 rounded-md whitespace-nowrap">
                                총 {articles.length}건
                            </span>
                            {/* NEW Badge for date section */}
                            {newCount > 0 && (
                                <span className="px-2 py-1 text-xs font-bold text-white bg-gradient-to-r from-red-500 to-orange-500 rounded-md animate-pulse whitespace-nowrap">
                                    NEW {newCount}
                                </span>
                            )}
                        </div>

                        {/* Row 2: Agency Breakdown Badges */}
                        <div className="flex items-center gap-2 flex-wrap">
                            {Object.entries(agencyCounts).map(([agency, count]) => {
                                const config = agencyConfig[agency] || { name: agency, className: 'bg-gray-50 text-gray-600 border border-gray-100' };
                                return (
                                    <span key={agency} className={`px-2 py-1 text-xs font-bold rounded-md whitespace-nowrap ${config.className}`}>
                                        {config.name} {count}
                                    </span>
                                );
                            })}
                        </div>
                    </div>

                    {/* Arrow Icon */}
                    <svg
                        className={`w-5 h-5 text-gray-400 transition-transform duration-200 ${isExpanded ? 'rotate-180 text-[#3B82F6]' : 'group-hover:text-gray-600'}`}
                        fill="none" stroke="currentColor" viewBox="0 0 24 24"
                    >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                </div>
            </div>

            {/* Articles List (Collapsible) */}
            {isExpanded && (
                <div className="px-4 space-y-3 mt-1 mb-6 animate-in slide-in-from-top-2 duration-200 fade-in">
                    {[...articles]
                        .sort((a, b) => {
                            // 1. Importance score (desc)
                            const scoreA = a.analysis_result?.importance_score || 0;
                            const scoreB = b.analysis_result?.importance_score || 0;
                            if (scoreB !== scoreA) return scoreB - scoreA;
                            // 2. If same score, latest first
                            return new Date(b.published_at).getTime() - new Date(a.published_at).getTime();
                        })
                        .map(article => (
                            <NewsCard
                                key={article.id}
                                article={article}
                                onGenerateReport={onGenerateReport}
                            />
                        ))}
                </div>
            )}
        </section>
    )
}
