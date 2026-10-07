"""Model-internal sensitivity and attribution; never a causal or crisis forecast."""
import itertools
import math
import numpy as np
import pandas as pd
from src.metrics.srisk import calc_srisk


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def scenario_grid(bank_record, parameters, market_drops=None, capital_ratios=None):
    drops = [0.2, 0.3, 0.4, 0.5, 0.6] if market_drops is None else market_drops
    ratios = [0.04, 0.06, 0.08, 0.10] if capital_ratios is None else capital_ratios
    if not drops or not ratios or len(drops)*len(ratios)>100:
        raise ValueError('Provide 1–100 scenarios')
    if any(not finite(v) or not 0<v<1 for v in [*drops,*ratios]):
        raise ValueError('Drops and capital ratios must be in (0,1)')
    w, debt = bank_record.get('market_cap_usd_bn'), bank_record.get('debt_usd_bn')
    beta = bank_record.get('beta_ols')
    source = 'estimated_ols_beta'
    if not finite(beta):
        loss, drop = bank_record.get('lrmes'), parameters.get('lrmes_market_drop')
        if not finite(loss) or not 0<loss<1 or not finite(drop) or not 0<drop<1:
            return {'status':'unavailable','reason':'OLS beta unavailable; clipped/boundary loss cannot identify beta'}
        beta = math.log1p(-loss)/math.log1p(-drop)
        source = 'inferred_from_rounded_interior_lrmes_and_original_scenario'
    if not all(finite(v) and v>0 for v in [w,debt]):
        return {'status':'unavailable','reason':'Positive equity and liabilities are required'}
    rows = []
    for drop,k in itertools.product(drops,ratios):
        loss = float(np.clip(-np.expm1(np.log1p(-drop)*beta),0,1))
        rows.append({'market_drop':drop,'capital_ratio':k,'lrmes':loss,
                     'srisk_usd_bn':calc_srisk(w,debt,loss,k)})
    return {'status':'ok','method':'ols_beta_scenario','beta':beta,'beta_source':source,
            'bank_id':bank_record.get('bank_id'),'rows':rows,
            'range_usd_bn':[min(r['srisk_usd_bn'] for r in rows),max(r['srisk_usd_bn'] for r in rows)],
            'limitations':['Scenario range is not a confidence interval.',
                           'Equity and liabilities held fixed; horizon label does not alter this model.']}


def explain_change(previous, current, bank_id):
    """Exact six-order Shapley attribution including the max(0,...) boundary."""
    if not previous.get('calibration_id') or (previous.get('calibration_id'),previous.get('methodology_version')) != (current.get('calibration_id'),current.get('methodology_version')):
        return {'status':'unavailable','reason':'Missing or changed model/calibration; compare separately'}
    if previous.get('parameters') != current.get('parameters'):
        return {'status':'unavailable','reason':'Parameters changed'}
    if previous['date'] >= current['date']:
        return {'status':'unavailable','reason':'Previous date must precede current date'}
    records = [next((b for b in p.get('banks',[]) if b['bank_id']==bank_id),{}) for p in (previous,current)]
    fields = ['debt_usd_bn','market_cap_usd_bn','lrmes']
    before,after = [{f:b.get(f) for f in fields} for b in records]
    if not all(finite(v) for d in (before,after) for v in d.values()):
        return {'status':'unavailable','reason':'Same bank needs complete inputs at both dates'}
    k = current.get('parameters',{}).get('srisk_k')
    if not finite(k) or not 0<k<1: return {'status':'unavailable','reason':'Missing valid capital ratio'}
    def value(d): return calc_srisk(d['market_cap_usd_bn'],d['debt_usd_bn'],d['lrmes'],k)
    if not all(finite(value(d)) for d in (before,after)):
        return {'status':'unavailable','reason':'Invalid input domain'}
    contributions = dict.fromkeys(fields,0.)
    for order in itertools.permutations(fields):
        state = dict(before)
        for f in order:
            old = value(state); state[f] = after[f]
            contributions[f] += (value(state)-old)/6
    change = value(after)-value(before)
    return {'status':'ok','method':'exact_shapley_three_inputs','bank_id':bank_id,
            'previous_date':previous['date'],'current_date':current['date'],
            'previous_srisk_usd_bn':value(before),'current_srisk_usd_bn':value(after),
            'change_usd_bn':change,'contributions_usd_bn':contributions,
            'reconciliation_residual':change-sum(contributions.values()),
            'evidence_changed':{f:records[0].get(f)!=records[1].get(f) for f in
                ['market_cap_evidence','liabilities_evidence','fundamentals_input_sha256']},
            'limitations':['Model arithmetic attribution, not economic causality.',
                'Currency and corporate-action effects remain in equity/liability changes; no separate FX claim.',
                'Changing sample coverage is excluded: the same bank is compared.']}


def bootstrap_uncertainty(bank_returns,index_returns,*,n_bootstrap=200,block_length=5,
                          confidence=.95,seed=0,tail_pct=.05,market_drop=.4):
    from src.metrics.mes import calc_mes,calc_lrmes
    if not 50<=n_bootstrap<=2000 or not 1<=block_length<=60 or not 0<confidence<1:
        raise ValueError('Invalid bootstrap controls')
    if not 0<tail_pct<1 or not 0<market_drop<1: raise ValueError('Invalid scenario')
    data = pd.concat([pd.Series(bank_returns).rename('bank'),pd.Series(index_returns).rename('index')],axis=1)
    data = data.replace([np.inf,-np.inf],np.nan).dropna().sort_index()
    if data.index.has_duplicates: raise ValueError('Duplicate observation dates')
    n = len(data)
    if n<60 or block_length>n//3:
        return {'status':'unavailable','reason':'At least 60 paired observations and adequate blocks required'}
    rng = np.random.default_rng(seed); estimates = []
    for _ in range(n_bootstrap):
        starts = rng.integers(0,n,size=math.ceil(n/block_length))
        indices = np.concatenate([(start+np.arange(block_length))%n for start in starts])[:n]
        sample = data.iloc[indices].reset_index(drop=True)
        estimates.append([calc_mes(sample.bank,sample['index'],tail_pct),calc_lrmes(sample.bank,sample['index'],market_drop=market_drop,window=n)])
    values = np.array(estimates); valid = values[np.isfinite(values).all(axis=1)]
    if len(valid)<.9*n_bootstrap: return {'status':'unavailable','reason':'Too many degenerate bootstrap samples'}
    q = (1-confidence)/2
    intervals = np.quantile(valid,[q,1-q],axis=0)
    tail_count = int((data['index']<=data['index'].quantile(tail_pct)).sum())
    return {'status':'ok','method':'paired_circular_moving_block_bootstrap','observations':n,
            'tail_observations':tail_count,'block_length':block_length,'replications':len(valid),
            'seed':seed,'confidence':confidence,
            'intervals':{name:[float(intervals[0,i]),float(intervals[1,i])] for i,name in enumerate(['mes','lrmes'])},
            'warnings':(['FEW_TAIL_OBSERVATIONS'] if tail_count<20 else []),
            'limitations':['Conditional on supplied return history, scenario and block length.',
                           'Not a forecast interval; no accounting/FX uncertainty included.']}
