"""
fetcher.py — Price, market cap, and debt data fetching

Data sources (in priority order):
    1. Local disk cache (data/raw/) — avoids redundant API calls
    2. yfinance   — used for all non-CN-A-share tickers
    3. akshare    — fallback for CN A-share prices (601398, etc.)

Outputs:
    - prices(ticker, start, end)  → pd.Series of adjusted close
    - market_cap(bank, date)      → float (USD billions)
    - total_debt(bank, date)      → float (USD billions, forward-filled quarterly)
"""

import os
import time
import logging
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import numpy as np

from src.config import cfg
from src.universe import Bank, BANK_BY_ID, ALL_INDICES

logger = logging.getLogger(__name__)

# Maximum reasonable market cap (USD bn) for a single bank.
# Values above this threshold trigger data quality warnings and fallback logic.
MCAP_UPPER_BOUND_USD_BN = 3000

# ---------------------------------------------------------------------------
# Lazy imports — avoid hard import errors if optional deps missing
# ---------------------------------------------------------------------------
def _yf():
    import yfinance as yf
    return yf


def _ak():
    import akshare as ak
    return ak


# ---------------------------------------------------------------------------
# Disk cache helpers
# ---------------------------------------------------------------------------
def _cache_path(ticker: str, start: str, end: str) -> Path:
    safe = ticker.replace("^", "IDX_").replace(".", "_").replace("/", "_")
    return Path(cfg.raw_dir) / f"v2_{safe}_{start}_{end}.parquet"


def _load_cache(path: Path) -> pd.DataFrame | None:
    if path.exists():
        try:
            return pd.read_parquet(path)
        except Exception as e:
            logger.warning(f"Cache read failed for {path}: {e}")
    return None


def _save_cache(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)


# ---------------------------------------------------------------------------
# Core price fetching
# ---------------------------------------------------------------------------
def fetch_prices(
    ticker: str,
    start: str,
    end: str,
    ak_ticker: str | None = None,
    use_cache: bool = True,
) -> pd.Series:
    """
    Return daily adjusted close prices as a pd.Series indexed by date.

    Args:
        ticker     : Yahoo Finance ticker (primary)
        start      : YYYY-MM-DD start date (inclusive)
        end        : YYYY-MM-DD end date (inclusive)
        ak_ticker  : AkShare A-share code (fallback for CN banks)
        use_cache  : Whether to read/write disk cache

    Returns:
        pd.Series with DatetimeIndex, float values in local currency.
    """
    from src.market_inputs import load_series
    external = load_series(ticker, "adjusted_close", start, end)
    if external is not None:
        return external.rename(ticker)
    cache_path = _cache_path(ticker, start, end)
    if use_cache:
        cached = _load_cache(cache_path)
        if cached is not None and "close" in cached.columns:
            logger.debug(f"Cache hit: {ticker}")
            return cached["close"]

    # ── Try Yahoo Finance ─────────────────────────────────────────────────
    series = _fetch_yf(ticker, start, end)

    # A-share returns cannot silently stand in for an H-share listing/index.
    # Missing primary data remains missing; an explicit security registry change is required.
    if series is None or series.empty:
        logger.warning(f"No price data found for {ticker} ({start} to {end})")
        return pd.Series(dtype=float, name=ticker)

    series.name = ticker
    series = _dates(series)

    if use_cache:
        _save_cache(pd.DataFrame({"close": series}), cache_path)

    time.sleep(cfg.yf_request_delay)
    return series


def _fetch_yf(ticker: str, start: str, end: str) -> pd.Series | None:
    try:
        yf = _yf()
        # Download with auto_adjust=True gives adjusted close in 'Close' column
        df = yf.download(ticker, start=start, end=(pd.Timestamp(end) + timedelta(days=1)).strftime("%Y-%m-%d"), auto_adjust=True,
                         progress=False, threads=False)
        if df.empty:
            return None
        col = "Close"
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        return df[col].dropna()
    except Exception as e:
        logger.error(f"yfinance error for {ticker}: {e}", exc_info=True)
        return None


def _fetch_ak(ak_ticker: str, start: str, end: str) -> pd.Series | None:
    """Fetch A-share daily close via AkShare stock_zh_a_hist."""
    try:
        ak = _ak()
        df = ak.stock_zh_a_hist(
            symbol=ak_ticker,
            period="daily",
            start_date=start.replace("-", ""),
            end_date=end.replace("-", ""),
            adjust="hfq",  # backward-adjusted
        )
        if df.empty:
            return None
        df.index = pd.to_datetime(df["日期"])
        return df["收盘"].astype(float)
    except Exception as e:
        logger.error(f"AkShare error for {ak_ticker}: {e}", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Market Cap
# ---------------------------------------------------------------------------
class DataQualityError(ValueError):
    """An input cannot safely be interpreted in the declared units/security scope."""


def _dates(series: pd.Series) -> pd.Series:
    series = series.copy()
    series.index = pd.to_datetime(series.index).tz_localize(None).normalize()
    return series[~series.index.duplicated(keep="last")].sort_index()


def convert_currency(series: pd.Series, currency: str) -> pd.Series:
    """Convert native amounts to USD; all FX tickers quote USD per currency unit.

    Missing/stale FX produces NaN, never native numbers mislabeled USD.
    """
    series = _dates(series)
    if series.empty or currency == "USD":
        return series
    factor = 0.01 if currency in ("GBp", "GBX") else 1.0
    currency = "GBP" if currency in ("GBp", "GBX") else currency
    pairs = {"GBP": "GBPUSD=X", "HKD": "HKDUSD=X", "CHF": "CHFUSD=X",
             "EUR": "EURUSD=X", "JPY": "JPYUSD=X", "CNY": "CNYUSD=X", "CAD": "CADUSD=X"}
    if currency not in pairs:
        raise DataQualityError(f"Unsupported currency: {currency}")
    from src.market_inputs import load_series
    external = load_series(currency, "fx_usd_per_unit", series.index.min().strftime("%Y-%m-%d"), series.index.max().strftime("%Y-%m-%d"))
    if external is not None:
        # Explicit feed: no fallback or forward fill without evidence for each date.
        return (series * factor * external.reindex(series.index)).rename(series.name)
    try:
        fx = _yf().download(pairs[currency],
            start=(series.index.min() - timedelta(days=7)).strftime("%Y-%m-%d"),
            end=(series.index.max() + timedelta(days=1)).strftime("%Y-%m-%d"),
            auto_adjust=True, progress=False, threads=False)
        if isinstance(fx.columns, pd.MultiIndex):
            fx.columns = fx.columns.droplevel(1)
        rates = _dates(fx["Close"].dropna())
        rates = rates.where(np.isfinite(rates) & (rates > 0)).dropna()
        rates = rates.reindex(series.index, method="ffill", tolerance=pd.Timedelta(days=7))
        return (series * factor * rates).rename(series.name)
    except Exception as exc:
        logger.warning("FX unavailable for %s: %s", currency, exc)
        return pd.Series(np.nan, index=series.index, name=series.name)


def _to_usd(series: pd.Series, ticker: str) -> pd.Series:
    banks = [b for b in BANK_BY_ID.values() if b.yf_ticker == ticker]
    if not banks:
        raise DataQualityError(f"No explicit quote currency for {ticker}")
    return convert_currency(series, banks[0].quote_currency)


def _to_usd_bs(series: pd.Series, ticker: str) -> pd.Series:
    banks = [b for b in BANK_BY_ID.values() if b.yf_ticker == ticker]
    if not banks:
        raise DataQualityError(f"No explicit reporting currency for {ticker}")
    return convert_currency(series, banks[0].reporting_currency)


def _verified_input(bank: Bank, field: str, start: str, end: str) -> pd.Series | None:
    """Optional dated issuer-scope amounts, with real public availability dates.

    Schema documented in docs/REPAIR.md. Inputs are absolute amounts, not billions.
    No file means unavailable, never a fabricated substitute.
    """
    import json
    path = Path(cfg.fundamentals_dir) / f"{bank.id}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    if data.get("bank_id") != bank.id or data.get("scope") != "consolidated_group":
        raise DataQualityError(f"{bank.id}: input identity/scope mismatch")
    rows = data.get(field, [])
    if not rows:
        return None
    from src.fundamentals import select_asof, validate_row, EvidenceError
    standard = data.get("accounting_standard")
    for row in rows:
        validate_row(row)
        expected_currency = data.get("currencies", {}).get(field, data.get("currency", ""))
        if row.get("currency", expected_currency) != expected_currency:
            raise EvidenceError("Mixed currencies in one input stream")
        if row.get("accounting_standard", standard) != standard:
            raise EvidenceError("Mixed accounting standards in one input stream")
    idx = pd.date_range(start, end, freq="B")
    selected = [select_asof(rows, dt.date()) for dt in idx]
    if field == "market_cap":
        selected = [r if r and r["effective_date"] == dt.strftime("%Y-%m-%d") else None
                    for r, dt in zip(selected, idx)]
    src = pd.Series([r["value"] if r else np.nan for r in selected], index=idx, dtype=float)
    result = convert_currency(src / 1e9, data.get("currencies", {}).get(field, data.get("currency", "")))
    import hashlib
    result.attrs["quality"] = "supplied_publication_dates"
    result.attrs["accounting_standard"] = standard or "unspecified"
    result.attrs["selected_sources"] = {dt.strftime("%Y-%m-%d"): {k:r.get(k) for k in ("effective_date","available_date","source","accession","accounting_standard")} for dt,r in zip(idx,selected) if r}
    result.attrs["input_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _component_market_cap(bank: Bank, start: str, end: str) -> pd.Series | None:
    import json
    from src.fundamentals import calculate_group_market_cap, EvidenceError
    path = Path(cfg.fundamentals_dir) / f"{bank.id}.json"
    if not path.exists(): return None
    data = json.loads(path.read_text())
    observations = data.get("equity_valuations")
    if observations is None: return None
    if data.get("bank_id") != bank.id or data.get("scope") != "consolidated_group":
        raise EvidenceError("Equity input identity mismatch")
    if set(data["expected_share_classes"]) != set(bank.equity_share_classes):
        raise EvidenceError("Share classes do not match the issuer registry")
    values={}; evidence={}
    for row in observations:
        when=row["valuation_date"]
        rates={}
        used_currencies = {"GBP" if c["currency"] in ("GBp", "GBX") else c["currency"] for c in row["components"]}
        for item in row.get("fx", []):
            if item["currency"] not in used_currencies:
                continue
            if item.get("source_release_date", when) > when and cfg.dataset_kind != "historical_reconstruction":
                raise EvidenceError("FX source was published later; require explicit historical_reconstruction mode")
            if item.get("date") != when or not item.get("source") or item.get("direction") != "USD_PER_UNIT":
                raise EvidenceError("FX must be same-date, sourced, USD per currency unit")
            if item["currency"] in rates:raise EvidenceError("Duplicate FX currency")
            rates[item["currency"]]=item["rate"]
        result=calculate_group_market_cap(row["components"],data["expected_share_classes"],when,rates)
        if when in values:raise EvidenceError("Duplicate valuation date")
        value=result["market_cap_usd_bn"]
        if not np.isfinite(value) or value <= 0 or value > MCAP_UPPER_BOUND_USD_BN:
            raise EvidenceError("Implausible or nonfinite consolidated market cap")
        values[when]=value
        evidence[when]={"components":result["components"], "sources":[{"share_source":c["share_source"],"price_source":c["price_source"],"shares_effective_date":c["shares_effective_date"],"shares_available_date":c["shares_available_date"],"share_count_basis":c.get("share_count_basis"),"precision":c.get("precision"),"caveat":c.get("caveat"),"price_adjustment":c.get("price_adjustment")} for c in row["components"]]}
    series=pd.Series(values,dtype=float);series.index=pd.to_datetime(series.index)
    series=series.reindex(pd.date_range(start,end,freq="B"))
    series.attrs["quality"]="sourced_class_prices_times_published_shares_estimate"
    series.attrs["selected_sources"]=evidence
    return series


def fetch_market_cap_series(bank: Bank, start: str, end: str) -> pd.Series:
    components = _component_market_cap(bank, start, end)
    if components is not None:
        return components.rename(f"{bank.id}_mcap_usd_bn")
    verified = _verified_input(bank, "market_cap", start, end)
    if verified is not None:
        return verified.rename(f"{bank.id}_mcap_usd_bn")
    if cfg.market_inputs_dir:
        # An explicitly selected local feed must remain offline and reproducible.
        # Never fill its missing issuer valuations from an unrelated live vendor.
        return pd.Series(dtype=float)
    if not bank.supported or bank.market_cap_policy == "verified_input":
        logger.warning("%s needs verified consolidated-group market cap", bank.id)
        return pd.Series(dtype=float)
    ticker = _yf().Ticker(bank.yf_ticker)
    # Separate price used for equity valuation from dividend-adjusted return prices.
    frame = ticker.history(start=start, end=(pd.Timestamp(end)+timedelta(days=1)).strftime("%Y-%m-%d"),
                           auto_adjust=False, actions=True)
    if frame is None or frame.empty:
        return pd.Series(dtype=float)
    # Yahoo Close may be split-adjusted. Refuse ranges crossing a split unless
    # verified market caps are supplied, rather than mix incompatible share bases.
    if "Stock Splits" in frame and (frame["Stock Splits"].fillna(0) != 0).any():
        logger.warning("%s split in range: verified market caps required", bank.id)
        return pd.Series(dtype=float)
    price = _dates(frame["Close"])
    shares = ticker.get_shares_full(start=(pd.Timestamp(start)-timedelta(days=180)).strftime("%Y-%m-%d"),
                                   end=(pd.Timestamp(end)+timedelta(days=1)).strftime("%Y-%m-%d"))
    if shares is None or shares.empty:
        return pd.Series(dtype=float)
    shares = _dates(shares)
    shares = shares.reindex(price.index, method="ffill", tolerance=pd.Timedelta(days=180))
    result = convert_currency(price * shares / 1e9, bank.quote_currency)
    invalid = ~np.isfinite(result) | (result <= 0) | (result > MCAP_UPPER_BOUND_USD_BN)
    if invalid.any():
        logger.warning("[DATA QUALITY] %s market cap invalid; excluded, no constant fallback", bank.id)
    result = result.mask(invalid).rename(f"{bank.id}_mcap_usd_bn")
    result.attrs["quality"] = "dated_vendor_shares_not_point_in_time_verified"
    return result


def fetch_debt_series(bank: Bank, start: str, end: str) -> pd.Series:
    """Only publication-dated consolidated liabilities may enter SRISK.

    Yahoo balance-sheet columns contain period end, not publication date.
    They are deliberately not forward-filled as if known at period end.
    Supply sourced input rather than silently introducing look-ahead bias.
    """
    verified = _verified_input(bank, "liabilities", start, end)
    if verified is None:
        logger.warning("%s: publication-dated liabilities unavailable", bank.id)
        return pd.Series(dtype=float)
    return verified.rename(f"{bank.id}_debt_usd_bn")


# ---------------------------------------------------------------------------
# Batch fetch: all banks + all indices
# ---------------------------------------------------------------------------
def fetch_all_prices(
    start: str,
    end: str,
    bank_ids: list[str] | None = None,
) -> dict[str, pd.Series]:
    """
    Fetch price series for all (or subset of) banks AND their regional indices.
    Returns dict: ticker → pd.Series of returns.
    """
    from src.universe import BANKS

    banks = BANKS if bank_ids is None else [BANK_BY_ID[i] for i in bank_ids]
    results: dict[str, pd.Series] = {}

    # Fetch bank prices
    for bank in banks:
        if not bank.supported:
            continue
        logger.info(f"Fetching prices: {bank.id} ({bank.yf_ticker})")
        p = fetch_prices(bank.yf_ticker, start, end, bank.ak_ticker)
        if not p.empty:
            results[bank.yf_ticker] = p

    # Fetch index prices (deduplicated)
    needed_indices = sorted(set(b.index_yf for b in banks))
    for idx_ticker in needed_indices:
        if idx_ticker not in results:
            logger.info(f"Fetching index: {idx_ticker}")
            p = fetch_prices(idx_ticker, start, end)
            if not p.empty:
                results[idx_ticker] = p

    return results
