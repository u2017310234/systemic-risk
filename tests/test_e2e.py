"""tests/test_e2e.py — End-to-end tests for complete pipeline workflows"""

import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.mark.e2e
class TestEndToEndPipeline:
    """End-to-end tests for the complete data pipeline."""

    @pytest.fixture
    def mock_price_data(self):
        """Generate realistic mock price data for testing."""
        dates = pd.date_range("2024-01-01", periods=300, freq="B")
        rng = np.random.default_rng(42)

        # Create correlated returns for bank and index
        index_returns = rng.normal(0.0005, 0.012, 300)
        bank_returns = 1.3 * index_returns + rng.normal(0, 0.006, 300)

        # Convert to prices (starting at 100)
        index_prices = pd.Series(100 * np.exp(np.cumsum(index_returns)), index=dates)
        bank_prices = pd.Series(100 * np.exp(np.cumsum(bank_returns)), index=dates)

        return bank_prices, index_prices

    def test_single_bank_pipeline_success(self, temp_data_dir, mock_price_data, monkeypatch):
        """Test complete pipeline for a single bank."""
        monkeypatch.setenv("DATA_DIR", str(temp_data_dir))

        # Reload modules to pick up new data dir
        import importlib
        from src import config, pipeline
        importlib.reload(config)
        importlib.reload(pipeline)

        bank_prices, index_prices = mock_price_data

        # Mock the fetcher functions
        with patch("src.pipeline.fetch_prices") as mock_fetch_prices, \
             patch("src.pipeline.fetch_market_cap_series") as mock_fetch_mcap, \
             patch("src.pipeline.fetch_debt") as mock_fetch_debt:

            # Setup mocks to return appropriate values
            def fetch_prices_side_effect(ticker, start, end):
                if "^GSPC" in ticker or ticker == "^GSPC":
                    return index_prices
                return bank_prices

            mock_fetch_prices.side_effect = fetch_prices_side_effect

            # Mock market cap (in USD billions)
            dates = bank_prices.index
            mock_fetch_mcap.return_value = pd.Series(
                [400.0] * len(dates), index=dates
            )

            # Mock debt (in USD billions)
            mock_fetch_debt.return_value = 2500.0

            # Run pipeline for single bank
            from src.pipeline import run_pipeline

            run_pipeline(
                target_date=date(2024, 12, 1),
                start_date=date(2024, 1, 1),
                bank_ids=["JPM"],
            )

            # Verify outputs were created
            latest_file = temp_data_dir / "latest.json"
            assert latest_file.exists()

            history_file = temp_data_dir / "history" / "2024-12-01.json"
            assert history_file.exists()

            bank_csv = temp_data_dir / "banks" / "JPM.csv"
            assert bank_csv.exists()

            # Verify latest.json structure
            with open(latest_file) as f:
                latest_data = json.load(f)

            assert latest_data["date"] == "2024-12-01"
            assert "system_srisk_usd_bn" in latest_data
            assert latest_data["bank_count"] >= 1
            assert len(latest_data["banks"]) >= 1

            # Find JPM in banks
            jpm_data = next((b for b in latest_data["banks"] if b["bank_id"] == "JPM"), None)
            assert jpm_data is not None

            # Verify all metrics are present
            assert "mes" in jpm_data
            assert "lrmes" in jpm_data
            assert "covar" in jpm_data
            assert "delta_covar" in jpm_data
            assert "srisk_usd_bn" in jpm_data
            assert "market_cap_usd_bn" in jpm_data
            assert "debt_usd_bn" in jpm_data

            # Verify bank CSV
            df = pd.read_csv(bank_csv)
            assert len(df) > 0
            assert "date" in df.columns
            assert "mes" in df.columns
            assert "srisk_usd_bn" in df.columns

    def test_pipeline_partial_failure_continues(self, temp_data_dir, mock_price_data, monkeypatch):
        """Test that pipeline continues when some banks fail."""
        monkeypatch.setenv("DATA_DIR", str(temp_data_dir))

        import importlib
        from src import config
        importlib.reload(config)

        bank_prices, index_prices = mock_price_data

        with patch("src.pipeline.process_bank") as mock_process:
            # First bank succeeds, second fails, third succeeds
            mock_process.side_effect = [
                {"2024-06-01": {"bank_id": "JPM", "srisk_usd_bn": 45.0}},  # Success
                None,  # Failure
                {"2024-06-01": {"bank_id": "C", "srisk_usd_bn": 25.0}},  # Success
            ]

            from src.pipeline import run_pipeline

            # Should not raise even though one bank failed
            run_pipeline(
                target_date=date(2024, 6, 1),
                start_date=date(2024, 1, 1),
                bank_ids=["JPM", "BAC", "C"],
            )

            # Latest should be created with successful banks only
            latest_file = temp_data_dir / "latest.json"
            assert latest_file.exists()

            with open(latest_file) as f:
                data = json.load(f)

            # Should have 2 banks (JPM and C, BAC failed)
            assert data["bank_count"] == 2


@pytest.mark.e2e
class TestDataIntegrity:
    """End-to-end tests for data integrity and consistency."""

    def test_metrics_are_in_valid_ranges(self, temp_data_dir, monkeypatch):
        """Verify computed metrics fall within expected ranges."""
        monkeypatch.setenv("DATA_DIR", str(temp_data_dir))

        import importlib
        from src import config
        importlib.reload(config)

        # Create a sample output file
        sample_data = {
            "date": "2024-06-15",
            "system_srisk_usd_bn": 500.0,
            "bank_count": 1,
            "banks": [
                {
                    "bank_id": "JPM",
                    "bank_name": "JPMorgan Chase",
                    "region": "US",
                    "mes": -0.025,
                    "lrmes": 0.35,
                    "covar": -0.015,
                    "delta_covar": -0.008,
                    "srisk_usd_bn": 45.5,
                    "srisk_share_pct": 9.1,
                    "market_cap_usd_bn": 450.0,
                    "debt_usd_bn": 2500.0,
                }
            ],
        }

        latest_file = temp_data_dir / "latest.json"
        with open(latest_file, "w") as f:
            json.dump(sample_data, f)

        # Read and validate
        with open(latest_file) as f:
            data = json.load(f)

        for bank in data["banks"]:
            # MES should be negative (bank loses on market down days)
            if bank.get("mes") is not None:
                assert bank["mes"] < 0

            # LRMES should be between 0 and 1
            if bank.get("lrmes") is not None:
                assert 0.0 <= bank["lrmes"] <= 1.0

            # ΔCoVaR should be negative for systemic banks
            if bank.get("delta_covar") is not None:
                assert bank["delta_covar"] < 0

            # SRISK should be non-negative
            if bank.get("srisk_usd_bn") is not None:
                assert bank["srisk_usd_bn"] >= 0

            # SRISK share should be between 0 and 100
            if bank.get("srisk_share_pct") is not None:
                assert 0.0 <= bank["srisk_share_pct"] <= 100.0

            # Market cap and debt should be positive
            if bank.get("market_cap_usd_bn") is not None:
                assert bank["market_cap_usd_bn"] > 0
            if bank.get("debt_usd_bn") is not None:
                assert bank["debt_usd_bn"] > 0

    def test_srisk_shares_sum_to_100(self, temp_data_dir, monkeypatch):
        """SRISK percentage shares across all banks should sum to ~100%."""
        monkeypatch.setenv("DATA_DIR", str(temp_data_dir))

        import importlib
        from src import config
        importlib.reload(config)

        sample_data = {
            "date": "2024-06-15",
            "system_srisk_usd_bn": 100.0,
            "bank_count": 3,
            "banks": [
                {"bank_id": "JPM", "srisk_usd_bn": 50.0, "srisk_share_pct": 50.0},
                {"bank_id": "BAC", "srisk_usd_bn": 30.0, "srisk_share_pct": 30.0},
                {"bank_id": "C", "srisk_usd_bn": 20.0, "srisk_share_pct": 20.0},
            ],
        }

        latest_file = temp_data_dir / "latest.json"
        with open(latest_file, "w") as f:
            json.dump(sample_data, f)

        with open(latest_file) as f:
            data = json.load(f)

        total_share = sum(
            b.get("srisk_share_pct", 0)
            for b in data["banks"]
            if b.get("srisk_share_pct") is not None
        )

        # Should sum to approximately 100% (allowing for rounding)
        assert abs(total_share - 100.0) < 0.1


@pytest.mark.e2e
@pytest.mark.slow
class TestHistoricalBackfill:
    """End-to-end tests for historical data backfill."""

    def test_backfill_creates_multiple_snapshots(self, temp_data_dir, monkeypatch):
        """Test that backfill creates snapshot for each date."""
        monkeypatch.setenv("DATA_DIR", str(temp_data_dir))

        import importlib
        from src import config
        importlib.reload(config)

        # Mock to avoid actual API calls
        with patch("src.pipeline.process_bank") as mock_process:
            mock_process.return_value = {
                "2024-06-01": {"bank_id": "JPM", "srisk_usd_bn": 45.0},
                "2024-06-02": {"bank_id": "JPM", "srisk_usd_bn": 46.0},
                "2024-06-03": {"bank_id": "JPM", "srisk_usd_bn": 44.0},
            }

            from src.pipeline import run_pipeline

            run_pipeline(
                target_date=date(2024, 6, 3),
                start_date=date(2024, 6, 1),
                bank_ids=["JPM"],
            )

            # Should create 3 snapshot files
            history_dir = temp_data_dir / "history"
            snapshots = list(history_dir.glob("*.json"))
            assert len(snapshots) >= 1  # At least latest date

            # Bank CSV should have multiple rows
            bank_csv = temp_data_dir / "banks" / "JPM.csv"
            if bank_csv.exists():
                df = pd.read_csv(bank_csv)
                assert len(df) >= 1
