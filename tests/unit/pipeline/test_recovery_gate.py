"""Bounded repair and production handoff safety, without any external services."""
import copy
import logging
import runpy
from types import SimpleNamespace

import pytest

from src.collectors.result import CollectionResult, FailureKind
from src.pipeline import BODY_RETRY_LIMIT, Pipeline, PipelineRunError
from tests.unit.pipeline.test_run import FakeAnalyzer, FakeNotifier, FakeScraper, FakeSupabase, _rss_item, _sanction_item


@pytest.fixture
def pipe(monkeypatch):
    monkeypatch.setattr('src.pipeline.collect_all_rss', lambda: [])
    monkeypatch.setattr('src.pipeline.collect_kfb_rss_first', lambda *a, **k: [])
    return Pipeline('config/agencies.json', db=FakeSupabase(), analyzer=FakeAnalyzer(),
                    notifier=FakeNotifier(), scraper=FakeScraper())


def sanction_candidate(pipe, duplicate=False):
    item = _sanction_item()
    pipe.scraper.sanction_items_by_agency = {'FSS_SANCTION': [item]}
    if duplicate:
        pipe.supabase.sanction_links_by_agency = {'FSS_SANCTION': [item['link']]}


@pytest.mark.parametrize('duplicate', [False, True])
def test_partial_failure_allows_only_confirmed_sanction_work(pipe, monkeypatch, duplicate):
    sanction_candidate(pipe, duplicate)
    batch = CollectionResult()
    batch.sources = {'MOEF': CollectionResult(failures=[FailureKind.CONNECTION])}
    monkeypatch.setattr('src.pipeline.collect_all_rss', lambda: batch)
    with pytest.raises(PipelineRunError):
        pipe.run()
    assert pipe.automation_ready is True
    assert pipe.source_results['FSS_SANCTION']['duplicates' if duplicate else 'saved'] == 1


def test_body_only_failure_still_allows_confirmed_sanctions(pipe):
    sanction_candidate(pipe)
    pipe.scraper.list_items_by_agency = {'FSS': [_rss_item('FSS')]}
    with pytest.raises(PipelineRunError):
        pipe.run()
    assert pipe.automation_ready is True
    assert pipe.source_results['FSS']['body_failed'] == 1


def test_no_sanction_candidate_does_not_unlock_analysis(pipe):
    assert pipe.run()['automation_ready'] is False


def test_save_failure_closes_gate_even_with_existing_sanction(pipe):
    sanction_candidate(pipe, duplicate=True)
    pipe.scraper.list_items_by_agency = {'FSS': [_rss_item('FSS')]}
    pipe._save_item = lambda _: False
    with pytest.raises(PipelineRunError):
        pipe.run()
    assert pipe.automation_ready is False


def test_whole_db_failure_closes_gate(pipe):
    sanction_candidate(pipe)
    pipe.supabase = None
    with pytest.raises(PipelineRunError):
        pipe.run()
    assert pipe.automation_ready is False


def test_source_config_failure_closes_gate(pipe):
    sanction_candidate(pipe)
    pipe.agency_map['BROKEN'] = {'code': 'BROKEN', 'collection_method': 'invalid'}
    with pytest.raises(PipelineRunError):
        pipe.run()
    assert pipe.automation_ready is False


def test_setup_read_failure_closes_gate(pipe):
    sanction_candidate(pipe, duplicate=True)
    def fail_read():
        pipe.setup_failures.append('existing_links')
        return set()
    pipe._load_existing_links = fail_read
    with pytest.raises(PipelineRunError):
        pipe.run()
    assert pipe.automation_ready is False


@pytest.mark.parametrize('ready', [False, True])
def test_main_transmits_bounded_boolean_on_partial_exit(monkeypatch, tmp_path, ready):
    class Partial:
        def __init__(self, _):
            self.automation_ready = ready
        def run(self):
            raise PipelineRunError('partial')
    output = tmp_path / 'output'
    monkeypatch.setenv('GITHUB_OUTPUT', str(output))
    monkeypatch.setattr('src.pipeline.Pipeline', Partial)
    monkeypatch.setattr('src.config.settings.load_env', lambda: None)
    monkeypatch.setattr('src.utils.logger.setup_logger', lambda: logging.getLogger('gate-test'))
    with pytest.raises(SystemExit) as exc:
        runpy.run_module('src.main', run_name='__main__')
    assert exc.value.code == 1
    assert output.read_text() == f"automation_ready={str(ready).lower()}\n"


class RepairDB:
    def __init__(self, rows, concurrent=False, fail=False):
        self.rows = copy.deepcopy(rows)
        self.concurrent = concurrent
        self.fail = fail
        self.filters = []
        self.updates = []

    def table(self, _):
        db = self
        class Query:
            payload = None
            link = None
            def select(self, columns):
                assert columns == 'agency,title,link'
                return self
            def update(self, payload):
                assert set(payload) == {'content'}
                self.payload = payload
                return self
            def eq(self, key, value):
                assert key == 'link'
                self.link = value
                return self
            def in_(self, key, values):
                db.filters.append((key, values))
                return self
            def or_(self, expression):
                assert expression == 'content.is.null,content.eq.'
                db.filters.append(('empty_only', expression))
                return self
            def gte(self, key, value):
                assert key == 'created_at'
                db.filters.append((key, value))
                return self
            def order(self, key, desc=False):
                return self
            def limit(self, count):
                assert count == BODY_RETRY_LIMIT
                return self
            def execute(self):
                if db.fail:
                    raise RuntimeError('DB unavailable')
                if self.payload is None:
                    return SimpleNamespace(data=copy.deepcopy(db.rows))
                db.updates.append((self.link, self.payload))
                return SimpleNamespace(data=[] if db.concurrent else [self.payload])
        return Query()


def repair_rows(count=1):
    return [{'agency': 'FSS', 'title': 'real title', 'link': f'https://example.test/{i}'} for i in range(count)]


def test_recent_repair_is_bounded_and_only_updates_body(pipe):
    rows = repair_rows(8)
    pipe.supabase = RepairDB(rows)
    pipe.scraper.content_by_link = {r['link']: 'real full body' for r in rows}
    pipe._repair_empty_bodies()
    assert len(pipe.supabase.updates) == BODY_RETRY_LIMIT
    assert pipe.source_results['FSS']['body_repaired'] == BODY_RETRY_LIMIT
    assert ('agency', ['FSC', 'FSS', 'KFB']) in pipe.supabase.filters
    assert any(k == 'created_at' for k, _ in pipe.supabase.filters)
    assert all(set(payload) == {'content'} for _, payload in pipe.supabase.updates)


def test_repair_preserves_concurrently_filled_body(pipe):
    pipe.supabase = RepairDB(repair_rows(), concurrent=True)
    pipe.scraper.content_by_link = {'https://example.test/0': 'new body'}
    pipe._repair_empty_bodies()
    assert pipe.source_results['FSS']['body_repaired'] == 0
    assert pipe.source_results['FSS']['save_failed'] == 0


def test_failed_body_retry_never_writes_title_or_empty_text(pipe):
    pipe.supabase = RepairDB(repair_rows())
    pipe._repair_empty_bodies()
    assert pipe.supabase.updates == []
    assert pipe.source_results['FSS']['body_failed'] == 1


def test_body_is_not_requested_twice_in_same_cycle(pipe):
    pipe.supabase = RepairDB(repair_rows())
    pipe.body_attempted.add('https://example.test/0')
    pipe._repair_empty_bodies()
    assert pipe.supabase.updates == []
    assert pipe.source_results == {}


def test_retry_db_read_failure_is_not_silent(pipe):
    pipe.supabase = RepairDB([], fail=True)
    pipe._repair_empty_bodies()
    assert pipe.setup_failures == ['body_retry_read']


def test_legacy_fsc_rss_link_matches_new_html_identity(pipe):
    pipe.supabase.existing_links.add('https://www.fsc.go.kr/no010101/87869?curPage=1')
    assert 'https://www.fsc.go.kr/no010101/87869' in pipe._load_existing_links()
