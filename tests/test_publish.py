"""tests/test_publish.py — Unit tests for data publishing module"""

import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.publish import publish_latest, publish_snapshot, publish_bank_csv
from src.universe import get_bank


@pytest.mark.unit
class TestPublishLatest:
    """Tests for publish_latest function."""

    def test_publish_latest_creates_file(self, temp_data_dir, sample_bank_data, monkeypatch):
        """publish_latest should create latest.json file."""
        monkeypatch.setenv("DATA_DIR", str(temp_data_dir))

        # Reload config to pick up new data dir
        import importlib
        from src import config
        importlib.reload(config)

        bank_records = {"JPM": sample_bank_data}
        system_srisk = 150.5

        publish_latest(date(2024, 6, 15), bank_records, system_srisk)

        latest_file = temp_data_dir / "latest.json"
        assert latest_file.exists()

        with open(latest_file) as f:
            data = json.load(f)

        assert data["date"] == "2024-06-15"
        assert data["system_srisk_usd_bn"] == 150.5
        assert data["bank_count"] == 1
        assert len(data["banks"]) == 1
        assert data["banks"][0]["bank_id"] == "JPM"

    def test_publish_latest_includes_parameters(self, temp_data_dir, sample_bank_data, monkeypatch):
        """published data should include methodology parameters."""
        monkeypatch.setenv("DATA_DIR", str(temp_data_dir))

        import importlib
        from src import config
        importlib.reload(config)

        bank_records = {"JPM": sample_bank_data}
        publish_latest(date(2024, 6, 15), bank_records, 150.0)

        latest_file = temp_data_dir / "latest.json"
        with open(latest_file) as f:
            data = json.load(f)

        assert "parameters" in data
        params = data["parameters"]
        assert "srisk_k" in params
        assert "covar_quantile" in params
        assert "lrmes_horizon_days" in params

    def test_publish_latest_handles_multiple_banks(self, temp_data_dir, monkeypatch):
        """publish_latest should handle multiple banks."""
        monkeypatch.setenv("DATA_DIR", str(temp_data_dir))

        import importlib
        from src import config
        importlib.reload(config)

        bank_records = {
            "JPM": {"bank_id": "JPM", "srisk_usd_bn": 45.0},
            "BAC": {"bank_id": "BAC", "srisk_usd_bn": 35.0},
            "C": {"bank_id": "C", "srisk_usd_bn": 25.0},
        }

        publish_latest(date(2024, 6, 15), bank_records, 105.0)

        latest_file = temp_data_dir / "latest.json"
        with open(latest_file) as f:
            data = json.load(f)

        assert data["bank_count"] == 3
        assert len(data["banks"]) == 3
        bank_ids = [b["bank_id"] for b in data["banks"]]
        assert bank_ids == ["BAC", "C", "JPM"]  # Should be sorted


@pytest.mark.unit
class TestPublishSnapshot:
    """Tests for publish_snapshot function."""

    def test_publish_snapshot_creates_history_file(self, temp_data_dir, sample_bank_data, monkeypatch):
        """publish_snapshot should create dated file in history/."""
        monkeypatch.setenv("DATA_DIR", str(temp_data_dir))

        import importlib
        from src import config
        importlib.reload(config)

        bank_records = {"JPM": sample_bank_data}
        publish_snapshot(date(2024, 6, 15), bank_records, 150.5)

        snapshot_file = temp_data_dir / "history" / "2024-06-15.json"
        assert snapshot_file.exists()

        with open(snapshot_file) as f:
            data = json.load(f)

        assert data["date"] == "2024-06-15"
        assert data["system_srisk_usd_bn"] == 150.5

    def test_publish_snapshot_accepts_string_date(self, temp_data_dir, sample_bank_data, monkeypatch):
        """publish_snapshot should accept date as string."""
        monkeypatch.setenv("DATA_DIR", str(temp_data_dir))

        import importlib
        from src import config
        importlib.reload(config)

        bank_records = {"JPM": sample_bank_data}
        publish_snapshot("2024-06-15", bank_records, 150.5)

        snapshot_file = temp_data_dir / "history" / "2024-06-15.json"
        assert snapshot_file.exists()


@pytest.mark.unit
class TestPublishBankCSV:
    """Tests for publish_bank_csv function."""

    def test_publish_bank_csv_creates_file(self, temp_data_dir, monkeypatch):
        """publish_bank_csv should create bank-specific CSV file."""
        monkeypatch.setenv("DATA_DIR", str(temp_data_dir))

        import importlib
        from src import config
        importlib.reload(config)

        bank = get_bank("JPM")
        date_metrics = {
            "2024-06-15": {
                "mes": -0.025,
                "lrmes": 0.35,
                "covar": -0.015,
                "delta_covar": -0.008,
                "covar_beta": 1.25,
                "srisk_usd_bn": 45.5,
                "srisk_share_pct": 12.3,
                "market_cap_usd_bn": 450.0,
                "debt_usd_bn": 2500.0,
            }
        }

        publish_bank_csv(bank, date_metrics)

        csv_file = temp_data_dir / "banks" / "JPM.csv"
        assert csv_file.exists()

        df = pd.read_csv(csv_file)
        assert len(df) == 1
        assert df.iloc[0]["date"] == "2024-06-15"
        assert df.iloc[0]["mes"] == -0.025
        assert df.iloc[0]["srisk_usd_bn"] == 45.5

    def test_publish_bank_csv_appends_and_deduplicates(self, temp_data_dir, monkeypatch):
        """publish_bank_csv should append new data and deduplicate."""
        monkeypatch.setenv("DATA_DIR", str(temp_data_dir))

        import importlib
        from src import config
        importlib.reload(config)

        bank = get_bank("JPM")

        # First write
        date_metrics_1 = {
            "2024-06-14": {"mes": -0.02, "lrmes": 0.30, "srisk_usd_bn": 40.0}
        }
        publish_bank_csv(bank, date_metrics_1)

        # Second write with overlap
        date_metrics_2 = {
            "2024-06-14": {"mes": -0.02, "lrmes": 0.30, "srisk_usd_bn": 40.0},  # Duplicate
            "2024-06-15": {"mes": -0.025, "lrmes": 0.35, "srisk_usd_bn": 45.0},  # New
        }
        publish_bank_csv(bank, date_metrics_2)

        csv_file = temp_data_dir / "banks" / "JPM.csv"
        df = pd.read_csv(csv_file)

        # Should have 2 unique dates (deduplicated)
        assert len(df) == 2
        assert list(df["date"]) == ["2024-06-14", "2024-06-15"]

    def test_publish_bank_csv_sorts_by_date(self, temp_data_dir, monkeypatch):
        """publish_bank_csv should sort results by date."""
        monkeypatch.setenv("DATA_DIR", str(temp_data_dir))

        import importlib
        from src import config
        importlib.reload(config)

        bank = get_bank("JPM")

        # Write dates out of order
        date_metrics = {
            "2024-06-15": {"mes": -0.025, "srisk_usd_bn": 45.0},
            "2024-06-10": {"mes": -0.020, "srisk_usd_bn": 40.0},
            "2024-06-20": {"mes": -0.030, "srisk_usd_bn": 50.0},
        }
        publish_bank_csv(bank, date_metrics)

        csv_file = temp_data_dir / "banks" / "JPM.csv"
        df = pd.read_csv(csv_file)

        # Should be sorted by date
        assert list(df["date"]) == ["2024-06-10", "2024-06-15", "2024-06-20"]

    def test_publish_bank_csv_empty_dict_no_error(self, temp_data_dir, monkeypatch):
        """publish_bank_csv should handle empty dict without error."""
        monkeypatch.setenv("DATA_DIR", str(temp_data_dir))

        import importlib
        from src import config
        importlib.reload(config)

        bank = get_bank("JPM")
        publish_bank_csv(bank, {})

        csv_file = temp_data_dir / "banks" / "JPM.csv"
        # Should not create file for empty data
        assert not csv_file.exists()

    def test_publish_bank_csv_handles_none_values(self, temp_data_dir, monkeypatch):
        """publish_bank_csv should handle None/NaN values."""
        monkeypatch.setenv("DATA_DIR", str(temp_data_dir))

        import importlib
        from src import config
        importlib.reload(config)

        bank = get_bank("JPM")
        date_metrics = {
            "2024-06-15": {
                "mes": -0.025,
                "lrmes": None,
                "covar": float("nan"),
                "delta_covar": -0.008,
                "srisk_usd_bn": 45.5,
            }
        }

        publish_bank_csv(bank, date_metrics)

        csv_file = temp_data_dir / "banks" / "JPM.csv"
        df = pd.read_csv(csv_file)

        assert len(df) == 1
        # None values should be preserved as NaN in CSV
        assert pd.isna(df.iloc[0]["lrmes"])
