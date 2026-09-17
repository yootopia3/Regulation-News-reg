"""Bounded private automation. Logs counts only; no artifacts or raw provider errors."""
import os
from datetime import datetime
from urllib.parse import urlsplit

import requests

from src.config.settings import load_env, get_supabase_service_role_key
from src.db.client import get_supabase_client
from .client import InspectionClient, Settings
from .worker import run_once


def config():
    if os.getenv('SANCTION_AUTOMATION_ENABLED') != 'true':
        raise ValueError('disabled')
    limit = int(os.getenv('SANCTION_BATCH_LIMIT', '3'))
    since = os.environ['SANCTION_AUTOMATION_SINCE']
    parsed_date = datetime.fromisoformat(since.replace('Z', '+00:00'))
    if not 1 <= limit <= 10 or parsed_date.tzinfo is None:
        raise ValueError('invalid_batch')
    site = os.environ['SANCTION_WEB_URL'].rstrip('/')
    parsed = urlsplit(site)
    token = os.environ['SANCTION_AUTOMATION_TOKEN']
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment or len(token) < 32:
        raise ValueError('invalid_endpoint')
    return limit, since, site + '/api/admin/inspections/automation', token


def publish(endpoint, token, job_id):
    with requests.Session() as session:
        session.trust_env = False
        with session.post(endpoint, headers={'Authorization': 'Bearer ' + token}, json={'id': job_id},
                          timeout=(10, 65), allow_redirects=False) as response:
            if response.status_code != 200:
                raise RuntimeError('publication_failed')
            state = response.json().get('status')
            if state not in ('published', 'needs_attention', 'skipped'):
                raise RuntimeError('publication_failed')
            return state


def run_batch(db, client, limit, since, endpoint, token, worker=run_once, publisher=publish):
    client.settings.check()
    db.rpc('inspection_auto_enqueue', {'p_since': since, 'p_limit': limit}).execute()
    processed = 0
    for _ in range(limit):
        if not worker(db, client):
            break
        processed += 1
    # Retry publication transport only, never repeat a completed/failed AI request.
    jobs = db.table('sanction_inspections').select('id').eq('status', 'needs_review').eq('automation_status', 'pending').order('updated_at').limit(limit).execute().data
    totals = {'processed': processed, 'published': 0, 'needs_attention': 0, 'skipped': 0, 'publication_errors': 0}
    for job in jobs:
        try:
            totals[publisher(endpoint, token, job['id'])] += 1
        except Exception:
            totals['publication_errors'] += 1
    return totals


def main():
    load_env()
    try:
        limit, since, endpoint, token = config()
        if not get_supabase_service_role_key():
            raise ValueError('not_configured')
        totals = run_batch(get_supabase_client(), InspectionClient(Settings.from_env()), limit, since, endpoint, token)
        print(totals)
        if totals['publication_errors']:
            raise SystemExit(1)
    except Exception:
        print('sanction_automation_failed')
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
