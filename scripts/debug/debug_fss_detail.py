import requests
from bs4 import BeautifulSoup

url = "https://www.fss.or.kr/fss/bbs/B0000188/view.do?nttId=208246&menuNo=200218&pageIndex=1"
headers = {
    'User-Agent': 'Mozilla/5.0'
}
resp = requests.get(url, headers=headers, verify=False)
with open("fss_detail.html", "w", encoding="utf-8") as f:
    f.write(resp.text)
