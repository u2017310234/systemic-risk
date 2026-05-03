"""Tests for branch cache helper behavior."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loc.branch_locator import annotate_existing_branches, dedupe_branches, matches_bank, normalize_text, score_branch


def test_normalize_text_strips_accents():
    assert normalize_text("Societe Generale") == normalize_text("Société Générale")


def test_matches_bank_uses_aliases():
    candidate = {
        "name": "JPMorgan Chase & Co",
        "display_name": "JPMorgan Chase & Co, New York, United States",
        "namedetails": {},
        "address": {"country": "United States"},
    }
    assert matches_bank("JPM", candidate) is True


def test_dedupe_branches_collapses_same_osm_entity():
    branch = {
        "branch_id": "HSBC-NODE-1",
        "name": "HSBC",
        "lat": 1.0,
        "lon": 2.0,
        "display_name": "HSBC London",
        "source": {"name": "osm_nominatim", "osm_type": "node", "osm_id": 1},
    }
    assert len(dedupe_branches([branch, dict(branch)])) == 1


def test_score_branch_sets_candidate_status():
    bank = {"bank_id": "JPM", "bank_name": "JP Morgan Chase"}
    branch = {
        "name": "JPMorgan Chase & Co",
        "display_name": "JPMorgan Chase & Co, New York, United States",
        "city": "New York",
        "country": "United States",
        "lat": 1.0,
        "lon": 2.0,
        "address": {"country": "United States"},
        "type": "branch",
        "source": {"name": "osm_nominatim", "osm_id": 1},
    }
    scored = score_branch(bank, branch)
    assert scored["verification"]["verification_status"] == "cross_source_verified"
    assert scored["verification"]["confidence_score"] >= 85


def test_annotate_existing_branches_marks_seed():
    bank = {
        "bank_id": "HSBC",
        "bank_name": "HSBC",
        "branches": [
            {
                "branch_id": "HSBC-HQ-LONDON",
                "name": "Head Office",
                "type": "head_office",
                "city": "London",
                "country": "United Kingdom",
                "lat": 1.0,
                "lon": 2.0,
                "source": {"name": "seed_manual"},
            }
        ],
    }
    annotated = annotate_existing_branches(bank, 5)
    assert annotated["branches"][0]["verification"]["verification_status"] == "candidate_verified"
