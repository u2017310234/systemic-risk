from datetime import datetime,timezone
import copy
import pytest
from src.yahoo_inputs import normalize_chart


def ts(value):return int(datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp())

def fixture():
 return {'chart':{'error':None,'result':[{'meta':{'symbol':'8316.T','currency':'JPY','instrumentType':'EQUITY','exchangeName':'JPX','exchangeTimezoneName':'Asia/Tokyo'},'timestamp':[ts('2025-05-15T00:00:00'),ts('2025-05-16T00:00:00')],'indicators':{'quote':[{'close':[50.,55.]}],'adjclose':[{'adjclose':[45.,49.5]}]},'events':{'splits':{'later':{'date':ts('2026-09-29T00:00:00'),'numerator':2.,'denominator':1.}}}}]}}

def call(raw,**kw):return normalize_chart(raw,'8316.T','JPY','2025-05-16',expected_exchange='JPX',retrieved_on='2026-10-04',**kw)

def test_later_split_reversed_only_for_valuation_not_return_prices():
 d=call(fixture(),split_window_complete=True)
 assert d['valuation']['price']==110.
 assert d['valuation']['future_split_undo_factor']==2.
 assert d['adjusted_close']==[('2025-05-15',45.),('2025-05-16',49.5)]


def test_absent_event_window_attestation_does_not_emit_market_cap_price():
 assert call(fixture())['valuation'] is None


@pytest.mark.parametrize('key,value',[('symbol','UBER'),('currency','USD'),('instrumentType','ETF'),('exchangeName','NYQ')])
def test_wrong_identity_rejected(key,value):
 raw=fixture();raw['chart']['result'][0]['meta'][key]=value
 with pytest.raises(ValueError):call(raw,split_window_complete=True)


def test_local_exchange_date_is_not_utc_date():
 raw=fixture();r=raw['chart']['result'][0];r['timestamp']=[ts('2025-05-14T15:30:00'),ts('2025-05-15T15:30:00')]
 assert call(raw,split_window_complete=True)['valuation']['price']==110.


def test_same_day_missing_close_not_forward_filled():
 raw=fixture();raw['chart']['result'][0]['indicators']['quote'][0]['close'][-1]=None
 assert call(raw,split_window_complete=True)['valuation'] is None


def test_future_quote_does_not_enter_return_history():
 raw=fixture();r=raw['chart']['result'][0]
 r['timestamp'].append(ts('2025-05-19T00:00:00'));r['indicators']['quote'][0]['close'].append(99.);r['indicators']['adjclose'][0]['adjclose'].append(88.)
 assert len(call(raw,split_window_complete=True)['adjusted_close'])==2


def test_invalid_split_and_duplicate_date_rejected():
 raw=fixture();raw['chart']['result'][0]['events']['splits']['later']['denominator']=0
 with pytest.raises(ValueError):call(raw,split_window_complete=True)
 raw=fixture();raw['chart']['result'][0]['timestamp'][1]=raw['chart']['result'][0]['timestamp'][0]
 with pytest.raises(ValueError):call(raw,split_window_complete=True)


def test_past_split_is_not_multiplied_twice():
 raw=fixture();raw['chart']['result'][0]['events']['splits']['later']['date']=ts('2024-09-27T00:00:00')
 assert call(raw,split_window_complete=True)['valuation']['price']==55.


def test_incomplete_array_is_rejected():
 raw=fixture();raw['chart']['result'][0]['indicators']['adjclose'][0]['adjclose'].pop()
 with pytest.raises(ValueError):call(raw)
