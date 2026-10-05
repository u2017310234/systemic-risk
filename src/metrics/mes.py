"""MES and an explicitly approximate OLS-beta cumulative-loss scenario.

LRMES proxy = clip(1 - (1-D)**beta_OLS, 0, 1). This is not the
Brownlees–Engle dynamic simulation. Horizon labels the cumulative scenario;
it does not alter the closed form. No upward max-beta selection is used.
"""

import numpy as np
import pandas as pd

from src.config import cfg


# ---------------------------------------------------------------------------
# Simple quantile-based MES
# ---------------------------------------------------------------------------
def calc_mes(
    bank_returns: pd.Series,
    index_returns: pd.Series,
    tail_pct: float | None = None,
) -> float:
    """
    Compute MES: mean bank return on index tail days.

    Args:
        bank_returns  : Daily simple or log returns of the bank.
        index_returns : Daily returns of the regional market index.
        tail_pct      : Left-tail threshold (default from cfg).

    Returns:
        MES as a float (negative = loss during system stress).
    """
    tail_pct = tail_pct if tail_pct is not None else cfg.mes_tail_pct

    aligned = _align(bank_returns, index_returns)
    if aligned.empty or len(aligned) < 30:
        return float("nan")

    threshold = aligned["index"].quantile(tail_pct)
    tail_days = aligned[aligned["index"] <= threshold]

    if tail_days.empty:
        return float("nan")

    return float(tail_days["bank"].mean())


# ---------------------------------------------------------------------------
# Rolling MES series
# ---------------------------------------------------------------------------
def calc_mes_rolling(
    bank_returns: pd.Series,
    index_returns: pd.Series,
    window: int | None = None,
    tail_pct: float | None = None,
) -> pd.Series:
    """
    Return a daily time series of MES computed over a rolling window.

    Args:
        bank_returns  : Daily returns of the bank.
        index_returns : Daily returns of the regional market index.
        window        : Rolling window size in days (default: cfg.covar_window).
        tail_pct      : Left-tail threshold (default: cfg.mes_tail_pct).

    Returns:
        pd.Series indexed by date, values = MES for each day.
    """
    window = window or cfg.covar_window
    tail_pct = tail_pct if tail_pct is not None else cfg.mes_tail_pct

    aligned = _align(bank_returns, index_returns)
    if aligned.empty:
        return pd.Series(dtype=float)

    results = {}
    for i in range(window, len(aligned)):
        window_data = aligned.iloc[i - window:i]
        thresh = window_data["index"].quantile(tail_pct)
        tail = window_data[window_data["index"] <= thresh]["bank"]
        results[aligned.index[i]] = float(tail.mean()) if not tail.empty else float("nan")

    return pd.Series(results, name=f"{bank_returns.name}_mes")


# ---------------------------------------------------------------------------
# LRMES — closed-form approximation
# ---------------------------------------------------------------------------
def calc_lrmes(
    bank_returns: pd.Series,
    index_returns: pd.Series,
    h: int | None = None,
    market_drop: float | None = None,
    window: int | None = None,
) -> float:
    """OLS-beta scenario proxy; h is a scenario label, not a simulation input."""
    h = h or cfg.lrmes_h
    market_drop = market_drop if market_drop is not None else cfg.lrmes_market_drop
    window = window or cfg.covar_window
    if not 0 < market_drop < 1 or h <= 0 or window < 30:
        raise ValueError("Invalid LRMES scenario parameters")

    aligned = _align(bank_returns, index_returns)
    if len(aligned) < 30:
        return float("nan")

    # Use most recent `window` observations
    data = aligned.tail(window)
    r_b = data["bank"].values
    r_m = data["index"].values

    # OLS market beta = Cov(r_b, r_m) / Var(r_m)
    cov = np.cov(r_b, r_m)
    var_m = cov[1, 1]
    if var_m == 0:
        return float("nan")
    beta_ols = cov[0, 1] / var_m

    # Versioned OLS-beta scenario; no upward selection.
    beta = beta_ols

    # LRMES = 1 - exp(log(1-D) * β)
    lrmes = 1 - np.exp(np.log(1 - market_drop) * beta)
    # Clamp to [0, 1] range — by definition a loss fraction
    return float(np.clip(lrmes, 0.0, 1.0))


def calc_lrmes_rolling(
    bank_returns: pd.Series,
    index_returns: pd.Series,
    window: int | None = None,
    h: int | None = None,
    market_drop: float | None = None,
) -> pd.Series:
    """Rolling daily LRMES time series."""
    window = window or cfg.covar_window
    h = h or cfg.lrmes_h
    market_drop = market_drop if market_drop is not None else cfg.lrmes_market_drop
    if not 0 < market_drop < 1 or h <= 0 or window < 30:
        raise ValueError("Invalid LRMES scenario parameters")

    aligned = _align(bank_returns, index_returns)
    if aligned.empty:
        return pd.Series(dtype=float)

    results = {}
    for i in range(window, len(aligned)):
        sub = aligned.iloc[i - window:i]
        r_b = sub["bank"].values
        r_m = sub["index"].values
        cov = np.cov(r_b, r_m)
        var_m = cov[1, 1]
        if var_m == 0:
            results[aligned.index[i]] = float("nan")
            continue
        beta_ols = cov[0, 1] / var_m
        # Same OLS estimator as the point calculation.
        beta = beta_ols
        val = 1 - np.exp(np.log(1 - market_drop) * beta)
        results[aligned.index[i]] = float(np.clip(val, 0.0, 1.0))

    return pd.Series(results, name=f"{bank_returns.name}_lrmes")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _align(bank: pd.Series, index: pd.Series) -> pd.DataFrame:
    """Inner-join bank and index return series on date."""
    df = pd.DataFrame({"bank": bank, "index": index}).replace([np.inf, -np.inf], np.nan).dropna().sort_index()
    return df
