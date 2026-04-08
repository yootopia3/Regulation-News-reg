import requests
from bs4 import BeautifulSoup

url = "https://www.bok.or.kr/portal/singl/newsData/listCont.do?menuNo=201263&pageIndex=1"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

print(f"Fetching {url}...")
resp = requests.get(url, headers=headers, verify=False)
print(f"Status: {resp.status_code}")
print(f"Content Length: {len(resp.text)}")
print("Preview:\n")
print(resp.text[:2000])

with open("debug_bok_fragment.html", "w", encoding="utf-8") as f:
    f.write(resp.text)
