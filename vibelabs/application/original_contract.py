"""Bounded passive document format shared by offline preparation and import."""
import io
import re
import zipfile

MAX_FILE = 128 * 1024 * 1024
TAGS = {'div','p','br','strong','em','u','sup','sub','h2','h3','h4','ul','ol','li','table','thead','tbody','tfoot','tr','td','th','blockquote','img'}
TYPES = {'pdf':'application/pdf','hwp':'application/x-hwp','hwpx':'application/hwp+zip',
    'doc':'application/msword','docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'xls':'application/vnd.ms-excel','xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'ppt':'application/vnd.ms-powerpoint','pptx':'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'zip':'application/zip','txt':'text/plain','md':'text/markdown','csv':'text/csv','png':'image/png','jpg':'image/jpeg','gif':'image/gif'}

def decode_filename(value):
    # HTTP headers from some agencies carry UTF-8 bytes interpreted as Latin-1.
    try:return str(value).encode('latin-1').decode('utf-8')
    except (UnicodeEncodeError,UnicodeDecodeError):return str(value)

def clean_name(value, extension):
    value=re.sub(r'\s*\(파일크기[:_].*$', '',decode_filename(value)).strip()
    value=re.sub(r'[\x00-\x1f\x7f/\\:*?"<>|]', '_', str(value)).strip(' .')
    value=re.sub(r'[\u202a-\u202e\u2066-\u2069]', '',value)
    if not value.lower().endswith('.'+extension):value=(value.rsplit('.',1)[0] if re.search(r'\.[a-z0-9]{2,5}$',value,re.I) else value)+'.'+extension
    # Keep the UTF-8 download filename below common filesystem component limits.
    stem=value[:-(len(extension)+1)] or '첨부파일'
    while len((stem+'.'+extension).encode('utf-8'))>230:stem=stem[:-1]
    return stem+'.'+extension

def file_type(data, name):
    if not 0<len(data)<=MAX_FILE:raise ValueError('file_size')
    hint=re.sub(r'\s*\(파일크기:.*$', '',name).strip().rsplit('.',1)[-1].lower()
    if data.startswith(b'%PDF-'):return 'pdf'
    if data.startswith(bytes.fromhex('d0cf11e0a1b11ae1')):
        if hint in {'hwp','doc','xls','ppt'}:return hint
        # Some agency files are named .hwpx while their bytes are legacy HWP.
        import olefile
        try:
            with olefile.OleFileIO(io.BytesIO(data)) as ole:
                if ole.exists('FileHeader') and ole.openstream('FileHeader').read(32).startswith(b'HWP Document File'):return 'hwp'
                for stream,ext in [('WordDocument','doc'),('Workbook','xls'),('Book','xls'),('PowerPoint Document','ppt')]:
                    if ole.exists(stream):return ext
        except (OSError,IOError):pass
    if data.startswith(b'PK'):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names=set(z.namelist())
            if len(names)>10000:raise ValueError('archive_entries')
            if 'mimetype' in names and z.getinfo('mimetype').file_size<=128 and z.read('mimetype').strip()==b'application/hwp+zip':return 'hwpx'
            if '[Content_Types].xml' in names:
                for item,ext in [('word/document.xml','docx'),('xl/workbook.xml','xlsx'),('ppt/presentation.xml','pptx')]:
                    if item in names:return ext
            if hint=='zip':return 'zip'
    if data.startswith(b'\x89PNG\r\n\x1a\n'):return 'png'
    if data.startswith(b'\xff\xd8\xff'):return 'jpg'
    if data.startswith((b'GIF87a',b'GIF89a')):return 'gif'
    if hint in {'txt','md','csv'} and not data.lstrip().startswith(b'<') and b'\x00' not in data:return hint
    raise ValueError('unsupported_file_type')

def validate_tree(tree):
    count=0
    def visit(node,depth):
        nonlocal count
        count+=1
        if count>40000 or depth>30:raise ValueError('document_too_complex')
        if isinstance(node,str):
            if len(node)>200000:raise ValueError('text_too_long')
            return
        if not isinstance(node,dict) or node.get('tag') not in TAGS:raise ValueError('invalid_node')
        if not set(node).issubset({'tag','children','colspan','rowspan','sha256','alt','align'}):raise ValueError('invalid_attribute')
        for key in ['colspan','rowspan']:
            if key in node and (node['tag'] not in {'td','th'} or type(node[key]) is not int or not 1<=node[key]<=100):raise ValueError('invalid_span')
        if 'align' in node and node['align'] not in {'left','center','right'}:raise ValueError('invalid_alignment')
        if node['tag']=='img':
            if not re.fullmatch('[0-9a-f]{64}',node.get('sha256','')) or not isinstance(node.get('alt'),str) or len(node['alt'])>500:raise ValueError('invalid_image')
        elif 'sha256' in node or 'alt' in node:raise ValueError('invalid_image_attribute')
        if not isinstance(node.get('children',[]),list):raise ValueError('invalid_children')
        for child in node.get('children',[]):visit(child,depth+1)
    if not isinstance(tree,list):raise ValueError('invalid_document')
    for node in tree:visit(node,0)
    return count
