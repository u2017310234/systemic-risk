"""Initialize a new UI-only demo directory from an explicitly selected snapshot.

Never downloads prices, modifies live data or pretends a one-day snapshot is a
historical backtest. The snapshot must already be a labeled reconstruction.
"""
import csv,json
from pathlib import Path


def install_demo(snapshot:Path,output:Path):
    payload=json.loads(snapshot.read_text())
    if payload.get('dataset_kind')!='historical_reconstruction' or payload.get('methodology_version')!='2.0-beta-scenario':
        raise ValueError('Only an explicitly labeled historical reconstruction may be used')
    if output.exists() and any(output.iterdir()):raise ValueError('Demo output must be empty; existing data is never overwritten')
    from datetime import date
    day=date.fromisoformat(payload['date']).isoformat()
    from src.universe import BANK_BY_ID
    for bank in payload.get('banks',[]):
        if bank['bank_id'] not in BANK_BY_ID:raise ValueError('Unknown bank identity')
    from src.publish import _write_json
    output.mkdir(parents=True,exist_ok=True);(output/'history').mkdir(exist_ok=True);(output/'banks').mkdir(exist_ok=True)
    _write_json(payload,output/'latest.json');_write_json(payload,output/'history'/f'{day}.json')
    fields=['date','methodology_version','mes','lrmes','covar','delta_covar','covar_beta','srisk_usd_bn','srisk_share_pct','market_cap_usd_bn','debt_usd_bn']
    for bank in payload['banks']:
        with (output/'banks'/f"{bank['bank_id']}.csv").open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerow({k:day if k=='date' else payload['methodology_version'] if k=='methodology_version' else bank.get(k) for k in fields})
    (output/'DEMO.txt').write_text('Historical single-day reconstruction for UI review. No invented time history or current-risk claim.\n')
    from src.pipeline import validate_batch
    validate_batch(output)


def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--snapshot',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();install_demo(a.snapshot,a.output)

if __name__=='__main__':main()
