"""tests/test_metrics.py — Unit tests for MES, CoVaR, SRISK engines"""

import math
import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.metrics.mes import calc_mes, calc_lrmes
from src.metrics.covar import calc_covar
from src.metrics.srisk import calc_srisk, calc_srisk_shares, system_srisk


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_returns():
    """300 days of synthetic returns: bank highly correlated with index."""
    rng = np.random.default_rng(42)
    n = 300
    index_ret = pd.Series(
        rng.normal(0.0003, 0.012, n),
        index=pd.date_range("2023-01-01", periods=n, freq="B"),
        name="IDX",
    )
    # Bank = 1.3 * index + idiosyncratic noise
    bank_ret = pd.Series(
        1.3 * index_ret.values + rng.normal(0, 0.006, n),
        index=index_ret.index,
        name="BANK",
    )
    return bank_ret, index_ret


# ---------------------------------------------------------------------------
# MES tests
# ---------------------------------------------------------------------------
class TestMES:
    def test_mes_is_negative(self, sample_returns):
        """MES should be negative (bank loses on market tail days)."""
        bank, idx = sample_returns
        mes = calc_mes(bank, idx)
        assert mes < 0, f"Expected negative MES, got {mes}"

    def test_mes_nan_on_insufficient_data(self):
        bank = pd.Series([0.01] * 10, index=pd.date_range("2023-01-01", periods=10, freq="B"))
        idx = pd.Series([0.01] * 10, index=bank.index)
        result = calc_mes(bank, idx)
        assert math.isnan(result)

    def test_mes_custom_threshold(self, sample_returns):
        bank, idx = sample_returns
        mes_5 = calc_mes(bank, idx, tail_pct=0.05)
        mes_10 = calc_mes(bank, idx, tail_pct=0.10)
        # 10% tail should include more regular days → less extreme MES
        assert abs(mes_5) >= abs(mes_10) * 0.5  # rough sanity check


# ---------------------------------------------------------------------------
# LRMES tests
# ---------------------------------------------------------------------------
class TestLRMES:
    def test_lrmes_in_range(self, sample_returns):
        bank, idx = sample_returns
        lrmes = calc_lrmes(bank, idx)
        assert 0.0 <= lrmes <= 1.0, f"LRMES out of [0,1]: {lrmes}"

    def test_lrmes_increases_with_beta(self):
        """Higher beta bank should have higher LRMES."""
        rng = np.random.default_rng(7)
        n = 300
        idx = pd.Series(rng.normal(0, 0.01, n), index=pd.date_range("2022-01-01", periods=n, freq="B"))
        bank_low_beta = pd.Series(0.5 * idx.values + rng.normal(0, 0.003, n), index=idx.index)
        bank_high_beta = pd.Series(2.0 * idx.values + rng.normal(0, 0.003, n), index=idx.index)
        lrmes_low = calc_lrmes(bank_low_beta, idx)
        lrmes_high = calc_lrmes(bank_high_beta, idx)
        assert lrmes_high > lrmes_low, f"Expected high beta LRMES > low: {lrmes_high:.4f} vs {lrmes_low:.4f}"

    def test_lrmes_formula_correctness(self):
        """
        LRMES = 1 - exp(log(1-D) * beta_OLS).
        For a bank with known OLS beta, verify the exact closed-form result.
        The old formula (rho * beta * sqrt(h)) was ~5-10x higher than correct.
        """
        rng = np.random.default_rng(99)
        n = 500
        sigma_m = 0.01
        idx = pd.Series(rng.normal(0, sigma_m, n),
                        index=pd.date_range("2020-01-01", periods=n, freq="B"))
        # Construct bank with true beta ≈ 1.5 (low noise)
        true_beta = 1.5
        bank = pd.Series(true_beta * idx.values + rng.normal(0, 0.0005, n), index=idx.index)

        lrmes = calc_lrmes(bank, idx, market_drop=0.40)

        # Expected: 1 - exp(log(0.6) * 1.5) ≈ 0.535
        expected = 1 - np.exp(np.log(0.60) * true_beta)
        assert abs(lrmes - expected) < 0.05, (
            f"LRMES {lrmes:.4f} far from expected {expected:.4f}; "
            "formula may still include incorrect rho or sqrt(h) factors"
        )

    def test_lrmes_realistic_range_for_gsib(self):
        """
        For typical G-SIB parameters (beta 0.8–2.5, D=40%), LRMES should
        fall in [0.15, 0.75] — the range consistent with NYU V-Lab data.
        The old formula produced values of 0.80–0.97 for the same inputs.
        """
        rng = np.random.default_rng(42)
        n = 300
        idx = pd.Series(rng.normal(0, 0.012, n),
                        index=pd.date_range("2022-01-01", periods=n, freq="B"))
        # Bank with beta ≈ 1.3 (typical large US bank vs S&P 500)
        bank = pd.Series(1.3 * idx.values + rng.normal(0, 0.006, n), index=idx.index)
        lrmes = calc_lrmes(bank, idx)
        assert 0.15 <= lrmes <= 0.75, (
            f"LRMES {lrmes:.4f} outside realistic G-SIB range [0.15, 0.75]; "
            "check for incorrect rho * sqrt(h) inflation"
        )

    def test_lrmes_tail_beta_captures_asymmetry(self):
        """
        For a bank with higher sensitivity during market downturns
        (asymmetric tail dependence), LRMES should be higher than the
        OLS-only estimate.  This is critical for preventing unrealistic
        SRISK = 0 for large G-SIBs.
        """
        rng = np.random.default_rng(123)
        n = 500
        idx = pd.Series(rng.normal(0, 0.012, n),
                        index=pd.date_range("2022-01-01", periods=n, freq="B"))
        # Asymmetric returns: beta ≈ 1.8 on down days, ≈ 1.0 on up days
        bank_returns = np.where(
            idx.values < 0,
            1.8 * idx.values + rng.normal(0, 0.003, n),
            1.0 * idx.values + rng.normal(0, 0.003, n),
        )
        bank = pd.Series(bank_returns, index=idx.index)
        lrmes = calc_lrmes(bank, idx)
        # OLS beta averages up/down-day betas ≈ 1.4
        # LRMES with OLS-only β=1.4: 1 - 0.6^1.4 ≈ 0.49
        lrmes_ols_only = 1 - np.exp(np.log(0.6) * 1.4)
        assert lrmes > lrmes_ols_only, (
            f"LRMES {lrmes:.4f} should exceed OLS-only estimate "
            f"{lrmes_ols_only:.4f} when bank has asymmetric tail dependence"
        )


# ---------------------------------------------------------------------------
# CoVaR tests
# ---------------------------------------------------------------------------
class TestCoVaR:
    def test_delta_covar_negative(self, sample_returns):
        """ΔCoVaR should be negative for a positively correlated bank."""
        bank, idx = sample_returns
        result = calc_covar(bank, idx)
        assert result["delta_covar"] < 0, f"Expected negative ΔCoVaR, got {result['delta_covar']}"

    def test_covar_result_keys(self, sample_returns):
        bank, idx = sample_returns
        result = calc_covar(bank, idx)
        assert all(k in result for k in ["covar", "delta_covar", "var_bank", "beta", "alpha"])

    def test_covar_beta_positive(self, sample_returns):
        """Regression beta should be positive (bank co-moves with index)."""
        bank, idx = sample_returns
        result = calc_covar(bank, idx)
        assert result["beta"] > 0


# ---------------------------------------------------------------------------
# SRISK tests
# ---------------------------------------------------------------------------
class TestSRISK:
    def test_srisk_positive_for_undercapitalised(self):
        """SRISK > 0 when bank has high debt, low cap, high LRMES."""
        srisk = calc_srisk(market_cap_usd_bn=50, debt_usd_bn=1000, lrmes=0.5, k=0.08)
        # 0.08*1000 - 0.92*50*(1-0.5) = 80 - 23 = 57 > 0
        assert srisk > 0

    def test_srisk_zero_for_well_capitalised(self):
        """Well-capitalised bank: SRISK = 0."""
        srisk = calc_srisk(market_cap_usd_bn=200, debt_usd_bn=500, lrmes=0.1, k=0.08)
        # 0.08*500 - 0.92*200*0.9 = 40 - 165.6 < 0 → clamped to 0
        assert srisk == 0.0

    def test_srisk_configurable_k(self):
        """Stricter k should produce higher SRISK."""
        srisk_8 = calc_srisk(50, 1000, 0.3, k=0.08)
        srisk_12 = calc_srisk(50, 1000, 0.3, k=0.12)
        assert srisk_12 >= srisk_8

    def test_srisk_nan_on_invalid_inputs(self):
        assert math.isnan(calc_srisk(float("nan"), 1000, 0.3))
        assert math.isnan(calc_srisk(0, 1000, 0.3))  # zero mcap

    def test_srisk_positive_for_large_gsib_with_tail_dependence(self):
        """
        Top G-SIBs like JPM (mcap ~600B, debt ~3400B) should have positive
        SRISK when the bank exhibits asymmetric tail dependence (higher
        co-movement during market downturns).  Previously, using OLS beta
        alone underestimated LRMES and produced SRISK = 0 for these banks,
        which is unrealistic.
        """
        rng = np.random.default_rng(42)
        n = 500
        idx = pd.Series(rng.normal(0, 0.012, n),
                        index=pd.date_range("2022-01-01", periods=n, freq="B"))
        # Asymmetric returns: beta ≈ 1.6 on down days, ≈ 1.1 on up days
        bank_returns = np.where(
            idx.values < 0,
            1.6 * idx.values + rng.normal(0, 0.005, n),
            1.1 * idx.values + rng.normal(0, 0.005, n),
        )
        bank = pd.Series(bank_returns, index=idx.index)
        lrmes = calc_lrmes(bank, idx)

        # JPM-like parameters
        srisk = calc_srisk(
            market_cap_usd_bn=600, debt_usd_bn=3400, lrmes=lrmes, k=0.08
        )
        assert srisk > 0, (
            f"SRISK={srisk:.2f} should be > 0 for JPM-like G-SIB with "
            f"asymmetric tail dependence; LRMES={lrmes:.4f}"
        )


# ---------------------------------------------------------------------------
# SRISK aggregation tests
# ---------------------------------------------------------------------------
class TestSRISKAggregation:
    def test_shares_sum_to_100(self):
        vals = {"A": 50.0, "B": 30.0, "C": 20.0}
        shares = calc_srisk_shares(vals)
        total = sum(shares.values())
        assert abs(total - 100.0) < 0.01

    def test_zero_srisk_excluded_from_shares(self):
        vals = {"A": 50.0, "B": 0.0, "C": float("nan")}
        shares = calc_srisk_shares(vals)
        assert "B" not in shares or shares.get("B", 0) == 0
        assert "C" not in shares

    def test_system_srisk(self):
        vals = {"A": 50.0, "B": 30.0, "C": 0.0, "D": float("nan")}
        assert system_srisk(vals) == 80.0


# ---------------------------------------------------------------------------
# Paper compliance tests — verify formulas match referenced papers
# ---------------------------------------------------------------------------
class TestPaperCompliance:
    """Verify computed results match the formulas from referenced papers."""

    def test_srisk_formula_matches_brownlees_engle_2017(self):
        """
        Brownlees & Engle (2017) eq. (2):
            SRISK_i = max(0, k·D - (1-k)·W·(1-LRMES))

        where capital shortfall = k·(D + W*) - W*,  W* = W·(1 - LRMES).
        Verify the code gives the exact analytical result.
        """
        D, W, L, k = 1000.0, 50.0, 0.5, 0.08
        expected = max(0.0, k * D - (1 - k) * W * (1 - L))
        # 0.08*1000 - 0.92*50*0.5 = 80 - 23 = 57
        assert expected == 57.0
        result = calc_srisk(market_cap_usd_bn=W, debt_usd_bn=D, lrmes=L, k=k)
        assert result == expected

    def test_lrmes_formula_matches_brownlees_engle_2017(self):
        """
        Brownlees & Engle (2017) closed-form approximation:
            LRMES ≈ 1 - exp(log(1-D) · β)

        For known β and D, verify the exact analytical result.
        """
        D = 0.40   # 40% market drop
        beta = 1.2
        expected = 1 - np.exp(np.log(1 - D) * beta)
        # 1 - exp(log(0.6) * 1.2) ≈ 0.474
        assert 0.40 < expected < 0.55

        # Generate synthetic returns with known beta
        rng = np.random.default_rng(314)
        n = 500
        idx = pd.Series(rng.normal(0, 0.01, n),
                        index=pd.date_range("2020-01-01", periods=n, freq="B"))
        bank = pd.Series(beta * idx.values + rng.normal(0, 0.0005, n),
                         index=idx.index)

        lrmes = calc_lrmes(bank, idx, market_drop=D)
        # Tolerance accounts for tail-adjusted beta (max(β_OLS, β_tail))
        # which can shift the result slightly above the pure OLS-based value
        assert abs(lrmes - expected) < 0.06, (
            f"LRMES {lrmes:.4f} deviates from analytical {expected:.4f} for β={beta}"
        )

    def test_covar_quantile_regression_direction(self):
        """
        Adrian & Brunnermeier (2011): CoVaR is estimated by regressing
        system returns on bank returns at quantile τ:
            q_τ(r_system | r_bank = x) = α + β·x

        Verify that β > 0 for positively correlated bank-system pairs
        and that ΔCoVaR is negative (more negative = more systemic).
        """
        rng = np.random.default_rng(42)
        n = 300
        idx = pd.Series(rng.normal(0, 0.01, n),
                        index=pd.date_range("2022-01-01", periods=n, freq="B"))
        bank = pd.Series(1.5 * idx.values + rng.normal(0, 0.005, n),
                         index=idx.index)

        result = calc_covar(bank, idx)
        assert result["beta"] > 0, "CoVaR β should be positive for co-moving pair"
        assert result["delta_covar"] < 0, "ΔCoVaR should be negative (systemic contribution)"

    def test_mes_consistent_with_acharya_2010(self):
        """
        Acharya et al. (2010): MES = E[r_i | r_m ≤ VaR_τ(r_m)]
        MES should be negative during market tail days for positively
        correlated banks, and more negative for higher-beta banks.
        """
        rng = np.random.default_rng(42)
        n = 300
        idx = pd.Series(rng.normal(0, 0.01, n),
                        index=pd.date_range("2022-01-01", periods=n, freq="B"))
        bank_low = pd.Series(0.8 * idx.values + rng.normal(0, 0.003, n),
                             index=idx.index)
        bank_high = pd.Series(2.0 * idx.values + rng.normal(0, 0.003, n),
                              index=idx.index)

        mes_low = calc_mes(bank_low, idx)
        mes_high = calc_mes(bank_high, idx)
        assert mes_low < 0, "MES should be negative"
        assert mes_high < 0, "MES should be negative"
        assert mes_high < mes_low, (
            f"Higher-beta bank should have more negative MES: "
            f"high={mes_high:.4f} vs low={mes_low:.4f}"
        )

    def test_lrmes_h_config_documents_six_month_horizon(self):
        """
        Brownlees & Engle (2017) use a 6-month crisis horizon (~126 trading days)
        for the 40% market drop scenario. The default lrmes_h should reflect this.
        """
        from src.config import _int
        # Check the hardcoded default (not the runtime value which can be
        # overridden via LRMES_H env var)
        import os
        if "LRMES_H" not in os.environ:
            from src.config import cfg
            assert cfg.lrmes_h == 126, (
                f"Default lrmes_h should be 126 (≈ 6 months) per "
                f"Brownlees & Engle (2017), got {cfg.lrmes_h}"
            )

    def test_gsib_count_matches_universe(self):
        """Universe should contain exactly 29 G-SIBs (FSB 2023 list)."""
        from src.universe import BANKS
        assert len(BANKS) == 29, (
            f"Expected 29 G-SIBs (FSB 2023 list), got {len(BANKS)}"
        )
