"""Strict public projection and review validation; private evidence never returned."""
import json
import unicodedata
from typing import Literal
from pydantic import Field, model_validator
from sqlalchemy import select, insert, update
from .inspection_engine.models import StrictModel
from .database import inspections, publications, documents, document_units, duty_masters, now
from .admin import record_event
from .security import Problem

class Basis(StrictModel):
    department: str = Field(min_length=1, max_length=120)
    basis: Literal['explicit', 'inferred', 'limited']
    duty_ids: list[str] = Field(min_length=1, max_length=2)

class Check(StrictModel):
    question: str = Field(min_length=1, max_length=400)
    evidence_to_request: str = Field(min_length=1, max_length=300)
    department: str | None = Field(default=None, min_length=1, max_length=120)

class Item(StrictModel):
    finding_id: str = Field(pattern=r'^F[1-9][0-9]?$')
    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=1000)
    departments: list[str] = Field(max_length=5)
    related_work: str = Field(min_length=1, max_length=500)
    source_pages: list[int] = Field(min_length=1, max_length=5)
    department_basis: list[Basis] | None = Field(default=None, max_length=5)
    checks: list[Check] = Field(min_length=1, max_length=30)

class Report(StrictModel):
    analysis_basis: Literal['organization', 'duty_master'] | None = None
    master_version: str | None = Field(default=None, min_length=1, max_length=80)
    master_fingerprint: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    items: list[Item] = Field(min_length=1, max_length=30)

    @model_validator(mode='after')
    def fields(self):
        master = self.analysis_basis == 'duty_master'
        if master and (not self.master_version or not self.master_fingerprint):
            raise ValueError('master_basis_required')
        if not master and (self.master_version or self.master_fingerprint):
            raise ValueError('unexpected_master_basis')
        for i in self.items:
            if any(not s.strip() or len(s) > 120 for s in i.departments) or any(not 1 <= p <= 200 for p in i.source_pages):
                raise ValueError('invalid_request')
            if master and (i.department_basis is None or any(not c.department for c in i.checks)):
                raise ValueError('master_basis_required')
            if not master and (i.department_basis is not None or any(c.department for c in i.checks)):
                raise ValueError('unexpected_master_basis')
        return self

def public_report(value):
    try:
        def trimmed(v):
            if isinstance(v, str):
                if not v.strip():
                    raise ValueError('blank')
                return v.strip()
            if isinstance(v, list):
                return [trimmed(x) for x in v]
            if isinstance(v, dict):
                return {k: trimmed(x) for k, x in v.items()}
            return v
        value = trimmed(value)
        return Report.model_validate(value).model_dump(exclude_none=True)
    except Exception:
        raise Problem('publication_review_required') from None

def compact(value):
    return ''.join(c for c in unicodedata.normalize('NFKC', value).lower()
                   if not c.isspace() and not unicodedata.category(c).startswith('P') and unicodedata.category(c) != 'Cf')

def validate(report, draft, private_texts):
    if report.get('analysis_basis') != draft.get('analysis_basis'):
        raise Problem('publication_review_required')
    master = draft.get('analysis_basis') == 'duty_master'
    if master and any(report.get(k) != draft.get(k) for k in ('master_version', 'master_fingerprint')):
        raise Problem('publication_review_required')
    findings = {f['id']: f for f in draft['findings']}
    ids = [i['finding_id'] for i in report['items']]
    if len(ids) != len(set(ids)) or set(ids) != set(findings):
        raise Problem('publication_review_required')
    for item in report['items']:
        matches = [m for m in draft['matches'] if m['finding_id'] == item['finding_id']]
        allowed = {m['department'] for m in matches}
        if draft.get('analysis_basis') and not set(item['departments']) <= allowed:
            raise Problem('publication_review_required')
        if not set(item['source_pages']) <= {e['page'] for e in findings[item['finding_id']]['evidence']}:
            raise Problem('publication_review_required')
        if master:
            bases = item['department_basis']
            if len(bases) != len(item['departments']) or len({b['department'] for b in bases}) != len(bases) or {b['department'] for b in bases} != set(item['departments']):
                raise Problem('publication_review_required')
            for b in bases:
                match = next((m for m in matches if m['department'] == b['department']), None)
                if not match or match.get('duty_basis') != b['basis'] or sorted(match.get('duty_ids', [])) != sorted(b['duty_ids']):
                    raise Problem('publication_review_required')
            if any(c['department'] not in item['departments'] for c in item['checks']):
                raise Problem('publication_review_required')
    fields = [compact(s) for i in report['items'] for s in
        [i['title'], i['summary'], i['related_work'], *(i['departments'] if not draft.get('analysis_basis') else []),
         *(v for c in i['checks'] for v in (c['question'], c['evidence_to_request']))]]
    output = ''.join(fields)
    quotes = [compact(e['quote']) for m in draft['matches'] for e in m.get('evidence', [])]
    for quote in (q for q in quotes if len(q) >= 8):
        remaining = quote
        for field in (f for f in fields if len(f) >= 4):
            remaining = remaining.replace(field, '', 1)
        if quote in output or not remaining:
            raise Problem('private_content_detected')
    windows = {output[i:i+24] for i in range(max(0, len(output)-23))}
    for text in map(compact, private_texts):
        if 8 <= len(text) < 24 and text in output or any(text[i:i+24] in windows for i in range(max(0, len(text)-23))):
            raise Problem('private_content_detected')

def current_versions(conn):
    masters = dict(conn.execute(select(duty_masters.c.id, duty_masters.c.revision).where(duty_masters.c.active == True)).all())
    return masters or dict(conn.execute(select(documents.c.id, documents.c.revision).where(
        documents.c.status == 'active', documents.c.document_kind == 'organization')).all())

def private_basis(conn, job):
    versions = json.loads(job['versions'])
    draft = json.loads(job['result'] or 'null')
    if not draft or not versions or versions != current_versions(conn):
        raise Problem('source_documents_required', 409)
    texts = []
    for ident, revision in versions.items():
        if draft.get('analysis_basis') == 'duty_master':
            row = conn.execute(select(duty_masters).where(duty_masters.c.id == ident).with_for_update()).mappings().first()
            if not row or not row['active'] or row['revision'] != revision or row['fingerprint'] != draft.get('master_fingerprint'):
                raise Problem('source_documents_required', 409)
            for duty in json.loads(row['payload'])['duties']:
                texts.extend([duty['detail'], duty['boundary'], *(s['document'] for s in duty['sources'])])
        else:
            row = conn.execute(select(documents).where(documents.c.id == ident).with_for_update()).mappings().first()
            if not row or row['status'] != 'active' or row['revision'] != revision:
                raise Problem('source_documents_required', 409)
            texts.append(row['title'])
            texts.extend(conn.execute(select(document_units.c.body).where(document_units.c.document_id == ident)).scalars())
    return draft, texts

def action(engine, actor, ident, revision, operation, value=None, reviewed=False):
    if not actor:
        raise Problem('admin_authorization_pending', 403)
    if operation == 'publish' and reviewed is not True:
        raise Problem('publication_review_required')
    with engine.begin() as conn:
        if engine.dialect.name == 'postgresql':
            from sqlalchemy import text
            conn.execute(text('SELECT pg_advisory_xact_lock(77461024)'))
        job = conn.execute(select(inspections).where(inspections.c.id == ident).with_for_update()).mappings().first()
        if not job or job['review_revision'] != revision:
            raise Problem('review_conflict', 409)
        if operation == 'withdraw':
            changed = conn.execute(update(publications).where(publications.c.inspection_id == ident, publications.c.status == 'published').values(status='withdrawn'))
            if not changed.rowcount:
                raise Problem('review_conflict', 409)
        elif operation in ('save', 'publish', 'validate'):
            if job['status'] != 'needs_review':
                raise Problem('review_conflict', 409)
            report = public_report(value if operation == 'save' else json.loads(job['review_draft'] or 'null'))
            if operation in ('publish', 'validate'):
                draft, texts = private_basis(conn, job)
                validate(report, draft, texts)
            if operation == 'validate':
                return {'valid': True, 'revision': revision}
            if operation == 'save':
                conn.execute(update(inspections).where(inspections.c.id == ident).values(review_draft=json.dumps(report, ensure_ascii=False)))
                withdrawn = conn.execute(update(publications).where(publications.c.inspection_id == ident, publications.c.status == 'published').values(status='withdrawn'))
                if withdrawn.rowcount:
                    record_event(conn, actor, 'automatic_withdrawal', ident)
            else:
                values = dict(article_id=job['article_id'], report=json.dumps(report, ensure_ascii=False), status='published', published_at=now(), publication_source='manual')
                existing = conn.execute(select(publications.c.inspection_id).where(publications.c.article_id == job['article_id'])).scalar_one_or_none()
                if existing is not None and existing != ident:
                    raise Problem('review_conflict', 409)
                if existing:
                    conn.execute(update(publications).where(publications.c.inspection_id == ident).values(**values))
                else:
                    conn.execute(insert(publications).values(inspection_id=ident, **values))
        else:
            raise Problem('invalid_request')
        changed = conn.execute(update(inspections).where(inspections.c.id == ident, inspections.c.review_revision == revision)
                               .values(review_revision=revision+1, automation_status='manual', **({'is_historical': False} if operation == 'publish' else {})))
        if changed.rowcount != 1:
            raise Problem('review_conflict', 409)
        record_event(conn, actor, 'inspection_' + operation, ident)
        return {'revision': revision+1}
