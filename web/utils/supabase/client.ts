import { createClient } from '@supabase/supabase-js'

// Check if we should use v2.0 DB (for development/beta)
const useV2 = process.env.NEXT_PUBLIC_USE_V2_DB === 'true'

const supabaseUrl = (useV2
    ? process.env.NEXT_PUBLIC_SUPABASE_URL_V2
    : process.env.NEXT_PUBLIC_SUPABASE_URL) || 'https://placeholder.supabase.co'

const supabaseKey = (useV2
    ? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY_V2
    : process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY) || 'placeholder-key'

// Debug log to confirm which DB is connected (CLIENT-SIDE ONLY)
if (typeof window !== 'undefined') {
    console.log(`[Supabase] Connected to ${useV2 ? 'v2.0 (Dev)' : 'v1.0 (Prod)'} DB`)
}

export const supabase = createClient(supabaseUrl, supabaseKey)
