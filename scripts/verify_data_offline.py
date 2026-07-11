#!/usr/bin/env python3
"""Offline check (stdlib only): proves the data the MCP relies on resolves.

Runs on any Python 3.x, needs no pip installs. It reproduces the MCP server's
'load latest snapshot + rank' selection against the committed data.
"""
import glob
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"


def load_latest():
    latest = DATA / "latest.json"
    if latest.exists():
        return "latest.json", json.load(open(latest, encoding="utf-8"))
    hist = sorted(glob.glob(str(DATA / "history" / "*.json")))
    if not hist:
        return None, None
    return os.path.basename(hist[-1]), json.load(open(hist[-1], encoding="utf-8"))


name, payload = load_latest()
assert payload is not None, "FAIL: no latest.json and no history snapshots found"
banks = payload.get("banks", [])
assert len(banks) >= 20, f"FAIL: snapshot {name} has only {len(banks)} banks"

ranked = sorted(
    [b for b in banks if b.get("srisk_usd_bn") is not None],
    key=lambda b: b["srisk_usd_bn"],
    reverse=True,
)
assert ranked, "FAIL: no srisk_usd_bn values to rank"

dranked = sorted(
    [b for b in banks if b.get("delta_covar") is not None],
    key=lambda b: b["delta_covar"],
)
assert dranked, "FAIL: no delta_covar values to rank"

print(f"OK  snapshot source       : {name}")
print(f"OK  banks in snapshot      : {len(banks)}")
print(f"OK  top SRISK bank         : {ranked[0]['bank_id']} = {ranked[0]['srisk_usd_bn']}")
print(f"OK  most systemic (dCoVaR) : {dranked[0]['bank_id']} = {dranked[0]['delta_covar']}")
print("\nOFFLINE DATA CHECK PASSED.")
