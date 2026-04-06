
import requests
from bs4 import BeautifulSoup

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}

print("=== 1. BOK (한국은행) 스크래핑 테스트 ===\n")
bok_url = "https://www.bok.or.kr/portal/singl/newsData/listCont.do?menuNo=201263&pageIndex=1"
bok_selector = "li.bbsRowCls"

try:
    res = requests.get(bok_url, headers=headers, timeout=30)
    soup = BeautifulSoup(res.content, 'html.parser')
    rows = soup.select(bok_selector)
    print(f"Selector '{bok_selector}' found {len(rows)} items")
    
    if rows:
        for i, row in enumerate(rows[:3], 1):
            title = row.select_one("a.title")
            date = row.select_one("span.date")
            print(f"{i}. {title.get_text(strip=True) if title else 'NO TITLE'}")
            print(f"   Date: {date.get_text(strip=True) if date else 'NO DATE'}")
    else:
        print("No rows found! Dump first 2000 chars:")
        print(soup.get_text()[:2000])
except Exception as e:
    print(f"Error: {e}")

print("\n=== 2. FSS_REG (금감원 세칙 제개정 예고) 스크래핑 테스트 ===\n")
fss_reg_url = "https://www.fss.or.kr/fss/job/lrgRegItnPrvntc/list.do?menuNo=200489"
fss_reg_selector = "table tbody tr"

try:
    res = requests.get(fss_reg_url, headers=headers, timeout=30, verify=False)
    soup = BeautifulSoup(res.content, 'html.parser')
    rows = soup.select(fss_reg_selector)
    print(f"Selector '{fss_reg_selector}' found {len(rows)} items")
    
    if rows:
        for i, row in enumerate(rows[:3], 1):
            title = row.select_one("td.title a")
            date = row.select_one("td:nth-of-type(3)")
            print(f"{i}. {title.get_text(strip=True) if title else 'NO TITLE'}")
            print(f"   Date: {date.get_text(strip=True) if date else 'NO DATE'}")
except Exception as e:
    print(f"Error: {e}")

print("\n=== 3. FSC_REG (금융위 규제변경예고) 스크래핑 테스트 ===\n")
fsc_reg_url = "https://www.fsc.go.kr/po040301"
fsc_reg_selector = ".board-list-wrap li"

try:
    res = requests.get(fsc_reg_url, headers=headers, timeout=30)
    soup = BeautifulSoup(res.content, 'html.parser')
    rows = soup.select(fsc_reg_selector)
    print(f"Selector '{fsc_reg_selector}' found {len(rows)} items")
    
    if rows:
        for i, row in enumerate(rows[:3], 1):
            title = row.select_one(".subject a")
            date = row.select_one(".day")
            print(f"{i}. {title.get_text(strip=True) if title else 'NO TITLE'}")
            print(f"   Date: {date.get_text(strip=True) if date else 'NO DATE'}")
except Exception as e:
    print(f"Error: {e}")
