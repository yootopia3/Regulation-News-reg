"""Source excerpt selection cannot invent quotes or alter public findings."""
from types import SimpleNamespace

import pytest

from src.services.sanction_inspections.engine import public_findings, public_evidence_candidates
from src.services.sanction_inspections.models import InspectionError, Page

TEXT = '담보 평가 확인 절차를 누락하여 개선이 요구되었다.'


def finding(**updates):
    return {'id': 'F1', 'title': '담보 확인 미흡', 'summary': '담보 확인 절차 개선 필요',
            'evidence': [{'page': 1, 'quote': TEXT}], **updates}


def correction(refs=None, finding_id='F1'):
    return {'finding_id': finding_id, 'refs': ['p1s1'] if refs is None else refs}


class Client:
    settings = SimpleNamespace(check=lambda: None)
    def __init__(self, *answers):
        self.answers, self.calls = answers, []
    def generate(self, instruction, data, schema):
        self.calls.append(data)
        answer = self.answers[len(self.calls)-1]
        if isinstance(answer, Exception):
            raise answer
        return schema.model_validate(answer)


def run(client):
    return public_findings([Page(number=1, text=TEXT)], client)


def bad_finding():
    return finding(evidence=[{'page': 2, 'quote': '원문에 없는 인용문을 만들었다.'}])


def test_selection_preserves_findings_and_uses_exact_source():
    original = bad_finding()
    client = Client({'findings': [original]}, {'corrections': [correction()]})
    result = run(client).findings[0]
    assert result.model_dump(exclude={'evidence'}) == {k:v for k,v in original.items() if k!='evidence'}
    assert result.evidence[0].page == 1 and result.evidence[0].quote == TEXT
    assert len(client.calls) == 2
    assert 'pages' not in client.calls[1]
    assert client.calls[1]['candidates'] == [{'ref':'p1s1','page':1,'quote':TEXT}]


@pytest.mark.parametrize('corrections', [
    [correction([])], [correction(['unknown'])], [correction(['p1s1','p1s1'])],
    [correction(finding_id='F2')], [correction(), correction()],
    [correction(), correction(finding_id='F2')],
])
def test_unbacked_unknown_duplicate_or_changed_finding_selection_fails(corrections):
    client = Client({'findings':[bad_finding()]}, {'corrections':corrections})
    with pytest.raises(InspectionError, match='invalid_public_evidence'):
        run(client)
    assert len(client.calls) == 2


def test_only_invalid_findings_are_corrected_without_dropping_valid_findings():
    original = finding(id='F2')
    client = Client({'findings':[bad_finding(), original]}, {'corrections':[correction()]})
    result = run(client)
    assert [f.id for f in result.findings] == ['F1','F2']
    assert result.findings[1].model_dump() == original
    assert len(client.calls[1]['findings']) == 1


def test_cannot_drop_an_invalid_finding():
    client = Client({'findings':[bad_finding(), {**bad_finding(),'id':'F2'}]},
                    {'corrections':[correction()]})
    with pytest.raises(InspectionError, match='invalid_public_evidence'):
        run(client)


def test_duplicate_original_finding_is_not_retried():
    client = Client({'findings':[finding(),finding()]})
    with pytest.raises(InspectionError, match='duplicate_finding'):
        run(client)
    assert len(client.calls) == 1


@pytest.mark.parametrize('during_correction', [False, True])
def test_provider_failures_are_not_retried(during_correction):
    error = InspectionError('rate_limited')
    client = Client({'findings':[bad_finding()]}, error) if during_correction else Client(error)
    with pytest.raises(InspectionError, match='rate_limited'):
        run(client)
    assert len(client.calls) == (2 if during_correction else 1)


def test_valid_whitespace_quote_does_not_request_correction():
    client = Client({'findings':[finding(evidence=[{'page':1,'quote':TEXT.replace(' ','\n')}])]})
    assert run(client).findings[0].id == 'F1'
    assert len(client.calls) == 1


def test_candidates_are_bounded_unchanged_single_page_substrings():
    pages = [Page(number=12,text=TEXT*40), Page(number=13,text='업무절차를 전반적으로 개선하시기 바랍니다.\n- 13 -')]
    candidates = public_evidence_candidates(pages)
    assert candidates
    for evidence in candidates.values():
        assert 8 <= len(evidence['quote']) <= 240
        assert evidence['quote'] in next(p.text for p in pages if p.number == evidence['page'])
    # A finding spanning a page break may cite its substantive preceding page.
    bad = finding(evidence=[{'page':13,'quote':TEXT}])
    client = Client({'findings':[bad]}, {'corrections':[correction(['p12s1'])]})
    result = public_findings(pages,client)
    assert result.findings[0].evidence[0].page == 12
    assert result.findings[0].summary == bad['summary']


def test_cross_page_concatenation_is_not_accepted_as_a_quote():
    pages = [Page(number=1,text='담보 평가 확인 절차'),Page(number=2,text='누락하여 개선이 요구되었다.')]
    bad = finding(evidence=[{'page':1,'quote':'담보 평가 확인 절차누락하여 개선이 요구되었다.'}])
    client = Client({'findings':[bad]}, {'corrections':[correction([])]})
    with pytest.raises(InspectionError, match='invalid_public_evidence'):
        public_findings(pages,client)
