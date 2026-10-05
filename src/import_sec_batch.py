"""Offline SEC batch import; preserves an existing bank file on validation failure."""
import argparse, hashlib, json
from datetime import date
from pathlib import Path
from src.sec_inputs import REGISTRY, extract_company_facts
from src.fundamentals import select_asof
from src.publish import _write_json


def reconcile_balance(payload, selected):
    if not selected:return {'status':'missing_liabilities'}
    matched={}
    for field in ('assets','equity'):
        candidates=[r for r in payload.get(field,[]) if r['effective_date']==selected['effective_date'] and r['accession']==selected['accession']]
        if not candidates:return {'status':'missing_matching_'+field,'accession':selected['accession']}
        values={r['value'] for r in candidates}
        if len(values)!=1:return {'status':'conflicting_'+field,'accession':selected['accession']}
        matched[field]=values.pop()
    temporary={r['value'] for r in payload.get('temporary_equity',[]) if r['effective_date']==selected['effective_date'] and r['accession']==selected['accession']}
    if len(temporary)>1:return {'status':'conflicting_temporary_equity'}
    temp=next(iter(temporary),0)
    residual=matched['assets']-selected['value']-matched['equity']-temp
    return {'status':'passed' if abs(residual)<=1_000_000 else 'failed',
            'residual':residual,'temporary_equity':temp,'tolerance_native_units':1_000_000,
            'assets':matched['assets'],'liabilities':selected['value'],'equity':matched['equity'],
            'currency':payload['currency'],'effective_date':selected['effective_date'],
            'accession':selected['accession'],'source':selected['source']}


def import_batch(input_dir:Path,output_dir:Path,asof:str):
    cutoff=date.fromisoformat(asof);rows=[]
    for bid in REGISTRY:
        row={'bank_id':bid,'status':'not_written'};rows.append(row)
        path=input_dir/f'{bid}-companyfacts.json'
        try:
            raw=path.read_bytes();result=extract_company_facts(json.loads(raw),bid,asof)
            selected=select_asof(result['liabilities'],cutoff)
            row['balance_check']=reconcile_balance(result,selected)
            if selected is None:raise ValueError('No current liabilities within 200 days')
            if row['balance_check']['status']!='passed':raise ValueError('Balance reconciliation needs manual review')
            result['source_sha256']=hashlib.sha256(raw).hexdigest();result['balance_check']=row['balance_check']
            row['shares_available']=select_asof(result['published_shares'],cutoff) is not None
            _write_json(result,output_dir/f'{bid}.json');row['status']='written'
        except (OSError,ValueError,KeyError,TypeError) as exc:row['error']=str(exc)
    return {'asof':asof,'banks':rows,'written_count':sum(r['status']=='written' for r in rows),
            'failed_count':sum(r['status']!='written' for r in rows)}


def main():
    p=argparse.ArgumentParser();p.add_argument('--input-dir',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--as-of',required=True)
    p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    report=import_batch(a.input_dir,a.output_dir,a.as_of);_write_json(report,a.report)
    print(f"Imported {report['written_count']}; needs review {report['failed_count']}")
    if report['failed_count']:raise SystemExit(2)

if __name__=='__main__':main()
