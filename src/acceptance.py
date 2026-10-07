"""Live Yahoo -> calculation -> publication -> real MCP transport acceptance.

This command never substitutes fixtures or the shipped demo. A provider outage
is a failed acceptance run, with a JSON report and nonzero exit code.
"""
import argparse
from datetime import date,timedelta,datetime,timezone
import json
from pathlib import Path
from src.config import cfg
from src.operational import DataUnavailable
from src.storage import active_root
from src.universe import BANK_BY_ID


def check_output(root, bank_ids):
    from src.pipeline import validate_batch
    from src.calendar_status import session_status
    root=Path(root);active=active_root(root);validate_batch(active)
    payload=json.loads((active/'latest.json').read_text())
    if payload.get('fundamentals_policy')!='yahoo_daily' or payload.get('dataset_kind')!='research_estimate':
        raise ValueError('Acceptance requires current Yahoo research data, not demo/historical data')
    checks=[]
    for bid in bank_ids:
        # Local markets can have different completed session dates.
        snapshots=sorted((active/'history').glob('*.json'),reverse=True)
        bank=None;day=None
        for file in snapshots:
            row=next((b for b in json.loads(file.read_text())['banks'] if b['bank_id']==bid),None)
            if row is not None:bank=row;day=file.stem;break
        if bank is None:raise DataUnavailable(f'{bid}: no observations')
        state=session_status(BANK_BY_ID[bid],date.today().isoformat(),day)
        if not state.get('up_to_date'):raise DataUnavailable(f'{bid}: stale {day}, expected {state.get("expected_session_date")}')
        missing=[m for m in ('mes','lrmes','covar','delta_covar','srisk_usd_bn') if bank.get(m) is None]
        if missing:raise DataUnavailable(f'{bid}: live acceptance missing {missing}')
        checks.append({'bank_id':bid,'as_of':day,'srisk_usd_bn':bank['srisk_usd_bn'],
                       'liabilities_evidence':bank.get('liabilities_evidence')})
    from fastapi.testclient import TestClient
    import risk_mcp.server as server
    original=server.DATA_DIR
    try:
        server.DATA_DIR=root
        with TestClient(server.app) as client:
            response=client.post('/mcp',headers={'host':'localhost:8000','accept':'application/json, text/event-stream'},
                json={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'get_latest_metrics','arguments':{}}})
            response.raise_for_status();result=response.json()['result']
            if result.get('isError'):raise ValueError('MCP tool failed')
            delivered=result.get('structuredContent') or json.loads(result['content'][0]['text'])
            if delivered.get('calibration_id')!=payload['calibration_id'] or delivered.get('banks')!=payload['banks']:
                raise ValueError('MCP delivered a different snapshot')
    finally:server.DATA_DIR=original
    return {'bank_checks':checks,'mcp_transport':'passed','json_csv_consistency':'passed','date':payload['date'],
            'calibration_id':payload['calibration_id'],'scope':'requested banks only; not a full-universe acceptance'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--banks',default='JPM,BAC');p.add_argument('--output',required=True);p.add_argument('--report',required=True)
    p.add_argument('--allow-unavailable',action='store_true',help='Operational no-data outcome exits 0, never claims acceptance passed')
    args=p.parse_args();report={'started_at':datetime.now(timezone.utc).isoformat(),'source':'live_yahoo','status':'failed'}
    try:
        bank_ids=[b.strip().upper() for b in args.banks.split(',')]
        if not bank_ids or any(b not in BANK_BY_ID for b in bank_ids):raise ValueError('Invalid bank IDs')
        output=Path(args.output)
        if output.exists() and any(output.iterdir()):raise ValueError('Acceptance output must be a new empty directory')
        cfg.data_dir=str(output);cfg.raw_dir=str(output.parent/'acceptance-raw')
        cfg.fundamentals_policy='yahoo_daily';cfg.publication_basis='market_metrics'
        cfg.publication_mode='research';cfg.dataset_kind='research_estimate'
        cfg.market_inputs_dir='';cfg.fundamentals_dir=str(output.parent/'acceptance-no-verified-inputs')
        from src.pipeline import run_pipeline
        today=date.today()
        run_pipeline(today,today-timedelta(days=int(cfg.covar_window*1.5)+30),bank_ids)
        report.update(check_output(output,bank_ids));report['status']='passed'
    except DataUnavailable as exc:
        report['status']='unavailable'
        report['error']=f'{type(exc).__name__}: {exc}'
    except Exception as exc:
        report['error']=f'{type(exc).__name__}: {exc}'
    destination=Path(args.report);destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report,indent=2,allow_nan=False))
    from src.workflow_run import write_actions_status
    write_actions_status(report['status'],report.get('error',''),ready=report['status']=='passed')
    if report['status']!='passed' and not (args.allow_unavailable and report['status']=='unavailable'):raise SystemExit(1)


if __name__=='__main__':main()
