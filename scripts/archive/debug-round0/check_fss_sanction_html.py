"""
Debug script to check actual HTML structure of FSS sanction pages.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz

kst = pytz.timezone('Asia/Seoul')
now_kst = datetime.now(kst)
cutoff = now_kst - timedelta(days=7)

today_str = now_kst.strftime('%Y-%m-%d')
week_ago_str = cutoff.strftime('%Y-%m-%d')

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

# Test FSS_SANCTION
url1 = f"https://www.fss.or.kr/fss/job/openInfo/list.do?menuNo=200476&sdate={week_ago_str}&edate={today_str}"
print(f"Fetching: {url1}\n")

response = requests.get(url1, headers=headers, timeout=20, verify=False)
soup = BeautifulSoup(response.content, 'html.parser')

# Try various selectors
print("=== Trying various selectors ===")

selectors_to_try = [
    '.bd-list dl',
    '.bd-list tbody tr',
    '.list-type01 dl',
    '.list-type01 li',
    'table tbody tr',
    '.board-list li',
    'ul.list li',
    'div.list-wrap > *'
]

for sel in selectors_to_try:
    items = soup.select(sel)
    print(f"{sel}: {len(items)} items")

print("\n=== Raw list structure ===")
# Find the main content area
content = soup.select_one('.content-box') or soup.select_one('#content') or soup.select_one('main')
if content:
    # Print first 3000 chars of HTML to understand structure
    print(str(content)[:3000])
else:
    print("Could not find content area")
    print(str(soup)[:3000])
