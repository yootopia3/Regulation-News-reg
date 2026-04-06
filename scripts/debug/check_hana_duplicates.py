import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from dotenv import load_dotenv
from supabase import create_client
from urllib.parse import urlparse, parse_qs

load_dotenv()
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_ANON_KEY')
supabase = create_client(url, key)

# 하나은행 중복 상세 확인
res = supabase.table('articles').select('id, title, published_at, link').eq('agency', 'FSS_SANCTION').ilike('title', '%하나은행%').order('published_at', desc=True).execute()

print('=== 하나은행 제재 상세 (링크 파라미터 비교) ===')
print(f'총 {len(res.data)}건\n')

# 링크에서 고유 식별자 추출
unique_ids = set()
for r in res.data:
    link = r['link']
    parsed = urlparse(link)
    params = parse_qs(parsed.query)
    exam_id = params.get('examMgmtNo', ['N/A'])[0]
    seq = params.get('emOpenSeq', ['N/A'])[0]
    unique_key = f"{exam_id}-{seq}"
    
    print(f"[{r['published_at'][:10]}] examMgmtNo={exam_id}, emOpenSeq={seq}")
    
    if unique_key in unique_ids:
        print(f"    ⚠️ 중복 발견!")
    else:
        unique_ids.add(unique_key)

print(f"\n총 {len(res.data)}건 중 고유 항목: {len(unique_ids)}건")
print(f"중복 저장된 항목: {len(res.data) - len(unique_ids)}건")
