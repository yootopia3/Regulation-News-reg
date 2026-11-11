"""Configure the existing cron service without changing its collector job."""
import copy,json,os,urllib.error,urllib.request
from .delivery import c
from .storage import NoRedirect,Storage

REPOSITORY='yootopia3/Regulation-News-reg'
BASE='https://api.github.com/repos/'+REPOSITORY+'/actions/workflows/'
SOURCE=BASE+'news_collector_v2_active.yml/dispatches'
TARGET=BASE+'regulatory_delta_mail.yml/dispatches'
SCHEDULE=dict(timezone='Asia/Seoul',expiresAt=0,hours=[9],minutes=[0],mdays=[-1],months=[-1],wdays=[1,2,3,4,5])
BODY=json.dumps(dict(ref='main',inputs=dict(mode='scheduled')),separators=(',',':'))

class Cron:
    def __init__(self):
        self.key=os.environ.get('REGMAIL_CRONJOB_API_KEY','')
        c.require(bool(self.key),'scheduler_credentials_missing',409)
    def call(self,path,method='GET',value=None):
        c.require(path=='/jobs' or (path.startswith('/jobs/') and path[6:].isdigit()),'scheduler_path_invalid')
        request=urllib.request.Request('https://api.cron-job.org'+path,method=method,
            data=None if value is None else c.encoded(value),
            headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'})
        try:
            with urllib.request.build_opener(NoRedirect()).open(request,timeout=40) as response:
                raw=response.read(2*1024*1024+1);c.require(len(raw)<=2*1024*1024,'scheduler_response_too_large')
                return json.loads(raw)
        except urllib.error.HTTPError as error:
            status=error.code;error.close();raise c.Problem('scheduler_http_'+str(status),502) from None

def specification(source):
    c.require(source['url']==SOURCE and source.get('requestMethod')==1 and source.get('enabled') is True,'collector_job_unavailable')
    original=source.get('extendedData',{}).get('headers',{})
    headers={k:v for k,v in original.items() if k.lower() in ('authorization','accept','content-type','x-github-api-version')}
    auth=[v for k,v in headers.items() if k.lower()=='authorization']
    c.require(len(auth)==1 and isinstance(auth[0],str) and auth[0].lower().startswith(('bearer ','token '))
        and len(auth[0])>20 and '*' not in auth[0],'collector_auth_unavailable')
    headers={k:v for k,v in headers.items() if k.lower()!='content-type'};headers['Content-Type']='application/json'
    return dict(title='Regulatory delta mail - 09:00 KST',url=TARGET,enabled=False,
        saveResponses=False,requestMethod=1,requestTimeout=30,redirectSuccess=False,
        schedule=copy.deepcopy(SCHEDULE),extendedData=dict(headers=headers,body=BODY),
        notification=dict(mode=0,onFailure=False,onSuccess=False,onDisable=False))

def check_job(job):
    c.require(job.get('url')==TARGET and job.get('requestMethod')==1 and job.get('schedule')==SCHEDULE,'scheduler_job_mismatch')
    c.require(json.loads(job.get('extendedData',{}).get('body','null'))==json.loads(BODY),'scheduler_job_mismatch')

def verify_dispatch(job):
    check_job(job)
    # Test the exact credentials retained by cron-job.org, not the operator's
    # different GitHub token. Auth mode queues a check and sends no email.
    headers=job['extendedData']['headers']
    request=urllib.request.Request(TARGET,method='POST',headers=headers,
        data=c.encoded(dict(ref='main',inputs=dict(mode='auth'))))
    try:
        with urllib.request.build_opener(NoRedirect()).open(request,timeout=40) as response:
            c.require(response.status==204,'scheduler_dispatch_unverified',502)
    except urllib.error.HTTPError as error:
        status=error.code;error.close();raise c.Problem('scheduler_dispatch_http_'+str(status),502) from None

def configure(cron,enable=False,cloud=None):
    listing=cron.call('/jobs');c.require(listing.get('someFailed') is False,'scheduler_list_incomplete')
    targets=[job for job in listing['jobs'] if job.get('url')==TARGET]
    c.require(len(targets)<=1,'scheduler_duplicate_jobs')
    if not targets:
        c.require(not enable,'scheduler_not_prepared')
        sources=[job for job in listing['jobs'] if job.get('url')==SOURCE and job.get('enabled') is True]
        c.require(bool(sources),'collector_job_unavailable')
        source=cron.call('/jobs/'+str(sources[0]['jobId']))['jobDetails']
        job=specification(source)
        # Only the new mail job is created; the collector is never mutated.
        result=cron.call('/jobs','PUT',dict(job=job));ident=result['jobId']
    else:ident=targets[0]['jobId']
    c.require(type(ident) is int and ident>0,'scheduler_job_invalid')
    job=cron.call('/jobs/'+str(ident))['jobDetails'];check_job(job)
    if not enable:verify_dispatch(job)
    if enable:
        result=(cloud or {}).get('migration_test') or (cloud or {}).get('last_result',{})
        c.require(os.environ.get('REGMAIL_ENABLED')=='true' and result.get('test') is True
            and result.get('packets_verified',0)>0 and result.get('code_sha')==os.environ.get('GITHUB_SHA')
            and cloud['delivery']['pending'] is None,'scheduler_test_required',409)
        cron.call('/jobs/'+str(ident),'PATCH',dict(job=dict(enabled=True)))
        job=cron.call('/jobs/'+str(ident))['jobDetails'];check_job(job)
        c.require(job.get('enabled') is True,'scheduler_enable_unverified')
    return dict(status='scheduler_ready',job_id=ident,enabled=job.get('enabled'),schedule='09:00 Asia/Seoul Monday-Friday')

def main(enable=False):
    c.require(os.environ.get('GITHUB_REPOSITORY')==REPOSITORY,'scheduler_repository_mismatch')
    cloud=None
    if enable:
        from .runner import validate
        cloud=Storage().load();validate(cloud)
    return configure(Cron(),enable,cloud)
