import copy,json
import pytest
from ops.regmail.scheduler import SOURCE,TARGET,SCHEDULE,BODY,specification,configure

@pytest.fixture(autouse=True)
def disable_real_dispatch(monkeypatch):
    monkeypatch.setattr('ops.regmail.scheduler.verify_dispatch',lambda job:None)

@pytest.fixture
def source():
    return dict(jobId=7,url=SOURCE,enabled=True,requestMethod=1,schedule=dict(hours=[8,12,18]),
        extendedData=dict(headers={'Authorization':'Bearer '+'x'*32,'Content-Type':'application/json','Cookie':'unrelated'},body='{}'))

class Cron:
    def __init__(self,source):self.jobs={7:copy.deepcopy(source)};self.writes=[]
    def call(self,path,method='GET',value=None):
        if method=='GET':
            return dict(jobs=copy.deepcopy(list(self.jobs.values())),someFailed=False) if path=='/jobs' else dict(jobDetails=copy.deepcopy(self.jobs[int(path[6:])]))
        self.writes.append((path,method,copy.deepcopy(value)))
        if method=='PUT':self.jobs[8]=dict(jobId=8,**value['job']);return dict(jobId=8)
        ident=int(path[6:]);self.jobs[ident].update(value['job']);return {}

def test_prepare_creates_disabled_job_without_touching_collector(source):
    cron=Cron(source);result=configure(cron)
    assert result['enabled'] is False and cron.jobs[7]==source
    assert cron.jobs[8]['schedule']==SCHEDULE and json.loads(cron.jobs[8]['extendedData']['body'])==json.loads(BODY)
    assert 'Cookie' not in cron.jobs[8]['extendedData']['headers']
    assert cron.writes[0][0:2]==('/jobs','PUT') and len(cron.writes)==1
    configure(cron);assert len(cron.writes)==1

def test_refuses_unrelated_or_masked_auth(source):
    source['url']='https://example.com/';
    with pytest.raises(Exception):specification(source)
    source['url']=SOURCE;source['extendedData']['headers']['Authorization']='Bearer '+'*'*32
    with pytest.raises(Exception):specification(source)

def test_mismatching_existing_job_is_never_overwritten(source):
    cron=Cron(source);configure(cron);cron.jobs[8]['schedule']['hours']=[18]
    with pytest.raises(Exception):configure(cron)
    assert len(cron.writes)==1

def test_enable_requires_real_verified_test(source,monkeypatch):
    cron=Cron(source);configure(cron)
    monkeypatch.setenv('REGMAIL_ENABLED','true');monkeypatch.setenv('GITHUB_SHA','current')
    cloud=dict(last_result=dict(test=True,packets_verified=0,code_sha='current'),delivery=dict(pending=None))
    with pytest.raises(Exception):configure(cron,True,cloud)
    assert cron.jobs[8]['enabled'] is False
    cloud['last_result']['packets_verified']=1
    result=configure(cron,True,cloud)
    assert result['enabled'] is True and cron.jobs[7]==source

def test_invalid_scheduler_token_leaves_new_job_disabled(source,monkeypatch):
    cron=Cron(source)
    def rejected(job):raise RuntimeError('authorization rejected')
    monkeypatch.setattr('ops.regmail.scheduler.verify_dispatch',rejected)
    with pytest.raises(RuntimeError):configure(cron)
    assert cron.jobs[8]['enabled'] is False and cron.jobs[7]==source
