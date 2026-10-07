"""Primary-equity session calendar. Missing quotes alone never prove a holiday.

Exchange calendars are versioned software estimates, not a live exchange feed.
Index outages/halts are not inferred from the equity calendar.
"""
from datetime import datetime, timezone, timedelta
from functools import lru_cache
import importlib.metadata
import math
import pandas as pd
from src.universe import BANKS
from src.config import cfg


def calendar_name(bank):
    suffixes = {'.HK':'XHKG', '.L':'XLON', '.PA':'XPAR', '.DE':'XETR',
                '.SW':'XSWX', '.AS':'XAMS', '.MC':'XMAD', '.TO':'XTSE', '.T':'XTKS'}
    return next((name for suffix,name in suffixes.items() if bank.yf_ticker.endswith(suffix)),
                'XNYS' if bank.region == 'US' else None)


@lru_cache(maxsize=100)
def _calendar(name, year):
    import exchange_calendars as xc
    return xc.get_calendar(name, start=f'{year-2}-01-01', end=f'{year+1}-12-31')


def session_status(bank, requested_date, observed_date=None, *, now=None):
    now = pd.Timestamp(now or datetime.now(timezone.utc))
    if now.tzinfo is None: now = now.tz_localize('UTC')
    result = {'requested_date':requested_date, 'observation_date':observed_date,
              'calendar':calendar_name(bank), 'calendar_scope':'primary_equity',
              'expected_session_date':None, 'status':'unknown_calendar'}
    if not bank.supported:
        return {**result, 'status':'unsupported', 'reason':bank.exclusion_reason}
    try:
        day = pd.Timestamp(requested_date)
        cal = _calendar(result['calendar'], day.year)
        result['calendar_version'] = importlib.metadata.version('exchange-calendars')
        sessions = cal.sessions_in_range(day-pd.Timedelta(days=40), day)
        due = [s for s in sessions if cal.session_close(s)+pd.Timedelta(minutes=cfg.market_close_grace_minutes) <= now]
        expected = due[-1].strftime('%Y-%m-%d') if due else None
        is_session = bool(cal.is_session(day))
        result.update(expected_session_date=expected, is_session=is_session)
        if observed_date == requested_date:
            status = 'observed'
        elif not is_session:
            status = 'market_closed'
        elif day.strftime('%Y-%m-%d') != expected:
            status = 'not_yet_due'
        else:
            status = 'missing_data'
        result['status'] = status
        result['up_to_date'] = bool(observed_date and expected and observed_date >= expected)
        return result
    except Exception as exc:
        return {**result, 'reason':f'Calendar unavailable: {type(exc).__name__}'}


def publication_report(payload, observations, target_date, *, now=None):
    """Freshness uses the wall clock; closed markets still need their last due result."""
    if cfg.publication_mode not in {'research', 'historical', 'production'}:
        raise ValueError('Unknown PUBLICATION_MODE')
    now = now or datetime.now(timezone.utc)
    current_day = now.date().isoformat()
    states = {}
    for bank in BANKS:
        observation = observations.get(bank.id, {})
        state = session_status(bank, current_day, observation.get('srisk_date'), now=now)
        if observation.get('failure'):
            state['input_failure'] = observation['failure']
            if state['status'] == 'missing_data': state['status'] = 'fetch_or_calculation_failed'
        states[bank.id] = state
    eligible = [b.id for b in BANKS if b.supported]
    ready = [bid for bid in eligible if states[bid].get('up_to_date')]
    reasons = []
    if not 0 < cfg.min_publication_coverage <= 1:
        raise ValueError('MIN_PUBLICATION_COVERAGE must be in (0,1]')
    if not payload.get('coverage', {}).get('srisk_count'): reasons.append('NO_SRISK')
    if len(ready)/len(eligible) < cfg.min_publication_coverage: reasons.append('INSUFFICIENT_FRESH_ELIGIBLE_COVERAGE')
    if payload.get('dataset_kind') in ('historical_reconstruction','synthetic_test'): reasons.append('NON_PRODUCTION_DATASET')
    if target_date > current_day: reasons.append('FUTURE_TARGET')
    if any(a.get('severity') == 'error' for a in payload.get('quality',{}).get('alerts',[])):
        reasons.append('QUALITY_ERROR')
    return {'mode':cfg.publication_mode, 'target_date':target_date,
            'evaluated_at':now.isoformat(), 'fresh_eligible_count':len(ready),
            'eligible_count':len(eligible), 'minimum_ratio':cfg.min_publication_coverage,
            'bank_status':states, 'reasons':reasons,
            'decision':'rejected' if reasons and cfg.publication_mode=='production' else 'accepted'}
