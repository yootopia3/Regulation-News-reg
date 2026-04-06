const { createClient } = require('@supabase/supabase-js');
const fs = require('fs');

// Load from .env.local manually
let supaUrl = '';
let supaKey = '';
try {
    const envContent = fs.readFileSync('.env.local', 'utf-8');
    const envLines = envContent.split('\n');
    envLines.forEach(line => {
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
    console.log("Checking DB with Correct Scale (1-5)...");

    // Recent 10 articles
    const { data } = await supabase.from('articles')
        .select('title, agency, analysis_result, published_at')
        .order('published_at', { ascending: false })
        .limit(10);

    console.log('\nTop 10 Recent Articles:');
    data?.forEach((a, i) => {
        const score = a.analysis_result?.importance_score || 'N/A';
        console.log(`${i + 1}. [Score: ${score}] ${a.title.substring(0, 40)}...`);
    });

    // Score distribution (1-5 Scale)
    const { data: all } = await supabase.from('articles').select('analysis_result');
    const scores = all?.map(a => a.analysis_result?.importance_score || 0) || [];
    const distribution = {
        'High (4-5)': 0,
        'Medium (3)': 0,
        'Low (1-2)': 0,
        'None (0)': 0
    };

    scores.forEach(s => {
        if (s >= 4) distribution['High (4-5)']++;
        else if (s === 3) distribution['Medium (3)']++;
        else if (s >= 1) distribution['Low (1-2)']++;
        else distribution['None (0)']++;
    });
    console.log('\nScore Distribution (Corrected):', distribution);
}

check();
