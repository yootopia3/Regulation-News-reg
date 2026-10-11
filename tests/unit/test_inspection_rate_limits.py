import json
from unittest.mock import Mock

import pytest

from src.services.sanction_inspections.client import (
    MAX_ERROR_BYTES, QUOTA_ERRORS, post_response, rate_limit_error,
)
from src.services.sanction_inspections.models import InspectionError


@pytest.mark.parametrize('code', sorted(QUOTA_ERRORS))
def test_quota_codes_are_preserved_without_provider_message(code):
    response = Mock()
    response.iter_content.return_value = [json.dumps({
        'error': {'code': code, 'type': 'insufficient_quota', 'message': 'PRIVATE_CANARY'},
    }).encode()]
    assert rate_limit_error(response) == code


@pytest.mark.parametrize('body', [b'not json', b'[]', b'{"error":[]}',
    b'{"error":{"code":"rate_limit_exceeded"}}',
    b'{"error":{"code":["PRIVATE_CANARY"]}}',
    b'{"error":{"code":"PRIVATE_CANARY"}}', b'x' * (MAX_ERROR_BYTES + 1)])
def test_unknown_malformed_and_oversize_bodies_remain_sanitized(body):
    response = Mock()
    response.iter_content.return_value = [body]
    assert rate_limit_error(response) == 'rate_limited'


def test_transport_records_quota_instead_of_temporary_rate_limit(monkeypatch):
    response = Mock(status_code=429)
    response.iter_content.return_value = [b'{"error":{"type":"insufficient_quota","message":"PRIVATE_CANARY"}}']
    session = Mock()
    session.post.return_value.__enter__ = Mock(return_value=response)
    session.post.return_value.__exit__ = Mock(return_value=False)
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    monkeypatch.setattr('src.services.sanction_inspections.client.requests.Session', lambda: session)
    with pytest.raises(InspectionError, match='^insufficient_quota$'):
        post_response({}, 'fixture')
    session.post.assert_called_once()


def test_error_body_read_failure_stays_sanitized():
    response = Mock()
    response.iter_content.side_effect = RuntimeError('PRIVATE_CANARY')
    assert rate_limit_error(response) == 'rate_limited'
