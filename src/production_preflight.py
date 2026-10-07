"""Fast, explicit prerequisite check. Passing this does not certify input quality."""
from pathlib import Path
from src.config import cfg


def main():
    root = Path(cfg.fundamentals_dir)
    files = list(root.glob('*.json')) if root.is_dir() else []
    if not files:
        raise SystemExit('Production inputs missing: add verified dated bank JSON files under '
                         f'{root}. See inputs/fundamentals.example.json and docs/REPAIR.md. '
                         'Historical demo data is not a production input source.')
    if cfg.market_inputs_dir and not Path(cfg.market_inputs_dir).is_dir():
        raise SystemExit('MARKET_INPUTS_DIR is configured but missing')
    print(f'Found {len(files)} fundamentals files; freshness and coverage are checked by the pipeline.')


if __name__ == '__main__':
    main()
