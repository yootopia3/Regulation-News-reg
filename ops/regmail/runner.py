"""Hosted entry point. Remote persistence must succeed before any SMTP send."""
import argparse,copy,hashlib,json,os,re,time
from datetime import datetime
from pathlib import Path
from .delivery import Manager,c,KST,SENDER,RECIPIENT,DEFAULT_OUTPUT,write,package
from .storage import Storage
from .gmail import Gmail,build
from .calendar import business_day
from .source import read_source

def validate(cloud):
    c.require(cloud.get('format')=='regmail-cloud-v1','cloud_state_invalid')
    state=cloud['delivery'];values=cloud['values'];base=state['delivered']
    c.require(state['sender']==SENDER and state['recipient']==RECIPIENT and bool(SENDER) and bool(RECIPIENT),'mail_address_invalid')
    c.require(set(values)==set(base['records']),'cloud_snapshot_mismatch')
    for key,value in values.items():
        normalized=c.envelope(value)
        c.require(value==normalized and value['article']['id']==key and c.digest(value)==base['records'][key],'cloud_snapshot_mismatch')
    from .delivery import compatible
    compatible(state,[])

class Hosted:
    def __init__(self,store,mail,runtime=None,supplier=None):
        self.store=store;self.mail=mail;self.root=Path(runtime or DEFAULT_OUTPUT.parent)
        self.manager=Manager(self.root/'delivery',self.root/'out');self.known=set()
        self.cloud=store.load();validate(self.cloud);state=copy.deepcopy(self.cloud['delivery'])
        for packet in (state['pending'] or {}).get('packets',[]):
            for item in packet['attachments']:
                relative=Path(item['path']);path=(self.root/'out'/relative).resolve()
                c.require(not relative.is_absolute() and path.is_relative_to((self.root/'out').resolve()),'cloud_path_invalid')
                data=store.get('blobs/'+item['sha256'])
                c.require(len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256'],'cloud_attachment_corrupt')
                path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
                item['path']=str(path);self.known.add(item['sha256'])
        write(self.manager.path,state)
        self.supplier=supplier or (lambda base:read_source(base,self.root/'cache',self.cloud['values']))
    def save(self):
        state=self.manager.load();remote=copy.deepcopy(state)
        for packet in (remote['pending'] or {}).get('packets',[]):
            for item in packet['attachments']:
                path=Path(item['path']).resolve();root=(self.root/'out').resolve()
                c.require(path.is_relative_to(root),'cloud_path_invalid')
                data=path.read_bytes();c.require(len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256'],'attachment_changed')
                if item['sha256'] not in self.known:self.store.blob(data);self.known.add(item['sha256'])
                item['path']=path.relative_to(root).as_posix()
        self.cloud['delivery']=remote;validate(self.cloud);self.store.save(self.cloud)
    def deliver_pending(self,sleeper=time.sleep):
        sent=0
        while self.manager.load()['pending']:
            state=self.manager.load()
            packet=next(p for p in state['pending']['packets'] if p['status']=='pending')
            proof=self.mail.find(packet)
            if proof is None:
                c.require(not packet.get('send_attempt'),'send_outcome_unknown',409)
                wire=build(packet)
                self.manager.begin_send(packet['package_id'])
                self.save() # Durable remote attempt marker BEFORE calling SMTP.
                self.mail.send(packet,wire)
                for attempt in range(4):
                    proof=self.mail.find(packet)
                    if proof is not None:break
                    if attempt<3:sleeper(5)
                c.require(proof is not None,'send_outcome_unknown',409)
            _,values,_=package(Path(packet['attachments'][0]['path']),state['delivered'])
            self.manager.confirm(packet['package_id'],proof)
            self.cloud['values'].update({v['article']['id']:v for v in values})
            self.cloud.setdefault('sent_proofs',{})[packet['package_id']]=proof
            self.save();sent+=1
        return sent
    def run(self,date,test=False):
        sent=self.deliver_pending()
        result=self.manager.prepare(self.supplier)
        if result['status']=='prepared' and test:
            state=self.manager.load()
            for packet in state['pending']['packets']:
                packet['subject']='[서버 전환 시험] '+packet['subject']
                packet['body_html']='<p>서버에서 생성·발송한 실제 증분자료입니다. 기존 파일 다음 순서로 반입할 수 있습니다.</p>'+packet['body_html']
            write(self.manager.path,state)
        self.save() # Package objects + pending manifest before delivery attempts.
        counts=(result.get('run') or {}).get('counts',dict(added=0,updated=0,changed=0))
        sent+=self.deliver_pending()
        self.cloud['last_completed_business_date']=date
        self.cloud['last_result']=dict(date=date,packets_verified=sent,**counts,test=test,
            server_run_id=os.environ.get('GITHUB_RUN_ID'),code_sha=os.environ.get('GITHUB_SHA'))
        if test and sent:self.cloud['migration_test']=copy.deepcopy(self.cloud['last_result'])
        self.save();return self.cloud['last_result']

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=('auth','check','test','scheduled','scheduler-prepare','scheduler-enable'),required=True);args=parser.parse_args()
    c.require(os.environ.get('GITHUB_REF')=='refs/heads/main','default_branch_required',403)
    if args.mode.startswith('scheduler-'):
        from .scheduler import main as scheduler
        print(json.dumps(scheduler(enable=args.mode=='scheduler-enable')));return
    if args.mode=='scheduled':c.require(os.environ.get('REGMAIL_ENABLED')=='true','schedule_not_enabled',409)
    if args.mode=='auth':
        Gmail().check_auth();print(json.dumps(dict(status='gmail_ready')));return
    day=business_day()
    if not day['business']:
        print(json.dumps(dict(status='holiday_skipped',**day),ensure_ascii=True));return
    if args.mode=='scheduled':c.require(datetime.now(KST).hour>=9,'before_scheduled_time',409)
    mail=Gmail();mail.check_auth();store=Storage();store.ensure_private()
    hosted=Hosted(store,mail)
    if args.mode=='check':
        print(json.dumps(dict(status='ready',business_date=day['date'],delivered_records=len(hosted.cloud['delivery']['delivered']['records']),pending=bool(hosted.cloud['delivery']['pending']))));return
    if args.mode=='scheduled' and hosted.cloud.get('last_completed_business_date')==day['date']:
        print(json.dumps(dict(status='already_completed',date=day['date'])));return
    result=hosted.run(day['date'],test=args.mode=='test')
    print(json.dumps(dict(status='completed',**result),ensure_ascii=True))
    summary=os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a',encoding='utf-8') as f:
            f.write(f"규제자료 발송 완료: 신규 {result['added']}건, 수정 {result['updated']}건, SENT 확인 {result['packets_verified']}개. 행내 적용은 별도입니다.\n")

if __name__=='__main__':
    try:main()
    except Exception as error:
        code=getattr(error,'code','hosted_operation_failed')
        if not isinstance(code,str) or not re.fullmatch('[a-z0-9_]+',code):code='hosted_operation_failed'
        print(json.dumps(dict(status='failed',code=code,error_type=type(error).__name__)))
        raise SystemExit(1)
