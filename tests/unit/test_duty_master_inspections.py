import copy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.services.sanction_inspections.duty_master import parse_master, convert_workbook_data
from src.services.sanction_inspections.master_engine import analyze_master
from src.services.sanction_inspections.models import Finding, InspectionError, Page
from src.services.sanction_inspections.worker import load_master, run_once

PUBLIC = '거래목적과 자금출처가 의심된 고객에 대해 고객확인 재검증을 누락하였다.'


def payload():
    return {'version': 'fixture-v1', 'scope': 'headquarters_only', 'source_document_count': 2,
        'departments': ['합성통제부', '합성지원부'], 'duties': [
            {'id': 'HQ-001', 'department': '합성통제부', 'parent': '합성그룹',
             'task': '고객확인 기준 관리', 'detail': '고객확인 재검증 및 거래목적 자금출처 확인기준을 점검한다.',
             'boundary': '거래 실행은 다른 부서의 영역이다.', 'basis': 'inferred',
             'sources': [{'unit': 'S1', 'document': '합성규정', 'article': '제1조', 'location': '문단 10'}]},
            {'id': 'HQ-002', 'department': '합성지원부', 'parent': '합성그룹',
             'task': '채용 교육 복리후생', 'detail': '채용 교육 및 급여제도를 지원한다.',
             'boundary': '고객확인 재검증 및 거래목적 자금출처 업무와 구분한다.', 'basis': 'limited',
             'sources': [{'unit': 'S2', 'document': '합성규정', 'article': '제2조', 'location': '문단 20'}]}]}


def finding():
    return {'id': 'F1', 'title': '고객확인 재검증 누락', 'summary': PUBLIC, 'evidence': [{'page': 1, 'quote': PUBLIC}]}


def match():
    return {'finding_id': 'F1', 'duty_ids': ['HQ-001'], 'rationale': '고객정보가 바뀐 경우의 통제기준 점검 후보이다.',
            'related_work': '고객정보 재확인', 'checks': [{'question': '경보 접수 후 재확인 완료까지 추적하는가?', 'evidence_to_request': '처리 이력과 표본'}]}


class Client:
    settings = SimpleNamespace(check=lambda: None, model='fixture-model')

    def __init__(self, answers=None):
        self.calls = []
        self.answers = answers or [{'findings': [finding()]}, {'matches': [match()], 'unmatched_finding_ids': []}]

    def generate(self, instruction, data, schema):
        self.calls.append((instruction, data))
        return schema.model_validate(self.answers[len(self.calls)-1])


def run(client=None, data=None):
    return analyze_master([Page(number=1, text=PUBLIC)], parse_master(data or payload()), client or Client(), versions={'master-id': 1})


def test_master_scopes_identity_and_fingerprint():
    original = payload(); master = parse_master(original)
    changed = copy.deepcopy(original); changed['duties'][0]['basis'] = 'explicit'
    assert parse_master(changed).fingerprint != master.fingerprint
    for edit in [dict(departments=['합성통제부']), dict(scope='all'), dict(departments=['합성통제부', '합성통제부'])]:
        with pytest.raises(InspectionError, match='invalid_duty_master'):
            parse_master({**original, **edit})
    original['duties'][1]['department'] = '합성지점'; original['departments'][1] = '합성지점'
    with pytest.raises(InspectionError): parse_master(original)


def test_full_compact_master_preserves_alternative_roles_and_boundaries():
    client = Client(); run(client)
    candidates = client.calls[1][1]['candidates']
    assert {d['id'] for d in candidates} == {'HQ-001', 'HQ-002'}
    assert candidates[1]['boundary'] == payload()['duties'][1]['boundary']
    assert all('sources' not in d for d in candidates)


def test_basis_and_department_come_from_master_not_provider():
    client = Client(); result = run(client)
    assert result['analysis_basis'] == 'duty_master'
    assert result['matches'][0]['department'] == '합성통제부'
    assert result['matches'][0]['duty_basis'] == 'inferred'
    assert result['matches'][0]['duty_sources'][0]['unit'] == 'S1'
    assert 'duties' not in client.calls[0][1]
    assert 'sources' not in client.calls[1][1]['candidates'][0]
    changed = payload(); changed['duties'][0]['detail'] += ' 주기적 검증을 수행한다.'
    assert run(data=changed)['fingerprint'] != result['fingerprint']


@pytest.mark.parametrize('ids', [['HQ-999'], ['HQ-001', 'HQ-001']])
def test_non_candidate_or_duplicate_ids_are_rejected(ids):
    m = match(); m['duty_ids'] = ids
    with pytest.raises(InspectionError, match='invalid_duty_reference'):
        run(Client([{'findings': [finding()]}, {'matches': [m], 'unmatched_finding_ids': []}]))


def test_finding_coverage_and_public_evidence():
    with pytest.raises(InspectionError, match='finding_coverage_failed'):
        run(Client([{'findings': [finding()]}, {'matches': [], 'unmatched_finding_ids': []}]))
    f = finding(); f['evidence'][0]['page'] = 2
    client = Client([{'findings': [f]}])
    with pytest.raises(InspectionError, match='invalid_public_evidence'): run(client)
    assert len(client.calls) == 1


def test_no_relevant_duties_can_be_left_unmatched():
    data = payload(); data['duties'] = data['duties'][1:]; data['departments'] = ['합성지원부']
    client = Client([{'findings': [finding()]}, {'matches': [], 'unmatched_finding_ids': ['F1']}]); result = run(client, data)
    assert result['unmatched_finding_ids'] == ['F1'] and not result['matches']
    assert len(client.calls) == 2


def test_workbook_conversion_excludes_full_text_and_filesystem_paths():
    data = {'version': 'fixture-v1', 'profiles': [{'name': '합성통제부'}],
        'documents': [{'id': 'D1', 'name': '합성규정', 'path': 'PRIVATE_PATH'}],
        'source_corpus': 'PRIVATE_FULL_CORPUS',
        'rows': [{'id': 'HQ-001', 'department': '합성통제부', 'parent': '합성그룹',
            'task': '고객확인 기준', 'detail': '확인절차를 점검한다.', 'boundary': '실행부서와 구분한다.', 'grade': 'I',
            'evidence': [{'unit': 'S1', 'doc': 'D1', 'article': '제1조', 'location': '문단 10', 'body': 'PRIVATE_FULL_TEXT'}]}]}
    master = convert_workbook_data(data)
    assert 'PRIVATE_' not in master.model_dump_json()
    assert master.duties[0].basis == 'inferred'


def test_loader_checks_active_identity_and_fingerprint():
    db = Mock(); q = db.table.return_value
    for method in ('select', 'eq', 'limit'): getattr(q, method).return_value = q
    master = parse_master(payload())
    row = {'id': 'm', 'revision': 1, 'version': master.version, 'fingerprint': master.fingerprint, 'payload': master.model_dump()}
    q.execute.return_value.data = [row]
    assert load_master(db, {'m': 1}) == master
    with pytest.raises(InspectionError, match='documents_changed'): load_master(db, {'m': 2})
    row['fingerprint'] = '0' * 64
    with pytest.raises(InspectionError, match='invalid_duty_master'): load_master(db, {'m': 1})


def test_worker_routes_master_and_preserves_job_versions(monkeypatch):
    db = Mock(); q = db.table.return_value
    for method in ('select', 'eq', 'single'): getattr(q, method).return_value = q
    q.execute.return_value.data = {'agency': 'FSS_SANCTION', 'category': 'sanction_notice', 'analysis_result': {'pdf_url': 'https://www.fss.or.kr/a'}}
    job = {'id': 'job', 'article_id': 'article', 'lease_token': 'lease', 'versions': {'m': 1}}
    db.rpc.return_value.execute.return_value.data = job
    monkeypatch.setattr('src.services.sanction_inspections.worker.load_master', lambda *_: parse_master(payload()))
    forbidden = Mock(side_effect=AssertionError('legacy units must not load'))
    monkeypatch.setattr('src.services.sanction_inspections.worker.load_units', forbidden)
    assert run_once(db, Client(), downloader=lambda _: b'%PDF', parser=lambda *a, **k: {'pages': [{'number': 1, 'text': PUBLIC}]})
    saved = db.rpc.call_args.args[1]
    assert saved['p_error'] is None
    assert saved['p_result']['document_versions'] == job['versions']
    assert saved['p_result']['analysis_basis'] == 'duty_master'
