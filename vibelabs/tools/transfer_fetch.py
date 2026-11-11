"""Conditional official-source refresh. Used only on the internet notebook."""
import hashlib
import json
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from lxml import html
import prepare_originals as p
from application import transfer_contract as c

class OriginalCache:
    def __init__(self,root,seed):
        self.root=Path(root);self.paths={};self.prior={};self.known={};self.warnings=[]
        for name in ('files','pages','requests','records'):(self.root/name).mkdir(parents=True,exist_ok=True)
        from transfer_export import local_source
        if (seed/'manifest.json').exists():
            _,values,paths=local_source(seed);self.paths.update(paths)
            self.prior={v['article']['id']:v['original'] for v in values if v['original']}
        for path in (self.root/'records').glob('*.json'):
            value=json.loads(path.read_bytes());self.prior[path.stem]=value
        for original in self.prior.values():
            for f in original['files']:
                if f['status']=='available':
                    cachefile=self.root/'files'/(f['sha256']+'.'+f['extension'])
                    if cachefile.exists():self.paths[f['sha256']]=cachefile
                    if f['sha256'] in self.paths:self.known[p.canonical(f['source_url'])]=f
        self.fetched={}
        self.download_locks=[threading.RLock() for _ in range(64)]
        self.file_locks=[threading.RLock() for _ in range(128)]

    def file_lock(self,path):
        return self.file_locks[int(hashlib.sha256(str(path).encode()).hexdigest()[:4],16)%len(self.file_locks)]

    def atomic_write(self,path,data):
        with self.file_lock(path):
            partial=path.with_name(path.name+'.partial-'+str(threading.get_ident()))
            try:
                partial.write_bytes(data);partial.replace(path)
            finally:partial.unlink(missing_ok=True)

    def request(self,url,limit,old_path=None):
        url=p.canonical(url);p.check_url(url)
        key=hashlib.sha256(url.encode()).hexdigest();path=self.root/'requests'/(key+'.json')
        with self.file_lock(path):previous=json.loads(path.read_bytes()) if path.exists() else {}
        headers={'User-Agent':'Mozilla/5.0','Accept-Language':'ko-KR,ko;q=0.9'}
        matches=False
        if old_path and old_path.exists():
            with old_path.open('rb') as stream:matches=hashlib.file_digest(stream,'sha256').hexdigest()==previous.get('sha256')
        if matches:
            if previous.get('etag'):headers['If-None-Match']=previous['etag']
            if previous.get('modified'):headers['If-Modified-Since']=previous['modified']
        try:
            host=urllib.parse.urlsplit(url).hostname
            limiter=p.HOST_LIMITS[next(h for h in p.HOSTS if host==h or host.endswith('.'+h))]
            with limiter, urllib.request.build_opener(p.Redirects()).open(urllib.request.Request(url,headers=headers),timeout=25) as response:
                prefix=response.read(8)
                if prefix.startswith(b'%PDF-'):limit=c.MAX_FILE
                data=prefix+response.read(limit+1-len(prefix))
                c.require(len(data)<=limit,'source_too_large')
                metadata=dict(etag=response.headers.get('ETag'),modified=response.headers.get('Last-Modified'),
                    name=p.decode_filename(urllib.parse.unquote(response.headers.get_filename() or '')),sha256=hashlib.sha256(data).hexdigest())
        except urllib.error.HTTPError as error:
            if error.code==304 and matches:
                error.close();return None,previous.get('name',''),None
            error.close();raise
        # Validators are saved only after the bytes have been persisted.
        return data,metadata['name'],(path,metadata)

    def remember(self,pending):
        if pending:
            path,value=pending;self.atomic_write(path,c.encoded(value))

    def download(self,url,name,kind,prefetched=None):
        url=p.canonical(url)
        lock=self.download_locks[int(hashlib.sha256(url.encode()).hexdigest()[:2],16)%len(self.download_locks)]
        with lock:return self.download_locked(url,name,kind,prefetched)

    def download_locked(self,url,name,kind,prefetched=None):
        url=p.canonical(url);old=self.known.get(url)
        try:
            if url in self.fetched and prefetched is None:result=self.fetched[url]
            else:
                old_path=self.paths.get(old['sha256']) if old else None
                data,header,pending=prefetched if prefetched is not None else self.request(url,c.MAX_FILE,old_path)
                if data is None:result=old
                else:
                    if data.lstrip().startswith(b'<') and len(data)<200000:
                        match=re.search(r'location\.href\s*=\s*["\']([^"\']+)',p.decode(data))
                        if match:
                            redirected=p.canonical(urllib.parse.urljoin(url,match[1]))
                            data,header,pending=self.request(redirected,c.MAX_FILE)
                    cleaned=re.sub(r'\s*\(파일크기:.*$','',name).strip()
                    if not re.search(r'\.(pdf|hwpx?|docx?|xlsx?|pptx?|zip|png|jpe?g|gif|txt|md|csv)$',cleaned,re.I):cleaned=header or cleaned
                    ext=p.file_type(data,cleaned);digest=hashlib.sha256(data).hexdigest()
                    target=self.paths.get(digest) or self.root/'files'/(digest+'.'+ext)
                    with self.file_lock(target):
                        if not target.exists():self.atomic_write(target,data)
                        self.paths[digest]=target
                    result=dict(sha256=digest,extension=ext,bytes=len(data),name=p.clean_name(cleaned,ext),
                        kind=kind,source_url=url,status='available')
                    self.remember(pending)
                self.fetched[url]=result
            label=re.sub(r'\s*\(파일크기:.*$','',name).strip()
            current_name=p.clean_name(label,result['extension']) if re.search(r'\.'+re.escape(result['extension'])+r'$',label,re.I) else result['name']
            return {**result,'kind':kind,'name':current_name}
        except Exception:
            self.warnings.append('첨부 확인 실패: '+name[:120])
            if old and old['sha256'] in self.paths and self.paths[old['sha256']].exists():return {**old,'kind':kind}
            return dict(name=p.clean_name(name or '첨부파일',''),kind=kind,status='unavailable')

    def refresh(self,article):
        ident=article['id'];old=self.prior.get(ident);url=p.article_url(article)
        page=self.root/'pages'/(ident+'.html')
        try:
            data,header,pending=self.request(url,8*1024*1024,page)
            if data is not None:
                self.atomic_write(page,data);self.remember(pending)
            data=page.read_bytes();files=[]
            if data.startswith(b'%PDF-'):
                files.append(self.download(url,article['title']+'.pdf','attachment',prefetched=(data,header,None)));tree=[]
            else:
                doc=html.fromstring(p.decode(data))
                for link in p.attachment_links(doc,url):files.append(self.download(link['source_url'],link['name'],'attachment'))
                def image(element):
                    src=element.get('src','')
                    if not src or src.startswith('data:'):return []
                    address=p.canonical(urllib.parse.urljoin(url,src))
                    file=self.download(address,urllib.parse.unquote(urllib.parse.urlsplit(address).path.rsplit('/',1)[-1]),'image');files.append(file)
                    if file['status']=='available' and file['extension'] in ('png','jpg','gif'):
                        return [dict(tag='img',sha256=file['sha256'],alt=(element.get('alt') or '원문 이미지')[:500])]
                    return [dict(tag='p',children=['[원문 이미지 미확보] '+(element.get('alt') or '')[:500]])]
                tree=p.passive_tree(p.container(doc,article['agency'],url),image)
            status='available' if len(p.tree_text(tree))>60 or any(f['kind']=='image' and f['status']=='available' for f in files) else 'attachment_only' if any(f['kind']=='attachment' and f['status']=='available' for f in files) else 'unavailable'
            if old and old['body_status']=='available' and status!='available':
                self.warnings.append('본문 확인 실패·이전 본문 유지: '+article['title'][:120]);tree=old['tree'];status='available'
                # Retain images referenced by the old tree, and old files when
                # a source page temporarily loses its attachment section.
                keys={f.get('sha256') for f in files}
                files += [f for f in old['files'] if f.get('sha256') not in keys and f['status']=='available']
            result=c.original(dict(source_url=url,tree=tree,files=files,body_status=status))
        except Exception:
            self.warnings.append('원문 확인 실패: '+article['title'][:120])
            result=old or c.original(dict(source_url=url,tree=[],files=[],body_status='unavailable'))
        self.atomic_write(self.root/'records'/(ident+'.json'),c.encoded(result))
        self.prior[ident]=result
        return result
