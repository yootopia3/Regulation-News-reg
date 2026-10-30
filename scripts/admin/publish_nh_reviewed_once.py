import json
from src.db.client import get_supabase_client
from src.services.sanction_inspections.batch import config
import requests
TARGETS=[{"article_id":"bd496848-06ef-40be-a22a-291873527a7a","id":"2d183cc0-68fb-43f7-87a9-73a25ced4dde","agency":"FSS_MGMT_NOTICE","review_revision":8},{"article_id":"d12befd7-25cb-4eb6-a949-81d16e263495","id":"45929c96-126b-4058-8940-cbd1df8ba1d5","agency":"FSS_SANCTION","review_revision":8}]
MASTER={"id":"49f0aaa3-12bd-400a-89d3-107e45697c72","revision":1,"fingerprint":"f63f6e8dd3d4f4ab5282f718de5caaae081ef650adcfb4961bebeaebca6b224f"}
VERSIONS={MASTER['id']:MASTER['revision']}
def publish(endpoint,token,job_id):
    with requests.Session() as session:
        session.trust_env=False
        with session.post(endpoint,headers={'Authorization':'Bearer '+token},json={'id':job_id},timeout=(10,65),allow_redirects=False) as response:
            code='unclassified'
            try:
                error=response.json().get('error')
                if error in {'unauthorized','disabled','request_failed','review_conflict','invalid_request','not_found'}:
                    code=error
            except Exception:
                pass
            print('PUBLICATION_HTTP',json.dumps({'status':response.status_code,'error':code}),flush=True)
            if response.status_code!=200:
                raise RuntimeError('publication_failed')
            state=response.json().get('status')
            if state not in ('published','needs_attention','skipped'):
                raise RuntimeError('publication_failed')
            return state

def main():
    db=get_supabase_client()
    _,_,endpoint,token=config()
    if endpoint != 'https://regulation-news-reg-fiu7.vercel.app/api/admin/inspections/automation':
        raise RuntimeError('unexpected_endpoint')
    if db.rpc('inspection_versions',{}).execute().data != VERSIONS:
        raise RuntimeError('documents_changed')
    for target in TARGETS:
        job=db.table('sanction_inspections').select('id,article_id,status,automation_status,review_revision,versions,result,review_draft').eq('id',target['id']).single().execute().data
        if (job['article_id']!=target['article_id'] or job['status']!='needs_review'
            or job['automation_status']!='needs_attention' or job['review_revision']!=8
            or job['versions']!=VERSIONS or job['review_draft'] is not None
            or job['result'].get('master_fingerprint')!=MASTER['fingerprint']
            or job['result'].get('prompt_version')!='duty-master-v5'):
            raise RuntimeError('reviewed_draft_changed')
        if db.table('sanction_publications').select('inspection_id').eq('inspection_id',target['id']).eq('status','published').limit(1).execute().data:
            raise RuntimeError('already_published')
    print('PUBLICATION_PREFLIGHT_PASSED',flush=True)
    failures=0
    for target in TARGETS:
        changed=(db.table('sanction_inspections').update({'automation_status':'pending'})
            .eq('id',target['id']).eq('article_id',target['article_id'])
            .eq('status','needs_review').eq('automation_status','needs_attention')
            .eq('review_revision',8).eq('versions',json.dumps(VERSIONS))
            .is_('review_draft','null').execute().data)
        print('PUBLICATION_CAS_ROWS',len(changed),flush=True)
        if len(changed)!=1:
            raise RuntimeError('reviewed_draft_changed')
        try:
            state=publish(endpoint,token,target['id'])
        except Exception as exc:
            print('PUBLICATION_TRANSPORT_ERROR',type(exc).__name__,flush=True)
            db.rpc('inspection_auto_attention',{'p_id':target['id'],'p_revision':8}).execute()
            raise RuntimeError('publication_failed') from None
        job=db.table('sanction_inspections').select('status,error_code,automation_status,review_revision').eq('id',target['id']).single().execute().data
        rows=db.table('sanction_publications').select('status,publication_source,published_at,revision').eq('inspection_id',target['id']).limit(1).execute().data
        print('PUBLICATION_RESULT',json.dumps({'agency':target['agency'],'state':state,'job':job,'publication':rows}),flush=True)
        if state!='published' or job['automation_status']!='published' or len(rows)!=1 or rows[0]['status']!='published':
            failures+=1
    if failures:
        raise RuntimeError('publication_review_required')
try:
    main()
except Exception as exc:
    print('PUBLICATION_FAILURE_TYPE',type(exc).__name__,str(getattr(exc,'code',''))[:10],flush=True)
    raise SystemExit('reviewed_publication_incomplete') from None
