from datetime import date
from pathlib import Path
import copy,json
import pandas as pd
import pytest
from src.fundamentals import select_asof,calculate_group_market_cap,EvidenceError
from src.sec_inputs import extract_company_facts
from src.quality import assess_quality
from src.fetcher import fetch_market_cap_series,fetch_debt_series
from src.universe import BANK_BY_ID
from src.config import cfg
ROOT=Path(__file__).resolve().parents[1]

def fact(period,available,value):
 return dict(effective_date=period,available_date=available,value=value,source='https://example.org/filing')

def component():
 return dict(share_class_id='ordinary',instrument_type='ordinary',price_basis='unadjusted',price=10.,
  price_date='2025-05-16',price_source='test',share_source='test',issued_shares=100,treasury_shares=10,
  shares_effective_date='2025-03-31',shares_available_date='2025-05-15',currency='USD',split_basis='post-split',price_split_basis='post-split')

def test_repeated_old_comparative_cannot_overwrite_new_quarter():
 rows=[fact('2024-12-31','2025-02-15',100),fact('2025-03-31','2025-05-02',120),fact('2024-12-31','2025-05-03',101)]
 assert select_asof(rows,date(2025,5,16))['value']==120

def test_revision_only_after_publication():
 rows=[fact('2025-03-31','2025-05-15',100),fact('2025-03-31','2025-06-21',101)]
 assert select_asof(rows,date(2025,6,20))['value']==100
 assert select_asof(rows,date(2025,6,21))['value']==101

def test_republication_does_not_refresh_old_period():
 assert select_asof([fact('2024-01-01','2025-05-15',100)],date(2025,5,16)) is None

def test_ambiguous_revision_rejected():
 with pytest.raises(EvidenceError):select_asof([fact('2025-03-31','2025-05-15',100),fact('2025-03-31','2025-05-15',101)],date(2025,5,16))

def test_treasury_and_outstanding_are_not_subtracted_twice():
 c=component();assert calculate_group_market_cap([c],['ordinary'],'2025-05-16',{})['market_cap_usd_bn']==900/1e9
 c['outstanding_shares']=90
 with pytest.raises(EvidenceError):calculate_group_market_cap([c],['ordinary'],'2025-05-16',{})
 del c['issued_shares'];del c['treasury_shares']
 assert calculate_group_market_cap([c],['ordinary'],'2025-05-16',{})['market_cap_usd_bn']==900/1e9

@pytest.mark.parametrize('field,value',[('instrument_type','adr'),('price_basis','adjusted'),('price_date','2025-05-15'),('shares_available_date','2025-05-17'),('price_split_basis','pre-split')])
def test_unsafe_equity_component_rejected(field,value):
 c=component();c[field]=value
 with pytest.raises(EvidenceError):calculate_group_market_cap([c],['ordinary'],'2025-05-16',{})

def test_missing_class_or_fx_rejected():
 c=component()
 with pytest.raises(EvidenceError):calculate_group_market_cap([c],['ordinary','H'],'2025-05-16',{})
 c['currency']='HKD'
 with pytest.raises(EvidenceError):calculate_group_market_cap([c],['ordinary'],'2025-05-16',{})

def test_ah_equity_sum_in_correct_currency_units():
 # Test prices/FX are synthetic. Counts are real disclosed ICBC counts.
 a=component();a.update(share_class_id='A',issued_shares=269612212539,treasury_shares=0,currency='CNY',price=7)
 h=component();h.update(share_class_id='H',issued_shares=86794044550,treasury_shares=0,currency='HKD',price=5)
 result=calculate_group_market_cap([a,h],['A','H'],'2025-05-16',{'CNY':1/7,'HKD':1/7.8})
 assert result['market_cap_usd_bn']==pytest.approx((269612212539+86794044550*5/7.8)/1e9)
 assert result['quality']=='published_share_count_estimate'

def test_sec_identity_duration_and_future_filters():
 def row(**kw):return dict(end='2024-12-31',filed='2025-02-14',val=100,accn='0000019617-25-000270',form='10-K',**kw)
 payload={'cik':19617,'facts':{'us-gaap':{'Liabilities':{'units':{'USD':[row(),row(start='2024-01-01')]}}}}}
 result=extract_company_facts(payload,'JPM','2025-02-15')
 assert len(result['liabilities'])==1
 assert not extract_company_facts(payload,'JPM','2025-02-14')['liabilities']
 payload['cik']=312069
 with pytest.raises(ValueError):extract_company_facts(payload,'JPM','2025-02-15')

def test_real_official_balances_and_shares():
 report=json.loads((ROOT/'examples/verified-disclosures/reconciliation.json').read_text())
 assert len(report['checks'])==4
 for bank in report['checks']:assert bank['balance_residual']==0
 jpm,barc,icbc,smfg=report['checks']
 assert jpm['liabilities']==3658056000000
 assert barc['liabilities']==1445721000000
 assert sum(icbc['share_class_counts'].values())==icbc['share_count_total']
 assert smfg['issued_shares']-smfg['treasury_shares']==smfg['outstanding_shares']
 assert abs(jpm['reported_market_cap']-jpm['market_cap_reconstructed'])<20_000_000

def test_real_sources_asof_selection():
 d=ROOT/'examples/verified-disclosures'
 jpm=json.loads((d/'JPM.json').read_text());barc=json.loads((d/'BARC.json').read_text())
 assert select_asof(jpm['liabilities'],date(2025,5,16))['value']==4006436000000
 assert select_asof(barc['liabilities'],date(2025,5,16))['value']==1445721000000
 smfg=json.loads((d/'SMFG.json').read_text())
 assert select_asof(smfg['liabilities'],date(2025,5,14)) is None
 assert select_asof(smfg['liabilities'],date(2025,5,15))['value']==291440506000000

def test_mixed_accounting_basis_rejected(monkeypatch,tmp_path):
 monkeypatch.setattr(cfg,'fundamentals_dir',str(tmp_path))
 data={'bank_id':'SMFG','scope':'consolidated_group','currency':'JPY','accounting_standard':'J-GAAP',
  'liabilities':[{**fact('2025-03-31','2025-05-15',100),'accounting_standard':'IFRS'}]}
 (tmp_path/'SMFG.json').write_text(json.dumps(data))
 with pytest.raises(EvidenceError):fetch_debt_series(BANK_BY_ID['SMFG'],'2025-05-15','2025-05-16')

def test_quality_missing_stale_and_coverage_loss():
 previous={'coverage':{'srisk_ids':['JPM','BARC']},'banks':[]}
 now={'date':'2025-05-16','coverage':{'expected_count':29,'srisk_count':0,'srisk_ids':[],'complete':False},'banks':[]}
 report=assess_quality(now,previous,today=date(2025,6,1))
 assert report['status']=='error'
 assert {'NO_SRISK','STALE_SNAPSHOT','COVERAGE_LOSS'} <= {a['code'] for a in report['alerts']}

def test_pipeline_rejects_omitted_h_class_even_if_input_claims_complete(monkeypatch,tmp_path):
 monkeypatch.setattr(cfg,'fundamentals_dir',str(tmp_path))
 data={'bank_id':'ICBC','scope':'consolidated_group','expected_share_classes':['A'],'equity_valuations':[]}
 (tmp_path/'ICBC.json').write_text(json.dumps(data))
 with pytest.raises(EvidenceError):fetch_market_cap_series(BANK_BY_ID['ICBC'],'2025-05-15','2025-05-16')

def test_market_currency_conflict_fails_closed(monkeypatch,tmp_path):
 import hashlib
 from src.market_inputs import load_series
 monkeypatch.setattr(cfg,'market_inputs_dir',str(tmp_path))
 raw=b'date,value\n2025-05-16,325.5\n';(tmp_path/'barc.csv').write_bytes(raw)
 item={'identifier':'BARC.L','kind':'adjusted_close','source':'test','path':'barc.csv','sha256':hashlib.sha256(raw).hexdigest(),
       'provider_currency_label':'USD','currency':'GBp'}
 manifest={'series':{'adjusted_close:BARC.L':item}};(tmp_path/'manifest.json').write_text(json.dumps(manifest))
 with pytest.raises(ValueError,match='currency'):load_series('BARC.L','adjusted_close','2025-05-16','2025-05-16')
 item['currency_override']={'source':'https://example.org/issuer','reason':'fixture verified'}
 (tmp_path/'manifest.json').write_text(json.dumps(manifest))
 assert load_series('BARC.L','adjusted_close','2025-05-16','2025-05-16').attrs['currency_override']

def test_market_hash_and_future_release(monkeypatch,tmp_path):
 import hashlib
 from src.market_inputs import load_series
 monkeypatch.setattr(cfg,'market_inputs_dir',str(tmp_path))
 monkeypatch.setattr(cfg,'dataset_kind','research_estimate')
 raw=b'date,value\n2025-05-16,1.3257\n';(tmp_path/'fx.csv').write_bytes(raw)
 item={'identifier':'GBP','kind':'fx_usd_per_unit','source':'test','path':'fx.csv','sha256':hashlib.sha256(raw).hexdigest(),'available_date':'2025-05-19'}
 manifest={'series':{'fx_usd_per_unit:GBP':item}};(tmp_path/'manifest.json').write_text(json.dumps(manifest))
 assert load_series('GBP','fx_usd_per_unit','2025-05-16','2025-05-16').isna().all()
 monkeypatch.setattr(cfg,'dataset_kind','historical_reconstruction')
 assert load_series('GBP','fx_usd_per_unit','2025-05-16','2025-05-16').iloc[0]==1.3257
 (tmp_path/'fx.csv').write_text('date,value\n2025-05-16,999\n')
 with pytest.raises(ValueError,match='hash'):load_series('GBP','fx_usd_per_unit','2025-05-16','2025-05-16')
