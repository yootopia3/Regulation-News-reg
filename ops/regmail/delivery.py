"""Delivery bookkeeping shared with the verified notebook export workflow."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager
import argparse, base64, copy, hashlib, html, json, os, struct, sys, uuid

REPO=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(REPO/'vibelabs/tools'),str(REPO/'vibelabs'),str(REPO)]
from application import transfer_contract as c
from application.original_contract import file_type
from transfer_export import receipt, internet_source, export

SENDER=os.environ.get('REGMAIL_SENDER','')
RECIPIENT=os.environ.get('REGMAIL_RECIPIENT','')
KST=timezone(timedelta(hours=9))
LIMIT=16_000_000
DEFAULT_OUTPUT=Path(os.environ.get('REGMAIL_RUNTIME',str(REPO/'.regmail-runtime')))/'out'
DEFAULT_STATE=DEFAULT_OUTPUT.parent/'delivery'
CONNECTION=REPO/'.env'

def now():return datetime.now(KST).isoformat()
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    part=path.with_name(path.name+'.tmp-'+uuid.uuid4().hex)
    try:
        with part.open('xb') as f:f.write(c.encoded(value));f.flush();os.fsync(f.fileno())
        os.replace(part,path)
    finally:part.unlink(missing_ok=True)

@contextmanager
def locked(root):
    root.mkdir(parents=True,exist_ok=True)
    with (root/'state.lock').open('a+b') as f:
        if f.tell()==0:f.write(b'0');f.flush()
        f.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:yield
        finally:
            f.seek(0)
            if os.name=='nt':msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(f.fileno(),fcntl.LOCK_UN)

def package(path,base):
    """Verify every byte with the deployed import contract, without DB writes."""
    path=Path(path);c.require(path.stat().st_size<=c.MAX_PACKAGE)
    values=[];needed={}
    with path.open('rb') as f:
        c.require(f.read(8)==c.MAGIC)
        size=f.read(4);c.require(len(size)==4)
        size=struct.unpack('>I',size)[0];c.require(0<size<=c.MAX_MANIFEST)
        raw=f.read(size);m=json.loads(raw);ident,encoded=c.manifest(m)
        c.require(raw==encoded and m['source_project']==base['source_project'])
        supplied={x['sha256']:{k:x[k] for k in ('bytes','extension')} for x in m['files']}
        for spec in m['records']:
            data=f.read(spec['bytes']);c.require(len(data)==spec['bytes'] and hashlib.sha256(data).hexdigest()==spec['sha256'])
            v=c.envelope(json.loads(data));c.require(c.encoded(v)==data and v['article']['id']==spec['id'])
            c.require(base['records'].get(spec['id'])==spec['base'],'delivery_base_mismatch',409)
            for item in (v['original'] or {}).get('files',[]):
                if item['status']!='available':continue
                meta={k:item[k] for k in ('bytes','extension')};digest=item['sha256']
                c.require(digest not in needed or needed[digest]==meta);needed[digest]=meta
                c.require((base['files'].get(digest) or supplied.get(digest))==meta,'transfer_missing_file',409)
            values.append(v)
        c.require(set(supplied)<=set(needed) and all(supplied[k]==needed[k] for k in supplied))
        for spec in m['files']:
            data=f.read(spec['bytes']);c.require(len(data)==spec['bytes'] and hashlib.sha256(data).hexdigest()==spec['sha256'])
            c.require(file_type(data,'file.'+spec['extension'])==spec['extension'])
        c.require(not f.read(1))
    return m,values,ident

def advance(base,m):
    value=copy.deepcopy(base)
    c.require(m['source_project']==value['source_project'])
    for r in m['records']:
        c.require(value['records'].get(r['id'])==r['base'],'delivery_base_mismatch',409)
        value['records'][r['id']]=r['sha256']
    for f in m['files']:
        meta={k:f[k] for k in ('bytes','extension')}
        c.require(f['sha256'] not in value['files'] or value['files'][f['sha256']]==meta)
        value['files'][f['sha256']]=meta
    value['created_at']=now();return value

def metadata(path):
    return dict(path=str(path),filename=path.name,bytes=path.stat().st_size,sha256=sha(path))

def guard(value):
    publication=value['publication']
    return dict(sha256=c.digest(value),body_available=bool(value['original'] and value['original']['body_status']=='available'),
        publication={k:publication[k] for k in ('inspection_id','status')} if publication else None)

def compatible(state,values):
    """Reject source changes the deployed importer's assess() cannot apply.

    Receipt hashes bind these compact guards to the actual delivered envelopes.
    This is not a check of edits made independently inside the bank.
    """
    baseline=state['delivered']['records'];guards=state['guards'];owners={}
    c.require(set(guards)==set(baseline) and all(guards[k]['sha256']==baseline[k] for k in baseline),'delivery_guard_missing',409)
    for ident,old in guards.items():
        pub=old['publication']
        if pub:
            c.require(pub['inspection_id'] not in owners or owners[pub['inspection_id']]==ident,'report_identity_changed',409)
            owners[pub['inspection_id']]=ident
    seen=set()
    for value in values:
        ident=value['article']['id'];c.require(ident not in seen,'duplicate_source_record',409);seen.add(ident)
        new=guard(value);old=guards.get(ident)
        if old and old['sha256']==new['sha256']:continue
        pub=new['publication'];old_pub=old['publication'] if old else None
        c.require(not old_pub or (pub and pub['status']=='published'),'report_removal',409)
        c.require(not pub or pub['status']=='published','report_removal',409)
        c.require(not(old_pub and pub) or old_pub['inspection_id']==pub['inspection_id'],'report_identity_changed',409)
        c.require(not old or not old['body_available'] or new['body_available'],'body_unavailable',409)
        if pub:
            c.require(pub['inspection_id'] not in owners or owners[pub['inspection_id']]==ident,'report_identity_changed',409)
            owners[pub['inspection_id']]=ident

def proof_matches(proof,subject,attachments,exact=True):
    c.require(proof.get('status')=='sent' and 'SENT' in proof.get('provider_labels',[]),'sent_not_verified',409)
    c.require(proof.get('to')==RECIPIENT and proof.get('from')==SENDER and proof.get('subject')==subject,'sent_address_mismatch',409)
    c.require(proof.get('sent_headers_and_attachment_sizes_verified') is True and proof.get('transport_checksum_verified') is True,'sent_not_verified',409)
    c.require(isinstance(proof.get('message_id'),str) and bool(proof['message_id']),'sent_not_verified',409)
    actual=proof.get('attachments',[])
    if exact:c.require(len(actual)==len(attachments),'sent_attachment_mismatch',409)
    for spec in attachments:
        found=[x for x in actual if x.get('filename')==spec['filename']]
        c.require(len(found)==1 and all(found[0].get(k)==spec[k] for k in ('bytes','sha256')),'sent_attachment_mismatch',409)

class Manager:
    def __init__(self,root=DEFAULT_STATE,output=DEFAULT_OUTPUT):
        self.root=Path(root);self.output=Path(output);self.path=self.root/'state.json'
    def load(self):
        s=json.loads(self.path.read_bytes());c.require(s['format']=='regmail-state-v1')
        c.require(s['sender']==SENDER and s['recipient']==RECIPIENT)
        return s
    def status(self):
        # State writes use atomic replacement, so a read-only status is coherent.
        s=self.load();return dict(bank_confirmed_records=len(s['bank_confirmed']['records']),
            delivered_records=len(s['delivered']['records']),delivered_files=len(s['delivered']['files']),
            last_delivery=s['deliveries'][-1] if s['deliveries'] else None,pending=s['pending'])
    def initialize(self,bank_path,bundle,proof_path,snapshot_path):
        with locked(self.root):
            c.require(not self.path.exists(),'already_initialized',409)
            bank=receipt(Path(bank_path));m,values,ident=package(bundle,bank)
            proof=json.loads(Path(proof_path).read_bytes());spec=metadata(Path(bundle))
            proof_matches(proof,proof['subject'],[spec],exact=False)
            delivered=advance(bank,m);guards={}
            with Path(snapshot_path).open('rb') as stream:
                for line in stream:
                    value=c.envelope(json.loads(line));key=value['article']['id']
                    c.require(key not in guards and c.digest(value)==delivered['records'].get(key),'delivery_guard_mismatch',409)
                    guards[key]=guard(value)
            c.require(set(guards)==set(delivered['records']),'delivery_guard_missing',409)
            s=dict(format='regmail-state-v1',sender=SENDER,recipient=RECIPIENT,
                bank_confirmed=bank,delivered=delivered,guards=guards,pending=None,
                deliveries=[dict(package_id=ident,filename=spec['filename'],sha256=spec['sha256'],
                    message_id=proof['message_id'],subject=proof['subject'],sent_at=proof.get('sent_at_kst'),bank_applied=False)])
            write(self.path,s)
            return dict(initialized=True,bank_confirmed_records=len(bank['records']),delivered_records=len(s['delivered']['records']))
    def prepare(self,supplier,check_only=False,max_bytes=LIMIT,max_records=c.MAX_RECORDS):
        with locked(self.root):
            s=self.load()
            if s['pending']:return dict(status='pending',run=s['pending'])
            base=s['delivered'];project,values,paths,warnings=supplier(copy.deepcopy(base))
            c.require(project==base['source_project'])
            compatible(s,values)
            expected={v['article']['id']:c.digest(v) for v in values if c.digest(v)!=base['records'].get(v['article']['id'])}
            counts=dict(added=sum(k not in base['records'] for k in expected),updated=sum(k in base['records'] for k in expected),changed=len(expected))
            if check_only:return dict(status='check_only',**counts,source_records=len(values),warnings=len(warnings))
            if not expected:
                s['last_checked_at']=now();write(self.path,s)
                return dict(status='no_changes',source_records=len(values),warnings=len(warnings))
            run_id=datetime.now(KST).strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]
            folder=self.output/(run_id+'_자동증분');c.require(not folder.exists())
            result=export(project,values,paths,base,folder,max_bytes=max_bytes,max_records=max_records)
            warning_file=folder/'원문확인_안내.txt'
            warning_file.write_text('\n'.join(warnings) if warnings else '이번 원문 확인에서 실패한 항목이 없습니다.',encoding='utf-8-sig')
            predecessor=s['deliveries'][-1]['filename'] if s['deliveries'] else '행내에서 적용을 확인한 기준자료'
            run=dict(id=run_id,created_at=now(),predecessor=predecessor,counts=counts,absent=result['absent'],packets=[])
            found={}
            for index,path in enumerate(result['files'],1):
                m,records,ident=package(path,base)
                for spec in m['records']:c.require(spec['id'] not in found);found[spec['id']]=spec['sha256']
                added=sum(r['base'] is None for r in m['records']);updated=len(records)-added
                subject=f'[규제정보 플랫폼][자동 {datetime.now(KST):%Y-%m-%d} {index:02d} {ident[:12]}] 신규{added}·수정{updated}'
                guide=folder/f'반입안내_{index:03d}.txt'
                guide.write_text(f'규제정보 플랫폼 자동 증분 반입\n\n파일: {path.name}\n신규{added}·수정{updated}건 / 새 파일{len(m["files"])}개\n'
                    f'이전 기준 파일: {predecessor}\n이전 메일의 모든 파일을 먼저 적용하고, 이번 메일도 번호 순서대로 적용해주세요.\n'
                    '관리자 설정 → 데이터 반입 → .regdata 선택 → 전송하고 검증 → 검토한 자료 적용 → 완료 확인 순서입니다.\n'
                    '메일 발송은 행내 반입 완료를 뜻하지 않습니다. 앞선 파일이 누락되거나 충돌이 나오면 강제 적용하지 말고 알려주세요.\n'
                    '변경 없는 자료와 기존 확보 파일은 재포함하지 않았습니다. 이미지 재배포는 필요하지 않습니다.\n'
                    'MAFRA·내부 문서·게시판·계정·접속키·비공개 분석은 제외합니다.\n'
                    '빠른 증분으로 인터넷 DB 변경과 미확보 원문을 확인합니다. 공식 사이트에서만 바뀐 과거 첨부는 전체 재확인이 필요합니다.\n'
                    '원문 확인 실패가 있으면 원문확인_안내.txt에 표시하며 기존 확보본을 유지합니다.\n'
                    f'SHA256: {sha(path)}\n',encoding='utf-8-sig')
                body=f'<p>규제정보 플랫폼 증분자료입니다.</p><p>신규 {added}건·수정 {updated}건, 새 첨부·이미지 {len(m["files"])}개를 담았습니다.</p>'
                body+=f'<p>이전 기준: {html.escape(predecessor)}<br>이전 메일의 모든 자료를 먼저 반입한 뒤 이번 파일을 적용해주세요.</p>'
                body+='<p>관리자 설정 → 데이터 반입 → 전송하고 검증 → 검토한 자료 적용 순서입니다. 완료 후 반입 기준파일을 보관해주세요. 이미지 재배포는 필요하지 않습니다.</p>'
                body+=f'<p>원문 확인 참고사항 {len(warnings)}개는 첨부 안내문에 적었습니다. 원문을 확보하지 못한 항목을 확보된 것으로 표시하지 않습니다.</p>'
                run['packets'].append(dict(package_id=ident,manifest=m,subject=subject,to=RECIPIENT,
                    from_address=SENDER,body_html=body,attachments=[metadata(path),metadata(guide),metadata(warning_file)],status='pending'))
            c.require(found==expected,'export_mismatch')
            s['pending']=run;s['last_checked_at']=now();write(self.path,s);write(folder/'자동발송_준비.json',run)
            return dict(status='prepared',run=run)
    def begin_send(self,package_id):
        """Persist an attempt before calling Gmail; an unknown outcome is not retryable."""
        with locked(self.root):
            s=self.load();c.require(s['pending'] is not None,'no_pending_delivery',409)
            first=next((x for x in s['pending']['packets'] if x['status']=='pending'),None)
            c.require(first is not None and first['package_id']==package_id,'delivery_order',409)
            c.require(not first.get('send_attempt'),'send_outcome_unknown',409)
            for item in first['attachments']:
                path=Path(item['path']);c.require(path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],'attachment_changed',409)
            m,values,ident=package(Path(first['attachments'][0]['path']),s['delivered'])
            c.require(ident==package_id and m==first['manifest'])
            compatible(s,values)
            attempt=dict(id=uuid.uuid4().hex,started_at=now(),status='outcome_unknown')
            first['send_attempt']=attempt;write(self.path,s)
            return dict(status='attempt_started',package_id=package_id,attempt=attempt)
    def confirm(self,package_id,proof):
        with locked(self.root):
            s=self.load()
            prior=next((x for x in s['deliveries'] if x['package_id']==package_id),None)
            if prior:
                c.require(proof.get('message_id')==prior['message_id'],'different_sent_message',409)
                return dict(status='already_recorded',package_id=package_id)
            c.require(s['pending'] is not None,'no_pending_delivery',409)
            p=next((x for x in s['pending']['packets'] if x['package_id']==package_id),None)
            c.require(p is not None and p['status']=='pending','unknown_package',409)
            first=next(x for x in s['pending']['packets'] if x['status']=='pending')
            c.require(first is p,'delivery_order',409)
            for item in p['attachments']:
                path=Path(item['path']);c.require(path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],'attachment_changed',409)
            m,values,ident=package(Path(p['attachments'][0]['path']),s['delivered'])
            c.require(ident==package_id and m==p['manifest'])
            proof_matches(proof,p['subject'],p['attachments'])
            compatible(s,values)
            s['delivered']=advance(s['delivered'],m)
            s['guards'].update({v['article']['id']:guard(v) for v in values})
            entry=dict(package_id=ident,filename=p['attachments'][0]['filename'],sha256=p['attachments'][0]['sha256'],
                message_id=proof['message_id'],subject=p['subject'],sent_at=proof.get('sent_at_kst'),bank_applied=False)
            s['deliveries'].append(entry);p['status']='sent';p['message_id']=entry['message_id']
            finished=all(x['status']=='sent' for x in s['pending']['packets'])
            audit=copy.deepcopy(s['pending'])
            if finished:s['pending']=None
            write(self.path,s)
            folder=Path(p['attachments'][0]['path']).parent
            write(folder/(ident[:12]+'_발송기록.json'),proof);write(folder/'자동발송_상태.json',audit)
            return dict(status='recorded',package_id=ident,run_complete=finished,bank_applied=False)
    def chunk(self,package_id,index,offset,length):
        c.require(type(offset) is int and offset>=0 and type(length) is int and 0<length<=262143)
        # Atomic state replacement makes read-only snapshot access safe; parallel
        # attachment reads must not contend on the writer's exclusive lock.
        s=self.load();c.require(s['pending'] is not None,'no_pending_delivery',409)
        p=next((p for p in s['pending']['packets'] if p['package_id']==package_id),None)
        c.require(p is not None and p['status']=='pending')
        c.require(type(index) is int and 0<=index<len(p['attachments']))
        item=p['attachments'][index];path=Path(item['path'])
        c.require(path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],'attachment_changed',409)
        with path.open('rb') as f:f.seek(offset);data=f.read(length)
        c.require(bool(data))
        return dict(filename=item['filename'],total=item['bytes'],file_sha256=item['sha256'],offset=offset,bytes=len(data),
            base64_url_content=base64.urlsafe_b64encode(data).decode().rstrip('='))

def source(base):
    from dotenv import dotenv_values
    values=dotenv_values(CONNECTION)
    for key in ('SUPABASE_URL','SUPABASE_SERVICE_ROLE_KEY'):
        value=values.get(key);c.require(value and '<' not in value and '>' not in value,'source_credentials_missing',409)
        os.environ[key]=value
    return internet_source(base,REPO/'vibelabs/.data-export-cache',lambda line:print(line,file=sys.stderr,flush=True),changed_records_only=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('initialize');p.add_argument('--bank-receipt',type=Path,required=True);p.add_argument('--sent-bundle',type=Path,required=True);p.add_argument('--sent-proof',type=Path,required=True);p.add_argument('--sent-snapshot',type=Path,required=True)
    sub.add_parser('status');p=sub.add_parser('prepare');p.add_argument('--check-only',action='store_true')
    p=sub.add_parser('begin-send');p.add_argument('--package-id',required=True)
    p=sub.add_parser('confirm');p.add_argument('--package-id',required=True);p.add_argument('--proof',type=Path,required=True)
    p=sub.add_parser('chunk');p.add_argument('--package-id',required=True);p.add_argument('--index',type=int,required=True);p.add_argument('--offset',type=int,required=True);p.add_argument('--length',type=int,default=262143)
    a=parser.parse_args();manager=Manager()
    if a.command=='initialize':result=manager.initialize(a.bank_receipt,a.sent_bundle,a.sent_proof,a.sent_snapshot)
    elif a.command=='status':result=manager.status()
    elif a.command=='prepare':result=manager.prepare(source,check_only=a.check_only)
    elif a.command=='begin-send':result=manager.begin_send(a.package_id)
    elif a.command=='confirm':result=manager.confirm(a.package_id,json.loads(a.proof.read_bytes()))
    else:result=manager.chunk(a.package_id,a.index,a.offset,a.length)
    print(json.dumps(result,ensure_ascii=True),flush=True)

if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps(dict(status='failed',error_type=type(error).__name__,code=getattr(error,'code','local_operation_failed'))),flush=True)
        raise SystemExit(1)
