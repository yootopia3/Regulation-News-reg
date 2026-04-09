"""Unit tests for `src.collectors.http.fetch` SSL verify kwarg."""

from unittest.mock import MagicMock, patch

import pytest

from src.collectors import http
from src.config import settings


@pytest.fixture
def mock_session():
    """Patch `get_session` so no real network call is attempted."""
    session = MagicMock()
    response = MagicMock()
    response.raise_for_status.return_value = None
    session.get.return_value = response
    with patch.object(http, "get_session", return_value=session):
        yield session


def test_fetch_defaults_verify_to_settings(mock_session):
    http.fetch("https://example.com")

    mock_session.get.assert_called_once()
    kwargs = mock_session.get.call_args.kwargs
    assert kwargs["verify"] is settings.SSL_VERIFY


def test_fetch_passes_verify_false(mock_session):
    http.fetch("https://example.com", verify=False)

    kwargs = mock_session.get.call_args.kwargs
    assert kwargs["verify"] is False


def test_fetch_passes_verify_true(mock_session):
    http.fetch("https://example.com", verify=True)

    kwargs = mock_session.get.call_args.kwargs
    assert kwargs["verify"] is True
