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
    console.log("=== Analysis Status Check ===\n");

    // Get recent articles with score >= 3
    const { data, error } = await supabase.from('articles')
        .select('title, agency, analysis_result, created_at')
        .gte('analysis_result->>importance_score', 3)
        .order('created_at', { ascending: false })
        .limit(15);

    if (error) {
        console.log("Error:", error.message);
        return;
    }

    let analyzed = 0;
    let failed = 0;
    let skipped = 0;
    let noSummary = 0;

    data?.forEach((a) => {
        const ar = a.analysis_result || {};
        const status = ar.analysis_status || 'UNKNOWN';
        const hasSummary = ar.summary && ar.summary.length > 0;

        if (status === 'ANALYZED') analyzed++;
        else if (status === 'ANALYSIS_FAILED') failed++;
        else if (status === 'SKIPPED') skipped++;

        if (!hasSummary) noSummary++;
    });

    console.log(`Total articles (score >= 3): ${data?.length}`);
    console.log(`- ANALYZED (with summary): ${analyzed}`);
    console.log(`- ANALYSIS_FAILED: ${failed}`);
    console.log(`- SKIPPED: ${skipped}`);
    console.log(`- Missing Summary: ${noSummary}`);
    console.log('');

    // Show articles without summary
    const missingSummary = data?.filter(a => {
        const ar = a.analysis_result || {};
        return !(ar.summary && ar.summary.length > 0);
    });

    if (missingSummary?.length > 0) {
        console.log("=== Articles Missing Summary ===");
        missingSummary.forEach((a, i) => {
            const ar = a.analysis_result || {};
            console.log(`${i + 1}. [${a.agency}] Score: ${ar.importance_score}, Status: ${ar.analysis_status}`);
            console.log(`   ${a.title.substring(0, 60)}...`);
            console.log(`   Created: ${new Date(a.created_at).toLocaleString('ko-KR')}`);
        });
    }
}

check();
