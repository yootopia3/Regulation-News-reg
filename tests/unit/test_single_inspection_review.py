from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.services.sanction_inspections.models import InspectionError
from src.services.sanction_inspections.single_review import review_one

ARTICLE = '00000000-0000-4000-8000-000000000001'
OTHER = '00000000-0000-4000-8000-000000000002'
MASTER = '00000000-0000-4000-8000-000000000003'
JOB = '00000000-0000-4000-8000-000000000004'
FINGERPRINT = 'a' * 64
VERSIONS = {MASTER: 1}


def fixture():
    db, client = MagicMock(), MagicMock()
    queue = [{'id': JOB, 'article_id': ARTICLE, 'status': 'queued', 'versions': VERSIONS}]
    master = [{'id': MASTER, 'revision': 1, 'fingerprint': FINGERPRINT}]
    final = {'status': 'needs_review', 'versions': VERSIONS,
             'result': {'analysis_basis': 'duty_master', 'master_fingerprint': FINGERPRINT}}
    db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = master
    db.table.return_value.select.return_value.in_.return_value.limit.return_value.execute.return_value.data = queue
    db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = final
    return db, client, queue, master, final


def test_only_atomic_scoped_claim_is_used_and_nothing_is_published():
    db, client, *_ = fixture()
    db.rpc.return_value.execute.return_value = SimpleNamespace(data={'id': JOB})

    def worker(scoped, passed_client):
        assert passed_client is client
        scoped.rpc('inspection_claim', {}).execute()
        scoped.rpc('inspection_finish', {'p_id': JOB}).execute()
        return True

    assert review_one(db, client, ARTICLE, FINGERPRINT, worker) == {
        'processed': 1, 'status': 'needs_review', 'published': 0}
    assert [call.args[0] for call in db.rpc.call_args_list] == [
        'inspection_claim_single', 'inspection_finish']
    assert db.rpc.call_args_list[0].args[1] == {
        'p_id': JOB, 'p_article': ARTICLE, 'p_versions': VERSIONS}


@pytest.mark.parametrize('change', ['wrong_master', 'other_queue', 'processing', 'old_version'])
def test_preflight_blocks_ai_for_wrong_basis_or_queue(change):
    db, client, queue, master, _ = fixture()
    if change == 'wrong_master':
        master[0]['fingerprint'] = 'b' * 64
    elif change == 'other_queue':
        queue.append({**queue[0], 'article_id': OTHER})
    elif change == 'processing':
        queue[0]['status'] = 'processing'
    else:
        queue[0]['versions'] = {MASTER: 0}
    worker = MagicMock()
    with pytest.raises(InspectionError):
        review_one(db, client, ARTICLE, FINGERPRINT, worker)
    worker.assert_not_called()
    db.rpc.assert_not_called()


@pytest.mark.parametrize('change', ['failed', 'old_fingerprint', 'old_basis', 'stale_versions'])
def test_worker_exit_alone_is_not_success(change):
    db, client, _, _, final = fixture()
    if change == 'failed':
        final['status'] = 'failed'
    elif change == 'old_fingerprint':
        final['result']['master_fingerprint'] = 'b' * 64
    elif change == 'old_basis':
        final['result']['analysis_basis'] = 'organization'
    else:
        final['versions'] = {MASTER: 0}
    with pytest.raises(InspectionError, match='single_review_failed'):
        review_one(db, client, ARTICLE, FINGERPRINT, MagicMock(return_value=True))
