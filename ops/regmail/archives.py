"""One Windows-compatible ZIP per import; split only after measuring compression."""
import json,struct,tempfile,zipfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from application import transfer_contract as c
from transfer_export import export

MAX_ATTACHMENTS=25_000_000  # Gmail personal-account attachment limit, before MIME.
MAX_MESSAGE=35_000_000  # Below Gmail SMTP's advertised SIZE; checked again at send.
GUIDE_RESERVE=64*1024

@contextmanager
def package_stream(path):
    path=Path(path);c.require(path.stat().st_size<=c.MAX_PACKAGE)
    if path.suffix.lower()!='.zip':
        with path.open('rb') as stream:yield stream
        return
    # No extraction, paths, extra entries or encrypted archives are accepted.
    with zipfile.ZipFile(path) as archive:
        entries=archive.infolist();c.require(len(entries)==1,'invalid_mail_archive')
        item=entries[0];name=item.filename
        c.require(name.endswith('.regdata') and not any(ch in name for ch in '/\\:')
            and not item.is_dir() and not item.flag_bits&1
            and item.compress_type in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED)
            and 12<item.file_size<=c.MAX_PACKAGE,'invalid_mail_archive')
        with archive.open(item) as stream:yield stream

def compressed_export(project,values,paths,baseline,output,*,max_bytes,max_records):
    c.require(12<max_bytes<=MAX_ATTACHMENTS and 0<max_records<=c.MAX_RECORDS)
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    by_id={v['article']['id']:v for v in values};c.require(len(by_id)==len(values))
    written=[];stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
    def fit(batch):
        with tempfile.TemporaryDirectory(prefix='.mail-pack-',dir=output) as temporary:
            root=Path(temporary)
            result=export(project,batch,paths,baseline,root/'raw',max_bytes=c.MAX_PACKAGE,max_records=max_records)
            for raw in result['files']:
                with raw.open('rb') as stream:
                    c.require(stream.read(8)==c.MAGIC)
                    size=struct.unpack('>I',stream.read(4))[0]
                    c.require(0<size<=c.MAX_MANIFEST)
                    manifest=json.loads(stream.read(size));ident,_=c.manifest(manifest)
                name=f'규제자료_{stamp}_{len(written)+1:03d}_{ident[:12]}.regdata'
                trial=root/'candidate.zip'
                with zipfile.ZipFile(trial,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
                    archive.write(raw,arcname=name)
                if trial.stat().st_size<=max_bytes:
                    target=output/(name+'.zip');c.require(not target.exists())
                    trial.replace(target);written.append(target)
                else:
                    subset=[by_id[r['id']] for r in manifest['records']]
                    c.require(len(subset)>1,'article_package_too_large',409)
                    middle=len(subset)//2;fit(subset[:middle]);fit(subset[middle:])
    try:fit(values)
    except BaseException:
        for path in written:path.unlink(missing_ok=True)
        raise
    changed=sum(c.digest(v)!=baseline['records'].get(v['article']['id']) for v in values)
    return dict(changed=changed,unchanged=len(values)-changed,files=written,
        absent=len(set(baseline['records'])-set(by_id)))
