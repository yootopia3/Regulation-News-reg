import copy,hashlib,json,uuid
from datetime import datetime,timezone
from pathlib import Path
import pytest
from ops.regmail.delivery import c,guard,write,Manager,SENDER,RECIPIENT
from ops.regmail.runner import Hosted
from ops.regmail.gmail import build,verify
from ops.regmail.source import DeliveredCache

def envelope(title='public record'):
    return c.envelope(dict(article=dict(id=str(uuid.uuid4()),title=title,agency='FSC',category='press_release',created_at='2026-11-11T00:00:00Z',
        published_at='2026-11-11T00:00:00Z',published_at_source='source',link='https://www.fsc.go.kr/test',content='public source text'),
        original=dict(source_url='https://www.fsc.go.kr/test',tree=[dict(tag='p',children=['public source text'])],body_status='available',files=[]),publication=None))

class MemoryStore:
    def __init__(self,value):self.value=copy.deepcopy(value);self.objects={};self.saves=0;self.fail_at=None
    def load(self):return copy.deepcopy(self.value)
    def save(self,value):
        self.saves+=1
        if self.saves==self.fail_at:raise RuntimeError('remote unavailable')
        self.value=copy.deepcopy(value)
    def blob(self,data):
        key='blobs/'+hashlib.sha256(data).hexdigest();self.objects[key]=data;return key
    def get(self,key):return self.objects[key]

class Mail:
    def __init__(self,store):self.store=store;self.sent={};self.calls=0;self.timeout=False
    def find(self,p):return self.sent.get(p['package_id'])
    def send(self,p,wire):
        self.calls+=1
        remote=self.store.value['delivery']['pending']['packets'][0]
        assert remote['send_attempt']['status']=='outcome_unknown'
        proof=verify(wire,p,'verified-provider-id','2026-11-11T09:00:00+09:00')
        self.sent[p['package_id']]=proof
        if self.timeout:raise TimeoutError('ambiguous after SMTP DATA')

@pytest.fixture
def case(tmp_path):
    old=envelope();base=dict(format='regulation-receipt-v1',source_project='a'*20,created_at='2026-11-11T00:00:00Z',records={old['article']['id']:c.digest(old)},files={})
    state=dict(format='regmail-state-v1',sender=SENDER,recipient=RECIPIENT,bank_confirmed=copy.deepcopy(base),delivered=base,
        guards={old['article']['id']:guard(old)},deliveries=[],pending=None)
    cloud=dict(format='regmail-cloud-v1',delivery=state,values={old['article']['id']:old})
    store=MemoryStore(cloud);mail=Mail(store);values=[old,envelope('new')]
    supplier=lambda baseline:('a'*20,copy.deepcopy(values),{},[])
    return store,mail,values,supplier,tmp_path

def test_remote_attempt_before_send_and_bank_receipt_unchanged(case):
    store,mail,values,source,root=case;bank=copy.deepcopy(store.value['delivery']['bank_confirmed'])
    result=Hosted(store,mail,root,source).run('2026-11-11',test=True)
    assert result['packets_verified']==1 and result['added']==1 and mail.calls==1
    assert store.value['delivery']['bank_confirmed']==bank and len(store.value['delivery']['delivered']['records'])==2
    assert store.value['delivery']['pending'] is None
    assert all(v.get('bank_applied') is False for v in store.value['delivery']['deliveries'])

def test_migration_test_proof_survives_next_business_day(case):
    store,mail,values,source,root=case
    result=Hosted(store,mail,root,source).run('2026-11-11',test=True)
    Hosted(store,mail,root/'next',source).run('2026-11-12')
    assert store.value['last_result']['test'] is False
    assert store.value['migration_test']==result and result['packets_verified']==1

def test_remote_attempt_write_failure_sends_nothing(case):
    store,mail,values,source,root=case;store.fail_at=2
    with pytest.raises(RuntimeError):Hosted(store,mail,root,source).run('2026-11-11')
    assert mail.calls==0 and len(store.value['delivery']['delivered']['records'])==1

def test_timeout_recovers_from_sent_on_fresh_runner_without_duplicate(case):
    store,mail,values,source,root=case;mail.timeout=True
    with pytest.raises(TimeoutError):Hosted(store,mail,root/'first',source).run('2026-11-11')
    assert store.value['delivery']['pending']['packets'][0]['send_attempt']
    assert not Path(store.value['delivery']['pending']['packets'][0]['attachments'][0]['path']).is_absolute()
    mail.timeout=False
    result=Hosted(store,mail,root/'different-runner',source).run('2026-11-12')
    assert mail.calls==1 and result['packets_verified']==1 and store.value['delivery']['pending'] is None

def test_unknown_attempt_without_sent_is_not_retried(case):
    store,mail,values,source,root=case;mail.timeout=True
    with pytest.raises(TimeoutError):Hosted(store,mail,root/'first',source).run('2026-11-11')
    mail.sent.clear();mail.timeout=False
    with pytest.raises(Exception) as error:Hosted(store,mail,root/'second',source).run('2026-11-12')
    assert error.value.code=='send_outcome_unknown' and mail.calls==1

def test_no_change_and_accumulated_records_after_gap(case):
    store,mail,values,source,root=case;values.pop()
    assert Hosted(store,mail,root/'first',source).run('2026-11-13')['packets_verified']==0
    values.extend([envelope('weekend new'),envelope('holiday new')]);values[0]['article']['title']='updated during closure'
    result=Hosted(store,mail,root/'monday',source).run('2026-11-16')
    assert result['added']==2 and result['updated']==1 and mail.calls==1

def test_corrupt_restored_packet_never_sends(case):
    store,mail,values,source,root=case;store.fail_at=2
    with pytest.raises(RuntimeError):Hosted(store,mail,root/'first',source).run('2026-11-11')
    key=next(iter(store.objects));store.objects[key]+=b'!';store.fail_at=None
    with pytest.raises(Exception):Hosted(store,mail,root/'second',source)
    assert mail.calls==0

def test_cold_cache_keeps_only_files_proven_delivered(tmp_path,monkeypatch):
    from transfer_fetch import OriginalCache
    old=envelope();file=dict(status='available',sha256='b'*64,bytes=4,extension='pdf',name='old.pdf',kind='attachment',source_url='https://www.fsc.go.kr/old.pdf')
    old['original']['files']=[file];base=dict(files={'b'*64:dict(bytes=4,extension='pdf')})
    cache=DeliveredCache(tmp_path,base,{old['article']['id']:old})
    monkeypatch.setattr(OriginalCache,'download_locked',lambda *a,**kw:dict(status='unavailable',kind='attachment',name='old.pdf'))
    assert cache.download_locked(file['source_url'],'old.pdf','attachment')==file
    assert cache.download_locked('https://www.fsc.go.kr/new.pdf','new.pdf','attachment')['status']=='unavailable'
    assert cache.prior[old['article']['id']]==old['original'] and not cache.paths
