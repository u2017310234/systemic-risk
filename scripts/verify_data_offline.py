#!/usr/bin/env python3
"""Verify the committed run, including cross-format numeric consistency."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import cfg
from src.storage import active_root
from src.pipeline import validate_batch
root = active_root(Path(cfg.data_dir))
payload = json.loads((root / "latest.json").read_text())
assert payload["methodology_version"] == "2.0-beta-scenario", "Recompute legacy data first"
validate_batch(root)
print(json.dumps({"date":payload["date"], "coverage":payload["coverage"], "status":"consistent"}))
