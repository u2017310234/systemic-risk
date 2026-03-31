"""tests/test_utils.py — Unit tests for utility functions"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import is_valid_date


@pytest.mark.unit
class TestIsValidDate:
    """Tests for date validation function (extended from test_security.py)."""

    def test_valid_date(self):
        """Valid dates should pass."""
        assert is_valid_date("2024-01-15") is True
        assert is_valid_date("2020-12-31") is True
        assert is_valid_date("2023-06-15") is True

    def test_valid_date_boundary(self):
        """Boundary dates should be valid."""
        assert is_valid_date("2015-01-01") is True
        assert is_valid_date("2099-12-31") is True

    def test_valid_leap_year(self):
        """Leap year dates should be valid."""
        assert is_valid_date("2024-02-29") is True
        assert is_valid_date("2020-02-29") is True

    def test_invalid_date_traversal(self):
        """Path traversal sequences must be rejected."""
        assert is_valid_date("../../etc/passwd") is False
        assert is_valid_date("../secret") is False
        assert is_valid_date("2024-01-01/../../etc") is False
        assert is_valid_date("./2024-01-01") is False

    def test_invalid_date_format(self):
        """Improperly formatted dates must be rejected."""
        assert is_valid_date("20240115") is False
        assert is_valid_date("2024/01/15") is False
        assert is_valid_date("2024.01.15") is False
        assert is_valid_date("not-a-date") is False
        assert is_valid_date("") is False
        assert is_valid_date("2024-1-15") is False  # Missing zero-padding
        assert is_valid_date("2024-01-5") is False  # Missing zero-padding

    def test_invalid_calendar_date(self):
        """Structurally valid but impossible dates must be rejected."""
        assert is_valid_date("2024-13-01") is False  # Invalid month
        assert is_valid_date("2024-00-01") is False  # Invalid month
        assert is_valid_date("2024-02-30") is False  # February doesn't have 30 days
        assert is_valid_date("2024-04-31") is False  # April only has 30 days
        assert is_valid_date("2024-02-00") is False  # Invalid day
        assert is_valid_date("2023-02-29") is False  # Not a leap year

    def test_invalid_date_with_extra_chars(self):
        """Dates with extra characters must be rejected."""
        assert is_valid_date("2024-01-15 extra") is False
        assert is_valid_date(" 2024-01-15") is False
        assert is_valid_date("2024-01-15\n") is False
        assert is_valid_date("2024-01-15\t") is False

    def test_invalid_date_sql_injection(self):
        """SQL injection attempts must be rejected."""
        assert is_valid_date("2024-01-15'; DROP TABLE--") is False
        assert is_valid_date("2024-01-15' OR '1'='1") is False

    def test_invalid_date_special_chars(self):
        """Special characters must be rejected."""
        assert is_valid_date("2024-01-15\x00") is False  # Null byte
        assert is_valid_date("2024-01-15<script>") is False
        assert is_valid_date("2024-01-15&param=value") is False

    def test_year_range_boundaries(self):
        """Test various year ranges."""
        assert is_valid_date("1900-01-01") is True
        assert is_valid_date("2100-12-31") is True
        assert is_valid_date("0000-01-01") is False  # Year 0 doesn't exist in ISO calendar
