"""Run separately from news collection; no AI calls or content logging."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from src.config.settings import load_env, get_supabase_service_role_key
from src.db.client import get_supabase_client

BUCKET = 'internal-documents'
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def parse_isolated(data, module='src.services.internal_documents.parser', suffix='.hwp'):
    with tempfile.TemporaryDirectory(prefix='private-hwp-') as directory:
        source, target = Path(directory) / ('input' + suffix), Path(directory) / 'result.json'
        source.write_bytes(data)
        env = {key: value for key, value in os.environ.items() if key in ('SYSTEMROOT', 'WINDIR', 'PATH', 'TEMP', 'TMP', 'LANG', 'PYTHONPATH')}
        env['PYTHONPATH'] = str(PROJECT_ROOT) + (os.pathsep + env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
        try:
            completed = subprocess.run([sys.executable, '-m', module, str(source), str(target)], cwd=directory, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60, check=False)
        except subprocess.TimeoutExpired:
            return {'error': 'parser_timeout'}
        if completed.returncode or not target.exists() or target.stat().st_size > 32 * 1024 * 1024:
            return {'error': 'parser_failed'}
        return json.loads(target.read_text(encoding='utf-8'))


def run_once(db, parser=parse_isolated):
    job = db.rpc('internal_document_claim', {}).execute().data
    if not job:
        return False
    result = {'units': [], 'warnings': []}
    try:
        if job['kind'] == 'delete':
            db.storage.from_(BUCKET).remove([job['object_key']])
        else:
            data = db.storage.from_(BUCKET).download(job['object_key'])
            if len(data) > 2 * 1024 * 1024:
                result = {'error': 'document_limit'}
            elif hashlib.sha256(data).hexdigest() != job['sha256']:
                result = {'error': 'invalid_hwp'}
            else:
                result = parser(data)
    except Exception:
        result = {'error': 'worker_failed'}
    db.rpc('internal_document_finish', {'p_id': job['document_id'], 'p_token': job['lease_token'], 'p_units': result.get('units', []), 'p_warnings': result.get('warnings', []), 'p_error': result.get('error')}).execute()
    return True


def main():
    args = argparse.ArgumentParser(description='Private document worker (no AI)')
    args.add_argument('--once', action='store_true')
    options = args.parse_args()
    load_env()
    if os.environ.get('INTERNAL_DOCUMENTS_ENABLED') != 'true' or not get_supabase_service_role_key():
        raise SystemExit('Private document worker is disabled or not configured')
    db = get_supabase_client()
    while True:
        try:
            worked = run_once(db)
        except Exception:
            # A stale lease/provider error is retried by the queue, without dumping payloads.
            print('document_worker_request_failed', file=sys.stderr)
            worked = False
            if options.once:
                raise SystemExit(1)
        if options.once:
            return
        if not worked:
            time.sleep(5)


if __name__ == '__main__':
    main()
