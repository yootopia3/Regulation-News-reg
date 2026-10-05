import BoardEditor from '@/components/board/BoardEditor'
export default async function EditBoardPost({ params }: { params: Promise<{ id: string }> }) {
    return <BoardEditor id={(await params).id} />
}
