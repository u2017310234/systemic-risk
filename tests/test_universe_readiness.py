import json
from datetime import date
from pathlib import Path
import pytest
from src.universe import BANKS,BANK_BY_ID
from src.config import cfg
from src.readiness import inspect_inputs
from src.fetcher import fetch_market_cap_series


def test_fsb_membership_is_exact_not_merely_29():
    expected={'JPM','BAC','C','WFC','GS','MS','BK','STT','ICBC','CCB','ABC','BOC','BOCOM','HSBC','BARC','STAN','BNP','ACA','GLE','BPCE','DBK','UBS','ING','SAN','RBC','TD','MUFG','SMFG','MFG'}
    assert {b.id for b in BANKS} == expected
    assert len(BANKS)==len(expected)
    assert {b.id for b in BANKS if not b.supported} == {'BPCE','ACA'}
    for bid in ['RBC','TD']:
        b=BANK_BY_ID[bid]
        assert (b.region,b.quote_currency,b.reporting_currency,b.index_yf)==('CA','CAD','CAD','^GSPTSE')
    assert not BANK_BY_ID['ACA'].yf_ticker


def test_preflight_reports_every_bank_and_no_network(tmp_path,monkeypatch):
    (tmp_path/'manifest.json').write_text('{"series":{}}')
    monkeypatch.setattr(cfg,'market_inputs_dir',str(tmp_path))
    monkeypatch.setattr(cfg,'fundamentals_dir',str(tmp_path/'missing'))
    r=inspect_inputs('2025-05-16')
    assert r['expected_count']==29 and r['eligible_count']==27
    assert r['ready_count']==0 and not r['eligible_complete']
    assert len(r['banks'])==29
    assert next(b for b in r['banks'] if b['bank_id']=='ACA')['issues']==['listed_subsidiary_not_consolidated_group_equity']


def test_explicit_market_feed_never_falls_back_to_yahoo(tmp_path,monkeypatch):
    monkeypatch.setattr(cfg,'market_inputs_dir',str(tmp_path))
    monkeypatch.setattr(cfg,'fundamentals_dir',str(tmp_path/'missing'))
    import src.fetcher as f
    def forbidden(): raise AssertionError('Unexpected network provider fallback')
    monkeypatch.setattr(f,'_yf',forbidden)
    assert fetch_market_cap_series(BANK_BY_ID['JPM'],'2025-05-16','2025-05-16').empty


def test_historical_membership_uses_only_published_release():
    from src.universe import universe_evidence
    assert universe_evidence('2025-05-16')['list_year']=='2024'
    assert universe_evidence('2025-11-27')['list_year']=='2024'
    assert universe_evidence('2025-11-28')['list_year']=='2025'
    with pytest.raises(ValueError):universe_evidence('2023-11-27')


def test_ubs_issued_share_tag_is_not_used():
    from src.sec_inputs import extract_company_facts
    row={'end':'2024-12-31','filed':'2025-03-17','accn':'0001610520-25-000023','form':'20-F'}
    raw={'cik':1610520,'facts':{'dei':{'EntityCommonStockSharesOutstanding':{'units':{'shares':[{**row,'val':3462087722}]}}},
         'ifrs-full':{'NumberOfSharesOutstanding':{'units':{'shares':[{**row,'val':3174825251}]}}}}}
    r=extract_company_facts(raw,'UBS','2025-05-16')
    assert r['published_shares'][0]['value']==3174825251
    assert r['share_tag']=='ifrs-full:NumberOfSharesOutstanding'


def test_canadian_40f_and_future_shares_filter():
    from src.sec_inputs import extract_company_facts
    row={'end':'2024-10-31','filed':'2024-12-04','accn':'0001193125-24-270294','form':'40-F','val':1415080299}
    raw={'cik':1000275,'facts':{'dei':{'EntityCommonStockSharesOutstanding':{'units':{'shares':[row]}}}}}
    assert extract_company_facts(raw,'RBC','2025-05-16')['published_shares'][0]['value']==1415080299
    assert not extract_company_facts(raw,'RBC','2024-12-04')['published_shares']


def test_sec_equity_fallback_is_per_filing_not_global():
    from src.sec_inputs import extract_company_facts
    row={'end':'2025-03-31','filed':'2025-05-01','accn':'current','form':'10-Q','val':100}
    old={**row,'end':'2024-03-31','accn':'old'}
    raw={'cik':19617,'facts':{'us-gaap':{
      'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest':{'units':{'USD':[old]}},
      'StockholdersEquity':{'units':{'USD':[row]}}}}}
    result=extract_company_facts(raw,'JPM','2025-05-16')
    assert {r['accession'] for r in result['equity']}=={'old','current'}


def test_sec_invalid_zero_shares_are_audited_without_poisoning_current_fact():
    from src.sec_inputs import extract_company_facts
    row={'end':'2024-10-31','filed':'2024-12-04','accn':'valid','form':'40-F','val':1415080299}
    old={**row,'end':'2020-10-31','accn':'old','val':0}
    raw={'cik':1000275,'facts':{'dei':{'EntityCommonStockSharesOutstanding':{'units':{'shares':[row,old]}}}}}
    r=extract_company_facts(raw,'RBC','2025-05-16')
    assert len(r['published_shares'])==1
    assert r['rejected_facts'][0]['accession']=='old'


def test_balance_check_accounts_for_explicit_temporary_equity():
    from src.import_sec_batch import reconcile_balance
    liab={'effective_date':'2025-03-31','accession':'filing','value':100,'source':'test'}
    p={'currency':'USD','assets':[{**liab,'value':150000000}],
       'equity':[{**liab,'value':55999900}], 'temporary_equity':[{**liab,'value':94000000}]}
    assert reconcile_balance(p,liab)['status']=='passed'
    p['temporary_equity']=[]
    assert reconcile_balance(p,liab)['status']=='failed'


def test_quarantined_feed_is_rejected_before_file_access(tmp_path,monkeypatch):
    from src.market_inputs import load_series
    monkeypatch.setattr(cfg,'market_inputs_dir',str(tmp_path))
    (tmp_path/'manifest.json').write_text(json.dumps({'series':{'adjusted_close:UBSG.SW':{'status':'quarantined','reason':'currency and security identity conflict'}}}))
    with pytest.raises(ValueError,match='Quarantined'):load_series('UBSG.SW','adjusted_close','2025-05-16','2025-05-16')


def test_failed_batch_does_not_replace_existing_input(tmp_path,monkeypatch):
    import src.import_sec_batch as b
    monkeypatch.setattr(b,'REGISTRY',{'JPM':None})
    source=tmp_path/'source';source.mkdir();dest=tmp_path/'dest';dest.mkdir()
    (source/'JPM-companyfacts.json').write_text('{"cik":312069,"facts":{}}')
    path=dest/'JPM.json';path.write_text('keep')
    r=b.import_batch(source,dest,'2025-05-16')
    assert r['failed_count']==1 and path.read_text()=='keep'


def test_quality_exposes_cross_basis_and_aged_shares():
    from src.quality import assess_quality
    p={'date':'2025-05-16','coverage':{'expected_count':2,'srisk_count':2,'complete':True},'banks':[
      {'bank_id':'JPM','accounting_standard':'US-GAAP'},
      {'bank_id':'BARC','accounting_standard':'IFRS','market_cap_evidence':{'components':[{'shares_age_days':150}]}}]}
    codes={a['code'] for a in assess_quality(p,today=date(2025,5,16))['alerts']}
    assert {'MIXED_ACCOUNTING_BASES','OLD_SHARE_COUNT'}<=codes


def test_preflight_counts_prior_returns_not_closes(tmp_path,monkeypatch):
    import pandas as pd
    import src.readiness as r
    monkeypatch.setattr(r,'BANKS',[BANK_BY_ID['JPM']])
    monkeypatch.setattr(cfg,'market_inputs_dir',str(tmp_path))
    monkeypatch.setattr(cfg,'fundamentals_dir',str(tmp_path))
    monkeypatch.setattr(cfg,'covar_window',30)
    (tmp_path/'JPM.json').write_text('{"accounting_standard":"US-GAAP"}')
    dates=pd.bdate_range(end='2025-05-16',periods=40)
    bank=pd.Series(range(1,41),index=dates,dtype=float)
    # 31 matched closes create 30 returns, but no extra target-day estimate.
    index=bank.iloc[-31:]
    monkeypatch.setattr(r,'load_series',lambda ident,*args:bank if ident=='JPM' else index)
    monkeypatch.setattr(r,'_verified_input',lambda *args:pd.Series([100.]))
    monkeypatch.setattr(r,'_component_market_cap',lambda *args:pd.Series([50.]))
    result=r.inspect_inputs('2025-05-16')
    assert result['ready_count']==0
    assert 'insufficient_matched_returns' in result['banks'][0]['issues']
