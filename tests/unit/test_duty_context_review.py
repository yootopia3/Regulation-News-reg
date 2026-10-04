import copy
import pytest
from src.services.sanction_inspections.master_engine import analyze_master
from src.services.sanction_inspections.duty_master import parse_master
from src.services.sanction_inspections.models import InspectionError, Page
from tests.unit.test_duty_master_inspections import Client, PUBLIC, assessment, finding, match, payload, run


def answers(assessments):
    return [{'findings':[finding()]}, {'matches':[match()], 'unmatched_finding_ids':[],
                                     'department_assessments':assessments}]


def test_full_source_reaches_matching_when_summary_omits_context():
    omitted = '합성 갑사의 해외송금 급증에 경고를 전달했으나 을사의 대응은 달랐다.'
    pages = [Page(number=1,text=PUBLIC), Page(number=2,text=omitted)]
    client = Client()
    result = analyze_master(pages,parse_master(payload()),client,versions={'m':1})
    assert omitted not in result['findings'][0]['summary']
    assert client.calls[1][1]['source_pages'] == [p.model_dump() for p in pages]
    assert 'sources' not in client.calls[1][1]['candidates'][0]
    assert result['prompt_version']=='duty-master-v2'


def test_included_and_excluded_have_source_and_master_identity():
    rejected = assessment(duty_ids=['HQ-002'],decision='excluded',reason='인사 지원업무는 거래 고객확인과 적용대상이 다르다.')
    result = run(Client(answers([assessment(),rejected])))
    records = result['department_assessments']
    assert [(a['department'],a['decision']) for a in records] == [('합성통제부','included'),('합성지원부','excluded')]
    assert len(result['matches'])==1


@pytest.mark.parametrize('records', [[], [assessment(decision='excluded')], [assessment(decision='uncertain')],
    [assessment(),assessment()], [assessment(finding_id='F2')], [assessment(duty_ids=['HQ-002'])]])
def test_contradictory_or_missing_assessments_rejected(records):
    with pytest.raises(InspectionError,match='invalid_department_assessment'):
        run(Client(answers(records)))


@pytest.mark.parametrize('ids', [['HQ-999'],['HQ-001','HQ-001']])
def test_invalid_audit_duty_ids_rejected(ids):
    with pytest.raises(InspectionError,match='invalid_duty_reference'):
        run(Client(answers([assessment(duty_ids=ids)])))


def test_assessment_cannot_mix_departments():
    with pytest.raises(InspectionError,match='invalid_department_assessment'):
        run(Client(answers([assessment(duty_ids=['HQ-001','HQ-002'])])))


@pytest.mark.parametrize('evidence', [[{'page':2,'quote':PUBLIC}],[{'page':1,'quote':'공시에서 찾을 수 없는 허위 인용'}]])
def test_assessment_evidence_must_exist_in_public_source(evidence):
    with pytest.raises(InspectionError,match='invalid_public_evidence'):
        run(Client(answers([assessment(public_evidence=evidence)])))


def test_selected_duties_must_match_assessment_exactly():
    data=payload(); extra=copy.deepcopy(data['duties'][0]); extra['id']='HQ-003'; data['duties'].append(extra)
    with pytest.raises(InspectionError,match='invalid_department_assessment'):
        run(Client(answers([assessment(duty_ids=['HQ-003'])])), data)


def test_different_duties_in_same_department_can_have_different_decisions():
    data=payload(); extra=copy.deepcopy(data['duties'][0]); extra['id']='HQ-003'; data['duties'].append(extra)
    result=run(Client(answers([assessment(),assessment(duty_ids=['HQ-003'],decision='uncertain')])),data)
    assert [a['decision'] for a in result['department_assessments']]==['included','uncertain']
    assert len({a['department'] for a in result['department_assessments']})==1
    assert result['matches'][0]['duty_ids']==['HQ-001']


def test_same_duty_cannot_be_both_included_and_uncertain():
    with pytest.raises(InspectionError,match='invalid_department_assessment'):
        run(Client(answers([assessment(),assessment(decision='uncertain')])))


def test_context_limit_includes_source_and_does_not_truncate():
    data=payload()
    for i in range(3,90):
        duty=copy.deepcopy(data['duties'][0]); duty['id']=f'HQ-{i:03}'; duty['detail']='합성 업무 설명 '*110
        data['duties'].append(duty)
    pages=[Page(number=1,text=PUBLIC)]+[Page(number=i,text='공개 원문 '*1700) for i in range(2,7)]
    client=Client()
    with pytest.raises(InspectionError,match='context_review_required'):
        analyze_master(pages,parse_master(data),client,versions={'m':1})
    assert len(client.calls)==1
