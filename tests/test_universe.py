"""tests/test_universe.py — Unit tests for bank universe module"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.universe import Bank, BANKS, BANK_BY_ID, REGIONS, ALL_INDICES, get_bank, banks_by_region


@pytest.mark.unit
class TestBankDataClass:
    """Tests for Bank dataclass."""

    def test_bank_creation(self):
        """Test creating a Bank instance."""
        bank = Bank(
            id="TEST",
            name="Test Bank",
            region="US",
            yf_ticker="TEST",
            index_yf="^GSPC",
        )
        assert bank.id == "TEST"
        assert bank.name == "Test Bank"
        assert bank.region == "US"
        assert bank.yf_ticker == "TEST"
        assert bank.index_yf == "^GSPC"
        assert bank.ak_ticker is None
        assert bank.listing == "equity"

    def test_bank_with_optional_fields(self):
        """Test Bank with optional fields."""
        bank = Bank(
            id="TEST",
            name="Test Bank",
            region="CN",
            yf_ticker="1234.HK",
            index_yf="^HSI",
            ak_ticker="601234",
            listing="adr",
        )
        assert bank.ak_ticker == "601234"
        assert bank.listing == "adr"


@pytest.mark.unit
class TestBankRegistry:
    """Tests for the G-SIB bank registry."""

    def test_banks_list_not_empty(self):
        """Banks list should contain all G-SIBs."""
        assert len(BANKS) > 0
        # FSB 2023 list has 29 active G-SIBs (after Credit Suisse merger)
        assert len(BANKS) == 29

    def test_all_banks_have_required_fields(self):
        """Every bank must have all required fields."""
        for bank in BANKS:
            assert bank.id
            assert bank.name
            assert bank.region in ["US", "CN", "GB", "EU", "JP"]
            assert bank.yf_ticker
            assert bank.index_yf

    def test_bank_ids_are_unique(self):
        """Bank IDs must be unique."""
        ids = [b.id for b in BANKS]
        assert len(ids) == len(set(ids))

    def test_bank_by_id_dict(self):
        """BANK_BY_ID dict should contain all banks."""
        assert len(BANK_BY_ID) == len(BANKS)
        for bank in BANKS:
            assert bank.id in BANK_BY_ID
            assert BANK_BY_ID[bank.id] == bank

    def test_regions_list(self):
        """REGIONS should contain all unique regions."""
        expected_regions = ["CN", "EU", "GB", "JP", "US"]
        assert REGIONS == expected_regions

    def test_all_indices_list(self):
        """ALL_INDICES should contain all unique index tickers."""
        assert len(ALL_INDICES) > 0
        # Should have at least 5 unique indices (one per region minimum)
        assert len(ALL_INDICES) >= 5
        # Should be deduplicated
        assert len(ALL_INDICES) == len(set(ALL_INDICES))


@pytest.mark.unit
class TestGetBank:
    """Tests for get_bank function."""

    def test_get_bank_valid_id(self):
        """get_bank should return correct bank for valid ID."""
        bank = get_bank("JPM")
        assert bank.id == "JPM"
        assert bank.name == "JPMorgan Chase"
        assert bank.region == "US"

    def test_get_bank_case_insensitive(self):
        """get_bank should be case-insensitive."""
        bank_upper = get_bank("JPM")
        bank_lower = get_bank("jpm")
        bank_mixed = get_bank("JpM")
        assert bank_upper == bank_lower == bank_mixed

    def test_get_bank_invalid_id_raises(self):
        """get_bank should raise KeyError for invalid ID."""
        with pytest.raises(KeyError):
            get_bank("INVALID")

    def test_get_bank_chinese_bank(self):
        """Test getting a Chinese bank with AkShare ticker."""
        bank = get_bank("ICBC")
        assert bank.id == "ICBC"
        assert bank.region == "CN"
        assert bank.ak_ticker is not None
        assert bank.index_yf == "^HSI"

    def test_get_bank_european_bank(self):
        """Test getting a European bank."""
        bank = get_bank("BNP")
        assert bank.id == "BNP"
        assert bank.region == "EU"
        assert bank.index_yf == "^STOXX50E"


@pytest.mark.unit
class TestBanksByRegion:
    """Tests for banks_by_region function."""

    def test_banks_by_region_us(self):
        """Test filtering US banks."""
        us_banks = banks_by_region("US")
        assert len(us_banks) == 8  # 8 US G-SIBs
        assert all(b.region == "US" for b in us_banks)
        bank_ids = [b.id for b in us_banks]
        assert "JPM" in bank_ids
        assert "BAC" in bank_ids
        assert "GS" in bank_ids

    def test_banks_by_region_cn(self):
        """Test filtering Chinese banks."""
        cn_banks = banks_by_region("CN")
        assert len(cn_banks) == 5  # 5 Chinese G-SIBs
        assert all(b.region == "CN" for b in cn_banks)
        assert all(b.ak_ticker is not None for b in cn_banks)

    def test_banks_by_region_eu(self):
        """Test filtering European banks."""
        eu_banks = banks_by_region("EU")
        assert len(eu_banks) == 10  # 10 European G-SIBs
        assert all(b.region == "EU" for b in eu_banks)

    def test_banks_by_region_gb(self):
        """Test filtering UK banks."""
        gb_banks = banks_by_region("GB")
        assert len(gb_banks) == 3  # 3 UK G-SIBs
        assert all(b.region == "GB" for b in gb_banks)
        bank_ids = [b.id for b in gb_banks]
        assert "HSBC" in bank_ids
        assert "BARC" in bank_ids
        assert "STAN" in bank_ids

    def test_banks_by_region_jp(self):
        """Test filtering Japanese banks."""
        jp_banks = banks_by_region("JP")
        assert len(jp_banks) == 3  # 3 Japanese G-SIBs
        assert all(b.region == "JP" for b in jp_banks)

    def test_banks_by_region_case_insensitive(self):
        """banks_by_region should be case-insensitive."""
        upper = banks_by_region("US")
        lower = banks_by_region("us")
        assert upper == lower

    def test_banks_by_region_invalid_returns_empty(self):
        """banks_by_region should return empty list for invalid region."""
        result = banks_by_region("INVALID")
        assert result == []


@pytest.mark.unit
class TestBankDataQuality:
    """Tests for data quality and consistency."""

    def test_all_us_banks_use_sp500(self):
        """All US banks should use S&P 500 as index."""
        us_banks = banks_by_region("US")
        assert all(b.index_yf == "^GSPC" for b in us_banks)

    def test_all_eu_banks_use_stoxx50e(self):
        """All EU banks should use EURO STOXX 50 as index."""
        eu_banks = banks_by_region("EU")
        assert all(b.index_yf == "^STOXX50E" for b in eu_banks)

    def test_all_gb_banks_use_ftse(self):
        """All GB banks should use FTSE 100 as index."""
        gb_banks = banks_by_region("GB")
        assert all(b.index_yf == "^FTSE" for b in gb_banks)

    def test_all_jp_banks_use_nikkei(self):
        """All JP banks should use Nikkei 225 as index."""
        jp_banks = banks_by_region("JP")
        assert all(b.index_yf == "^N225" for b in jp_banks)

    def test_chinese_banks_have_hk_or_csi_index(self):
        """Chinese banks should use either HSI or CSI 300."""
        cn_banks = banks_by_region("CN")
        for bank in cn_banks:
            assert bank.index_yf in ["^HSI", "000300.SS"]

    def test_no_duplicate_names(self):
        """Bank names should be unique."""
        names = [b.name for b in BANKS]
        assert len(names) == len(set(names))

    def test_ticker_format_consistency(self):
        """Verify ticker formats are consistent per exchange."""
        for bank in BANKS:
            ticker = bank.yf_ticker
            if bank.region == "US":
                # US tickers are simple symbols
                assert not any(c in ticker for c in [".", "="])
            elif bank.region == "CN":
                # Chinese tickers have .HK suffix
                assert ".HK" in ticker or ".SS" in ticker
            elif bank.region == "GB":
                # UK tickers have .L suffix
                assert ".L" in ticker
            elif bank.region == "EU":
                # EU tickers have various suffixes (.PA, .DE, .SW, .AS, .MC, .MI)
                assert any(suffix in ticker for suffix in [".PA", ".DE", ".SW", ".AS", ".MC", ".MI"])
            elif bank.region == "JP":
                # Japanese tickers have .T suffix
                assert ".T" in ticker
