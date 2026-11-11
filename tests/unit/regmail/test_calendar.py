import json
from datetime import date,datetime,timedelta,timezone
import pytest
from ops.regmail.calendar import business_day,load_calendar

def moment(stamp):return datetime.fromisoformat(stamp+'T09:00:00+09:00')

def test_current_business_day_works_without_key_or_network(monkeypatch):
    monkeypatch.delenv('REGMAIL_DATA_GO_KR_SERVICE_KEY',raising=False)
    monkeypatch.setattr('urllib.request.urlopen',lambda *a,**k:pytest.fail('Calendar used the network'))
    result=business_day(moment('2026-11-11'))
    assert result['business'] is True and result['valid_through']=='2027-12-31'

@pytest.mark.parametrize('stamp',['2026-05-01','2026-07-17','2026-12-25','2027-02-09','2027-05-03','2027-05-13','2027-07-19','2027-12-27'])
def test_public_and_substitute_holidays_are_closed(stamp):
    assert business_day(moment(stamp))['business'] is False

def test_timezone_is_korean_and_weekends_skip_missing_calendar(tmp_path):
    assert business_day(datetime(2026,12,24,23,59,tzinfo=timezone.utc))['date']=='2026-12-25'
    assert business_day(datetime(2026,12,24,23,59,tzinfo=timezone.utc))['business'] is False
    assert business_day(moment('2026-11-14'),tmp_path/'missing.json')['reason']=='weekend'

@pytest.mark.parametrize('stamp',['2025-12-31','2028-01-03'])
def test_unregistered_year_never_defaults_to_business_day(stamp):
    with pytest.raises(Exception) as error:business_day(moment(stamp))
    assert error.value.code=='holiday_year_not_configured'

@pytest.mark.parametrize('mutation',['missing_year','invalid_date','compact_date','bad_json','duplicate_key'])
def test_corrupt_or_incomplete_calendar_fails_closed(tmp_path,mutation):
    value=load_calendar()
    if mutation=='missing_year':value['years'].pop('2027')
    if mutation=='invalid_date':value['years']['2026']['2026-11-99']='invalid'
    if mutation=='compact_date':value['years']['2026']['20261111']='invalid'
    raw=json.dumps(value)
    if mutation=='bad_json':raw='invalid JSON'
    if mutation=='duplicate_key':raw=raw.replace('"format":','"format":"duplicate","format":',1)
    path=tmp_path/'calendar.json';path.write_text(raw,encoding='utf-8')
    with pytest.raises(Exception) as error:business_day(moment('2026-11-11'),path)
    assert error.value.code=='holiday_calendar_invalid'

@pytest.mark.parametrize('year,expected',[(2026,120),(2027,119)])
def test_annual_closed_day_totals_match_latest_kasa_publication(year,expected):
    first=date(year,1,1);last=date(year,12,31);closed=0
    for offset in range((last-first).days+1):
        closed+=not business_day(moment((first+timedelta(days=offset)).isoformat()))['business']
    assert closed==expected
