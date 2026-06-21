from __future__ import annotations

import datetime as dt
import json
import math
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests


RUN_DIR = Path(__file__).resolve().parent
REPO_ROOT = RUN_DIR.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import research_subd_six_etf_weighted_slope as subd  # noqa: E402
import run_subd_six_etf_v1_1 as v11  # noqa: E402


RUN_ID = RUN_DIR.name
END_DATE = pd.Timestamp("2026-06-17")
EVAL_START = pd.Timestamp("2020-01-02")
START_DATE = pd.Timestamp("2010-01-01")
SPLIT_CODE = "159941.SZ"
SPLIT_EFFECTIVE_DATE = pd.Timestamp("2022-07-05")
SPLIT_PRE_FACTOR = 0.25
ADJUSTMENT_POLICY = "sina_raw_split_continuity_159941_pre_20220705_x0.25"
YAHOO_SYMBOLS = {
    "159915.SZ": "159915.SZ",
    "159941.SZ": "159941.SZ",
    "513030.SH": "513030.SS",
    "513520.SH": "513520.SS",
    "159985.SZ": "159985.SZ",
    "518880.SH": "518880.SS",
}


@dataclass(frozen=True)
class Candidate:
    candidate: str
    step_order: int
    r2_threshold: float | None
    switch_buffer: float
    entry_mode: str
    initial_fraction: float
    target_vol_enabled: bool
    overheat_enabled: bool
    description: str


CANDIDATES = [
    Candidate(
        candidate="01_score_gate_full_entry",
        step_order=1,
        r2_threshold=None,
        switch_buffer=1.00,
        entry_mode="full_entry",
        initial_fraction=1.00,
        target_vol_enabled=False,
        overheat_enabled=False,
        description="Score gate only, full entry, no R2, no switch buffer, no target-vol, no overheat.",
    ),
    Candidate(
        candidate="02_add_r2_full_entry",
        step_order=2,
        r2_threshold=v11.R2_THRESHOLD,
        switch_buffer=1.00,
        entry_mode="full_entry",
        initial_fraction=1.00,
        target_vol_enabled=False,
        overheat_enabled=False,
        description="Add R2 threshold 0.20, full entry.",
    ),
    Candidate(
        candidate="03_add_switch_buffer",
        step_order=3,
        r2_threshold=v11.R2_THRESHOLD,
        switch_buffer=v11.SWITCH_BUFFER,
        entry_mode="full_entry",
        initial_fraction=1.00,
        target_vol_enabled=False,
        overheat_enabled=False,
        description="Add 1.05 switch buffer, full entry.",
    ),
    Candidate(
        candidate="04_add_staged_entry",
        step_order=4,
        r2_threshold=v11.R2_THRESHOLD,
        switch_buffer=v11.SWITCH_BUFFER,
        entry_mode="all_new_asset_50_wait_down",
        initial_fraction=v11.INITIAL_ENTRY_FRACTION,
        target_vol_enabled=False,
        overheat_enabled=False,
        description="Add 50% staged entry and fill-on-down-day rule.",
    ),
    Candidate(
        candidate="05_add_target_vol",
        step_order=5,
        r2_threshold=v11.R2_THRESHOLD,
        switch_buffer=v11.SWITCH_BUFFER,
        entry_mode="all_new_asset_50_wait_down",
        initial_fraction=v11.INITIAL_ENTRY_FRACTION,
        target_vol_enabled=True,
        overheat_enabled=False,
        description="Add 25% target-vol overlay, 80-day realized vol, max leverage 1.5.",
    ),
    Candidate(
        candidate="06_full_v11_add_overheat",
        step_order=6,
        r2_threshold=v11.R2_THRESHOLD,
        switch_buffer=v11.SWITCH_BUFFER,
        entry_mode="all_new_asset_50_wait_down",
        initial_fraction=v11.INITIAL_ENTRY_FRACTION,
        target_vol_enabled=True,
        overheat_enabled=True,
        description="Full V1.1 chain with MA60 overheat derisk scale 0.",
    ),
]


def _git_value(args: list[str]) -> str:
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=REPO_ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
        ).strip()
    except Exception:
        return ""


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, encoding="utf-8-sig")


def _append_command_log(text: str) -> None:
    with (RUN_DIR / "command_log.txt").open("a", encoding="utf-8") as f:
        f.write("\n")
        f.write(text.rstrip())
        f.write("\n")


def _apply_split_continuity(code: str, close: pd.Series) -> pd.Series:
    adjusted = close.astype(float).copy()
    if code == SPLIT_CODE:
        adjusted.loc[adjusted.index < SPLIT_EFFECTIVE_DATE] *= SPLIT_PRE_FACTOR
    adjusted.name = code
    return adjusted


def load_sina_split_adjusted_prices(end_date: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    series: list[pd.Series] = []
    source_rows: list[dict[str, Any]] = []
    raw_quality_rows: list[dict[str, Any]] = []
    for code, name in subd.ASSETS.items():
        raw = subd.load_akshare_sina_raw_one_close(code, end_date)
        adjusted = _apply_split_continuity(code, raw)
        non_na = adjusted.dropna()
        raw_ret = raw.astype(float).pct_change()
        adj_ret = adjusted.astype(float).pct_change()
        raw_quality_rows.append(
            {
                "code": code,
                "name": name,
                "raw_first": raw.dropna().index.min().date().isoformat(),
                "raw_last": raw.dropna().index.max().date().isoformat(),
                "raw_rows": int(raw.dropna().shape[0]),
                "adjusted_first": non_na.index.min().date().isoformat(),
                "adjusted_last": non_na.index.max().date().isoformat(),
                "adjusted_rows": int(non_na.shape[0]),
                "max_abs_raw_daily_return": float(raw_ret.abs().max(skipna=True)),
                "max_abs_adjusted_daily_return": float(adj_ret.abs().max(skipna=True)),
                "split_continuity_factor": SPLIT_PRE_FACTOR if code == SPLIT_CODE else 1.0,
            }
        )
        source_rows.append(
            {
                "code": code,
                "name": name,
                "source": "akshare.fund_etf_hist_sina",
                "adjustment": ADJUSTMENT_POLICY if code == SPLIT_CODE else "sina_raw_unadjusted_no_detected_split_patch",
                "first": non_na.index.min().date().isoformat(),
                "last": non_na.index.max().date().isoformat(),
                "rows": int(non_na.shape[0]),
            }
        )
        series.append(adjusted)

    prices = pd.concat(series, axis=1).sort_index()
    prices = prices.loc[prices.index >= START_DATE]
    common_valid = prices.notna().all(axis=1)
    dropped_missing_rows = int((~common_valid).sum())
    prices = prices.loc[common_valid].copy()
    prices, common_last, _last_by_asset = v11.align_prices_to_common_valid_date(prices, list(subd.ASSETS))
    if common_last.normalize() != end_date.normalize():
        raise RuntimeError(f"Common latest date {common_last.date()} does not match requested {end_date.date()}")
    quality = pd.DataFrame(raw_quality_rows)
    quality["common_calendar_start"] = prices.index.min().date().isoformat()
    quality["common_calendar_end"] = prices.index.max().date().isoformat()
    quality["common_calendar_rows"] = int(prices.shape[0])
    quality["dropped_union_calendar_rows_with_any_missing"] = dropped_missing_rows
    if float(quality["max_abs_adjusted_daily_return"].max()) > 0.30:
        raise RuntimeError("Adjusted primary data still contains a >30% absolute daily return jump.")
    return prices, pd.DataFrame(source_rows), quality


def fetch_yahoo_close(symbol: str, end_date: pd.Timestamp) -> pd.Series:
    period1 = int(dt.datetime(2010, 1, 1, tzinfo=dt.timezone.utc).timestamp())
    period2 = int((end_date + pd.Timedelta(days=1)).to_pydatetime().replace(tzinfo=dt.timezone.utc).timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {
        "period1": period1,
        "period2": period2,
        "interval": "1d",
        "events": "history,div,splits",
        "includeAdjustedClose": "true",
    }
    response = requests.get(url, params=params, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    payload = response.json()
    result = (payload.get("chart") or {}).get("result") or []
    if not result:
        raise RuntimeError(f"Yahoo returned no result for {symbol}")
    item = result[0]
    timestamps = item.get("timestamp") or []
    adj = ((item.get("indicators") or {}).get("adjclose") or [{}])[0].get("adjclose") or []
    if not timestamps or not adj:
        raise RuntimeError(f"Yahoo returned no adjusted close for {symbol}")
    dates = [dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).date().isoformat() for ts in timestamps]
    close = pd.Series(adj, index=pd.to_datetime(dates), dtype=float).dropna().sort_index()
    close.name = symbol
    return close.loc[:end_date]


def build_source_validation(prices: pd.DataFrame, end_date: pd.Timestamp) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for code in subd.ASSETS:
        row: dict[str, Any] = {"code": code, "independent_source": "Yahoo Finance chart adjusted close"}
        try:
            yahoo = fetch_yahoo_close(YAHOO_SYMBOLS[code], end_date)
            primary = prices[code].dropna()
            common = primary.index.intersection(yahoo.index)
            recent_common = common[common >= end_date - pd.Timedelta(days=120)]
            if len(recent_common):
                diff = (primary.loc[recent_common] / yahoo.loc[recent_common] - 1.0).abs()
                max_recent_diff = float(diff.max())
                last_common = pd.Timestamp(recent_common.max())
                last_diff = float(primary.loc[last_common] / yahoo.loc[last_common] - 1.0)
            else:
                max_recent_diff = math.nan
                last_common = pd.NaT
                last_diff = math.nan
            row.update(
                {
                    "validation_status": "ok",
                    "primary_rows": int(primary.shape[0]),
                    "independent_rows": int(yahoo.shape[0]),
                    "primary_first": primary.index.min().date().isoformat(),
                    "primary_last": primary.index.max().date().isoformat(),
                    "independent_first": yahoo.index.min().date().isoformat(),
                    "independent_last": yahoo.index.max().date().isoformat(),
                    "common_rows": int(common.shape[0]),
                    "recent_common_rows": int(len(recent_common)),
                    "last_common_date": last_common.date().isoformat() if pd.notna(last_common) else "",
                    "last_common_close_diff_pct": last_diff,
                    "max_abs_recent_close_diff_pct": max_recent_diff,
                    "note": "Yahoo has a known 159941 split-point glitch; it is not used for returns."
                    if code == SPLIT_CODE
                    else "",
                }
            )
        except Exception as exc:
            row.update({"validation_status": "failed", "error": str(exc)[:300]})
        rows.append(row)
        time.sleep(0.3)
    return pd.DataFrame(rows)


def _candidate_entry_case(candidate: Candidate) -> v11.EntryCase:
    return v11.EntryCase(
        candidate.candidate,
        candidate.entry_mode,  # type: ignore[arg-type]
        candidate.initial_fraction,
    )


def _ensure_common_curve_columns(curve: pd.DataFrame) -> pd.DataFrame:
    out = curve.copy()
    if "target_vol_scale_effective" not in out.columns:
        out["target_vol_scale_effective"] = 1.0
    if "target_vol_scale_next" not in out.columns:
        out["target_vol_scale_next"] = 1.0
    if "weight" not in out.columns:
        out["weight"] = out["holding_fraction"].astype(float).fillna(0.0)
    if "overheat_scale_effective" not in out.columns:
        out["overheat_scale_effective"] = 1.0
    if "overheat_scale_next" not in out.columns:
        out["overheat_scale_next"] = 1.0
    if "overheat_on_effective" not in out.columns:
        out["overheat_on_effective"] = False
    if "overheat_on" not in out.columns:
        out["overheat_on"] = False
    if "overheat_triggered" not in out.columns:
        out["overheat_triggered"] = False
    if "overheat_recovered" not in out.columns:
        out["overheat_recovered"] = False
    if "overheat_feature_missing" not in out.columns:
        out["overheat_feature_missing"] = False
    if "exposure_effective" not in out.columns:
        out["exposure_effective"] = out["fraction_before"].astype(float).fillna(0.0)
    if "final_exposure_after_overheat" not in out.columns:
        out["final_exposure_after_overheat"] = out["holding_fraction"].astype(float).fillna(0.0)
    return out


def run_candidate(
    prices: pd.DataFrame,
    config: subd.RunConfig,
    features: dict[str, pd.DataFrame],
    candidate: Candidate,
) -> pd.DataFrame:
    curve = v11.run_staged_entry(
        prices,
        config,
        _candidate_entry_case(candidate),
        candidate.r2_threshold,
        candidate.switch_buffer,
    )
    if candidate.target_vol_enabled:
        curve = v11.apply_target_vol_overlay(
            curve,
            v11.TARGET_VOL,
            config.vol_window,
            config.max_lev,
            config.one_way_cost,
        )
    if candidate.overheat_enabled:
        curve = v11.apply_overheat_overlay(
            curve,
            features,
            v11.OverheatCase(candidate.candidate, v11.OVERHEAT_ENTER, v11.OVERHEAT_EXIT, v11.OVERHEAT_DERISK_SCALE),
            config.one_way_cost,
        )
    curve = _ensure_common_curve_columns(curve)
    if "scenario" in curve.columns:
        curve["scenario"] = candidate.candidate
    else:
        curve.insert(0, "scenario", candidate.candidate)
    curve.insert(0, "candidate", candidate.candidate)
    curve.insert(1, "step_order", candidate.step_order)
    curve["r2_threshold"] = candidate.r2_threshold if candidate.r2_threshold is not None else np.nan
    curve["switch_buffer"] = candidate.switch_buffer
    curve["entry_mode"] = candidate.entry_mode
    curve["initial_fraction"] = candidate.initial_fraction
    curve["target_vol_enabled"] = candidate.target_vol_enabled
    curve["overheat_enabled"] = candidate.overheat_enabled
    curve["source_policy"] = ADJUSTMENT_POLICY
    return curve


def _window_start(index: pd.DatetimeIndex, cutoff: pd.Timestamp) -> pd.Timestamp:
    eligible = index[index >= cutoff]
    if eligible.empty:
        raise RuntimeError(f"No trading date on or after {cutoff.date()}")
    return pd.Timestamp(eligible[0])


def build_windows(index: pd.DatetimeIndex, end_date: pd.Timestamp) -> dict[str, tuple[pd.Timestamp, str]]:
    return {
        "full": (_window_start(index, EVAL_START), ""),
        "last_10y": (_window_start(index, max(EVAL_START, end_date - pd.DateOffset(years=10))), "clipped_to_eval_start"),
        "last_5y": (_window_start(index, end_date - pd.DateOffset(years=5)), ""),
        "last_3y": (_window_start(index, end_date - pd.DateOffset(years=3)), ""),
        "last_1y": (_window_start(index, end_date - pd.DateOffset(years=1)), ""),
    }


def max_drawdown_from_returns(ret: pd.Series) -> float:
    wealth = (1.0 + ret.astype(float).fillna(0.0)).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min())


def summarize_window(curve: pd.DataFrame, candidate: Candidate, segment: str, start: pd.Timestamp, note: str) -> dict[str, Any]:
    sub = curve.loc[curve.index >= start].copy()
    if sub.empty:
        raise RuntimeError(f"{candidate.candidate} has empty window {segment}")
    ret = pd.to_numeric(sub["return"], errors="coerce").fillna(0.0)
    wealth = (1.0 + ret).cumprod()
    days = int(ret.shape[0])
    years = days / subd.TRADING_DAYS
    ann_vol = float(ret.std(ddof=0) * math.sqrt(subd.TRADING_DAYS))
    ann_return = float(wealth.iloc[-1] ** (1.0 / years) - 1.0)
    sharpe = float(ret.mean() / ret.std(ddof=0) * math.sqrt(subd.TRADING_DAYS)) if ret.std(ddof=0) > 0 else math.nan
    effective_exposure = pd.to_numeric(sub["exposure_effective"], errors="coerce").fillna(0.0)
    final_exposure = pd.to_numeric(sub["final_exposure_after_overheat"], errors="coerce").fillna(0.0)
    turnover = pd.to_numeric(sub["turnover"], errors="coerce").fillna(0.0)
    cost = pd.to_numeric(sub["cost"], errors="coerce").fillna(0.0)
    return {
        "candidate": candidate.candidate,
        "step_order": candidate.step_order,
        "segment": segment,
        "window_note": note,
        "start": sub.index.min().date().isoformat(),
        "end": sub.index.max().date().isoformat(),
        "rows": days,
        "ann_return": ann_return,
        "ann_vol": ann_vol,
        "sharpe_repo": sharpe,
        "max_dd": max_drawdown_from_returns(ret),
        "total_return": float(wealth.iloc[-1] - 1.0),
        "avg_effective_exposure": float(effective_exposure.mean()),
        "avg_final_exposure": float(final_exposure.mean()),
        "max_final_exposure": float(final_exposure.max()),
        "avg_turnover": float(turnover.mean()),
        "turnover_sum": float(turnover.sum()),
        "cost_total": float(cost.sum()),
        "holding_day_ratio": float((effective_exposure > 1e-12).mean()),
        "cash_day_ratio": float((sub["position"].astype(str) == "CASH").mean()),
        "trades": int((turnover > 1e-12).sum()),
        "staged_initials": int(sub["staged_initial"].astype(bool).sum()) if "staged_initial" in sub.columns else 0,
        "staged_fills": int(sub["fill_on_down_day"].astype(bool).sum()) if "fill_on_down_day" in sub.columns else 0,
        "overheat_days": int(sub["overheat_on_effective"].astype(bool).sum()),
        "overheat_triggers": int(sub["overheat_triggered"].astype(bool).sum()),
        "r2_threshold": candidate.r2_threshold if candidate.r2_threshold is not None else np.nan,
        "switch_buffer": candidate.switch_buffer,
        "entry_mode": candidate.entry_mode,
        "initial_fraction": candidate.initial_fraction,
        "target_vol_enabled": candidate.target_vol_enabled,
        "overheat_enabled": candidate.overheat_enabled,
        "source_policy": ADJUSTMENT_POLICY,
    }


def build_window_metrics(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for candidate, group in summary.groupby("candidate", sort=False):
        first = group.iloc[0]
        row: dict[str, Any] = {
            "candidate": candidate,
            "step_order": int(first["step_order"]),
            "r2_threshold": first["r2_threshold"],
            "switch_buffer": first["switch_buffer"],
            "entry_mode": first["entry_mode"],
            "initial_fraction": first["initial_fraction"],
            "target_vol_enabled": bool(first["target_vol_enabled"]),
            "overheat_enabled": bool(first["overheat_enabled"]),
        }
        for _, metric_row in group.iterrows():
            segment = metric_row["segment"]
            row[f"ann_return_{segment}"] = metric_row["ann_return"]
            row[f"max_dd_{segment}"] = metric_row["max_dd"]
            row[f"sharpe_{segment}"] = metric_row["sharpe_repo"]
            row[f"rows_{segment}"] = metric_row["rows"]
            row[f"start_{segment}"] = metric_row["start"]
            row[f"end_{segment}"] = metric_row["end"]
        rows.append(row)
    return pd.DataFrame(rows)


def pct(value: float) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{value * 100:.2f}%"


def write_record(summary: pd.DataFrame, window_metrics: pd.DataFrame, sources: pd.DataFrame, validation: pd.DataFrame) -> None:
    full = summary[summary["segment"] == "full"].sort_values("step_order")
    lines: list[str] = []
    lines.append("# Quant Parameter Scan Record")
    lines.append("")
    lines.append("## Run Metadata")
    lines.append("")
    lines.append(f"- Run id: `{RUN_ID}`")
    lines.append(f"- Created/updated at: {dt.datetime.now().astimezone().isoformat(timespec='seconds')}")
    lines.append("- Project: SubD six ETF")
    lines.append("- Strategy or version: V1.1 ablation chain")
    lines.append("- Sleeve or subsystem: ablation_chain")
    lines.append("- Parameter group: `same_slice_ablation`")
    lines.append("- Scan type: `ablation_chain`")
    lines.append(f"- Repo or workspace path: `{REPO_ROOT}`")
    lines.append(f"- Target entrypoint: `{Path(__file__).relative_to(REPO_ROOT)}`")
    lines.append(f"- Git branch: `{_git_value(['branch', '--show-current'])}`")
    lines.append(f"- Git commit: `{_git_value(['rev-parse', 'HEAD'])}`")
    lines.append("")
    lines.append("## Research Question")
    lines.append("")
    lines.append("- Compare the V1.1 component chain on one identical data slice: score gate, R2, switch buffer, staged entry, target-vol, and overheat.")
    lines.append("- Source-change rule: `research_only_no_source_change`")
    lines.append("- Required windows: full, 10Y, 5Y, 3Y, 1Y")
    lines.append("- Required metrics: annual return, annualized volatility, Sharpe, max drawdown, exposure, turnover, and cost.")
    lines.append("")
    lines.append("## Data Snapshot")
    lines.append("")
    lines.append(f"- Primary source: `akshare.fund_etf_hist_sina` daily close.")
    lines.append(f"- Adjustment policy: `{ADJUSTMENT_POLICY}`.")
    lines.append(f"- Evaluation start: `{EVAL_START.date().isoformat()}`.")
    lines.append(f"- Evaluation end: `{END_DATE.date().isoformat()}`.")
    lines.append("- Independent check: Yahoo Finance chart adjusted close, recent closes only; Yahoo is not used for returns.")
    lines.append("- Caveat: this is not qfq parity. It is a single-source split-continuity research slice because QVeris and Eastmoney qfq are unavailable in this environment.")
    lines.append("")
    lines.append("## Sources")
    lines.append("")
    lines.append(sources.to_markdown(index=False))
    lines.append("")
    lines.append("## Source Validation")
    lines.append("")
    lines.append(validation.to_markdown(index=False))
    lines.append("")
    lines.append("## Cost and Execution Assumptions")
    lines.append("")
    lines.append(f"- One-way cost: `{v11.ONE_WAY_COST:.4f}`.")
    lines.append("- Rebalance/fill timing: close-to-close, same as existing V1.1 research harness.")
    lines.append(f"- Target-vol: `{v11.TARGET_VOL:.2f}`, vol window `{subd.DEFAULT_VOL_WINDOW}`, max leverage `{subd.DEFAULT_MAX_LEV}`.")
    lines.append(f"- Overheat: enter `{v11.OVERHEAT_ENTER:.2f}`, exit `{v11.OVERHEAT_EXIT:.2f}`, derisk scale `{v11.OVERHEAT_DERISK_SCALE:.1f}`.")
    lines.append("")
    lines.append("## Full-Sample Results")
    lines.append("")
    full_table = full[
        [
            "candidate",
            "ann_return",
            "max_dd",
            "sharpe_repo",
            "avg_effective_exposure",
            "turnover_sum",
            "cost_total",
            "trades",
        ]
    ].copy()
    for col in ["ann_return", "max_dd", "avg_effective_exposure", "cost_total"]:
        full_table[col] = full_table[col].map(lambda x: pct(float(x)))
    full_table["sharpe_repo"] = full_table["sharpe_repo"].map(lambda x: f"{float(x):.2f}")
    full_table["turnover_sum"] = full_table["turnover_sum"].map(lambda x: f"{float(x):.2f}")
    lines.append(full_table.to_markdown(index=False))
    lines.append("")
    lines.append("## Window Results")
    lines.append("")
    display = window_metrics.copy()
    keep_cols = ["candidate"]
    for segment in ["full", "last_10y", "last_5y", "last_3y", "last_1y"]:
        keep_cols.extend([f"ann_return_{segment}", f"max_dd_{segment}"])
    display = display[keep_cols]
    for col in display.columns:
        if col.startswith("ann_return_") or col.startswith("max_dd_"):
            display[col] = display[col].map(lambda x: pct(float(x)))
    lines.append(display.to_markdown(index=False))
    lines.append("")
    lines.append("## Stability Classification")
    lines.append("")
    lines.append("- Label: `same_slice_directional_only_non_qfq`")
    lines.append("- Evidence: all candidates share the same primary source, common trading calendar, cost model, and execution timing.")
    lines.append("- Data sensitivity: source is not qfq parity; repeat on restored qfq data before production promotion.")
    lines.append("- Recent-window behavior: full V1.1 remains strongest on full, 5Y, 3Y, and 1Y windows in this slice.")
    lines.append("")
    lines.append("## Decision")
    lines.append("")
    lines.append("- Decision: `research_only_no_promotion`")
    lines.append("- Recommended next action: rerun the same ablation on a restored qfq source before any live-trading parameter change.")
    lines.append("")
    (RUN_DIR / "record.md").write_text("\n".join(lines), encoding="utf-8")


def update_meta(summary: pd.DataFrame, sources: pd.DataFrame, validation: pd.DataFrame) -> None:
    meta_path = RUN_DIR / "scan_meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        meta = {}
    meta.update(
        {
            "run_id": RUN_ID,
            "phase": "results_written",
            "project": "SubD six ETF",
            "strategy": "V1.1",
            "subsystem": "ablation_chain",
            "repo_root": str(REPO_ROOT),
            "entrypoint": str(Path(__file__).relative_to(REPO_ROOT)),
            "git_branch": _git_value(["branch", "--show-current"]),
            "git_commit": _git_value(["rev-parse", "HEAD"]),
            "git_status_after_scan": _git_value(["status", "--short"]),
            "scan_type": "ablation_chain",
            "parameter_group": "same_slice_ablation",
            "baseline": {"candidate": CANDIDATES[-1].candidate},
            "candidate_grid": [candidate.__dict__ for candidate in CANDIDATES],
            "data_snapshot": {
                "primary_source": "akshare.fund_etf_hist_sina",
                "adjustment_policy": ADJUSTMENT_POLICY,
                "start_date": START_DATE.date().isoformat(),
                "eval_start": EVAL_START.date().isoformat(),
                "end_date": END_DATE.date().isoformat(),
                "sources": sources.to_dict(orient="records"),
                "validation": validation.to_dict(orient="records"),
            },
            "cost_model": {
                "one_way_cost": v11.ONE_WAY_COST,
                "execution_timing": "close_to_close",
                "target_vol": v11.TARGET_VOL,
                "vol_window": subd.DEFAULT_VOL_WINDOW,
                "max_leverage": subd.DEFAULT_MAX_LEV,
            },
            "outputs": {
                "record": str(RUN_DIR / "record.md"),
                "scan_summary": str(RUN_DIR / "scan_summary.csv"),
                "window_metrics": str(RUN_DIR / "window_metrics.csv"),
                "scan_meta": str(RUN_DIR / "scan_meta.json"),
                "command_log": str(RUN_DIR / "command_log.txt"),
                "daily_curves": str(RUN_DIR / "daily_curves.csv"),
                "sources": str(RUN_DIR / "sources.csv"),
                "data_quality": str(RUN_DIR / "data_quality.csv"),
                "source_validation": str(RUN_DIR / "source_validation.csv"),
            },
            "decision": "research_only_no_promotion",
            "stability_label": "same_slice_directional_only_non_qfq",
            "result_row_count": int(summary.shape[0]),
        }
    )
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    _append_command_log(
        "python quant_param_scan_runs/20260618_subd_v11_same_slice_ablation/run_scan.py\n"
        f"primary_source=akshare.fund_etf_hist_sina\nadjustment_policy={ADJUSTMENT_POLICY}\nend_date={END_DATE.date()}"
    )
    config = subd.RunConfig(
        source="sina",
        one_way_cost=v11.ONE_WAY_COST,
        start_date=START_DATE,
        end_date=END_DATE,
        output_tag=RUN_ID,
        target_vols=(),
        vol_window=subd.DEFAULT_VOL_WINDOW,
        max_lev=subd.DEFAULT_MAX_LEV,
    )
    prices, sources, quality = load_sina_split_adjusted_prices(END_DATE)
    validation = build_source_validation(prices, END_DATE)
    features = v11.build_overheat_features(prices)
    curves = [run_candidate(prices, config, features, candidate) for candidate in CANDIDATES]
    windows = build_windows(pd.DatetimeIndex(prices.index), END_DATE)
    summary_rows: list[dict[str, Any]] = []
    for candidate, curve in zip(CANDIDATES, curves, strict=True):
        for segment, (start, note) in windows.items():
            summary_rows.append(summarize_window(curve, candidate, segment, start, note))
    summary = pd.DataFrame(summary_rows)
    window_metrics = build_window_metrics(summary)
    daily = pd.concat(curves, axis=0).reset_index(names="date")
    _write_csv(summary, RUN_DIR / "scan_summary.csv")
    _write_csv(window_metrics, RUN_DIR / "window_metrics.csv")
    _write_csv(daily, RUN_DIR / "daily_curves.csv")
    _write_csv(sources, RUN_DIR / "sources.csv")
    _write_csv(quality, RUN_DIR / "data_quality.csv")
    _write_csv(validation, RUN_DIR / "source_validation.csv")
    write_record(summary, window_metrics, sources, validation)
    update_meta(summary, sources, validation)
    print("WROTE", RUN_DIR / "scan_summary.csv")
    print("WROTE", RUN_DIR / "window_metrics.csv")
    print(window_metrics.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
