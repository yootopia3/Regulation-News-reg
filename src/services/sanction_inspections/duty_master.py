"""Versioned, inferred headquarters duties; never treat this as approved allocation."""
import hashlib
import json
from typing import Literal

from pydantic import Field, model_validator

from .models import StrictModel, InspectionError


class DutySource(StrictModel):
    unit: str = Field(min_length=1, max_length=100)
    document: str = Field(min_length=1, max_length=180)
    article: str = Field(min_length=1, max_length=80)
    location: str = Field(min_length=1, max_length=120)


class Duty(StrictModel):
    id: str = Field(pattern=r'^HQ-[0-9]{3,5}$')
    department: str = Field(min_length=2, max_length=120)
    parent: str = Field(min_length=1, max_length=120)
    task: str = Field(min_length=1, max_length=200)
    detail: str = Field(min_length=1, max_length=1000)
    boundary: str = Field(min_length=1, max_length=1000)
    basis: Literal['explicit', 'inferred', 'limited']
    sources: list[DutySource] = Field(min_length=1, max_length=30)


class DutyMaster(StrictModel):
    version: str = Field(min_length=1, max_length=80)
    scope: Literal['headquarters_only']
    source_document_count: int = Field(ge=1, le=10000)
    departments: list[str] = Field(min_length=1, max_length=200)
    duties: list[Duty] = Field(min_length=1, max_length=1000)

    @model_validator(mode='after')
    def consistent(self):
        if (len(set(self.departments)) != len(self.departments)
                or any(not name.strip() or name != name.strip() or len(name) > 120 for name in self.departments)
                or len({d.id for d in self.duties}) != len(self.duties)
                or {d.department for d in self.duties} != set(self.departments)):
            raise ValueError('invalid_duty_master')
        # Named HQ support departments remain eligible; branch organizations do not.
        if any(name.endswith(('지점', '영업점', '지역본부', '사무소')) for name in self.departments):
            raise ValueError('sales_organization_not_allowed')
        if len(self.model_dump_json()) > 1500000:
            raise ValueError('master_limit')
        return self

    @property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(self.model_dump(), ensure_ascii=False,
                                         sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def parse_master(payload):
    try:
        return DutyMaster.model_validate(payload)
    except Exception:
        raise InspectionError('invalid_duty_master') from None


def convert_workbook_data(data):
    """Convert the companion JSON; exclude source corpus, paths and source bodies."""
    try:
        documents = {d['id']: d['name'] for d in data['documents']}
        names = [p['name'] for p in data['profiles']]
        levels = {'M': 'explicit', 'I': 'inferred', 'L': 'limited'}
        return parse_master({'version': data['version'], 'scope': 'headquarters_only',
            'source_document_count': len(documents), 'departments': names,
            'duties': [{'id': row['id'], 'department': row['department'], 'parent': row['parent'],
                'task': row['task'], 'detail': row['detail'], 'boundary': row['boundary'],
                'basis': levels[row['grade']], 'sources': [{'unit': e['unit'],
                    'document': documents[e['doc']], 'article': e['article'], 'location': e['location']}
                    for e in row['evidence']]} for row in data['rows']]})
    except InspectionError:
        raise
    except Exception:
        raise InspectionError('invalid_duty_master') from None

