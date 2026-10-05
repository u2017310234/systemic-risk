"""Offline, identity-checked Yahoo chart normalization for historical reconstruction.

Does not download, infer tickers, or claim a point-in-time vendor archive. Daily
adjusted close is for returns. Market-cap prices restore any later split factors
from the explicitly supplied complete event window, never dividend adjustments.
"""
from datetime import date,datetime,timezone
from zoneinfo import ZoneInfo
import math


def normalize_chart(payload:dict, symbol:str, currency:str|None, asof:str,
                    *, expected_exchange:str|None=None, retrieved_on:str,
                    split_window_complete:bool=False) -> dict:
    day=date.fromisoformat(asof);retrieved=date.fromisoformat(retrieved_on)
    if day>retrieved:raise ValueError('Future valuation date')
    chart=payload.get('chart',{})
    if chart.get('error'):raise ValueError('Provider returned an error')
    result=chart.get('result') or []
    if len(result)!=1:raise ValueError('Expected one identified instrument')
    r=result[0];m=r.get('meta',{})
    if m.get('symbol')!=symbol:raise ValueError('Provider security identity mismatch')
    kind='INDEX' if symbol.startswith('^') else 'EQUITY'
    if m.get('instrumentType')!=kind:raise ValueError('Instrument type mismatch')
    if currency and m.get('currency')!=currency:raise ValueError('Quote currency mismatch')
    if expected_exchange and m.get('exchangeName')!=expected_exchange:raise ValueError('Exchange mismatch')
    tz=ZoneInfo(m['exchangeTimezoneName'])
    stamps=r.get('timestamp') or []
    quote=(r.get('indicators',{}).get('quote') or [{}])[0]
    adjusted=(r.get('indicators',{}).get('adjclose') or [{}])[0].get('adjclose')
    closes=quote.get('close')
    if adjusted is None or closes is None or len(stamps)!=len(adjusted) or len(stamps)!=len(closes):
        raise ValueError('Missing or misaligned close/adjusted-close history')
    rows=[];seen=set();target=None
    def positive(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>0
    for ts,c,a in zip(stamps,closes,adjusted):
        when=datetime.fromtimestamp(ts,tz).date()
        if when>day:continue
        if when.isoformat() in seen:raise ValueError('Duplicate market-local date')
        seen.add(when.isoformat())
        if not positive(c) or not positive(a):continue
        rows.append((when.isoformat(),float(a)))
        if when==day:target=float(c)
    rows.sort()
    events=[];factor=1.
    for split in (r.get('events',{}).get('splits') or {}).values():
        when=datetime.fromtimestamp(split['date'],tz).date()
        n,d=split.get('numerator'),split.get('denominator')
        if not positive(n) or not positive(d):raise ValueError('Invalid split ratio')
        if when>retrieved:raise ValueError('Future split in event window')
        event={'date':when.isoformat(),'factor':n/d}
        events.append(event)
        if when>day:factor*=n/d
    if not math.isfinite(factor) or factor<=0:raise ValueError('Invalid cumulative split factor')
    valuation=None
    # A history request ending at asof cannot prove that later splits were absent.
    if target is not None and split_window_complete:
        valuation={'date':asof,'price':target*factor,'provider_split_adjusted_close':target,
                   'future_split_undo_factor':factor,'later_splits':[s for s in events if s['date']>asof],
                   'basis':'asof_share_units','quality':'historical_reconstruction_not_PIT'}
    return {'symbol':symbol,'currency':m.get('currency'),'exchange':m.get('exchangeName'),
            'timezone':m['exchangeTimezoneName'],'adjusted_close':rows,'valuation':valuation,
            'splits':events,'retrieved_on':retrieved_on}


def main():
    import argparse,json
    from pathlib import Path
    from src.publish import _write_json
    p=argparse.ArgumentParser(description='Normalize an explicit official chart response offline')
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--symbol',required=True)
    p.add_argument('--currency')
    p.add_argument('--exchange',required=True)
    p.add_argument('--as-of',required=True)
    p.add_argument('--retrieved-on',required=True)
    p.add_argument('--complete-split-window',action='store_true',help='Confirm request included split events through retrieved-on; otherwise no valuation price is emitted')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    result=normalize_chart(json.loads(a.input.read_text()),a.symbol,a.currency,a.as_of,
      expected_exchange=a.exchange,retrieved_on=a.retrieved_on,split_window_complete=a.complete_split_window)
    _write_json(result,a.output)

if __name__=='__main__':main()
