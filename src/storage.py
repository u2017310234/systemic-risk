"""Immutable publication batches. current.json is the sole atomic commit point."""
import json
import re
from pathlib import Path

def active_root(root: Path) -> Path:
    pointer = root / 'current.json'
    if not pointer.exists():
        return root
    name = json.loads(pointer.read_text())['run']
    if not re.fullmatch(r'[A-Za-z0-9_-]+', name):
        raise ValueError('Invalid publication run')
    result = root / 'runs' / name
    result.resolve().relative_to(root.resolve())
    if not (result / 'latest.json').is_file():
        raise ValueError('Incomplete publication run')
    return result
