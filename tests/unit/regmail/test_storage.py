import json
import pytest
from ops.regmail.storage import Storage

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
