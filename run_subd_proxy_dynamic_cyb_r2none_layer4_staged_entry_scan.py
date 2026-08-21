from __future__ import annotations

import argparse
import json
import math
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd

import research_subd_six_etf_weighted_slope as subd
import run_subd_proxy_dynamic_cyb_layer0 as layer0
import run_subd_proxy_dynamic_cyb_layer1_scan as layer1
import run_subd_proxy_dynamic_cyb_layer2_r2_scan as layer2
import run_subd_proxy_dynamic_cyb_layer3_switch_buffer_scan as layer3
import run_subd_proxy_dynamic_cyb_layer4_staged_entry_scan as layer4
import run_subd_six_etf_v1_1 as v11


DEFAULT_START = pd.Timestamp("2007-01-01")
DEFAULT_END = pd.Timestamp("2016-12-30")
DEFAULT_RUN_FOLDER = Path(
    "quant_param_scan_runs"
    "/20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_r2_removed_branch_layer4_staged_entry_after_r2_removed"
)
LINE_GRID: tuple[tuple[int, float, str], ...] = (
    (28, 1.15, "primary_drawdown_r2_removed"),
    (28, 1.08, "return_watch_r2_removed"),
    (30, 1.03, "width_confirm_r2_removed"),
)
ENTRY_FRACTION_GRID = (1.00, 0.75, 0.67, 0.50, 0.33, 0.25)
ONE_WAY_COST = 0.001
TRADING_DAYS = 252
SEGMENTS = ("full", "last_10y", "last_5y", "last_3y", "last_1y")
AVAILABLE_PASS_SEGMENTS = ("full", "last_5y", "last_3y", "last_1y")
MDD_IMPROVE_EPS_PP = 0.01
R2_EXEC_THRESHOLD_FOR_REMOVED = 0.0


def git_value(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def candidate_label(lookback: int, switch_buffer: float, entry_fraction: float) -> str:
    return (
        f"lb_{lookback}_r2_none_buf_{layer3.buffer_label(switch_buffer)}"
        f"_entry_{layer4.fraction_label(entry_fraction)}"
    )


def pct(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value) * 100:.2f}%"


def fmt(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value):.2f}"


def run_staged_line(
    prices: pd.DataFrame,
    end_date: pd.Timestamp,
    lookback: int,
    switch_buffer: float,
    entry_fraction: float,
    line_role: str,
) -> pd.DataFrame:
    original_lookback = subd.LOOKBACK
    original_assets = dict(subd.ASSETS)
    try:
        subd.LOOKBACK = int(lookback)
        subd.ASSETS.clear()
        subd.ASSETS.update(layer0.PROXY_ASSETS)
        config = subd.RunConfig(
            source="proxy_dynamic_cyb",
            one_way_cost=ONE_WAY_COST,
            start_date=pd.Timestamp(prices.index[0]),
            end_date=end_date,
            output_tag="r2none_layer4_staged_entry",
            target_vols=(),
            vol_window=subd.DEFAULT_VOL_WINDOW,
            max_lev=subd.DEFAULT_MAX_LEV,
        )
        mode = "full_entry" if abs(float(entry_fraction) - 1.0) < 1e-12 else "all_new_asset_50_wait_down"
        case = v11.EntryCase(
            label=f"entry_{layer4.fraction_label(entry_fraction)}",
            mode=mode,  # type: ignore[arg-type]
            initial_fraction=float(entry_fraction),
        )
        curve = v11.run_staged_entry(
            prices,
            config,
            case,
            R2_EXEC_THRESHOLD_FOR_REMOVED,
            float(switch_buffer),
        ).copy()
    finally:
        subd.LOOKBACK = original_lookback
        subd.ASSETS.clear()
        subd.ASSETS.update(original_assets)

    curve.insert(0, "candidate", candidate_label(lookback, switch_buffer, entry_fraction))
    curve.insert(1, "line_role", line_role)
    curve.insert(2, "lookback", int(lookback))
    curve.insert(3, "r2_threshold", np.nan)
    curve.insert(4, "r2_label", "none")
    curve.insert(5, "r2_execution_threshold", R2_EXEC_THRESHOLD_FOR_REMOVED)
    curve.insert(6, "switch_buffer", float(switch_buffer))
    curve.insert(7, "buffer_label", layer3.buffer_label(switch_buffer))
    curve.insert(8, "entry_fraction", float(entry_fraction))
    curve.insert(9, "entry_label", layer4.fraction_label(entry_fraction))
    return curve


def max_drawdown(nav: pd.Series) -> float:
    peak = nav.astype(float).cummax().clip(lower=1.0)
    return float((nav.astype(float) / peak - 1.0).min())


def summarize_curve(
    curve: pd.DataFrame,
    segment: str,
    label: str,
    start: pd.Timestamp | None,
    reason: str,
) -> dict[str, object]:
    first = curve.iloc[0]
    base = {
        "candidate": str(first["candidate"]),
        "line_role": str(first["line_role"]),
        "lookback": int(first["lookback"]),
        "r2_threshold": np.nan,
        "r2_label": "none",
        "r2_execution_threshold": R2_EXEC_THRESHOLD_FOR_REMOVED,
        "switch_buffer": float(first["switch_buffer"]),
        "buffer_label": str(first["buffer_label"]),
        "entry_fraction": float(first["entry_fraction"]),
        "entry_label": str(first["entry_label"]),
        "segment": segment,
        "window": label,
        "end": curve.index[-1].date().isoformat(),
    }
    if start is None:
        return {
            **base,
            "start": "",
            "rows": np.nan,
            "ann_return": np.nan,
            "ann_vol": np.nan,
            "max_dd": np.nan,
            "sharpe_repo": np.nan,
            "cash_days": np.nan,
            "trades": np.nan,
            "cost_total": np.nan,
            "turnover_total": np.nan,
            "holding_day_ratio": np.nan,
            "avg_holding_fraction": np.nan,
            "partial_position_days": np.nan,
            "pending_days": np.nan,
            "staged_initials": np.nan,
            "staged_fills": np.nan,
            "reason": reason,
        }
    sub = curve.loc[curve.index >= start].copy()
    ret = sub["return"].astype(float).fillna(0.0)
    wealth = (1.0 + ret).cumprod()
    years = len(sub) / TRADING_DAYS
    ann_vol = float(ret.std(ddof=0) * math.sqrt(TRADING_DAYS))
    sharpe = float(ret.mean() / ret.std(ddof=0) * math.sqrt(TRADING_DAYS)) if ret.std(ddof=0) > 0 else math.nan
    holding_fraction = sub["holding_fraction"].astype(float).fillna(0.0)
    return {
        **base,
        "start": sub.index[0].date().isoformat(),
        "rows": int(len(sub)),
        "ann_return": float(wealth.iloc[-1] ** (1.0 / years) - 1.0),
        "ann_vol": ann_vol,
        "max_dd": max_drawdown(wealth),
        "sharpe_repo": sharpe,
        "cash_days": int((sub["position"] == "CASH").sum()),
        "trades": int((sub["turnover"].astype(float) > 1e-12).sum()),
        "cost_total": float(sub["cost"].sum()),
        "turnover_total": float(sub["turnover"].sum()),
        "holding_day_ratio": float((sub["position"] != "CASH").mean()),
        "avg_holding_fraction": float(holding_fraction.mean()),
        "partial_position_days": int(((holding_fraction > 1e-12) & (holding_fraction < 1.0 - 1e-12)).sum()),
        "pending_days": int(sub["pending_entry_target"].notna().sum()),
        "staged_initials": int(sub["staged_initial"].astype(bool).sum()),
        "staged_fills": int(sub["fill_on_down_day"].astype(bool).sum()),
        "reason": reason,
    }


def build_window_metrics(scan_summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for candidate, group in scan_summary.groupby("candidate", sort=False):
        first = group.iloc[0]
        baseline_candidate = candidate_label(
            int(first["lookback"]),
            float(first["switch_buffer"]),
            1.0,
        )
        row: dict[str, object] = {
            "candidate": candidate,
            "baseline_candidate": baseline_candidate,
            "line_role": first["line_role"],
            "lookback": int(first["lookback"]),
            "r2_threshold": np.nan,
            "r2_label": "none",
            "r2_execution_threshold": R2_EXEC_THRESHOLD_FOR_REMOVED,
            "switch_buffer": float(first["switch_buffer"]),
            "buffer_label": first["buffer_label"],
            "entry_fraction": float(first["entry_fraction"]),
            "entry_label": first["entry_label"],
        }
        for segment in SEGMENTS:
            sub = group[group["segment"].eq(segment)]
            if sub.empty:
                row[f"ann_return_{segment}"] = np.nan
                row[f"max_dd_{segment}"] = np.nan
                row[f"reason_{segment}"] = "missing segment"
            else:
                source = sub.iloc[0]
                for col in (
                    "ann_return",
                    "ann_vol",
                    "max_dd",
                    "sharpe_repo",
                    "trades",
                    "cost_total",
                    "turnover_total",
                    "holding_day_ratio",
                    "avg_holding_fraction",
                    "partial_position_days",
                    "pending_days",
                    "staged_initials",
                    "staged_fills",
                ):
                    row[f"{col}_{segment}"] = source[col]
                row[f"reason_{segment}"] = source["reason"]

        base_rows = scan_summary[scan_summary["candidate"].eq(baseline_candidate)]
        for segment in SEGMENTS:
            base_sub = base_rows[base_rows["segment"].eq(segment)]
            if base_sub.empty:
                row[f"ann_delta_{segment}_pp"] = np.nan
                row[f"mdd_improve_{segment}_pp"] = np.nan
                row[f"trade_delta_{segment}"] = np.nan
            else:
                base = base_sub.iloc[0]
                ann = row.get(f"ann_return_{segment}", np.nan)
                dd = row.get(f"max_dd_{segment}", np.nan)
                trades = row.get(f"trades_{segment}", np.nan)
                row[f"ann_delta_{segment}_pp"] = (
                    (ann - base["ann_return"]) * 100.0 if pd.notna(ann) and pd.notna(base["ann_return"]) else np.nan
                )
                row[f"mdd_improve_{segment}_pp"] = (
                    (dd - base["max_dd"]) * 100.0 if pd.notna(dd) and pd.notna(base["max_dd"]) else np.nan
                )
                row[f"trade_delta_{segment}"] = (
                    trades - base["trades"] if pd.notna(trades) and pd.notna(base["trades"]) else np.nan
                )
        rows.append(row)
    out = pd.DataFrame(rows).sort_values(["line_role", "entry_fraction"], ascending=[True, False])
    return apply_pass_flags(out)


def apply_pass_flags(window_metrics: pd.DataFrame) -> pd.DataFrame:
    out = window_metrics.copy()
    pass_rows = []
    for _, row in out.iterrows():
        if abs(float(row["entry_fraction"]) - 1.0) < 1e-12:
            pass_rows.append(
                {
                    "dd_improve_window_count": 0,
                    "return_tolerance_ok": False,
                    "full_mdd_improved": False,
                    "layer4_pass": False,
                    "pass_reason": "baseline/full entry",
                }
            )
            continue
        dd_count = 0
        tolerance_ok = True
        for segment in AVAILABLE_PASS_SEGMENTS:
            mdd_improve = row.get(f"mdd_improve_{segment}_pp", np.nan)
            ann_delta = row.get(f"ann_delta_{segment}_pp", np.nan)
            if pd.notna(mdd_improve) and float(mdd_improve) > MDD_IMPROVE_EPS_PP:
                dd_count += 1
            tolerance = 1.0 if segment in {"full", "last_5y"} else 3.0
            if pd.isna(ann_delta) or float(ann_delta) < -tolerance:
                tolerance_ok = False
        full_mdd = row.get("mdd_improve_full_pp", np.nan)
        full_mdd_improved = bool(pd.notna(full_mdd) and float(full_mdd) > MDD_IMPROVE_EPS_PP)
        layer4_pass = bool(full_mdd_improved and dd_count >= 3 and tolerance_ok)
        reason = "pass" if layer4_pass else f"full_mdd={full_mdd_improved};dd_windows={dd_count};return_tol={tolerance_ok}"
        pass_rows.append(
            {
                "dd_improve_window_count": dd_count,
                "return_tolerance_ok": tolerance_ok,
                "full_mdd_improved": full_mdd_improved,
                "layer4_pass": layer4_pass,
                "pass_reason": reason,
            }
        )
    return pd.concat([out.reset_index(drop=True), pd.DataFrame(pass_rows)], axis=1)


def select_by_line(window_metrics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for line_role, group in window_metrics.groupby("line_role", sort=False):
        passed = group[group["layer4_pass"].astype(bool)].copy()
        if not passed.empty:
            selected = passed.sort_values(["mdd_improve_full_pp", "ann_return_full"], ascending=[False, False]).iloc[0].to_dict()
            selected["selection_role"] = "selected_drawdown_pass"
        else:
            selected = group[group["entry_fraction"].eq(1.0)].iloc[0].to_dict()
            selected["selection_role"] = "baseline_no_staged_entry_pass"
        return_passed = group[group["layer4_pass"].astype(bool)].copy()
        if not return_passed.empty:
            return_watch = return_passed.sort_values(["ann_return_full", "mdd_improve_full_pp"], ascending=[False, False]).iloc[0].to_dict()
            return_watch["selection_role"] = "return_watch_pass"
            if return_watch["candidate"] != selected["candidate"]:
                rows.append(return_watch)
        rows.append(selected)
    return pd.DataFrame(rows)


def original_full_reference(prices: pd.DataFrame, end_date: pd.Timestamp) -> dict[str, object]:
    row = layer2.original_full_reference(prices, end_date)
    row["candidate_type"] = "original_full_strategy_reference"
    row["lookback"] = 25
    row["r2_threshold"] = 0.20
    row["switch_buffer"] = 1.05
    row["entry_fraction"] = 0.50
    row["notes"] = "Full official V1.1 chain; context only, not Layer4 pass baseline"
    return row


def row_from_window(source: dict[str, object], ctype: str, notes: str) -> dict[str, object]:
    row = {
        "candidate": source["candidate"],
        "candidate_type": ctype,
        "line_role": source.get("line_role", ""),
        "lookback": source.get("lookback", ""),
        "r2_threshold": source.get("r2_threshold", np.nan),
        "switch_buffer": source.get("switch_buffer", np.nan),
        "entry_fraction": source.get("entry_fraction", np.nan),
        "notes": notes,
    }
    for segment in SEGMENTS:
        row[f"ann_return_{segment}"] = source.get(f"ann_return_{segment}", np.nan)
        row[f"max_dd_{segment}"] = source.get(f"max_dd_{segment}", np.nan)
        row[f"reason_{segment}"] = source.get(f"reason_{segment}", "")
    return row


def build_comparison_list(
    window_metrics: pd.DataFrame,
    line_selection: pd.DataFrame,
    full_reference: dict[str, object],
) -> pd.DataFrame:
    rows = []
    for _, row in window_metrics[window_metrics["entry_fraction"].eq(1.0)].iterrows():
        rows.append(row_from_window(row.to_dict(), "line_baseline_full_entry", "Line baseline before staged-entry layer"))
    for _, row in line_selection.iterrows():
        rows.append(row_from_window(row.to_dict(), str(row["selection_role"]), "Line-level selected/watch staged-entry candidate"))
    rows.append(full_reference)
    return pd.DataFrame(rows)


def daily_output_frame(curves: list[pd.DataFrame]) -> pd.DataFrame:
    keep = [
        "candidate",
        "line_role",
        "lookback",
        "r2_label",
        "r2_execution_threshold",
        "switch_buffer",
        "entry_fraction",
        "position_before",
        "fraction_before",
        "position",
        "holding_fraction",
        "pending_entry_target",
        "pending_entry_since",
        "pending_entry_days",
        "trade_target",
        "trade_fraction",
        "staged_initial",
        "fill_on_down_day",
        "best_candidate",
        "best_candidate_score",
        "current_score",
        "buffer_blocked",
        "trade_blocked_by_stale_price",
        "asset_return",
        "gross_return",
        "turnover",
        "cost",
        "return",
        "nav",
        "trade_count",
    ]
    return pd.concat([curve[[col for col in keep if col in curve.columns]] for curve in curves], axis=0).reset_index()


def write_record(
    run_folder: Path,
    window_metrics: pd.DataFrame,
    line_selection: pd.DataFrame,
    comparison_list: pd.DataFrame,
    sources: pd.DataFrame,
    meta: dict[str, object],
) -> None:
    lines = [
        "# Sub-D Dynamic ChiNext Proxy R2-Removed Branch Layer 4 Staged-Entry Scan",
        "",
        "## Run Metadata",
        "",
        f"- Run folder: `{run_folder}`",
        "- Layer: `Layer 4` after resetting Layer 2 to `R2 removed` and Layer 3 to selected switch-buffer lines.",
        "- Strategy: dynamic ChiNext proxy pool, 2007-2016.",
        "- Entrypoint: `run_subd_proxy_dynamic_cyb_r2none_layer4_staged_entry_scan.py`",
        "",
        "## Research Question",
        "",
        "After removing R2 and selecting switch-buffer lines, test whether staged entry improves drawdown without excessive return drag.",
        "",
        "## Implementation Anchor",
        "",
        "- Data loader reused from `run_subd_proxy_dynamic_cyb_layer0.py`.",
        "- Staged-entry behavior reuses `EntryCase` and `run_staged_entry` from `run_subd_six_etf_v1_1.py`.",
        "- `R2` is labeled removed; execution threshold is `0.0`, equivalent to no positive R2 filter for this weighted-slope score path.",
        "- No target-vol, momentum decay, NAV defense, or overheat in this layer.",
        "",
        "## Data Snapshot",
        "",
        f"- Start/end: `{meta['data_snapshot']['start']}` to `{meta['data_snapshot']['end']}`.",
        f"- Rows: `{meta['data_snapshot']['rows']}`.",
        "- Pool: QQQ/EWG/EWJ/GLD from 2007 start; ChiNext joins when its own data exists.",
        "",
        "## Cost and Execution Assumptions",
        "",
        f"- One-way cost: `{ONE_WAY_COST}`.",
        "- Calendar: A-share trading days; US adjusted closes are forward-filled onto that calendar for this proxy diagnostic.",
        "- Trades involving a forward-filled trade leg are blocked for that day.",
        "",
        "## Runtime Override Plan",
        "",
        f"- Lines: `{[(lb, buf, role) for lb, buf, role in LINE_GRID]}`.",
        f"- Entry-fraction grid: `{[layer4.fraction_label(x) for x in ENTRY_FRACTION_GRID]}`.",
        "- Baseline: same line with `entry_full`.",
        f"- Pass rule: Full maxDD improves by more than `{MDD_IMPROVE_EPS_PP:.2f}pp`; at least 3 of 4 available windows improve maxDD; Full/5Y annualized return lag <=1pp and 3Y/1Y lag <=3pp.",
        "",
        "## Commands",
        "",
        f"- `{meta['command']}`",
        "",
        "## Output Files",
        "",
        "- `scan_summary.csv`",
        "- `window_metrics.csv`",
        "- `line_selection.csv`",
        "- `comparison_list.csv`",
        "- `daily_outputs/r2none_staged_entry_daily_curves.csv`",
        "- `sources.csv`",
        "",
        "## Line-Level Selection",
        "",
        "| Line Role | Candidate | Selection | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | MDD Improve pp | Pass Reason |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for _, row in line_selection.iterrows():
        lines.append(
            "| "
            f"{row['line_role']} | `{row['candidate']}` | {row['selection_role']} | "
            f"{pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{pct(row['ann_return_last_10y'])} | {pct(row['max_dd_last_10y'])} | "
            f"{pct(row['ann_return_last_5y'])} | {pct(row['max_dd_last_5y'])} | "
            f"{pct(row['ann_return_last_3y'])} | {pct(row['max_dd_last_3y'])} | "
            f"{pct(row['ann_return_last_1y'])} | {pct(row['max_dd_last_1y'])} | "
            f"{fmt(row['mdd_improve_full_pp'])} | {row['pass_reason']} |"
        )
    lines.extend(
        [
            "",
            "## Full-Sample Results",
            "",
            "| Candidate | Line Role | Full Ann. | Full MDD | Full Ann Delta pp | Full MDD Improve pp | 5Y Ann. | 3Y Ann. | 1Y Ann. | Partial Days Full | Staged Fills Full | Pass | Reason |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    display = window_metrics.sort_values(["line_role", "entry_fraction"], ascending=[True, False])
    for _, row in display.iterrows():
        lines.append(
            "| "
            f"`{row['candidate']}` | {row['line_role']} | {pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{fmt(row['ann_delta_full_pp'])} | {fmt(row['mdd_improve_full_pp'])} | "
            f"{pct(row['ann_return_last_5y'])} | {pct(row['ann_return_last_3y'])} | {pct(row['ann_return_last_1y'])} | "
            f"{int(row['partial_position_days_full']) if pd.notna(row['partial_position_days_full']) else 'N/A'} | "
            f"{int(row['staged_fills_full']) if pd.notna(row['staged_fills_full']) else 'N/A'} | "
            f"{bool(row['layer4_pass'])} | {row['pass_reason']} |"
        )
    lines.extend(
        [
            "",
            "## Comparison List",
            "",
            "| Candidate | Type | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Notes |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for _, row in comparison_list.iterrows():
        lines.append(
            "| "
            f"`{row['candidate']}` | {row['candidate_type']} | "
            f"{pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{pct(row['ann_return_last_10y'])} | {pct(row['max_dd_last_10y'])} | "
            f"{pct(row['ann_return_last_5y'])} | {pct(row['max_dd_last_5y'])} | "
            f"{pct(row['ann_return_last_3y'])} | {pct(row['max_dd_last_3y'])} | "
            f"{pct(row['ann_return_last_1y'])} | {pct(row['max_dd_last_1y'])} | {row['notes']} |"
        )
    lines.extend(
        [
            "",
            "## Stability Classification",
            "",
            "- Decision: `line_level_selection_after_staged_entry`.",
            "- Stability label: `mixed_pass_keep_line_baselines_when_staged_fails`.",
            "- 10Y remains N/A by sample length and is not fabricated for strict scanner compatibility.",
            "",
            "## Decision",
            "",
            "- Keep each line's selected row from `line_selection.csv`.",
            "- Stop here before target-vol, momentum decay, NAV defense, or overheat layers.",
            "",
            "## User-Facing Summary",
            "",
            "Layer 4 completed on the R2-removed branch. See line-level selection above for the carried candidates.",
            "",
            "## Source Audit",
            "",
            sources.to_markdown(index=False),
            "",
        ]
    )
    (run_folder / "record.md").write_text("\n".join(lines), encoding="utf-8")


def run_scan(start_date: pd.Timestamp, end_date: pd.Timestamp, run_folder: Path) -> None:
    started = time.time()
    run_folder.mkdir(parents=True, exist_ok=True)
    daily_dir = run_folder / "daily_outputs"
    daily_dir.mkdir(parents=True, exist_ok=True)

    prices, sources = layer0.build_proxy_panel(start_date, end_date)
    curves = []
    summary_rows = []
    for lookback, switch_buffer, line_role in LINE_GRID:
        for entry_fraction in ENTRY_FRACTION_GRID:
            curve = run_staged_line(prices, end_date, lookback, switch_buffer, entry_fraction, line_role)
            curves.append(curve)
            for segment, label, start, reason in layer1.window_specs(prices.index):
                summary_rows.append(summarize_curve(curve, segment, label, start, reason))

    scan_summary = pd.DataFrame(summary_rows)
    window_metrics = build_window_metrics(scan_summary)
    line_selection = select_by_line(window_metrics)
    full_reference = original_full_reference(prices, end_date)
    comparison_list = build_comparison_list(window_metrics, line_selection, full_reference)
    daily = daily_output_frame(curves)

    scan_summary.to_csv(run_folder / "scan_summary.csv", index=False, encoding="utf-8-sig")
    window_metrics.to_csv(run_folder / "window_metrics.csv", index=False, encoding="utf-8-sig")
    line_selection.to_csv(run_folder / "line_selection.csv", index=False, encoding="utf-8-sig")
    comparison_list.to_csv(run_folder / "comparison_list.csv", index=False, encoding="utf-8-sig")
    daily.to_csv(daily_dir / "r2none_staged_entry_daily_curves.csv", index=False, encoding="utf-8-sig")
    sources.to_csv(run_folder / "sources.csv", index=False, encoding="utf-8-sig")

    command = (
        "python run_subd_proxy_dynamic_cyb_r2none_layer4_staged_entry_scan.py "
        f"--start-date {start_date.date()} --end-date {end_date.date()} --run-folder {run_folder}"
    )
    metadata_path = run_folder / "scan_meta.json"
    meta = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    meta.update(
        {
            "phase": "scan_complete_unfinalized",
            "scan_type": "layer4_staged_entry_scan_after_r2_removed",
            "parameter_group": "layer4_staged_entry_after_r2_removed",
            "baseline": {
                "rule": "same lookback + switch_buffer with R2 removed and entry_fraction=1.00",
                "line_baselines": [candidate_label(lb, buf, 1.00) for lb, buf, _ in LINE_GRID],
            },
            "candidate_grid": [
                {
                    "lookback": int(lookback),
                    "switch_buffer": float(switch_buffer),
                    "line_role": line_role,
                    "r2_threshold": None,
                    "r2_execution_threshold": R2_EXEC_THRESHOLD_FOR_REMOVED,
                    "entry_fraction": float(entry_fraction),
                }
                for lookback, switch_buffer, line_role in LINE_GRID
                for entry_fraction in ENTRY_FRACTION_GRID
            ],
            "data_snapshot": {
                "start": pd.Timestamp(prices.index[0]).date().isoformat(),
                "end": pd.Timestamp(prices.index[-1]).date().isoformat(),
                "rows": int(len(prices)),
                "calendar": "A-share trading-day cache",
                "pool_rule": "QQQ/EWG/EWJ/GLD from 2007 start; CN_CYB_399006 joins from own data with no backfill",
                "ffill_counts_on_cn_calendar": {
                    code: int(prices.attrs["price_ffill_flags"][code].sum()) for code in prices.columns
                },
            },
            "cost_model": {"one_way_cost": ONE_WAY_COST, "stale_trade_guard": True},
            "execution_assumptions": {
                "signal": "close-to-close weighted-slope ranking, score range 0..5, switch buffer, R2 removed",
                "r2_removed_execution": "r2 execution threshold is set to 0.0 in run_staged_entry; output labels use r2_none",
                "staged_entry": "enter new asset with initial fraction; fill to 100% on later down day if signal remains unchanged",
                "overlays": "none in this layer beyond switch buffer and staged entry",
                "mixed_market_calendar": "diagnostic A-share calendar with US proxy forward-filled; trades on stale trade legs blocked",
            },
            "pass_rule": {
                "mdd_improve_eps_pp": MDD_IMPROVE_EPS_PP,
                "available_windows": list(AVAILABLE_PASS_SEGMENTS),
                "return_lag_tolerance_pp": {"full": 1.0, "last_5y": 1.0, "last_3y": 3.0, "last_1y": 3.0},
            },
            "line_selection": json.loads(line_selection.to_json(orient="records")),
            "outputs": {
                "scan_summary": str(run_folder / "scan_summary.csv"),
                "window_metrics": str(run_folder / "window_metrics.csv"),
                "line_selection": str(run_folder / "line_selection.csv"),
                "comparison_list": str(run_folder / "comparison_list.csv"),
                "daily_curves": str(daily_dir / "r2none_staged_entry_daily_curves.csv"),
                "sources": str(run_folder / "sources.csv"),
                "record": str(run_folder / "record.md"),
                "scan_meta": str(run_folder / "scan_meta.json"),
                "command_log": str(run_folder / "command_log.txt"),
            },
            "git_branch_after": git_value(["branch", "--show-current"]),
            "git_commit_after": git_value(["rev-parse", "HEAD"]),
            "git_status_after": git_value(["status", "--short"]),
            "command": command,
            "elapsed_sec": round(time.time() - started, 3),
        }
    )
    metadata_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    write_record(run_folder, window_metrics, line_selection, comparison_list, sources, meta)

    with (run_folder / "command_log.txt").open("a", encoding="utf-8") as fh:
        fh.write("\n[scan]\n")
        fh.write(f"cwd={Path.cwd()}\n")
        fh.write(command + "\n")
        fh.write(f"elapsed_sec={meta['elapsed_sec']}\n")

    print(f"WROTE {run_folder / 'scan_summary.csv'}")
    print(f"WROTE {run_folder / 'window_metrics.csv'}")
    print(f"WROTE {run_folder / 'line_selection.csv'}")
    print(f"WROTE {run_folder / 'comparison_list.csv'}")
    print(f"WROTE {daily_dir / 'r2none_staged_entry_daily_curves.csv'}")
    display_cols = [
        "line_role",
        "candidate",
        "selection_role",
        "ann_return_full",
        "max_dd_full",
        "ann_delta_full_pp",
        "mdd_improve_full_pp",
        "ann_return_last_5y",
        "max_dd_last_5y",
        "ann_return_last_3y",
        "max_dd_last_3y",
        "ann_return_last_1y",
        "max_dd_last_1y",
        "layer4_pass",
        "pass_reason",
    ]
    print(line_selection[display_cols].to_string(index=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", default=str(DEFAULT_START.date()))
    parser.add_argument("--end-date", default=str(DEFAULT_END.date()))
    parser.add_argument("--run-folder", default=str(DEFAULT_RUN_FOLDER))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_scan(pd.Timestamp(args.start_date), pd.Timestamp(args.end_date), Path(args.run_folder))


if __name__ == "__main__":
    main()
