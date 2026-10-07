import copy
import json
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
import pytest
from src.config import cfg
from src.universe import BANKS, BANK_BY_ID
from src.calendar_status import session_status, publication_report
from src.analysis import scenario_grid, explain_change, bootstrap_uncertainty
from src.validation import evaluate_predictions


def test_exchange_holiday_and_missing_quote_are_distinct():
    closed=session_status(BANK_BY_ID['JPM'],'2024-07-04','2024-07-03',now='2024-07-04T23:00:00Z')
    missing=session_status(BANK_BY_ID['JPM'],'2024-07-05','2024-07-03',now='2024-07-05T23:00:00Z')
    assert closed['status']=='market_closed' and closed['up_to_date']
    assert missing['status']=='missing_data' and not missing['up_to_date']


def test_close_grace_uses_previous_due_session():
    result=session_status(BANK_BY_ID['JPM'],'2024-07-05','2024-07-03',now='2024-07-05T20:30:00Z')
    assert result['status']=='not_yet_due' and result['up_to_date']


def test_production_all_closed_with_fresh_prior_observations(monkeypatch):
    monkeypatch.setattr(cfg,'publication_mode','production')
    now=datetime(2024,7,7,23,tzinfo=timezone.utc)
    observations={}
    for bank in BANKS:
        state=session_status(bank,'2024-07-07',now=now)
        if bank.supported:
            assert state['expected_session_date'], (bank.id,state)
            observations[bank.id]={'srisk_date':state['expected_session_date']}
    payload={'coverage':{'srisk_count':27},'dataset_kind':'research_estimate'}
    report=publication_report(payload,observations,'2024-07-07',now=now)
    assert report['decision']=='accepted' and report['fresh_eligible_count']==27
    assert publication_report(payload,{},'2024-07-07',now=now)['decision']=='rejected'
    payload['coverage']['srisk_count']=0
    assert 'NO_SRISK' in publication_report(payload,observations,'2024-07-07',now=now)['reasons']


def test_production_rejection_keeps_committed_pointer(monkeypatch,tmp_path):
    from src.pipeline import run_pipeline
    monkeypatch.setattr(cfg,'data_dir',str(tmp_path))
    monkeypatch.setattr(cfg,'publication_mode','research')
    bank={'bank_id':'JPM','bank_name':'JPM','region':'US','mes':-.01,'lrmes':.3,
          'covar':-.01,'delta_covar':-.005,'srisk_usd_bn':10,'market_cap_usd_bn':400,'debt_usd_bn':2000}
    def process(b,*args): return {'2024-07-05':copy.deepcopy(bank)} if b.id=='JPM' else None
    with patch('src.pipeline.process_bank',side_effect=process):
        run_pipeline(date(2024,7,5),date(2024,7,1))
    pointer=(tmp_path/'current.json').read_bytes()
    monkeypatch.setattr(cfg,'publication_mode','production')
    with patch('src.pipeline.process_bank',side_effect=process):
        with pytest.raises(RuntimeError,match='Publication rejected'):
            run_pipeline(date(2024,7,5),date(2024,7,1))
    assert (tmp_path/'current.json').read_bytes()==pointer
    report=json.loads((tmp_path/'last-attempt.json').read_text())
    assert report['decision']=='rejected' and 'INSUFFICIENT_FRESH_ELIGIBLE_COVERAGE' in report['reasons']


def test_scenario_monotonic_and_boundary_unidentifiable():
    bank={'market_cap_usd_bn':100,'debt_usd_bn':2000,'lrmes':.64}
    grid=scenario_grid(bank,{'lrmes_market_drop':.4},[.2,.4],[.08])
    assert grid['beta']==pytest.approx(2)
    assert grid['rows'][0]['srisk_usd_bn']<grid['rows'][1]['srisk_usd_bn']
    assert scenario_grid({**bank,'lrmes':0},{'lrmes_market_drop':.4})['status']=='unavailable'
    with pytest.raises(ValueError): scenario_grid(bank,{},[1],[.08])


def test_shapley_reconciles_across_zero_boundary_and_rejects_calibration():
    a={'calibration_id':'same','methodology_version':'2.0-beta-scenario','date':'2024-01-01','parameters':{'srisk_k':.08},
       'banks':[{'bank_id':'JPM','market_cap_usd_bn':100,'debt_usd_bn':1000,'lrmes':0}]}
    b=copy.deepcopy(a);b['date']='2024-01-02';b['banks'][0].update(debt_usd_bn=1200,market_cap_usd_bn=90,lrmes=.4)
    result=explain_change(a,b,'JPM')
    assert result['previous_srisk_usd_bn']==0
    assert sum(result['contributions_usd_bn'].values())==pytest.approx(result['change_usd_bn'])
    b['calibration_id']='different'
    assert explain_change(a,b,'JPM')['status']=='unavailable'


def test_joint_bootstrap_reproducible_and_informative():
    rng=np.random.default_rng(22);index=pd.Series(rng.normal(0,.01,150));bank=index*1.5
    a=bootstrap_uncertainty(bank,index,n_bootstrap=50)
    assert a==bootstrap_uncertainty(bank,index,n_bootstrap=50)
    assert a['intervals']['lrmes']==pytest.approx([1-.6**1.5]*2)
    assert a['tail_observations']==8
    assert bootstrap_uncertainty(bank[:40],index[:40])['status']=='unavailable'


def test_evaluation_purges_unmatured_training_labels_and_blocks_lookahead():
    rows=[dict(entity='a',forecast_date='2024-01-01',known_at='2024-01-01',outcome_date='2024-02-01',score=.2,outcome=0),
          dict(entity='b',forecast_date='2024-02-01',known_at='2024-02-01',outcome_date='2024-05-01',score=.4,outcome=1),
          dict(entity='a',forecast_date='2024-04-01',known_at='2024-04-01',outcome_date='2024-05-01',score=.7,outcome=1)]
    report=evaluate_predictions(rows,'2024-03-01')
    assert report['train_count']==1 and report['test_brier']==pytest.approx(.09)
    rows[-1]['known_at']='2024-04-02'
    with pytest.raises(ValueError,match='Look-ahead'):evaluate_predictions(rows,'2024-03-01')


def test_mcp_metadata_scenarios_and_holiday_bank_lookup(monkeypatch,tmp_path):
    import risk_mcp.server as server
    payload=json.loads(Path('examples/verified-disclosures-v23/reconstructed-snapshot.json').read_text())
    monkeypatch.setattr(server,'DATA_DIR',tmp_path)
    monkeypatch.setattr(cfg,'github_repo','')
    (tmp_path/'history').mkdir()
    (tmp_path/'history'/f"{payload['date']}.json").write_text(json.dumps(payload))
    latest=copy.deepcopy(payload);latest['date']='2025-05-19';latest['banks']=[b for b in latest['banks'] if b['bank_id']!='JPM']
    (tmp_path/'latest.json').write_text(json.dumps(latest))
    found=server.get_latest_metrics('JPM')
    assert found['as_of']=='2025-05-16' and found['requested_date']=='2025-05-19'
    assert 'system_srisk_usd_bn' not in found
    ranking=server.get_srisk_ranking()
    assert ranking['calibration_id']==payload['calibration_id']
    assert all(b['bank_id']!='JPM' for b in ranking['ranking'])
    assert server.get_sensitivity('JPM','2025-05-16')['analysis']['status']=='ok'
    monkeypatch.setattr(cfg,'covar_window',999)
    assert server.get_methodology()['rolling_window_days']==252
