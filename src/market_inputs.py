"""Optional, hash-checked local market feed. No implicit provider substitution."""
import hashlib,json
from pathlib import Path
import pandas as pd
import numpy as np
from src.config import cfg

def load_series(identifier:str,kind:str,start:str,end:str)->pd.Series|None:
    if not cfg.market_inputs_dir:return None
    root=Path(cfg.market_inputs_dir).resolve()
    manifest=json.loads((root/'manifest.json').read_text())
    entry=manifest.get('series',{}).get(f'{kind}:{identifier}')
    if entry is None:
        return pd.Series(dtype=float)
    if entry.get('status')=='quarantined':
        raise ValueError('Quarantined market instrument: '+entry.get('reason','identity not verified'))
    if entry.get('identifier')!=identifier or entry.get('kind')!=kind or not entry.get('source'):
        raise ValueError('Market feed identity/kind/source mismatch')
    provider_currency=entry.get('provider_currency_label')
    declared_currency=entry.get('currency')
    override=entry.get('currency_override')
    if provider_currency and declared_currency and provider_currency!=declared_currency:
        if not override or not override.get('source') or not override.get('reason'):
            raise ValueError('Conflicting currency metadata requires a sourced explicit override')
    path=(root/entry['path']).resolve();path.relative_to(root)
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=entry['sha256']:raise ValueError('Market feed hash mismatch')
    frame=pd.read_csv(path,dtype={'date':str})
    if not {'date','value'}<=set(frame):raise ValueError('CSV requires date,value')
    dates=pd.to_datetime(frame['date'],format='%Y-%m-%d',errors='raise')
    if dates.duplicated().any():raise ValueError('Duplicate market dates')
    values=pd.to_numeric(frame['value'],errors='raise').to_numpy()
    if not np.isfinite(values).all() or (values<=0).any():raise ValueError('Invalid market values')
    series=pd.Series(values,index=dates).sort_index().loc[start:end]
    if entry.get('available_date') and cfg.dataset_kind != 'historical_reconstruction':
        series = series.where(series.index >= pd.Timestamp(entry['available_date']))
    series.attrs['source']=entry['source'];series.attrs['quality']=entry.get('quality','external_feed_not_vintage_verified')
    if override:series.attrs['currency_override']=override
    return series
