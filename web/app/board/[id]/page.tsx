import BoardDetail from '@/components/board/BoardDetail'
export default async function BoardPostPage({ params }: { params: Promise<{ id: string }> }) {
    return <BoardDetail id={(await params).id} />
}
