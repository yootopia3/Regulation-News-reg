"""Offline regressions for partial cycles and non-destructive persistence."""

import copy
import logging
import runpy
from types import SimpleNamespace

import pytest

from src.collectors.result import CollectionResult, FailureKind
from src.pipeline import Pipeline, PipelineRunError
from tests.unit.pipeline.test_run import (
    FakeAnalyzer, FakeNotifier, FakeScraper, FakeSupabase, _kfb_item, _rss_item,
)


class MemoryDB(FakeSupabase):
    """Model conflict-ignore and column-selective UPDATE, not destructive upsert."""

    def __init__(self, row=None, fail=None):
        super().__init__()
        self.row = copy.deepcopy(row)
        self.fail = fail
        self.writes = []

    def table(self, name):
        base = super().table(name)
        db = self

        class Table:
            select = base.select

            def upsert(self, payload, *, on_conflict, ignore_duplicates=False):
                class Insert:
                    def execute(self):
                        if db.fail == 'insert':
                            raise RuntimeError('insert failed')
                        db.writes.append(('insert', copy.deepcopy(payload)))
                        if db.row is None or not ignore_duplicates:
                            db.row = copy.deepcopy(payload)
                        return SimpleNamespace(data=[])
                assert on_conflict == 'dedup_key'
                assert ignore_duplicates is True
                return Insert()

            def update(self, payload):
                class Update:
                    def eq(self, column, value):
                        assert column == 'dedup_key'
                        self.value = value
                        return self

                    def execute(self):
                        if db.fail == 'update':
                            raise RuntimeError('update failed')
                        db.writes.append(('update', copy.deepcopy(payload)))
                        assert db.row['dedup_key'] == self.value
                        db.row.update(copy.deepcopy(payload))
                        return SimpleNamespace(data=[db.row])
                return Update()

            def insert(self, payload):
                class Insert:
                    def execute(self):
                        if db.fail == 'insert':
                            raise RuntimeError('insert failed')
                        db.row = copy.deepcopy(payload)
                        db.inserted.append(copy.deepcopy(payload))
                        return SimpleNamespace(data=[db.row])
                return Insert()

        return Table()


@pytest.fixture
def make_pipe(monkeypatch):
    monkeypatch.setattr('src.pipeline.collect_all_rss', lambda: [])
    monkeypatch.setattr('src.pipeline.collect_kfb_rss_first', lambda *a, **k: [])
    monkeypatch.setattr('src.config.settings.load_env', lambda: None)
    monkeypatch.delenv('GEMINI_ENABLED', raising=False)

    def make(db=None, scraper=None):
        return Pipeline('config/agencies.json', analyzer=FakeAnalyzer(),
                        notifier=FakeNotifier(), db=db or FakeSupabase(),
                        scraper=scraper or FakeScraper())
    return make


@pytest.mark.parametrize('body', [None, '', '   '])
@pytest.mark.parametrize('analysis', [None, {}, {'analysis_status': 'ANALYSIS_FAILED'}])
def test_existing_body_and_analysis_survive_unavailable_results(make_pipe, body, analysis):
    old = {**_kfb_item(), 'content': 'previous body',
           'analysis_result': {'summary': ['previous'], 'detailed_report': 'cached'}}
    db = MemoryDB(old)
    pipe = make_pipe(db=db)
    item = {**_kfb_item(), 'content': body, 'analysis_result': analysis}
    assert pipe._save_item(item) is True
    assert db.row['content'] == old['content']
    assert db.row['analysis_result'] == old['analysis_result']
    assert 'content' not in db.writes[1][1]
    assert 'analysis_result' not in db.writes[1][1]


def test_pdf_only_result_does_not_replace_existing_analysis(make_pipe):
    old = {**_kfb_item(), 'content': 'previous', 'analysis_result': {'summary': ['keep']}}
    db = MemoryDB(old)
    pipe = make_pipe(db=db)
    assert pipe._save_item({**_kfb_item(), 'pdf_url': 'https://example.test/new.pdf'})
    assert db.row['analysis_result'] == {'summary': ['keep']}


def test_new_empty_body_keeps_metadata_and_pdf_without_inventing_content(make_pipe):
    db = MemoryDB()
    pipe = make_pipe(db=db)
    assert pipe._save_item({**_kfb_item(), 'pdf_url': 'https://example.test/new.pdf'})
    assert db.row['content'] == ''
    assert db.row['title'] == _kfb_item()['title']
    assert db.row['analysis_result'] == {'pdf_url': 'https://example.test/new.pdf'}


def test_successful_refresh_replaces_available_fields_without_mutating_input(make_pipe):
    old = {**_kfb_item(), 'content': 'previous', 'analysis_result': {'summary': ['old']}}
    db = MemoryDB(old)
    item = {**_kfb_item(), 'content': 'new body',
            'analysis_result': {'analysis_status': 'ANALYZED', 'summary': ['new']},
            'pdf_url': 'https://example.test/new.pdf'}
    before = copy.deepcopy(item)
    assert make_pipe(db=db)._save_item(item)
    assert db.row['content'] == 'new body'
    assert db.row['analysis_result']['summary'] == ['new']
    assert db.row['analysis_result']['pdf_url'] == item['pdf_url']
    assert item == before


@pytest.mark.parametrize('phase', ['insert', 'update'])
def test_write_failures_are_reported_and_existing_values_preserved(make_pipe, phase):
    old = {**_kfb_item(), 'content': 'keep', 'analysis_result': {'summary': ['keep']}}
    db = MemoryDB(old, fail=phase)
    assert make_pipe(db=db)._save_item(_kfb_item()) is False
    assert db.row == old


def test_empty_sources_are_successful_not_failed(make_pipe):
    pipe = make_pipe()
    report = pipe.run()
    assert len(report['sources']) == 11
    assert all(s['status'] == 'empty' for s in report['sources'].values())


@pytest.mark.parametrize('kind', list(FailureKind))
def test_zero_failed_source_is_not_normal_empty_and_healthy_source_is_saved(
    make_pipe, monkeypatch, caplog, kind,
):
    batch = CollectionResult([_rss_item()])
    batch.sources = {'FSC': CollectionResult(failures=[kind]),
                     'MOEF': CollectionResult([_rss_item()]),
                     'MAFRA': CollectionResult()}
    monkeypatch.setattr('src.pipeline.collect_all_rss', lambda: batch)
    pipe = make_pipe()
    with caplog.at_level(logging.INFO), pytest.raises(PipelineRunError, match='FSC'):
        pipe.run()
    assert pipe.source_results['FSC']['status'] == 'failed'
    assert pipe.source_results['FSC']['failures'] == [kind]
    assert pipe.source_results['MAFRA']['status'] == 'empty'
    assert pipe.source_results['MOEF']['saved'] == 1
    assert len(pipe.supabase.inserted) == 1
    assert 'Collection summary:' in caplog.text
    assert 'completed successfully' not in caplog.text


def test_all_failed_zero_items_still_fails(make_pipe, monkeypatch):
    batch = CollectionResult()
    batch.sources = {'FSC': CollectionResult(failures=[FailureKind.CONNECTION])}
    monkeypatch.setattr('src.pipeline.collect_all_rss', lambda: batch)
    with pytest.raises(PipelineRunError):
        make_pipe().run()


def test_partial_page_failure_preserves_candidates_and_fails_cycle(make_pipe):
    class PartialScraper(FakeScraper):
        def fetch_list_items(self, agency, last_crawled_date=None):
            if agency['code'] == 'FSS':
                return CollectionResult([_rss_item('FSS')], failures=[FailureKind.CONNECTION])
            return []
    scraper = PartialScraper(content_by_link={_rss_item()['link']: 'real body'})
    pipe = make_pipe(scraper=scraper)
    with pytest.raises(PipelineRunError, match='FSS'):
        pipe.run()
    assert pipe.source_results['FSS']['saved'] == 1
    assert pipe.source_results['FSS']['collected'] == 1
    assert pipe.source_results['FSS']['status'] == 'failed'


def test_missing_body_new_fss_metadata_saved_but_cycle_degraded(make_pipe):
    pipe = make_pipe(scraper=FakeScraper(list_items_by_agency={'FSS': [_rss_item('FSS')]}))
    with pytest.raises(PipelineRunError, match='FSS'):
        pipe.run()
    row = pipe.supabase.inserted[0]
    assert row['content'] == ''
    assert row['title'] == 't1'
    assert pipe.source_results['FSS']['body_failed'] == 1
    assert pipe.source_results['FSS']['collection_status'] == 'success'
    assert pipe.source_results['FSS']['status'] == 'failed'


def test_kfb_duplicate_with_failed_body_preserves_existing_data(make_pipe, monkeypatch):
    old = {**_kfb_item(), 'content': 'keep body', 'analysis_result': {'summary': ['keep']}}
    db = MemoryDB(old)
    db.existing_links.add(old['link'])
    monkeypatch.setattr('src.pipeline.collect_kfb_rss_first', lambda *a, **k: [_kfb_item()])
    pipe = make_pipe(db=db)
    with pytest.raises(PipelineRunError, match='KFB'):
        pipe.run()
    assert db.row == old
    assert pipe.source_results['KFB']['saved'] == 1
    assert pipe.source_results['KFB']['body_failed'] == 1


def test_save_failure_is_counted_and_does_not_notify(make_pipe, monkeypatch):
    monkeypatch.setattr('src.pipeline.collect_all_rss', lambda: [_rss_item()])
    pipe = make_pipe(db=MemoryDB(fail='insert'))
    pipe.analyzer = FakeAnalyzer({'analysis_status': 'ANALYZED'})
    with pytest.raises(PipelineRunError, match='MOEF'):
        pipe.run()
    assert pipe.source_results['MOEF']['save_failed'] == 1
    assert pipe.source_results['MOEF']['saved'] == 0
    assert pipe.notifier.sent == []


def test_no_db_cannot_report_success_even_with_no_items(make_pipe):
    pipe = make_pipe()
    pipe.supabase = None
    with pytest.raises(PipelineRunError, match='db_unavailable'):
        pipe.run()


def test_cycle_state_resets_after_recovery(make_pipe, monkeypatch):
    pipe = make_pipe()
    batch = CollectionResult()
    batch.sources = {'FSC': CollectionResult(failures=[FailureKind.HTTP])}
    monkeypatch.setattr('src.pipeline.collect_all_rss', lambda: batch)
    with pytest.raises(PipelineRunError):
        pipe.run()
    monkeypatch.setattr('src.pipeline.collect_all_rss', lambda: [])
    assert pipe.run()['sources']['FSC']['status'] == 'empty'


def test_main_exits_nonzero_on_incomplete_cycle(monkeypatch):
    class FailedPipeline:
        def __init__(self, config_path):
            pass

        def run(self):
            raise PipelineRunError('incomplete cycle')

    monkeypatch.setattr('src.pipeline.Pipeline', FailedPipeline)
    monkeypatch.setattr('src.config.settings.load_env', lambda: None)
    monkeypatch.setattr('src.utils.logger.setup_logger', lambda: logging.getLogger('test-main'))
    with pytest.raises(SystemExit) as result:
        runpy.run_module('src.main', run_name='__main__')
    assert result.value.code == 1


def test_new_insert_then_failed_update_is_reported_and_retry_is_safe(make_pipe):
    db = MemoryDB(fail='update')
    pipe = make_pipe(db=db)
    item = {**_kfb_item(), 'content': 'new body'}
    assert pipe._save_item(item) is False
    # Two requests are not a transaction: the insert can already have succeeded.
    assert db.row['content'] == 'new body'
    db.fail = None
    assert pipe._save_item(_kfb_item()) is True
    assert db.row['content'] == 'new body'


def test_unconfirmed_empty_write_response_is_failure(make_pipe):
    from unittest.mock import MagicMock
    db = MagicMock()
    db.table.return_value.insert.return_value.execute.return_value.data = []
    db.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []
    pipe = make_pipe(db=db)
    assert pipe._save_item(_rss_item()) is False
    assert pipe._save_item(_kfb_item()) is False


def test_unknown_collection_method_is_not_silently_ignored(make_pipe):
    pipe = make_pipe()
    pipe.agency_map = {'BROKEN': {'code': 'BROKEN', 'collection_method': 'typo'}}
    with pytest.raises(PipelineRunError, match='BROKEN'):
        pipe.run()
    assert pipe.source_results['BROKEN']['failures'] == [FailureKind.CONFIG]


def test_failed_save_does_not_stop_later_items(make_pipe, monkeypatch):
    items = [_rss_item(link='https://example.test/1'), _rss_item(link='https://example.test/2')]
    monkeypatch.setattr('src.pipeline.collect_all_rss', lambda: items)
    pipe = make_pipe()
    original_save = pipe._save_item
    pipe._save_item = lambda item: False if item['link'].endswith('/1') else original_save(item)
    with pytest.raises(PipelineRunError, match='MOEF'):
        pipe.run()
    assert pipe.source_results['MOEF']['saved'] == 1
    assert pipe.source_results['MOEF']['save_failed'] == 1
    assert pipe.supabase.inserted[0]['link'].endswith('/2')


def test_failed_dedup_read_degrades_final_status(make_pipe):
    from unittest.mock import MagicMock
    db = MagicMock()
    db.table.return_value.select.return_value.range.return_value.execute.side_effect = RuntimeError('DB read failed')
    db.table.return_value.select.return_value.eq.return_value.range.return_value.execute.return_value.data = []
    db.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []
    pipe = make_pipe(db=db)
    with pytest.raises(PipelineRunError, match='existing_links'):
        pipe.run()


def test_real_postgrest_requests_ignore_conflicts_and_omit_unavailable_columns(make_pipe):
    """Verify the SDK wire contract with MockTransport, never a real database."""
    import httpx
    from postgrest import SyncPostgrestClient

    captured = []

    def handle(request):
        import json
        captured.append(request)
        if request.method == 'POST':
            return httpx.Response(201, json=[])
        return httpx.Response(200, json=[json.loads(request.content)])

    client = SyncPostgrestClient('https://example.test/rest/v1')
    client.session.close()
    client.session = httpx.Client(transport=httpx.MockTransport(handle),
                                 base_url='https://example.test/rest/v1/')
    try:
        assert make_pipe(db=client)._save_item(_kfb_item())
        import json
        assert [r.method for r in captured] == ['POST', 'PATCH']
        assert 'resolution=ignore-duplicates' in captured[0].headers['prefer']
        assert captured[0].url.params['on_conflict'] == 'dedup_key'
        assert captured[1].url.params['dedup_key'] == 'eq.' + _kfb_item()['dedup_key']
        assert 'content' not in json.loads(captured[1].content)
        assert 'analysis_result' not in json.loads(captured[1].content)
    finally:
        client.session.close()


def test_real_empty_body_scraper_cannot_overwrite_old_kfb_content(make_pipe, monkeypatch):
    from src.collectors import content_scraper
    from src.collectors.scraper import ContentScraper
    monkeypatch.setattr(content_scraper.time, 'sleep', lambda _: None)
    monkeypatch.setattr(content_scraper.http, 'fetch', lambda *a, **k: SimpleNamespace(
        content=b'<html><div class="view_cont">  </div></html>'))
    old = {**_kfb_item(), 'content': 'keep body', 'analysis_result': {'summary': ['keep']}}
    db = MemoryDB(old)
    pipe = make_pipe(db=db, scraper=ContentScraper())
    pipe._process_single_item(_kfb_item(), {old['link']}, set())
    assert db.row == old
    assert pipe.source_results['KFB']['body_failed'] == 1
