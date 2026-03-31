"""tests/conftest.py — Shared pytest fixtures and configuration"""

import sys
from pathlib import Path

import pytest

# Add parent directory to path so tests can import src modules
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_bank_data():
    """Sample bank data for testing."""
    return {
        "bank_id": "JPM",
        "bank_name": "JPMorgan Chase",
        "region": "US",
        "covar_index": "^GSPC",
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


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create a temporary data directory for testing."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "history").mkdir()
    (data_dir / "banks").mkdir()
    return data_dir
