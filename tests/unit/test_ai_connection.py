import base64
import json
import shutil
import subprocess
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.services.sanction_inspections.client import InspectionClient, Settings, post_configured_response
from src.services.sanction_inspections.connection import allowed_address, destination, decrypt_key, load_settings
from src.services.sanction_inspections.models import InspectionError, StrictModel
from src.services.sanction_inspections.worker import run_once


class Probe(StrictModel):
    ok: bool


@pytest.fixture
def configured(monkeypatch):
    key = 'ab' * 32
    monkeypatch.setenv('SANCTION_AI_SETTINGS_ENABLED', 'true')
    monkeypatch.setenv('AI_CONNECTION_ENCRYPTION_KEY', key)
    monkeypatch.setenv('SANCTION_INSPECTIONS_ENABLED', 'true')
    monkeypatch.setenv('OPENAI_INSPECTION_POLICY_CONFIRMED', 'true')
    monkeypatch.setenv('OPENAI_INSPECTION_MODEL', 'environment-model')
    monkeypatch.setenv('OPENAI_API_KEY', 'environment-' + 'unit' * 10)
    plain = 'synthetic-' + 'unit' * 12
    base = 'https://ai.example.test/v1'
    nonce = bytes(range(12))
    encrypted = AESGCM(bytes.fromhex(key)).encrypt(nonce, plain.encode(), ('sanction-ai-connection:v1:' + base).encode())
    encode = lambda value: base64.b64encode(value).decode()
    row = {'base_url': base, 'protocol': 'chat_completions', 'model': 'fixture-model', 'revision': 1,
           'api_key_ciphertext': '.'.join(('v1', encode(nonce), encode(encrypted[-16:]), encode(encrypted[:-16])))}
    db, query = Mock(), Mock()
    db.table.return_value = query
    for name in ('select', 'eq', 'limit'):
        getattr(query, name).return_value = query
    query.execute.return_value.data = [row]
    return db, row, plain


def test_settings_load_encrypted_key_and_fail_closed_on_database_or_decryption_error(configured, monkeypatch):
    db, row, plain = configured
    settings = load_settings(db)
    assert settings.model == row['model'] and settings.api_key == plain and settings.connection_revision == 1
    assert plain not in repr(settings)
    monkeypatch.setenv('AI_CONNECTION_ENCRYPTION_KEY', 'cd' * 32)
    with pytest.raises(InspectionError, match='^connection_not_configured$'):
        load_settings(db)
    monkeypatch.setenv('AI_CONNECTION_ENCRYPTION_KEY', 'ab' * 32)
    db.table.side_effect = RuntimeError('PRIVATE_CANARY')
    with pytest.raises(InspectionError, match='^connection_not_configured$'):
        load_settings(db)


def test_legacy_settings_are_used_only_when_disabled_or_row_absent(configured, monkeypatch):
    db, _, _ = configured
    monkeypatch.setenv('SANCTION_AI_SETTINGS_ENABLED', 'false')
    assert load_settings(db).model == 'environment-model'
    db.table.assert_not_called()
    monkeypatch.setenv('SANCTION_AI_SETTINGS_ENABLED', 'true')
    db.table.return_value.execute.return_value.data = []
    assert load_settings(db).connection_revision == 0
    monkeypatch.delenv('AI_CONNECTION_ENCRYPTION_KEY')
    with pytest.raises(InspectionError, match='connection_not_configured'):
        load_settings(db)


def test_node_encryption_format_is_readable_by_python(configured):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for the cross-runtime cipher test')
    _, row, plain = configured
    script = """const c=require('node:crypto'); const v=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const iv=c.randomBytes(12), cipher=c.createCipheriv('aes-256-gcm',Buffer.from(v.key,'hex'),iv);
cipher.setAAD(Buffer.from('sanction-ai-connection:v1:'+v.base));
const data=Buffer.concat([cipher.update(v.plain,'utf8'),cipher.final()]);
process.stdout.write(['v1',iv.toString('base64'),cipher.getAuthTag().toString('base64'),data.toString('base64')].join('.'));"""
    encrypted = subprocess.run([node, '-e', script], input=json.dumps({'key': 'ab'*32, 'plain': plain, 'base': row['base_url']}), text=True, capture_output=True, check=True).stdout
    assert decrypt_key({**row, 'api_key_ciphertext': encrypted}) == plain
    with pytest.raises(InspectionError, match='connection_not_configured'):
        decrypt_key({**row, 'api_key_ciphertext': encrypted, 'base_url': 'https://other.test/v1'})


@pytest.mark.parametrize('address', ['127.0.0.1', '0.0.0.0', '169.254.169.254', '100.64.0.1', '192.168.1.1', '10.0.0.1', '172.20.0.1', '224.0.0.1', '::1', '::ffff:127.0.0.1', 'fe80::1', 'fc00::1', '2001:db8::1', '2002:7f00:1::'])
def test_non_public_addresses_are_denied(address, monkeypatch):
    assert not allowed_address(address)
    monkeypatch.setattr('socket.getaddrinfo', lambda *a, **k: [(None,None,None,None,(address,443))])
    with pytest.raises(InspectionError, match='unsafe_ai_url'):
        destination('https://ai.example.test/v1')


def test_dns_pin_and_private_allowlist(monkeypatch):
    monkeypatch.setattr('socket.getaddrinfo', lambda *a, **k: [(None,None,None,None,('8.8.8.8',443)),(None,None,None,None,('10.0.0.8',443))])
    with pytest.raises(InspectionError, match='unsafe_ai_url'):
        destination('https://ai.example.test/v1')
    monkeypatch.setenv('AI_CONNECTION_PRIVATE_BASE_URLS', 'http://ai.company.test:8000/v1')
    monkeypatch.setattr('socket.getaddrinfo', lambda *a, **k: [(None,None,None,None,('10.0.0.8',8000))])
    assert destination('http://ai.company.test:8000/v1')[1:] == ('10.0.0.8', 8000)
    with pytest.raises(InspectionError, match='unsafe_ai_url'):
        destination('http://other.company.test:8000/v1')
    for ip in ('127.0.0.1', '169.254.169.254', '8.8.8.8'):
        monkeypatch.setattr('socket.getaddrinfo', lambda *a, **k: [(None,None,None,None,(ip,8000))])
        with pytest.raises(InspectionError, match='unsafe_ai_url'):
            destination('http://ai.company.test:8000/v1')


def test_chat_payload_and_strict_validation(configured):
    settings = load_settings(configured[0])
    transport = Mock(return_value={'choices':[{'finish_reason':'stop','message':{'content':'{"ok":true}'}}]})
    client = InspectionClient(settings, transport)
    assert client.generate('Synthetic instruction', {'value':'synthetic'}, Probe).ok is True
    payload = transport.call_args.args[0]
    assert payload['max_tokens'] == 12000 and payload['response_format'] == {'type':'json_object'}
    assert 'JSON' in payload['messages'][0]['content'] and 'input' not in payload
    for raw in [[], {'choices':[]}, {'choices':[{'finish_reason':'length','message':{'content':'{"ok":true}'}}]},
                {'choices':[{'finish_reason':'stop','message':{'content':'{"ok":"true"}'}}]},
                {'choices':[{'finish_reason':'stop','message':{'content':'{"ok":true,"extra":1}'}}]}]:
        transport.return_value = raw
        with pytest.raises(InspectionError):
            client.generate('Synthetic', {}, Probe)


def test_job_refreshes_config_once_then_holds_it_for_all_calls(configured):
    db, _, _ = configured
    first = load_settings(db)
    second = replace(first, model='changed-model', connection_revision=2)
    loader = Mock(side_effect=[first, second])
    transport = Mock(return_value={'choices':[{'finish_reason':'stop','message':{'content':'{"ok":true}'}}]})
    client = InspectionClient(first, transport, settings_loader=loader)
    db.rpc.return_value.execute.return_value.data = None
    assert run_once(db, client) is False
    client.generate('Synthetic', {}, Probe); client.generate('Synthetic', {}, Probe)
    assert loader.call_count == 1
    assert run_once(db, client) is False
    client.generate('Synthetic', {}, Probe)
    assert transport.call_args.args[0]['model'] == 'changed-model'


def test_config_failure_does_not_claim_a_job():
    db = Mock()
    client = InspectionClient(Settings(True,True,'fixture','synthetic'), settings_loader=Mock(side_effect=InspectionError('connection_not_configured')))
    with pytest.raises(InspectionError, match='connection_not_configured'):
        run_once(db, client)
    db.rpc.assert_not_called()


def test_transport_preserves_tls_name_pins_ip_and_sanitizes_errors(configured, monkeypatch):
    settings = load_settings(configured[0])
    monkeypatch.setattr('socket.getaddrinfo', lambda *a, **k: [(None,None,None,None,('8.8.8.8',443))])
    create_socket, tls, connection = Mock(), Mock(), Mock()
    response = Mock(status=200); response.read1.side_effect = [b'{"choices":[]}', b'']
    connection.getresponse.return_value = response
    monkeypatch.setattr('socket.create_connection', create_socket)
    monkeypatch.setattr('ssl.create_default_context', lambda: tls)
    monkeypatch.setattr('http.client.HTTPSConnection', lambda *a, **k: connection)
    assert post_configured_response({}, settings) == {'choices':[]}
    create_socket.assert_called_with(('8.8.8.8',443), timeout=10)
    assert tls.wrap_socket.call_args.kwargs['server_hostname'] == 'ai.example.test'
    assert connection.request.call_args.args[:2] == ('POST','/v1/chat/completions')
    response.status = 302
    with pytest.raises(InspectionError, match='^provider_failed$'):
        post_configured_response({}, settings)
    response.status = 429; response.read1.side_effect = [b'{"error":{"code":"insufficient_quota","message":"PRIVATE_CANARY"}}',b'']
    with pytest.raises(InspectionError, match='^insufficient_quota$'):
        post_configured_response({}, settings)
    response.status = 200; response.read1.side_effect = [b'x'*(1024*1024+1),b'']
    with pytest.raises(InspectionError, match='^response_limit$'):
        post_configured_response({}, settings)
