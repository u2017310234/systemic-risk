"""tests/test_config.py — Unit tests for configuration module"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.mark.unit
class TestConfig:
    """Tests for configuration loading and defaults."""

    def test_default_values(self, monkeypatch):
        """Verify default configuration values."""
        # Clear any existing env vars
        for key in ["SRISK_K", "MES_TAIL_PCT", "LRMES_H", "COVAR_QUANTILE"]:
            monkeypatch.delenv(key, raising=False)

        # Reload config module to pick up clean environment
        import importlib
        from src import config
        importlib.reload(config)

        cfg = config.cfg
        assert cfg.srisk_k == 0.08
        assert cfg.mes_tail_pct == 0.05
        assert cfg.lrmes_h == 22
        assert cfg.lrmes_market_drop == 0.40
        assert cfg.covar_quantile == 0.05
        assert cfg.covar_window == 252
        assert cfg.data_dir == "data"
        assert cfg.mcp_host == "127.0.0.1"
        assert cfg.mcp_port == 8000

    def test_env_override_float(self, monkeypatch):
        """Test that float parameters can be overridden via environment."""
        monkeypatch.setenv("SRISK_K", "0.12")
        monkeypatch.setenv("MES_TAIL_PCT", "0.10")

        import importlib
        from src import config
        importlib.reload(config)

        cfg = config.cfg
        assert cfg.srisk_k == 0.12
        assert cfg.mes_tail_pct == 0.10

    def test_env_override_int(self, monkeypatch):
        """Test that integer parameters can be overridden via environment."""
        monkeypatch.setenv("LRMES_H", "30")
        monkeypatch.setenv("COVAR_WINDOW", "500")
        monkeypatch.setenv("MCP_PORT", "9000")

        import importlib
        from src import config
        importlib.reload(config)

        cfg = config.cfg
        assert cfg.lrmes_h == 30
        assert cfg.covar_window == 500
        assert cfg.mcp_port == 9000

    def test_env_override_string(self, monkeypatch):
        """Test that string parameters can be overridden via environment."""
        monkeypatch.setenv("DATA_DIR", "/tmp/test_data")
        monkeypatch.setenv("MCP_HOST", "0.0.0.0")
        monkeypatch.setenv("GITHUB_REPO", "test-org/test-repo")

        import importlib
        from src import config
        importlib.reload(config)

        cfg = config.cfg
        assert cfg.data_dir == "/tmp/test_data"
        assert cfg.mcp_host == "0.0.0.0"
        assert cfg.github_repo == "test-org/test-repo"

    def test_raw_base_url_with_repo(self, monkeypatch):
        """Test raw_base_url when GitHub repo is configured."""
        monkeypatch.setenv("GITHUB_REPO", "user/repo")
        monkeypatch.setenv("GITHUB_BRANCH", "develop")

        import importlib
        from src import config
        importlib.reload(config)

        cfg = config.cfg
        url = cfg.raw_base_url()
        assert url == "https://raw.githubusercontent.com/user/repo/develop"

    def test_raw_base_url_without_repo(self, monkeypatch):
        """Test raw_base_url returns None when no repo configured."""
        monkeypatch.setenv("GITHUB_REPO", "")

        import importlib
        from src import config
        importlib.reload(config)

        cfg = config.cfg
        url = cfg.raw_base_url()
        assert url is None

    def test_config_parameters_in_valid_ranges(self):
        """Verify configuration parameters are within valid ranges."""
        from src.config import cfg

        # SRISK capital ratio should be positive and reasonable (e.g., 5-15%)
        assert 0.01 <= cfg.srisk_k <= 0.20

        # MES tail percentile should be between 0 and 1
        assert 0.0 < cfg.mes_tail_pct < 1.0

        # LRMES horizon should be positive
        assert cfg.lrmes_h > 0

        # Market drop should be between 0 and 1
        assert 0.0 < cfg.lrmes_market_drop < 1.0

        # CoVaR quantile should be between 0 and 1
        assert 0.0 < cfg.covar_quantile < 1.0

        # CoVaR window should be positive
        assert cfg.covar_window > 0

        # MCP port should be valid port number
        assert 1 <= cfg.mcp_port <= 65535
