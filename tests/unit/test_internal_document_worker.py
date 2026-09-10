import hashlib
from types import SimpleNamespace
from unittest.mock import Mock

from src.services.internal_documents.worker import run_once
from src.services.internal_documents.parser import expanded_stream
import pytest
import zlib
import subprocess
import sys


def fake_db(kind='extract'):
    data = b'synthetic-file'
    job = {'document_id': 'fixture-id', 'lease_token': 'fixture-lease', 'object_key': 'fixture.hwp', 'sha256': hashlib.sha256(data).hexdigest(), 'kind': kind}
    db = Mock()
    db.rpc.return_value.execute.side_effect = [SimpleNamespace(data=job), SimpleNamespace(data=None)]
    db.storage.from_.return_value.download.return_value = data
    return db


def test_worker_checks_hash_before_parser():
    db = fake_db()
    db.storage.from_.return_value.download.return_value = b'changed-file'
    parser = Mock()
    assert run_once(db, parser)
    parser.assert_not_called()
    assert db.rpc.call_args.args[1]['p_error'] == 'invalid_hwp'


def test_worker_does_not_send_content_in_provider_failure():
    db = fake_db()
    db.storage.from_.return_value.download.side_effect = RuntimeError('PRIVATE SENTINEL')
    run_once(db)
    assert db.rpc.call_args.args[1]['p_error'] == 'worker_failed'
    assert 'PRIVATE SENTINEL' not in str(db.rpc.call_args)


def test_worker_deletes_storage_before_finishing():
    db = fake_db('delete')
    parser = Mock()
    run_once(db, parser)
    db.storage.from_.return_value.remove.assert_called_once_with(['fixture.hwp'])
    parser.assert_not_called()
    assert db.rpc.call_args.args[1]['p_error'] is None


def test_worker_retries_storage_deletion_failure():
    db = fake_db('delete')
    db.storage.from_.return_value.remove.side_effect = RuntimeError('fail')
    run_once(db)
    assert db.rpc.call_args.args[1]['p_error'] == 'worker_failed'


def test_decompression_is_bounded_before_xml_conversion():
    encoder = zlib.compressobj(wbits=-15)
    data = encoder.compress(b'x' * 10000) + encoder.flush()
    with pytest.raises(ValueError, match='document_limit'):
        expanded_stream(data, True, 100)
    assert expanded_stream(data, True, 10000) == 10000


def test_network_guard_preserves_ssl_import_but_blocks_sockets():
    result = subprocess.run([sys.executable, '-c',
        'import sys; from src.services.internal_documents.parser import deny_network; '
        'sys.addaudithook(deny_network); import ssl, socket; '
        '\ntry: socket.socket()\nexcept RuntimeError: print("blocked")'],
        capture_output=True, text=True, timeout=10, check=True)
    assert result.stdout.strip() == 'blocked'
