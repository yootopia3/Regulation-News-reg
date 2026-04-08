
import requests
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings()

url = "https://www.fss.or.kr/fss/bbs/B0000188/list.do?menuNo=200218"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
}

resp = requests.get(url, headers=headers, timeout=20, verify=False)
print(f"Status: {resp.status_code}")

soup = BeautifulSoup(resp.text, 'html.parser')

# Current selector
rows = soup.select("table tbody tr")
print(f"Rows found with 'table tbody tr': {len(rows)}")

if len(rows) > 0:
    first = rows[0]
    print("\n[First Row HTML]")
    print(first.prettify()[:500])
    
    title_elem = first.select_one("td.title a")
    print(f"\nSelector 'td.title a': {title_elem}")
    
    date_elem = first.select_one("td:nth-of-type(4)")
    print(f"Selector 'td:nth-of-type(4)': {date_elem}")
else:
    print("No rows found! Trying alternate selectors...")
    # Try alternate selector
    alt_rows = soup.select(".list-tb tbody tr")
    print(f"Rows with '.list-tb tbody tr': {len(alt_rows)}")
