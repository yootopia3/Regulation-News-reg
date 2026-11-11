"""Read-only source export; deterministic comparison and bounded streaming files."""
import hashlib
import json
import shutil
import re
from concurrent.futures import ThreadPoolExecutor,as_completed
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from application import transfer_contract as c
from application.agency_policy import is_excluded

def receipt(path):
    c.require(path.stat().st_size<=32*1024*1024)
    value=json.loads(path.read_bytes())
    c.require(value.get('format')=='regulation-receipt-v1')
    c.require(isinstance(value.get('source_project'),str) and re.fullmatch('[a-z0-9]{20}',value['source_project']))
    c.require(isinstance(value.get('records'),dict) and isinstance(value.get('files'),dict))
    for ident,digest in value['records'].items():c.identifier(ident);c.require(c.sha(digest))
    for digest,meta in value['files'].items():
        c.require(c.sha(digest) and type(meta.get('bytes')) is int and 0<meta['bytes']<=c.MAX_FILE and meta.get('extension') in c.TYPES)
    return value

def rows(path):
    if not path.exists():return []
    with path.open('rb') as stream:return [json.loads(line) for line in stream if line.strip()]

def local_source(root):
    manifest=json.loads((root/'manifest.json').read_bytes())
    publications={r['article_id']:r for r in rows(root/'sanction_publications.jsonl')}
    originals={r['article_id']:r for r in rows(root/'originals/records.jsonl')}
    paths={}
    for record in originals.values():
        for f in record['files']:
            if f['status']=='available':
                path=(root/'originals'/f['file']).resolve()
                c.require(path.is_relative_to((root/'originals/files').resolve()))
                paths[f['sha256']]=path
    values=[c.envelope(dict(article=a,original=originals.get(a['id']),publication=publications.get(a['id'])))
        for a in rows(root/'articles.jsonl') if not is_excluded(a['agency'])]
    return manifest['source_project'],values,paths

def pages(client,table,fields,key):
    result=[];offset=0
    while True:
        part=client.table(table).select(','.join(fields)).order(key).range(offset,offset+999).execute().data
        c.require(isinstance(part,list))
        result.extend(part)
        if len(part)<1000:break
        offset+=1000
    c.require(len({r[key] for r in result})==len(result),'source_changing',409)
    return result

def catalog(client):
    articles=[c.article(a) for a in pages(client,'articles',c.ARTICLE_FIELDS,'id') if not is_excluded(a['agency'])]
    ids={a['id'] for a in articles}
    pubs=[c.publication(p,p['article_id']) for p in pages(client,'sanction_publications',c.PUBLICATION_FIELDS,'inspection_id') if p['article_id'] in ids]
    return articles,{p['article_id']:p for p in pubs}

def refresh_originals(articles,publications,original_cache,progress=print,workers=8,baseline=None):
    c.require(type(workers) is int and 1<=workers<=8)
    values=[];pending=[]
    for a in articles:
        original=original_cache.prior.get(a['id']) if baseline is not None else None
        value=c.envelope(dict(article=a,original=original,publication=publications.get(a['id'])))
        complete=original and original['body_status']!='unavailable' and all(f['status']=='available' for f in original['files'])
        if baseline is not None and complete and c.digest(value)==baseline['records'].get(a['id']):values.append(value)
        else:pending.append(a)
    if baseline is not None:progress(f'빠른 증분 확인: 원문·첨부 확인 대상 {len(pending):,}건 / 동일 {len(values):,}건 재사용')
    finished=0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        tasks={pool.submit(original_cache.refresh,a):a for a in pending}
        for future in as_completed(tasks):
            a=tasks[future]
            values.append(c.envelope(dict(article=a,original=future.result(),publication=publications.get(a['id']))))
            finished+=1
            if finished%10==0 or finished==len(pending):progress(f'본문·첨부 확인 {finished:,} / {len(pending):,}건')
    return values

def internet_source(baseline,cache,progress=print,workers=8,changed_records_only=False):
    repo=Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo))
    from src.config import settings
    settings.load_env(repo/'notepad.env' if (repo/'notepad.env').exists() else repo/'.env')
    from urllib.parse import urlsplit
    key=settings.get_supabase_service_role_key()
    c.require(bool(key) and '<' not in key and '>' not in key,'source_credentials_missing',409)
    url=urlsplit(settings.get_supabase_url());project=(url.hostname or '').split('.')[0]
    c.require(project==baseline['source_project'],'source_project_conflict',409)
    c.require(url.scheme=='https' and url.hostname==project+'.supabase.co' and url.port in (None,443)
        and not url.username and not url.password and url.path in ('','/') and not url.query and not url.fragment,'source_project_conflict',409)
    from src.db.client import get_supabase_client
    from transfer_fetch import OriginalCache
    client=get_supabase_client()
    progress('인터넷 플랫폼의 자료와 공개 분석 결과를 조회합니다.')
    first=catalog(client);second=catalog(client)
    c.require(c.digest(first)==c.digest(second),'source_changing',409)
    original_cache=OriginalCache(cache,repo/'vibelabs/history-data')
    values=refresh_originals(first[0],first[1],original_cache,progress,workers,baseline if changed_records_only else None)
    # A source edit while downloading must not produce a mixed catalog. Cache
    # remains reusable; no baseline is advanced on failure or export alone.
    c.require(c.digest(first)==c.digest(catalog(client)),'source_changing',409)
    return project,values,original_cache.paths,original_cache.warnings

def export(project,values,paths,baseline,output,*,max_bytes=c.MAX_PACKAGE,max_records=c.MAX_RECORDS):
    c.require(project==baseline['source_project'],'source_project_conflict',409)
    c.require(12<max_bytes<=c.MAX_PACKAGE and 0<max_records<=c.MAX_RECORDS)
    values=sorted(values,key=lambda v:v['article']['id'])
    c.require(len({v['article']['id'] for v in values})==len(values))
    changed=[v for v in values if c.digest(v)!=baseline['records'].get(v['article']['id'])]
    stamp=datetime.now(timezone.utc).isoformat();packages=[];group=[]
    def describe(batch):
        records=[];files={}
        for value in batch:
            ident=value['article']['id'];data=c.encoded(value)
            records.append(dict(id=ident,base=baseline['records'].get(ident),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data)))
            for f in (value['original'] or {}).get('files',[]):
                if f['status']!='available':continue
                meta={k:f[k] for k in ('bytes','extension')}
                if f['sha256'] in baseline['files']:
                    c.require(baseline['files'][f['sha256']]==meta);continue
                c.require(f['sha256'] not in files or {k:files[f['sha256']][k] for k in meta}==meta)
                files[f['sha256']]=dict(sha256=f['sha256'],**meta)
        manifest=dict(format='regulation-delta-v1',source_project=project,created_at=stamp,records=records,files=sorted(files.values(),key=lambda f:f['sha256']))
        size=12+len(c.encoded(manifest))+sum(r['bytes'] for r in records)+sum(f['bytes'] for f in files.values())
        return manifest,size
    for value in changed:
        proposed=group+[value];_,size=describe(proposed)
        if group and (len(proposed)>max_records or size>max_bytes or sum(len(c.encoded(v)) for v in proposed)>c.MAX_RECORD_TOTAL):packages.append(group);group=[]
        group.append(value);_,size=describe(group)
        c.require(size<=max_bytes,'article_package_too_large',409)
    if group:packages.append(group)
    output.mkdir(parents=True,exist_ok=True)
    written=[]
    try:
        for index,batch in enumerate(packages,1):
            manifest,size=describe(batch);ident,_=c.manifest(manifest)
            c.require(shutil.disk_usage(output).free>size+64*1024*1024,'export_disk_full',409)
            target=output/f'규제자료_{datetime.now():%Y%m%d_%H%M%S}_{index:03d}_{ident[:12]}.regdata'
            part=target.with_suffix('.partial')
            try:
                with part.open('xb') as stream:
                    stream.write(c.header(manifest))
                    for value in batch:stream.write(c.encoded(value))
                    for spec in manifest['files']:
                        path=paths.get(spec['sha256']);c.require(path and path.is_file(),'export_missing_file',409)
                        digest=hashlib.sha256();length=0
                        with path.open('rb') as source:
                            while data:=source.read(c.CHUNK):stream.write(data);digest.update(data);length+=len(data)
                        c.require(length==spec['bytes'] and digest.hexdigest()==spec['sha256'],'transfer_corrupt')
                c.require(part.stat().st_size==size);part.replace(target);written.append(target)
            finally:part.unlink(missing_ok=True)
    except BaseException:
        for target in written:target.unlink(missing_ok=True)
        raise
    return dict(changed=len(changed),unchanged=len(values)-len(changed),files=written,
        absent=len(set(baseline['records'])-{v['article']['id'] for v in values}))
