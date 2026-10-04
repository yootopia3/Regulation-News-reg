import json
import pytest
from src.services.sanction_inspections.engine import analyze, normalized, organization_quote
from src.services.sanction_inspections.models import InspectionError, Page, Unit
from tests.unit.test_sanction_inspection_engine import client, finding, match, PUBLIC

BODY = '본부조직은 여신심사부, 인사부, 금융소비자보호부로 구성한다.'

def organization_unit(**updates):
    return Unit(**dict(document_id='org', revision=1, article_key='6', department='', body=BODY,
        active=True, reviewed=True, document_kind='organization', organization_names=['여신심사부', '인사부', '금융소비자보호부']) | updates)

def responses(candidate_id='C1'):
    row = match()
    row.pop('department_ref')
    row.pop('evidence')
    row.update(candidate_id=candidate_id)
    return [{'findings':[finding()]},{'matches':[row], 'unmatched_finding_ids':[]}]

def run(api, units):
    return analyze([Page(number=1,text=PUBLIC)],units,api,organization=True)

def test_roster_used_without_keyword_overlap_and_allocation_excluded():
    api,calls=client(responses())
    private=Unit(document_id='old',revision=1,article_key='1',department='여신심사부',body='ALLOCATION_PRIVATE_CANARY',active=True,reviewed=True)
    result=run(api,[organization_unit(),private])
    assert result['analysis_basis']=='organization'
    assert result['document_versions']=={'org':1}
    assert result['matches'][0]['department']=='여신심사부'
    assert 'ALLOCATION_PRIVATE_CANARY' not in json.dumps(calls)
    assert result['prompt_version']=='organization-v2'
    assert 'candidate_id' not in result['matches'][0]

def test_unknown_department_blocked():
    api,_=client(responses('C999'))
    with pytest.raises(InspectionError,match='invalid_response'):
        run(api,[organization_unit()])

@pytest.mark.parametrize('updates',[{'active':False},{'reviewed':False},{'organization_names':[]},{'document_kind':'allocation'}])
def test_missing_reviewed_roster_never_calls_ai(updates):
    api,calls=client(responses())
    with pytest.raises(InspectionError,match='no_active_documents'):
        run(api,[organization_unit(**updates)])
    assert not calls

def test_multiple_departments_in_same_article_supported():
    supplied=responses()
    second=dict(supplied[1]['matches'][0],candidate_id='C3')
    supplied[1]['matches'].append(second)
    api,_=client(supplied)
    assert len(run(api,[organization_unit()])['matches'])==2

def test_organization_evidence_is_exact_source_for_selected_department():
    api,_=client(responses('C2'))
    result=run(api,[organization_unit()])
    assert result['matches'][0]['evidence']==[{'ref':'org:6','quote':BODY}]
    assert result['matches'][0]['department']=='인사부'

def test_uncertain_mapping_returns_unmatched_for_manual_review():
    api,_=client([{'findings':[finding()]},{'matches':[], 'unmatched_finding_ids':['F1']}])
    assert run(api,[organization_unit()])['unmatched_finding_ids']==['F1']


def test_selection_binds_name_to_its_article_and_schema_restricts_ids():
    other_body = '영업조직에는 국제업무부 및 해외영업부를 둔다.'
    other = organization_unit(article_key='9', body=other_body,
        organization_names=['국제업무부', '해외영업부'])
    supplied = responses('C4')
    api, calls = client(supplied)
    result = run(api, [other, organization_unit()])
    selected = result['matches'][0]
    assert (selected['department'], selected['department_ref']) == ('국제업무부', 'org:9')
    assert selected['evidence'] == [{'ref': 'org:9', 'quote': other_body}]
    schema = calls[1]['text']['format']['schema']['$defs']['OrganizationSelection']['properties']
    assert schema['candidate_id']['enum'] == ['C1', 'C2', 'C3', 'C4', 'C5']
    assert not {'department_name','department_ref','evidence'} & schema.keys()


def test_ai_cannot_supply_its_own_evidence():
    supplied = responses()
    supplied[1]['matches'][0]['evidence'] = [{'ref':'org:9','quote':'다른 조문의 임의 인용문'}]
    api, _ = client(supplied)
    with pytest.raises(InspectionError, match='invalid_response'):
        run(api, [organization_unit()])


def test_quote_retains_original_spacing_and_includes_name_at_end_of_long_body():
    body = '본부 조직 목록 안내. ' * 50 + '여신 심사부'
    quote = organization_quote(organization_unit(body=body), '여신심사부')
    assert quote in body and len(quote)<=300
    assert '여신심사부' in normalized(quote)


@pytest.mark.parametrize('body', ['없는 조직의 본문입니다.', '여'+' '*301+'신심사부', '여신심사부'])
def test_invalid_source_cannot_be_used_as_quote(body):
    with pytest.raises(InspectionError, match='invalid_internal_evidence'):
        organization_quote(organization_unit(body=body), '여신심사부')


def test_duplicate_selected_department_is_still_rejected():
    supplied = responses()
    supplied[1]['matches'].append(dict(supplied[1]['matches'][0]))
    api, _ = client(supplied)
    with pytest.raises(InspectionError, match='invalid_department'):
        run(api, [organization_unit()])


def test_oversized_choice_list_fails_before_provider_call():
    names = [f'조직{i}부' for i in range(200)]
    units = [organization_unit(article_key=str(i), body=' '.join(names), organization_names=names)
             for i in range(1, 7)]
    api, calls = client()
    with pytest.raises(InspectionError, match='context_review_required'):
        run(api, units)
    assert not calls

