"""Current Yahoo research inputs, never a point-in-time historical backfill.

Each observation is retained with its retrieval time. Only the latest completed
primary-equity session may receive current vendor fundamentals. Group-scope
exceptions remain excluded. No report-period date is called a disclosure date.
"""
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import logging
from pathlib import Path
import numpy as np
import pandas as pd
from src.config import cfg

logger = logging.getLogger(__name__)


def now_utc():
    return datetime.now(timezone.utc)


def current_session(bank, end):
    from src.calendar_status import session_status
    now = now_utc()
    # This source cannot be selected to reconstruct earlier dates.
    if end != now.date().isoformat():
        return None
    return session_status(bank, end, now=now).get('expected_session_date')


def valid_number(value):
    return isinstance(value, (float,int,np.number)) and np.isfinite(value) and value > 0


def _capture(bank):
    from src.fetcher import _yf
    now=now_utc()
    from src.calendar_status import session_status
    completed=session_status(bank,now.date().isoformat(),now=now).get('expected_session_date')
    ticker=_yf().Ticker(bank.yf_ticker)
    snapshot={'bank_id':bank.id, 'ticker':bank.yf_ticker,
              'retrieved_at':now.isoformat(), 'source':f'https://finance.yahoo.com/quote/{bank.yf_ticker}/balance-sheet/',
              'point_in_time_verified':False, 'disclosure_date':None, 'completed_session_date':completed, 'errors':{}}
    try:
        info=ticker.get_info() or {}
        snapshot.update(shares=info.get('sharesOutstanding'),quote_currency=info.get('currency'),
                        financial_currency=info.get('financialCurrency'))
    except Exception as exc:
        snapshot['errors']['metadata']=f'{type(exc).__name__}: {exc}'
    try:
        frame=ticker.history(period='1mo',auto_adjust=False,actions=True)
        if frame is not None and not frame.empty:
            snapshot['closes']={pd.Timestamp(d).strftime('%Y-%m-%d'):float(v) for d,v in frame['Close'].dropna().items() if completed and pd.Timestamp(d).strftime('%Y-%m-%d')<=completed}
    except Exception as exc:
        snapshot['errors']['close']=f'{type(exc).__name__}: {exc}'
    try:
        frame=ticker.get_balance_sheet(freq='quarterly')
        # Do not substitute Total Debt: SRISK needs all liabilities.
        for field in ('TotalLiabilitiesNetMinorityInterest','Total Liabilities Net Minority Interest'):
            if frame is not None and field in frame.index:
                row=frame.loc[field].dropna().sort_index(ascending=False)
                if len(row):
                    snapshot.update(liabilities=float(row.iloc[0]),report_period=pd.Timestamp(row.index[0]).strftime('%Y-%m-%d'),liabilities_field=field)
                break
    except Exception as exc:
        snapshot['errors']['liabilities']=f'{type(exc).__name__}: {exc}'
    encoded=json.dumps(snapshot,sort_keys=True,allow_nan=False,default=str).encode()
    root=Path(cfg.vendor_cache_dir)/bank.id;root.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256(encoded).hexdigest()
    (root/f'{now.strftime("%Y%m%dT%H%M%S")}-{digest[:12]}.json').write_bytes(encoded)
    snapshot['input_sha256']=digest
    return snapshot


@lru_cache(maxsize=64)
def _snapshot(bank_id, retrieval_day, cache_directory, session_day):
    from src.universe import BANK_BY_ID
    bank=BANK_BY_ID[bank_id]
    root=Path(cache_directory)/bank.id
    now=now_utc()
    for file in sorted(root.glob('*.json'), reverse=True):
        raw=file.read_bytes(); data=json.loads(raw)
        age=(now-datetime.fromisoformat(data['retrieved_at'])).total_seconds()
        # Same-day successful inputs may survive fresh GitHub runners. Failed
        # snapshots are evidence only, never a reason to suppress recovery.
        if 0<=age<=21600 and data.get('retrieved_at','')[:10]==retrieval_day and data.get('completed_session_date')==session_day and not data.get('errors') and (valid_number(data.get('liabilities')) or valid_number(data.get('shares'))):
            data['input_sha256']=hashlib.sha256(raw).hexdigest()
            return data
    return _capture(bank)


def series(bank, field, start, end):
    from src.fetcher import convert_currency, MCAP_UPPER_BOUND_USD_BN
    empty=pd.Series(dtype=float)
    if cfg.market_inputs_dir or cfg.dataset_kind=='historical_reconstruction' or cfg.publication_mode=='historical':
        return empty
    day=current_session(bank,end)
    if not day or day<start or not bank.supported:
        return empty
    if field=='market_cap' and bank.market_cap_policy=='verified_input':
        return empty
    data=_snapshot(bank.id,now_utc().date().isoformat(),cfg.vendor_cache_dir,day)
    evidence={key:data.get(key) for key in ('source','retrieved_at','report_period','disclosure_date','point_in_time_verified','liabilities_field','input_sha256')}
    evidence.update(valuation_date=day, availability_policy='current_retrieval_for_daily_research_only')
    if field=='liabilities':
        value=data.get('liabilities');period=data.get('report_period')
        if not period or not 0<=(pd.Timestamp(day)-pd.Timestamp(period)).days<=200:
            return empty
        if data.get('financial_currency') != bank.reporting_currency:
            return empty
        currency=bank.reporting_currency
    else:
        price=data.get('closes',{}).get(day);shares=data.get('shares')
        if not valid_number(price) or not valid_number(shares):return empty
        # Yahoo marketCap currency can be ambiguous for pence-quoted listings.
        # Calculate latest close × current vendor shares with explicit units.
        if data.get('quote_currency') not in ({'GBp','GBX'} if bank.quote_currency in ('GBp','GBX') else {bank.quote_currency}):
            return empty
        value=price*shares;currency=bank.quote_currency
        evidence.update(shares=shares,price=price,quote_currency=currency,
                        share_basis='current_vendor_shares_not_historical_vintage')
    if not valid_number(value):return empty
    result=convert_currency(pd.Series(float(value)/1e9,index=pd.to_datetime([day])),currency)
    result=result.where(np.isfinite(result)&(result>0))
    if field=='market_cap':result=result.where(result<=MCAP_UPPER_BOUND_USD_BN)
    result.attrs.update(quality='yahoo_current_research_not_point_in_time_verified',
                        selected_sources={day:evidence},input_sha256=data['input_sha256'],accounting_standard='unspecified')
    return result
