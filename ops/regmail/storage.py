"""Private object storage with verified immutable snapshots and a guarded head."""
import gzip,hashlib,json,os,re,time,urllib.error,urllib.parse,urllib.request,uuid
from .delivery import c

BUCKET='regulatory-delta-mail'

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

class Storage:
    def __init__(self,url=None,key=None):
        self.url=(url or os.environ['SUPABASE_URL']).rstrip('/')
        parsed=urllib.parse.urlsplit(self.url)
        c.require(parsed.scheme=='https' and re.fullmatch(r'[a-z0-9]{20}\.supabase\.co',parsed.hostname or '')
            and parsed.path=='' and not parsed.username and not parsed.query and not parsed.fragment,'storage_address_invalid')
        self.key=key or os.environ['SUPABASE_SERVICE_ROLE_KEY'];self.head=None
    def request(self,method,path,data=None,extra=None,missing=False):
        headers={'Authorization':'Bearer '+self.key,'apikey':self.key,**(extra or {})}
        request=urllib.request.Request(self.url+'/storage/v1/'+path,data=data,headers=headers,method=method)
        try:
            with urllib.request.build_opener(NoRedirect()).open(request,timeout=90) as response:
                raw=response.read(32*1024*1024+1);c.require(len(raw)<=32*1024*1024,'storage_object_too_large');return raw
        except urllib.error.HTTPError as error:
            status=error.code;body=error.read(8192);error.close()
            absent=status==404
            if status==400:
                try:
                    detail=json.loads(body)
                    absent=str(detail.get('statusCode'))=='404' and detail.get('error') in ('not_found','Not Found','Object not found')
                except (ValueError,AttributeError):pass
            if missing and absent:return None
            raise c.Problem('storage_http_'+str(status),502) from None
        except (TimeoutError,OSError):raise c.Problem('storage_connection_failed',502) from None
    def path(self,key):
        c.require(re.fullmatch(r'[a-zA-Z0-9_./-]+',key) and '..' not in key,'storage_key_invalid')
        return 'object/'+BUCKET+'/'+key
    def get(self,key,missing=False):
        # A cached head could roll the delivery cursor backwards. Private object
        # reads use a unique URL, including the read-back immediately after PUT.
        return self.request('GET',self.path(key)+'?regmail_read='+uuid.uuid4().hex,
            extra={'Cache-Control':'no-cache','Pragma':'no-cache'},missing=missing)
    def put(self,key,data,overwrite=False):
        self.request('POST',self.path(key),data,{'Content-Type':'application/octet-stream','x-upsert':'true' if overwrite else 'false'})
        for attempt in range(4):
            if self.get(key)==data:return
            if attempt<3:time.sleep(attempt+1)
        raise c.Problem('storage_write_unverified',502)
    def ensure_private(self):
        value=json.loads(self.request('GET','bucket/'+BUCKET))
        c.require(value.get('id')==BUCKET and value.get('public') is False,'storage_not_private',409)
    def blob(self,data):
        digest=hashlib.sha256(data).hexdigest();key='blobs/'+digest
        old=self.get(key,missing=True)
        if old is None:self.put(key,data)
        else:c.require(old==data,'storage_blob_mismatch',409)
        return key
    def load(self):
        raw=self.get('head.json');head=json.loads(raw)
        c.require(c.sha(head.get('sha256')) and type(head.get('revision')) is int,'cloud_state_invalid')
        packed=self.get('states/'+head['sha256']+'.gz')
        c.require(hashlib.sha256(packed).hexdigest()==head['sha256'],'cloud_state_corrupt')
        # A bounded reader rejects decompression bombs before parsing JSON.
        import io
        with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
            data=stream.read(64*1024*1024+1)
        c.require(len(data)<=64*1024*1024,'cloud_state_too_large')
        self.head=raw;return json.loads(data)
    def save(self,value,initialize=False):
        current=self.get('head.json',missing=True)
        c.require(current is None if initialize else current==self.head,'cloud_state_changed',409)
        packed=gzip.compress(c.encoded(value),mtime=0);digest=hashlib.sha256(packed).hexdigest()
        path='states/'+digest+'.gz';old=self.get(path,missing=True)
        if old is None:self.put(path,packed)
        else:c.require(old==packed,'cloud_state_corrupt')
        revision=1 if current is None else json.loads(current)['revision']+1
        # All hosted entry points use the same GitHub concurrency group. The
        # checked head also rejects stale manual/bootstrap writers.
        c.require(self.get('head.json',missing=True)==current,'cloud_state_changed',409)
        head=c.encoded(dict(revision=revision,sha256=digest))
        self.put('head.json',head,overwrite=current is not None);self.head=head

