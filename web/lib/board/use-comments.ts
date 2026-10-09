'use client'
import { useEffect, useRef, useState } from 'react'
import { boardRequest, jsonRequest } from './client'
import { BOARD_COMMENT_PAGE_SIZE, type BoardComment, type BoardCommentsResponse } from './types'

type CommentAction = { comment: BoardComment; kind: 'edit' | 'delete' }
const emptyComments = { comments: [] as BoardComment[], total: 0, isAdmin: false }
export function useBoardComments(postId: string) {
    const [data, setData] = useState(emptyComments)
    const [page, setPage] = useState(1)
    const [version, setVersion] = useState(0)
    const [loading, setLoading] = useState(true)
    const [loadError, setLoadError] = useState('')
    const [error, setError] = useState('')
    const [notice, setNotice] = useState('')
    const [busy, setBusy] = useState(false)
    const busyRef = useRef(false)
    const [author, setAuthor] = useState('')
    const [body, setBody] = useState('')
    const [password, setPassword] = useState('')
    const [action, setAction] = useState<CommentAction | null>(null)
    const [editBody, setEditBody] = useState('')
    const [actionPassword, setActionPassword] = useState('')
    const url = `/api/board/${postId}/comments`
    useEffect(() => {
        const controller = new AbortController()
        let correctingPage = false
        boardRequest<BoardCommentsResponse>(`${url}?page=${page}`, { signal: controller.signal }).then(result => {
            if (controller.signal.aborted) return
            // A concurrent deletion can remove the last item of the last page.
            const lastPage = Math.max(1, Math.ceil(result.total / BOARD_COMMENT_PAGE_SIZE))
            if (page > lastPage) { correctingPage = true; setPage(lastPage); return }
            setData(result)
        }).catch(error => {
            if (!controller.signal.aborted) { setData(emptyComments); setLoadError(error.message) }
        }).finally(() => { if (!controller.signal.aborted && !correctingPage) setLoading(false) })
        return () => controller.abort()
    }, [url, page, version])
    function reload(target = page) {
        setLoading(true); setLoadError(''); setPage(target); setVersion(value => value + 1)
    }
    function cancel() { setAction(null); setEditBody(''); setActionPassword(''); setError('') }
    function begin(comment: BoardComment, kind: CommentAction['kind']) {
        setAction({ comment, kind }); setEditBody(comment.body); setActionPassword(''); setError(''); setNotice('')
    }
    async function run(operation: () => Promise<void>) {
        if (busyRef.current) return
        busyRef.current = true; setBusy(true); setError(''); setNotice('')
        try { await operation() }
        catch (error) { setError(error instanceof Error ? error.message : '댓글을 처리하지 못했습니다.') }
        finally { busyRef.current = false; setBusy(false) }
    }
    const create = () => run(async () => {
        await boardRequest(url, jsonRequest('POST', { author_name: author, body, password }))
        setBody(''); setPassword(''); cancel(); setNotice('댓글이 등록되었습니다.'); reload(1)
    })
    const confirm = () => run(async () => {
        if (!action) return
        const { comment, kind } = action
        await boardRequest(`${url}/${comment.id}`, jsonRequest(kind === 'edit' ? 'PATCH' : 'DELETE', {
            password: actionPassword, revision: comment.revision, ...(kind === 'edit' ? { body: editBody } : {}),
        }))
        cancel(); setNotice(kind === 'edit' ? '댓글이 수정되었습니다.' : '댓글이 삭제되었습니다.'); reload()
    })
    return { ...data, page, totalPages: Math.max(1, Math.ceil(data.total / BOARD_COMMENT_PAGE_SIZE)), loading, loadError,
        error, notice, busy, author, setAuthor, body, setBody, password, setPassword,
        action, editBody, setEditBody, actionPassword, setActionPassword, begin, cancel, create, confirm, reload }
}
