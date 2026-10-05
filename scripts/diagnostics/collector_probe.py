"""Bounded read-only probe of public source HTML; no DB, credentials or AI."""
import json
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup

URLS = {
    'FSC_RSS': 'https://www.fsc.go.kr/about/fsc_bbs_rss/?fid=0111',
    'FSC_LIST': 'https://www.fsc.go.kr/no010101',
    'FSS_236976': 'https://www.fss.or.kr/fss/bbs/B0000188/view.do?nttId=236976&menuNo=200218&pageIndex=1',
    'FSS_237413': 'https://www.fss.or.kr/fss/bbs/B0000188/view.do?nttId=237413&menuNo=200218&pageIndex=1',
    'FSS_REG_INFO': 'https://www.fss.or.kr/fss/job/lrgRegItnInfo/list.do?menuNo=200488&pageIndex=1',
    'KFB_2012': 'https://m.kfb.or.kr/news/info_news_view.php?idx=2012&col=&sw=&pg=1&gubun=&orderby=&code=&data_year=&SearchOffice=&SearchOpinion=&cate_idx=&BankAll=',
}


def probe(pair):
    label, url = pair
    start = time.monotonic()
    result = {'source': label, 'url': url}
    try:
        response = requests.get(url, timeout=(15, 25), headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        })
        result.update(status=response.status_code, final_url=response.url,
                      bytes=len(response.content), content_type=response.headers.get('Content-Type'))
        soup = BeautifulSoup(response.content, 'html.parser')
        result['title'] = soup.title.get_text(' ', strip=True) if soup.title else None
        # Remove scripts/forms and output only public document structures. Never
        # print response headers, cookies, environment or request credentials.
        for node in soup.select('script,style,input,form button'):
            node.decompose()
        result['iframes'] = [n.get('src') for n in soup.select('iframe')]
        result['structure'] = [str(n)[:14000] for n in soup.select(
            '.dbdata,.bd-view,.board-list-wrap,.bd-list,.view_cont,.view_con,.view-content,.bbs_view,.view-body,article,table'
        )[:5]]
        result['containers'] = [
            {'tag': n.name, 'id': n.get('id'), 'class': n.get('class'),
             'chars': len(n.get_text(' ', strip=True)), 'text': n.get_text(' ', strip=True)[:250]}
            for n in soup.select('div,section')
            if len(n.get_text(' ', strip=True)) > 80
        ][-35:]
        result['tail_html'] = str(soup)[-20000:]
        if len(response.content) < 3000:
            result['small_html'] = str(soup)
    except requests.RequestException as exc:
        result['error'] = type(exc).__name__
    result['seconds'] = round(time.monotonic() - start, 2)
    return result


if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=2) as executor:
        for result in executor.map(probe, URLS.items()):
            print('PROBE_JSON ' + json.dumps(result, ensure_ascii=False), flush=True)
