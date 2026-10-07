"""Vendor responses are fixtures; these tests never claim live market validation."""
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import copy,json
import numpy as np
import pandas as pd
import pytest
from src.config import cfg
from src.universe import BANK_BY_ID,BANKS
from src import yahoo_daily
from src.calendar_status import publication_report

NOW=datetime(2026,10,7,10,tzinfo=timezone.utc)

@pytest.fixture
def daily(monkeypatch,tmp_path):
    monkeypatch.setattr(cfg,'fundamentals_policy','yahoo_daily')
    monkeypatch.setattr(cfg,'fundamentals_dir',str(tmp_path/'verified'))
    monkeypatch.setattr(cfg,'vendor_cache_dir',str(tmp_path/'vendor'))
    monkeypatch.setattr(cfg,'market_inputs_dir','')
    monkeypatch.setattr(cfg,'dataset_kind','research_estimate')
    monkeypatch.setattr(cfg,'publication_mode','research')
    monkeypatch.setattr(yahoo_daily,'now_utc',lambda:NOW)
    yahoo_daily._snapshot.cache_clear()
    yield
    yahoo_daily._snapshot.cache_clear()


def vendor():
    ticker=MagicMock()
    ticker.get_info.return_value={'sharesOutstanding':1e9,'currency':'USD','financialCurrency':'USD'}
    ticker.history.return_value=pd.DataFrame({'Close':[100.]},index=pd.to_datetime(['2026-10-06']))
    ticker.get_balance_sheet.return_value=pd.DataFrame({'2026-06-30':[2e12]},index=['TotalLiabilitiesNetMinorityInterest'])
    return ticker


def test_current_yahoo_inputs_never_backfill_the_price_window(daily):
    from src.fetcher import fetch_market_cap_series,fetch_debt_series
    ticker=vendor()
    with patch('src.fetcher._yf') as yf:
        yf.return_value.Ticker.return_value=ticker
        cap=fetch_market_cap_series(BANK_BY_ID['JPM'],'2025-01-01','2026-10-07')
        debt=fetch_debt_series(BANK_BY_ID['JPM'],'2025-01-01','2026-10-07')
    assert list(cap.index)==list(pd.to_datetime(['2026-10-06']))
    assert cap.iloc[0]==100 and debt.iloc[0]==2000
    evidence=debt.attrs['selected_sources']['2026-10-06']
    assert evidence['report_period']=='2026-06-30' and evidence['disclosure_date'] is None
    assert evidence['retrieved_at'].startswith('2026-10-07') and not evidence['point_in_time_verified']
    assert ticker.get_balance_sheet.call_count==1
    assert list(Path(cfg.vendor_cache_dir).rglob('*.json'))
    assert yahoo_daily.series(BANK_BY_ID['JPM'],'liabilities','2025-01-01','2025-05-16').empty


def test_current_vendor_cannot_override_historical_or_group_scope(daily,monkeypatch):
    with patch('src.yahoo_daily._snapshot') as fetch:
        assert yahoo_daily.series(BANK_BY_ID['ICBC'],'market_cap','2025-01-01','2026-10-07').empty
        monkeypatch.setattr(cfg,'publication_mode','historical')
        assert yahoo_daily.series(BANK_BY_ID['JPM'],'liabilities','2025-01-01','2026-10-07').empty
        fetch.assert_not_called()


def test_wrong_currency_and_old_liabilities_do_not_become_usd(daily):
    ticker=vendor();ticker.get_info.return_value['financialCurrency']='JPY'
    with patch('src.fetcher._yf') as yf:
        yf.return_value.Ticker.return_value=ticker
        assert yahoo_daily.series(BANK_BY_ID['JPM'],'liabilities','2025-01-01','2026-10-07').empty
    yahoo_daily._snapshot.cache_clear()
    for file in Path(cfg.vendor_cache_dir).rglob('*.json'):file.unlink()
    ticker=vendor();ticker.get_balance_sheet.return_value.columns=['2025-06-30']
    with patch('src.fetcher._yf') as yf:
        yf.return_value.Ticker.return_value=ticker
        assert yahoo_daily.series(BANK_BY_ID['JPM'],'liabilities','2025-01-01','2026-10-07').empty


def test_market_metrics_can_publish_without_srisk_but_not_without_prices(daily,monkeypatch):
    from src.calendar_status import session_status
    from src.quality import assess_quality
    monkeypatch.setattr(cfg,'publication_mode','production')
    monkeypatch.setattr(cfg,'publication_basis','market_metrics')
    observations={}
    for bank in BANKS:
        if bank.supported:
            day=session_status(bank,'2026-10-07',now=NOW)['expected_session_date']
            observations[bank.id]={'metric_dates':{m:day for m in ('mes','lrmes','covar','delta_covar')}}
    payload={'date':'2026-10-06','fundamentals_policy':'yahoo_daily','dataset_kind':'research_estimate',
             'coverage':{'srisk_count':0,'expected_count':29},'banks':[]}
    payload['quality']=assess_quality(payload,today=NOW.date())
    report=publication_report(payload,observations,'2026-10-07',now=NOW)
    assert report['decision']=='accepted'
    assert report['fresh_count_by_metric']['srisk_usd_bn']==0
    assert publication_report(payload,{},'2026-10-07',now=NOW)['decision']=='rejected'


def test_optional_fundamentals_failure_keeps_calculated_market_metrics(daily,monkeypatch,tmp_path):
    from src.pipeline import process_bank
    monkeypatch.setattr(cfg,'covar_window',60)
    dates=pd.bdate_range(end='2026-10-07',periods=100)
    rng=np.random.default_rng(4)
    market=pd.Series(100*np.exp(np.cumsum(rng.normal(0,.01,100))),index=dates)
    stock=pd.Series(50*np.exp(np.cumsum(rng.normal(0,.004,100))) * (market/100)**1.3,index=dates)
    with patch('src.pipeline.fetch_prices',side_effect=lambda ticker,*a:market if ticker.startswith('^') else stock), \
         patch('src.pipeline.fetch_market_cap_series',side_effect=RuntimeError('vendor timeout')), \
         patch('src.pipeline.fetch_debt_series',side_effect=RuntimeError('vendor timeout')):
        result=process_bank(BANK_BY_ID['JPM'],'2026-01-01','2026-10-07')
    assert max(result)=='2026-10-06' # no intraday current close
    record=result[max(result)]
    assert all(record[m] is not None for m in ('mes','lrmes','covar','delta_covar'))
    assert record['srisk_usd_bn'] is None and any('vendor timeout' in w for w in record['data_quality_warnings'])


def test_daily_updates_do_not_erase_previously_published_srisk(daily,monkeypatch,tmp_path):
    from src.pipeline import run_pipeline,validate_batch
    from src.storage import active_root
    monkeypatch.setattr(cfg,'data_dir',str(tmp_path/'data'))
    # Wall clock actual date matters to the public CLI guard; use today's date.
    day=date.today(); yesterday=(pd.Timestamp(day)-pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    record={'bank_id':'JPM','bank_name':'JPM','region':'US','mes':-.01,'lrmes':.3,'covar':-.02,
            'delta_covar':-.01,'srisk_usd_bn':12.,'market_cap_usd_bn':100.,'debt_usd_bn':1000.}
    values={yesterday:record}
    with patch('src.pipeline.process_bank',side_effect=lambda bank,*a:copy.deepcopy(values) if bank.id=='JPM' else None):
        run_pipeline(day,day-pd.Timedelta(days=400))
    values={yesterday:{**record,'srisk_usd_bn':None},day.isoformat():{**record,'srisk_usd_bn':13.}}
    with patch('src.pipeline.process_bank',side_effect=lambda bank,*a:copy.deepcopy(values) if bank.id=='JPM' else None):
        run_pipeline(day,day-pd.Timedelta(days=400))
    root=active_root(Path(cfg.data_dir));validate_batch(root)
    assert json.loads((root/'history'/f'{yesterday}.json').read_text())['banks'][0]['srisk_usd_bn']==12.


def test_fixture_end_to_end_yahoo_adapter_calculation_and_mcp(daily,monkeypatch,tmp_path):
    from src.pipeline import run_pipeline
    from src.acceptance import check_output
    from src.calendar_status import session_status
    actual_now=datetime.now(timezone.utc)
    monkeypatch.setattr(yahoo_daily,'now_utc',lambda:actual_now)
    day=actual_now.date()
    due=session_status(BANK_BY_ID['JPM'],day.isoformat(),now=actual_now)['expected_session_date']
    monkeypatch.setattr(cfg,'data_dir',str(tmp_path/'data'))
    monkeypatch.setattr(cfg,'raw_dir',str(tmp_path/'raw'))
    monkeypatch.setattr(cfg,'covar_window',60)
    monkeypatch.setattr(cfg,'yf_request_delay',0)
    dates=pd.bdate_range(end=day,periods=110)
    rng=np.random.default_rng(812)
    index=pd.Series(100*np.exp(np.cumsum(rng.normal(0,.01,len(dates)))),index=dates)
    stock=pd.Series(100*np.exp(np.cumsum(rng.normal(0,.003,len(dates)))),index=dates)*(index/100)**1.2
    ticker=vendor()
    ticker.history.return_value=pd.DataFrame({'Close':stock})
    ticker.get_balance_sheet.return_value.columns=[(pd.Timestamp(due)-pd.Timedelta(days=90)).strftime('%Y-%m-%d')]
    with patch('src.fetcher._fetch_yf',side_effect=lambda name,*a:index if name.startswith('^') else stock), patch('src.fetcher._yf') as yf:
        yf.return_value.Ticker.return_value=ticker
        run_pipeline(day,(dates[0]-pd.Timedelta(days=1)).date(),['JPM'])
    import subprocess,sys
    code='import json,sys; from src.acceptance import check_output; print(json.dumps(check_output(sys.argv[1],["JPM"])))'
    result=subprocess.run([sys.executable,'-c',code,str(tmp_path/'data')],capture_output=True,text=True,check=True)
    report=json.loads(result.stdout)
    assert report['mcp_transport']=='passed' and report['json_csv_consistency']=='passed'
    assert report['bank_checks'][0]['liabilities_evidence']['point_in_time_verified'] is False


def test_demo_pointer_bootstraps_without_copying_old_calibration(daily,monkeypatch,tmp_path):
    import shutil
    from src.pipeline import run_pipeline
    from src.storage import active_root
    root=tmp_path/'data';shutil.copytree('data/runs/demo-v23',root/'runs/demo-v23')
    (root/'current.json').write_text('{"run":"demo-v23"}')
    monkeypatch.setattr(cfg,'data_dir',str(root))
    record={'bank_id':'JPM','bank_name':'JPM','region':'US','mes':-.01,'lrmes':.3,'covar':-.02,
            'delta_covar':-.01,'srisk_usd_bn':12.,'market_cap_usd_bn':100.,'debt_usd_bn':1000.}
    day=date.today()
    with patch('src.pipeline.process_bank',side_effect=lambda bank,*a:{day.isoformat():copy.deepcopy(record)} if bank.id=='JPM' else None):
        run_pipeline(day,day-pd.Timedelta(days=400))
    active=active_root(root)
    assert active.name!='demo-v23'
    assert not (active/'history/2025-05-16.json').exists()
    assert (root/'runs/demo-v23/history/2025-05-16.json').exists()
