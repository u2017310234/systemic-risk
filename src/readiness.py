"""Offline input preflight for every member of the declared universe.

Does not fetch data, change inputs, or reinterpret missing information as zero.
"""
from datetime import date, timedelta
import json
from pathlib import Path
import math
from src.config import cfg
from src.universe import BANKS, UNIVERSE_VERSION, universe_evidence
from src.market_inputs import load_series
from src.fetcher import _component_market_cap, _verified_input


def inspect_inputs(asof: str) -> dict:
    membership = universe_evidence(asof)
    day = date.fromisoformat(asof)
    if not cfg.market_inputs_dir:
        raise ValueError('MARKET_INPUTS_DIR is required for an offline preflight')
    start = (day - timedelta(days=max(550, cfg.covar_window * 2))).isoformat()
    rows = []
    for bank in BANKS:
        row = {'bank_id':bank.id, 'name':bank.name, 'region':bank.region,
               'eligible':bank.supported, 'ready':False, 'issues':[]}
        rows.append(row)
        if not bank.supported:
            row['issues'].append(bank.exclusion_reason)
            continue
        try:
            prices = load_series(bank.yf_ticker, 'adjusted_close', start, asof)
            index = load_series(bank.index_yf, 'adjusted_close', start, asof)
            matched = prices.dropna().index.intersection(index.dropna().index)
            row['matched_closes'] = len(matched)
            if len(prices) < cfg.covar_window + 10:
                row["issues"].append("insufficient_price_history_for_pipeline")
            # One close is lost to returns, and the target return is not in its
            # own prior estimation window. Need window + 2 matched closes.
            if len(matched) < cfg.covar_window + 2:
                row['issues'].append('insufficient_matched_returns')
            if not len(matched) or matched[-1].strftime('%Y-%m-%d') != asof:
                row['issues'].append('no_same_day_matched_close')
            path = Path(cfg.fundamentals_dir) / f'{bank.id}.json'
            if not path.exists():
                row['issues'].append('missing_fundamentals_file')
                continue
            raw = json.loads(path.read_text())
            row['accounting_standard'] = raw.get('accounting_standard')
            if not row['accounting_standard']:
                row['issues'].append('unspecified_accounting_standard')
            debt = _verified_input(bank, 'liabilities', asof, asof)
            cap = _component_market_cap(bank, asof, asof)
            if cap is None:
                cap = _verified_input(bank, 'market_cap', asof, asof)
            for field, series in [('liabilities', debt), ('market_cap', cap)]:
                value = float(series.iloc[-1]) if series is not None and not series.empty else float('nan')
                if not math.isfinite(value) or value <= 0:
                    row['issues'].append(f'{field}_unavailable_at_date')
                else:
                    row[field+'_usd_bn'] = value
            row['ready'] = not row['issues']
        except (ValueError, KeyError, TypeError, OSError) as exc:
            row['issues'].append(f'invalid_input: {exc}')
    eligible = [r for r in rows if r['eligible']]
    return {'asof':asof, 'dataset_kind':cfg.dataset_kind, 'universe_version':UNIVERSE_VERSION, 'list_evidence':membership,
            'expected_count':len(rows), 'eligible_count':len(eligible),
            'ready_count':sum(r['ready'] for r in rows),
            'eligible_complete':all(r['ready'] for r in eligible),
            'full_universe_complete':all(r['ready'] for r in rows),
            'scope_note':'Unlisted groups remain in the denominator; eligible completeness is not full-system coverage.',
            'banks':rows}


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--as-of',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--require-eligible-complete',action='store_true')
    args=parser.parse_args()
    report=inspect_inputs(args.as_of)
    from src.publish import _write_json
    _write_json(report,Path(args.output))
    print(f"Ready {report['ready_count']}/{report['eligible_count']} eligible; {report['expected_count']} total members")
    if args.require_eligible_complete and not report['eligible_complete']:
        raise SystemExit(2)

if __name__=='__main__': main()
