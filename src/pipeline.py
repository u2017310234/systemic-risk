"""
pipeline.py — Orchestrates daily data → metrics → publish cycle

Usage:
    python src/pipeline.py                        # today
    python src/pipeline.py --date 2024-01-15      # specific date
    python src/pipeline.py --start 2020-01-01 --end 2024-12-31  # range (backfill)
    python src/pipeline.py --banks JPM,HSBC       # subset
"""

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# Ensure src/ is importable when called as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import cfg
from src.operational import DataUnavailable, PublicationRejected
from src.universe import BANKS, BANK_BY_ID, UNIVERSE_MEMBERSHIP_AVAILABLE_FROM, universe_evidence
from src.fetcher import fetch_prices, fetch_market_cap_series, fetch_debt_series, MCAP_UPPER_BOUND_USD_BN
from src.metrics.mes import calc_lrmes_rolling, calc_mes_rolling
from src.metrics.covar import calc_covar_rolling
from src.metrics.srisk import calc_srisk_series, calc_srisk_shares, system_srisk
from src.publish import publish_snapshot, publish_bank_csv, publish_latest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pipeline")


def run_pipeline(target_date: date, start_date: date, bank_ids: list[str] | None = None) -> None:
    """Stage and validate a complete batch before atomically switching readers.

    Local publisher lock prevents concurrent writers from losing corrections.
    Legacy v1 files are not copied into the repaired v2 series.
    """
    if cfg.fundamentals_policy not in {"verified", "yahoo_daily"}:
        raise ValueError("Unknown FUNDAMENTALS_POLICY")
    if cfg.fundamentals_policy == "yahoo_daily" and (cfg.publication_mode == "historical" or cfg.dataset_kind == "historical_reconstruction" or target_date != date.today()):
        raise ValueError("yahoo_daily is for today's research run only; historical runs require verified inputs")
    universe_evidence(target_date.isoformat())
    import json, shutil, uuid, fcntl
    from src.storage import active_root
    from src.publish import _write_json, calibration_id
    root = Path(cfg.data_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if start_date > target_date:
        raise ValueError("start_date exceeds target_date")
    with open(root / ".publish.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        name = uuid.uuid4().hex
        staged = root / "runs" / name
        staged.mkdir(parents=True)
        previous = active_root(root)
        if bank_ids and previous != root:
            raise ValueError("Subset runs require a separate DATA_DIR; cannot overwrite an existing full publication")
        if previous != root:
            previous_payload = json.loads((previous / "latest.json").read_text())
            # Explicit demo-to-live bootstrap: never copy demo records into a new calibration.
            if previous.name == "demo-v23" and (previous / "DEMO.txt").exists() and previous_payload.get("dataset_kind") == "historical_reconstruction" and cfg.dataset_kind == "research_estimate":
                previous = root
        if previous != root:
            if json.loads((previous / "latest.json").read_text()).get("calibration_id") != calibration_id():
                raise ValueError("Calibration changed; use a separate DATA_DIR and full recomputation")
            shutil.copytree(previous, staged, dirs_exist_ok=True)
        old_dir = cfg.data_dir
        try:
            cfg.data_dir = str(staged)
            observations = _compute_and_publish(target_date, start_date, bank_ids)
            latest_path = staged / "latest.json"
            if not latest_path.exists():
                raise RuntimeError("Batch has no latest snapshot")
            latest = json.loads(latest_path.read_text())
            if previous != root:
                old_latest = json.loads((previous / "latest.json").read_text())
                if old_latest["date"] > latest["date"]:
                    _write_json(old_latest, latest_path)
            # Compare with the previous committed run; don't confuse liveness with data quality.
            from src.quality import assess_quality
            selected = json.loads(latest_path.read_text())
            prior = json.loads((previous / "latest.json").read_text()) if previous != root else None
            selected["quality"] = assess_quality(selected, prior, today=(date.today() if cfg.publication_mode == "production" else date.fromisoformat(selected["date"])))
            from src.calendar_status import publication_report
            report = publication_report(selected, observations or {}, target_date.isoformat())
            report["run"] = name
            selected["publication"] = report
            _write_json(report, root / "last-attempt.json")
            if report["decision"] == "rejected":
                raise PublicationRejected("Publication rejected: " + ", ".join(report["reasons"]))
            _write_json(selected, latest_path)
            _write_json(selected["quality"], staged / "quality-report.json")
            # Verify JSON/CSV for every regenerated snapshot before commit.
            validate_batch(staged)
            _write_json({"run": name, "methodology_version": "2.0-beta-scenario"}, root / "current.json")
        except Exception as exc:
            attempt_path = root / "last-attempt.json"
            report = json.loads(attempt_path.read_text()) if attempt_path.exists() else {}
            if report.get("decision") != "rejected" or report.get("run") != name:
                report = {"decision":"rejected", "mode":cfg.publication_mode,
                          "target_date":target_date.isoformat(), "run":name,
                          "error":f"{type(exc).__name__}: {exc}"}
            _write_json(report, attempt_path)
            raise
        finally:
            cfg.data_dir = old_dir
        # Failed staging directories stay unreferenced for diagnosis; readers never see them.


def validate_batch(root: Path):
    import json
    csvs = {}
    for path in (root / "history").glob("*.json"):
        payload = json.loads(path.read_text())
        for bank in payload["banks"]:
            bid = bank["bank_id"]
            if bid not in csvs:
                csvs[bid] = pd.read_csv(root / "banks" / f"{bid}.csv").set_index("date")
            rows = csvs[bid]
            if payload["date"] not in rows.index:
                raise ValueError(f"Missing CSV date: {bid} {payload['date']}")
            for field in ["srisk_usd_bn", "srisk_share_pct", "market_cap_usd_bn", "debt_usd_bn", "mes", "lrmes", "covar", "delta_covar"]:
                expected, actual = bank.get(field), rows.loc[payload["date"], field]
                if expected is None:
                    if pd.notna(actual): raise ValueError(f"CSV/JSON null mismatch: {bid}/{field}")
                elif not np.isclose(expected, actual, rtol=1e-9, atol=1e-9):
                    raise ValueError(f"CSV/JSON mismatch: {bid}/{field}")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def _compute_and_publish(
    target_date: date,
    start_date: date,
    bank_ids: list[str] | None = None,
) -> None:
    """
    Run the full pipeline for a given date range and publish results.
    target_date is the final date whose snapshot gets written to data/latest.json.
    """
    banks = BANKS if not bank_ids else [BANK_BY_ID[i.upper()] for i in bank_ids]
    start_str = start_date.isoformat()
    end_str = target_date.isoformat()

    logger.info(f"Pipeline start: {start_str} → {end_str}, {len(banks)} banks")

    all_results: dict[str, dict] = {}  # bank_id → {date → metrics}
    failed_banks: list[str] = []
    failures: dict[str, str] = {}

    for bank in banks:
        if not bank.supported:
            failed_banks.append(bank.id)
            continue
        logger.info(f"Processing {bank.id} ({bank.name})")
        try:
            bank_data = process_bank(bank, start_str, end_str)
            if bank_data is not None:
                if cfg.fundamentals_policy == "yahoo_daily" and bank_data:
                    latest_bank_day = max(bank_data)
                    bank_data = {latest_bank_day:bank_data[latest_bank_day]}
                all_results[bank.id] = {d:m for d,m in bank_data.items() if d >= UNIVERSE_MEMBERSHIP_AVAILABLE_FROM}
                logger.info(f"  ✓ {bank.id} completed")
            else:
                failed_banks.append(bank.id)
        except Exception as e:
            failed_banks.append(bank.id)
            failures[bank.id] = f"{type(e).__name__}: {e}"
            logger.error(f"  ✗ {bank.id} failed: {e}", exc_info=True)

    # Publish daily snapshots
    if not all_results:
        # Unexpected per-bank exceptions remain hard failures; only a normal
        # absence of provider data is an operational skip.
        error_type = RuntimeError if failures else DataUnavailable
        raise error_type(
            f"Pipeline produced no data: all {len(banks)} banks failed "
            f"({', '.join(failed_banks)})"
        )

    snapshot_dates = sorted(
        set().union(*[set(v.keys()) for v in all_results.values()])
    )
    for snap_date in snapshot_dates:
        day_data = {
            bid: metrics[snap_date]
            for bid, metrics in all_results.items()
            if snap_date in metrics
        }
        if day_data:
            if cfg.fundamentals_policy == "yahoo_daily":
                import json
                existing = Path(cfg.data_dir) / "history" / f"{snap_date}.json"
                if existing.exists():
                    prior_records = {b['bank_id']:b for b in json.loads(existing.read_text())['banks']}
                    prior_records.update(day_data)
                    day_data = prior_records
            # Add SRISK shares for the day
            srisk_vals = {bid: day_data[bid].get("srisk_usd_bn", float("nan"))
                          for bid in day_data}
            shares = calc_srisk_shares(srisk_vals)
            sys_srisk = system_srisk(srisk_vals)
            for bid in day_data:
                day_data[bid]["srisk_share_pct"] = shares.get(bid)
            publish_snapshot(snap_date, day_data, sys_srisk)
            if cfg.fundamentals_policy == "yahoo_daily":
                for bid, metrics in day_data.items():
                    publish_bank_csv(BANK_BY_ID[bid], {snap_date:metrics})

    # Update latest.json from target_date. If today's prices are not published
    # yet (yfinance `end` is exclusive, so data only reaches the prior trading
    # day), fall back to the newest available date so latest.json is ALWAYS
    # written — the MCP server and the dashboard both need it.
    target_str = target_date.isoformat()
    if not any(target_str in metrics for metrics in all_results.values()):
        available = sorted(
            {d for metrics in all_results.values() for d in metrics}
        )
        if available:
            logger.warning(
                f"No data for target {target_str}; "
                f"using newest available date {available[-1]} for latest.json"
            )
            target_str = available[-1]
    latest_data = {
        bid: metrics.get(target_str, {})
        for bid, metrics in all_results.items()
        if target_str in metrics
    }
    if latest_data:
        if cfg.fundamentals_policy == "yahoo_daily":
            import json
            latest_data = {b['bank_id']:b for b in json.loads((Path(cfg.data_dir)/"history"/f"{target_str}.json").read_text())['banks']}
        srisk_vals = {bid: v.get("srisk_usd_bn", float("nan"))
                      for bid, v in latest_data.items()}
        shares = calc_srisk_shares(srisk_vals)
        sys_srisk = system_srisk(srisk_vals)
        for bid in latest_data:
            latest_data[bid]["srisk_share_pct"] = shares.get(bid)
        publish_latest(date.fromisoformat(target_str), latest_data, sys_srisk)
        logger.info(f"Published latest.json for {target_str}")

    # Shares are now present in the same canonical records used for JSON.
    for bank in banks:
        if bank.id in all_results:
            publish_bank_csv(bank, all_results[bank.id])
    logger.info("Pipeline complete.")
    return {bank.id: {"srisk_date": max((d for d,m in all_results.get(bank.id, {}).items() if m.get("srisk_usd_bn") is not None), default=None),
                      "metric_dates": {metric: max((d for d,m in all_results.get(bank.id, {}).items() if m.get(metric) is not None), default=None)
                                       for metric in ("mes", "lrmes", "covar", "delta_covar", "srisk_usd_bn")},
                      "failure": failures.get(bank.id)} for bank in banks}


def process_bank(bank, start_str: str, end_str: str) -> dict | None:
    """
    Full processing for one bank: fetch data → compute metrics → return dict.

    Returns:
        dict mapping date strings to metric dicts, or None on fatal error.
    """
    if not bank.supported:
        return None
    # ----- Price returns -----
    prices = fetch_prices(bank.yf_ticker, start_str, end_str, bank.ak_ticker)
    if prices.empty or len(prices) < cfg.covar_window + 10:
        logger.warning(f"  Insufficient price data for {bank.id}")
        return None

    index_prices = fetch_prices(bank.index_yf, start_str, end_str)
    if index_prices.empty:
        logger.warning(f"  Missing index data {bank.index_yf} for {bank.id}")
        return None

    if cfg.fundamentals_policy == "yahoo_daily":
        from src.yahoo_daily import current_session
        due = current_session(bank, end_str)
        if not due: return None
        prices = prices.loc[:due]
        index_prices = index_prices.loc[:due]
    # Join closing dates first so returns cover identical calendar intervals.
    paired_prices = pd.concat([prices.rename("bank"), index_prices.rename("index")], axis=1).dropna().sort_index()
    paired_prices = paired_prices.where(paired_prices > 0).dropna()
    paired_returns = np.log(paired_prices / paired_prices.shift(1)).replace([np.inf, -np.inf], np.nan).dropna()
    bank_rets, index_rets = paired_returns["bank"], paired_returns["index"]

    # ----- Market cap & debt -----
    input_errors = []
    def optional_input(fetch, label):
        try:
            return fetch(bank, start_str, end_str)
        except Exception as exc:
            input_errors.append(f"{label}: {type(exc).__name__}: {exc}")
            logger.warning("%s %s unavailable: %s", bank.id, label, exc)
            return pd.Series(dtype=float)
    mcap = optional_input(fetch_market_cap_series, "market_cap")
    debt = optional_input(fetch_debt_series, "liabilities")

    # ----- Data quality warnings -----
    warnings_list: list[str] = list(input_errors)
    if prices.attrs.get("quality"):
        warnings_list.append(prices.attrs["quality"])
    if prices.attrs.get("currency_override"):
        warnings_list.append("CURRENCY_METADATA_CONFLICT: explicit sourced currency override applied")
    if mcap.empty:
        warnings_list.append("market_cap_unavailable_or_unverified_group_scope")
    if debt.empty:
        warnings_list.append("publication_dated_liabilities_required")
    if mcap.attrs.get("quality"):
        warnings_list.append(mcap.attrs["quality"])
    if debt.attrs.get("quality"):
        warnings_list.append(debt.attrs["quality"])
    if not mcap.empty:
        median_mcap = float(mcap.median())
        if not np.isnan(median_mcap) and median_mcap > MCAP_UPPER_BOUND_USD_BN:
            warnings_list.append(
                f"market_cap_usd_bn ({median_mcap:.1f}) exceeds "
                f"{MCAP_UPPER_BOUND_USD_BN} USD bn — possible shares/FX unit error"
            )
    if not debt.empty:
        median_debt = float(debt.median())
        if not np.isnan(median_debt) and median_debt <= 0:
            warnings_list.append("debt_usd_bn is non-positive — check balance sheet data")

    # ----- Rolling metrics -----
    window = cfg.covar_window

    mes_series = calc_mes_rolling(bank_rets, index_rets, window=window)
    lrmes_series = calc_lrmes_rolling(bank_rets, index_rets, window=window)
    covar_df = calc_covar_rolling(bank_rets, index_rets, window=window)

    # ----- Rolling SRISK (requires aligned mcap, debt, lrmes) -----
    srisk_series = pd.Series(dtype=float)
    if not mcap.empty and not debt.empty and not lrmes_series.empty:
        srisk_series = calc_srisk_series(mcap, debt, lrmes_series)

    # ----- Assemble per-date records -----
    # Common date index = all dates where lrmes is available
    all_dates = lrmes_series.index if not lrmes_series.empty else mes_series.index

    result: dict[str, dict] = {}
    for dt in all_dates:
        dt_str = dt.strftime("%Y-%m-%d")
        covar_row = covar_df.loc[dt] if dt in covar_df.index else None

        record = {
            "bank_id": bank.id,
            "bank_name": bank.name,
            "region": bank.region,
            "covar_index": bank.index_yf,
            "security_ticker": bank.yf_ticker,
            "accounting_standard": debt.attrs.get("accounting_standard", "unspecified"),
            "market_cap_evidence": mcap.attrs.get("selected_sources", {}).get(dt_str),
            "liabilities_evidence": debt.attrs.get("selected_sources", {}).get(dt_str),
            "fundamentals_input_sha256": debt.attrs.get("input_sha256") or mcap.attrs.get("input_sha256"),
            "methodology_version": "2.0-beta-scenario",
            "fundamentals_quality": {"market_cap": mcap.attrs.get("quality", "unavailable"), "liabilities": debt.attrs.get("quality", "unavailable")},
            "mes": _safe_float(mes_series.get(dt)),
            "lrmes": _safe_float(lrmes_series.get(dt)),
            "covar": _safe_float(covar_row["covar"] if covar_row is not None else None),
            "delta_covar": _safe_float(covar_row["delta_covar"] if covar_row is not None else None),
            "covar_beta": _safe_float(covar_row["beta"] if covar_row is not None else None),
            "srisk_usd_bn": _safe_float(srisk_series.get(dt) if not srisk_series.empty else None),
            "market_cap_usd_bn": _safe_float(mcap.get(dt) if not mcap.empty else None),
            "debt_usd_bn": _safe_float(debt.get(dt) if not debt.empty else None),
        }
        if warnings_list:
            record["data_quality_warnings"] = list(warnings_list)
        result[dt_str] = record

    return result if result else None


def _safe_float(val) -> float | None:
    try:
        f = float(val)
        return None if not np.isfinite(f) else round(f, 6)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="G-SIBs Systemic Risk Pipeline")
    parser.add_argument("--date", default=None,
                        help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--start", default=None,
                        help="Start date for historical range YYYY-MM-DD")
    parser.add_argument("--end", default=None,
                        help="End date for historical range YYYY-MM-DD (default: today)")
    parser.add_argument("--banks", default=None,
                        help="Comma-separated bank IDs to process (default: all)")
    parser.add_argument("--mode", choices=["research", "historical", "production"], default=cfg.publication_mode)
    args = parser.parse_args()
    cfg.publication_mode = args.mode
    if args.mode == "historical": cfg.dataset_kind = "historical_reconstruction"

    today = date.today()

    if args.date:
        target = date.fromisoformat(args.date)
    elif args.end:
        target = date.fromisoformat(args.end)
    else:
        target = today

    if args.start:
        start = date.fromisoformat(args.start)
    else:
        # Default: convert covar_window (trading days) to calendar days (~7/5 ratio)
        # and add a 30-day holiday/buffer, so we always have enough trading days.
        start = target - timedelta(days=int(cfg.covar_window * 1.5) + 30)

    bank_ids = [b.strip().upper() for b in args.banks.split(",")] if args.banks else None

    try:
        run_pipeline(target_date=target, start_date=start, bank_ids=bank_ids)
    except RuntimeError as e:
        logger.error(f"Pipeline failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
