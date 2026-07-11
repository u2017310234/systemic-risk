#!/usr/bin/env python3
"""Full check: imports the real MCP tool functions and calls them.

Prerequisites: Python 3.11+, and `pip install -r requirements.txt`.
Run from anywhere:  python scripts/verify_mcp.py
"""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# config reads DATA_DIR from the environment AT IMPORT TIME, so set it first.
os.environ["DATA_DIR"] = str(REPO / "data")

# Import the repo's mcp/server.py as the top-level module `server`, while keeping
# the pip-installed `mcp` SDK importable. We put ONLY <repo>/mcp on sys.path so
# that `import mcp` inside server.py resolves to the pip SDK, not the repo folder.
sys.path.insert(0, str(REPO / "mcp"))
import server  # noqa: E402  (this is repo/mcp/server.py)


def ok(name, res):
    assert isinstance(res, dict) and "error" not in res, f"FAIL {name}: {res}"
    print(f"OK  {name}")


r = server.get_latest_metrics()
ok("get_latest_metrics()", r)
print("    banks:", len(r.get("banks", [])))

ok("get_srisk_ranking(top_n=5)", server.get_srisk_ranking(top_n=5))
ok("get_delta_covar_ranking(top_n=5)", server.get_delta_covar_ranking(top_n=5))
ok("get_historical(bank_id='JPM')", server.get_historical(bank_id="JPM"))
ok("get_methodology()", server.get_methodology())

# Security regression: a traversal date must be rejected, not read a file.
bad = server.get_srisk_ranking(date="../../../../etc/hostname")
assert "error" in bad, f"FAIL: path traversal not blocked: {bad}"
print("OK  path-traversal date rejected")

print("\nMCP TOOL CHECK PASSED — the server's tools return data.")
