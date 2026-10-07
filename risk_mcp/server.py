"""
server.py — G-SIBs Systemic Risk MCP Server (FastAPI + Streamable HTTP transport)

Exposes systemic risk metrics for the FSB-designated G-SIB universe via the
Model Context Protocol.

Transport:
    Streamable HTTP — suitable for remote deployment.
    Default: http://0.0.0.0:8000

Data source priority:
    1. Local data/ directory (when running alongside the pipeline)
    2. raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/data/
       (set GITHUB_REPO env var when deploying remotely)

Run:
    python mcp/server.py
    uvicorn risk_mcp.server:app --host 0.0.0.0 --port 8000

MCP clients connect to:
    http://<host>:8000/mcp
"""

import json
import logging
import os
import sys
import contextlib
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.config import cfg
from src.universe import BANKS, BANK_BY_ID, REGIONS
from src.utils import is_valid_date

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("mcp-server")


transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[h.strip() for h in os.getenv("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()] + [
        "systemic-risk-mcp.jollydune-d1aeed5e.southeastasia.azurecontainerapps.io",
        "systemic-risk-mcp.jollydune-d1aeed5e.southeastasia.azurecontainerapps.io:*",
        "localhost:*",
        "127.0.0.1:*",
    ],
)

# ---------------------------------------------------------------------------
# FastMCP instance
# ---------------------------------------------------------------------------
mcp = FastMCP(
    name="gsib-systemic-risk",
    instructions=(
        "Research metrics for a versioned 29-bank universe. Coverage is date-specific. "
        "Missing values are unknown, not zero. SRISK uses a beta-scenario approximation."
    ),
    stateless_http=True,
    json_response=True,
    transport_security=transport_security,
)

# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------
DATA_DIR = Path(cfg.data_dir)


def _active_root() -> Path:
    from src.storage import active_root
    return active_root(DATA_DIR)


def _load_json(rel_path: str) -> dict | None:
    """Load JSON from local data dir or GitHub raw URL, confined to DATA_DIR."""
    local = _active_root() / rel_path
    # Security: refuse any path that escapes DATA_DIR (path-traversal guard).
    try:
        local.resolve().relative_to(DATA_DIR.resolve())
    except ValueError:
        logger.warning(f"Blocked path outside data dir: {rel_path}")
        return None

    if local.exists():
        with open(local, encoding="utf-8") as f:
            return json.load(f)

    base = cfg.raw_base_url()
    if base:
        try:
            pointer_response = httpx.get(f"{base}/data/current.json", timeout=10)
            if pointer_response.status_code == 404:
                remote_root = f"{base}/data"
            else:
                pointer_response.raise_for_status()
                name = pointer_response.json()["run"]
                import re
                if not re.fullmatch(r"[a-zA-Z0-9_-]+", name): raise ValueError("Invalid run pointer")
                remote_root = f"{base}/data/runs/{name}"
        except Exception as exc:
            logger.warning("Cannot resolve remote publication: %s", exc)
            return None
        url = f"{remote_root}/{rel_path}"
        try:
            resp = httpx.get(url, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Remote fetch failed for {rel_path}: {e}")
    return None


def _newest_history_date() -> str | None:
    """Return the most recent YYYY-MM-DD that has a local history snapshot."""
    hist_dir = _active_root() / "history"
    if hist_dir.exists():
        dates = sorted(p.stem for p in hist_dir.glob("*.json"))
        if dates:
            return dates[-1]
    return None


def _load_latest() -> dict | None:
    """Load latest.json; if missing, fall back to the newest history snapshot."""
    _rel = "latest.json"          # kept as a variable so task 1c's replace-all
    payload = _load_json(_rel)    # does NOT rewrite this line into recursion.
    if payload is not None:
        return payload
    newest = _newest_history_date()
    if newest:
        logger.info(f"latest.json missing; using newest history snapshot {newest}")
        return _load_json(f"history/{newest}.json")
    return None


def _load_bank_csv(bank_id: str) -> pd.DataFrame | None:
    """Load per-bank CSV time series."""
    local = _active_root() / "banks" / f"{bank_id}.csv"
    if local.exists():
        return pd.read_csv(local, parse_dates=["date"])

    base = cfg.raw_base_url()
    if base:
        pointer = httpx.get(f"{base}/data/current.json", timeout=10)
        import re
        name = pointer.json().get("run") if pointer.status_code == 200 else None
        if name and not re.fullmatch(r"[a-zA-Z0-9_-]+", name): return None
        if pointer.status_code not in (200, 404): return None
        prefix = f"runs/{name}/" if name else ""
        url = f"{base}/data/{prefix}banks/{bank_id}.csv"
        try:
            return pd.read_csv(url, parse_dates=["date"])
        except Exception as e:
            logger.warning(f"Remote CSV fetch failed for {bank_id}: {e}")
    return None


def _metadata(payload):
    return {key: payload.get(key) for key in (
        "date", "generated_at", "dataset_kind", "calibration_id", "methodology_version",
        "parameters", "coverage", "quality", "publication", "provenance", "data_policy_version", "units", "share_denominator")}


def _snapshot_on(day):
    if not is_valid_date(day):
        raise ValueError("Invalid date. Expected YYYY-MM-DD")
    payload = _load_json(f"history/{day}.json")
    if not payload or payload.get("methodology_version") != "2.0-beta-scenario":
        raise ValueError("No compatible snapshot for requested date")
    return payload


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------
@mcp.tool()
def get_latest_metrics(
    bank_id: str | None = None,
    region: str | None = None,
) -> dict:
    """
    Get the latest available systemic risk metrics.

    Args:
        bank_id : Optional. Return metrics for a single bank (e.g. 'JPM').
                  Case-insensitive. If omitted, returns all banks.
        region  : Optional. Filter by region: US | CN | GB | EU | JP.
                  Ignored if bank_id is provided.

    Returns:
        Full latest.json payload (or filtered subset).
    """
    payload = _load_latest()
    if payload is None:
        return {"error": "latest.json not found. Has the pipeline run yet?"}

    if payload.get("methodology_version") != "2.0-beta-scenario":
        return {"error": "Legacy estimates require recomputation; not certified by the repaired pipeline", "date": payload.get("date")}
    banks_list = payload.get("banks", [])

    if bank_id:
        bid = bank_id.upper()
        match = [b for b in banks_list if b.get("bank_id") == bid]
        if not match:
            if bid not in BANK_BY_ID:
                return {"error": f"Unknown bank '{bid}'"}
            # Individual lookup may expose an older record, never carry it into aggregates.
            history = _active_root() / "history"
            for file in sorted(history.glob("*.json"), reverse=True):
                if file.stem >= payload["date"]: continue
                old = _load_json(f"history/{file.name}")
                if not old or old.get("calibration_id") != payload.get("calibration_id"): continue
                record = next((b for b in old.get("banks", []) if b.get("bank_id") == bid and b.get("srisk_usd_bn") is not None), None)
                if record:
                    return {**_metadata(old), "requested_date":payload["date"], "as_of":old["date"],
                            "status":"previous_observation", "banks":[record], "aggregate_scope":"none; individual historical lookup"}
            return {**_metadata(payload), "status":"unavailable", "bank_id":bid,
                    "reason":payload.get("coverage",{}).get("missing",{}).get(bid, "No observation for this date"), "banks":[]}
        return {**{k: v for k, v in payload.items() if k != "banks"}, "banks": match, "returned_bank_count": len(match), "aggregate_scope": "entire snapshot before bank filter"}

    if region:
        reg = region.upper()
        filtered = [b for b in banks_list if b.get("region") == reg]
        if not filtered:
            return {"error": f"Region '{reg}' not found. Valid: {REGIONS}"}
        return {**{k: v for k, v in payload.items() if k != "banks"}, "banks": filtered, "returned_bank_count": len(filtered), "aggregate_scope": "entire snapshot before region filter"}

    return payload


@mcp.tool()
def get_historical(
    bank_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    metric: str | None = None,
) -> dict:
    """
    Get historical time series for a specific bank.

    Args:
        bank_id    : Bank identifier (e.g. 'JPM', 'ICBC', 'HSBC'). Required.
        start_date : Start date YYYY-MM-DD (inclusive). Optional.
        end_date   : End date YYYY-MM-DD (inclusive). Optional.
        metric     : If provided, return only this metric column.
                     Options: mes | lrmes | covar | delta_covar | srisk_usd_bn |
                              srisk_share_pct | market_cap_usd_bn | debt_usd_bn

    Returns:
        Dict with bank info and 'records' list of daily metric values.
    """
    bid = bank_id.upper()
    if bid not in BANK_BY_ID:
        return {"error": f"Unknown bank_id '{bid}'."}

    bank = BANK_BY_ID[bid]
    df = _load_bank_csv(bid)
    if df is None or df.empty:
        return {"error": f"No historical data found for {bid}. Has the pipeline run?"}

    if any(value and not is_valid_date(value) for value in (start_date, end_date)):
        return {"error": "Invalid date. Expected YYYY-MM-DD."}
    if start_date and end_date and start_date > end_date:
        return {"error": "start_date exceeds end_date"}
    if "methodology_version" not in df.columns or not (df["methodology_version"] == "2.0-beta-scenario").all():
        return {"error": "Legacy CSV requires recomputation"}
    if start_date:
        df = df[df["date"] >= pd.Timestamp(start_date)]
    if end_date:
        df = df[df["date"] <= pd.Timestamp(end_date)]

    if df.empty:
        return {"error": f"No data in specified date range for {bid}."}

    if metric:
        if metric not in df.columns:
            return {"error": f"Unknown metric '{metric}'. Valid: {list(df.columns[1:])}"}
        df = df[["date", metric]]

    records = df.astype(object).where(pd.notna(df), None).to_dict(orient="records")
    for r in records:
        if hasattr(r.get("date"), "isoformat"):
            r["date"] = r["date"].isoformat()

    metadata_by_date = {}
    for row in records:
        day = row["date"][:10]
        local = _active_root() / "history" / f"{day}.json"
        if local.exists():
            snapshot = json.loads(local.read_text())
            metadata_by_date[day] = _metadata(snapshot)
        else:
            metadata_by_date[day] = {"date":day, "status":"snapshot_metadata_unavailable"}
    return {
        "metadata_by_date": metadata_by_date,
        "metadata_scope": "per observation date; never inferred from today's configuration",
        "bank_id": bid,
        "bank_name": bank.name,
        "region": bank.region,
        "covar_index": bank.index_yf,
        "record_count": len(records),
        "records": records,
    }


@mcp.tool()
def get_srisk_ranking(
    date: str | None = None,
    region: str | None = None,
    top_n: int = 30,
) -> dict:
    """
    Get banks ranked by SRISK (highest systemic capital shortfall first).

    Args:
        date   : Date YYYY-MM-DD to use for snapshot. Default: latest.
        region : Filter by region (US|CN|GB|EU|JP). Optional.
        top_n  : Number of top banks to return. Default: 30 (all).

    Returns:
        Ranked list of banks by SRISK with key metrics.
    """
    if date:
        if not is_valid_date(date):
            return {"error": f"Invalid date '{date}'. Expected format YYYY-MM-DD."}
        payload = _load_json(f"history/{date}.json")
        if payload is None:
            return {"error": f"No snapshot found for {date}."}
    else:
        payload = _load_latest()
        if payload is None:
            return {"error": "No data available."}

    if payload.get("methodology_version") != "2.0-beta-scenario":
        return {"error": "Legacy estimates require recomputation", "date": payload.get("date")}
    if not 1 <= top_n <= 100:
        return {"error": "top_n must be between 1 and 100"}
    banks = payload.get("banks", [])
    if region:
        banks = [b for b in banks if b.get("region") == region.upper()]

    ranked = sorted(
        [b for b in banks if b.get("srisk_usd_bn") is not None],
        key=lambda x: x.get("srisk_usd_bn", 0),
        reverse=True,
    )[:top_n]

    return {
        **_metadata(payload),
        "date": payload.get("date"),
        "system_srisk_usd_bn": payload.get("system_srisk_usd_bn"),
        "coverage": payload.get("coverage"),
        "covered_srisk_usd_bn": payload.get("covered_srisk_usd_bn"),
        "aggregate_scope": "entire snapshot, before region/top_n filtering",
        "region_filter": region,
        "ranking": [
            {
                "rank": i + 1,
                "market_cap_evidence": b.get("market_cap_evidence"),
                "liabilities_evidence": b.get("liabilities_evidence"),
                "fundamentals_input_sha256": b.get("fundamentals_input_sha256"),
                "bank_id": b.get("bank_id"),
                "bank_name": b.get("bank_name"),
                "region": b.get("region"),
                "srisk_usd_bn": b.get("srisk_usd_bn"),
                "srisk_share_pct": b.get("srisk_share_pct"),
                "lrmes": b.get("lrmes"),
                "market_cap_usd_bn": b.get("market_cap_usd_bn"),
            }
            for i, b in enumerate(ranked)
        ],
    }


@mcp.tool()
def get_delta_covar_ranking(
    date: str | None = None,
    region: str | None = None,
    top_n: int = 30,
) -> dict:
    """
    Get banks ranked by ΔCoVaR (most systemic first, i.e. most negative ΔCoVaR).

    Args:
        date   : Date YYYY-MM-DD. Default: latest.
        region : Filter by region. Optional.
        top_n  : Number of banks to return. Default: 30.

    Returns:
        Ranked list with ΔCoVaR and CoVaR values.
    """
    if date:
        if not is_valid_date(date):
            return {"error": f"Invalid date '{date}'. Expected format YYYY-MM-DD."}
        payload = _load_json(f"history/{date}.json")
        if payload is None:
            return {"error": f"No snapshot for {date}."}
    else:
        payload = _load_latest()
        if payload is None:
            return {"error": "No data available."}

    if payload.get("methodology_version") != "2.0-beta-scenario":
        return {"error": "Legacy estimates require recomputation", "date": payload.get("date")}
    if not 1 <= top_n <= 100:
        return {"error": "top_n must be between 1 and 100"}
    banks = payload.get("banks", [])
    if region:
        banks = [b for b in banks if b.get("region") == region.upper()]

    ranked = sorted(
        [b for b in banks if b.get("delta_covar") is not None],
        key=lambda x: x.get("delta_covar", 0),
    )[:top_n]  # most negative first = most systemic

    return {
        **_metadata(payload),
        "date": payload.get("date"),
        "coverage": payload.get("coverage"),
        "covered_srisk_usd_bn": payload.get("covered_srisk_usd_bn"),
        "aggregate_scope": "entire snapshot, before region/top_n filtering",
        "region_filter": region,
        "note": "More negative ΔCoVaR indicates greater systemic risk contribution.",
        "ranking": [
            {
                "rank": i + 1,
                "market_cap_evidence": b.get("market_cap_evidence"),
                "liabilities_evidence": b.get("liabilities_evidence"),
                "fundamentals_input_sha256": b.get("fundamentals_input_sha256"),
                "bank_id": b.get("bank_id"),
                "bank_name": b.get("bank_name"),
                "region": b.get("region"),
                "covar_index": b.get("covar_index"),
                "delta_covar": b.get("delta_covar"),
                "covar": b.get("covar"),
                "mes": b.get("mes"),
            }
            for i, b in enumerate(ranked)
        ],
    }


@mcp.tool()
def get_methodology() -> dict:
    """
    Return the full methodology documentation for all metrics.

    Returns:
        Dict describing MES, LRMES, CoVaR, ΔCoVaR, SRISK formulas,
        data sources, index choices, and configurable parameters.
    """
    snapshot = _load_latest() or {}
    parameters = snapshot.get("parameters", {})
    return {
        **_metadata(snapshot),
        "parameter_scope": "published snapshot" if parameters else "configuration defaults; no snapshot parameters available",
        "title": "G-SIBs Systemic Risk Metrics — Methodology",
        "version": "2.0-beta-scenario",
        "metrics": {
            "MES": {
                "full_name": "Marginal Expected Shortfall",
                "reference": "Acharya, Pedersen, Philippon & Richardson (2010)",
                "formula": "MES_i = E[r_i | r_m ≤ VaR_τ(r_m)]",
                "description": "Mean return of bank i on days when the market falls below its τ-th percentile.",
                "default_tau": parameters.get("mes_tail_pct", cfg.mes_tail_pct),
            },
            "LRMES": {
                "full_name": "Long-Run Marginal Expected Shortfall",
                "reference": "Custom OLS-beta scenario proxy; not the Brownlees–Engle dynamic estimator",
                "formula": "LRMES = 1 - exp(log(1-D) · β_OLS)",
                "parameters": {
                    "D": f"Market drop scenario = {parameters.get('lrmes_market_drop', cfg.lrmes_market_drop):.0%}",
                    "h": f"Horizon = {parameters.get('lrmes_horizon_days', cfg.lrmes_h)} trading days (scenario label; not in the closed form)",
                    "beta_OLS": "Cov(bank log returns, index log returns) / Var(index log returns)",
                },
            },
            "CoVaR": {
                "full_name": "Conditional Value-at-Risk",
                "reference": "Adrian & Brunnermeier (2011)",
                "formula": "q_τ(r_system | r_bank = x) = α + β·x  [quantile regression]",
                "description": "System VaR conditional on bank being at its own VaR.",
            },
            "DeltaCoVaR": {
                "full_name": "ΔCoVaR",
                "formula": "ΔCoVaR_i = β̂ · (VaR_i - Median_i)",
                "description": "Incremental systemic risk contribution vs normal state.",
                "note": "More negative = greater systemic importance.",
            },
            "SRISK": {
                "full_name": "Systemic Risk (Capital Shortfall)",
                "reference": "Brownlees & Engle (2017)",
                "formula": "SRISK_i = max(0, k·Debt_i - (1-k)·W_i·(1-LRMES_i))",
                "parameters": {
                    "k": f"Prudential capital ratio = {parameters.get('srisk_k', cfg.srisk_k):.0%} (configurable via SRISK_K env var)",
                    "Debt": "Total liabilities (USD bn, quarterly balance sheet)",
                    "W": "Market capitalisation (USD bn)",
                    "LRMES": f"OLS-beta loss proxy; drop={parameters.get('lrmes_market_drop', cfg.lrmes_market_drop)}, horizon label={parameters.get('lrmes_horizon_days', cfg.lrmes_h)}",
                },
            },
        },
        "data_sources": {
            "prices": "Yahoo Finance; no silent cross-listing fallback",
            "market_cap": "Dated vendor shares × non-dividend-adjusted price; split ranges and multi-class/group mismatch require verified inputs",
            "debt": "Sourced consolidated liabilities, activated only at actual public availability date",
            "fx_conversion": "All monetary values converted to USD via daily FX rates from Yahoo Finance",
        },
        "covar_index_by_region": {
            "US": "^GSPC (S&P 500) — domestic systemic benchmark",
            "CN": "^HSI (Hang Seng) for H-share listed CN banks — reflects offshore systemic risk",
            "GB": "^FTSE (FTSE 100) — post-Brexit separate benchmark",
            "EU": "^STOXX50E (EURO STOXX 50) — eurozone systemic reference",
            "JP": "^N225 (Nikkei 225) — domestic systemic reference",
            "CA": "^GSPTSE (S&P/TSX Composite)",
        },
        "rolling_window_days": parameters.get("covar_window_days", cfg.covar_window),
        "universe": snapshot.get("coverage", {}).get("universe_version"),
    }


@mcp.tool()
def get_sensitivity(bank_id: str, date: str | None = None,
                    market_drops: list[float] | None = None,
                    capital_ratios: list[float] | None = None) -> dict:
    """Fixed-input OLS-beta scenario grid. A range, not a confidence interval."""
    from src.analysis import scenario_grid
    try:
        payload = _snapshot_on(date) if date else _load_latest()
        if not payload: return {"error":"No snapshot"}
        if payload.get("methodology_version") != "2.0-beta-scenario": return {"error":"Incompatible methodology"}
        bank = next((b for b in payload["banks"] if b["bank_id"] == bank_id.upper()), {})
        return {**_metadata(payload), "input_evidence":{key:bank.get(key) for key in
                    ("market_cap_evidence", "liabilities_evidence", "fundamentals_input_sha256")},
                "analysis":scenario_grid(bank,payload.get("parameters",{}),market_drops,capital_ratios)}
    except ValueError as exc:
        return {"error":str(exc)}


@mcp.tool()
def get_change_explanation(bank_id: str, previous_date: str, current_date: str) -> dict:
    """Exact Shapley change attribution for the same bank and model calibration."""
    from src.analysis import explain_change
    try:
        previous, current = _snapshot_on(previous_date), _snapshot_on(current_date)
        return {**_metadata(current), "previous_metadata":_metadata(previous),
                "analysis":explain_change(previous,current,bank_id.upper())}
    except ValueError as exc:
        return {"error":str(exc)}


# ---------------------------------------------------------------------------
# FastAPI app + MCP Streamable HTTP transport
# ---------------------------------------------------------------------------
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(
    title="G-SIBs Systemic Risk MCP",
    description="Research systemic-risk metrics with explicit coverage and missing inputs",
    version="2.4.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Health check endpoint."""
    payload = _load_latest()
    from src.quality import assess_quality
    quality = assess_quality(payload) if payload else {"status":"error", "alerts":[{"code":"NO_DATA"}]}
    # Liveness remains explicit even when the dataset is incomplete or stale.
    return {"service_status":"ok", "data_status":quality["status"],
            "status":"ok" if quality["status"]=="ok" else "degraded",
            "dataset_kind":payload.get("dataset_kind") if payload else None,
            "data_date":payload.get("date") if payload else None,
            "calibration_id":payload.get("calibration_id") if payload else None,
            "methodology_version":payload.get("methodology_version") if payload else None,
            "coverage":payload.get("coverage") if payload else None,
            "quality":quality,"server":"gsib-systemic-risk-mcp","version":"2.4.0"}


@app.get("/")
async def root():
    return {
        "name": "G-SIBs Systemic Risk MCP Server",
        "mcp_endpoint": "/mcp",
        "health": "/health",
        "docs": "/docs",
    }


# The public Azure Container Apps hostname must be explicitly trusted by the
# MCP SDK's DNS-rebinding protection.

# streamable_http_app() exposes the SDK's default /mcp endpoint.
app.mount("/", mcp.streamable_http_app())


def main():
    import uvicorn
    uvicorn.run(
        app,
        host=cfg.mcp_host,
        port=cfg.mcp_port,
        reload=False,
    )



if __name__ == "__main__":
    main()
