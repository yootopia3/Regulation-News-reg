import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from dotenv import load_dotenv
from supabase import create_client
from collections import Counter

load_dotenv()
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_ANON_KEY')
supabase = create_client(url, key)

# FSS_SANCTION 데이터 확인
print('=== FSS_SANCTION (검사결과 제재) ===')
res = supabase.table('articles').select('id, title, agency, published_at, link').eq('agency', 'FSS_SANCTION').order('published_at', desc=True).limit(100).execute()
print(f'Total fetched: {len(res.data)}')

# 제목별 카운트
titles = [r['title'] for r in res.data]
title_counts = Counter(titles)

print('\n=== 중복 제목 (2회 이상) ===')
duplicates = [(t, c) for t, c in title_counts.items() if c > 1]
if duplicates:
    for title, count in sorted(duplicates, key=lambda x: -x[1])[:10]:
        print(f'  [{count}회] {title[:50]}...')
else:
    print('  중복 없음')

# 링크별 카운트
links = [r['link'] for r in res.data]
link_counts = Counter(links)

print('\n=== 중복 링크 (2회 이상) ===')
dup_links = [(l, c) for l, c in link_counts.items() if c > 1]
if dup_links:
    for link, count in sorted(dup_links, key=lambda x: -x[1])[:10]:
        print(f'  [{count}회] {link[:60]}...')
else:
    print('  중복 없음')

print('\n=== FSS_MGMT_NOTICE (경영유의사항) ===')
res2 = supabase.table('articles').select('id, title, agency, published_at, link').eq('agency', 'FSS_MGMT_NOTICE').order('published_at', desc=True).limit(100).execute()
print(f'Total fetched: {len(res2.data)}')

titles2 = [r['title'] for r in res2.data]
title_counts2 = Counter(titles2)
duplicates2 = [(t, c) for t, c in title_counts2.items() if c > 1]

print('\n=== 중복 제목 (2회 이상) ===')
if duplicates2:
    for title, count in sorted(duplicates2, key=lambda x: -x[1])[:10]:
        print(f'  [{count}회] {title[:50]}...')
else:
    print('  중복 없음')
