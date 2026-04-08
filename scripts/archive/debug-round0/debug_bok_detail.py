import requests
from bs4 import BeautifulSoup

url = "https://www.bok.or.kr/portal/bbs/P0000559/view.do?nttId=10095250&depth=201150&pageUnit=10&pageIndex=1&programType=newsData&menuNo=200690&oldMenuNo=201263"
headers = {
    'User-Agent': 'Mozilla/5.0'
}
resp = requests.get(url, headers=headers, verify=False)
with open("bok_detail.html", "w", encoding="utf-8") as f:
    f.write(resp.text)
