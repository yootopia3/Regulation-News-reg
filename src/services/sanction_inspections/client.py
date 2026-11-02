"""Single stateless endpoint, no SDK logging, tools, uploads or retries."""
import json
import os
import http.client
import socket
import ssl
import time
from dataclasses import dataclass, field

import requests
from pydantic import ValidationError

from .models import InspectionError

ENDPOINT = 'https://api.openai.com/v1/responses'
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_ERROR_BYTES = 16 * 1024
QUOTA_ERRORS = frozenset({
    'insufficient_quota', 'credit_balance_exhausted',
    'organization_spend_limit_exceeded', 'project_spend_limit_exceeded',
    'organization_usage_limit_exceeded', 'usage_limit_exceeded',
})


def rate_limit_code(raw):
    error = raw.get('error') if isinstance(raw, dict) else None
    if isinstance(error, dict):
        code, kind = error.get('code'), error.get('type')
        if isinstance(code, str) and code in QUOTA_ERRORS:
            return code
        if kind == 'insufficient_quota':
            return 'insufficient_quota'
    return 'rate_limited'


def rate_limit_error(response):
    """Keep only allowlisted codes; never persist provider messages or bodies."""
    try:
        body = bytearray()
        for chunk in response.iter_content(4096):
            if len(body) + len(chunk) > MAX_ERROR_BYTES:
                return 'rate_limited'
            body.extend(chunk)
        return rate_limit_code(json.loads(body))
    except Exception:
        pass
    return 'rate_limited'


@dataclass(frozen=True)
class Settings:
    enabled: bool
    policy_confirmed: bool
    model: str
    api_key: str = field(repr=False)
    base_url: str = 'https://api.openai.com/v1'
    protocol: str = 'responses'
    connection_revision: int = 0

    @classmethod
    def from_env(cls):
        return cls(os.getenv('SANCTION_INSPECTIONS_ENABLED') == 'true',
                   os.getenv('OPENAI_INSPECTION_POLICY_CONFIRMED') == 'true',
                   os.getenv('OPENAI_INSPECTION_MODEL', ''), os.getenv('OPENAI_API_KEY', ''))

    def check(self):
        if not self.enabled:
            raise InspectionError('disabled')
        if not self.policy_confirmed or not self.model.strip() or not self.api_key.strip():
            raise InspectionError('not_configured')


def post_response(payload, key):
    # Disable ambient proxy/credential files for this private transmission.
    try:
        with requests.Session() as session:
            session.trust_env = False
            with session.post(ENDPOINT, json=payload, headers={'Authorization': f'Bearer {key}'},
                              timeout=(10, 60), stream=True, allow_redirects=False) as response:
                if response.status_code == 429:
                    raise InspectionError(rate_limit_error(response))
                if response.status_code != 200:
                    raise InspectionError('provider_failed')
                chunks, size = [], 0
                for chunk in response.iter_content(8192):
                    size += len(chunk)
                    if size > MAX_RESPONSE_BYTES:
                        raise InspectionError('response_limit')
                    chunks.append(chunk)
                return json.loads(b''.join(chunks))
    except InspectionError:
        raise
    except Exception:
        raise InspectionError('provider_failed') from None


def read_http_body(response, connection, deadline, limit):
    chunks, size = [], 0
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise InspectionError('provider_failed')
        if connection.sock:
            connection.sock.settimeout(remaining)
        chunk = response.read1(8192)
        if not chunk:
            return b''.join(chunks)
        size += len(chunk)
        if size > limit:
            raise InspectionError('response_limit')
        chunks.append(chunk)


def post_configured_response(payload, settings):
    from .connection import destination
    deadline = time.monotonic() + 60
    connection = None
    try:
        url, ip, port = destination(settings.base_url)
        connection = (http.client.HTTPSConnection if url.scheme == 'https' else http.client.HTTPConnection)(url.hostname, port, timeout=10)
        raw = socket.create_connection((ip, port), timeout=10)
        try:
            connection.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=url.hostname) if url.scheme == 'https' else raw
        except Exception:
            raw.close()
            raise
        connection.sock.settimeout(max(1, deadline - time.monotonic()))
        path = url.path + ('/responses' if settings.protocol == 'responses' else '/chat/completions')
        connection.request('POST', path, body=json.dumps(payload, ensure_ascii=False).encode(), headers={
            'Authorization': 'Bearer ' + settings.api_key, 'Content-Type': 'application/json',
            'Accept': 'application/json', 'Accept-Encoding': 'identity'})
        response = connection.getresponse()
        if response.status == 429:
            try:
                code = rate_limit_code(json.loads(read_http_body(response, connection, deadline, MAX_ERROR_BYTES)))
            except Exception:
                code = 'rate_limited'
            raise InspectionError(code)
        if response.status != 200:
            # Never follow redirects with credentials or persist provider bodies.
            raise InspectionError('provider_auth_failed' if response.status in (401, 403) else 'provider_failed')
        return json.loads(read_http_body(response, connection, deadline, MAX_RESPONSE_BYTES))
    except InspectionError:
        raise
    except Exception:
        raise InspectionError('provider_failed') from None
    finally:
        if connection:
            connection.close()


class InspectionClient:
    def __init__(self, settings, transport=None, settings_loader=None):
        self.settings = settings
        self.transport = transport or self._post
        self.settings_loader = settings_loader

    def refresh(self):
        if self.settings_loader:
            self.settings = self.settings_loader()

    def _post(self, payload, key):
        if self.settings.connection_revision:
            return post_configured_response(payload, self.settings)
        return post_response(payload, key)

    def generate(self, instruction, data, result_type):
        self.settings.check()
        payload = {'model': self.settings.model, 'store': False, 'background': False,
                   'max_output_tokens': 12000, 'truncation': 'disabled',
                   'instructions': instruction,
                   'input': [{'role': 'user', 'content': json.dumps(data, ensure_ascii=False)}],
                   'text': {'format': {'type': 'json_schema', 'name': result_type.__name__,
                                       'strict': True, 'schema': result_type.model_json_schema()}}}
        if self.settings.protocol == 'chat_completions':
            payload = {'model': self.settings.model, 'max_tokens': 12000, 'stream': False,
                       'response_format': {'type': 'json_object'}, 'messages': [
                           {'role': 'system', 'content': instruction + '\nReturn only JSON conforming to this schema: ' + json.dumps(result_type.model_json_schema(), ensure_ascii=False)},
                           {'role': 'user', 'content': json.dumps(data, ensure_ascii=False)}]}
        try:
            raw = self.transport(payload, self.settings.api_key)
            if self.settings.protocol == 'chat_completions':
                choices = raw.get('choices') if isinstance(raw, dict) else None
                if not isinstance(choices, list) or len(choices) != 1:
                    raise InspectionError('invalid_response')
                choice = choices[0]
                if choice.get('finish_reason') != 'stop':
                    raise InspectionError('incomplete_response')
                if choice['message'].get('refusal'):
                    raise InspectionError('refused')
                return result_type.model_validate_json(choice['message']['content'])
            if not isinstance(raw, dict) or raw.get('status') != 'completed':
                raise InspectionError('incomplete_response')
            texts = []
            for item in raw.get('output', []):
                if item.get('type') != 'message':
                    continue
                for part in item.get('content', []):
                    if part.get('type') == 'refusal':
                        raise InspectionError('refused')
                    if part.get('type') == 'output_text':
                        texts.append(part['text'])
            if len(texts) != 1:
                raise InspectionError('invalid_response')
            return result_type.model_validate_json(texts[0])
        except InspectionError:
            raise
        except (ValidationError, ValueError, TypeError, KeyError, AttributeError):
            raise InspectionError('invalid_response') from None
        except Exception:
            raise InspectionError('provider_failed') from None
