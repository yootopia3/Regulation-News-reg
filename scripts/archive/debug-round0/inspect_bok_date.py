import requests
from bs4 import BeautifulSoup

url = "https://www.bok.or.kr/portal/singl/newsData/listCont.do?menuNo=201263"
try:
    resp = requests.get(url, verify=False, timeout=10)
    soup = BeautifulSoup(resp.content, 'html.parser')
    
    items = soup.select('li.bbsRowCls') # From agencies.json selector
    print(f"Found {len(items)} items")
    
    for item in items[:3]:
        title = item.select_one('a.title').get_text(strip=True)
        date_elem = item.select_one('span.date') # From agencies.json selector
        date_text = date_elem.get_text(strip=True) if date_elem else "No date span"
        
        print(f"Title: {title}")
        print(f"Date Text: '{date_text}'")
        print("-" * 20)
        
except Exception as e:
    print(e)
