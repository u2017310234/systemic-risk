"""
branch_locator.py - Build and refresh a single-file G-SIB branch cache.

This module keeps `loc/gsib_branches.json` as a read-optimized cache while
refreshing branch candidates in the background from low-friction public data
sources. The current implementation uses OpenStreetMap Nominatim as a dynamic
source and preserves manual seed branches already present in the dataset.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx


DATASET_PATH = Path(__file__).resolve().parent / "gsib_branches.json"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "systemic-risk-loc-maintainer/1.0"


BANK_SEARCH_CONFIG: dict[str, dict[str, Any]] = {
    "ABC": {"search_name": "Agricultural Bank of China", "match_terms": ["agricultural bank of china", "zhong guo nong ye yin hang", "中国农业银行"]},
    "ACA": {"search_name": "Credit Agricole", "match_terms": ["credit agricole"]},
    "BAC": {"search_name": "Bank of America", "match_terms": ["bank of america"]},
    "BARC": {"search_name": "Barclays", "match_terms": ["barclays"]},
    "BK": {"search_name": "BNY Mellon", "match_terms": ["bny mellon", "bank of new york mellon"]},
    "BNP": {"search_name": "BNP Paribas", "match_terms": ["bnp paribas"]},
    "BOC": {"search_name": "Bank of China", "match_terms": ["bank of china", "中国银行"]},
    "BOCOM": {"search_name": "Bank of Communications", "match_terms": ["bank of communications", "交通银行"]},
    "BPCE": {"search_name": "BPCE", "match_terms": ["bpce"]},
    "C": {"search_name": "Citigroup", "match_terms": ["citigroup", "citi"]},
    "CCB": {"search_name": "China Construction Bank", "match_terms": ["china construction bank", "中国建设银行"]},
    "DBK": {"search_name": "Deutsche Bank", "match_terms": ["deutsche bank"]},
    "GLE": {"search_name": "Societe Generale", "match_terms": ["societe generale"]},
    "GS": {"search_name": "Goldman Sachs", "match_terms": ["goldman sachs"]},
    "HSBC": {"search_name": "HSBC", "match_terms": ["hsbc"]},
    "ICBC": {"search_name": "Industrial and Commercial Bank of China", "match_terms": ["industrial and commercial bank of china", "中国工商银行", "icbc"]},
    "ING": {"search_name": "ING", "match_terms": ["ing"]},
    "JPM": {"search_name": "JPMorgan Chase", "match_terms": ["jpmorgan chase", "jpmorgan"]},
    "MFG": {"search_name": "Mizuho", "match_terms": ["mizuho"]},
    "MS": {"search_name": "Morgan Stanley", "match_terms": ["morgan stanley"]},
    "MUFG": {"search_name": "MUFG", "match_terms": ["mufg", "mitsubishi ufj"]},
    "RBC": {"search_name": "Royal Bank of Canada", "match_terms": ["royal bank of canada", "rbc"]},
    "SAN": {"search_name": "Banco Santander", "match_terms": ["banco santander", "santander"]},
    "SMFG": {"search_name": "SMBC", "match_terms": ["smbc", "sumitomo mitsui"]},
    "STAN": {"search_name": "Standard Chartered", "match_terms": ["standard chartered"]},
    "STT": {"search_name": "State Street", "match_terms": ["state street"]},
    "TD": {"search_name": "TD Bank", "match_terms": ["td bank", "toronto dominion", "toronto-dominion"]},
    "UBS": {"search_name": "UBS", "match_terms": ["ubs"]},
    "WFC": {"search_name": "Wells Fargo", "match_terms": ["wells fargo"]},
}


EXTRA_CITY_QUERIES: dict[str, list[str]] = {
    "HSBC": ["Hong Kong"],
    "JPM": ["London"],
    "BARC": ["Canary Wharf London"],
    "C": ["New York"],
    "UBS": ["Zurich"],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_text(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    lowered = ascii_value.lower()
    return re.sub(r"[^a-z0-9]+", " ", lowered).strip()


def slugify(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "-", normalize_text(value).upper()).strip("-")


def load_dataset(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_dataset(path: Path, payload: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def should_refresh(bank: dict[str, Any], ttl_hours: int, force: bool) -> bool:
    if force:
        return True
    maintenance = bank.get("maintenance", {})
    last_refreshed = maintenance.get("last_refreshed_at")
    if not last_refreshed:
        return True
    try:
        refreshed_at = datetime.fromisoformat(last_refreshed.replace("Z", "+00:00"))
    except ValueError:
        return True
    return datetime.now(timezone.utc) - refreshed_at >= timedelta(hours=ttl_hours)


def get_seed_city(bank: dict[str, Any]) -> str:
    branches = bank.get("branches", [])
    if branches:
        city = branches[0].get("city")
        if city:
            return city
    return bank.get("country", "")


def build_queries(bank: dict[str, Any]) -> list[str]:
    bank_id = bank["bank_id"]
    config = BANK_SEARCH_CONFIG.get(bank_id, {})
    search_name = config.get("search_name", bank["bank_name"])
    queries = [f"{search_name} {get_seed_city(bank)}".strip()]
    for extra_city in EXTRA_CITY_QUERIES.get(bank_id, []):
        queries.append(f"{search_name} {extra_city}".strip())
    return list(dict.fromkeys(queries))


def matches_bank(bank_id: str, candidate: dict[str, Any]) -> bool:
    config = BANK_SEARCH_CONFIG.get(bank_id, {})
    haystack = " ".join(
        [
            candidate.get("name", ""),
            candidate.get("display_name", ""),
            json.dumps(candidate.get("namedetails", {}), ensure_ascii=False),
            json.dumps(candidate.get("address", {}), ensure_ascii=False),
        ]
    )
    normalized = normalize_text(haystack)
    return any(normalize_text(term) in normalized for term in config.get("match_terms", []))


def score_branch(bank: dict[str, Any], branch: dict[str, Any]) -> dict[str, Any]:
    bank_id = bank["bank_id"]
    source = branch.get("source", {})
    reasons: list[str] = []
    score = 0

    if source.get("name") == "seed_manual":
        score += 45
        reasons.append("manual_seed_location")
    elif source.get("name") == "osm_nominatim":
        score += 25
        reasons.append("osm_source_match")

    haystack = " ".join(
        [
            branch.get("name") or "",
            branch.get("display_name") or "",
            json.dumps(branch.get("address") or {}, ensure_ascii=False),
        ]
    )
    normalized = normalize_text(haystack)
    match_terms = [normalize_text(term) for term in BANK_SEARCH_CONFIG.get(bank_id, {}).get("match_terms", [])]
    if any(term in normalized for term in match_terms):
        score += 25
        reasons.append("bank_name_alias_match")

    if branch.get("lat") is not None and branch.get("lon") is not None:
        score += 10
        reasons.append("has_coordinates")

    if branch.get("city"):
        score += 10
        reasons.append("has_city")

    if branch.get("country"):
        score += 10
        reasons.append("has_country")

    if branch.get("address"):
        score += 10
        reasons.append("has_structured_address")

    if source.get("osm_id") is not None:
        score += 10
        reasons.append("has_source_entity_id")

    if branch.get("type") == "head_office":
        score += 5
        reasons.append("head_office_seed")

    score = max(0, min(score, 100))
    if score >= 85:
        status = "cross_source_verified"
    elif score >= 60:
        status = "candidate_verified"
    else:
        status = "seed_unverified"

    branch["verification"] = {
        "verification_status": status,
        "confidence_score": score,
        "verification_reasons": reasons,
        "verified_at": now_iso(),
        "verified_by": "loc.branch_locator.rule_engine.v1",
    }
    return branch


def search_nominatim(client: httpx.Client, query: str, limit: int) -> list[dict[str, Any]]:
    response = client.get(
        NOMINATIM_URL,
        params={
            "q": query,
            "format": "jsonv2",
            "limit": limit,
            "addressdetails": 1,
            "namedetails": 1,
            "dedupe": 1,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def convert_seed_branch(bank_id: str, branch: dict[str, Any]) -> dict[str, Any]:
    branch_id = branch.get("branch_id") or f"{bank_id}-{slugify(branch.get('name', 'BRANCH'))}"
    return {
        "branch_id": branch_id,
        "name": branch.get("name", "Head Office"),
        "type": branch.get("type", "branch"),
        "city": branch.get("city"),
        "country": branch.get("country"),
        "lat": branch.get("lat"),
        "lon": branch.get("lon"),
        "display_name": branch.get("display_name"),
        "address": branch.get("address"),
        "source": branch.get("source")
        or {
            "name": "seed_manual",
            "query": None,
            "osm_type": None,
            "osm_id": None,
            "license": None,
            "last_verified_at": now_iso(),
        },
        "verification": branch.get("verification"),
    }


def convert_nominatim_candidate(bank_id: str, query: str, candidate: dict[str, Any]) -> dict[str, Any]:
    address = candidate.get("address", {})
    city = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or address.get("county")
    )
    country = address.get("country")
    osm_type = candidate.get("osm_type")
    osm_id = candidate.get("osm_id")
    branch_id = f"{bank_id}-{slugify(f'{osm_type}-{osm_id}')}"
    return {
        "branch_id": branch_id,
        "name": candidate.get("name") or bank_id,
        "type": "branch",
        "city": city,
        "country": country,
        "lat": float(candidate["lat"]),
        "lon": float(candidate["lon"]),
        "display_name": candidate.get("display_name"),
        "address": address,
        "source": {
            "name": "osm_nominatim",
            "query": query,
            "osm_type": osm_type,
            "osm_id": osm_id,
            "category": candidate.get("category"),
            "place_type": candidate.get("type"),
            "importance": candidate.get("importance"),
            "license": candidate.get("licence"),
            "last_verified_at": now_iso(),
        },
        "verification": candidate.get("verification"),
    }


def dedupe_branches(branches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    unique: list[dict[str, Any]] = []
    for branch in branches:
        source = branch.get("source", {})
        key = (
            source.get("name"),
            source.get("osm_type"),
            source.get("osm_id"),
            branch.get("lat"),
            branch.get("lon"),
            branch.get("display_name"),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(branch)
    return unique


def refresh_bank(
    client: httpx.Client,
    bank: dict[str, Any],
    per_query_limit: int,
    max_branches: int,
    query_delay: float,
) -> dict[str, Any]:
    bank_id = bank["bank_id"]
    existing = [convert_seed_branch(bank_id, branch) for branch in bank.get("branches", [])]
    fetched: list[dict[str, Any]] = []
    queries = build_queries(bank)
    for query in queries:
        candidates = search_nominatim(client, query, per_query_limit)
        for candidate in candidates:
            if not matches_bank(bank_id, candidate):
                continue
            fetched.append(convert_nominatim_candidate(bank_id, query, candidate))
            if len(fetched) >= max_branches:
                break
        if len(fetched) >= max_branches:
            break
        time.sleep(query_delay)

    merged = dedupe_branches(existing + fetched)
    bank["branches"] = [score_branch(bank, branch) for branch in merged[:max_branches]]
    bank["maintenance"] = {
        "last_refreshed_at": now_iso(),
        "refresh_source": "osm_nominatim",
        "refresh_queries": queries,
        "ttl_hours": bank.get("maintenance", {}).get("ttl_hours", 24),
        "branch_count": len(bank["branches"]),
        "dynamic_ready": True,
        "cache_strategy": "stale-while-revalidate",
        "verification_engine": "rule_engine_v1",
    }
    return bank


def annotate_existing_branches(bank: dict[str, Any], max_branches: int) -> dict[str, Any]:
    normalized = [convert_seed_branch(bank["bank_id"], branch) for branch in bank.get("branches", [])]
    deduped = dedupe_branches(normalized)
    bank["branches"] = [score_branch(bank, branch) for branch in deduped[:max_branches]]
    return bank


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh G-SIB branch cache")
    parser.add_argument("--dataset", default=str(DATASET_PATH), help="Path to loc JSON dataset")
    parser.add_argument("--bank", action="append", dest="banks", help="Refresh only selected bank_id; repeatable")
    parser.add_argument("--force", action="store_true", help="Ignore TTL and refresh selected banks immediately")
    parser.add_argument("--ttl-hours", type=int, default=24, help="Skip banks refreshed more recently than this TTL")
    parser.add_argument("--per-query-limit", type=int, default=5, help="Max raw Nominatim hits per query")
    parser.add_argument("--max-branches", type=int, default=8, help="Max stored branches per bank")
    parser.add_argument("--query-delay", type=float, default=1.1, help="Delay between Nominatim queries in seconds")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset_path = Path(args.dataset).resolve()
    payload = load_dataset(dataset_path)
    selected_ids = {bank_id.upper() for bank_id in (args.banks or [])}

    payload["maintenance"] = {
        "mode": "dynamic_low_latency_cache",
        "reader_contract": "single_file_json",
        "writer_strategy": "background_refresh_with_stale_while_revalidate",
        "primary_source": "osm_nominatim",
        "preferred_future_source": "official_bank_locator_api",
        "generated_at": now_iso(),
    }

    with httpx.Client() as client:
        for bank in payload.get("banks", []):
            bank["maintenance"] = bank.get("maintenance", {})
            bank["maintenance"]["ttl_hours"] = args.ttl_hours
            annotate_existing_branches(bank, args.max_branches)
            if selected_ids and bank["bank_id"] not in selected_ids:
                continue
            if not should_refresh(bank, args.ttl_hours, args.force):
                continue
            try:
                refresh_bank(
                    client=client,
                    bank=bank,
                    per_query_limit=args.per_query_limit,
                    max_branches=args.max_branches,
                    query_delay=args.query_delay,
                )
            except Exception as exc:  # pragma: no cover - network failures are expected in practice
                bank["maintenance"].update(
                    {
                        "last_refresh_error": str(exc),
                        "last_refresh_attempt_at": now_iso(),
                        "dynamic_ready": True,
                        "cache_strategy": "stale-if-error",
                    }
                )

    payload["collected_at"] = now_iso().split("T", 1)[0]
    save_dataset(dataset_path, payload)


if __name__ == "__main__":
    main()
