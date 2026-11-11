"""Korean business days from the user's chosen, maintained holiday list."""
import json
from datetime import date,datetime
from pathlib import Path
from .delivery import c,KST

CALENDAR=Path(__file__).with_name('holidays-kr.json')

def load_calendar(path=CALENDAR):
    def unique(pairs):
        value={}
        for key,item in pairs:
            c.require(key not in value,'holiday_calendar_invalid');value[key]=item
        return value
    try:
        raw=Path(path).read_bytes();c.require(len(raw)<=256_000,'holiday_calendar_invalid')
        value=json.loads(raw,object_pairs_hook=unique)
        c.require(value['format']=='regmail-holidays-v1','holiday_calendar_invalid')
        first=date.fromisoformat(value['valid_from']);last=date.fromisoformat(value['valid_through'])
        c.require(first.isoformat()==value['valid_from'] and last.isoformat()==value['valid_through'],'holiday_calendar_invalid')
        c.require(first<=last and date.fromisoformat(value['reviewed_at'])<=last,'holiday_calendar_invalid')
        c.require(set(value['years'])=={str(year) for year in range(first.year,last.year+1)},'holiday_calendar_invalid')
        for year,holidays in value['years'].items():
            c.require(isinstance(holidays,dict) and len(holidays)>=10,'holiday_calendar_invalid')
            for stamp,name in holidays.items():
                day=date.fromisoformat(stamp)
                c.require(stamp==day.isoformat() and str(day.year)==year and first<=day<=last and isinstance(name,str) and 0<len(name)<100,'holiday_calendar_invalid')
        return value
    except (OSError,ValueError,KeyError,TypeError):raise c.Problem('holiday_calendar_invalid',409) from None

def business_day(moment=None,calendar_path=CALENDAR):
    moment=moment or datetime.now(KST)
    c.require(moment.tzinfo is not None,'holiday_timezone_required')
    day=moment.astimezone(KST).date()
    if day.weekday()>=5:return dict(business=False,date=day.isoformat(),reason='weekend')
    value=load_calendar(calendar_path)
    c.require(value['valid_from']<=day.isoformat()<=value['valid_through'],'holiday_year_not_configured',409)
    name=value['years'][str(day.year)].get(day.isoformat())
    return dict(business=not name,date=day.isoformat(),reason=name or 'business_day',
        source='maintained official holiday list',valid_through=value['valid_through'])
