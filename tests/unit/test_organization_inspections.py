import json
import pytest
from src.services.sanction_inspections.engine import analyze
from src.services.sanction_inspections.models import InspectionError, Page, Unit
from tests.unit.test_sanction_inspection_engine import client, finding, match, PUBLIC

BODY = '본부조직은 여신심사부, 인사부, 금융소비자보호부로 구성한다.'

def organization_unit(**updates):
    return Unit(**dict(document_id='org', revision=1, article_key='6', department='', body=BODY,
        active=True, reviewed=True, document_kind='organization', organization_names=['여신심사부', '인사부', '금융소비자보호부']) | updates)

def responses(name='여신심사부'):
    row = match()
    row.update(department_ref='org:6', department_name=name, evidence=[{'ref':'org:6','quote':BODY}])
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
    assert result['prompt_version']=='organization-v1'

def test_unknown_department_blocked():
    api,_=client(responses('가상부서'))
    with pytest.raises(InspectionError,match='invalid_department'):
        run(api,[organization_unit()])

@pytest.mark.parametrize('updates',[{'active':False},{'reviewed':False},{'organization_names':[]},{'document_kind':'allocation'}])
def test_missing_reviewed_roster_never_calls_ai(updates):
    api,calls=client(responses())
    with pytest.raises(InspectionError,match='no_active_documents'):
        run(api,[organization_unit(**updates)])
    assert not calls

def test_multiple_departments_in_same_article_supported():
    supplied=responses()
    second=dict(supplied[1]['matches'][0],department_name='금융소비자보호부')
    supplied[1]['matches'].append(second)
    api,_=client(supplied)
    assert len(run(api,[organization_unit()])['matches'])==2

def test_organization_evidence_must_name_selected_department():
    supplied=responses()
    supplied[1]['matches'][0]['evidence'][0]['quote']='본부조직은 여신심사부'
    supplied[1]['matches'][0]['department_name']='인사부'
    api,_=client(supplied)
    with pytest.raises(InspectionError,match='missing_department_evidence'):
        run(api,[organization_unit()])

def test_uncertain_mapping_returns_unmatched_for_manual_review():
    api,_=client([{'findings':[finding()]},{'matches':[], 'unmatched_finding_ids':['F1']}])
    assert run(api,[organization_unit()])['unmatched_finding_ids']==['F1']

