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
import run_subd_proxy_dynamic_cyb_layer5_target_vol_scan as layer5
import run_subd_proxy_dynamic_cyb_r2none_layer4_staged_entry_scan as r2none_layer4
import run_subd_six_etf_v1_1 as v11


DEFAULT_START = pd.Timestamp("2007-01-01")
DEFAULT_END = pd.Timestamp("2016-12-30")
DEFAULT_RUN_FOLDER = Path(
    "quant_param_scan_runs"
    "/20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_r2_removed_branch_layer5_target_vol_after_r2_removed"
)

LINE_GRID: tuple[tuple[int, float, float, str], ...] = (
    (28, 1.15, 0.25, "main_line_r2_removed"),
    (28, 1.15, 0.75, "return_watch_line_r2_removed"),
)
TARGET_VOL_GRID: tuple[float | None, ...] = (None, 0.15, 0.18, 0.20, 0.22, 0.25, 0.28, 0.30, 0.35)
ONE_WAY_COST = 0.001
VOL_WINDOW = subd.DEFAULT_VOL_WINDOW
MAX_LEV = subd.DEFAULT_MAX_LEV
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


def pct(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value) * 100:.2f}%"


def fmt(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value):.2f}"


def candidate_label(lookback: int, switch_buffer: float, entry_fraction: float, target_vol: float | None) -> str:
    return (
        f"lb_{lookback}_r2_none_buf_{layer3.buffer_label(switch_buffer)}"
        f"_entry_{layer4.fraction_label(entry_fraction)}"
        f"_{layer5.target_vol_label(target_vol)}"
    )


def apply_target_vol_layer(
    base_curve: pd.DataFrame,
    lookback: int,
    switch_buffer: float,
    entry_fraction: float,
    target_vol: float | None,
    line_role: str,
    line_order: int,
) -> pd.DataFrame:
    if target_vol is None:
        curve = base_curve.copy()
        curve["target_vol_input_return"] = curve["return"].astype(float).fillna(0.0)
        curve["target_vol_input_nav"] = curve["nav"].astype(float)
        curve["base_gross_return"] = curve["gross_return"].astype(float).fillna(0.0)
        curve["base_return"] = curve["return"].astype(float).fillna(0.0)
        curve["base_nav"] = curve["nav"].astype(float)
        curve["base_turnover"] = curve["turnover"].astype(float).fillna(0.0)
        curve["base_cost"] = curve["cost"].astype(float).fillna(0.0)
        curve["virtual_base_realized_vol"] = np.nan
        curve["realized_vol"] = np.nan
        curve["target_vol_scale_effective"] = 1.0
        curve["target_vol_scale_next"] = 1.0
        curve["weight"] = 1.0
        curve["overheat_scale_effective"] = 1.0
        curve["overheat_scale_next"] = 1.0
        curve["overheat_scale"] = 1.0
        fraction_before = curve["fraction_before"].astype(float).fillna(0.0)
        holding_fraction = curve["holding_fraction"].astype(float).fillna(0.0)
        curve["exposure_effective"] = fraction_before.where(curve["position_before"].astype(str) != "CASH", 0.0)
        curve["final_exposure"] = holding_fraction.where(curve["position"].astype(str) != "CASH", 0.0)
        curve["final_exposure_after_overheat"] = curve["final_exposure"]
        curve["effective_trade_count"] = (curve["turnover"].astype(float).fillna(0.0) > 1e-12).cumsum()
        curve["target_vol"] = np.nan
    else:
        curve = v11.apply_target_vol_overlay(
            base_curve,
            float(target_vol),
            VOL_WINDOW,
            MAX_LEV,
            ONE_WAY_COST,
        ).copy()

    curve["candidate"] = candidate_label(lookback, switch_buffer, entry_fraction, target_vol)
    curve["line_role"] = line_role
    curve["line_order"] = int(line_order)
    curve["lookback"] = int(lookback)
    curve["r2_threshold"] = np.nan
    curve["r2_label"] = "none"
    curve["r2_execution_threshold"] = R2_EXEC_THRESHOLD_FOR_REMOVED
    curve["switch_buffer"] = float(switch_buffer)
    curve["buffer_label"] = layer3.buffer_label(switch_buffer)
    curve["entry_fraction"] = float(entry_fraction)
    curve["entry_label"] = layer4.fraction_label(entry_fraction)
    curve["target_vol_label"] = layer5.target_vol_label(target_vol)
    curve["target_vol"] = np.nan if target_vol is None else float(target_vol)
    curve["vol_window"] = VOL_WINDOW
    curve["max_lev"] = MAX_LEV
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
        "line_order": int(first["line_order"]),
        "lookback": int(first["lookback"]),
        "r2_threshold": np.nan,
        "r2_label": "none",
        "r2_execution_threshold": R2_EXEC_THRESHOLD_FOR_REMOVED,
        "switch_buffer": float(first["switch_buffer"]),
        "buffer_label": str(first["buffer_label"]),
        "entry_fraction": float(first["entry_fraction"]),
        "entry_label": str(first["entry_label"]),
        "target_vol": first["target_vol"],
        "target_vol_label": str(first["target_vol_label"]),
        "vol_window": int(first["vol_window"]),
        "max_lev": float(first["max_lev"]),
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
            "avg_scale_effective": np.nan,
            "avg_scale_next": np.nan,
            "avg_exposure_effective": np.nan,
            "avg_final_exposure": np.nan,
            "scale_change_days": np.nan,
            "avg_realized_vol": np.nan,
            "reason": reason,
        }

    sub = curve.loc[curve.index >= start].copy()
    ret = sub["return"].astype(float).fillna(0.0)
    wealth = (1.0 + ret).cumprod()
    years = len(sub) / TRADING_DAYS
    ann_vol = float(ret.std(ddof=0) * math.sqrt(TRADING_DAYS))
    sharpe = float(ret.mean() / ret.std(ddof=0) * math.sqrt(TRADING_DAYS)) if ret.std(ddof=0) > 0 else math.nan
    scale_next = sub["target_vol_scale_next"].astype(float).fillna(1.0)
    scale_effective = sub["target_vol_scale_effective"].astype(float).fillna(1.0)
    realized_vol = pd.to_numeric(sub["realized_vol"], errors="coerce").replace([np.inf, -np.inf], np.nan)
    return {
        **base,
        "start": sub.index[0].date().isoformat(),
        "rows": int(len(sub)),
        "ann_return": float(wealth.iloc[-1] ** (1.0 / years) - 1.0),
        "ann_vol": ann_vol,
        "max_dd": max_drawdown(wealth),
        "sharpe_repo": sharpe,
        "cash_days": int((sub["position"] == "CASH").sum()),
        "trades": int((sub["turnover"].astype(float).fillna(0.0) > 1e-12).sum()),
        "cost_total": float(sub["cost"].astype(float).fillna(0.0).sum()),
        "turnover_total": float(sub["turnover"].astype(float).fillna(0.0).sum()),
        "holding_day_ratio": float((sub["position"] != "CASH").mean()),
        "avg_holding_fraction": float(sub["holding_fraction"].astype(float).fillna(0.0).mean()),
        "avg_scale_effective": float(scale_effective.mean()),
        "avg_scale_next": float(scale_next.mean()),
        "avg_exposure_effective": float(sub["exposure_effective"].astype(float).fillna(0.0).mean()),
        "avg_final_exposure": float(sub["final_exposure_after_overheat"].astype(float).fillna(0.0).mean()),
        "scale_change_days": int((scale_next.diff().abs().fillna(0.0) > 1e-12).sum()),
        "avg_realized_vol": float(realized_vol.mean()) if realized_vol.notna().any() else np.nan,
        "reason": reason,
    }


def build_window_metrics(scan_summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for candidate, group in scan_summary.groupby("candidate", sort=False):
        first = group.iloc[0]
        baseline_candidate = candidate_label(
            int(first["lookback"]),
            float(first["switch_buffer"]),
            float(first["entry_fraction"]),
            None,
        )
        row: dict[str, object] = {
            "candidate": candidate,
            "baseline_candidate": baseline_candidate,
            "line_role": first["line_role"],
            "line_order": int(first["line_order"]),
            "lookback": int(first["lookback"]),
            "r2_threshold": np.nan,
            "r2_label": "none",
            "r2_execution_threshold": R2_EXEC_THRESHOLD_FOR_REMOVED,
            "switch_buffer": float(first["switch_buffer"]),
            "buffer_label": first["buffer_label"],
            "entry_fraction": float(first["entry_fraction"]),
            "entry_label": first["entry_label"],
            "target_vol": first["target_vol"],
            "target_vol_label": first["target_vol_label"],
            "vol_window": int(first["vol_window"]),
            "max_lev": float(first["max_lev"]),
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
                    "avg_scale_effective",
                    "avg_exposure_effective",
                    "avg_final_exposure",
                    "scale_change_days",
                    "avg_realized_vol",
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

    out = pd.DataFrame(rows)
    out["_tv_sort"] = out["target_vol"].fillna(-1.0)
    out = out.sort_values(["line_order", "_tv_sort"]).drop(columns=["_tv_sort"])
    return layer5.apply_pass_flags(out)


def select_by_line(window_metrics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for line_role, group in window_metrics.groupby("line_role", sort=False):
        passed = group[group["layer5_pass"].astype(bool)].copy()
        baseline = group[group["target_vol_label"].eq("no_tv")].iloc[0].to_dict()
        if passed.empty:
            selected = baseline
            selected["selection_role"] = "baseline_no_target_vol_pass"
        elif line_role.startswith("return_watch"):
            selected = passed.sort_values(["ann_return_full", "mdd_improve_full_pp"], ascending=[False, False]).iloc[0].to_dict()
            selected["selection_role"] = "return_watch_target_vol_pass"
        else:
            selected = passed.sort_values(["mdd_improve_full_pp", "ann_return_full"], ascending=[False, False]).iloc[0].to_dict()
            selected["selection_role"] = "selected_drawdown_target_vol_pass"
        rows.append(selected)
    return pd.DataFrame(rows)


def original_full_reference(prices: pd.DataFrame, end_date: pd.Timestamp) -> dict[str, object]:
    row = r2none_layer4.original_full_reference(prices, end_date)
    row["candidate_type"] = "original_full_v1_1_reference"
    row["target_vol"] = v11.TARGET_VOL
    row["target_vol_label"] = layer5.target_vol_label(v11.TARGET_VOL)
    row["notes"] = (
        "Full official V1.1 chain on this proxy panel; includes original lookback 25, "
        "R2 0.20, switch buffer 1.05, staged entry 0.50, target-vol 25%, and later overlays."
    )
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
        "target_vol": source.get("target_vol", np.nan),
        "target_vol_label": source.get("target_vol_label", ""),
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
    for _, row in window_metrics[window_metrics["target_vol_label"].eq("no_tv")].iterrows():
        rows.append(row_from_window(row.to_dict(), "line_baseline_no_target_vol", "Same carried line before target-vol layer"))
    for _, row in line_selection.iterrows():
        rows.append(row_from_window(row.to_dict(), str(row["selection_role"]), "Line-level selected target-vol result"))
    rows.append(full_reference)
    return pd.DataFrame(rows)


def daily_output_frame(curves: list[pd.DataFrame]) -> pd.DataFrame:
    keep = [
        "candidate",
        "line_role",
        "line_order",
        "lookback",
        "r2_label",
        "r2_execution_threshold",
        "switch_buffer",
        "entry_fraction",
        "target_vol_label",
        "target_vol",
        "vol_window",
        "max_lev",
        "position_before",
        "fraction_before",
        "position",
        "holding_fraction",
        "target_vol_scale_effective",
        "target_vol_scale_next",
        "realized_vol",
        "exposure_effective",
        "final_exposure_after_overheat",
        "pending_entry_target",
        "pending_entry_days",
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
        "effective_trade_count",
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
    display = window_metrics.sort_values(["line_order", "target_vol"], na_position="first")
    lines = [
        "# Sub-D Dynamic ChiNext Proxy R2-Removed Branch Layer 5 Target-Vol Scan",
        "",
        "## Run Metadata",
        "",
        f"- Run folder: `{run_folder}`",
        "- Layer: `Layer 5` after R2 removal, switch-buffer selection, and staged-entry selection.",
        "- Strategy: dynamic ChiNext proxy pool, 2007-2016.",
        "- Entrypoint: `run_subd_proxy_dynamic_cyb_r2none_layer5_target_vol_scan.py`",
        "",
        "## Research Question",
        "",
        "Test target-vol scaling on the two user-confirmed carried lines: main line `entry_0p25` and return watch line `entry_0p75`.",
        "",
        "## Implementation Anchor",
        "",
        "- Data loader reused from `run_subd_proxy_dynamic_cyb_layer0.py`.",
        "- Base curves reuse `run_subd_proxy_dynamic_cyb_r2none_layer4_staged_entry_scan.py`.",
        "- Target-vol behavior reuses `apply_target_vol_overlay` from `run_subd_six_etf_v1_1.py`.",
        "- No momentum decay, NAV defense, or overheat in this layer.",
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
        f"- Target-vol window: `{VOL_WINDOW}` trading days.",
        f"- Max leverage: `{MAX_LEV}`.",
        f"- Rebalance threshold: `{v11.TARGET_VOL_SCALE_REBALANCE_THRESHOLD}` scale points.",
        "- Calendar: A-share trading days; US adjusted closes are forward-filled onto that calendar for this proxy diagnostic.",
        "- Trades involving a forward-filled trade leg are blocked for that day.",
        "",
        "## Runtime Override Plan",
        "",
        f"- Lines: `{[(lb, buf, entry, role) for lb, buf, entry, role in LINE_GRID]}`.",
        f"- Target-vol grid: `{[layer5.target_vol_label(x) for x in TARGET_VOL_GRID]}`.",
        "- Baseline: same `lookback + switch buffer + entry fraction` with no target-vol overlay.",
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
        "- `daily_outputs/r2none_target_vol_daily_curves.csv`",
        "- `sources.csv`",
        "",
        "## Line-Level Selection",
        "",
        "| Line Role | Candidate | Selection | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | MDD Improve pp | Avg Scale Full | Pass Reason |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
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
            f"{fmt(row['mdd_improve_full_pp'])} | {fmt(row['avg_scale_effective_full'])} | {row['pass_reason']} |"
        )
    lines.extend(
        [
            "",
            "## Full-Sample Target-Vol Grid",
            "",
            "| Candidate | Line Role | Full Ann. | Full MDD | Full Ann Delta pp | Full MDD Improve pp | 5Y Ann. | 3Y Ann. | 1Y Ann. | Avg Scale Full | Avg Exposure Full | Pass | Reason |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for _, row in display.iterrows():
        lines.append(
            "| "
            f"`{row['candidate']}` | {row['line_role']} | {pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{fmt(row['ann_delta_full_pp'])} | {fmt(row['mdd_improve_full_pp'])} | "
            f"{pct(row['ann_return_last_5y'])} | {pct(row['ann_return_last_3y'])} | {pct(row['ann_return_last_1y'])} | "
            f"{fmt(row['avg_scale_effective_full'])} | {fmt(row['avg_exposure_effective_full'])} | "
            f"{bool(row['layer5_pass'])} | {row['pass_reason']} |"
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
            "- Decision: `line_level_selection_after_target_vol_on_r2_removed_branch`.",
            "- Stability label: `target_vol_pass_if_line_selection_uses_overlay_else_keep_previous`.",
            "- 10Y remains N/A by sample length and is not fabricated for strict scanner compatibility.",
            "",
            "## Decision",
            "",
            "- Keep each line's selected row from `line_selection.csv`.",
            "- Stop here before momentum decay, NAV defense, or overheat layers.",
            "",
            "## User-Facing Summary",
            "",
            "Layer 5 completed on the R2-removed branch. See line-level selection above for carried candidates.",
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
    for line_order, (lookback, switch_buffer, entry_fraction, line_role) in enumerate(LINE_GRID):
        base_curve = r2none_layer4.run_staged_line(
            prices,
            end_date,
            lookback,
            switch_buffer,
            entry_fraction,
            line_role,
        )
        for target_vol in TARGET_VOL_GRID:
            curve = apply_target_vol_layer(
                base_curve,
                lookback,
                switch_buffer,
                entry_fraction,
                target_vol,
                line_role,
                line_order,
            )
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
    daily.to_csv(daily_dir / "r2none_target_vol_daily_curves.csv", index=False, encoding="utf-8-sig")
    sources.to_csv(run_folder / "sources.csv", index=False, encoding="utf-8-sig")

    command = (
        "python run_subd_proxy_dynamic_cyb_r2none_layer5_target_vol_scan.py "
        f"--start-date {start_date.date()} --end-date {end_date.date()} --run-folder {run_folder}"
    )
    metadata_path = run_folder / "scan_meta.json"
    meta = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    meta.update(
        {
            "phase": "scan_complete_unfinalized",
            "scan_type": "layer5_target_vol_scan_after_r2_removed",
            "parameter_group": "layer5_target_vol_after_r2_removed",
            "baseline": {
                "rule": "same lookback + switch_buffer + entry_fraction with R2 removed and no target-vol",
                "line_baselines": [candidate_label(lb, buf, entry, None) for lb, buf, entry, _ in LINE_GRID],
            },
            "candidate_grid": [
                {
                    "lookback": int(lookback),
                    "switch_buffer": float(switch_buffer),
                    "entry_fraction": float(entry_fraction),
                    "line_role": line_role,
                    "r2_threshold": None,
                    "r2_execution_threshold": R2_EXEC_THRESHOLD_FOR_REMOVED,
                    "target_vol": None if target_vol is None else float(target_vol),
                }
                for lookback, switch_buffer, entry_fraction, line_role in LINE_GRID
                for target_vol in TARGET_VOL_GRID
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
            "cost_model": {
                "one_way_cost": ONE_WAY_COST,
                "stale_trade_guard": True,
                "target_vol_rebalance_cost_included": True,
            },
            "execution_assumptions": {
                "signal": "close-to-close weighted-slope ranking, score range 0..5, switch buffer, R2 removed",
                "r2_removed_execution": "r2 execution threshold is set to 0.0 in run_staged_entry; output labels use r2_none",
                "staged_entry": "enter new asset with selected initial fraction; fill to 100% on later down day if signal remains unchanged",
                "target_vol": "80-day realized vol, next-day effective scale, max leverage 1.5, scale rebalance threshold 0.075",
                "overlays": "none in this layer beyond switch buffer, staged entry, and target-vol",
                "mixed_market_calendar": "diagnostic A-share calendar with US proxy forward-filled; trades on stale trade legs blocked",
            },
            "pass_rule": {
                "mdd_improve_eps_pp": MDD_IMPROVE_EPS_PP,
                "available_windows": list(AVAILABLE_PASS_SEGMENTS),
                "return_lag_tolerance_pp": {"full": 1.0, "last_5y": 1.0, "last_3y": 3.0, "last_1y": 3.0},
            },
            "line_selection": json.loads(line_selection.to_json(orient="records")),
            "comparison_reference": {
                "original_full_strategy_candidate": "orig_full_v1_1_reference",
                "original_default_params": {
                    "lookback": subd.LOOKBACK,
                    "r2_threshold": v11.R2_THRESHOLD,
                    "switch_buffer": v11.SWITCH_BUFFER,
                    "entry_fraction": v11.INITIAL_ENTRY_FRACTION,
                    "target_vol": v11.TARGET_VOL,
                },
            },
            "outputs": {
                "scan_summary": str(run_folder / "scan_summary.csv"),
                "window_metrics": str(run_folder / "window_metrics.csv"),
                "line_selection": str(run_folder / "line_selection.csv"),
                "comparison_list": str(run_folder / "comparison_list.csv"),
                "daily_curves": str(daily_dir / "r2none_target_vol_daily_curves.csv"),
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
    print(f"WROTE {daily_dir / 'r2none_target_vol_daily_curves.csv'}")
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
        "avg_scale_effective_full",
        "layer5_pass",
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
