
'use client'

import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import { X, Download, Printer } from 'lucide-react'

interface ReportModalProps {
    isOpen: boolean
    onClose: () => void
    article: {
        id: number
        title: string
        content?: string
        agency: string
    } | null
}

export default function ReportModal({ isOpen, onClose, article }: ReportModalProps) {
    const [loading, setLoading] = useState(false)
    const [report, setReport] = useState<string | null>(null)

    useEffect(() => {
        if (isOpen && article) {
            fetchReport()
        } else {
            setReport(null)
        }
    }, [isOpen, article])

    const fetchReport = async () => {
        if (!article) return
        setLoading(true)
        try {
            const res = await fetch('/api/report', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    articleId: article.id,
                    title: article.title,
                    content: article.content || article.title, // Fallback if content missing
                    agency: article.agency
                })
            })

            if (!res.ok) {
                const errorData = await res.json().catch(() => ({}))
                throw new Error(errorData.error || 'Failed to fetch report')
            }

            const data = await res.json()
            setReport(data.report)
        } catch (error: any) {
            console.error(error)
            setReport(`**Error:** ${error.message || 'Failed to generate report. Please try again.'}`)
        } finally {
            setLoading(false)
        }
    }

    // Custom Markdown Components for styling
    const MarkdownComponents = {
        h1: ({ node, ...props }: any) => <h1 className="text-xl font-bold text-slate-900 mb-4 pb-2 border-b border-slate-200 mt-6 first:mt-0" {...props} />,
        h2: ({ node, ...props }: any) => <h2 className="text-lg font-bold text-sky-700 mb-3 mt-6" {...props} />,
        h3: ({ node, ...props }: any) => <h3 className="text-base font-bold text-slate-800 mb-2 mt-4" {...props} />,
        p: ({ node, ...props }: any) => <p className="text-[15px] leading-7 text-slate-700 mb-3 break-words text-justify" {...props} />,
        li: ({ node, children, ...props }: any) => (
            <li className="text-[15px] leading-7 text-slate-700 mb-1 pl-1" {...props}>
                <span className="mr-2 text-sky-500">•</span>
                {children}
            </li>
        ),
        ul: ({ node, ...props }: any) => <ul className="mb-4 pl-4" {...props} />,
        strong: ({ node, ...props }: any) => <strong className="font-bold text-slate-900" {...props} />,
        hr: ({ node, ...props }: any) => <hr className="my-6 border-slate-200" {...props} />,
    }

    if (!isOpen || !article) return null

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm transition-opacity"
                onClick={onClose}
            ></div>

            {/* Modal Container - Modern Dashboard Style */}
            <div className="relative w-full max-w-3xl bg-white shadow-xl rounded-2xl overflow-hidden flex flex-col max-h-[85vh] animate-in fade-in zoom-in-95 duration-200 border border-slate-200">

                {/* Header Toolbar */}
                <div className="flex items-center justify-between px-8 py-5 border-b border-slate-100 bg-white">
                    <div className="flex items-center gap-3">
                        <div className="bg-sky-50 rounded-lg p-2">
                            <span className="text-lg">✨</span>
                        </div>
                        <div>
                            <h2 className="text-sm font-bold text-slate-900 tracking-tight">AI 심층 분석 리포트</h2>
                            <p className="text-xs text-slate-500 font-medium">{article.agency} • {new Date().toLocaleDateString()}</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-1">
                        <button className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-50 rounded-full transition-colors" title="Print" onClick={() => window.print()}>
                            <Printer className="w-4 h-4" />
                        </button>
                        <button onClick={onClose} className="p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-full transition-colors ml-1">
                            <X className="w-5 h-5" />
                        </button>
                    </div>
                </div>

                {/* Content Area */}
                <div className="flex-1 overflow-y-auto p-8 sm:p-10 bg-white scrollbar-thin scrollbar-thumb-slate-200">
                    {loading ? (
                        <div className="flex flex-col items-center justify-center h-64 space-y-4">
                            <div className="relative">
                                <div className="w-12 h-12 border-4 border-slate-100 border-t-sky-500 rounded-full animate-spin"></div>
                                <div className="absolute inset-0 flex items-center justify-center">
                                    <div className="w-2 h-2 bg-sky-500 rounded-full animate-pulse"></div>
                                </div>
                            </div>
                            <p className="text-sm font-medium text-slate-500 animate-pulse">
                                리포트 생성 중...
                            </p>
                        </div>
                    ) : (
                        <div className="max-w-none">
                            {/* Title Section */}
                            <div className="mb-8">
                                <h1 className="text-2xl font-bold text-slate-900 leading-snug mb-3">
                                    {article.title}
                                </h1>
                                <div className="flex flex-wrap gap-2 text-xs font-semibold">
                                    <span className="px-2.5 py-1 rounded bg-slate-100 text-slate-600">
                                        {article.agency}
                                    </span>
                                    <span className="px-2.5 py-1 rounded bg-sky-50 text-sky-600 border border-sky-100">
                                        Risk Analysis
                                    </span>
                                </div>
                            </div>

                            {/* Markdown Content */}
                            <ReactMarkdown components={MarkdownComponents}>
                                {report || ''}
                            </ReactMarkdown>

                            {/* Footer */}
                            <div className="mt-12 pt-6 border-t border-slate-100 flex items-center justify-center gap-2">
                                <span className="text-[10px] font-bold text-slate-300 uppercase tracking-widest">
                                    Powered by MarketPulse AI
                                </span>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
