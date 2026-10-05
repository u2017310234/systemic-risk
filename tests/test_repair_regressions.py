import copy
import json
from datetime import date
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
import pytest
from src.config import cfg
from src.universe import BANKS, BANK_BY_ID
from src.metrics.srisk import calc_srisk, calc_srisk_shares, system_srisk
from src.metrics.mes import calc_lrmes
from src.publish import _build_payload, _write_json, common_cohort_change, publish_bank_csv
from src.pipeline import run_pipeline, validate_batch, process_bank
from src.storage import active_root

def record(bid='JPM', srisk=10.):
 b=BANK_BY_ID[bid]
 return dict(bank_id=bid,bank_name=b.name,region=b.region,mes=-.02,lrmes=.3,covar=-.01,
             delta_covar=-.005,covar_beta=1.2,srisk_usd_bn=srisk,market_cap_usd_bn=400.,debt_usd_bn=2000.)

def test_bpce_has_no_proxy_or_processing():
 assert not BANK_BY_ID['BPCE'].supported
 assert BANK_BY_ID['BPCE'].yf_ticker == ''
 assert process_bank(BANK_BY_ID['BPCE'],'2024-01-01','2024-12-31') is None

def test_missing_and_zero_are_distinct():
 shares=calc_srisk_shares({'a':10,'b':0,'c':None,'d':np.nan,'e':np.inf})
 assert shares=={'a':100.,'b':0.}
 assert system_srisk({'a':10,'b':20.,'c':np.inf})==30
 assert np.isnan(system_srisk({'a':None}))

@pytest.mark.parametrize('values',[(100,1000,1.1),(100,1000,-.1),(np.inf,1000,.5),(100,np.inf,.5),(None,1000,.5)])
def test_invalid_srisk_inputs(values):
 assert np.isnan(calc_srisk(*values))

def test_partial_total_not_system_total():
 p=_build_payload(date(2024,1,1),{'JPM':record(),'BAC':record('BAC',None)},999999.)
 assert p['system_srisk_usd_bn'] is None
 assert p['covered_srisk_usd_bn']==10
 assert p['coverage']['srisk_count']==1
 assert p['coverage']['missing']['BAC']=='srisk_inputs_unavailable'
 assert p['banks'][0]['srisk_share_pct'] is None

def test_duplicate_bank_excluded_at_publish_boundary():
 p=_build_payload(date(2024,1,1),{'GLE':record('GLE'),'BPCE':record('BPCE')},20)
 assert p['bank_count']==1 and p['covered_srisk_usd_bn']==10

def test_constant_cohort_not_apparent_crash():
 old={'methodology_version':'2','banks':[record('JPM',10.),record('ICBC',100.)]}
 new={'methodology_version':'2','banks':[record('JPM',12.)]}
 result=common_cohort_change(old,new)
 assert result['bank_ids']==['JPM'] and result['change_pct']==pytest.approx(20.)
 new['methodology_version']='3'
 assert not common_cohort_change(old,new)['comparable']

def test_strict_json_inf_nan_null(tmp_path):
 p=tmp_path/'out.json';_write_json({'a':np.nan,'b':[np.inf,1.]},p)
 assert json.loads(p.read_text())=={'a':None,'b':[None,1.]}
 assert 'NaN' not in p.read_text()

def test_corrected_csv_replaces_date(monkeypatch,tmp_path):
 monkeypatch.setattr(cfg,'data_dir',str(tmp_path))
 publish_bank_csv(BANK_BY_ID['JPM'],{'2024-01-01':record(srisk=10.)})
 publish_bank_csv(BANK_BY_ID['JPM'],{'2024-01-01':record(srisk=11.)})
 rows=pd.read_csv(tmp_path/'banks/JPM.csv')
 assert len(rows)==1 and rows.iloc[0].srisk_usd_bn==11

def test_atomic_pipeline_shares_and_failure(monkeypatch,tmp_path):
 monkeypatch.setattr(cfg,'data_dir',str(tmp_path))
 data={'2024-01-03':record()}
 with patch('src.pipeline.process_bank',side_effect=lambda bank,*args:copy.deepcopy(data) if bank.id=='JPM' else None):
  run_pipeline(date(2024,1,3),date(2024,1,1))
 root=active_root(tmp_path);validate_batch(root)
 latest=json.loads((root/'latest.json').read_text())
 assert latest['banks'][0]['srisk_share_pct']==100
 assert pd.read_csv(root/'banks/JPM.csv').iloc[0].srisk_share_pct==100
 pointer=(tmp_path/'current.json').read_bytes()
 with patch('src.pipeline.process_bank',return_value=None):
  with pytest.raises(RuntimeError):run_pipeline(date(2024,1,4),date(2024,1,1))
 assert (tmp_path/'current.json').read_bytes()==pointer
 assert cfg.data_dir==str(tmp_path)
 # Successful rerun revises both formats, rather than CSV keeping stale first row.
 data['2024-01-03']['srisk_usd_bn']=21.
 with patch('src.pipeline.process_bank',side_effect=lambda bank,*args:copy.deepcopy(data) if bank.id=='JPM' else None):
  run_pipeline(date(2024,1,3),date(2024,1,1))
 root=active_root(tmp_path);validate_batch(root)
 assert pd.read_csv(root/'banks/JPM.csv').iloc[0].srisk_usd_bn==21.

def test_no_subset_overwrite_or_pointer_traversal(monkeypatch,tmp_path):
 monkeypatch.setattr(cfg,'data_dir',str(tmp_path))
 (tmp_path/'current.json').write_text('{"run":"../../oops"}')
 with pytest.raises(ValueError):active_root(tmp_path)

def test_lrmes_known_beta_and_horizon_label():
 idx=pd.Series(np.linspace(-.05,.05,100));bank=idx*2
 assert calc_lrmes(bank,idx,market_drop=.4,h=22)==pytest.approx(.64)
 assert calc_lrmes(bank,idx,h=126)==calc_lrmes(bank,idx,h=22)

@pytest.mark.parametrize('drop',[-.1,0,1,1.1])
def test_bad_scenario_rejected(drop):
 with pytest.raises(ValueError):calc_lrmes(pd.Series(range(40)),pd.Series(range(40)),market_drop=drop)

def test_server_real_loader_and_methodology(monkeypatch,tmp_path):
 import risk_mcp.server as server
 monkeypatch.setattr(server,'DATA_DIR',tmp_path)
 monkeypatch.setattr(cfg,'github_repo','')
 outside=tmp_path.parent/'secret.json';outside.write_text('{"secret":1}')
 assert server._load_json('../secret.json') is None
 assert server.get_methodology()['version']=='2.0-beta-scenario'
 assert server.get_historical('JPM',start_date='bad').get('error')
 (tmp_path/'latest.json').write_text(json.dumps(_build_payload(date(2024,1,1),{'JPM':record()},10)))
 assert server.get_srisk_ranking(top_n=0).get('error')
 assert server.get_srisk_ranking()['coverage']['srisk_count']==1
 assert server.get_latest_metrics(bank_id='JPM')['aggregate_scope'].startswith('entire snapshot')

def test_csv_nulls_serialise_as_null(monkeypatch,tmp_path):
 import risk_mcp.server as server
 monkeypatch.setattr(server,'DATA_DIR',tmp_path)
 (tmp_path/'banks').mkdir();(tmp_path/'banks/JPM.csv').write_text('date,srisk_usd_bn,methodology_version\n2024-01-01,,2.0-beta-scenario\n')
 result=server.get_historical('JPM')
 assert result['records'][0]['srisk_usd_bn'] is None
 json.dumps(result,allow_nan=False)

def test_full_calculation_pipeline_without_live_network(monkeypatch,tmp_path):
 """Actual return transforms + rolling MES/CoVaR/LRMES/SRISK + atomic export."""
 monkeypatch.setattr(cfg,'data_dir',str(tmp_path))
 monkeypatch.setattr(cfg,'covar_window',60)
 dates=pd.bdate_range('2024-01-01',periods=85)
 rng=np.random.default_rng(13)
 index=pd.Series(100*np.exp(np.cumsum(rng.normal(0,.01,len(dates)))),index=dates)
 prices=pd.Series(50*np.exp(np.cumsum(rng.normal(0,.004,len(dates))+np.diff(np.log(index),prepend=np.log(index.iloc[0]))*1.4)),index=dates)
 def get_prices(ticker,*args):return index if ticker.startswith('^') else prices
 with patch('src.pipeline.fetch_prices',side_effect=get_prices), \
      patch('src.pipeline.fetch_market_cap_series',return_value=pd.Series(100.,index=dates)), \
      patch('src.pipeline.fetch_debt_series',return_value=pd.Series(2000.,index=dates)):
  run_pipeline(dates[-1].date(),dates[0].date(),['JPM'])
 root=active_root(tmp_path); validate_batch(root)
 payload=json.loads((root/'latest.json').read_text());bank=payload['banks'][0]
 assert bank['srisk_usd_bn']==pytest.approx(max(0,.08*2000-.92*100*(1-bank['lrmes'])),abs=.0001)
 assert bank['srisk_share_pct']==100
 assert payload['system_srisk_usd_bn'] is None
 assert payload['coverage']['srisk_count']==1
 assert bank['covar'] is not None
 # Only synthetic QA output. Not a real banking risk estimate.
 import os,shutil
 if os.getenv('RISK_QA_OUTPUT'):
  out=Path(os.environ['RISK_QA_OUTPUT']);shutil.copytree(root,out,dirs_exist_ok=True)
  for f in [out/'latest.json',*list((out/'history').glob('*.json'))]:
   data=json.loads(f.read_text());data['dataset_kind']='synthetic_test';f.write_text(json.dumps(data))

def test_mcp_transport_lists_and_calls_tools(monkeypatch,tmp_path):
 from fastapi.testclient import TestClient
 import risk_mcp.server as server
 monkeypatch.setattr(server,'DATA_DIR',tmp_path)
 monkeypatch.setattr(cfg,'github_repo','')
 (tmp_path/'latest.json').write_text(json.dumps(_build_payload(date(2024,1,1),{'JPM':record()},10)))
 headers={'host':'localhost:8000','accept':'application/json, text/event-stream'}
 with TestClient(server.app) as client:
  response=client.post('/mcp',headers=headers,json={'jsonrpc':'2.0','id':1,'method':'tools/list'})
  assert response.status_code==200
  assert 'get_latest_metrics' in {t['name'] for t in response.json()['result']['tools']}
  response=client.post('/mcp',headers=headers,json={'jsonrpc':'2.0','id':2,'method':'tools/call',
   'params':{'name':'get_latest_metrics','arguments':{}}})
  assert response.status_code==200
  result=response.json()['result'];assert not result.get('isError')
  payload=result.get('structuredContent') or json.loads(result['content'][0]['text'])
  assert payload['system_srisk_usd_bn'] is None and payload['covered_srisk_usd_bn']==10
  assert client.get('/health').json()['status']=='degraded'

def test_publication_config_change_and_subset_do_not_replace_active(monkeypatch,tmp_path):
 monkeypatch.setattr(cfg,'data_dir',str(tmp_path))
 with patch('src.pipeline.process_bank',side_effect=lambda bank,*args:{'2024-01-03':record()} if bank.id=='JPM' else None):
  run_pipeline(date(2024,1,3),date(2024,1,1))
 pointer=(tmp_path/'current.json').read_bytes()
 with pytest.raises(ValueError,match='Subset'):
  run_pipeline(date(2024,1,3),date(2024,1,1),['JPM'])
 monkeypatch.setattr(cfg,'srisk_k',.09)
 with pytest.raises(ValueError,match='Calibration'):
  run_pipeline(date(2024,1,3),date(2024,1,1))
 assert (tmp_path/'current.json').read_bytes()==pointer

def test_v1_results_not_silently_certified(monkeypatch,tmp_path):
 import risk_mcp.server as server
 monkeypatch.setattr(server,'DATA_DIR',tmp_path)
 (tmp_path/'latest.json').write_text(json.dumps({'methodology_version':'1.0','banks':[record()]}))
 assert 'error' in server.get_latest_metrics()
 assert 'error' in server.get_srisk_ranking()
