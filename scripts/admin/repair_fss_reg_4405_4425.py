"""Repair only existing FSS_REG notices 4405 and 4425; default is read-only."""
import argparse
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

TARGETS = ('4405', '4425')
COLUMNS = 'id,agency,link,title,content,analysis_result,published_at,category,created_at'
DETAIL_PATH = '/fss/job/lrgRegItnPrvntc/view.do'


def matches(link, source_id):
    url = urlsplit(link)
    return (url.scheme == 'https' and url.hostname == 'www.fss.or.kr'
            and url.path == DETAIL_PATH
            and parse_qs(url.query).get('lrgSlno') == [source_id])


def read_target(db, source_id):
    rows = (db.table('articles').select(COLUMNS).eq('agency', 'FSS_REG')
            .like('link', '%lrgSlno=' + source_id + '%').limit(3).execute().data or [])
    exact = [row for row in rows if matches(row['link'], source_id)]
    if len(rows) >= 3 or len(exact) != 1:
        raise RuntimeError('target_missing_or_ambiguous')
    return exact[0]


def repair(db, fetcher, agency, apply=False):
    # Read and validate both targets before any mutation; never insert.
    before = {source_id: read_target(db, source_id) for source_id in TARGETS}
    reports = []
    for source_id, row in before.items():
        old = row.get('content')
        if old is not None and not isinstance(old, str):
            raise RuntimeError('unexpected_content_type')
        length = len(old or '')
        report = {'source_id': source_id, 'before_chars': length,
                  'before_present': bool((old or '').strip()), 'after_chars': length}
        if report['before_present']:
            report['status'] = 'already_present'
        elif not apply:
            report['status'] = 'missing_read_only'
        else:
            content = fetcher(row['link'], agency)
            if not content or len(content.strip()) < 50 or content.startswith('[Short Content]'):
                raise RuntimeError('body_not_verified')
            query = (db.table('articles').update({'content': content})
                     .eq('id', row['id']).eq('agency', 'FSS_REG').eq('link', row['link']))
            query = query.is_('content', 'null') if old is None else query.eq('content', old)
            saved = query.execute().data or []
            after = read_target(db, source_id)
            if any(after.get(key) != value for key, value in row.items() if key != 'content'):
                raise RuntimeError('metadata_changed_during_repair')
            if not (after.get('content') or '').strip():
                raise RuntimeError('body_still_missing')
            if saved and after['content'] != content:
                raise RuntimeError('stored_body_mismatch')
            report['after_chars'] = len(after['content'])
            report['status'] = 'repaired' if saved else 'concurrently_filled_preserved'
        report['after_present'] = report['after_chars'] > 0 if report['status'] != 'missing_read_only' else False
        reports.append(report)
        print('FSS_REG_REPAIR ' + json.dumps(report, sort_keys=True), flush=True)
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    from src.config.settings import load_env
    from src.db.client import get_supabase_client
    from src.collectors.content_scraper import fetch_content
    load_env()
    config = json.loads(Path('config/agencies.json').read_text())
    agency = next(a for a in config['agencies'] if a['code'] == 'FSS_REG')
    repair(get_supabase_client(), fetch_content, agency, apply=args.apply)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Never print provider response bodies, credentials, or stored content.
        print('FSS_REG_REPAIR_FAILED ' + type(exc).__name__, flush=True)
        raise SystemExit(1) from None
