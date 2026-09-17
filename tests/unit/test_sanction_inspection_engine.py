import json

import pytest

from src.services.sanction_inspections.client import InspectionClient, Settings
from src.services.sanction_inspections.engine import analyze, select_candidates
from src.services.sanction_inspections.models import Finding, InspectionError, Page, Unit

PUBLIC = '대출 심사에서 담보 평가 확인을 누락하여 부실 대출이 발생하였다.'
PRIVATE = '여신심사부는 대출 심사와 담보 평가 기준 수립 및 심사 결과 확인 업무를 담당한다.'


def unit(**updates):
    return Unit(**dict({'document_id': 'doc', 'revision': 3, 'article_key': '1',
                       'department': '여신심사부', 'body': PRIVATE, 'active': True, 'reviewed': True}, **updates))


def finding():
    return {'id': 'F1', 'title': '담보 평가 누락', 'summary': PUBLIC,
            'evidence': [{'page': 1, 'quote': PUBLIC}]}


def match():
    return {'finding_id': 'F1', 'department_ref': 'doc:1', 'related_work': '대출 담보 심사', 'rationale': '담보 평가 기준을 관리하는 부서로 검토가 필요합니다.',
            'evidence': [{'ref': 'doc:1', 'quote': PRIVATE}],
            'checks': [{'question': '최근 취급 건의 평가 승인 여부를 확인했는가?', 'evidence_to_request': '승인 이력 및 표본 점검 결과'}]}


def client(responses=None, **settings):
    supplied = responses if responses is not None else [{'findings': [finding()]}, {'matches': [match()], 'unmatched_finding_ids': []}]
    calls = []

    def transport(payload, key):
        calls.append(payload)
        value = supplied[len(calls)-1]
        return {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(value)}]}]}

    config = Settings(**dict({'enabled': True, 'policy_confirmed': True, 'model': 'test-model', 'api_key': 'fixture'}, **settings))
    return InspectionClient(config, transport), calls


def run(api, units=None):
    return analyze([Page(number=1, text=PUBLIC)], [unit()] if units is None else units, api)


def test_two_pass_private_draft_minimal_context_and_version_fingerprint():
    api, calls = client()
    excluded = unit(article_key='2', department='인사부', body='채용과 급여 산정 및 임직원 복리후생 담당')
    result = run(api, [unit(), excluded])
    assert result['status'] == 'needs_review'
    assert result['matches'][0]['department'] == '여신심사부'
    assert PRIVATE not in json.dumps(calls[0], ensure_ascii=False)
    assert PRIVATE in json.dumps(calls[1], ensure_ascii=False)
    assert excluded.body not in json.dumps(calls[1], ensure_ascii=False)
    for payload in calls:
        assert payload['store'] is False and payload['background'] is False
        assert payload['text']['format']['strict'] is True
        assert not {'tools', 'conversation', 'previous_response_id'} & payload.keys()
    other, _ = client()
    assert run(other, [unit(revision=4), excluded.model_copy(update={'revision': 4})])['fingerprint'] != result['fingerprint']


@pytest.mark.parametrize('setting', [{'enabled': False}, {'policy_confirmed': False}, {'api_key': ''}, {'model': ''}])
def test_disabled_or_unconfigured_never_calls_provider(setting):
    api, calls = client(**setting)
    with pytest.raises(InspectionError):
        run(api)
    assert calls == []


def test_unreviewed_and_retired_documents_are_excluded():
    api, calls = client()
    with pytest.raises(InspectionError, match='no_active_documents'):
        run(api, [unit(active=False), unit(article_key='2', reviewed=False)])
    assert not calls


def test_cross_reference_expansion_and_missing_reference_fail_closed():
    first = unit(body=PRIVATE + ' 제2조에 따른다.')
    second = unit(article_key='2', department='', body='공통 정의에 따른 기준과 방법을 사용한다.')
    assert {u.ref for u in select_candidates(Finding(**finding()), [first, second])} == {'doc:1', 'doc:2'}
    with pytest.raises(InspectionError, match='reference_review_required'):
        select_candidates(Finding(**finding()), [first])


@pytest.mark.parametrize('reference', ['은행법 제2조에 따른다.', '「개인정보 보호법」 제2조를 준용한다.',
                                      '은행법의 제2조를 준용한다.', '「은행법」의 제2조를 준용한다.',
                                      '은행법에 따른 제2조를 준용한다.',
                                      '제2조부터 제4조까지 적용한다.', '제2조 내지 제4조를 적용한다.'])
def test_external_or_range_reference_never_transmits_unrelated_articles(reference):
    api, calls = client()
    with pytest.raises(InspectionError, match='reference_review_required'):
        run(api, [unit(body=PRIVATE + reference), unit(article_key='2', body='별도 내부 비공개 자료 내용', department=''),
                  unit(article_key='3', body='중간 조문 내용', department=''), unit(article_key='4', body='마지막 조문 내용', department='')])
    assert len(calls) == 1


def test_context_limit_does_not_truncate_or_transmit_private_text():
    api, calls = client()
    with pytest.raises(InspectionError, match='context_review_required'):
        run(api, [unit(body=PRIVATE * 1000)])
    assert len(calls) == 1


def test_no_candidate_requires_review_without_private_call():
    api, calls = client()
    result = run(api, [unit(body='채용 급여 복리후생', department='인사부')])
    assert result['unmatched_finding_ids'] == ['F1']
    assert result['matches'] == [] and len(calls) == 1


@pytest.mark.parametrize('field,value,code', [
    ('department_ref', 'invented:1', 'invalid_department'),
    ('finding_id', 'F2', 'finding_coverage_failed'),
    ('evidence', [{'ref': 'doc:1', 'quote': '입력에 존재하지 않는 가상의 근거'}], 'invalid_internal_evidence'),
    ('evidence', [{'ref': 'doc:1', 'quote': '        '}], 'invalid_internal_evidence'),
])
def test_invalid_model_references_rejected(field, value, code):
    row = match(); row[field] = value
    api, _ = client([{'findings': [finding()]}, {'matches': [row], 'unmatched_finding_ids': []}])
    with pytest.raises(InspectionError, match=code):
        run(api)


def test_wrong_public_page_prevents_private_transmission():
    row = finding(); row['evidence'][0]['page'] = 2
    api, calls = client([{'findings': [row]}])
    with pytest.raises(InspectionError, match='invalid_public_evidence'):
        run(api)
    assert len(calls) == 1


def test_internal_long_quote_outside_evidence_blocked():
    body = PRIVATE + ' 해당 기준은 업무의 적정성과 승인 절차에 따라 지속적으로 확인한다.'
    row = match(); row['rationale'] = body
    api, _ = client([{'findings': [finding()]}, {'matches': [row], 'unmatched_finding_ids': []}])
    with pytest.raises(InspectionError, match='private_quote_review_required'):
        run(api, [unit(body=body)])


@pytest.mark.parametrize('raw,code', [
    ({'status': 'incomplete'}, 'incomplete_response'),
    ({'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'refusal'}]}]}, 'refused'),
    ({'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'PRIVATE_CANARY'}]}]}, 'invalid_response'),
])
def test_provider_failure_is_sanitized(raw, code):
    api, _ = client()
    api.transport = lambda *_: raw
    with pytest.raises(InspectionError, match=code) as error:
        run(api)
    assert 'PRIVATE_CANARY' not in str(error.value)
    assert error.value.__suppress_context__ or code != 'invalid_response'


def test_settings_repr_hides_key():
    assert 'fixture' not in repr(Settings(True, True, 'model', 'fixture'))


def test_inconsistent_document_versions_block_before_request():
    api, calls = client()
    with pytest.raises(InspectionError, match='version_conflict'):
        run(api, [unit(), unit(article_key='2', revision=4)])
    assert not calls


def test_blank_pdf_text_cannot_be_analyzed():
    api, calls = client()
    with pytest.raises(InspectionError, match='source_text_required'):
        analyze([Page(number=1, text='  \n ')], [unit()], api)
    assert not calls


def test_unmatched_and_matched_overlap_or_omission_are_not_accepted():
    for response in [{'matches': [match()], 'unmatched_finding_ids': ['F1']},
                     {'matches': [], 'unmatched_finding_ids': []}]:
        api, _ = client([{'findings': [finding()]}, response])
        with pytest.raises(InspectionError, match='finding_coverage_failed'):
            run(api)


def test_unknown_model_fields_and_wrapped_lists_are_rejected():
    for response in [[{'findings': [finding()]}], {'findings': [finding()], 'instructions': 'PRIVATE_CANARY'}]:
        api, _ = client([response])
        with pytest.raises(InspectionError, match='invalid_response'):
            run(api)


def test_transport_locks_endpoint_and_rejects_redirect_without_logging(monkeypatch):
    from src.services.sanction_inspections.client import ENDPOINT, post_response
    calls = []

    class Response:
        status_code = 302
        def __enter__(self): return self
        def __exit__(self, *_): pass

    class Session:
        trust_env = True
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def post(self, url, **kwargs):
            calls.append((url, kwargs, self.trust_env))
            return Response()

    monkeypatch.setattr('src.services.sanction_inspections.client.requests.Session', Session)
    with pytest.raises(InspectionError, match='provider_failed'):
        post_response({'input': 'PRIVATE_CANARY'}, 'fixture')
    assert calls[0][0] == ENDPOINT
    assert calls[0][1]['allow_redirects'] is False
    assert calls[0][2] is False
