
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.db.client import supabase

print("=== 1. 규제개정 (최근 데이터 확인) ===\n")

# FSS_REG 최근 데이터
res = supabase.table('articles') \
    .select('agency, published_at, title') \
    .in_('agency', ['FSS_REG', 'FSC_REG', 'FSS_REG_INFO']) \
    .order('published_at', desc=True) \
    .limit(10) \
    .execute()

if res.data:
    for row in res.data:
        print(f"[{row['agency']}] {row['published_at'][:10]} - {row['title'][:40]}...")
else:
    print("규제개정 데이터 없음!")

print("\n=== 2. 한국은행 (BOK) 보도자료 확인 ===\n")

# BOK 최근 데이터
res2 = supabase.table('articles') \
    .select('agency, published_at, title') \
    .eq('agency', 'BOK') \
    .order('published_at', desc=True) \
    .limit(10) \
    .execute()

if res2.data:
    for row in res2.data:
        print(f"[{row['agency']}] {row['published_at'][:10]} - {row['title'][:40]}...")
else:
    print("BOK 데이터 없음!")

print("\n=== 3. 전체 기관별 최신 날짜 ===\n")

# 각 기관별 최신 날짜 확인
agencies = ['FSC', 'FSS', 'MOEF', 'BOK', 'FSS_REG', 'FSC_REG', 'FSS_REG_INFO']
for agency in agencies:
    res3 = supabase.table('articles') \
        .select('published_at') \
        .eq('agency', agency) \
        .order('published_at', desc=True) \
        .limit(1) \
        .execute()
    
    if res3.data:
        print(f"{agency}: 최신 {res3.data[0]['published_at'][:10]}")
    else:
        print(f"{agency}: 데이터 없음")
