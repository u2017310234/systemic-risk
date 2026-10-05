"""Dated evidence selection and consolidated common-equity valuation."""
from __future__ import annotations
from datetime import date
import math

class EvidenceError(ValueError):
    pass

def validate_row(row: dict):
    effective, available = date.fromisoformat(row['effective_date']), date.fromisoformat(row['available_date'])
    value = row['value']
    if available < effective or isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value <= 0:
        raise EvidenceError('Invalid date/value in evidence')
    if not isinstance(row.get('source'),str) or not row['source'].strip():
        raise EvidenceError('Source required')
    return effective, available

def select_asof(rows: list[dict], asof: date, max_age_days: int = 200) -> dict | None:
    """Newest effective period, then latest available revision of THAT period.

    A later filing repeating an older comparative period must never overwrite a
    newer period. A revision cannot enter the series before its publication.
    Freshness is measured from period end, not reset by repeated publication.
    """
    candidates=[]
    for row in rows:
        effective, available=validate_row(row)
        if available <= asof and effective <= asof and (asof-effective).days <= max_age_days:
            candidates.append((effective,available,row))
    if not candidates:return None
    key=max((e,a) for e,a,_ in candidates)
    winners=[r for e,a,r in candidates if (e,a)==key]
    signatures={(r['value'],r.get('accounting_standard'),r.get('currency')) for r in winners}
    if len(signatures)>1:raise EvidenceError('Conflicting facts for the same period and publication date')
    return winners[0]

def calculate_group_market_cap(components: list[dict], expected_classes: list[str], valuation_date: str,
                               fx_usd_per_unit: dict[str,float]) -> dict:
    """All ordinary equity classes, no ADR double counting, no partial totals.

    Components carry exact valuation-date unadjusted prices and dated published
    issued/treasury shares. Stale shares are disclosed; this is not exact daily
    outstanding-shares verification.
    """
    asof=date.fromisoformat(valuation_date)
    ids=[c['share_class_id'] for c in components]
    if len(set(ids))!=len(ids) or set(ids)!=set(expected_classes):
        raise EvidenceError('Missing or duplicate ordinary share class')
    rows=[]
    for c in components:
        if c.get('instrument_type')!='ordinary' or c.get('price_basis')!='unadjusted':
            raise EvidenceError('Only ordinary unadjusted equity; ADRs need explicit separate handling')
        if c.get('price_date')!=valuation_date or not c.get('price_source') or not c.get('share_source'):
            raise EvidenceError('Same-date sourced prices and share evidence are required')
        if date.fromisoformat(c['shares_available_date'])>asof:
            raise EvidenceError('Share count was not yet public')
        effective=date.fromisoformat(c['shares_effective_date'])
        age=(asof-effective).days
        if age<0 or age>200:raise EvidenceError('Stale or future share count')
        if 'outstanding_shares' in c:
            if 'issued_shares' in c or 'treasury_shares' in c:raise EvidenceError('Do not subtract treasury twice from outstanding shares')
            issued,treasury=c['outstanding_shares'],0
        else:
            issued,treasury=c['issued_shares'],c.get('treasury_shares',0)
        price=c['price']
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (issued,treasury,price)):
            raise EvidenceError('Invalid numeric component')
        if issued<=treasury or treasury<0 or price<=0:raise EvidenceError('Invalid shares or price')
        if c.get('split_basis') != c.get('price_split_basis') or not c.get('split_basis'):
            raise EvidenceError('Share and price split bases do not match')
        currency=c['currency']; factor=.01 if currency in ('GBp','GBX') else 1.
        key='GBP' if currency in ('GBp','GBX') else currency
        rate=1. if key=='USD' else fx_usd_per_unit.get(key)
        if rate is None or not math.isfinite(rate) or rate<=0:raise EvidenceError('Missing or invalid same-date FX')
        usd=(issued-treasury)*price*factor*rate
        rows.append({'share_class_id':c['share_class_id'],'outstanding_shares':issued-treasury,
                     'shares_age_days':age,'usd':usd})
    return {'valuation_date':valuation_date,'market_cap_usd_bn':sum(r['usd'] for r in rows)/1e9,
            'components':rows,'quality':'published_share_count_estimate' if any(r['shares_age_days'] for r in rows) else 'same_date_components'}
