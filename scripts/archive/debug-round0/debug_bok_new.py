import requests
from bs4 import BeautifulSoup

url = "https://www.bok.or.kr/portal/singl/newsData/list.do?menuNo=201263"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

try:
    print(f"Fetching {url}...")
    res = requests.get(url, headers=headers, timeout=10, verify=False)
    print(f"Status: {res.status_code}")
    
    soup = BeautifulSoup(res.content, 'html.parser')
    
    # Try finding list items
    # Typically <div class="bdList"> or <ul>
    # Let's verify commonly used structures
    
    articles = []
    
    # Guessing structure based on 'singl' portal
    rows = soup.select(".fixed li") # Common in BOK singl
    if not rows:
        rows = soup.select(".bdList tbody tr")
    if not rows:
        rows = soup.select("ul.list li")
        
    print(f"Rows found: {len(rows)}")
    
    if rows:
        print("First row HTML:")
        print(rows[0].prettify()[:500])
        
    # Dump for view
    with open("bok_debug.html", "w", encoding="utf-8") as f:
        f.write(soup.prettify())
        
except Exception as e:
    print(e)
