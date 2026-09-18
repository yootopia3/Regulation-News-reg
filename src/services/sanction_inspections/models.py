"""Strict boundaries for public evidence and private candidate drafts."""
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


class InspectionError(Exception):
    """Only fixed error codes may leave this service."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, hide_input_in_errors=True)


class Page(StrictModel):
    number: int = Field(ge=1, le=200)
    text: str = Field(min_length=1, max_length=12000)


class PublicEvidence(StrictModel):
    page: int = Field(ge=1, le=200)
    quote: str = Field(min_length=8, max_length=300)


class Finding(StrictModel):
    id: str = Field(pattern=r'^F[1-9][0-9]?$')
    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=1000)
    evidence: list[PublicEvidence] = Field(min_length=1, max_length=5)


class Findings(StrictModel):
    findings: list[Finding] = Field(min_length=1, max_length=30)


class Unit(StrictModel):
    document_kind: Literal['allocation', 'analysis', 'organization'] = 'allocation'
    organization_names: list[str] = Field(default_factory=list, max_length=200)
    document_id: str = Field(min_length=1, max_length=64)
    revision: int = Field(ge=0)
    article_key: str = Field(pattern=r'^[0-9]+(?:-[0-9]+)?$')
    department: str = Field(max_length=120)
    body: str = Field(min_length=1, max_length=500000)
    active: bool
    reviewed: bool

    @property
    def ref(self):
        return f'{self.document_id}:{self.article_key}'


class InternalEvidence(StrictModel):
    ref: str = Field(min_length=1, max_length=100)
    quote: str = Field(min_length=8, max_length=300)


class Check(StrictModel):
    question: str = Field(min_length=5, max_length=400)
    evidence_to_request: str = Field(min_length=1, max_length=300)


class Match(StrictModel):
    finding_id: str = Field(pattern=r'^F[1-9][0-9]?$')
    department_ref: str = Field(min_length=1, max_length=100)
    rationale: str = Field(min_length=1, max_length=500)
    related_work: str = Field(min_length=1, max_length=160)
    evidence: list[InternalEvidence] = Field(min_length=1, max_length=5)
    checks: list[Check] = Field(min_length=1, max_length=6)


class Matches(StrictModel):
    matches: list[Match] = Field(max_length=90)
    unmatched_finding_ids: list[str] = Field(max_length=30)


class OrganizationMatch(Match):
    department_name: str = Field(min_length=1, max_length=120)


class OrganizationMatches(StrictModel):
    matches: list[OrganizationMatch] = Field(max_length=90)
    unmatched_finding_ids: list[str] = Field(max_length=30)
