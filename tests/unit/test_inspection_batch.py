from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from src.services.sanction_inspections.batch import config, run_batch


def test_batch_is_bounded_and_continues_after_publication_transport_failure():
    db, client = Mock(), Mock()
    query = db.table.return_value
    for method in ('select', 'eq', 'order', 'limit'):
        getattr(query, method).return_value = query
    query.execute.return_value = SimpleNamespace(data=[{'id':'one'}, {'id':'two'}])
    worker = Mock(return_value=True)
    publisher = Mock(side_effect=[RuntimeError('PRIVATE_CANARY'), 'published'])
    counts=run_batch(db,client,2,'2026-09-17T00:00:00Z','https://example.test/api','token',worker,publisher)
    assert worker.call_count == 2
    assert counts['published'] == 1 and counts['publication_errors'] == 1
    assert 'PRIVATE_CANARY' not in str(counts)
    assert db.rpc.call_args.args[0] == 'inspection_auto_enqueue'


def test_disabled_batch_rejects_before_database_access(monkeypatch):
    monkeypatch.delenv('SANCTION_AUTOMATION_ENABLED',raising=False)
    with pytest.raises(ValueError,match='disabled'): config()


@pytest.mark.parametrize('site',['http://example.test','https://user:password@example.test','https://example.test/other'])
def test_endpoint_must_be_https_origin(monkeypatch,site):
    monkeypatch.setenv('SANCTION_AUTOMATION_ENABLED','true')
    monkeypatch.setenv('SANCTION_AUTOMATION_SINCE','2026-09-17T00:00:00Z')
    monkeypatch.setenv('SANCTION_WEB_URL',site)
    monkeypatch.setenv('SANCTION_AUTOMATION_TOKEN','x'*32)
    with pytest.raises(ValueError,match='invalid_endpoint'): config()
