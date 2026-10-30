"""Public evidence remains exact and fail-closed after one correction."""
from types import SimpleNamespace

import pytest

from src.services.sanction_inspections.engine import public_findings
from src.services.sanction_inspections.models import InspectionError, Page

TEXT = '담보 평가 확인 절차를 누락하여 개선이 요구되었다.'


def finding(**updates):
    return {'id': 'F1', 'title': '담보 확인 미흡', 'summary': '담보 확인 절차 개선 필요',
            'evidence': [{'page': 1, 'quote': TEXT}], **updates}


class Client:
    settings = SimpleNamespace(check=lambda: None)
    def __init__(self, *answers):
        self.answers, self.calls = answers, []
    def generate(self, instruction, data, schema):
        self.calls.append(data)
        answer = self.answers[len(self.calls)-1]
        if isinstance(answer, Exception):
            raise answer
        return schema.model_validate({'findings': answer})


def run(client):
    return public_findings([Page(number=1, text=TEXT)], client)


@pytest.mark.parametrize('evidence', [
    [{'page': 2, 'quote': TEXT}],
    [{'page': 1, 'quote': '원문에는 존재하지 않는 요약문'}],
    [{'page': 1, 'quote': '        '}],
    [{'page': 1, 'quote': '담보 평가...개선이 요구되었다.'}],
])
def test_invalid_correction_never_passes(evidence):
    bad = finding(evidence=evidence)
    client = Client([bad], [bad])
    with pytest.raises(InspectionError, match='invalid_public_evidence'):
        run(client)
    assert len(client.calls) == 2


@pytest.mark.parametrize('changed', [
    [finding(id='F2')], [finding(title='다른 지적사항')],
    [finding(summary='변경된 사실')], [finding(), finding(id='F2')],
])
def test_correction_cannot_change_or_add_findings(changed):
    client = Client([finding(evidence=[{'page': 2, 'quote': TEXT}])], changed)
    with pytest.raises(InspectionError, match='invalid_public_evidence'):
        run(client)
    assert len(client.calls) == 2


def test_correction_cannot_drop_a_finding():
    bad = finding(evidence=[{'page': 2, 'quote': TEXT}])
    client = Client([bad, finding(id='F2')], [finding()])
    with pytest.raises(InspectionError, match='invalid_public_evidence'):
        run(client)


def test_duplicate_finding_is_not_retried():
    client = Client([finding(), finding()])
    with pytest.raises(InspectionError, match='duplicate_finding'):
        run(client)
    assert len(client.calls) == 1


@pytest.mark.parametrize('during_correction', [False, True])
def test_provider_failures_are_not_retried(during_correction):
    error = InspectionError('rate_limited')
    bad = finding(evidence=[{'page': 2, 'quote': TEXT}])
    client = Client([bad], error) if during_correction else Client(error)
    with pytest.raises(InspectionError, match='rate_limited'):
        run(client)
    assert len(client.calls) == (2 if during_correction else 1)


def test_whitespace_remains_the_only_normalization():
    client = Client([finding(evidence=[{'page': 1, 'quote': TEXT.replace(' ', '\n')}])])
    assert run(client).findings[0].id == 'F1'
    assert len(client.calls) == 1


def test_quote_cannot_join_text_across_pages():
    pages = [Page(number=1, text='담보 평가 확인 절차'), Page(number=2, text='누락하여 개선이 요구되었다.')]
    bad = finding(evidence=[{'page': 1, 'quote': '담보 평가 확인 절차누락하여 개선이 요구되었다.'}])
    client = Client([bad], [bad])
    with pytest.raises(InspectionError, match='invalid_public_evidence'):
        public_findings(pages, client)
