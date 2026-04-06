import requests
import feedparser
from bs4 import BeautifulSoup
import io

agencies = {
    "FSS": "http://www.fss.or.kr/fss/bbs/B0000188/rss.do?menuNo=200218",
    "BOK": "https://www.bok.or.kr/portal/bbs/B0000245/rss.do?menuNo=200129",
    "FSC": "http://www.fsc.go.kr/about/fsc_bbs_rss/?fid=0111"
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
}

with open("rss_debug_result.txt", "w", encoding="utf-8") as f:
    f.write("=== Testing RSS Feeds with Headers ===\n")
    for name, url in agencies.items():
        msg = f"\n[{name}] Checking {url}..."
        print(msg)
        f.write(msg + "\n")
        try:
            # 1. Fetch with Requests (Advanced Headers)
            response = requests.get(url, headers=headers, timeout=15, verify=False) # verify=False for some gov sites
            msg = f"  HTTP Status: {response.status_code}"
            print(msg)
            f.write(msg + "\n")
            
            content = response.content
            
            # 2. Parse with Feedparser (using content)
            feed = feedparser.parse(content)
            msg = f"  Entries found (Standard): {len(feed.entries)}"
            print(msg)
            f.write(msg + "\n")

            if len(feed.entries) == 0:
                 # Dump content snippet to see what we got
                 snippet = response.text[:500].replace('\n', ' ').replace('\r', '')
                 f.write(f"  [DEBUG] Content snippet: {snippet}\n")

            if len(feed.entries) == 0 and response.status_code == 200:
                 # 3. Fallback: BS4 + LXML (Manual parsing if Feedparser fails on XML)
                 msg = "  -> Trying BS4/LXML Fallback..."
                 print(msg)
                 f.write(msg + "\n")
                 try:
                     soup = BeautifulSoup(content, 'xml')
                     items = soup.find_all('item')
                     msg = f"  Entries found (BS4 Fallback): {len(items)}"
                     print(msg)
                     f.write(msg + "\n")
                     if len(items) > 0:
                         title = items[0].find('title')
                         if title:
                             msg = f"  First Entry (BS4): {title.get_text().strip()}"
                             print(msg)
                             f.write(msg + "\n")
                 except Exception as e:
                     msg = f"  BS4 Error: {e}"
                     print(msg)
                     f.write(msg + "\n")

            if len(feed.entries) > 0:
                msg = f"  First entry title: {feed.entries[0].title}"
                print(msg)
                f.write(msg + "\n")
            
        except Exception as e:
            msg = f"  Error: {e}"
            print(msg)
            f.write(msg + "\n")
