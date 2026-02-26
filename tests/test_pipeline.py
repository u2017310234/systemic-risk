"""tests/test_pipeline.py — Tests for pipeline error handling"""

import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pipeline import run_pipeline


class TestPipelineFailure:
    """Pipeline must raise RuntimeError when no data is produced."""

    def test_raises_when_all_banks_fail(self):
        """run_pipeline raises RuntimeError when every bank returns no data."""
        with patch("src.pipeline.process_bank", return_value=None):
            with pytest.raises(RuntimeError, match="Pipeline produced no data"):
                run_pipeline(
                    target_date=date(2024, 6, 1),
                    start_date=date(2024, 1, 1),
                    bank_ids=["JPM"],
                )

    def test_raises_when_all_banks_raise(self):
        """run_pipeline raises RuntimeError when every bank raises an exception."""
        with patch("src.pipeline.process_bank", side_effect=ValueError("fetch error")):
            with pytest.raises(RuntimeError, match="Pipeline produced no data"):
                run_pipeline(
                    target_date=date(2024, 6, 1),
                    start_date=date(2024, 1, 1),
                    bank_ids=["JPM"],
                )

    def test_no_raise_when_some_banks_succeed(self):
        """run_pipeline does NOT raise when at least one bank returns data."""
        fake_data = {
            "2024-06-01": {
                "bank_id": "JPM",
                "bank_name": "JPMorgan Chase",
                "region": "US",
                "covar_index": "^GSPC",
                "mes": -0.02,
                "lrmes": 0.3,
                "covar": -0.01,
                "delta_covar": -0.005,
                "covar_beta": 1.2,
                "srisk_usd_bn": 10.0,
                "market_cap_usd_bn": 400.0,
                "debt_usd_bn": 2000.0,
            }
        }
        with patch("src.pipeline.process_bank", return_value=fake_data), \
             patch("src.pipeline.publish_bank_csv"), \
             patch("src.pipeline.publish_snapshot"), \
             patch("src.pipeline.publish_latest"):
            # Should not raise
            run_pipeline(
                target_date=date(2024, 6, 1),
                start_date=date(2024, 1, 1),
                bank_ids=["JPM"],
            )
