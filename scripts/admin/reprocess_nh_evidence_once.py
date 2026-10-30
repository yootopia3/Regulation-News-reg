import json
from datetime import datetime, timezone
from uuid import uuid4
from src.db.client import get_supabase_client
from src.services.sanction_inspections.client import InspectionClient, Settings
from src.services.sanction_inspections.single_review import review_one
from src.services.sanction_inspections.models import InspectionError

TARGETS = [{"article_id":"bd496848-06ef-40be-a22a-291873527a7a","agency":"FSS_MGMT_NOTICE","id":"2d183cc0-68fb-43f7-87a9-73a25ced4dde","review_revision":5},{"article_id":"d12befd7-25cb-4eb6-a949-81d16e263495","agency":"FSS_SANCTION","id":"45929c96-126b-4058-8940-cbd1df8ba1d5","review_revision":5}]
MASTER = {"id":"49f0aaa3-12bd-400a-89d3-107e45697c72","revision":1,"fingerprint":"f63f6e8dd3d4f4ab5282f718de5caaae081ef650adcfb4961bebeaebca6b224f"}
VERSIONS = {MASTER['id']: MASTER['revision']}

def main():
    db = get_supabase_client()
    client = InspectionClient(Settings.from_env())
    client.settings.check()
    active = db.table('inspection_duty_masters').select('id,revision,fingerprint').eq('active', True).limit(2).execute().data
    if active != [MASTER]:
        raise RuntimeError('documents_changed')
    if db.table('sanction_inspections').select('id').in_('status', ['queued','processing']).limit(1).execute().data:
        raise RuntimeError('queue_not_empty')
    # Verify both exact failed jobs before touching either. No private payload output.
    for target in TARGETS:
        article = db.table('articles').select('title,agency,category,created_at').eq('id',target['article_id']).single().execute().data
        if article['title'] != '농협은행주식회사' or article['agency'] != target['agency'] or article['category'] != 'sanction_notice':
            raise RuntimeError('target_changed')
        job = db.table('sanction_inspections').select('id,article_id,status,error_code,automation_status,review_revision,versions,result,review_draft').eq('id',target['id']).single().execute().data
        expected = dict(target)
        expected.pop('agency')
        expected.update(status='failed', error_code='invalid_public_evidence', automation_status='needs_attention', versions=VERSIONS, result=None, review_draft=None)
        if job != expected:
            raise RuntimeError('target_changed')
        if db.table('sanction_publications').select('inspection_id').eq('inspection_id',target['id']).eq('status','published').limit(1).execute().data:
            raise RuntimeError('already_published')
    failures = 0
    for target in TARGETS:
        if db.rpc('inspection_versions',{}).execute().data != VERSIONS:
            raise RuntimeError('documents_changed')
        if db.table('sanction_inspections').select('id').in_('status',['queued','processing']).limit(1).execute().data:
            raise RuntimeError('queue_not_empty')
        # CAS preserves any intervening administrator edit or completed result.
        changed = (db.table('sanction_inspections').update({
            'status':'queued','request_id':str(uuid4()),'error_code':None,
            'lease_token':None,'lease_until':None,'updated_at':datetime.now(timezone.utc).isoformat()
        }).eq('id',target['id']).eq('article_id',target['article_id'])
          .eq('status','failed').eq('error_code','invalid_public_evidence')
          .eq('automation_status','needs_attention').eq('review_revision',target['review_revision'])
          .eq('versions',json.dumps(VERSIONS)).is_('result','null').is_('review_draft','null').execute().data)
        if len(changed) != 1:
            raise RuntimeError('target_changed')
        # Hold before any AI work, so even worker/output failures cannot leave
        # a successful draft eligible for the next automatic publication batch.
        held = (db.table('sanction_inspections').update({'automation_status':'needs_attention'})
                .eq('id',target['id']).eq('status','queued').eq('automation_status','pending')
                .eq('request_id',changed[0]['request_id'])
                .eq('review_revision',changed[0]['review_revision']).execute().data)
        if len(held) != 1:
            raise RuntimeError('review_hold_failed')
        try:
            review_one(db,client,target['article_id'],MASTER['fingerprint'])
        except InspectionError:
            job = db.table('sanction_inspections').select('status,error_code,automation_status,review_revision').eq('id',target['id']).single().execute().data
            if job['status'] == 'needs_review' and job['automation_status'] == 'pending':
                db.rpc('inspection_auto_attention',{'p_id':target['id'],'p_revision':job['review_revision']}).execute()
                job['automation_status'] = 'needs_attention'
            # Fixed safe status only. Do not print provider errors or model output.
            print('REPROCESS_RESULT',json.dumps({'agency':target['agency'],'status':job['status'],'error_code':job['error_code'],'automation_status':job['automation_status']}))
            failures += 1
            if job['status'] in ('queued','processing'):
                raise RuntimeError('target_not_finished')
            continue
        job = db.table('sanction_inspections').select('status,error_code,automation_status,result,review_revision').eq('id',target['id']).single().execute().data
        db.rpc('inspection_auto_attention',{'p_id':target['id'],'p_revision':job['review_revision']}).execute()
        held = db.table('sanction_inspections').select('status,automation_status,review_revision').eq('id',target['id']).single().execute().data
        if held != {'status':'needs_review','automation_status':'needs_attention','review_revision':job['review_revision']}:
            raise RuntimeError('review_hold_failed')
        print('REPROCESS_RESULT',json.dumps({'agency':target['agency'],'error_code':job['error_code'],**held}))
        # Public PDF-derived findings only, for source relevance review before publication.
        print('PUBLIC_FINDINGS_REVIEW',json.dumps({'agency':target['agency'],'findings':job['result']['findings']},ensure_ascii=False))
    if failures:
        raise RuntimeError('target_review_required')

try:
    main()
except Exception:
    raise SystemExit('targeted_reprocessing_incomplete') from None
