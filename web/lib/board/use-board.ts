'use client'
import { useCallback, useEffect, useRef, useState } from 'react'
import { boardRequest, jsonRequest } from './client'
import { MAX_ATTACHMENTS, MAX_ATTACHMENT_BYTES, type BoardListItem, type BoardPost, type BoardCategory, type BoardStatus } from './types'

export function useBoardList() {
    const [search, setSearch] = useState('')
    const [query, setQuery] = useState('')
    const [category, setCategory] = useState('all')
    const [page, setPage] = useState(1)
    const [manage, setManage] = useState(false)
    const [version, setVersion] = useState(0)
    const [data, setData] = useState<{ posts: BoardListItem[]; total: number; isAdmin: boolean }>({ posts: [], total: 0, isAdmin: false })
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    useEffect(() => {
        const controller = new AbortController()
        const params = new URLSearchParams({ q: query, category, page: String(page), manage: manage ? '1' : '0' })
        boardRequest<typeof data>(`/api/board?${params}`, { signal: controller.signal }).then(setData).catch(error => {
            if (!controller.signal.aborted) { setError(error.message); setData({ posts: [], total: 0, isAdmin: false }) }
        }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
        return () => controller.abort()
    }, [query, category, page, manage, version])
    function reload() { setLoading(true); setError(''); setVersion(value => value + 1) }
    return { ...data, loading, error, search, setSearch, page, category, manage,
        setPage: (value: number) => { setPage(value); reload() },
        searchPosts: () => { setQuery(search); setPage(1); reload() },
        selectCategory: (value: string) => { setCategory(value); setPage(1); reload() },
        setManage: (value: boolean) => { setManage(value); setPage(1); reload() }, reload,
        logout: async () => {
            try {
                await boardRequest('/api/admin/logout', { method: 'POST' })
                setManage(false); setPage(1); setData({ posts: [], total: 0, isAdmin: false }); reload()
            } catch (error) { setError(error instanceof Error ? error.message : '로그아웃하지 못했습니다.') }
        } }
}

export function useBoardPost(id: string) {
    const [post, setPost] = useState<BoardPost | null>(null)
    const [isAdmin, setAdmin] = useState(false)
    const [error, setError] = useState('')
    useEffect(() => {
        const controller = new AbortController()
        boardRequest<{ post: BoardPost; isAdmin: boolean }>(`/api/board/${id}`, { signal: controller.signal }).then(result => { setPost(result.post); setAdmin(result.isAdmin) }).catch(error => { if (!controller.signal.aborted) setError(error.message) })
        return () => controller.abort()
    }, [id])
    return { post, isAdmin, error }
}

export function useBoardEditor(id?: string) {
    const [post, setPost] = useState<BoardPost | null>(null)
    const [isAdmin, setAdmin] = useState(false)
    const [loaded, setLoaded] = useState(false)
    const [password, setPassword] = useState('')
    const [author, setAuthor] = useState('')
    const [title, setTitle] = useState('')
    const [body, setBody] = useState('')
    const [category, setCategory] = useState<BoardCategory>('general')
    const [pinned, setPinned] = useState(false)
    const [keptIds, setKeptIds] = useState<string[]>([])
    const [files, setFiles] = useState<File[]>([])
    const [busy, setBusy] = useState(false)
    const busyRef = useRef(false)
    const [error, setError] = useState('')
    const [saved, setSaved] = useState<BoardPost | null>(null)
    const fill = useCallback((value: BoardPost) => {
        setPost(value); setAuthor(value.author_name); setTitle(value.title); setBody(value.body)
        setCategory(value.category); setPinned(value.is_pinned); setKeptIds(value.attachments.map(file => file.id)); setLoaded(true)
    }, [])
    useEffect(() => {
        const controller = new AbortController()
        boardRequest<{ isAdmin: boolean }>('/api/board?page=1', { signal: controller.signal }).then(result => {
            setAdmin(result.isAdmin)
            if (!id) setLoaded(true)
        }).catch(error => { if (!controller.signal.aborted) setError(error.message) })
        return () => controller.abort()
    }, [id])
    async function run(action: () => Promise<void>) {
        if (busyRef.current) return
        busyRef.current = true; setBusy(true); setError('')
        try { await action() } catch (error) { setError(error instanceof Error ? error.message : '처리하지 못했습니다.') }
        finally { busyRef.current = false; setBusy(false) }
    }
    const unlock = () => run(async () => {
        const result = await boardRequest<{ post: BoardPost; isAdmin: boolean }>(`/api/board/${id}/unlock`, jsonRequest('POST', { password }))
        setAdmin(result.isAdmin); fill(result.post)
    })
    const save = (status: BoardStatus) => run(async () => {
        const retained = post?.attachments.filter(file => keptIds.includes(file.id)) || []
        if (retained.length + files.length > MAX_ATTACHMENTS || retained.reduce((sum, file) => sum + file.size, 0) + files.reduce((sum, file) => sum + file.size, 0) > MAX_ATTACHMENT_BYTES) throw new Error('첨부파일은 최대 3개, 합계 3MB까지 등록할 수 있습니다.')
        const form = new FormData()
        form.set('payload', JSON.stringify({ author_name: author, title, body, category, password, status, is_pinned: pinned, ...(post ? { revision: post.revision } : {}), keepAttachmentIds: keptIds }))
        files.forEach(file => form.append('files', file))
        const result = await boardRequest<{ post: BoardPost }>(id ? `/api/board/${id}` : '/api/board', { method: id ? 'PATCH' : 'POST', body: form })
        setSaved(result.post); setPassword(''); setFiles([])
    })
    const remove = (onDeleted: () => void) => run(async () => {
        await boardRequest(`/api/board/${id}`, jsonRequest('DELETE', { password, revision: post?.revision }))
        setPassword(''); onDeleted()
    })
    return { post, isAdmin, loaded, password, setPassword, author, setAuthor, title, setTitle, body, setBody, category, setCategory,
        pinned, setPinned, keptIds, setKeptIds, files, setFiles, busy, error, saved, unlock, save, remove }
}
