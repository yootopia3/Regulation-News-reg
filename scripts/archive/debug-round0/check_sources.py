
import requests
import feedparser
from bs4 import BeautifulSoup

def check_moef():
    url = "https://www.korea.kr/rss/dept_moef.xml"
    print(f"\n[MOEF Test] Checking RSS: {url}")
    try:
        # RSS는 feedparser로 바로 체크하거나 requests로 raw xml 확인
        resp = requests.get(url, timeout=10)
        print(f"Status Code: {resp.status_code}")
        if resp.status_code == 200:
            feed = feedparser.parse(resp.content)
            print(f"Feed Title: {feed.feed.get('title', 'N/A')}")
            print(f"Entries found: {len(feed.entries)}")
            if len(feed.entries) > 0:
                print(f"Latest entry: {feed.entries[0].title} ({feed.entries[0].get('published', 'No date')})")
        else:
            print("Failed to fetch RSS.")
    except Exception as e:
        print(f"Error: {e}")

def check_bok():
    url = "https://www.bok.or.kr/portal/singl/newsData/listCont.do?menuNo=201263&pageIndex=1"
    print(f"\n[BOK Test] Checking Scraper: {url}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Connection': 'keep-alive'
    }
    try:
        import urllib3
        urllib3.disable_warnings()
        resp = requests.get(url, headers=headers, timeout=20, verify=False)
        print(f"Status Code: {resp.status_code}")
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            # Check main list selector
            items = soup.select("li.bbsRowCls")
            print(f"Items found (li.bbsRowCls): {len(items)}")
            
            if len(items) > 0:
                first = items[0]
                print("\n[Debugging First Item HTML]")
                print(first.prettify())
                
                # Check current selectors
                date_elem = first.select_one("span.date")
                print(f"\nSelector 'span.date' result: {date_elem}")
                
                title_elem = first.select_one("a.title") # or whatever is in config
                print(f"Selector 'a.title' result: {title_elem}")
            else:
                # Debug if selector is wrong
                print("No items found with 'li.bbsRowCls'. Dumping body structure...")
                body_sample = soup.select_one(".content") or soup.body
                print(body_sample.prettify()[:1000])

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    import sys
    # Redirect stdout to a file
    with open("debug_bok_output.txt", "w", encoding="utf-8") as f:
        sys.stdout = f
        try:
            # check_moef()
            check_bok()
        except Exception as e:
            print(f"CRITICAL ERROR: {e}")
