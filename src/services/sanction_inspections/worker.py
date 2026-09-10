"""Dedicated worker: never run inside the public collector workflow."""
import argparse
import hashlib
import sys
import time

from src.config.settings import load_env, get_supabase_service_role_key
from src.db.client import get_supabase_client
from src.services.internal_documents.worker import parse_isolated
from .client import InspectionClient, Settings
from .download import download_pdf
from .engine import analyze
from .models import InspectionError, Page, Unit


def load_units(db, versions):
    if db.rpc('inspection_versions', {}).execute().data != versions:
        raise InspectionError('documents_changed')
    units = []
    for document_id, revision in versions.items():
        for offset in range(0, 2000, 1000):
            rows = db.table('internal_document_units').select('article_key,department,body,reviewed').eq('document_id', document_id).order('article_key').range(offset, offset+999).execute().data
            for row in rows:
                if row['reviewed'] is not True:
                    raise InspectionError('documents_changed')
                units.append(Unit(document_id=document_id, revision=revision, active=True, **row))
            if len(rows) < 1000:
                break
        else:
            raise InspectionError('document_limit')
    if db.rpc('inspection_versions', {}).execute().data != versions:
        raise InspectionError('documents_changed')
    return units


def run_once(db, client, downloader=download_pdf, parser=parse_isolated):
    client.settings.check()
    job = db.rpc('inspection_claim', {}).execute().data
    if not job:
        return False
    result, error = None, None
    try:
        article = db.table('articles').select('agency,category,analysis_result').eq('id', job['article_id']).single().execute().data
        if article['category'] != 'sanction_notice' or article['agency'] not in ('FSS_SANCTION', 'FSS_MGMT_NOTICE'):
            raise InspectionError('invalid_article')
        metadata = article.get('analysis_result') or {}
        url = metadata.get('pdf_url') if isinstance(metadata, dict) else None
        if not url:
            raise InspectionError('pdf_missing')
        data = downloader(url)
        parsed = parser(data, module='src.services.sanction_inspections.pdf_parser', suffix='.pdf')
        if parsed.get('error'):
            raise InspectionError(parsed['error'])
        units = load_units(db, job['versions'])
        result = analyze([Page(**page) for page in parsed['pages']], units, client)
        result['pdf_sha256'] = hashlib.sha256(data).hexdigest()
    except InspectionError as exc:
        error = str(exc)
    except Exception:
        error = 'inspection_failed'
    db.rpc('inspection_finish', {'p_id': job['id'], 'p_token': job['lease_token'], 'p_result': result, 'p_error': error}).execute()
    return True


def main():
    argument_parser = argparse.ArgumentParser(description='Private sanction inspection worker')
    argument_parser.add_argument('--once', action='store_true')
    args = argument_parser.parse_args()
    load_env()
    settings = Settings.from_env()
    try:
        settings.check()
        if not get_supabase_service_role_key():
            raise InspectionError('not_configured')
    except InspectionError:
        raise SystemExit('inspection_worker_not_configured') from None
    db, client = get_supabase_client(), InspectionClient(settings)
    while True:
        try:
            worked = run_once(db, client)
        except Exception:
            print('inspection_worker_request_failed', file=sys.stderr)
            if args.once:
                raise SystemExit(1) from None
            worked = False
        if args.once:
            return
        if not worked:
            time.sleep(5)


if __name__ == '__main__':
    main()
