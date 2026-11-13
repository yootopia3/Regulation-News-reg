import json
import pytest
from ops.regmail.storage import Storage,BUCKET,MAX_ATTACHMENTS

@pytest.mark.parametrize('limit',[None,MAX_ATTACHMENTS,MAX_ATTACHMENTS+1])
def test_private_bucket_supports_attachment_budget(monkeypatch,limit):
    store=Storage('https://'+'a'*20+'.supabase.co','test')
    value=dict(id=BUCKET,public=False,file_size_limit=limit)
    monkeypatch.setattr(store,'request',lambda *a,**k:json.dumps(value).encode())
    store.ensure_private()

@pytest.mark.parametrize('public,limit,code',[
    (True,MAX_ATTACHMENTS,'storage_not_private'),
    (False,24_000_000,'storage_size_limit_too_small'),
    (False,str(MAX_ATTACHMENTS),'storage_size_limit_too_small')])
def test_unsuitable_bucket_stops_before_delivery(monkeypatch,public,limit,code):
    store=Storage('https://'+'a'*20+'.supabase.co','test')
    value=dict(id=BUCKET,public=public,file_size_limit=limit)
    monkeypatch.setattr(store,'request',lambda *a,**k:json.dumps(value).encode())
    with pytest.raises(Exception) as error:store.ensure_private()
    assert error.value.code==code

def test_head_reads_bypass_cached_urls(monkeypatch):
    store=Storage('https://'+'a'*20+'.supabase.co','test')
    calls=[]
    monkeypatch.setattr(store,'request',lambda method,path,**kwargs:calls.append((path,kwargs)))
    store.get('head.json');store.get('head.json')
    assert calls[0][0]!=calls[1][0]
    assert all(path.startswith('object/regulatory-delta-mail/head.json?') for path,_ in calls)
    assert all(value['extra']['Cache-Control']=='no-cache' for _,value in calls)

def test_upload_retries_verification_without_rewriting(monkeypatch):
    store=Storage('https://'+'a'*20+'.supabase.co','test');writes=[]
    monkeypatch.setattr(store,'request',lambda *a,**k:writes.append(a))
    answers=iter([b'old',b'correct'])
    monkeypatch.setattr(store,'get',lambda key:next(answers))
    monkeypatch.setattr('ops.regmail.storage.time.sleep',lambda seconds:None)
    store.put('head.json',b'correct',overwrite=True)
    assert len(writes)==1

def test_unverified_upload_stops_without_overwrite_retry(monkeypatch):
    store=Storage('https://'+'a'*20+'.supabase.co','test');writes=[]
    monkeypatch.setattr(store,'request',lambda *a,**k:writes.append(a))
    monkeypatch.setattr(store,'get',lambda key:b'corrupt')
    monkeypatch.setattr('ops.regmail.storage.time.sleep',lambda seconds:None)
    with pytest.raises(Exception) as error:store.put('head.json',b'correct')
    assert error.value.code=='storage_write_unverified' and len(writes)==1
