"""Read the source catalog while preserving already-delivered originals."""
import os
from pathlib import Path
from urllib.parse import urlsplit
from .delivery import c
from transfer_export import catalog,refresh_originals
from transfer_fetch import OriginalCache,p

class DeliveredCache(OriginalCache):
    def __init__(self,root,baseline,values):
        super().__init__(root,Path(root)/'no-history-seed')
        self.baseline=baseline
        self.prior={k:v['original'] for k,v in values.items() if v['original']}
        for original in self.prior.values():
            for item in original['files']:
                if self.delivered(item):self.known[p.canonical(item['source_url'])]=item
    def delivered(self,item):
        return item.get('status')=='available' and self.baseline['files'].get(item['sha256'])=={k:item[k] for k in ('bytes','extension')}
    def download_locked(self,url,name,kind,prefetched=None):
        old=self.known.get(p.canonical(url))
        value=super().download_locked(url,name,kind,prefetched)
        # Existing bytes are already in the bank. Only new bytes need a local
        # path for packaging. Never apply this fallback to an unknown digest.
        if value['status']=='unavailable' and old and self.delivered(old):return {**old,'kind':kind}
        return value

def read_source(baseline,root,values,progress=print):
    host=urlsplit(os.environ['SUPABASE_URL']).hostname
    c.require(host==baseline['source_project']+'.supabase.co','source_project_conflict',409)
    from src.db.client import get_supabase_client
    client=get_supabase_client();first=catalog(client)
    c.require(c.digest(first)==c.digest(catalog(client)),'source_changing',409)
    cache=DeliveredCache(root,baseline,values)
    envelopes=refresh_originals(first[0],first[1],cache,progress,baseline=baseline)
    c.require(c.digest(first)==c.digest(catalog(client)),'source_changing',409)
    return baseline['source_project'],envelopes,cache.paths,cache.warnings

