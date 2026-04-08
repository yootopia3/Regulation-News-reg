import { z } from 'zod'

export const ReportRequestSchema = z.object({
  articleId: z.string().min(1),
})

export type ReportRequest = z.infer<typeof ReportRequestSchema>
