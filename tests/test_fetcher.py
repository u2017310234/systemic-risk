"""Numeric regression fixtures; no live network, no source-string assertions."""
import json
from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
import pytest
from src.config import cfg
from src.universe import BANK_BY_ID
from src.fetcher import convert_currency, fetch_market_cap_series, fetch_debt_series, fetch_prices, _to_usd_bs

@pytest.mark.parametrize('currency,amount,rate,expected', [
 ('HKD',780.,1/7.8,100.),('GBP',80.,1.25,100.),('GBp',8000.,1.25,100.),
 ('CHF',90.,1/0.9,100.),('JPY',15000.,1/150,100.),('CNY',720.,1/7.2,100.),
 ('EUR',100.,1.1,110.),('USD',100.,1.,100.)])
def test_fx(currency,amount,rate,expected):
 dates=pd.date_range('2024-01-01',periods=3)
 with patch('src.fetcher._yf') as yf:
  yf.return_value.download.return_value=pd.DataFrame({'Close':[rate]*3},index=dates)
  actual=convert_currency(pd.Series(amount,index=dates),currency)
  np.testing.assert_allclose(actual,expected)
  if currency!='USD': assert yf.return_value.download.call_args.args[0].endswith('USD=X')

def test_missing_fx_is_not_native_usd():
 dates=pd.date_range('2024-01-01',periods=2)
 with patch('src.fetcher._yf') as yf:
  yf.return_value.download.return_value=pd.DataFrame()
  assert convert_currency(pd.Series(780.,index=dates),'HKD').isna().all()

def test_stale_fx_and_no_future_backfill():
 dates=pd.to_datetime(['2024-01-01','2024-01-02','2024-02-01'])
 with patch('src.fetcher._yf') as yf:
  yf.return_value.download.return_value=pd.DataFrame({'Close':[1.25]},index=[dates[1]])
  result=convert_currency(pd.Series(80.,index=dates),'GBP')
  assert np.isnan(result.iloc[0]) and result.iloc[1]==100 and np.isnan(result.iloc[2])

@pytest.mark.parametrize('bank,currency',[('HSBC','USD'),('STAN','USD'),('UBS','USD'),('BARC','GBP'),('ICBC','CNY')])
def test_explicit_reporting_currency(bank,currency):
 with patch('src.fetcher.convert_currency',return_value=pd.Series(dtype=float)) as convert:
  _to_usd_bs(pd.Series(dtype=float),BANK_BY_ID[bank].yf_ticker)
  assert convert.call_args.args[1]==currency

def test_no_silent_h_share_to_a_share_fallback():
 with patch('src.fetcher._fetch_yf',return_value=None),patch('src.fetcher._fetch_ak') as ak:
  assert fetch_prices('1398.HK','2024-01-01','2024-01-03','601398',use_cache=False).empty
  ak.assert_not_called()

def ticker_fixture(shares=1e9,split=False):
 dates=pd.date_range('2024-01-01',periods=5,freq='B')
 ticker=MagicMock()
 ticker.history.return_value=pd.DataFrame({'Close':[50.]*5,'Stock Splits':[0,0,2 if split else 0,0,0]},index=dates)
 ticker.get_shares_full.return_value=pd.Series([shares,shares*2],index=dates[[1,3]])
 return ticker

def test_dated_shares_not_current_constant(monkeypatch,tmp_path):
 monkeypatch.setattr(cfg,'fundamentals_dir',str(tmp_path))
 with patch('src.fetcher._yf') as yf:
  yf.return_value.Ticker.return_value=ticker_fixture()
  result=fetch_market_cap_series(BANK_BY_ID['JPM'],'2024-01-01','2024-01-05')
  assert np.isnan(result.iloc[0]);assert list(result.iloc[1:])==[50,50,100,100]
  assert yf.return_value.Ticker.return_value.history.call_args.kwargs['auto_adjust'] is False

def test_outlier_is_excluded_not_kept(monkeypatch,tmp_path):
 monkeypatch.setattr(cfg,'fundamentals_dir',str(tmp_path))
 with patch('src.fetcher._yf') as yf:
  yf.return_value.Ticker.return_value=ticker_fixture(1e12)
  assert fetch_market_cap_series(BANK_BY_ID['JPM'],'2024-01-01','2024-01-05').isna().all()

def test_split_needs_verified_input(monkeypatch,tmp_path):
 monkeypatch.setattr(cfg,'fundamentals_dir',str(tmp_path))
 with patch('src.fetcher._yf') as yf:
  yf.return_value.Ticker.return_value=ticker_fixture(split=True)
  assert fetch_market_cap_series(BANK_BY_ID['JPM'],'2024-01-01','2024-01-05').empty

def test_multiclass_not_arbitrarily_divided_by_100(monkeypatch,tmp_path):
 monkeypatch.setattr(cfg,'fundamentals_dir',str(tmp_path))
 assert fetch_market_cap_series(BANK_BY_ID['ICBC'],'2024-01-01','2024-01-05').empty

def test_actual_publication_date_no_lookahead(monkeypatch,tmp_path):
 monkeypatch.setattr(cfg,'fundamentals_dir',str(tmp_path))
 (tmp_path/'JPM.json').write_text(json.dumps({'bank_id':'JPM','scope':'consolidated_group','currency':'USD',
  'liabilities':[{'effective_date':'2023-12-31','available_date':'2024-01-03','source':'test fixture','value':2e12}]}))
 result=fetch_debt_series(BANK_BY_ID['JPM'],'2024-01-01','2024-01-05')
 assert result.iloc[:2].isna().all(); assert (result.iloc[2:]==2000).all()

def test_no_period_end_liabilities_fallback(monkeypatch,tmp_path):
 monkeypatch.setattr(cfg,'fundamentals_dir',str(tmp_path))
 with patch('src.fetcher._yf') as yf:
  assert fetch_debt_series(BANK_BY_ID['JPM'],'2024-01-01','2024-01-05').empty
  yf.assert_not_called()
