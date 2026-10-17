import copy
from types import SimpleNamespace
import pytest
from scripts.admin.repair_fss_reg_4405_4425 import repair, matches

def rows():
    return [{'id': n, 'agency': 'FSS_REG', 'link': 'https://www.fss.or.kr/fss/job/lrgRegItnPrvntc/view.do?lrgSlno='+n+'&menuNo=200489&pageIndex=1',
             'title': 'original title', 'content': None if n == '4405' else '',
             'analysis_result': {'retained': True}, 'published_at': '2026-10-01', 'category': 'regulation_notice', 'created_at': '2026-10-02'}
            for n in ('4405','4425')]

class DB:
    def __init__(self, records, concurrent=False):
        self.rows = copy.deepcopy(records)
        self.writes = []
        self.concurrent = concurrent
    def table(self, name):
        assert name == 'articles'
        db = self
        class Q:
            def __init__(self): self.filters=[]; self.payload=None; self.pattern=None
            def select(self, _): return self
            def eq(self, key, value): self.filters.append((key,value)); return self
            def is_(self, key, value): assert value == 'null'; return self.eq(key,None)
            def like(self, key, value): assert key == 'link'; self.pattern=value.strip('%'); return self
            def limit(self, limit): assert limit == 3; return self
            def update(self, payload):
                assert set(payload) == {'content'}
                self.payload=payload; return self
            def execute(self):
                if self.payload is not None and db.concurrent:
                    target=next(r for r in db.rows if r['id']==dict(self.filters)['id'])
                    target['content']='concurrent original body'
                found=[r for r in db.rows if all(r[k]==v for k,v in self.filters) and (self.pattern is None or self.pattern in r['link'])]
                if self.payload is not None:
                    assert {'id','agency','link','content'} == set(dict(self.filters))
                    db.writes.append(copy.deepcopy(self.payload))
                    for row in found: row.update(self.payload)
                return SimpleNamespace(data=copy.deepcopy(found[:3]))
        return Q()

def fetch(*_): return 'verified original amendment body ' * 5

def test_read_only_does_not_fetch_or_write():
    db=DB(rows())
    result=repair(db, lambda *_: pytest.fail('must not fetch'), {}, apply=False)
    assert [r['status'] for r in result] == ['missing_read_only'] * 2
    assert db.writes == []

def test_apply_only_content_and_preserves_metadata():
    original=rows(); db=DB(original)
    result=repair(db,fetch,{},apply=True)
    assert [r['status'] for r in result] == ['repaired'] * 2
    assert len(db.writes)==2
    for before,after in zip(original,db.rows):
        assert {k:v for k,v in before.items() if k!='content'} == {k:v for k,v in after.items() if k!='content'}
        assert after['content']==fetch()

def test_existing_body_is_preserved_without_fetch():
    records=rows()
    for row in records: row['content']='already repaired'
    db=DB(records)
    result=repair(db,lambda *_: pytest.fail('must not fetch'),{},apply=True)
    assert [r['status'] for r in result] == ['already_present'] * 2
    assert db.writes==[]

def test_concurrent_body_is_never_overwritten():
    db=DB(rows(),concurrent=True)
    result=repair(db,fetch,{},apply=True)
    assert all(r['status']=='concurrently_filled_preserved' for r in result)
    assert all(r['content']=='concurrent original body' for r in db.rows)

@pytest.mark.parametrize('records', [rows()[:1],rows()+[rows()[0]]])
def test_missing_or_ambiguous_target_stops_before_any_write(records):
    db=DB(records)
    with pytest.raises(RuntimeError,match='target_missing_or_ambiguous'):
        repair(db,fetch,{},apply=True)
    assert db.writes==[]

@pytest.mark.parametrize('body',[None,'','title only','[Short Content] ' + 'x'*80])
def test_bad_extraction_never_writes(body):
    db=DB(rows())
    with pytest.raises(RuntimeError,match='body_not_verified'):
        repair(db,lambda *_:body,{},apply=True)
    assert db.writes==[]

def test_identity_does_not_match_prefix_or_other_domain():
    assert matches(rows()[0]['link'],'4405')
    assert not matches(rows()[0]['link'].replace('4405','44050'),'4405')
    assert not matches(rows()[0]['link'].replace('www.fss.or.kr','example.test'),'4405')
