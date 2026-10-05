"""
universe.py — Global Systemically Important Banks (G-SIBs) Registry

Source: frozen FSB 2023 membership, cross-checked against 2024 and 2025 lists.
Membership is not silently updated; a new set requires a new universe version.
Each bank entry contains:
    - id         : short key used in filenames and API responses
    - name       : full name
    - region     : one of US / CN / GB / EU / JP
    - yf_ticker  : Yahoo Finance ticker (primary price source)
    - ak_ticker  : AkShare ticker (A-share fallback for CN banks, None otherwise)
    - index_yf   : Yahoo Finance ticker of the regional market index used as
                   the "system" return in CoVaR / ΔCoVaR calculations.
                   Documented here for full transparency.

CoVaR Index Rationale (documented per region):
    US  → ^GSPC  (S&P 500)        — primary domestic systemic benchmark
    CN  → 000300.SS (CSI 300)     — for A-share pricing / domestic risk
          ^HSI    (Hang Seng)     — for H-share pricing
          (each CN bank gets the index matching its primary listing)
    GB  → ^FTSE  (FTSE 100)       — post-Brexit separate benchmark from EU
    EU  → ^STOXX50E (EURO STOXX 50) — eurozone systemic reference
    JP  → ^N225  (Nikkei 225)     — domestic systemic reference
"""

from typing import Optional
from dataclasses import dataclass, field


@dataclass
class Bank:
    id: str
    name: str
    region: str          # US | CN | GB | EU | JP | CA
    yf_ticker: str       # Yahoo Finance ticker
    index_yf: str        # Regional index ticker for CoVaR
    ak_ticker: Optional[str] = None  # AkShare code (CN A-share only)
    quote_currency: str = "USD"
    reporting_currency: str = "USD"
    supported: bool = True
    market_cap_policy: str = "dated_shares"
    equity_share_classes: tuple[str, ...] = ("ordinary",)
    exclusion_reason: str = "unlisted_without_own_equity_data"
    listing: str = "equity"          # equity | adr


# ---------------------------------------------------------------------------
# G-SIBs — FSB 2023 list (29 institutions; Credit Suisse absorbed by UBS)
# ---------------------------------------------------------------------------
BANKS: list[Bank] = [
    # ── United States ────────────────────────────────────────────────────
    Bank("JPM",   "JPMorgan Chase",          "US", "JPM",      "^GSPC"),
    Bank("BAC",   "Bank of America",          "US", "BAC",      "^GSPC"),
    Bank("C",     "Citigroup",                "US", "C",        "^GSPC"),
    Bank("WFC",   "Wells Fargo",              "US", "WFC",      "^GSPC"),
    Bank("GS",    "Goldman Sachs",            "US", "GS",       "^GSPC"),
    Bank("MS",    "Morgan Stanley",           "US", "MS",       "^GSPC"),
    Bank("BK",    "Bank of New York Mellon",  "US", "BK",       "^GSPC"),
    Bank("STT",   "State Street",             "US", "STT",      "^GSPC"),

    # ── China ────────────────────────────────────────────────────────────
    # H-share returns; A/H components separately valued for group market cap.
    # A-share codes are metadata only, never silent price substitutes.
    # CoVaR index = CSI 300 for A-share, HSI for H-share primary listing.
    Bank("ICBC",  "Industrial & Commercial Bank of China", "CN",
         "1398.HK", "^HSI", ak_ticker="601398"),
    Bank("CCB",   "China Construction Bank",               "CN",
         "0939.HK", "^HSI", ak_ticker="601939"),
    Bank("ABC",   "Agricultural Bank of China",            "CN",
         "1288.HK", "^HSI", ak_ticker="601288"),
    Bank("BOC",   "Bank of China",                         "CN",
         "3988.HK", "^HSI", ak_ticker="601988"),
    Bank("BOCOM", "Bank of Communications",                "CN",
         "3328.HK", "^HSI", ak_ticker="601328"),

    # ── United Kingdom ───────────────────────────────────────────────────
    Bank("HSBC",  "HSBC Holdings",            "GB", "HSBA.L",   "^FTSE"),
    Bank("BARC",  "Barclays",                 "GB", "BARC.L",   "^FTSE"),
    Bank("STAN",  "Standard Chartered",       "GB", "STAN.L",   "^FTSE"),

    # ── France ───────────────────────────────────────────────────────────
    Bank("BNP",   "BNP Paribas",              "EU", "BNP.PA",   "^STOXX50E"),
    Bank("ACA",   "Groupe Crédit Agricole",   "EU", "", "^STOXX50E", supported=False,
         exclusion_reason="listed_subsidiary_not_consolidated_group_equity"),
    Bank("GLE",   "Société Générale",         "EU", "GLE.PA",   "^STOXX50E"),
    Bank("BPCE",  "Groupe BPCE",              "EU", "",   "^STOXX50E", supported=False),  # Unlisted: no substitute institution
    # ── Germany ──────────────────────────────────────────────────────────
    Bank("DBK",   "Deutsche Bank",            "EU", "DBK.DE",   "^STOXX50E"),
    # ── Switzerland ──────────────────────────────────────────────────────
    Bank("UBS",   "UBS Group",                "EU", "UBSG.SW",  "^STOXX50E"),
    # ── Netherlands ──────────────────────────────────────────────────────
    Bank("ING",   "ING Groep",                "EU", "INGA.AS",  "^STOXX50E"),
    # ── Spain ────────────────────────────────────────────────────────────
    Bank("SAN",   "Banco Santander",          "EU", "SAN.MC",   "^STOXX50E"),
    # ── Canada: ordinary Toronto shares, not duplicate US listings ────────
    Bank("RBC", "Royal Bank of Canada", "CA", "RY.TO", "^GSPTSE"),
    Bank("TD", "Toronto-Dominion Bank", "CA", "TD.TO", "^GSPTSE"),

    # ── Japan ────────────────────────────────────────────────────────────
    Bank("MUFG",  "Mitsubishi UFJ Financial", "JP", "8306.T",   "^N225"),
    Bank("SMFG",  "Sumitomo Mitsui Financial","JP", "8316.T",   "^N225"),
    Bank("MFG",   "Mizuho Financial Group",   "JP", "8411.T",   "^N225"),
]

# Explicit security/reporting currencies. Exchange suffix is not a reporting currency.
for bank in BANKS:
    if bank.region == "CN":
        bank.quote_currency, bank.reporting_currency = "HKD", "CNY"
        bank.equity_share_classes = ("A", "H")
        bank.market_cap_policy = "verified_input"  # A/H share classes need issuer-wide equity value
    elif bank.region == "JP":
        bank.quote_currency = bank.reporting_currency = "JPY"
    elif bank.region == "CA":
        bank.quote_currency = bank.reporting_currency = "CAD"
    elif bank.region == "GB":
        bank.quote_currency = "GBp"
        bank.reporting_currency = "GBP" if bank.id == "BARC" else "USD"
    elif bank.region == "EU":
        bank.quote_currency = "CHF" if bank.id == "UBS" else "EUR"
        bank.reporting_currency = "USD" if bank.id == "UBS" else "EUR"
    if bank.id == "ACA":
        bank.market_cap_policy = "verified_input"  # Listed subsidiary != whole G-SIB group

# This is a versioned research universe, not a claim to be today's FSB list.
UNIVERSE_VERSION = "fsb-2023-membership-verified-v2.2"
UNIVERSE_SOURCE = "https://www.fsb.org/uploads/P271123.pdf"
UNIVERSE_MEMBERSHIP_AVAILABLE_FROM = "2023-11-28"
UNIVERSE_CROSSCHECKS = ["https://www.fsb.org/uploads/P261124.pdf", "https://www.fsb.org/uploads/P271125.pdf"]

# Quick-lookup helpers
BANK_BY_ID: dict[str, Bank] = {b.id: b for b in BANKS}
REGIONS: list[str] = sorted(set(b.region for b in BANKS))

# All unique index tickers needed (deduplicated)
ALL_INDICES: list[str] = sorted(set(b.index_yf for b in BANKS))


def get_bank(bank_id: str) -> Bank:
    """Return Bank by id (case-insensitive). Raises KeyError if not found."""
    return BANK_BY_ID[bank_id.upper()]


def banks_by_region(region: str) -> list[Bank]:
    """Return all banks in a given region."""
    return [b for b in BANKS if b.region == region.upper()]

# Publication dates are daily conservative activation dates (publication + 1).
# All three releases have the same members; capital-buffer buckets are separate
# regulatory information and are NOT the k in our scenario calculation.
UNIVERSE_RELEASES = (
    ('2023-11-28', '2023', 'https://www.fsb.org/uploads/P271123.pdf'),
    ('2024-11-27', '2024', 'https://www.fsb.org/uploads/P261124.pdf'),
    ('2025-11-28', '2025', 'https://www.fsb.org/uploads/P271125.pdf'),
)


def universe_evidence(asof: str) -> dict:
    from datetime import date, timedelta
    date.fromisoformat(asof)
    usable = [r for r in UNIVERSE_RELEASES if r[0] <= asof]
    if not usable:
        raise ValueError('No verified universe membership for this historical date')
    available, year, source = usable[-1]
    return {'list_year':year, 'source':source, 'available_date':available,
            'published_date':(date.fromisoformat(available)-timedelta(days=1)).isoformat(),
            'membership_version':UNIVERSE_VERSION,
            'scope':'verified_membership_not_regulatory_capital_bucket_calibration'}
