import base64,copy,json,uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from ops.regmail.delivery import Manager,c,export,metadata,write,guard,RECIPIENT,SENDER

PROJECT='a'*20
def value(title):
    return c.envelope(dict(article=dict(id=str(uuid.uuid4()),title=title,agency='FSC',category='press_release',
        created_at='2026-11-11T00:00:00Z',published_at='2026-11-11T00:00:00Z',published_at_source='source',
        link='https://www.fsc.go.kr/test',content='공개 본문'),
        original=dict(source_url='https://www.fsc.go.kr/test',tree=[dict(tag='p',children=['공개 본문'])],body_status='available',files=[]),publication=None))
def proof(subject,attachments):
    return dict(status='sent',provider_labels=['SENT'],message_id=uuid.uuid4().hex,
        to=RECIPIENT,**{'from':SENDER},subject=subject,
        sent_headers_and_attachment_sizes_verified=True,transport_checksum_verified=True,
        attachments=[{k:a[k] for k in ('filename','bytes','sha256')} for a in attachments],sent_at_kst='2026-11-11T18:00:00+09:00')

@pytest.fixture
def seeded(tmp_path):
    old=value('행내 기존자료');seed=value('직전에 보낸 신규자료')
    bank=dict(format='regulation-receipt-v1',source_project=PROJECT,created_at='2026-11-11T00:00:00Z',
        records={old['article']['id']:c.digest(old)},files={})
    bank_path=tmp_path/'bank.json';write(bank_path,bank)
    result=export(PROJECT,[old,seed],{},bank,tmp_path/'seed')
    bundle=result['files'][0];sent=proof('이미 보낸 파일',[metadata(bundle)])
    proof_path=tmp_path/'sent.json';write(proof_path,sent)
    snapshot=tmp_path/'snapshot.jsonl';snapshot.write_bytes(b''.join(c.encoded(v)+b'\n' for v in [old,seed]))
    manager=Manager(tmp_path/'state',tmp_path/'out')
    manager.initialize(bank_path,bundle,proof_path,snapshot)
    return manager,[old,seed],bank

def supplier(values):return lambda baseline:(PROJECT,copy.deepcopy(values),{},[])

def test_seed_separates_bank_application_and_delivered_state(seeded):
    manager,values,bank=seeded;s=manager.load()
    assert s['bank_confirmed']==bank and len(s['delivered']['records'])==2
    assert s['deliveries'][0]['bank_applied'] is False and s['pending'] is None

def test_unchanged_source_creates_no_email_and_no_data_folder(seeded):
    manager,values,bank=seeded
    assert manager.prepare(supplier(values))['status']=='no_changes'
    assert not manager.output.exists()
    assert manager.load()['bank_confirmed']==bank

def test_check_only_does_not_create_delivery_or_advance_state(seeded):
    manager,values,_=seeded;before=manager.path.read_bytes();values.append(value('새로운 자료'))
    result=manager.prepare(supplier(values),check_only=True)
    assert result['added']==1 and result['updated']==0
    assert manager.path.read_bytes()==before and not manager.output.exists()

def test_new_and_modified_after_last_sent_are_the_only_records(seeded):
    manager,values,_=seeded;values[1]['article']['title']='수정된 제목';values.append(value('새로운 자료'))
    result=manager.prepare(supplier(values));run=result['run']
    assert run['counts']==dict(added=1,updated=1,changed=2)
    ids={r['id'] for p in run['packets'] for r in p['manifest']['records']}
    assert ids=={values[1]['article']['id'],values[2]['article']['id']}
    assert len(manager.load()['delivered']['records'])==2
    assert '이전 메일의 모든 자료' in run['packets'][0]['body_html']

@pytest.mark.parametrize('bad',['recipient','sender','status','label','name','size','hash','unverified'])
def test_failed_or_mismatching_send_never_advances_state(seeded,bad):
    manager,values,_=seeded;values.append(value('새로운 자료'))
    p=manager.prepare(supplier(values))['run']['packets'][0]
    sent=proof(p['subject'],p['attachments']);before=manager.path.read_bytes()
    if bad=='recipient':sent['to']='someone@example.com'
    if bad=='sender':sent['from']='someone@example.com'
    if bad=='status':sent['status']='failed'
    if bad=='label':sent['provider_labels']=['DRAFT']
    if bad=='name':sent['attachments'][0]['filename']='different.regdata'
    if bad=='size':sent['attachments'][0]['bytes']+=1
    if bad=='hash':sent['attachments'][0]['sha256']='0'*64
    if bad=='unverified':sent['sent_headers_and_attachment_sizes_verified']=False
    with pytest.raises(Exception):manager.confirm(p['package_id'],sent)
    assert manager.path.read_bytes()==before

def test_restart_resumes_pending_before_querying_new_source(seeded):
    manager,values,_=seeded;values.append(value('새로운 자료'))
    first=manager.prepare(supplier(values))['run']
    restarted=Manager(manager.root,manager.output)
    def forbidden(_):raise AssertionError('Must reconcile pending email first')
    result=restarted.prepare(forbidden)
    assert result['status']=='pending' and result['run']==first

def test_partial_success_order_and_idempotent_confirmation(seeded):
    manager,values,bank=seeded;values.extend([value('신규1'),value('신규2')])
    packets=manager.prepare(supplier(values),max_records=1)['run']['packets'];assert len(packets)==2
    first,second=packets;second_proof=proof(second['subject'],second['attachments'])
    before=manager.path.read_bytes()
    with pytest.raises(Exception):manager.confirm(second['package_id'],second_proof)
    assert manager.path.read_bytes()==before
    first_proof=proof(first['subject'],first['attachments'])
    assert manager.confirm(first['package_id'],first_proof)['run_complete'] is False
    mid=manager.load();assert len(mid['delivered']['records'])==3 and mid['pending'] is not None
    assert manager.confirm(first['package_id'],first_proof)['status']=='already_recorded'
    restarted=Manager(manager.root,manager.output)
    assert restarted.confirm(second['package_id'],second_proof)['run_complete'] is True
    done=restarted.load();assert len(done['delivered']['records'])==4 and done['bank_confirmed']==bank
    assert done['pending'] is None and restarted.prepare(supplier(values))['status']=='no_changes'

def test_changed_attachment_is_not_sent_or_recorded(seeded):
    manager,values,_=seeded;values.append(value('신규'))
    p=manager.prepare(supplier(values))['run']['packets'][0];before=manager.path.read_bytes()
    path=Path(p['attachments'][0]['path']);path.write_bytes(path.read_bytes()+b'!')
    with pytest.raises(Exception):manager.chunk(p['package_id'],0,0,262143)
    with pytest.raises(Exception):manager.confirm(p['package_id'],proof(p['subject'],p['attachments']))
    assert manager.path.read_bytes()==before

def test_parallel_attachment_reads_are_stable(seeded):
    manager,values,_=seeded;values.append(value('신규'))
    p=manager.prepare(supplier(values))['run']['packets'][0]
    with ThreadPoolExecutor(max_workers=4) as pool:
        parts=list(pool.map(lambda _:manager.chunk(p['package_id'],0,0,262143),range(8)))
    assert all(x==parts[0] for x in parts)
    raw=parts[0]['base64_url_content'];actual=base64.urlsafe_b64decode(raw+'='*((-len(raw))%4))
    assert actual==Path(p['attachments'][0]['path']).read_bytes()

def test_large_single_record_stops_without_advancing(seeded):
    manager,values,_=seeded;values.append(value('신규'));before=manager.path.read_bytes()
    with pytest.raises(Exception):manager.prepare(supplier(values),max_bytes=128)
    assert manager.path.read_bytes()==before

def test_source_failure_does_not_advance_or_create_pending(seeded):
    manager,_,_=seeded;before=manager.path.read_bytes()
    def fail(_):raise RuntimeError('source unavailable')
    with pytest.raises(RuntimeError):manager.prepare(fail)
    assert manager.path.read_bytes()==before


def test_send_attempt_survives_restart_and_blocks_unknown_retry(seeded):
    manager,values,bank=seeded;values.append(value('신규'))
    packet=manager.prepare(supplier(values))['run']['packets'][0]
    delivered=manager.load()['delivered']
    started=manager.begin_send(packet['package_id'])
    assert started['attempt']['status']=='outcome_unknown'
    restarted=Manager(manager.root,manager.output)
    s=restarted.load();assert s['delivered']==delivered and s['bank_confirmed']==bank
    assert s['pending']['packets'][0]['send_attempt']==started['attempt']
    before=restarted.path.read_bytes()
    with pytest.raises(Exception):restarted.begin_send(packet['package_id'])
    assert restarted.path.read_bytes()==before
    assert restarted.confirm(packet['package_id'],proof(packet['subject'],packet['attachments']))['run_complete'] is True
    assert restarted.load()['guards'][values[-1]['article']['id']]['sha256']==c.digest(values[-1])


def test_send_attempt_checks_order_and_attachment_integrity(seeded):
    manager,values,_=seeded;values.extend([value('신규1'),value('신규2')])
    packets=manager.prepare(supplier(values),max_records=1)['run']['packets'];before=manager.path.read_bytes()
    with pytest.raises(Exception):manager.begin_send(packets[1]['package_id'])
    assert manager.path.read_bytes()==before
    path=Path(packets[0]['attachments'][0]['path']);path.write_bytes(path.read_bytes()+b'!')
    with pytest.raises(Exception):manager.begin_send(packets[0]['package_id'])
    assert manager.path.read_bytes()==before


@pytest.mark.parametrize('change',['report_removal','report_withdrawn','report_identity','body_removed','body_unavailable','inspection_reuse','guard_missing'])
def test_unimportable_source_change_does_not_poison_delivery_chain(seeded,change):
    manager,values,_=seeded
    # A compact guard is seeded as if this publication had already been delivered.
    state=manager.load();key=values[1]['article']['id'];old_pub=dict(inspection_id=str(uuid.uuid4()),status='published')
    if change in ('report_removal','report_withdrawn','report_identity','inspection_reuse'):
        state['guards'][key]['publication']=old_pub
    if change=='guard_missing':del state['guards'][key]
    write(manager.path,state);before=manager.path.read_bytes()
    values[1]['article']['title']='수정된 제목'
    if change=='report_withdrawn':values[1]['publication']={**old_pub,'status':'withdrawn'}
    if change=='report_identity':values[1]['publication']={**old_pub,'inspection_id':str(uuid.uuid4())}
    if change=='body_removed':values[1]['original']=None
    if change=='body_unavailable':values[1]['original']['body_status']='unavailable'
    if change=='inspection_reuse':
        values[1]['publication']=old_pub
        other=value('다른 자료');other['publication']=old_pub;values.append(other)
    with pytest.raises(Exception) as failure:manager.prepare(supplier(values))
    expected=dict(report_removal='report_removal',report_withdrawn='report_removal',report_identity='report_identity_changed',
        body_removed='body_unavailable',body_unavailable='body_unavailable',inspection_reuse='report_identity_changed',guard_missing='delivery_guard_missing')
    assert failure.value.code==expected[change]
    assert manager.path.read_bytes()==before and not manager.output.exists()
