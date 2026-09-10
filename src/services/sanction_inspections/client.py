"""Single stateless endpoint, no SDK logging, tools, uploads or retries."""
import json
import os
from dataclasses import dataclass, field

import requests
from pydantic import ValidationError

from .models import InspectionError

ENDPOINT = 'https://api.openai.com/v1/responses'
MAX_RESPONSE_BYTES = 1024 * 1024


@dataclass(frozen=True)
class Settings:
    enabled: bool
    policy_confirmed: bool
    model: str
    api_key: str = field(repr=False)

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
                    raise InspectionError('rate_limited')
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


class InspectionClient:
    def __init__(self, settings, transport=post_response):
        self.settings, self.transport = settings, transport

    def generate(self, instruction, data, result_type):
        self.settings.check()
        payload = {'model': self.settings.model, 'store': False, 'background': False,
                   'max_output_tokens': 12000, 'truncation': 'disabled',
                   'instructions': instruction,
                   'input': [{'role': 'user', 'content': json.dumps(data, ensure_ascii=False)}],
                   'text': {'format': {'type': 'json_schema', 'name': result_type.__name__,
                                       'strict': True, 'schema': result_type.model_json_schema()}}}
        try:
            raw = self.transport(payload, self.settings.api_key)
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
