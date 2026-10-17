"""Official regulation forms differ from FSS press release templates."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup
from src.collectors.content_scraper import fetch_content

FIXTURES = Path(__file__).resolve().parents[2] / 'fixtures' / 'collectors'


@pytest.mark.parametrize('source_id,title,body_fragment', [
    ('4405', '보험업감독업무시행세칙', '계리가정 보고서'),
    ('4425', '금융투자업규정시행세칙', '新조정유동성비율'),
])
def test_regulation_form_and_external_attachments(monkeypatch, source_id, title, body_fragment):
    html = (FIXTURES / f'fss_reg_{source_id}.html').read_bytes()
    agency = next(a for a in json.loads(Path('config/agencies.json').read_text())['agencies'] if a['code'] == 'FSS_REG')
    soup = BeautifulSoup(html, 'html.parser')
    assert not soup.select('.bd-view, .krds-bd-view > .n-dbdata')
    assert len(soup.select('.krds-reg.reg2 > dl.form-group')) == 6
    assert len(soup.select(agency['selector']['attachment_links'])) == 2
    assert not soup.select('.krds-reg.reg2 .btn-attach-download')
    monkeypatch.setattr('src.collectors.content_scraper.time.sleep', lambda _: None)
    monkeypatch.setattr('src.collectors.content_scraper.http.fetch', lambda *a, **k: SimpleNamespace(content=html))
    text = fetch_content(f'https://www.fss.or.kr/fss/job/lrgRegItnPrvntc/view.do?lrgSlno={source_id}&menuNo=200489&pageIndex=1', agency)
    assert title in text and body_fragment in text
    assert '3. 규정의 제' in text and '5. 의견제출시한' in text
    assert text.count('https://www.fss.or.kr/fss.hpdownload?') == 2
    assert '.hwp' in text and '.xlsx' in text


def test_regulation_title_guard_rejects_error_page(monkeypatch):
    agency = next(a for a in json.loads(Path('config/agencies.json').read_text())['agencies'] if a['code'] == 'FSS_REG')
    monkeypatch.setattr('src.collectors.content_scraper.time.sleep', lambda _: None)
    monkeypatch.setattr('src.collectors.content_scraper.http.fetch', lambda *a, **k: SimpleNamespace(content=b'<div class="krds-reg reg2">error</div>'))
    assert fetch_content('https://www.fss.or.kr/error', agency) is None
