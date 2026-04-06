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
    console.log("=== Searching for specific article ===\n");

    // Search for the article
    const { data, error } = await supabase.from('articles')
        .select('id, title, agency, analysis_result, created_at, published_at')
        .ilike('title', '%자금세탁방지제도%')
        .order('created_at', { ascending: false })
        .limit(5);

    if (error) {
        console.log("Error:", error.message);
        return;
    }

    if (!data || data.length === 0) {
        console.log("Article not found!");
        return;
    }

    data.forEach((a, i) => {
        console.log(`=== Article ${i + 1} ===`);
        console.log(`ID: ${a.id}`);
        console.log(`Title: ${a.title}`);
        console.log(`Agency: ${a.agency}`);
        console.log(`Published: ${a.published_at}`);
        console.log(`Created: ${a.created_at}`);
        console.log(`\nAnalysis Result:`);
        console.log(JSON.stringify(a.analysis_result, null, 2));
        console.log('\n');
    });
}

check();
