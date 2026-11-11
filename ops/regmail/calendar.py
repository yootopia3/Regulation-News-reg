"""Korean business-day gate using KASI's official live holiday API."""
import os,urllib.parse,urllib.request,xml.etree.ElementTree as ET
from datetime import datetime
from .delivery import c,KST

URL='https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo'

def parse(raw,day,page):
    c.require(len(raw)<=1024*1024 and b'<!DOCTYPE' not in raw.upper() and b'<!ENTITY' not in raw.upper(),'holiday_response_invalid')
    try:root=ET.fromstring(raw)
    except ET.ParseError:raise c.Problem('holiday_response_invalid',502) from None
    c.require(root.findtext('./header/resultCode')=='00','holiday_lookup_failed',502)
    body=root.find('./body');c.require(body is not None,'holiday_response_invalid')
    try:total=int(body.findtext('totalCount'));page_no=int(body.findtext('pageNo'));size=int(body.findtext('numOfRows'))
    except (TypeError,ValueError):raise c.Problem('holiday_response_invalid',502) from None
    c.require(page_no==page and 1<=size<=1000 and 0<=total<=1000,'holiday_response_invalid')
    rows=[]
    for item in body.findall('./items/item'):
        stamp=item.findtext('locdate');flag=item.findtext('isHoliday');seq=item.findtext('seq')
        c.require(stamp and len(stamp)==8 and stamp.isdigit() and stamp[:6]==day.strftime('%Y%m') and flag in ('Y','N') and seq,'holiday_response_invalid')
        try:datetime.strptime(stamp,'%Y%m%d')
        except ValueError:raise c.Problem('holiday_response_invalid',502) from None
        rows.append((stamp,seq,flag,item.findtext('dateName') or '공휴일'))
    return total,size,rows

def business_day(moment=None,fetch=None):
    moment=moment or datetime.now(KST);day=moment.astimezone(KST).date()
    if day.weekday()>=5:return dict(business=False,date=day.isoformat(),reason='weekend')
    key=os.environ.get('REGMAIL_DATA_GO_KR_SERVICE_KEY','').strip()
    c.require(key,'holiday_key_missing',409)
    def request(page):
        query=urllib.parse.urlencode(dict(serviceKey=urllib.parse.unquote(key),solYear=day.year,solMonth=f'{day.month:02d}',pageNo=page,numOfRows=100))
        try:
            with urllib.request.urlopen(URL+'?'+query,timeout=30) as response:return response.read(1024*1024+1)
        except Exception:raise c.Problem('holiday_lookup_failed',502) from None
    fetch=fetch or request;page=1;rows=[];expected=None;seen=set()
    while True:
        total,size,part=parse(fetch(page),day,page)
        c.require(expected is None or total==expected,'holiday_response_changed');expected=total
        for row in part:
            c.require(row[:2] not in seen,'holiday_response_invalid');seen.add(row[:2]);rows.append(row)
        c.require(len(rows)<=total and len(part)<=size,'holiday_response_invalid')
        if len(rows)==total:break
        c.require(len(part)==size and page<10,'holiday_response_incomplete');page+=1
    names=[r[3] for r in rows if r[0]==day.strftime('%Y%m%d') and r[2]=='Y']
    # May 1 is also a bank non-business day even if an upstream calendar omits it.
    if (day.month,day.day)==(5,1):names.append('노동절')
    return dict(business=not names,date=day.isoformat(),reason='; '.join(names) if names else 'business_day',source='KASI getRestDeInfo')
