
import requests
from bs4 import BeautifulSoup

headers = {'User-Agent': 'Mozilla/5.0'}
url = "https://www.bok.or.kr/portal/singl/newsData/listCont.do?menuNo=201263&pageIndex=1"

res = requests.get(url, headers=headers, timeout=30)
soup = BeautifulSoup(res.content, 'html.parser')
rows = soup.select("li.bbsRowCls")

print("=== BOK Date Parsing Test ===\n")
for i, row in enumerate(rows[:5], 1):
    title_elem = row.select_one("a.title")
    date_elem = row.select_one("span.date")
    
    title = title_elem.get_text(strip=True) if title_elem else "NO TITLE"
    date_raw = date_elem.get_text(strip=True) if date_elem else "NO DATE"
    
    print(f"{i}. Title: {title[:40]}...")
    print(f"   Date RAW: '{date_raw}'")
    
    # Try parsing
    import re
    match = re.search(r'(\d{4}[.-]\d{2}[.-]\d{2})', date_raw)
    if match:
        print(f"   Date PARSED: {match.group(1)}")
    else:
        print(f"   Date PARSED: FAILED!")
    print()
