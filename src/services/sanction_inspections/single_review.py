"""Manual one-job verification, without enqueueing or publishing other articles."""
import os
import re
from uuid import UUID

from src.config.settings import get_supabase_service_role_key, load_env
from src.db.client import get_supabase_client
from .client import InspectionClient, Settings
from .models import InspectionError
from .worker import run_once


def review_one(db, client, article_id, fingerprint, worker=run_once):
    article_id = str(UUID(article_id))
    if not re.fullmatch(r'[0-9a-f]{64}', fingerprint):
        raise InspectionError('invalid_duty_master')
    client.settings.check()
    masters = db.table('inspection_duty_masters').select('id,revision,fingerprint').eq('active', True).limit(2).execute().data
    if len(masters) != 1 or masters[0]['fingerprint'] != fingerprint:
        raise InspectionError('documents_changed')
    versions = {masters[0]['id']: masters[0]['revision']}
    jobs = db.table('sanction_inspections').select('id,article_id,status,versions').in_('status', ['queued', 'processing']).limit(2).execute().data
    if len(jobs) != 1 or jobs[0]['article_id'] != article_id or jobs[0]['status'] != 'queued' or jobs[0]['versions'] != versions:
        raise InspectionError('single_queue_required')
    target = jobs[0]

    class ScopedDB:
        def table(self, name):
            return db.table(name)

        def rpc(self, name, params):
            if name == 'inspection_claim':
                return db.rpc('inspection_claim_single', {'p_id': target['id'],
                    'p_article': article_id, 'p_versions': versions})
            return db.rpc(name, params)

    if not worker(ScopedDB(), client):
        raise InspectionError('single_job_not_processed')
    job = db.table('sanction_inspections').select('status,versions,result').eq('id', target['id']).single().execute().data
    result = job.get('result') or {}
    if job['status'] != 'needs_review' or job['versions'] != versions or result.get('analysis_basis') != 'duty_master' or result.get('master_fingerprint') != fingerprint:
        raise InspectionError('single_review_failed')
    return {'processed': 1, 'status': 'needs_review', 'published': 0}


def main():
    load_env()
    try:
        if not get_supabase_service_role_key():
            raise InspectionError('not_configured')
        result = review_one(get_supabase_client(), InspectionClient(Settings.from_env()),
                            os.environ['TARGET_ARTICLE_ID'], os.environ['EXPECTED_MASTER_FINGERPRINT'])
        print(result)
    except Exception:
        raise SystemExit('single_review_failed') from None


if __name__ == '__main__':
    main()
