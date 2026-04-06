const { createClient } = require('@supabase/supabase-js');

// Hardcode for quick check (read from .env.local manually if needed)
const url = process.env.NEXT_PUBLIC_SUPABASE_URL_V2 || 'YOUR_URL_HERE';
const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY_V2 || 'YOUR_KEY_HERE';

// Load from .env.local manually
const fs = require('fs');
const envContent = fs.readFileSync('.env.local', 'utf-8');
const envLines = envContent.split('\n');
let supaUrl = '';
let supaKey = '';
envLines.forEach(line => {
    if (line.startsWith('NEXT_PUBLIC_SUPABASE_URL_V2=')) {
        supaUrl = line.split('=')[1].trim();
    }
    if (line.startsWith('NEXT_PUBLIC_SUPABASE_ANON_KEY_V2=')) {
        supaKey = line.split('=')[1].trim();
    }
});

const supabase = createClient(supaUrl, supaKey);

async function check() {
    // Total count
    const { count: total } = await supabase.from('articles').select('*', { count: 'exact', head: true });
    console.log('Total articles:', total);

    // Recent 10 articles
    const { data } = await supabase.from('articles')
        .select('title, agency, analysis_result, published_at')
        .order('published_at', { ascending: false })
        .limit(10);

    console.log('\nRecent 10 articles:');
    data?.forEach((a, i) => {
        const score = a.analysis_result?.importance_score || 'N/A';
        const date = new Date(a.published_at).toLocaleDateString('ko-KR');
        console.log((i + 1) + '. [' + date + '] [' + a.agency + '] ' + a.title.substring(0, 35) + '... (Score: ' + score + ')');
    });

    // Score distribution
    const { data: all } = await supabase.from('articles').select('analysis_result');
    const scores = all?.map(a => a.analysis_result?.importance_score || 0) || [];
    const distribution = { 'high(7-10)': 0, 'medium(4-6)': 0, 'low(1-3)': 0, 'none(0)': 0 };
    scores.forEach(s => {
        if (s >= 7) distribution['high(7-10)']++;
        else if (s >= 4) distribution['medium(4-6)']++;
        else if (s >= 1) distribution['low(1-3)']++;
        else distribution['none(0)']++;
    });
    console.log('\nScore distribution:', distribution);
}

check();
