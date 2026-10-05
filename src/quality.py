"""Explain data readiness separately from server liveness. Thresholds are heuristics."""
from datetime import date
import math

def assess_quality(payload:dict, previous:dict|None=None, today:date|None=None)->dict:
    today=today or date.today();alerts=[]
    def add(code,message,bank=None,severity='warning'):
        alerts.append({'code':code,'severity':severity,'bank_id':bank,'message':message})
    coverage=payload.get('coverage',{});expected=coverage.get('expected_count',0);valid=coverage.get('srisk_count',0)
    if not valid:add('NO_SRISK','No bank has valid SRISK inputs',severity='error')
    elif not expected or valid/expected<.8:add('LOW_COVERAGE',f'SRISK coverage {valid}/{expected}; threshold 80%')
    if not coverage.get('complete'):add('INCOMPLETE_UNIVERSE','Covered subtotal is not the full-system total')
    try:
        age=(today-date.fromisoformat(payload['date'])).days
        if age<0:add('FUTURE_DATA_DATE','Snapshot date is in the future',severity='error')
        elif age>7:add('STALE_SNAPSHOT',f'Snapshot is {age} calendar days old',severity='error')
    except (ValueError,KeyError,TypeError):add('INVALID_DATA_DATE','Snapshot date invalid',severity='error')
    bases=sorted({b.get('accounting_standard') for b in payload.get('banks',[]) if b.get('accounting_standard') not in (None,'unspecified')})
    if len(bases)>1:add('MIXED_ACCOUNTING_BASES','Cross-country balance sheets are not harmonized (including derivative netting): '+', '.join(bases))
    old={b['bank_id']:b for b in (previous or {}).get('banks',[])}
    for bank in payload.get('banks',[]):
        bid=bank['bank_id']
        if bank.get('accounting_standard') in (None,'unspecified'):
            add('UNSPECIFIED_ACCOUNTING','Accounting basis not supplied',bid)
        for text in bank.get('data_quality_warnings',[]):add('INPUT_WARNING',text,bid)
        evidence=bank.get('liabilities_evidence')
        if evidence and evidence.get('effective_date'):
            age=(date.fromisoformat(payload['date'])-date.fromisoformat(evidence['effective_date'])).days
            if age>100:add('OLD_FUNDAMENTALS',f'Liabilities period is {age} days old',bid)
        cap_evidence=bank.get("market_cap_evidence") or {}
        ages=[c.get("shares_age_days",0) for c in cap_evidence.get("components",[])]
        for source in cap_evidence.get('sources',[]):
            if source.get('caveat'):add('SHARE_BASIS_VARIANT',source['caveat'],bid)
            if source.get('precision'):add('SHARE_COUNT_PRECISION',source['precision'],bid)
            adjustment=source.get('price_adjustment') or {}
            if adjustment.get('future_split_undo_factor',1)!=1:
                add('LATER_SPLIT_RESTORED',f"Historical close restored by factor {adjustment['future_split_undo_factor']} to valuation-date share units; retrospective data",bid)
        if ages and max(ages)>100:
            add("OLD_SHARE_COUNT",f"Published share count is {max(ages)} days old; repurchases/issuance may change market cap",bid)
        prior=old.get(bid,{})
        for field,limit in [('market_cap_usd_bn',2.),('debt_usd_bn',1.3)]:
            a,b=prior.get(field),bank.get(field)
            if all(isinstance(v,(int,float)) and math.isfinite(v) and v>0 for v in (a,b)):
                if b/a>limit or b/a<1/limit:add('LARGE_INPUT_CHANGE',f'{field} ratio {b/a:.3f}; verify corporate actions, units and period',bid)
        if prior.get('accounting_standard') and bank.get('accounting_standard')!=prior['accounting_standard']:
            add('ACCOUNTING_BASIS_CHANGED','Do not splice different accounting bases',bid,severity='error')
    if previous:
        before=set(previous.get('coverage',{}).get('srisk_ids',[]));after=set(coverage.get('srisk_ids',[]))
        lost=sorted(before-after)
        if lost:add('COVERAGE_LOSS','Previously covered banks now missing: '+', '.join(lost))
    return {'status':'error' if any(a['severity']=='error' for a in alerts) else 'warning' if alerts else 'ok',
            'srisk_coverage_ratio':valid/expected if expected else 0.,'alerts':alerts,
            'thresholds':{'min_srisk_coverage':.8,'snapshot_max_calendar_days':7,'fundamentals_warning_days':100}}
