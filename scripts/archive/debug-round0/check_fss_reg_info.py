
import requests
from bs4 import BeautifulSoup

headers = {'User-Agent': 'Mozilla/5.0'}

print("=== FSS_REG_INFO (최근 제개정 정보) ===")
url = "https://www.fss.or.kr/fss/job/lrgRegItnInfo/list.do?menuNo=200488"
selector = ".bd-list tbody tr"

try:
    res = requests.get(url, headers=headers, timeout=30, verify=False)
    soup = BeautifulSoup(res.content, 'html.parser')
    rows = soup.select(selector)
    print(f"Selector '{selector}' found {len(rows)} items")
    
    if rows:
        # Check title selector
        first_row = rows[0]
        title_elem = first_row.select_one("td:nth-child(2) a")
        date_elem = first_row.select_one("td:nth-child(3)")
        
        print(f"Title: {title_elem.get_text(strip=True) if title_elem else 'NOT FOUND'}")
        print(f"Date: {date_elem.get_text(strip=True) if date_elem else 'NOT FOUND'}")
        print(f"Link: {title_elem.get('href') if title_elem else 'NOT FOUND'}")
    else:
        print("No rows found! Checking alternative selectors...")
        alt_selectors = ["table tbody tr", ".list tbody tr", "tbody tr"]
        for alt in alt_selectors:
            alt_rows = soup.select(alt)
            if alt_rows:
                print(f"  ALT: '{alt}' found {len(alt_rows)} items")
except Exception as e:
    print(f"Error: {e}")
