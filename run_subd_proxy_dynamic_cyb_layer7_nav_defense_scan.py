from __future__ import annotations

import argparse
import json
import math
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd

import run_subd_proxy_dynamic_cyb_layer0 as layer0
import run_subd_proxy_dynamic_cyb_layer1_scan as layer1
import run_subd_proxy_dynamic_cyb_layer2_r2_scan as layer2
import run_subd_proxy_dynamic_cyb_layer3_switch_buffer_scan as layer3
import run_subd_proxy_dynamic_cyb_layer4_staged_entry_scan as layer4
import run_subd_proxy_dynamic_cyb_layer6_momentum_decay_scan as layer6
import run_subd_six_etf_v1_1 as v11


DEFAULT_START = pd.Timestamp("2007-01-01")
DEFAULT_END = pd.Timestamp("2016-12-30")
DEFAULT_RUN_FOLDER = Path(
    "quant_param_scan_runs"
    "/20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_nav_defense_layer7_nav_drawdown_gate"
)
PRIMARY_LOOKBACK = 28
PRIMARY_R2 = 0.50
PRIMARY_SWITCH_BUFFER = 1.00
PRIMARY_ENTRY_FRACTION = 0.75
PRIMARY_DECAY_RATIO = 0.55
PRIMARY_RECOVERY_RATIO = 0.85
PRIMARY_CONFIRM_DAYS = 3
PRIMARY_DERISK_SCALE = 0.75
LINE_GRID: tuple[tuple[int, float, float, float, float | None, float | None, int | None, float | None, str, bool], ...] = (
    (28, 0.50, 1.00, 0.75, 0.55, 0.85, 3, 0.75, "layer6_carried_primary", True),
    (28, 0.50, 1.00, 0.75, 0.55, 0.95, 3, 0.75, "recovery_neighbor", True),
    (28, 0.50, 1.00, 0.75, 0.55, 0.85, 3, 0.50, "decay_scale_neighbor", True),
    (32, 0.50, 1.00, 0.75, 0.55, 0.85, 1, 0.75, "return_peak_watch", True),
    (25, 0.20, 1.05, 0.50, None, None, None, None, "original_layer7_same_stage", False),
)
NAV_ENTER_THRESHOLDS = (0.075, 0.10, 0.125, 0.15, 0.20)
NAV_EXIT_THRESHOLDS = (0.03, 0.05, 0.08, 0.10)
DEFENSE_SCALES = (0.0, 0.25, 0.50, 0.75)
ONE_WAY_COST = 0.001
TRADING_DAYS = 252
SEGMENTS = ("full", "last_10y", "last_5y", "last_3y", "last_1y")
AVAILABLE_PASS_SEGMENTS = ("full", "last_5y", "last_3y", "last_1y")
MDD_IMPROVE_EPS_PP = 0.01


def git_value(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def pct_label(value: float) -> str:
    return f"{float(value):.3f}".rstrip("0").rstrip(".").replace(".", "p")


def scale_label(value: float) -> str:
    return f"{float(value):.2f}".replace(".", "p")


def nav_label(enter_threshold: float | None, exit_threshold: float | None, defense_scale: float | None) -> str:
    if enter_threshold is None:
        return "nav_off"
    return (
        f"nav_enter_{pct_label(float(enter_threshold))}"
        f"_exit_{pct_label(float(exit_threshold))}"
        f"_scale_{scale_label(float(defense_scale))}"
    )


def candidate_label(
    lookback: int,
    r2_threshold: float,
    switch_buffer: float,
    entry_fraction: float,
    decay_ratio: float | None,
    recovery_ratio: float | None,
    confirm_days: int | None,
    derisk_scale: float | None,
    nav_enter: float | None,
    nav_exit: float | None,
    defense_scale: float | None,
) -> str:
    base = layer6.candidate_label(
        lookback,
        r2_threshold,
        switch_buffer,
        entry_fraction,
        decay_ratio,
        recovery_ratio,
        confirm_days,
        derisk_scale,
    )
    return f"{base}_{nav_label(nav_enter, nav_exit, defense_scale)}"


def nav_defense_state(
    base_curve: pd.DataFrame,
    enter_threshold: float,
    exit_threshold: float,
    defense_scale: float,
) -> pd.DataFrame:
    if not 0.0 < exit_threshold < enter_threshold < 1.0:
        raise ValueError("exit_threshold must be in (0, enter_threshold)")
    if not 0.0 <= defense_scale <= 1.0:
        raise ValueError("defense_scale must be in [0, 1]")

    pre_nav = base_curve["nav"].astype(float)
    base_dd = pre_nav / pre_nav.cummax() - 1.0
    next_scales: list[float] = []
    trigger_flags: list[bool] = []
    recovery_flags: list[bool] = []
    state = False

    for dd in base_dd:
        prev_state = state
        if state:
            if float(dd) >= -float(exit_threshold):
                state = False
        elif float(dd) <= -float(enter_threshold):
            state = True
        next_scales.append(float(defense_scale) if state else 1.0)
        trigger_flags.append(bool(state and not prev_state))
        recovery_flags.append(bool((not state) and prev_state))

    next_scale = pd.Series(next_scales, index=base_curve.index, dtype=float)
    effective_scale = next_scale.shift(1).fillna(1.0)
    return pd.DataFrame(
        {
            "return_before_nav_defense": base_curve["return"].astype(float).fillna(0.0),
            "nav_before_nav_defense": pre_nav,
            "nav_defense_base_dd": base_dd,
            "nav_defense_scale_next": next_scale,
            "nav_defense_scale_effective": effective_scale,
            "nav_defense_on_next": next_scale < 0.999999,
            "nav_defense_on_effective": effective_scale < 0.999999,
            "nav_defense_triggered": pd.Series(trigger_flags, index=base_curve.index, dtype=bool),
            "nav_defense_recovered": pd.Series(recovery_flags, index=base_curve.index, dtype=bool),
        },
        index=base_curve.index,
    )


def apply_nav_defense_layer(
    base_curve: pd.DataFrame,
    lookback: int,
    r2_threshold: float,
    switch_buffer: float,
    entry_fraction: float,
    decay_ratio: float | None,
    recovery_ratio: float | None,
    confirm_days: int | None,
    derisk_scale: float | None,
    nav_enter: float | None,
    nav_exit: float | None,
    defense_scale: float | None,
    line_role: str,
) -> pd.DataFrame:
    enabled = nav_enter is not None
    curve = base_curve.copy()
    curve["return_before_nav_defense"] = curve["return"].astype(float).fillna(0.0)
    curve["nav_before_nav_defense"] = curve["nav"].astype(float)
    curve["nav_defense_base_dd"] = curve["nav_before_nav_defense"] / curve["nav_before_nav_defense"].cummax() - 1.0

    if enabled:
        gate = nav_defense_state(curve, float(nav_enter), float(nav_exit), float(defense_scale))
        score_effective = pd.to_numeric(
            curve.get("score_decay_multiplier_effective", pd.Series(1.0, index=curve.index)),
            errors="coerce",
        ).fillna(1.0)
        score_next = pd.to_numeric(
            curve.get("score_decay_multiplier_next", pd.Series(1.0, index=curve.index)),
            errors="coerce",
        ).fillna(1.0)
        combined_effective = score_effective * gate["nav_defense_scale_effective"]
        combined_next = score_next * gate["nav_defense_scale_next"]
        ones = pd.Series(1.0, index=curve.index, dtype=float)
        out = v11._recompute_final_exposure_nav(
            curve,
            ones,
            ones,
            combined_effective,
            combined_next,
            ONE_WAY_COST,
        )
        for col in gate.columns:
            out[col] = gate[col]
        out["score_decay_multiplier_effective"] = score_effective
        out["score_decay_multiplier_next"] = score_next
        out["combined_overlay_scale_effective"] = combined_effective
        out["combined_overlay_scale_next"] = combined_next
    else:
        out = curve.copy()
        out["nav_defense_scale_next"] = 1.0
        out["nav_defense_scale_effective"] = 1.0
        out["nav_defense_on_next"] = False
        out["nav_defense_on_effective"] = False
        out["nav_defense_triggered"] = False
        out["nav_defense_recovered"] = False
        out["combined_overlay_scale_effective"] = pd.to_numeric(
            out.get("score_decay_multiplier_effective", pd.Series(1.0, index=out.index)),
            errors="coerce",
        ).fillna(1.0)
        out["combined_overlay_scale_next"] = pd.to_numeric(
            out.get("score_decay_multiplier_next", pd.Series(1.0, index=out.index)),
            errors="coerce",
        ).fillna(1.0)

    out["candidate"] = candidate_label(
        lookback,
        r2_threshold,
        switch_buffer,
        entry_fraction,
        decay_ratio,
        recovery_ratio,
        confirm_days,
        derisk_scale,
        nav_enter,
        nav_exit,
        defense_scale,
    )
    out["baseline_candidate"] = candidate_label(
        lookback,
        r2_threshold,
        switch_buffer,
        entry_fraction,
        decay_ratio,
        recovery_ratio,
        confirm_days,
        derisk_scale,
        None,
        None,
        None,
    )
    out["line_role"] = line_role
    out["lookback"] = int(lookback)
    out["r2_threshold"] = float(r2_threshold)
    out["r2_label"] = layer2.r2_label(r2_threshold)
    out["switch_buffer"] = float(switch_buffer)
    out["buffer_label"] = layer3.buffer_label(switch_buffer)
    out["entry_fraction"] = float(entry_fraction)
    out["entry_label"] = layer4.fraction_label(entry_fraction)
    out["momentum_decay_enabled"] = bool(decay_ratio is not None)
    out["decay_ratio_threshold"] = np.nan if decay_ratio is None else float(decay_ratio)
    out["recovery_ratio_threshold"] = np.nan if recovery_ratio is None else float(recovery_ratio)
    out["confirm_days"] = np.nan if confirm_days is None else int(confirm_days)
    out["derisk_scale"] = 1.0 if derisk_scale is None else float(derisk_scale)
    out["decay_label"] = layer6.decay_label(decay_ratio, recovery_ratio, confirm_days, derisk_scale)
    out["nav_defense_enabled"] = bool(enabled)
    out["nav_enter_threshold"] = np.nan if nav_enter is None else float(nav_enter)
    out["nav_exit_threshold"] = np.nan if nav_exit is None else float(nav_exit)
    out["nav_defense_scale"] = 1.0 if defense_scale is None else float(defense_scale)
    out["nav_label"] = nav_label(nav_enter, nav_exit, defense_scale)
    return out


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
        "baseline_candidate": str(first["baseline_candidate"]),
        "line_role": str(first["line_role"]),
        "lookback": int(first["lookback"]),
        "r2_threshold": float(first["r2_threshold"]),
        "r2_label": str(first["r2_label"]),
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
        "nav_defense_enabled": bool(first["nav_defense_enabled"]),
        "nav_enter_threshold": first["nav_enter_threshold"],
        "nav_exit_threshold": first["nav_exit_threshold"],
        "nav_defense_scale": float(first["nav_defense_scale"]),
        "nav_label": str(first["nav_label"]),
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
            "trades": np.nan,
            "cost_total": np.nan,
            "turnover_total": np.nan,
            "avg_exposure_effective": np.nan,
            "avg_final_exposure": np.nan,
            "avg_nav_defense_scale_effective": np.nan,
            "avg_nav_defense_scale_next": np.nan,
            "defense_day_ratio": np.nan,
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
    scale_effective = sub["nav_defense_scale_effective"].astype(float).fillna(1.0)
    scale_next = sub["nav_defense_scale_next"].astype(float).fillna(1.0)
    defense_on = sub["nav_defense_on_effective"].astype(bool)
    return {
        **base,
        "start": sub.index[0].date().isoformat(),
        "rows": int(len(sub)),
        "ann_return": float(wealth.iloc[-1] ** (1.0 / years) - 1.0),
        "ann_vol": ann_vol,
        "max_dd": max_drawdown(wealth),
        "sharpe_repo": sharpe,
        "trades": int((sub["turnover"].astype(float).fillna(0.0) > 1e-12).sum()),
        "cost_total": float(sub["cost"].astype(float).fillna(0.0).sum()),
        "turnover_total": float(sub["turnover"].astype(float).fillna(0.0).sum()),
        "avg_exposure_effective": float(exposure_effective.mean()),
        "avg_final_exposure": float(final_exposure.mean()),
        "avg_nav_defense_scale_effective": float(scale_effective.mean()),
        "avg_nav_defense_scale_next": float(scale_next.mean()),
        "defense_day_ratio": float(defense_on.mean()),
        "trigger_count": int(sub["nav_defense_triggered"].astype(bool).sum()),
        "recovery_count": int(sub["nav_defense_recovered"].astype(bool).sum()),
        "reason": reason,
    }


def build_window_metrics(scan_summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for candidate, group in scan_summary.groupby("candidate", sort=False):
        first = group.iloc[0]
        row: dict[str, object] = {
            "candidate": candidate,
            "baseline_candidate": first["baseline_candidate"],
            "line_role": first["line_role"],
            "lookback": int(first["lookback"]),
            "r2_threshold": float(first["r2_threshold"]),
            "r2_label": first["r2_label"],
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
            "nav_defense_enabled": bool(first["nav_defense_enabled"]),
            "nav_enter_threshold": first["nav_enter_threshold"],
            "nav_exit_threshold": first["nav_exit_threshold"],
            "nav_defense_scale": float(first["nav_defense_scale"]),
            "nav_label": first["nav_label"],
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
                row[f"avg_exposure_effective_{segment}"] = source["avg_exposure_effective"]
                row[f"avg_final_exposure_{segment}"] = source["avg_final_exposure"]
                row[f"avg_nav_defense_scale_effective_{segment}"] = source["avg_nav_defense_scale_effective"]
                row[f"avg_nav_defense_scale_next_{segment}"] = source["avg_nav_defense_scale_next"]
                row[f"defense_day_ratio_{segment}"] = source["defense_day_ratio"]
                row[f"trigger_count_{segment}"] = source["trigger_count"]
                row[f"recovery_count_{segment}"] = source["recovery_count"]
        base_rows = scan_summary[scan_summary["candidate"].eq(first["baseline_candidate"])]
        for segment in SEGMENTS:
            base_sub = base_rows[base_rows["segment"].eq(segment)]
            if base_sub.empty:
                row[f"ann_delta_{segment}_pp"] = np.nan
                row[f"mdd_improve_{segment}_pp"] = np.nan
            else:
                base = base_sub.iloc[0]
                ann = row[f"ann_return_{segment}"]
                dd = row[f"max_dd_{segment}"]
                row[f"ann_delta_{segment}_pp"] = (
                    (ann - base["ann_return"]) * 100.0 if pd.notna(ann) and pd.notna(base["ann_return"]) else np.nan
                )
                row[f"mdd_improve_{segment}_pp"] = (
                    (dd - base["max_dd"]) * 100.0 if pd.notna(dd) and pd.notna(base["max_dd"]) else np.nan
                )
        rows.append(row)
    out = pd.DataFrame(rows)
    out["_enter_sort"] = out["nav_enter_threshold"].fillna(-1.0)
    out["_exit_sort"] = out["nav_exit_threshold"].fillna(-1.0)
    out = out.sort_values(
        [
            "lookback",
            "r2_threshold",
            "switch_buffer",
            "entry_fraction",
            "decay_label",
            "_enter_sort",
            "_exit_sort",
            "nav_defense_scale",
        ]
    ).drop(columns=["_enter_sort", "_exit_sort"])
    return apply_pass_flags(out)


def apply_pass_flags(window_metrics: pd.DataFrame) -> pd.DataFrame:
    out = window_metrics.copy()
    pass_rows = []
    for _, row in out.iterrows():
        if not bool(row["nav_defense_enabled"]):
            pass_rows.append(
                {
                    "dd_improve_window_count": 0,
                    "return_tolerance_ok": False,
                    "full_mdd_improved": False,
                    "material_defense": False,
                    "layer7_pass": False,
                    "pass_reason": "baseline/no NAV defense",
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
        material_defense = bool(
            pd.notna(row.get("trigger_count_full", np.nan))
            and float(row.get("trigger_count_full", 0.0)) > 0.0
            and pd.notna(row.get("defense_day_ratio_full", np.nan))
            and float(row.get("defense_day_ratio_full", 0.0)) > 0.0
        )
        layer7_pass = bool(full_mdd_improved and dd_count >= 3 and tolerance_ok and material_defense)
        reason = (
            "pass"
            if layer7_pass
            else f"full_mdd={full_mdd_improved};dd_windows={dd_count};return_tol={tolerance_ok};material={material_defense}"
        )
        pass_rows.append(
            {
                "dd_improve_window_count": dd_count,
                "return_tolerance_ok": tolerance_ok,
                "full_mdd_improved": full_mdd_improved,
                "material_defense": material_defense,
                "layer7_pass": layer7_pass,
                "pass_reason": reason,
            }
        )
    return pd.concat([out.reset_index(drop=True), pd.DataFrame(pass_rows)], axis=1)


def select_candidate(window_metrics: pd.DataFrame) -> dict[str, object]:
    passed = window_metrics[window_metrics["layer7_pass"].astype(bool)].copy()
    primary_passed = passed[
        passed["lookback"].eq(PRIMARY_LOOKBACK)
        & passed["r2_threshold"].eq(PRIMARY_R2)
        & passed["switch_buffer"].eq(PRIMARY_SWITCH_BUFFER)
        & passed["entry_fraction"].eq(PRIMARY_ENTRY_FRACTION)
        & passed["decay_ratio_threshold"].eq(PRIMARY_DECAY_RATIO)
        & passed["recovery_ratio_threshold"].eq(PRIMARY_RECOVERY_RATIO)
        & passed["confirm_days"].eq(PRIMARY_CONFIRM_DAYS)
        & passed["derisk_scale"].eq(PRIMARY_DERISK_SCALE)
    ].copy()
    if not primary_passed.empty:
        selected = primary_passed.sort_values(
            ["ann_return_full", "mdd_improve_full_pp", "defense_day_ratio_full"],
            ascending=[False, False, True],
        ).iloc[0].to_dict()
        decision = "carry_forward_primary_nav_defense_pass"
        stability = "primary_pass"
    else:
        primary_baseline = window_metrics[
            window_metrics["lookback"].eq(PRIMARY_LOOKBACK)
            & window_metrics["r2_threshold"].eq(PRIMARY_R2)
            & window_metrics["switch_buffer"].eq(PRIMARY_SWITCH_BUFFER)
            & window_metrics["entry_fraction"].eq(PRIMARY_ENTRY_FRACTION)
            & window_metrics["decay_ratio_threshold"].eq(PRIMARY_DECAY_RATIO)
            & window_metrics["recovery_ratio_threshold"].eq(PRIMARY_RECOVERY_RATIO)
            & window_metrics["confirm_days"].eq(PRIMARY_CONFIRM_DAYS)
            & window_metrics["derisk_scale"].eq(PRIMARY_DERISK_SCALE)
            & (~window_metrics["nav_defense_enabled"].astype(bool))
        ]
        selected = primary_baseline.iloc[0].to_dict()
        if not passed.empty:
            decision = "do_not_add_nav_defense_keep_layer6_primary_watch_nonprimary"
            stability = "nonprimary_watch_only"
        else:
            decision = "do_not_add_nav_defense_keep_layer6_primary"
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
    row["notes"] = "Full official V1.1 chain including target-vol and overheat; context only, not Layer7 pass baseline"
    return row


def row_from_window(source: dict[str, object], candidate: str, ctype: str, notes: str) -> dict[str, object]:
    row = {
        "candidate": candidate,
        "candidate_type": ctype,
        "lookback": source["lookback"],
        "r2_threshold": source["r2_threshold"],
        "switch_buffer": source["switch_buffer"],
        "entry_fraction": source["entry_fraction"],
        "decay_label": source["decay_label"],
        "nav_label": source["nav_label"],
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
            candidate_label(28, 0.50, 1.00, 0.75, 0.55, 0.85, 3, 0.75, None, None, None),
            "layer6_carried_baseline",
            "Layer6 carried primary line before NAV defense",
            None,
        ),
        (
            str(selected["candidate"]),
            "layer7_selected",
            "Selected Layer7 line under the documented pass rule",
            None,
        ),
        (
            candidate_label(28, 0.50, 1.00, 0.75, 0.55, 0.85, 3, 0.50, None, None, None),
            "decay_scale_neighbor_nav_off",
            "More defensive Layer6 neighbor before NAV defense",
            None,
        ),
        (
            candidate_label(32, 0.50, 1.00, 0.75, 0.55, 0.85, 1, 0.75, None, None, None),
            "return_peak_watch_nav_off",
            "Return-peak watch line before NAV defense",
            None,
        ),
        (
            candidate_label(25, 0.20, 1.05, 0.50, None, None, None, None, None, None, None),
            "original_layer7_same_stage_nav_off",
            "Original first-layer parameter plus original R2 0.20, switch buffer 1.05, initial entry fraction 0.50; no momentum decay and no NAV defense",
            "orig_layer7_lb25_r2_0p20_buf_1p05_entry_0p50_decay_off_nav_off",
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


def fmt_num(value: object, digits: int = 2) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value):.{digits}f}"


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
        & window_metrics["decay_ratio_threshold"].eq(PRIMARY_DECAY_RATIO)
        & window_metrics["recovery_ratio_threshold"].eq(PRIMARY_RECOVERY_RATIO)
        & window_metrics["confirm_days"].eq(PRIMARY_CONFIRM_DAYS)
        & window_metrics["derisk_scale"].eq(PRIMARY_DERISK_SCALE)
    ].copy()
    primary_display = pd.concat(
        [
            primary[~primary["nav_defense_enabled"].astype(bool)],
            primary[primary["nav_defense_enabled"].astype(bool)].sort_values(
                ["layer7_pass", "ann_return_full", "mdd_improve_full_pp"],
                ascending=[False, False, False],
            ).head(12),
        ],
        ignore_index=True,
    )
    top_pass = window_metrics[window_metrics["layer7_pass"].astype(bool)].sort_values(
        ["ann_return_full", "mdd_improve_full_pp"],
        ascending=[False, False],
    ).head(10)
    if top_pass.empty:
        top_pass = window_metrics[window_metrics["nav_defense_enabled"].astype(bool)].sort_values(
            "mdd_improve_full_pp",
            ascending=False,
        ).head(10)

    lines = [
        "# Sub-D Dynamic ChiNext Proxy Layer 7 NAV Defense Scan",
        "",
        "## Run Metadata",
        "",
        f"- Run folder: `{run_folder}`",
        "- Layer: `Layer 7`",
        "- Strategy: dynamic ChiNext proxy pool, 2007-2016.",
        "- Entrypoint: `run_subd_proxy_dynamic_cyb_layer7_nav_defense_scan.py`",
        "",
        "## Research Question",
        "",
        "Add strategy-level NAV drawdown defense after the carried Layer 6 score-peak momentum-decay line.",
        "",
        "## Implementation Anchor",
        "",
        "- Data loader reused from `run_subd_proxy_dynamic_cyb_layer0.py`.",
        "- Base curves reuse Layer 4 staged entry plus Layer 6 `apply_momentum_decay_layer`.",
        "- NAV defense uses the pre-NAV-defense Layer 6 NAV drawdown as `nav_defense_base_dd`.",
        "- T close base DD determines the next-session defense scale; effective scale is shifted one session.",
        "- NAV/exposure/cost recomputation reuses `_recompute_final_exposure_nav` from `run_subd_six_etf_v1_1.py`.",
        "- No target-vol or overheat in this layer.",
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
        "- NAV defense cost is charged when the defense scale changes final exposure.",
        "- Calendar: A-share trading days; US adjusted closes are forward-filled onto that calendar for this proxy diagnostic.",
        "- Trades involving a forward-filled trade leg are blocked by the base staged-entry path for that day.",
        "",
        "## Runtime Override Plan",
        "",
        f"- Lines carried: `{[(lb, r2, buf, entry, dr, rr, c, sc, role, scan) for lb, r2, buf, entry, dr, rr, c, sc, role, scan in LINE_GRID]}`.",
        f"- NAV enter thresholds: `{list(NAV_ENTER_THRESHOLDS)}`.",
        f"- NAV exit thresholds: `{list(NAV_EXIT_THRESHOLDS)}`.",
        f"- Defense scales: `{list(DEFENSE_SCALES)}`.",
        "- Baseline: same `lookback + R2 + switch buffer + entry fraction + momentum decay` with NAV defense disabled.",
        f"- Pass rule: Full maxDD improves by more than `{MDD_IMPROVE_EPS_PP:.2f}pp`; at least 3 of the 4 available windows improve maxDD by more than `{MDD_IMPROVE_EPS_PP:.2f}pp`; Full/5Y annualized return lag <=1pp and 3Y/1Y lag <=3pp versus same-line no-NAV-defense baseline.",
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
        "- `daily_outputs/nav_defense_daily_curves.csv`",
        "- `sources.csv`",
        "",
        "## Primary Line Results",
        "",
        "| Candidate | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Full Ann Delta pp | Full MDD Improve pp | Trigger Full | Defense Days Full | Pass | Reason |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for _, row in primary_display.iterrows():
        lines.append(
            "| "
            f"{row['candidate']} | {pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{pct(row['ann_return_last_10y'])} | {pct(row['max_dd_last_10y'])} | "
            f"{pct(row['ann_return_last_5y'])} | {pct(row['max_dd_last_5y'])} | "
            f"{pct(row['ann_return_last_3y'])} | {pct(row['max_dd_last_3y'])} | "
            f"{pct(row['ann_return_last_1y'])} | {pct(row['max_dd_last_1y'])} | "
            f"{fmt_num(row['ann_delta_full_pp'])} | {fmt_num(row['mdd_improve_full_pp'])} | "
            f"{int(row['trigger_count_full']) if pd.notna(row['trigger_count_full']) else 'N/A'} | "
            f"{pct(row['defense_day_ratio_full'])} | {bool(row['layer7_pass'])} | {row['pass_reason']} |"
        )
    lines.extend(
        [
            "",
            "## Passing Or Best Candidates",
            "",
            "| Candidate | Role | Full Ann. | Full MDD | Full MDD Improve pp | DD Improve Windows | Trigger Full | Defense Days Full | Pass |",
            "|---|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for _, row in top_pass.iterrows():
        lines.append(
            "| "
            f"{row['candidate']} | {row['line_role']} | {pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{fmt_num(row['mdd_improve_full_pp'])} | {int(row['dd_improve_window_count'])} | "
            f"{int(row['trigger_count_full']) if pd.notna(row['trigger_count_full']) else 'N/A'} | "
            f"{pct(row['defense_day_ratio_full'])} | {bool(row['layer7_pass'])} |"
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
            f"{row['candidate']} | {row['candidate_type']} | "
            f"{pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{pct(row['ann_return_last_10y'])} | {pct(row['max_dd_last_10y'])} | "
            f"{pct(row['ann_return_last_5y'])} | {pct(row['max_dd_last_5y'])} | "
            f"{pct(row['ann_return_last_3y'])} | {pct(row['max_dd_last_3y'])} | "
            f"{pct(row['ann_return_last_1y'])} | {pct(row['max_dd_last_1y'])} | "
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
            "- 10Y remains N/A by sample length: 2432 sessions is less than 2520 trading days.",
            "",
            "## Decision",
            "",
            f"- Decision: `{selection['decision']}`.",
            "- Stop here before any later overlay.",
            "",
            "## User-Facing Summary",
            "",
            f"Layer 7 selected `{selected['candidate']}` under the documented pass rule. See `window_metrics.csv` for all NAV defense lines.",
            "",
            "## Source Audit",
            "",
            sources.to_markdown(index=False),
            "",
        ]
    )
    (run_folder / "record.md").write_text("\n".join(lines), encoding="utf-8")


def candidate_grid(scan_nav: bool) -> list[tuple[float | None, float | None, float | None]]:
    grid: list[tuple[float | None, float | None, float | None]] = [(None, None, None)]
    if not scan_nav:
        return grid
    for enter in NAV_ENTER_THRESHOLDS:
        for exit_value in NAV_EXIT_THRESHOLDS:
            if exit_value >= enter:
                continue
            for scale in DEFENSE_SCALES:
                grid.append((float(enter), float(exit_value), float(scale)))
    return grid


def daily_output_frame(curves: list[pd.DataFrame]) -> pd.DataFrame:
    cols = [
        "candidate",
        "baseline_candidate",
        "line_role",
        "lookback",
        "r2_threshold",
        "switch_buffer",
        "entry_fraction",
        "decay_label",
        "nav_label",
        "nav_defense_enabled",
        "nav_enter_threshold",
        "nav_exit_threshold",
        "nav_defense_scale",
        "position_before",
        "fraction_before",
        "position",
        "holding_fraction",
        "score_decay_multiplier_effective",
        "score_decay_multiplier_next",
        "nav_defense_base_dd",
        "nav_defense_scale_effective",
        "nav_defense_scale_next",
        "nav_defense_on_effective",
        "nav_defense_on_next",
        "nav_defense_triggered",
        "nav_defense_recovered",
        "combined_overlay_scale_effective",
        "combined_overlay_scale_next",
        "asset_return",
        "gross_return",
        "turnover",
        "cost",
        "return",
        "nav",
        "return_before_nav_defense",
        "nav_before_nav_defense",
        "exposure_effective",
        "final_exposure_after_overheat",
    ]
    out = pd.concat([curve[[c for c in cols if c in curve.columns]] for curve in curves], axis=0)
    return out.reset_index()


def run_scan(start_date: pd.Timestamp, end_date: pd.Timestamp, run_folder: Path) -> None:
    started = time.time()
    run_folder.mkdir(parents=True, exist_ok=True)
    daily_dir = run_folder / "daily_outputs"
    daily_dir.mkdir(parents=True, exist_ok=True)

    prices, sources = layer0.build_proxy_panel(start_date, end_date)
    base_curves = {}
    for line in LINE_GRID:
        lookback, r2_threshold, switch_buffer, entry_fraction, decay_ratio, recovery_ratio, confirm_days, derisk_scale, line_role, _scan_nav = line
        staged = layer4.run_staged_line(
            prices,
            end_date,
            lookback,
            r2_threshold,
            switch_buffer,
            entry_fraction,
            line_role,
        )
        base_curves[line] = layer6.apply_momentum_decay_layer(
            staged,
            lookback,
            r2_threshold,
            switch_buffer,
            entry_fraction,
            decay_ratio,
            recovery_ratio,
            confirm_days,
            derisk_scale,
            line_role,
        )

    curves = []
    summary_rows = []
    for line, base_curve in base_curves.items():
        lookback, r2_threshold, switch_buffer, entry_fraction, decay_ratio, recovery_ratio, confirm_days, derisk_scale, line_role, scan_nav = line
        for nav_enter, nav_exit, defense_scale in candidate_grid(scan_nav):
            curve = apply_nav_defense_layer(
                base_curve,
                lookback,
                r2_threshold,
                switch_buffer,
                entry_fraction,
                decay_ratio,
                recovery_ratio,
                confirm_days,
                derisk_scale,
                nav_enter,
                nav_exit,
                defense_scale,
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
    daily = daily_output_frame(curves)

    scan_summary.to_csv(run_folder / "scan_summary.csv", index=False, encoding="utf-8-sig")
    window_metrics.to_csv(run_folder / "window_metrics.csv", index=False, encoding="utf-8-sig")
    comparison_list.to_csv(run_folder / "comparison_list.csv", index=False, encoding="utf-8-sig")
    daily.to_csv(daily_dir / "nav_defense_daily_curves.csv", index=False, encoding="utf-8-sig")
    sources.to_csv(run_folder / "sources.csv", index=False, encoding="utf-8-sig")

    metadata_path = run_folder / "scan_meta.json"
    meta = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    command = (
        "python run_subd_proxy_dynamic_cyb_layer7_nav_defense_scan.py "
        f"--start-date {start_date.date()} --end-date {end_date.date()} --run-folder {run_folder}"
    )
    meta.update(
        {
            "phase": "scan_complete_unfinalized",
            "scan_type": "layer7_grid_scan",
            "parameter_group": "layer7_nav_drawdown_gate",
            "baseline": {"rule": "same lookback + R2 + switch_buffer + entry_fraction + momentum_decay with NAV defense disabled"},
            "candidate_grid": [
                {
                    "lookback": int(lookback),
                    "r2_threshold": float(r2_threshold),
                    "switch_buffer": float(switch_buffer),
                    "entry_fraction": float(entry_fraction),
                    "decay_ratio": None if decay_ratio is None else float(decay_ratio),
                    "recovery_ratio": None if recovery_ratio is None else float(recovery_ratio),
                    "confirm_days": None if confirm_days is None else int(confirm_days),
                    "derisk_scale": None if derisk_scale is None else float(derisk_scale),
                    "line_role": line_role,
                    "nav_enter": None if nav_enter is None else float(nav_enter),
                    "nav_exit": None if nav_exit is None else float(nav_exit),
                    "defense_scale": None if defense_scale is None else float(defense_scale),
                }
                for lookback, r2_threshold, switch_buffer, entry_fraction, decay_ratio, recovery_ratio, confirm_days, derisk_scale, line_role, scan_nav in LINE_GRID
                for nav_enter, nav_exit, defense_scale in candidate_grid(scan_nav)
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
                "nav_defense_rebalance_cost_included": True,
            },
            "execution_assumptions": {
                "signal": "close-to-close weighted-slope ranking with fixed R2 threshold, switch buffer, staged entry, and Layer6 score-peak decay",
                "nav_defense": "pre-NAV-defense Layer6 NAV DD at T close sets next-session defense scale",
                "nav_defense_dd_basis": "nav_before_nav_defense; not recursive final NAV",
                "target_vol": "disabled because Layer 5 rejected target-vol for this branch",
                "overheat": "not tested in Layer 7",
                "mixed_market_calendar": "diagnostic A-share calendar with US proxy forward-filled; base trades on stale trade legs blocked",
            },
            "pass_rule": {
                "mdd_improve_eps_pp": MDD_IMPROVE_EPS_PP,
                "available_windows": list(AVAILABLE_PASS_SEGMENTS),
                "return_lag_tolerance_pp": {"full": 1.0, "last_5y": 1.0, "last_3y": 3.0, "last_1y": 3.0},
            },
            "layer7_selection": selection,
            "comparison_reference": {
                "layer6_carried_candidate": candidate_label(28, 0.50, 1.00, 0.75, 0.55, 0.85, 3, 0.75, None, None, None),
                "original_layer7_same_stage_candidate": "orig_layer7_lb25_r2_0p20_buf_1p05_entry_0p50_decay_off_nav_off",
                "original_full_strategy_candidate": "orig_full_v1_1_reference",
            },
            "outputs": {
                "scan_summary": str(run_folder / "scan_summary.csv"),
                "window_metrics": str(run_folder / "window_metrics.csv"),
                "comparison_list": str(run_folder / "comparison_list.csv"),
                "daily_curves": str(daily_dir / "nav_defense_daily_curves.csv"),
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
    print(f"WROTE {daily_dir / 'nav_defense_daily_curves.csv'}")
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
        & window_metrics["decay_ratio_threshold"].eq(PRIMARY_DECAY_RATIO)
        & window_metrics["recovery_ratio_threshold"].eq(PRIMARY_RECOVERY_RATIO)
        & window_metrics["confirm_days"].eq(PRIMARY_CONFIRM_DAYS)
        & window_metrics["derisk_scale"].eq(PRIMARY_DERISK_SCALE)
    ].copy()
    display_cols = [
        "candidate",
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
        "defense_day_ratio_full",
        "layer7_pass",
        "pass_reason",
    ]
    print(
        primary.sort_values(["layer7_pass", "ann_return_full", "mdd_improve_full_pp"], ascending=[False, False, False])
        .head(20)[display_cols]
        .to_string(index=False)
    )


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
