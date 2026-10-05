"""SEC Company Facts adapter. Reads entity-level instant facts, never duration EPS shares.

No credentials. Imported data remains reviewable, with filing accession and
availability policy. The API's filed date is not necessarily the first public
announcement; next-calendar-day activation is a conservative daily convention.
"""
from datetime import date,timedelta
import json,hashlib,math
from pathlib import Path
# CIKs verified against official SEC entities and filings.
REGISTRY={'JPM': (19617, 'us-gaap', 'USD', 'US-GAAP'), 'BAC': (70858, 'us-gaap', 'USD', 'US-GAAP'), 'C': (831001, 'us-gaap', 'USD', 'US-GAAP'), 'WFC': (72971, 'us-gaap', 'USD', 'US-GAAP'), 'GS': (886982, 'us-gaap', 'USD', 'US-GAAP'), 'MS': (895421, 'us-gaap', 'USD', 'US-GAAP'), 'BK': (1390777, 'us-gaap', 'USD', 'US-GAAP'), 'STT': (93751, 'us-gaap', 'USD', 'US-GAAP'), 'BARC': (312069, 'ifrs-full', 'GBP', 'IFRS'), 'RBC': (1000275, 'ifrs-full', 'CAD', 'IFRS'), 'TD': (947263, 'ifrs-full', 'CAD', 'IFRS'), 'HSBC': (1089113, 'ifrs-full', 'USD', 'IFRS'), 'ING': (1039765, 'ifrs-full', 'EUR', 'IFRS'), 'SAN': (891478, 'ifrs-full', 'EUR', 'IFRS'), 'UBS': (1610520, 'ifrs-full', 'USD', 'IFRS'), 'DBK': (1159508, 'ifrs-full', 'EUR', 'IFRS')}
# UBS DEI cover reports issued shares including treasury. Explicit override only.
SHARE_TAGS={'UBS':('ifrs-full','NumberOfSharesOutstanding')}
FORMS={'10-K','10-Q','20-F','40-F','6-K','10-K/A','10-Q/A','20-F/A','40-F/A','6-K/A'}

def extract_company_facts(payload:dict, bank_id:str, asof:str) -> dict:
    cik,ns,currency,standard=REGISTRY[bank_id]
    if int(payload.get('cik',-1))!=cik:raise ValueError('Wrong legal entity CIK')
    cutoff=date.fromisoformat(asof)
    rejected=[]
    def extract(namespace,tag,unit):
        records=[];seen=set()
        for r in payload.get('facts',{}).get(namespace,{}).get(tag,{}).get('units',{}).get(unit,[]):
            if r.get('start') or r.get('form') not in FORMS:continue
            if not r.get('filed') or not r.get('end') or not r.get('accn'):continue
            available=date.fromisoformat(r['filed'])+timedelta(days=1)
            if available>cutoff or r['end']>asof:continue
            value=r.get('val')
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or ((unit=='shares' or tag in ('Assets','Liabilities')) and value<=0):
                rejected.append({'tag':namespace+':'+tag,'accession':r['accn'],'end':r['end'],'reason':'invalid_nonnegative_amount_or_positive_shares'})
                continue
            key=(r['end'],r['filed'],r['val'],r['accn'])
            if key in seen:continue
            seen.add(key)
            records.append({'effective_date':r['end'],'available_date':available.isoformat(),'value':r['val'],
                            'source':f"https://www.sec.gov/Archives/edgar/data/{cik}/{r['accn'].replace('-','')}/{r['accn']}-index.html",
                            'tag':namespace+':'+tag,'accession':r['accn'],'filed_date':r['filed'],'accounting_standard':standard,'currency':unit,
                            'availability_policy':'selected_SEC_filing_plus_one_calendar_day_not_first_public_disclosure'})
        return sorted(records,key=lambda r:(r['effective_date'],r['available_date'],r['accession']))
    preferred=extract(ns,'Equity' if ns=='ifrs-full' else 'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',currency)
    keys={(r['effective_date'],r['accession']) for r in preferred}
    fallback=extract(ns,'StockholdersEquity',currency) if ns=='us-gaap' else []
    equity=preferred+[r for r in fallback if (r['effective_date'],r['accession']) not in keys]
    return {'bank_id':bank_id,'scope':'consolidated_group','accounting_standard':standard,'currency':currency,
            'retrieved_asof':asof,'liabilities':extract(ns,'Liabilities',currency),
            'published_shares':extract(*SHARE_TAGS.get(bank_id,('dei','EntityCommonStockSharesOutstanding')),'shares'),
            'share_tag': ':'.join(SHARE_TAGS.get(bank_id,('dei','EntityCommonStockSharesOutstanding'))),
            'source_entity_name': payload.get('entityName'),
            'assets':extract(ns,'Assets',currency),
            'equity':equity,
            'temporary_equity':extract(ns,'TemporaryEquityCarryingAmountIncludingPortionAttributableToNoncontrollingInterests',currency) if ns=='us-gaap' else [],
            'rejected_facts':rejected,
            'source_api':f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json'}

def main():
    import argparse,urllib.request
    parser=argparse.ArgumentParser();parser.add_argument('--bank',choices=REGISTRY,required=True)
    parser.add_argument('--as-of',required=True);parser.add_argument('--input');parser.add_argument('--output',required=True)
    args=parser.parse_args();date.fromisoformat(args.as_of)
    if args.input:raw=Path(args.input).read_bytes()
    else:
        cik=REGISTRY[args.bank][0]
        request=urllib.request.Request(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json',
            headers={'User-Agent':'systemic-risk-research/2.1 (https://github.com/u2017310234/systemic-risk)'})
        with urllib.request.urlopen(request,timeout=30) as response:raw=response.read(20_000_001)
        if len(raw)>20_000_000:raise ValueError('Response too large')
    result=extract_company_facts(json.loads(raw),args.bank,args.as_of)
    if not result['liabilities']:raise ValueError('No usable liabilities; existing output unchanged')
    result['source_sha256']=hashlib.sha256(raw).hexdigest()
    from src.fundamentals import select_asof
    if select_asof(result['liabilities'],date.fromisoformat(args.as_of)) is None:
        raise ValueError('No sufficiently recent liabilities; existing output unchanged')
    from src.publish import _write_json
    _write_json(result,Path(args.output))
if __name__=='__main__':main()
