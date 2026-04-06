
export const toKSTDate = (dateStr: string): Date => {
    const date = new Date(dateStr)
    // UTC to KST conversion (+9 hours)
    // Server usually returns ISO string in UTC or with offset.
    // Ideally, if string has offset, new Date() handles it.
    // If we want to display KST time explicitly:
    const kstOffset = 9 * 60 * 60 * 1000
    const kstDate = new Date(date.getTime() + kstOffset)
    return kstDate
}

export const formatDateTitle = (dateStr: string): string => {
    const kstDate = toKSTDate(dateStr)
    const year = kstDate.getUTCFullYear()
    const month = kstDate.getUTCMonth() + 1
    const day = kstDate.getUTCDate()
    const weekDays = ['일', '월', '화', '수', '목', '금', '토']
    const weekDay = weekDays[kstDate.getUTCDay()]
    return `${year}. ${month}. ${day} (${weekDay})`
}
