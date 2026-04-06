const { createClient } = require('@supabase/supabase-js');
const fs = require('fs');

// Load from .env.local
let supaUrl = '';
let supaKey = '';
try {
    const envContent = fs.readFileSync('.env.local', 'utf-8');
    envContent.split('\n').forEach(line => {
        if (line.startsWith('NEXT_PUBLIC_SUPABASE_URL_V2=')) {
            supaUrl = line.split('=')[1].trim();
        }
        if (line.startsWith('NEXT_PUBLIC_SUPABASE_ANON_KEY_V2=')) {
            supaKey = line.split('=')[1].trim();
        }
    });
} catch (e) {
    console.log("Error reading .env.local");
}

const supabase = createClient(supaUrl, supaKey);

async function check() {
    console.log("=== Recent Articles Analysis Status ===\n");

    // Get articles from today
    const { data, error } = await supabase.from('articles')
        .select('id, title, agency, analysis_result, created_at')
        .gte('created_at', '2025-12-29T00:00:00')
        .order('created_at', { ascending: false });

    if (error) {
        console.log("Error:", error.message);
        return;
    }

    let total = data?.length || 0;
    let nullAnalysis = 0;
    let hasAnalysis = 0;

    console.log(`Total articles from today: ${total}\n`);

    data?.forEach((a) => {
        if (a.analysis_result === null) {
            nullAnalysis++;
            console.log(`[NULL] ${a.agency} - ${a.title.substring(0, 50)}...`);
        } else {
            hasAnalysis++;
        }
    });

    console.log(`\n=== Summary ===`);
    console.log(`With analysis: ${hasAnalysis}`);
    console.log(`NULL analysis: ${nullAnalysis}`);
}

check();
