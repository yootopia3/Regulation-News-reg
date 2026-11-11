"""Offline-only official-source recovery. No credentials, runtime network or AI calls."""
import argparse,concurrent.futures,hashlib,ipaddress,json,re,socket,sys,threading,time,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from lxml import html
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from application.original_contract import MAX_FILE,TAGS,clean_name,decode_filename,file_type,validate_tree

HOSTS=('fsc.go.kr','fss.or.kr','bok.or.kr','kfb.or.kr','mofe.go.kr','moef.go.kr','korea.kr','bis.org')
HOST_LIMITS={h:threading.BoundedSemaphore(3) for h in HOSTS}
def canonical(url):
    url=re.sub(r';jsessionid=[^?/#;]*','',url,flags=re.I)
    p=urllib.parse.urlsplit(url)
    if p.scheme=='http':p=p._replace(scheme='https')
    return urllib.parse.quote(urllib.parse.urlunsplit(p._replace(fragment='')),safe=":/?&=%+@,;!*'()[]")

def article_url(row):
    url=canonical(row['link']);p=urllib.parse.urlsplit(url)
    # Older KFB records used the list path with a valid article id. The official
    # mobile detail path is info_news_view.php (also used by newer saved links).
    if row['agency']=='KFB' and p.hostname=='m.kfb.or.kr' and p.path=='/news/info_news.php':
        ident=urllib.parse.parse_qs(p.query).get('idx',[''])[0]
        if ident.isdigit():url=urllib.parse.urlunsplit(p._replace(path='/news/info_news_view.php'))
    return url
def check_url(url):
    p=urllib.parse.urlsplit(url);host=p.hostname or ''
    if p.scheme!='https' or p.username or p.password or p.port not in (None,443) or not any(host==h or host.endswith('.'+h) for h in HOSTS):raise ValueError('source_host')
    if any(not ipaddress.ip_address(a[4][0]).is_global for a in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)):raise ValueError('private_address')
class Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        newurl=canonical(newurl);check_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)
def fetch(url,limit,with_name=False):
    url=canonical(url);check_url(url)
    opener=urllib.request.build_opener(Redirects())
    host=urllib.parse.urlsplit(url).hostname
    limiter=HOST_LIMITS[next(h for h in HOSTS if host==h or host.endswith('.'+h))]
    with limiter, opener.open(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept-Language':'ko-KR,ko;q=0.9'}),timeout=20) as response:
        data=response.read(limit+1);filename=response.headers.get_filename() or ''
    if len(data)>limit:raise ValueError('source_too_large')
    return (data,decode_filename(urllib.parse.unquote(filename))) if with_name else data
def decode(data):
    try:return data.decode('utf-8-sig')
    except UnicodeDecodeError:return data.decode('cp949',errors='replace')
def cls(name):return 'contains(concat(" ", normalize-space(@class), " "), " '+name+' ")'
def container(doc,agency,url):
    selectors={
        'FSC':'//*['+cls('board-view-wrap')+']//*['+cls('body')+']/*['+cls('cont')+']',
        'FSC_REG':'//*['+cls('board-view-wrap')+']//*['+cls('cont')+']',
        'FSS':'//*['+cls('krds-bd-view')+']/*['+cls('n-dbdata')+']',
        'FSS_REG_INFO':'//*['+cls('krds-bd-view')+']/*['+cls('n-dbdata')+']',
        'FSS_REG':'//*['+cls('krds-reg')+' and '+cls('reg2')+']',
        'FSS_SANCTION':'//*['+cls('bd-view')+']',
        'FSS_MGMT_NOTICE':'//*['+cls('bd-view')+']',
        'BOK':'//*['+cls('dbdata')+']',
        'KFB':'//*['+cls('viewInfo')+']/*['+cls('txt')+']',
        'MOEF':'//*['+cls('view_cont' if 'korea.kr' in url else 'editorCont')+']'}
    found=doc.xpath(selectors[agency])
    return found[0] if found else None
def attachment_links(doc,base):
    found={}
    for a in doc.xpath('//a[@href]'):
        href=a.get('href','');lower=href.lower()
        if not re.search(r'(getfile\?|filedown\.do|hpdownload\?|/download\.php|/download\.do|/filesrc/|\.(?:pdf|hwpx?|docx?|xlsx?|pptx?|zip|txt|md|csv)(?:\?|$))',lower):continue
        if any(x in lower for x in ['synap','viewer.html','docview','atchzipfiledown']):continue
        target=canonical(urllib.parse.urljoin(base,href))
        label=re.sub(r'\s+',' ',a.text_content()).strip()
        if label in {'문서뷰어','뷰어','바로보기','자료열기'}:continue
        old=found.get(target)
        if old is None or re.search(r'\.(pdf|hwp|hwpx|xlsx?|docx?|pptx?|zip|txt|md|csv)',label,re.I):found[target]=label
    return [dict(source_url=url,name=name) for url,name in found.items()]

def passive_tree(element,image_loader):
    def meaningful(node):
        return bool(node.strip()) if isinstance(node,str) else node['tag']=='img' or any(meaningful(c) for c in node.get('children',[]))
    def walk(e,depth=0):
        if not isinstance(e.tag,str) or depth>25:return []
        tag=e.tag.lower()
        if tag in {'script','style','noscript','nav','form','input','button','textarea','iframe','object','embed','svg','link','meta'}:return []
        if any(c in (e.get('class') or '').split() for c in ['attach-file-box','fileView','fileInfo']):return []
        if tag=='img':
            return image_loader(e)
        children=[]
        if e.text:children.append(re.sub(r'\s+',' ',e.text))
        for child in e:
            children.extend(walk(child,depth+1))
            if child.tail:children.append(re.sub(r'\s+',' ',child.tail))
        joined=[]
        for child in children:
            if isinstance(child,str) and joined and isinstance(joined[-1],str):joined[-1]+=child
            else:joined.append(child)
        children=joined
        if tag not in TAGS:
            if tag in {'dl','dt','dd','section','article','figcaption'}:tag='div'
            else:return children
        if tag=='br':return [dict(tag='br')]
        if tag in {'p','div','h2','h3','h4','li','blockquote'} and not any(meaningful(c) for c in children):return []
        if tag not in {'td','th'} and (not children or all(isinstance(c,str) and not c.strip() for c in children)):return []
        node=dict(tag=tag,children=children)
        if tag in {'td','th'}:
            for key in ['colspan','rowspan']:
                value=e.get(key,'1')
                if value.isdigit() and 1<int(value)<=100:node[key]=int(value)
        align=re.search(r'text-align\s*:\s*(left|center|right)',e.get('style',''))
        if align:node['align']=align[1]
        return [node]
    tree=walk(element) if element is not None else []
    validate_tree(tree)
    return tree

def tree_text(tree):
    def text(n):return n if isinstance(n,str) else ('\n' if n['tag']=='br' else ''.join(text(c) for c in n.get('children',[])))
    return ''.join(text(n) for n in tree).strip()

def main():
    p=argparse.ArgumentParser();p.add_argument('--history',type=Path,required=True);p.add_argument('--cache',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,default=4);p.add_argument('--limit',type=int)
    p.add_argument('--retry-failed',action='store_true',help='Retry source pages/files that were unavailable in the last run');args=p.parse_args()
    for directory in [args.cache/'pages',args.cache/'downloads',args.cache/'records',args.output/'files']:directory.mkdir(parents=True,exist_ok=True)
    rows=[]
    for line in (args.history/'articles.jsonl').read_bytes().splitlines():
        row=json.loads(line)
        if (row.get('agency') or '').strip().upper()=='MAFRA':continue
        row['_hash']=hashlib.sha256(line).hexdigest();rows.append(row)
    rows.sort(key=lambda r:r['published_at'],reverse=True)
    if args.limit:rows=rows[:args.limit]
    locks=[threading.Lock() for _ in range(64)]
    def download(url,name,kind):
        url=canonical(url);key=hashlib.sha256(url.encode()).hexdigest();saved=args.cache/'downloads'/(key+'.json')
        with locks[int(key[:2],16)%64]:
            if saved.exists():
                result=json.loads(saved.read_bytes())
                if result.get('status')=='available' and decode_filename(result['name'])==result['name'] and (args.output/result['file']).exists():
                    cached=args.output/result['file']
                    with cached.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
                    if digest==result['sha256']:
                        # Preserve a real filename from Content-Disposition when a link says only 'download'.
                        if not re.search(r'\.(pdf|hwpx?|docx?|xlsx?|pptx?|zip|png|jpe?g|gif|txt|md|csv)',name,re.I):name=result['name']
                        return {**result,'name':clean_name(name,result['extension']),'kind':kind}
            try:
                data,header_name=fetch(url,MAX_FILE,with_name=True)
                if data.lstrip().startswith(b'<') and len(data)<200000:
                    match=re.search(r'location\.href\s*=\s*[\"\']([^\"\']+)',decode(data))
                    if match:data,header_name=fetch(urllib.parse.urljoin(url,match[1]),MAX_FILE,with_name=True)
                name=re.sub(r'\s*\(파일크기:.*$', '',name).strip()
                if not re.search(r'\.(pdf|hwpx?|docx?|xlsx?|pptx?|zip|png|jpe?g|gif|txt|md|csv)$',name,re.I):name=header_name or name
                extension=file_type(data,name)
                digest=hashlib.sha256(data).hexdigest();file='files/'+digest+'.'+extension
                part=(args.output/file).with_suffix('.part-'+str(threading.get_ident()))
                part.write_bytes(data);part.replace(args.output/file)
                result=dict(status='available',sha256=digest,extension=extension,bytes=len(data),file=file,source_url=url,name=clean_name(name,extension),kind=kind)
            except Exception as exc:
                result=dict(status='unavailable',source_url=url,name=re.sub(r'\s+',' ',name)[:240],kind=kind,error=type(exc).__name__,reason=str(exc)[:80])
            saved.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
            return result
    def process(row):
        saved=args.cache/'records'/(row['id']+'.json')
        path=args.cache/'pages'/(row['id']+'.html')
        source_url=article_url(row)
        if saved.exists():
            previous=json.loads(saved.read_bytes())
            same_source=previous.get('source_version')=='archive:'+row['_hash'] and previous.get('source_url')==source_url
            incomplete=previous['body_status']=='unavailable' or any(f['status']=='unavailable' for f in previous['files'])
            files_present=all((args.output/f['file']).is_file() and (args.output/f['file']).stat().st_size==f['bytes'] for f in previous['files'] if f['status']=='available')
            if previous.get('extractor_version')==4 and same_source and files_present and not (args.retry_failed and incomplete):return previous
            if not same_source or previous['body_status']=='unavailable':path.unlink(missing_ok=True)
        result=dict(article_id=row['id'],extractor_version=4,source_version='archive:'+row['_hash'],source_url=source_url,
            fetched_at=datetime.now(timezone.utc).isoformat(),tree=[],files=[],body_status='unavailable')
        try:
            if not path.exists():path.write_bytes(fetch(source_url,8*1024*1024))
            result['fetched_at']=datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat()
            if path.read_bytes().startswith(b'%PDF-'):
                result['files'].append(download(source_url,row['title']+'.pdf','attachment'))
                result['body_status']='attachment_only' if result['files'][0]['status']=='available' else 'unavailable'
                saved.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
                return result
            doc=html.fromstring(decode(path.read_bytes()))
            for link in attachment_links(doc,source_url):result['files'].append(download(link['source_url'],link['name'],'attachment'))
            def load_image(e):
                src=e.get('src','')
                if not src or src.startswith('data:'):return []
                url=canonical(urllib.parse.urljoin(source_url,src))
                name=urllib.parse.unquote(urllib.parse.urlsplit(url).path.rsplit('/',1)[-1]) or '본문 이미지'
                file=download(url,name,'image');result['files'].append(file)
                if file['status']=='available' and file['extension'] in {'png','jpg','gif'}:
                    return [dict(tag='img',sha256=file['sha256'],alt=(e.get('alt') or '원문 이미지')[:500])]
                return [dict(tag='p',children=['[원문 이미지 미확보] '+(e.get('alt') or '')])]
            area=container(doc,row['agency'],source_url)
            result['tree']=passive_tree(area,load_image)
            content=tree_text(result['tree'])
            result['body_status']='available' if len(content)>60 or any(f.get('kind')=='image' and f['status']=='available' for f in result['files']) else 'attachment_only' if any(f['status']=='available' and f['kind']=='attachment' for f in result['files']) else 'unavailable'
            if area is None:result['error']='body_container_missing'
        except Exception as exc:result['error']=type(exc).__name__
        saved.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
        return result
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs={pool.submit(process,row):row['id'] for row in rows}
        for future in concurrent.futures.as_completed(jobs):
            results.append(future.result())
            if len(results)%25==0 or len(results)==len(rows):
                print(json.dumps(dict(completed=len(results),total=len(rows),bodies=sum(r['body_status']=='available' for r in results),files=sum(f['status']=='available' for r in results for f in r['files']))),flush=True)
    results.sort(key=lambda r:r['article_id'])
    raw=''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in results).encode()
    (args.output/'records.jsonl').write_bytes(raw)
    manifest=dict(format='regulation-originals-v1',created_at=datetime.now(timezone.utc).isoformat(),rows=len(results),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(manifest),flush=True)
if __name__=='__main__':main()
