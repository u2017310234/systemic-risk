"""tests/test_fetcher.py — Tests for data fetcher, FX conversion, and anomaly detection"""

import logging
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.universe import Bank


class TestMarketCapAnomalyDetection:
    """Verify that unreasonable market cap values trigger warnings and fallback."""

    def _make_bank(self, ticker=".HK"):
        return Bank(
            id="TEST",
            name="Test Bank",
            region="CN",
            yf_ticker=f"9999{ticker}",
            index_yf="^HSI",
        )

    def test_reasonable_mcap_no_warning(self, caplog):
        """Normal market cap should not trigger any warning."""
        bank = self._make_bank("")  # US-style ticker, no FX needed
        dates = pd.date_range("2024-01-01", periods=5, freq="B")
        prices = pd.Series([50.0] * 5, index=dates, name="TEST")
        shares = 1e9  # 1 billion shares → mcap = 50 * 1e9 / 1e9 = 50 USD bn

        mock_fast_info = MagicMock()
        mock_fast_info.shares = shares
        mock_fast_info.market_cap = 50e9

        mock_ticker = MagicMock()
        mock_ticker.fast_info = mock_fast_info

        with patch("src.fetcher.fetch_prices", return_value=prices), \
             patch("src.fetcher._yf") as mock_yf:
            mock_yf.return_value.Ticker.return_value = mock_ticker

            from src.fetcher import fetch_market_cap_series
            with caplog.at_level(logging.WARNING):
                result = fetch_market_cap_series(bank, "2024-01-01", "2024-01-05")

            assert not result.empty
            # Should not have any DATA QUALITY warnings
            assert "[DATA QUALITY]" not in caplog.text

    def test_unreasonable_mcap_triggers_warning(self, caplog):
        """Market cap > 3000 USD bn should trigger a data quality warning."""
        bank = self._make_bank("")
        dates = pd.date_range("2024-01-01", periods=5, freq="B")
        prices = pd.Series([500.0] * 5, index=dates, name="TEST")
        shares = 100e9  # huge shares → mcap = 500 * 100e9 / 1e9 = 50000 USD bn

        mock_fast_info = MagicMock()
        mock_fast_info.shares = shares
        mock_fast_info.market_cap = 200e9  # reasonable fallback

        mock_ticker = MagicMock()
        mock_ticker.fast_info = mock_fast_info

        with patch("src.fetcher.fetch_prices", return_value=prices), \
             patch("src.fetcher._yf") as mock_yf:
            mock_yf.return_value.Ticker.return_value = mock_ticker

            from src.fetcher import fetch_market_cap_series
            with caplog.at_level(logging.WARNING):
                result = fetch_market_cap_series(bank, "2024-01-01", "2024-01-05")

            assert "[DATA QUALITY]" in caplog.text
            assert "exceeds 3000 USD bn" in caplog.text
            # Should have fallen back to the reasonable marketCap
            assert (result.median() - 200.0) < 1.0  # 200 USD bn from fallback

    def test_unreasonable_mcap_no_fallback_available(self, caplog):
        """When fallback is also unavailable, keep computed value and warn."""
        bank = self._make_bank("")
        dates = pd.date_range("2024-01-01", periods=5, freq="B")
        prices = pd.Series([500.0] * 5, index=dates, name="TEST")
        shares = 100e9  # huge

        mock_fast_info = MagicMock()
        mock_fast_info.shares = shares
        mock_fast_info.market_cap = None  # no fallback

        mock_ticker = MagicMock()
        mock_ticker.fast_info = mock_fast_info

        with patch("src.fetcher.fetch_prices", return_value=prices), \
             patch("src.fetcher._yf") as mock_yf:
            mock_yf.return_value.Ticker.return_value = mock_ticker

            from src.fetcher import fetch_market_cap_series
            with caplog.at_level(logging.WARNING):
                result = fetch_market_cap_series(bank, "2024-01-01", "2024-01-05")

            assert "no fallback marketCap available" in caplog.text
            # Keeps the original (inflated) value since no fallback exists
            assert result.median() > 3000


class TestFXConversionDirection:
    """Verify FX conversion logic produces values in the correct direction."""

    def test_to_usd_jpy_uses_correct_ticker(self):
        """JPY conversion should use JPYUSD=X (USD per JPY ≈ 0.0065), not JPY=X."""
        from src.fetcher import _to_usd

        source_file = Path(__file__).parent.parent / "src" / "fetcher.py"
        source = source_file.read_text(encoding="utf-8")

        # The correct ticker for JPY → USD is JPYUSD=X (gives ~0.0065)
        # JPY=X gives ~155 (JPY per USD) which would inflate values
        assert '"JPYUSD=X"' in source, (
            "JPY conversion should use JPYUSD=X (USD per JPY), not JPY=X"
        )
        # Also verify CNY uses the correct direction
        assert '"CNYUSD=X"' in source, (
            "CNY conversion should use CNYUSD=X (USD per CNY)"
        )

    def test_to_usd_bs_hk_uses_cny_not_hkd(self):
        """Balance sheet FX for HK-listed Chinese banks should use CNY, not HKD."""
        source_file = Path(__file__).parent.parent / "src" / "fetcher.py"
        source = source_file.read_text(encoding="utf-8")

        # In _to_usd_bs, .HK should map to CNYUSD=X (CN banks report in CNY)
        assert 'bs_fx_pairs' in source
        # The function should have CNYUSD=X for .HK in balance sheet conversion
        assert '".HK": ("CNYUSD=X"' in source, (
            "Balance sheet FX for .HK should use CNYUSD=X (Chinese banks report in CNY)"
        )
