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
import run_subd_proxy_dynamic_cyb_layer3_switch_buffer_scan as layer3
import run_subd_proxy_dynamic_cyb_layer4_staged_entry_scan as layer4
import run_subd_proxy_dynamic_cyb_layer6_momentum_decay_scan as layer6
import run_subd_proxy_dynamic_cyb_r2none_layer4_staged_entry_scan as r2none_layer4
import run_subd_proxy_dynamic_cyb_r2none_layer5_target_vol_scan as r2none_layer5
import run_subd_six_etf_v1_1 as v11


DEFAULT_START = pd.Timestamp("2007-01-01")
DEFAULT_END = pd.Timestamp("2016-12-30")
DEFAULT_RUN_FOLDER = Path(
    "quant_param_scan_runs"
    "/20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_r2_removed_branch_layer6_momentum_decay_after_r2_removed"
)

LINE_GRID: tuple[tuple[int, float, float, str], ...] = (
    (28, 1.15, 0.25, "main_line_r2_removed"),
    (28, 1.15, 0.75, "return_watch_line_r2_removed"),
)
DECAY_RATIOS = (0.45, 0.55, 0.65, 0.75)
RECOVERY_RATIOS = (0.85, 0.95)
CONFIRM_DAYS = (1, 3)
DERISK_SCALES = (0.0, 0.50, 0.75)
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


def pct(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value) * 100:.2f}%"


def fmt(value: object, digits: int = 2) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value):.{digits}f}"


def candidate_label(
    lookback: int,
    switch_buffer: float,
    entry_fraction: float,
    decay_ratio: float | None,
    recovery_ratio: float | None,
    confirm_days: int | None,
    derisk_scale: float | None,
) -> str:
    return (
        f"lb_{lookback}_r2_none_buf_{layer3.buffer_label(switch_buffer)}"
        f"_entry_{layer4.fraction_label(entry_fraction)}"
        f"_{layer6.decay_label(decay_ratio, recovery_ratio, confirm_days, derisk_scale)}"
    )


def candidate_grid() -> list[tuple[float | None, float | None, int | None, float | None]]:
    grid: list[tuple[float | None, float | None, int | None, float | None]] = [(None, None, None, None)]
    for decay_ratio in DECAY_RATIOS:
        for recovery_ratio in RECOVERY_RATIOS:
            if recovery_ratio <= decay_ratio:
                continue
            for confirm_days in CONFIRM_DAYS:
                for derisk_scale in DERISK_SCALES:
                    grid.append((decay_ratio, recovery_ratio, confirm_days, derisk_scale))
    return grid


def apply_momentum_decay_layer(
    base_curve: pd.DataFrame,
    lookback: int,
    switch_buffer: float,
    entry_fraction: float,
    decay_ratio: float | None,
    recovery_ratio: float | None,
    confirm_days: int | None,
    derisk_scale: float | None,
    line_role: str,
    line_order: int,
) -> pd.DataFrame:
    curve = base_curve.copy()
    curve["base_return"] = curve["return"].astype(float).fillna(0.0)
    curve["base_nav"] = curve["nav"].astype(float)
    curve["base_gross_return"] = curve["gross_return"].astype(float).fillna(0.0)
    curve["base_turnover"] = curve["turnover"].astype(float).fillna(0.0)
    curve["base_cost"] = curve["cost"].astype(float).fillna(0.0)
    curve["base_position_before_score_decay"] = curve["position_before"].astype(str)
    curve["base_position_after_score_decay_signal"] = curve["position"].astype(str)
    curve["base_holding_fraction_before_score_decay"] = curve["fraction_before"].astype(float).fillna(0.0)
    curve["base_holding_fraction_after_score_decay_signal"] = curve["holding_fraction"].astype(float).fillna(0.0)

    enabled = decay_ratio is not None
    if enabled:
        decay = layer6.score_peak_decay_state(
            curve,
            float(decay_ratio),
            float(recovery_ratio),
            int(confirm_days),
            float(derisk_scale),
        )
        ones = pd.Series(1.0, index=curve.index, dtype=float)
        curve = v11._recompute_final_exposure_nav(
            curve,
            ones,
            ones,
            decay["score_decay_multiplier_effective"],
            decay["score_decay_multiplier_next"],
            ONE_WAY_COST,
        )
        for col in decay.columns:
            curve[col] = decay[col]
    else:
        active_score = layer6.active_score_series(curve)
        curve["score_decay_active_score"] = active_score
        curve["score_decay_multiplier_next"] = 1.0
        curve["score_decay_multiplier_effective"] = 1.0
        curve["score_decay_peak"] = np.nan
        curve["score_decay_ratio"] = np.nan
        curve["score_decay_overlay_on"] = False
        curve["score_decay_triggered"] = False
        curve["score_decay_recovered"] = False
        curve["score_decay_trade_id"] = pd.Series(np.nan, index=curve.index, dtype="Float64")
        curve["score_decay_waiting_for_new_peak"] = False
        curve["target_vol_scale_effective"] = 1.0
        curve["target_vol_scale_next"] = 1.0
        curve["weight"] = 1.0
        curve["overheat_scale_effective"] = 1.0
        curve["overheat_scale_next"] = 1.0
        curve["overheat_scale"] = 1.0
        curve["exposure_effective"] = curve["fraction_before"].astype(float).fillna(0.0).where(
            curve["position_before"].astype(str) != "CASH",
            0.0,
        )
        curve["final_exposure"] = curve["holding_fraction"].astype(float).fillna(0.0).where(
            curve["position"].astype(str) != "CASH",
            0.0,
        )
        curve["final_exposure_after_overheat"] = curve["final_exposure"]
        curve["actual_position_before"] = curve["position_before"]
        curve["actual_position_next"] = curve["position"]
        curve["effective_trade_count"] = (curve["turnover"].astype(float).fillna(0.0) > 1e-12).cumsum()

    curve["candidate"] = candidate_label(
        lookback,
        switch_buffer,
        entry_fraction,
        decay_ratio,
        recovery_ratio,
        confirm_days,
        derisk_scale,
    )
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
    curve["momentum_decay_enabled"] = bool(enabled)
    curve["decay_ratio_threshold"] = np.nan if decay_ratio is None else float(decay_ratio)
    curve["recovery_ratio_threshold"] = np.nan if recovery_ratio is None else float(recovery_ratio)
    curve["confirm_days"] = np.nan if confirm_days is None else int(confirm_days)
    curve["derisk_scale"] = 1.0 if derisk_scale is None else float(derisk_scale)
    curve["decay_label"] = layer6.decay_label(decay_ratio, recovery_ratio, confirm_days, derisk_scale)
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
        "momentum_decay_enabled": bool(first["momentum_decay_enabled"]),
        "decay_ratio_threshold": first["decay_ratio_threshold"],
        "recovery_ratio_threshold": first["recovery_ratio_threshold"],
        "confirm_days": first["confirm_days"],
        "derisk_scale": float(first["derisk_scale"]),
        "decay_label": str(first["decay_label"]),
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
            "avg_exposure_effective": np.nan,
            "avg_final_exposure": np.nan,
            "avg_decay_multiplier_effective": np.nan,
            "avg_decay_multiplier_next": np.nan,
            "decay_day_ratio": np.nan,
            "trigger_count": np.nan,
            "recovery_count": np.nan,
            "reason": reason,
        }
    sub = curve.loc[curve.index >= start].copy()
    ret = sub["return"].astype(float).fillna(0.0)
    wealth = (1.0 + ret).cumprod()
    years = len(sub) / TRADING_DAYS
    ann_vol = float(ret.std(ddof=0) * math.sqrt(TRADING_DAYS))
    sharpe = float(ret.mean() / ret.std(ddof=0) * math.sqrt(TRADING_DAYS)) if ret.std(ddof=0) > 0 else math.nan
    final_exposure = sub["final_exposure_after_overheat"].astype(float).fillna(0.0)
    exposure_effective = sub["exposure_effective"].astype(float).fillna(0.0)
    decay_effective = sub["score_decay_multiplier_effective"].astype(float).fillna(1.0)
    decay_next = sub["score_decay_multiplier_next"].astype(float).fillna(1.0)
    decay_on = sub["score_decay_overlay_on"].astype(bool)
    return {
        **base,
        "start": sub.index[0].date().isoformat(),
        "rows": int(len(sub)),
        "ann_return": float(wealth.iloc[-1] ** (1.0 / years) - 1.0),
        "ann_vol": ann_vol,
        "max_dd": max_drawdown(wealth),
        "sharpe_repo": sharpe,
        "cash_days": int((final_exposure <= 1e-12).sum()),
        "trades": int((sub["turnover"].astype(float).fillna(0.0) > 1e-12).sum()),
        "cost_total": float(sub["cost"].astype(float).fillna(0.0).sum()),
        "turnover_total": float(sub["turnover"].astype(float).fillna(0.0).sum()),
        "holding_day_ratio": float((final_exposure > 1e-12).mean()),
        "avg_holding_fraction": float(sub["holding_fraction"].astype(float).fillna(0.0).mean()),
        "avg_exposure_effective": float(exposure_effective.mean()),
        "avg_final_exposure": float(final_exposure.mean()),
        "avg_decay_multiplier_effective": float(decay_effective.mean()),
        "avg_decay_multiplier_next": float(decay_next.mean()),
        "decay_day_ratio": float(decay_on.mean()),
        "trigger_count": int(sub["score_decay_triggered"].astype(bool).sum()),
        "recovery_count": int(sub["score_decay_recovered"].astype(bool).sum()),
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
            None,
            None,
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
            "momentum_decay_enabled": bool(first["momentum_decay_enabled"]),
            "decay_ratio_threshold": first["decay_ratio_threshold"],
            "recovery_ratio_threshold": first["recovery_ratio_threshold"],
            "confirm_days": first["confirm_days"],
            "derisk_scale": float(first["derisk_scale"]),
            "decay_label": first["decay_label"],
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
                    "max_dd",
                    "trades",
                    "cost_total",
                    "turnover_total",
                    "avg_exposure_effective",
                    "avg_final_exposure",
                    "avg_decay_multiplier_effective",
                    "avg_decay_multiplier_next",
                    "decay_day_ratio",
                    "trigger_count",
                    "recovery_count",
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
    out["_decay_sort"] = out["decay_ratio_threshold"].fillna(-1.0)
    out["_rec_sort"] = out["recovery_ratio_threshold"].fillna(-1.0)
    out["_confirm_sort"] = out["confirm_days"].fillna(0)
    out = out.sort_values(
        ["line_order", "_decay_sort", "_rec_sort", "_confirm_sort", "derisk_scale"]
    ).drop(columns=["_decay_sort", "_rec_sort", "_confirm_sort"])
    return apply_pass_flags(out)


def apply_pass_flags(window_metrics: pd.DataFrame) -> pd.DataFrame:
    out = window_metrics.copy()
    pass_rows = []
    for _, row in out.iterrows():
        if not bool(row["momentum_decay_enabled"]):
            pass_rows.append(
                {
                    "dd_improve_window_count": 0,
                    "return_tolerance_ok": False,
                    "full_mdd_improved": False,
                    "material_decay": False,
                    "layer6_pass": False,
                    "pass_reason": "baseline/no momentum decay",
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
        material_decay = bool(
            pd.notna(row.get("trigger_count_full", np.nan))
            and float(row.get("trigger_count_full", 0.0)) > 0.0
            and pd.notna(row.get("decay_day_ratio_full", np.nan))
            and float(row.get("decay_day_ratio_full", 0.0)) > 0.0
        )
        layer6_pass = bool(full_mdd_improved and dd_count >= 3 and tolerance_ok and material_decay)
        reason = (
            "pass"
            if layer6_pass
            else f"full_mdd={full_mdd_improved};dd_windows={dd_count};return_tol={tolerance_ok};material={material_decay}"
        )
        pass_rows.append(
            {
                "dd_improve_window_count": dd_count,
                "return_tolerance_ok": tolerance_ok,
                "full_mdd_improved": full_mdd_improved,
                "material_decay": material_decay,
                "layer6_pass": layer6_pass,
                "pass_reason": reason,
            }
        )
    return pd.concat([out.reset_index(drop=True), pd.DataFrame(pass_rows)], axis=1)


def select_by_line(window_metrics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for line_role, group in window_metrics.groupby("line_role", sort=False):
        passed = group[group["layer6_pass"].astype(bool)].copy()
        baseline = group[~group["momentum_decay_enabled"].astype(bool)].iloc[0].to_dict()
        if passed.empty:
            selected = baseline
            selected["selection_role"] = "baseline_no_momentum_decay_pass"
        elif line_role.startswith("return_watch"):
            selected = passed.sort_values(
                ["ann_return_full", "mdd_improve_full_pp", "decay_day_ratio_full"],
                ascending=[False, False, True],
            ).iloc[0].to_dict()
            selected["selection_role"] = "return_watch_momentum_decay_pass"
        else:
            selected = passed.sort_values(
                ["mdd_improve_full_pp", "ann_return_full", "decay_day_ratio_full"],
                ascending=[False, False, True],
            ).iloc[0].to_dict()
            selected["selection_role"] = "selected_drawdown_momentum_decay_pass"
        rows.append(selected)
    return pd.DataFrame(rows)


def original_full_reference(prices: pd.DataFrame, end_date: pd.Timestamp) -> dict[str, object]:
    row = r2none_layer5.original_full_reference(prices, end_date)
    row["candidate_type"] = "original_full_v1_1_reference"
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
        "decay_label": source.get("decay_label", ""),
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
    for _, row in window_metrics[~window_metrics["momentum_decay_enabled"].astype(bool)].iterrows():
        rows.append(row_from_window(row.to_dict(), "line_baseline_no_momentum_decay", "Same carried line before momentum-decay layer"))
    for _, row in line_selection.iterrows():
        rows.append(row_from_window(row.to_dict(), str(row["selection_role"]), "Line-level selected momentum-decay result"))
    rows.append(full_reference)
    return pd.DataFrame(rows)


def daily_output_frame(curves: list[pd.DataFrame]) -> pd.DataFrame:
    cols = [
        "candidate",
        "line_role",
        "line_order",
        "lookback",
        "r2_label",
        "r2_execution_threshold",
        "switch_buffer",
        "entry_fraction",
        "momentum_decay_enabled",
        "decay_label",
        "decay_ratio_threshold",
        "recovery_ratio_threshold",
        "confirm_days",
        "derisk_scale",
        "position_before",
        "fraction_before",
        "position",
        "holding_fraction",
        "actual_position_before",
        "actual_position_next",
        "score_decay_active_score",
        "score_decay_peak",
        "score_decay_ratio",
        "score_decay_multiplier_effective",
        "score_decay_multiplier_next",
        "score_decay_overlay_on",
        "score_decay_triggered",
        "score_decay_recovered",
        "score_decay_waiting_for_new_peak",
        "asset_return",
        "gross_return",
        "turnover",
        "cost",
        "return",
        "nav",
        "base_return",
        "base_nav",
        "exposure_effective",
        "final_exposure_after_overheat",
    ]
    out = pd.concat([curve[[c for c in cols if c in curve.columns]] for curve in curves], axis=0)
    return out.reset_index()


def write_record(
    run_folder: Path,
    window_metrics: pd.DataFrame,
    line_selection: pd.DataFrame,
    comparison_list: pd.DataFrame,
    sources: pd.DataFrame,
    meta: dict[str, object],
) -> None:
    top = window_metrics[window_metrics["momentum_decay_enabled"].astype(bool)].sort_values(
        ["layer6_pass", "mdd_improve_full_pp", "ann_return_full"],
        ascending=[False, False, False],
    ).head(14)
    lines = [
        "# Sub-D Dynamic ChiNext Proxy R2-Removed Branch Layer 6 Momentum Decay Scan",
        "",
        "## Run Metadata",
        "",
        f"- Run folder: `{run_folder}`",
        "- Layer: `Layer 6` after R2 removal, switch-buffer/staged-entry selection, and rejected target-vol.",
        "- Entrypoint: `run_subd_proxy_dynamic_cyb_r2none_layer6_momentum_decay_scan.py`",
        "",
        "## Research Question",
        "",
        "Test score-peak momentum decay on the two user-confirmed no-target-vol lines.",
        "",
        "## Implementation Anchor",
        "",
        "- Data loader reused from `run_subd_proxy_dynamic_cyb_layer0.py`.",
        "- Base curves reuse `run_subd_proxy_dynamic_cyb_r2none_layer4_staged_entry_scan.py`.",
        "- Momentum decay state machine reuses `score_peak_decay_state` from the existing Layer 6 script.",
        "- NAV/exposure/cost recomputation reuses `_recompute_final_exposure_nav` from `run_subd_six_etf_v1_1.py`.",
        "- No target-vol, NAV defense, or overheat in this layer.",
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
        "- Score-decay signal uses close information for the next holding scale; effective scale is shifted one session.",
        "- Calendar: A-share trading days; US adjusted closes are forward-filled onto that calendar for this proxy diagnostic.",
        "- Trades involving a forward-filled trade leg are blocked by the base staged-entry path for that day.",
        "",
        "## Runtime Override Plan",
        "",
        f"- Lines: `{[(lb, buf, entry, role) for lb, buf, entry, role in LINE_GRID]}`.",
        f"- Decay ratios: `{list(DECAY_RATIOS)}`.",
        f"- Recovery ratios: `{list(RECOVERY_RATIOS)}`.",
        f"- Confirm days: `{list(CONFIRM_DAYS)}`.",
        f"- Derisk scales: `{list(DERISK_SCALES)}`.",
        "- Baseline: same `lookback + switch buffer + entry fraction` with momentum decay disabled.",
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
        "- `daily_outputs/r2none_momentum_decay_daily_curves.csv`",
        "- `sources.csv`",
        "",
        "## Line-Level Selection",
        "",
        "| Line Role | Candidate | Selection | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | MDD Improve pp | Trigger Full | Decay Days Full | Pass Reason |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
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
            f"{fmt(row['mdd_improve_full_pp'])} | "
            f"{int(row['trigger_count_full']) if pd.notna(row['trigger_count_full']) else 'N/A'} | "
            f"{pct(row['decay_day_ratio_full'])} | {row['pass_reason']} |"
        )
    lines.extend(
        [
            "",
            "## Best Decay Candidates",
            "",
            "| Candidate | Role | Full Ann. | Full MDD | Full Ann Delta pp | Full MDD Improve pp | DD Improve Windows | Trigger Full | Decay Days Full | Pass | Reason |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for _, row in top.iterrows():
        lines.append(
            "| "
            f"`{row['candidate']}` | {row['line_role']} | {pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{fmt(row['ann_delta_full_pp'])} | {fmt(row['mdd_improve_full_pp'])} | {int(row['dd_improve_window_count'])} | "
            f"{int(row['trigger_count_full']) if pd.notna(row['trigger_count_full']) else 'N/A'} | "
            f"{pct(row['decay_day_ratio_full'])} | {bool(row['layer6_pass'])} | {row['pass_reason']} |"
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
            "- Decision: `line_level_selection_after_momentum_decay_on_r2_removed_branch`.",
            "- Stability label: `momentum_decay_pass_if_line_selection_uses_overlay_else_keep_previous`.",
            "- 10Y remains N/A by sample length: 2432 sessions is less than 2520 trading days.",
            "",
            "## Decision",
            "",
            "- Keep each line's selected row from `line_selection.csv`.",
            "- Stop here before NAV defense.",
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
    grid = candidate_grid()
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
        for decay_ratio, recovery_ratio, confirm_days, derisk_scale in grid:
            curve = apply_momentum_decay_layer(
                base_curve,
                lookback,
                switch_buffer,
                entry_fraction,
                decay_ratio,
                recovery_ratio,
                confirm_days,
                derisk_scale,
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
    daily.to_csv(daily_dir / "r2none_momentum_decay_daily_curves.csv", index=False, encoding="utf-8-sig")
    sources.to_csv(run_folder / "sources.csv", index=False, encoding="utf-8-sig")

    command = (
        "python run_subd_proxy_dynamic_cyb_r2none_layer6_momentum_decay_scan.py "
        f"--start-date {start_date.date()} --end-date {end_date.date()} --run-folder {run_folder}"
    )
    metadata_path = run_folder / "scan_meta.json"
    meta = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    meta.update(
        {
            "phase": "scan_complete_unfinalized",
            "scan_type": "layer6_momentum_decay_scan_after_r2_removed",
            "parameter_group": "layer6_momentum_decay_after_r2_removed",
            "baseline": {
                "rule": "same lookback + switch_buffer + entry_fraction with R2 removed and momentum decay disabled",
                "line_baselines": [
                    candidate_label(lb, buf, entry, None, None, None, None) for lb, buf, entry, _ in LINE_GRID
                ],
            },
            "candidate_grid": [
                {
                    "lookback": int(lookback),
                    "switch_buffer": float(switch_buffer),
                    "entry_fraction": float(entry_fraction),
                    "line_role": line_role,
                    "r2_threshold": None,
                    "r2_execution_threshold": R2_EXEC_THRESHOLD_FOR_REMOVED,
                    "decay_ratio": None if decay_ratio is None else float(decay_ratio),
                    "recovery_ratio": None if recovery_ratio is None else float(recovery_ratio),
                    "confirm_days": None if confirm_days is None else int(confirm_days),
                    "derisk_scale": None if derisk_scale is None else float(derisk_scale),
                }
                for lookback, switch_buffer, entry_fraction, line_role in LINE_GRID
                for decay_ratio, recovery_ratio, confirm_days, derisk_scale in grid
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
                "score_decay_rebalance_cost_included": True,
            },
            "execution_assumptions": {
                "signal": "close-to-close weighted-slope ranking, score range 0..5, switch buffer, R2 removed",
                "staged_entry": "enter new asset with selected initial fraction; fill to 100% on later down day if signal remains unchanged",
                "momentum_decay": "current target holding score divided by active trade score peak; close signal sets next-session scale",
                "target_vol": "disabled because Layer 5 rejected target-vol for both carried lines",
                "nav_defense": "not tested in Layer 6",
                "overheat": "not tested in Layer 6",
                "mixed_market_calendar": "diagnostic A-share calendar with US proxy forward-filled; base trades on stale trade legs blocked",
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
                "daily_curves": str(daily_dir / "r2none_momentum_decay_daily_curves.csv"),
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
    print(f"WROTE {daily_dir / 'r2none_momentum_decay_daily_curves.csv'}")
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
        "trigger_count_full",
        "decay_day_ratio_full",
        "layer6_pass",
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
