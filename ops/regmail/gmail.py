"""TLS Gmail transport with exact Sent-message and attachment verification."""
import hashlib,imaplib,os,re,smtplib,ssl
from datetime import datetime
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import format_datetime,getaddresses
from pathlib import Path
from .delivery import c,SENDER,RECIPIENT,KST,now,sha
from .archives import MAX_ATTACHMENTS,MAX_MESSAGE

def message_id(packet):return '<regmail.'+packet['package_id']+'@regulation-news-reg.local>'

def build(packet):
    c.require(packet['to']==RECIPIENT and packet['from_address']==SENDER,'mail_address_invalid')
    message=EmailMessage(policy=policy.SMTP)
    message['From']=SENDER;message['To']=RECIPIENT;message['Subject']=packet['subject']
    message['Date']=format_datetime(datetime.now(KST));message['Message-ID']=message_id(packet)
    message['X-Regmail-Package']=packet['package_id']
    message.set_content(packet.get('body_text') or '규제정보 플랫폼 증분 반입자료입니다. 첨부된 반입안내를 확인해주세요.')
    message.add_alternative(packet['body_html'],subtype='html')
    c.require(sum(item['bytes'] for item in packet['attachments'])<=MAX_ATTACHMENTS,'mail_too_large',409)
    for item in packet['attachments']:
        path=Path(item['path']);data=path.read_bytes()
        c.require(len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256'],'attachment_changed',409)
        message.add_attachment(data,maintype='application',subtype='zip' if path.suffix.lower()=='.zip' else 'octet-stream',filename=item['filename'])
    wire=message.as_bytes();c.require(len(wire)<=MAX_MESSAGE,'mail_too_large',409)
    return wire

def verify(raw,packet,provider_id,internal_date):
    message=BytesParser(policy=policy.default).parsebytes(raw)
    addresses=lambda key:[addr.lower() for _,addr in getaddresses(message.get_all(key,[]))]
    c.require(addresses('From')==[SENDER] and addresses('To')==[RECIPIENT] and not addresses('Cc') and not addresses('Bcc'),'sent_address_mismatch',409)
    c.require(str(message['Subject'])==packet['subject'] and str(message['Message-ID'])==message_id(packet),'sent_subject_mismatch',409)
    files=[part for part in message.walk() if part.get_filename() is not None]
    c.require(len(files)==len(packet['attachments']),'sent_attachment_mismatch',409)
    verified=[]
    for item in packet['attachments']:
        candidates=[part for part in files if part.get_filename()==item['filename']]
        c.require(len(candidates)==1,'sent_attachment_mismatch',409)
        data=candidates[0].get_payload(decode=True)
        c.require(isinstance(data,bytes) and len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256'],'sent_attachment_mismatch',409)
        verified.append({k:item[k] for k in ('filename','bytes','sha256')})
    return dict(status='sent',provider_labels=['SENT'],message_id=provider_id,to=RECIPIENT,**{'from':SENDER},
        subject=packet['subject'],sent_at_kst=internal_date,attachments=verified,
        transport_checksum_verified=True,sent_headers_and_attachment_sizes_verified=True,
        sent_attachment_hashes_verified=True)

class Gmail:
    def __init__(self):
        self.password=''.join(os.environ.get('REGMAIL_GMAIL_APP_PASSWORD','').split())
        c.require(len(self.password)==16 and self.password.isascii(),'gmail_credentials_missing',409)
        self.context=ssl.create_default_context()
    def connect(self):
        client=imaplib.IMAP4_SSL('imap.gmail.com',993,ssl_context=self.context,timeout=45)
        try:
            client.login(SENDER,self.password);status,folders=client.list()
            c.require(status=='OK','sent_folder_unavailable',502)
            matches=[]
            for line in folders or []:
                if not isinstance(line,bytes):continue
                match=re.match(rb'^\(([^)]*)\)\s+(?:"[^"]*"|NIL)\s+(.+)$',line,re.I)
                if match and b'\\sent' in match.group(1).lower().split():matches.append(match.group(2).decode('ascii'))
            c.require(len(matches)==1,'sent_folder_unavailable',502)
            status,_=client.select(matches[0],readonly=True);c.require(status=='OK','sent_folder_unavailable',502)
            return client
        except Exception:
            try:client.logout()
            except Exception:pass
            raise
    def check_auth(self):
        client=self.connect();client.logout()
        with smtplib.SMTP_SSL('smtp.gmail.com',465,context=self.context,timeout=45) as smtp:smtp.login(SENDER,self.password)
        return dict(authenticated=True)
    def find(self,packet):
        client=self.connect()
        try:
            status,data=client.uid('search',None,'HEADER','Message-ID','"'+message_id(packet)+'"')
            c.require(status=='OK' and data and isinstance(data[0],bytes),'sent_search_failed',502)
            ids=data[0].split();c.require(len(ids)<=1,'sent_ambiguous',409)
            if not ids:return None
            status,data=client.uid('fetch',ids[0],'(BODY.PEEK[] X-GM-MSGID INTERNALDATE)')
            c.require(status=='OK','sent_read_failed',502)
            parts=[item for item in data if isinstance(item,tuple) and len(item)==2 and isinstance(item[1],bytes)]
            c.require(len(parts)==1,'sent_read_failed',502);header,raw=parts[0]
            gm=re.search(rb'X-GM-MSGID (\d+)',header,re.I);stamp=re.search(rb'INTERNALDATE "([^"]+)"',header,re.I)
            c.require(gm and stamp,'sent_read_failed',502)
            recorded=datetime.strptime(stamp.group(1).decode('ascii'),'%d-%b-%Y %H:%M:%S %z').astimezone(KST).isoformat()
            return verify(raw,packet,format(int(gm.group(1)),'x'),recorded)
        finally:
            try:client.logout()
            except Exception:pass
    def send(self,packet,wire):
        # No automatic retry: a timeout after DATA is an unknown delivery outcome.
        with smtplib.SMTP_SSL('smtp.gmail.com',465,context=self.context,timeout=90) as smtp:
            smtp.login(SENDER,self.password)
            limit=smtp.esmtp_features.get('size')
            c.require(limit is None or limit.isdigit() and len(wire)<=int(limit),'mail_too_large',409)
            rejected=smtp.sendmail(SENDER,[RECIPIENT],wire)
            c.require(not rejected,'mail_recipient_rejected',502)
