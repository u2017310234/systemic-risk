"""
publish.py — Write computed metrics to JSON and CSV files

Output layout:
    data/
        latest.json                     ← latest full snapshot (all banks)
        history/YYYY-MM-DD.json         ← daily snapshot
        banks/{BANK_ID}.csv             ← per-bank time series
"""

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from src.config import cfg
from src.universe import Bank, BANKS, UNIVERSE_VERSION, UNIVERSE_SOURCE, UNIVERSE_MEMBERSHIP_AVAILABLE_FROM, universe_evidence
import math
import os
import tempfile

logger = logging.getLogger(__name__)


def _data_root() -> Path:
    root = Path(cfg.data_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def publish_latest(
    snapshot_date: date,
    bank_records: dict[str, dict],
    system_srisk_usd_bn: float,
) -> None:
    """Write data/latest.json with full snapshot for all banks."""
    payload = _build_payload(snapshot_date, bank_records, system_srisk_usd_bn)
    path = _data_root() / "latest.json"
    _write_json(payload, path)
    logger.info(f"Published {path}")


def publish_snapshot(
    snapshot_date: date | str,
    bank_records: dict[str, dict],
    system_srisk_usd_bn: float,
) -> None:
    """Write data/history/YYYY-MM-DD.json."""
    d = date.fromisoformat(str(snapshot_date)) if isinstance(snapshot_date, str) else snapshot_date
    payload = _build_payload(d, bank_records, system_srisk_usd_bn)
    path = _data_root() / "history" / f"{d.isoformat()}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(payload, path)


def publish_bank_csv(bank: Bank, date_metrics: dict[str, dict]) -> None:
    """
    Write / append data/banks/{BANK_ID}.csv with the bank's full time series.
    Columns: date, mes, lrmes, covar, delta_covar, srisk_usd_bn, srisk_share_pct,
             market_cap_usd_bn, debt_usd_bn, covar_beta
    """
    if not date_metrics:
        return

    rows = []
    for dt_str, m in sorted(date_metrics.items()):
        rows.append({
            "date": dt_str,
            "methodology_version": "2.0-beta-scenario",
            "calibration_id": calibration_id(),
            "dataset_kind": cfg.dataset_kind,
            "mes": m.get("mes"),
            "lrmes": m.get("lrmes"),
            "covar": m.get("covar"),
            "delta_covar": m.get("delta_covar"),
            "covar_beta": m.get("covar_beta"),
            "srisk_usd_bn": m.get("srisk_usd_bn"),
            "srisk_share_pct": m.get("srisk_share_pct"),
            "market_cap_usd_bn": m.get("market_cap_usd_bn"),
            "debt_usd_bn": m.get("debt_usd_bn"),
        })

    new_df = pd.DataFrame(rows)
    path = _data_root() / "banks" / f"{bank.id}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        existing = pd.read_csv(path)
        combined = (
            pd.concat([existing, new_df])
            .drop_duplicates(subset=["date"], keep="last")
            .sort_values("date")
        )
    else:
        combined = new_df.sort_values("date")

    _atomic_text(path, combined.to_csv(index=False))
    logger.debug(f"Updated {path} ({len(combined)} rows)")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _build_payload(
    snapshot_date: date,
    bank_records: dict[str, dict],
    system_srisk: float,
) -> dict:
    """Build the standard JSON payload structure."""
    membership = universe_evidence(snapshot_date.isoformat())
    expected = [b.id for b in BANKS]
    supported = [b.id for b in BANKS if b.supported]
    valid = [bid for bid, rec in bank_records.items()
             if bid in supported and _finite(rec.get("srisk_usd_bn"))]
    records = {bid: dict(rec) for bid, rec in bank_records.items() if bid in supported}
    subtotal = sum(max(0, records[bid]["srisk_usd_bn"]) for bid in valid)
    for bid, rec in records.items():
        rec["srisk_share_pct"] = (round(max(0, rec["srisk_usd_bn"]) / subtotal * 100, 4)
                                  if bid in valid and subtotal > 0 else 0.0 if bid in valid else None)
    missing = {bid: (next(b.exclusion_reason for b in BANKS if b.id == bid) if bid not in supported else
                    "no_record_for_date" if bid not in records else "srisk_inputs_unavailable")
               for bid in expected if bid not in valid}
    from src.calendar_status import session_status
    from datetime import timedelta
    evaluation = datetime.combine(snapshot_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    bank_status = {b.id: session_status(b, snapshot_date.isoformat(), snapshot_date.isoformat() if b.id in records else None, now=evaluation) for b in BANKS}
    for bid in records:
        if records[bid].get("srisk_usd_bn") is None:
            bank_status[bid]["status"] = "insufficient_input"
    payload = {
        "calibration_id": calibration_id(),
        "data_policy_version": "2.4.1",
        "fundamentals_policy": cfg.fundamentals_policy,
        "dataset_kind": cfg.dataset_kind,
        "date": snapshot_date.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "methodology_version": "2.0-beta-scenario",
        "parameters": {
            "srisk_k": cfg.srisk_k, "covar_quantile": cfg.covar_quantile,
            "covar_window_days": cfg.covar_window, "lrmes_horizon_days": cfg.lrmes_h,
            "lrmes_market_drop": cfg.lrmes_market_drop, "mes_tail_pct": cfg.mes_tail_pct,
            "covar_solver_policy": "quantile_irls_with_same_objective_highs_lp_fallback",
            "lrmes_model": "ols_beta_scenario", "horizon_is_label_only": True,
        },
        "coverage": {
            "metric_coverage": {metric: {"count":sum(_finite(r.get(metric)) for r in records.values()),
                 "ids":sorted(bid for bid,r in records.items() if _finite(r.get(metric)))}
                 for metric in ("mes", "lrmes", "covar", "delta_covar", "srisk_usd_bn")},
            "bank_status": bank_status,
            "universe_version": UNIVERSE_VERSION, "universe_source": membership["source"], "list_evidence": membership,
            "membership_available_from": UNIVERSE_MEMBERSHIP_AVAILABLE_FROM, "expected_ids": expected,
            "eligible_count": len(supported), "ineligible_ids": [b.id for b in BANKS if not b.supported],
            "eligible_complete": set(valid) == set(supported),
            "eligible_ids": supported, "observed_ids": sorted(records),
            "srisk_ids": sorted(valid), "missing": missing,
            "complete": not missing, "expected_count": len(expected),
            "srisk_count": len(valid),
        },
        "system_srisk_usd_bn": _round(subtotal) if not missing else None,
        "covered_srisk_usd_bn": _round(subtotal) if valid else None,
        "units": {"monetary": "USD billions", "returns": "log returns over matched closing-date intervals", "shares": "percent"},
        "share_denominator": "covered_srisk_usd_bn",
        "bank_count": len(records),
        "banks": [{**_clean(rec), "bank_id": bid} for bid, rec in sorted(records.items())],
    }

    from src.quality import assess_quality
    payload["quality"] = assess_quality(payload, today=snapshot_date)
    return payload


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def calibration_id():
    import hashlib
    parameters = ["2.0-beta-scenario", "fundamentals-policy-2.4.1", cfg.fundamentals_policy, cfg.dataset_kind, UNIVERSE_VERSION, cfg.srisk_k, cfg.covar_quantile,
                  cfg.covar_window, cfg.lrmes_h, cfg.lrmes_market_drop, cfg.mes_tail_pct]
    return hashlib.sha256(json.dumps(parameters).encode()).hexdigest()[:16]


def common_cohort_change(previous: dict, current: dict) -> dict:
    """Compare identical bank IDs and methodology only; never treat missing as zero."""
    if (previous.get("methodology_version"), previous.get("calibration_id")) != (current.get("methodology_version"), current.get("calibration_id")):
        return {"comparable": False, "reason": "methodology_changed"}
    def values(payload):
        return {r["bank_id"]: r["srisk_usd_bn"] for r in payload.get("banks", [])
                if _finite(r.get("srisk_usd_bn"))}
    before, after = values(previous), values(current)
    ids = sorted(before.keys() & after.keys())
    a, b = sum(before[i] for i in ids), sum(after[i] for i in ids)
    return {"comparable": bool(ids), "bank_ids": ids, "previous": a if ids else None,
            "current": b if ids else None, "change_pct": (b/a-1)*100 if ids and a else None}


def _clean(record: dict) -> dict:
    """Remove None values; keep NaN as null for JSON transparency."""
    return {k: v for k, v in record.items() if k != "bank_id"}


def _round(v) -> float | None:
    try:
        import math
        if not math.isfinite(float(v)):
            return None
        return round(float(v), 4)
    except (TypeError, ValueError):
        return None


def _sanitise(value):
    if isinstance(value, dict):
        return {k: _sanitise(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitise(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _atomic_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".staging-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _write_json(payload: dict, path: Path) -> None:
    _atomic_text(path, json.dumps(_sanitise(payload), indent=2, ensure_ascii=False, allow_nan=False))
