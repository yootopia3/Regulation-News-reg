import copy,hashlib,json,os,ssl,zipfile
from pathlib import Path
from email import policy
from email.parser import BytesParser
import pytest
from ops.regmail.delivery import c,metadata,package,write,Manager,SENDER,RECIPIENT
from ops.regmail import archives,gmail
from test_delivery import seeded,value,supplier,proof

def test_one_zip_contains_one_import_and_guides_are_in_mail(seeded):
    manager,values,_=seeded;values.extend([value('first'),value('second')])
    for v in values[2:]:v['article']['content']='공개 자료 '*20000
    source=lambda base:(base['source_project'],values,{},['<원문 확인 필요>'])
    packet=manager.prepare(source)['run']['packets'][0]
    assert len(packet['attachments'])==1
    attachment=Path(packet['attachments'][0]['path'])
    assert attachment.name.endswith('.regdata.zip')
    with zipfile.ZipFile(attachment) as z:
        assert len(z.namelist())==1 and z.namelist()[0].endswith('.regdata')
        assert z.getinfo(z.namelist()[0]).file_size>attachment.stat().st_size*10
    manifest,records,_=package(attachment,manager.load()['delivered'])
    assert {c.digest(v) for v in records}=={c.digest(v) for v in values[2:]}
    assert '&lt;원문 확인 필요&gt;' in packet['body_html'] and '모두 압축 풀기' in packet['body_html']
    mime=BytesParser(policy=policy.default).parsebytes(gmail.build(packet))
    plain=mime.get_body(preferencelist=('plain',)).get_content()
    assert '모두 압축 풀기' in plain and '.regdata 선택' in plain
    assert '<원문 확인 필요>' in plain and '이전 기준 파일:' in plain
    parts=list(mime.iter_attachments());assert len(parts)==1 and parts[0].get_content_type()=='application/zip'
    assert parts[0].get_payload(decode=True)==attachment.read_bytes()

def test_compressed_size_drives_splits_without_record_loss(tmp_path):
    values=[value('first'),value('second')]
    for v in values:v['article']['content']=os.urandom(12000).hex()
    base=dict(source_project='a'*20,records={},files={})
    full=archives.compressed_export('a'*20,values,{},base,tmp_path/'full',max_bytes=archives.MAX_ATTACHMENTS,max_records=c.MAX_RECORDS)
    assert len(full['files'])==1
    budget=int(full['files'][0].stat().st_size*.7)
    split=archives.compressed_export('a'*20,values,{},base,tmp_path/'split',max_bytes=budget,max_records=c.MAX_RECORDS)
    assert len(split['files'])==2
    found=[]
    for i,p in enumerate(split['files'],1):
        assert p.stat().st_size<=budget and f'_{i:03d}_' in p.name
        manifest,records,_=package(p,base);found.extend(records)
    assert {c.digest(v) for v in found}=={c.digest(v) for v in values}

def test_oversized_record_does_not_advance_state_or_leave_partial_archives(seeded):
    manager,values,_=seeded;values.append(value('incompressible'))
    values[-1]['article']['content']=os.urandom(6000).hex();before=manager.path.read_bytes()
    with pytest.raises(Exception) as failure:manager.prepare(supplier(values),max_bytes=1000)
    assert failure.value.code=='article_package_too_large'
    assert manager.path.read_bytes()==before and not list(manager.output.rglob('*.zip'))

@pytest.mark.parametrize('name',['../source.regdata','folder/source.regdata','folder\\source.regdata','x:source.regdata','source.exe'])
def test_archive_rejects_paths_and_wrong_types(tmp_path,name):
    path=tmp_path/'bad.zip'
    with zipfile.ZipFile(path,'w') as z:z.writestr(name,b'REGDATA1'+b'x'*20)
    with pytest.raises(Exception) as failure:
        with archives.package_stream(path) as stream:stream.read()
    assert failure.value.code=='invalid_mail_archive'

def test_archive_rejects_multiple_entries(tmp_path):
    path=tmp_path/'bad.zip'
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('a.regdata',b'REGDATA1'+b'x'*20);z.writestr('b.regdata',b'REGDATA1'+b'y'*20)
    with pytest.raises(Exception):
        with archives.package_stream(path) as stream:stream.read()

def test_legacy_raw_pending_packet_still_confirms_after_restart(seeded):
    manager,values,_=seeded;values.append(value('legacy pending'))
    packet=manager.prepare(supplier(values))['run']['packets'][0]
    zipped=Path(packet['attachments'][0]['path']);raw=zipped.with_suffix('')
    with zipfile.ZipFile(zipped) as z:raw.write_bytes(z.read(z.namelist()[0]))
    state=manager.load();state['pending']['packets'][0]['attachments']=[metadata(raw)];write(manager.path,state)
    restarted=Manager(manager.root,manager.output);packet=restarted.load()['pending']['packets'][0]
    restarted.begin_send(packet['package_id'])
    assert restarted.confirm(packet['package_id'],proof(packet['subject'],packet['attachments']))['run_complete']
    assert restarted.load()['delivered']['records'][values[-1]['article']['id']]==c.digest(values[-1])

def test_attachment_and_actual_mime_limits_are_separate(seeded,monkeypatch):
    manager,values,_=seeded;values.append(value('new'))
    packet=manager.prepare(supplier(values))['run']['packets'][0]
    raw_size=sum(a['bytes'] for a in packet['attachments'])
    monkeypatch.setattr(gmail,'MAX_ATTACHMENTS',raw_size-1)
    with pytest.raises(Exception) as e:gmail.build(packet)
    assert e.value.code=='mail_too_large'
    monkeypatch.setattr(gmail,'MAX_ATTACHMENTS',raw_size)
    wire=gmail.build(packet);assert len(wire)>raw_size
    monkeypatch.setattr(gmail,'MAX_MESSAGE',len(wire)-1)
    with pytest.raises(Exception) as e:gmail.build(packet)
    assert e.value.code=='mail_too_large'

def test_actual_mime_failure_precedes_pending_state(seeded,monkeypatch):
    manager,values,_=seeded;values.append(value('new'));before=manager.path.read_bytes()
    monkeypatch.setattr(gmail,'MAX_MESSAGE',100)
    with pytest.raises(Exception) as e:manager.prepare(supplier(values))
    assert e.value.code=='mail_too_large' and manager.path.read_bytes()==before

def test_smaller_advertised_smtp_size_rejected_before_data(monkeypatch):
    sent=[]
    class SMTP:
        esmtp_features={'size':'100'}
        def __init__(self,*a,**kw):pass
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def login(self,*a):pass
        def sendmail(self,*a):sent.append(a);return {}
    monkeypatch.setattr(gmail.smtplib,'SMTP_SSL',SMTP)
    mail=gmail.Gmail.__new__(gmail.Gmail);mail.context=ssl.create_default_context();mail.password='unused test value'
    with pytest.raises(Exception) as e:mail.send({},b'x'*101)
    assert e.value.code=='mail_too_large' and sent==[]
