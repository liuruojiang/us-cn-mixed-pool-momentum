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
    "/20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_target_vol_layer5_target_vol"
)
PRIMARY_LOOKBACK = 28
PRIMARY_R2 = 0.50
PRIMARY_SWITCH_BUFFER = 1.00
PRIMARY_ENTRY_FRACTION = 0.75
LINE_GRID: tuple[tuple[int, float, float, float, str], ...] = (
    (28, 0.50, 1.00, 0.75, "layer4_primary"),
    (28, 0.50, 1.00, 0.67, "entry_neighbor"),
    (28, 0.40, 1.00, 0.75, "r2_neighbor"),
    (32, 0.50, 1.00, 0.75, "return_peak_watch"),
    (25, 0.20, 1.05, 0.50, "original_layer5"),
)
TARGET_VOL_GRID: tuple[float | None, ...] = (None, 0.15, 0.18, 0.20, 0.22, 0.25, 0.28, 0.30, 0.35)
ONE_WAY_COST = 0.001
VOL_WINDOW = subd.DEFAULT_VOL_WINDOW
MAX_LEV = subd.DEFAULT_MAX_LEV
TRADING_DAYS = 252
SEGMENTS = ("full", "last_10y", "last_5y", "last_3y", "last_1y")
AVAILABLE_PASS_SEGMENTS = ("full", "last_5y", "last_3y", "last_1y")
MDD_IMPROVE_EPS_PP = 0.01


def git_value(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def target_vol_label(value: float | None) -> str:
    if value is None:
        return "no_tv"
    return f"tv{int(round(float(value) * 100)):02d}"


def candidate_label(
    lookback: int,
    r2_threshold: float,
    switch_buffer: float,
    entry_fraction: float,
    target_vol: float | None,
) -> str:
    return (
        f"lb_{lookback}_r2_{layer2.r2_label(r2_threshold)}"
        f"_buf_{layer3.buffer_label(switch_buffer)}"
        f"_entry_{layer4.fraction_label(entry_fraction)}"
        f"_{target_vol_label(target_vol)}"
    )


def apply_target_vol_layer(
    base_curve: pd.DataFrame,
    lookback: int,
    r2_threshold: float,
    switch_buffer: float,
    entry_fraction: float,
    target_vol: float | None,
    line_role: str,
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

    curve["candidate"] = candidate_label(lookback, r2_threshold, switch_buffer, entry_fraction, target_vol)
    curve["line_role"] = line_role
    curve["lookback"] = int(lookback)
    curve["r2_threshold"] = float(r2_threshold)
    curve["r2_label"] = layer2.r2_label(r2_threshold)
    curve["switch_buffer"] = float(switch_buffer)
    curve["buffer_label"] = layer3.buffer_label(switch_buffer)
    curve["entry_fraction"] = float(entry_fraction)
    curve["entry_label"] = layer4.fraction_label(entry_fraction)
    curve["target_vol_label"] = target_vol_label(target_vol)
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
        "lookback": int(first["lookback"]),
        "r2_threshold": float(first["r2_threshold"]),
        "r2_label": str(first["r2_label"]),
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
            float(first["r2_threshold"]),
            float(first["switch_buffer"]),
            float(first["entry_fraction"]),
            None,
        )
        row: dict[str, object] = {
            "candidate": candidate,
            "baseline_candidate": baseline_candidate,
            "line_role": first["line_role"],
            "lookback": int(first["lookback"]),
            "r2_threshold": float(first["r2_threshold"]),
            "r2_label": first["r2_label"],
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
                row[f"ann_return_{segment}"] = source["ann_return"]
                row[f"max_dd_{segment}"] = source["max_dd"]
                row[f"reason_{segment}"] = source["reason"]
                row[f"trades_{segment}"] = source["trades"]
                row[f"cost_total_{segment}"] = source["cost_total"]
                row[f"turnover_total_{segment}"] = source["turnover_total"]
                row[f"avg_scale_effective_{segment}"] = source["avg_scale_effective"]
                row[f"avg_exposure_effective_{segment}"] = source["avg_exposure_effective"]
                row[f"scale_change_days_{segment}"] = source["scale_change_days"]
                row[f"avg_realized_vol_{segment}"] = source["avg_realized_vol"]

        base_rows = scan_summary[scan_summary["candidate"].eq(baseline_candidate)]
        for segment in SEGMENTS:
            base_sub = base_rows[base_rows["segment"].eq(segment)]
            if base_sub.empty:
                row[f"ann_delta_{segment}_pp"] = np.nan
                row[f"mdd_improve_{segment}_pp"] = np.nan
                row[f"trade_delta_{segment}"] = np.nan
            else:
                base = base_sub.iloc[0]
                ann = row[f"ann_return_{segment}"]
                dd = row[f"max_dd_{segment}"]
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
    out = out.sort_values(["lookback", "r2_threshold", "switch_buffer", "entry_fraction", "_tv_sort"]).drop(columns=["_tv_sort"])
    return apply_pass_flags(out)


def apply_pass_flags(window_metrics: pd.DataFrame) -> pd.DataFrame:
    out = window_metrics.copy()
    pass_rows = []
    for _, row in out.iterrows():
        if str(row["target_vol_label"]) == "no_tv":
            pass_rows.append(
                {
                    "dd_improve_window_count": 0,
                    "return_tolerance_ok": False,
                    "full_mdd_improved": False,
                    "layer5_pass": False,
                    "pass_reason": "baseline/no target-vol",
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
        layer5_pass = bool(full_mdd_improved and dd_count >= 3 and tolerance_ok)
        reason = "pass" if layer5_pass else f"full_mdd={full_mdd_improved};dd_windows={dd_count};return_tol={tolerance_ok}"
        pass_rows.append(
            {
                "dd_improve_window_count": dd_count,
                "return_tolerance_ok": tolerance_ok,
                "full_mdd_improved": full_mdd_improved,
                "layer5_pass": layer5_pass,
                "pass_reason": reason,
            }
        )
    return pd.concat([out.reset_index(drop=True), pd.DataFrame(pass_rows)], axis=1)


def select_candidate(window_metrics: pd.DataFrame) -> dict[str, object]:
    passed = window_metrics[window_metrics["layer5_pass"].astype(bool)].copy()
    primary_passed = passed[
        passed["lookback"].eq(PRIMARY_LOOKBACK)
        & passed["r2_threshold"].eq(PRIMARY_R2)
        & passed["switch_buffer"].eq(PRIMARY_SWITCH_BUFFER)
        & passed["entry_fraction"].eq(PRIMARY_ENTRY_FRACTION)
    ].copy()
    if not primary_passed.empty:
        selected = primary_passed.sort_values(
            ["ann_return_full", "mdd_improve_full_pp"],
            ascending=[False, False],
        ).iloc[0].to_dict()
        decision = "carry_forward_primary_target_vol_pass"
        stability = "primary_pass"
    else:
        primary_baseline = window_metrics[
            window_metrics["lookback"].eq(PRIMARY_LOOKBACK)
            & window_metrics["r2_threshold"].eq(PRIMARY_R2)
            & window_metrics["switch_buffer"].eq(PRIMARY_SWITCH_BUFFER)
            & window_metrics["entry_fraction"].eq(PRIMARY_ENTRY_FRACTION)
            & window_metrics["target_vol_label"].eq("no_tv")
        ]
        selected = primary_baseline.iloc[0].to_dict()
        if not passed.empty:
            decision = "do_not_add_target_vol_keep_layer4_primary_watch_nonprimary"
            stability = "nonprimary_watch_only"
        else:
            decision = "do_not_add_target_vol_keep_layer4_primary"
            stability = "no_pass_keep_previous"
    result = {"selected": selected, "decision": decision, "stability_label": stability}
    if not passed.empty:
        result["best_nonprimary_pass"] = passed.sort_values(
            ["ann_return_full", "mdd_improve_full_pp"],
            ascending=[False, False],
        ).iloc[0].to_dict()
    return result


def original_full_reference(prices: pd.DataFrame, end_date: pd.Timestamp) -> dict[str, object]:
    row = layer2.original_full_reference(prices, end_date)
    row["candidate_type"] = "original_full_strategy_reference"
    row["notes"] = "Full official V1.1 chain including overheat; reference only, not Layer5 pass baseline"
    return row


def row_from_window(source: dict[str, object], candidate: str, ctype: str, notes: str) -> dict[str, object]:
    row = {
        "candidate": candidate,
        "candidate_type": ctype,
        "lookback": source["lookback"],
        "r2_threshold": source["r2_threshold"],
        "switch_buffer": source["switch_buffer"],
        "entry_fraction": source["entry_fraction"],
        "target_vol": source["target_vol"],
        "notes": notes,
    }
    for segment in SEGMENTS:
        row[f"ann_return_{segment}"] = source[f"ann_return_{segment}"]
        row[f"max_dd_{segment}"] = source[f"max_dd_{segment}"]
        row[f"reason_{segment}"] = source.get(f"reason_{segment}", "")
    return row


def build_comparison_list(window_metrics: pd.DataFrame, full_reference: dict[str, object], selected: dict[str, object]) -> pd.DataFrame:
    rows = []
    comparisons = [
        (
            candidate_label(28, 0.50, 1.00, 0.75, None),
            "layer4_carried_baseline",
            "Layer4 carried primary line before target-vol",
            None,
        ),
        (
            candidate_label(28, 0.50, 1.00, 0.75, 0.25),
            "layer5_primary_original_target_vol",
            "Layer4 primary with original target-vol 25%",
            None,
        ),
        (
            str(selected["candidate"]),
            "layer5_selected",
            "Selected Layer5 line under the documented pass rule",
            None,
        ),
        (
            candidate_label(28, 0.50, 1.00, 0.67, 0.25),
            "entry_neighbor_original_target_vol",
            "Entry-fraction neighbor with original target-vol 25%",
            None,
        ),
        (
            candidate_label(32, 0.50, 1.00, 0.75, 0.25),
            "return_peak_watch_original_target_vol",
            "Return peak watch line with original target-vol 25%",
            None,
        ),
        (
            candidate_label(25, 0.20, 1.05, 0.50, 0.25),
            "original_layer5_target_vol",
            "Original first-layer parameter plus original R2 0.20, switch buffer 1.05, initial entry fraction 0.50, and target-vol 25%",
            "orig_layer5_lb25_r2_0p20_buf_1p05_entry_0p50_tv25",
        ),
    ]
    seen = set()
    for label, ctype, notes, output_label in comparisons:
        if label in seen:
            continue
        seen.add(label)
        match = window_metrics[window_metrics["candidate"].eq(label)]
        if match.empty:
            continue
        rows.append(row_from_window(match.iloc[0].to_dict(), output_label or label, ctype, notes))
    rows.append(full_reference)
    return pd.DataFrame(rows)


def pct(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value) * 100:.2f}%"


def write_record(
    run_folder: Path,
    window_metrics: pd.DataFrame,
    comparison_list: pd.DataFrame,
    selection: dict[str, object],
    sources: pd.DataFrame,
    meta: dict[str, object],
) -> None:
    selected = selection["selected"]
    primary = window_metrics[
        window_metrics["lookback"].eq(PRIMARY_LOOKBACK)
        & window_metrics["r2_threshold"].eq(PRIMARY_R2)
        & window_metrics["switch_buffer"].eq(PRIMARY_SWITCH_BUFFER)
        & window_metrics["entry_fraction"].eq(PRIMARY_ENTRY_FRACTION)
    ].copy()
    primary["_tv_sort"] = primary["target_vol"].fillna(-1.0)
    primary = primary.sort_values("_tv_sort").drop(columns=["_tv_sort"])
    top_pass = window_metrics[window_metrics["layer5_pass"].astype(bool)].sort_values(
        ["ann_return_full", "mdd_improve_full_pp"],
        ascending=[False, False],
    ).head(10)
    if top_pass.empty:
        top_pass = window_metrics[window_metrics["target_vol_label"].ne("no_tv")].sort_values(
            "mdd_improve_full_pp",
            ascending=False,
        ).head(10)

    lines = [
        "# Sub-D Dynamic ChiNext Proxy Layer 5 Target-Vol Scan",
        "",
        "## Run Metadata",
        "",
        f"- Run folder: `{run_folder}`",
        "- Layer: `Layer 5`",
        "- Strategy: dynamic ChiNext proxy pool, 2007-2016.",
        "- Entrypoint: `run_subd_proxy_dynamic_cyb_layer5_target_vol_scan.py`",
        "",
        "## Research Question",
        "",
        "Add target-vol scaling after the Layer 4 staged-entry line and compare each target-vol candidate to the same line with no target-vol overlay.",
        "",
        "## Implementation Anchor",
        "",
        "- Data loader reused from `run_subd_proxy_dynamic_cyb_layer0.py`.",
        "- Base staged-entry curves reuse Layer 4's `run_staged_line` helper.",
        "- Target-vol behavior reuses `apply_target_vol_overlay` from `run_subd_six_etf_v1_1.py`.",
        "- No overheat in this layer.",
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
        f"- Lines carried: `{[(lb, r2, buf, entry, role) for lb, r2, buf, entry, role in LINE_GRID]}`.",
        f"- Target-vol grid: `{[target_vol_label(x) for x in TARGET_VOL_GRID]}`.",
        "- Baseline: same `lookback + R2 + switch buffer + entry fraction` with no target-vol overlay.",
        f"- Pass rule: Full maxDD improves by more than `{MDD_IMPROVE_EPS_PP:.2f}pp`; at least 3 of the 4 available windows improve maxDD by more than `{MDD_IMPROVE_EPS_PP:.2f}pp`; Full/5Y annualized return lag <=1pp and 3Y/1Y lag <=3pp versus same-line no-target-vol baseline.",
        "",
        "## Commands",
        "",
        f"- `{meta['command']}`",
        "",
        "## Output Files",
        "",
        "- `scan_summary.csv`",
        "- `window_metrics.csv`",
        "- `comparison_list.csv`",
        "- `daily_outputs/target_vol_daily_curves.csv`",
        "- `sources.csv`",
        "",
        "## Primary Line Results",
        "",
        "| Candidate | Full Ann. | Full MDD | Full Ann Delta pp | Full MDD Improve pp | 5Y Ann. | 3Y Ann. | 1Y Ann. | Avg Scale Full | Avg Exposure Full | Pass | Reason |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for _, row in primary.iterrows():
        lines.append(
            "| "
            f"{row['candidate']} | {pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{row['ann_delta_full_pp']:.2f} | {row['mdd_improve_full_pp']:.2f} | "
            f"{pct(row['ann_return_last_5y'])} | {pct(row['ann_return_last_3y'])} | {pct(row['ann_return_last_1y'])} | "
            f"{float(row['avg_scale_effective_full']):.2f} | {float(row['avg_exposure_effective_full']):.2f} | "
            f"{bool(row['layer5_pass'])} | {row['pass_reason']} |"
        )
    lines.extend(
        [
            "",
            "## Passing Or Best Candidates",
            "",
            "| Candidate | Role | Full Ann. | Full MDD | Full MDD Improve pp | DD Improve Windows | Pass |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
    )
    for _, row in top_pass.iterrows():
        lines.append(
            "| "
            f"{row['candidate']} | {row['line_role']} | {pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{row['mdd_improve_full_pp']:.2f} | {int(row['dd_improve_window_count'])} | {bool(row['layer5_pass'])} |"
        )
    lines.extend(
        [
            "",
            "## Comparison List",
            "",
            "| Candidate | Type | Full Ann. | Full MDD | 5Y Ann. | 3Y Ann. | 1Y Ann. | Notes |",
            "|---|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for _, row in comparison_list.iterrows():
        lines.append(
            "| "
            f"{row['candidate']} | {row['candidate_type']} | "
            f"{pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{pct(row['ann_return_last_5y'])} | {pct(row['ann_return_last_3y'])} | {pct(row['ann_return_last_1y'])} | "
            f"{row['notes']} |"
        )
    lines.extend(
        [
            "",
            "## Stability Classification",
            "",
            f"- Selected candidate: `{selected['candidate']}`.",
            f"- Decision: `{selection['decision']}`.",
            f"- Stability label: `{selection['stability_label']}`.",
            f"- Best non-primary pass: `{selection.get('best_nonprimary_pass', {}).get('candidate', 'N/A')}`.",
            "- 10Y remains N/A by sample length and is not fabricated for strict scanner compatibility.",
            "",
            "## Decision",
            "",
            f"- Decision: `{selection['decision']}`.",
            "- Stop here before any overheat layer.",
            "",
            "## User-Facing Summary",
            "",
            f"Layer 5 selected `{selected['candidate']}` under the documented pass rule. See `window_metrics.csv` for all target-vol lines.",
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
    base_curves: dict[tuple[int, float, float, float, str], pd.DataFrame] = {}
    for line in LINE_GRID:
        lookback, r2_threshold, switch_buffer, entry_fraction, line_role = line
        base_curves[line] = layer4.run_staged_line(
            prices,
            end_date,
            lookback,
            r2_threshold,
            switch_buffer,
            entry_fraction,
            line_role,
        )

    curves = []
    summary_rows = []
    for line, base_curve in base_curves.items():
        lookback, r2_threshold, switch_buffer, entry_fraction, line_role = line
        for target_vol in TARGET_VOL_GRID:
            curve = apply_target_vol_layer(
                base_curve,
                lookback,
                r2_threshold,
                switch_buffer,
                entry_fraction,
                target_vol,
                line_role,
            )
            curves.append(curve)
            for segment, label, start, reason in layer1.window_specs(prices.index):
                summary_rows.append(summarize_curve(curve, segment, label, start, reason))

    scan_summary = pd.DataFrame(summary_rows)
    window_metrics = build_window_metrics(scan_summary)
    full_reference = original_full_reference(prices, end_date)
    selection = select_candidate(window_metrics)
    comparison_list = build_comparison_list(window_metrics, full_reference, selection["selected"])
    daily = pd.concat(curves, axis=0).reset_index()

    scan_summary.to_csv(run_folder / "scan_summary.csv", index=False, encoding="utf-8-sig")
    window_metrics.to_csv(run_folder / "window_metrics.csv", index=False, encoding="utf-8-sig")
    comparison_list.to_csv(run_folder / "comparison_list.csv", index=False, encoding="utf-8-sig")
    daily.to_csv(daily_dir / "target_vol_daily_curves.csv", index=False, encoding="utf-8-sig")
    sources.to_csv(run_folder / "sources.csv", index=False, encoding="utf-8-sig")

    metadata_path = run_folder / "scan_meta.json"
    meta = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    command = (
        "python run_subd_proxy_dynamic_cyb_layer5_target_vol_scan.py "
        f"--start-date {start_date.date()} --end-date {end_date.date()} --run-folder {run_folder}"
    )
    meta.update(
        {
            "phase": "scan_complete_unfinalized",
            "scan_type": "layer5_grid_scan",
            "parameter_group": "layer5_target_vol",
            "baseline": {"rule": "same lookback + R2 + switch_buffer + entry_fraction with no target-vol"},
            "candidate_grid": [
                {
                    "lookback": int(lookback),
                    "r2_threshold": float(r2_threshold),
                    "switch_buffer": float(switch_buffer),
                    "entry_fraction": float(entry_fraction),
                    "line_role": line_role,
                    "target_vol": None if target_vol is None else float(target_vol),
                }
                for lookback, r2_threshold, switch_buffer, entry_fraction, line_role in LINE_GRID
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
                "signal": "close-to-close weighted-slope ranking with fixed R2 threshold and switch buffer",
                "staged_entry": "enter new asset with initial fraction; fill to 100% on later down day if signal remains unchanged",
                "target_vol": "80-day realized vol, next-day effective scale, max leverage 1.5, scale rebalance threshold 0.075",
                "overlays": "none in Layer 5 beyond R2, switch buffer setting, staged-entry rule, and target-vol overlay",
                "mixed_market_calendar": "diagnostic A-share calendar with US proxy forward-filled; trades on stale trade legs blocked",
            },
            "pass_rule": {
                "mdd_improve_eps_pp": MDD_IMPROVE_EPS_PP,
                "available_windows": list(AVAILABLE_PASS_SEGMENTS),
                "return_lag_tolerance_pp": {"full": 1.0, "last_5y": 1.0, "last_3y": 3.0, "last_1y": 3.0},
            },
            "layer5_selection": selection,
            "comparison_reference": {
                "layer4_baseline_candidate": candidate_label(28, 0.50, 1.00, 0.75, None),
                "original_layer5_candidate": "orig_layer5_lb25_r2_0p20_buf_1p05_entry_0p50_tv25",
                "original_full_strategy_candidate": "orig_full_v1_1_reference",
            },
            "outputs": {
                "scan_summary": str(run_folder / "scan_summary.csv"),
                "window_metrics": str(run_folder / "window_metrics.csv"),
                "comparison_list": str(run_folder / "comparison_list.csv"),
                "daily_curves": str(daily_dir / "target_vol_daily_curves.csv"),
                "sources": str(run_folder / "sources.csv"),
                "record": str(run_folder / "record.md"),
            },
            "git_branch_after": git_value(["branch", "--show-current"]),
            "git_commit_after": git_value(["rev-parse", "HEAD"]),
            "git_status_after": git_value(["status", "--short"]),
            "command": command,
            "elapsed_sec": round(time.time() - started, 3),
        }
    )
    metadata_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    write_record(run_folder, window_metrics, comparison_list, selection, sources, meta)

    with (run_folder / "command_log.txt").open("a", encoding="utf-8") as fh:
        fh.write("\n[scan]\n")
        fh.write(f"cwd={Path.cwd()}\n")
        fh.write(command + "\n")
        fh.write(f"elapsed_sec={meta['elapsed_sec']}\n")

    print(f"WROTE {run_folder / 'scan_summary.csv'}")
    print(f"WROTE {run_folder / 'window_metrics.csv'}")
    print(f"WROTE {run_folder / 'comparison_list.csv'}")
    print(f"WROTE {daily_dir / 'target_vol_daily_curves.csv'}")
    print(
        json.dumps(
            {
                "selected": selection["selected"],
                "decision": selection["decision"],
                "stability_label": selection["stability_label"],
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
    primary = window_metrics[
        window_metrics["lookback"].eq(PRIMARY_LOOKBACK)
        & window_metrics["r2_threshold"].eq(PRIMARY_R2)
        & window_metrics["switch_buffer"].eq(PRIMARY_SWITCH_BUFFER)
        & window_metrics["entry_fraction"].eq(PRIMARY_ENTRY_FRACTION)
    ].copy()
    primary["_tv_sort"] = primary["target_vol"].fillna(-1.0)
    print(primary.sort_values("_tv_sort").drop(columns=["_tv_sort"]).to_string(index=False))


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
