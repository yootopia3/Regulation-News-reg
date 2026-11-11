"""Portable data-only format. No archive extraction, scripts or external requests."""
import hashlib
import json
import re
import struct
from .history import identifier, instant, article_values, ANALYSIS_FIELDS
from .article_dates import display_date
from .agency_policy import is_excluded
from .original_contract import MAX_FILE, TYPES, clean_name, validate_tree
from .publication import public_report
from .security import Problem

MAGIC = b'REGDATA1'
CHUNK = 2 * 1024 * 1024
MAX_MANIFEST = 2 * 1024 * 1024
MAX_RECORD = 4 * 1024 * 1024
MAX_RECORD_TOTAL = 32 * 1024 * 1024
MAX_PACKAGE = 900 * 1024 * 1024
MAX_RECORDS = 200
ARTICLE_FIELDS = ('id','title','agency','category','published_at','published_at_source','created_at','link','content','analysis_result','star_rating','source_org','source_name','subcategory')
PUBLICATION_FIELDS = ('inspection_id','article_id','status','report','published_at','publication_source')

def require(value, code='invalid_transfer', status=400):
    if not value:
        raise Problem(code, status)

def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')

def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()

def sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None

def string(value, maximum, empty=True):
    require(isinstance(value, str) and (empty or bool(value)) and len(value) <= maximum
            and not any(0xD800 <= ord(c) <= 0xDFFF or ord(c)==0 for c in value))
    return value

def article(value):
    require(isinstance(value, dict))
    result = {key:value.get(key) for key in ARTICLE_FIELDS}
    identifier(result['id']); string(result['title'],1000,False); string(result['link'],4000,False)
    require(not is_excluded(result['agency']), 'excluded_agency')
    for key in ('published_at','created_at'):
        if result[key] is not None: result[key]=instant(result[key]).isoformat()
    require(result['created_at'] is not None)
    if result['content'] is not None:string(result['content'],2*1024*1024)
    require(result['published_at_source'] in (None,'source','collected_fallback'))
    for key in ('source_org','source_name','subcategory'):
        if result[key] is not None:string(result[key],1000)
    analysis = result['analysis_result']
    require(analysis is None or isinstance(analysis, dict))
    result['analysis_result'] = ({k:analysis[k] for k in ANALYSIS_FIELDS if k in analysis} or None) if analysis else None
    require(result['star_rating'] is None or type(result['star_rating']) is int and 0 <= result['star_rating'] <= 5)
    article_values({'article_id':result['id'],'record':result,'payload_sha256':digest(result)})
    display_date(result)
    return result

def publication(value, article_id):
    if value is None:return None
    require(isinstance(value, dict))
    result={k:value.get(k) for k in PUBLICATION_FIELDS}
    identifier(result['inspection_id']); require(result['article_id']==article_id)
    require(result['status'] in ('published','withdrawn'))
    result['report']=public_report(result['report'])
    result['published_at']=instant(result['published_at']).isoformat()
    require(result['publication_source'] in (None,'manual','automatic'))
    result['publication_source']=result['publication_source'] or 'manual'
    return result

def original(value):
    if value is None:return None
    require(isinstance(value, dict))
    tree=value.get('tree',[]); validate_tree(tree)
    status=value.get('body_status'); require(status in ('available','attachment_only','unavailable'))
    string(value.get('source_url'),4000)
    raw=value.get('files'); require(isinstance(raw,list) and len(raw)<=200)
    available={}; unavailable=[]
    for spec in raw:
        require(isinstance(spec,dict) and spec.get('kind') in ('attachment','image'))
        string(spec.get('name'),240); string(spec.get('source_url',''),4000)
        require(spec.get('status') in ('available','unavailable'))
        if spec['status']=='unavailable':
            unavailable.append({k:spec[k] for k in ('name','kind','status')});continue
        require(sha(spec.get('sha256')) and spec.get('extension') in TYPES)
        require(type(spec.get('bytes')) is int and 0<spec['bytes']<=MAX_FILE)
        require(spec['name']==clean_name(spec['name'],spec['extension']))
        require(spec['kind']!='image' or spec['extension'] in ('png','jpg','gif'))
        item={k:spec[k] for k in ('sha256','extension','bytes','name','kind','source_url','status')}
        previous=available.get(item['sha256'])
        if previous:
            require((previous['extension'],previous['bytes'])==(item['extension'],item['bytes']))
            if previous['kind']=='attachment':item['kind']='attachment'
        available[item['sha256']]=item
    def check_images(nodes):
        for node in nodes:
            if isinstance(node,dict):
                if node['tag']=='img':require(node['sha256'] in available and available[node['sha256']]['extension'] in ('png','jpg','gif'))
                check_images(node.get('children',[]))
    check_images(tree)
    return dict(tree=tree,body_status=status,source_url=value['source_url'],files=[
        *sorted(available.values(),key=lambda f:f['sha256']),*sorted(unavailable,key=lambda f:(f['name'],f['kind']))])

def envelope(value):
    require(isinstance(value,dict) and set(value)=={'article','original','publication'})
    a=article(value['article'])
    result=dict(article=a,original=original(value['original']),publication=publication(value['publication'],a['id']))
    require(len(encoded(result))<=MAX_RECORD)
    return result

def manifest(value):
    require(isinstance(value,dict) and set(value)=={'format','source_project','created_at','records','files'})
    require(value['format']=='regulation-delta-v1' and isinstance(value['source_project'],str)
            and re.fullmatch('[a-z0-9]{20}',value['source_project']))
    instant(value['created_at'])
    require(isinstance(value['records'],list) and 1<=len(value['records'])<=MAX_RECORDS)
    require(isinstance(value['files'],list) and len(value['files'])<=20000)
    ids=set(); hashes=set(); total=0
    for item in value['records']:
        require(isinstance(item,dict) and set(item)=={'id','base','sha256','bytes'})
        identifier(item['id']); require(item['id'] not in ids); ids.add(item['id'])
        require(item['base'] is None or sha(item['base']))
        require(sha(item['sha256']) and item['sha256'] not in hashes);hashes.add(item['sha256'])
        require(type(item['bytes']) is int and 0<item['bytes']<=MAX_RECORD);total+=item['bytes']
    require(total<=MAX_RECORD_TOTAL)
    for item in value['files']:
        require(isinstance(item,dict) and set(item)=={'sha256','bytes','extension'})
        require(sha(item['sha256']) and item['sha256'] not in hashes);hashes.add(item['sha256'])
        require(item['extension'] in TYPES and type(item['bytes']) is int and 0<item['bytes']<=MAX_FILE);total+=item['bytes']
    data=encoded(value);require(len(data)<=MAX_MANIFEST and total+len(data)+12<=MAX_PACKAGE)
    return hashlib.sha256(data).hexdigest(),data

def header(value):
    _,data=manifest(value)
    return MAGIC+struct.pack('>I',len(data))+data
