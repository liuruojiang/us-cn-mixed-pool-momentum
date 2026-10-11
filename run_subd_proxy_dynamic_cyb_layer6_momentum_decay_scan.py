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
import run_subd_six_etf_v1_1 as v11


DEFAULT_START = pd.Timestamp("2007-01-01")
DEFAULT_END = pd.Timestamp("2016-12-30")
DEFAULT_RUN_FOLDER = Path(
    "quant_param_scan_runs"
    "/20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_momentum_decay_layer6_score_peak_decay"
)
PRIMARY_LOOKBACK = 28
PRIMARY_R2 = 0.50
PRIMARY_SWITCH_BUFFER = 1.00
PRIMARY_ENTRY_FRACTION = 0.75
LINE_GRID: tuple[tuple[int, float, float, float, str], ...] = (
    (28, 0.50, 1.00, 0.75, "layer5_carried_primary"),
    (28, 0.50, 1.00, 0.67, "entry_neighbor"),
    (28, 0.40, 1.00, 0.75, "r2_neighbor"),
    (32, 0.50, 1.00, 0.75, "return_peak_watch"),
    (25, 0.20, 1.05, 0.50, "original_layer6_same_stage"),
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


def git_value(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def pct_label(value: float) -> str:
    return f"{float(value):.2f}".replace(".", "p")


def scale_label(value: float) -> str:
    return f"{float(value):.2f}".replace(".", "p")


def decay_label(
    decay_ratio: float | None,
    recovery_ratio: float | None,
    confirm_days: int | None,
    derisk_scale: float | None,
) -> str:
    if decay_ratio is None:
        return "decay_off"
    return (
        f"decay_{pct_label(decay_ratio)}"
        f"_rec_{pct_label(float(recovery_ratio))}"
        f"_c{int(confirm_days)}"
        f"_scale_{scale_label(float(derisk_scale))}"
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
) -> str:
    return (
        f"lb_{lookback}_r2_{layer2.r2_label(r2_threshold)}"
        f"_buf_{layer3.buffer_label(switch_buffer)}"
        f"_entry_{layer4.fraction_label(entry_fraction)}"
        f"_{decay_label(decay_ratio, recovery_ratio, confirm_days, derisk_scale)}"
    )


def active_score_series(curve: pd.DataFrame) -> pd.Series:
    values: list[float] = []
    for _, row in curve.iterrows():
        asset = str(row.get("position", "CASH"))
        fraction = float(row.get("holding_fraction", 0.0) or 0.0)
        if asset == "CASH" or fraction <= 1e-12:
            values.append(np.nan)
            continue
        col = f"score_{asset}"
        score = row.get(col, np.nan)
        try:
            score_float = float(score)
        except Exception:
            score_float = math.nan
        values.append(score_float if math.isfinite(score_float) and score_float > 0.0 else np.nan)
    return pd.Series(values, index=curve.index, dtype=float)


def score_peak_decay_state(
    curve: pd.DataFrame,
    decay_ratio: float,
    recovery_ratio: float,
    confirm_days: int,
    derisk_scale: float,
) -> pd.DataFrame:
    if not 0.0 < decay_ratio < 1.0:
        raise ValueError("decay_ratio must be in (0, 1)")
    if not decay_ratio < recovery_ratio <= 1.0:
        raise ValueError("recovery_ratio must be in (decay_ratio, 1]")
    if confirm_days < 1:
        raise ValueError("confirm_days must be >= 1")
    if not 0.0 <= derisk_scale <= 1.0:
        raise ValueError("derisk_scale must be in [0, 1]")

    position = curve["position"].fillna("CASH").astype(str)
    fraction = curve["holding_fraction"].fillna(0.0).astype(float)
    score = active_score_series(curve)

    multiplier_next: list[float] = []
    score_peak_values: list[float] = []
    ratio_values: list[float] = []
    overlay_on: list[bool] = []
    triggered: list[bool] = []
    recovered: list[bool] = []
    trade_ids: list[int] = []
    waiting_flags: list[bool] = []

    trade_id = 0
    prev_asset = "CASH"
    score_peak: float | None = None
    in_decay = False
    waiting_for_new_peak = False
    rearm_peak: float | None = None
    below_count = 0

    for idx in curve.index:
        asset = str(position.loc[idx])
        frac = float(fraction.loc[idx])
        cur_score = float(score.loc[idx]) if pd.notna(score.loc[idx]) else math.nan
        eligible = asset != "CASH" and frac > 1e-12 and math.isfinite(cur_score) and cur_score > 0.0
        new_trade = eligible and (asset != prev_asset or score_peak is None)

        if not eligible:
            score_peak = None
            in_decay = False
            waiting_for_new_peak = False
            rearm_peak = None
            below_count = 0
            prev_asset = asset
            multiplier_next.append(1.0)
            score_peak_values.append(math.nan)
            ratio_values.append(math.nan)
            overlay_on.append(False)
            triggered.append(False)
            recovered.append(False)
            trade_ids.append(trade_id)
            waiting_flags.append(False)
            continue

        if new_trade:
            trade_id += 1
            score_peak = cur_score
            in_decay = False
            waiting_for_new_peak = False
            rearm_peak = None
            below_count = 0
        else:
            if score_peak is None or cur_score > score_peak:
                score_peak = cur_score
                if waiting_for_new_peak:
                    waiting_for_new_peak = False
                    rearm_peak = None

        ratio = cur_score / score_peak if score_peak and score_peak > 0 else math.nan
        trigger_today = False
        recover_today = False

        if in_decay:
            if math.isfinite(ratio) and ratio >= recovery_ratio:
                in_decay = False
                waiting_for_new_peak = True
                rearm_peak = score_peak
                below_count = 0
                recover_today = True
        elif waiting_for_new_peak:
            if rearm_peak is not None and score_peak is not None and score_peak > rearm_peak + 1e-12:
                waiting_for_new_peak = False
                rearm_peak = None
            below_count = 0
        else:
            if math.isfinite(ratio) and ratio <= decay_ratio:
                below_count += 1
            else:
                below_count = 0
            if below_count >= confirm_days:
                in_decay = True
                trigger_today = True

        multiplier_next.append(float(derisk_scale) if in_decay else 1.0)
        score_peak_values.append(float(score_peak) if score_peak is not None else math.nan)
        ratio_values.append(float(ratio) if math.isfinite(ratio) else math.nan)
        overlay_on.append(bool(in_decay))
        triggered.append(bool(trigger_today))
        recovered.append(bool(recover_today))
        trade_ids.append(int(trade_id))
        waiting_flags.append(bool(waiting_for_new_peak))
        prev_asset = asset

    next_scale = pd.Series(multiplier_next, index=curve.index, dtype=float)
    effective_scale = next_scale.shift(1).fillna(1.0)
    return pd.DataFrame(
        {
            "score_decay_active_score": score,
            "score_decay_multiplier_next": next_scale,
            "score_decay_multiplier_effective": effective_scale,
            "score_decay_peak": pd.Series(score_peak_values, index=curve.index, dtype=float),
            "score_decay_ratio": pd.Series(ratio_values, index=curve.index, dtype=float),
            "score_decay_overlay_on": pd.Series(overlay_on, index=curve.index, dtype=bool),
            "score_decay_triggered": pd.Series(triggered, index=curve.index, dtype=bool),
            "score_decay_recovered": pd.Series(recovered, index=curve.index, dtype=bool),
            "score_decay_trade_id": pd.Series(trade_ids, index=curve.index, dtype="Int64"),
            "score_decay_waiting_for_new_peak": pd.Series(waiting_flags, index=curve.index, dtype=bool),
        },
        index=curve.index,
    )


def apply_momentum_decay_layer(
    base_curve: pd.DataFrame,
    lookback: int,
    r2_threshold: float,
    switch_buffer: float,
    entry_fraction: float,
    decay_ratio: float | None,
    recovery_ratio: float | None,
    confirm_days: int | None,
    derisk_scale: float | None,
    line_role: str,
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
        decay = score_peak_decay_state(
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
        active_score = active_score_series(curve)
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
        r2_threshold,
        switch_buffer,
        entry_fraction,
        decay_ratio,
        recovery_ratio,
        confirm_days,
        derisk_scale,
    )
    curve["line_role"] = line_role
    curve["lookback"] = int(lookback)
    curve["r2_threshold"] = float(r2_threshold)
    curve["r2_label"] = layer2.r2_label(r2_threshold)
    curve["switch_buffer"] = float(switch_buffer)
    curve["buffer_label"] = layer3.buffer_label(switch_buffer)
    curve["entry_fraction"] = float(entry_fraction)
    curve["entry_label"] = layer4.fraction_label(entry_fraction)
    curve["momentum_decay_enabled"] = bool(enabled)
    curve["decay_ratio_threshold"] = np.nan if decay_ratio is None else float(decay_ratio)
    curve["recovery_ratio_threshold"] = np.nan if recovery_ratio is None else float(recovery_ratio)
    curve["confirm_days"] = np.nan if confirm_days is None else int(confirm_days)
    curve["derisk_scale"] = 1.0 if derisk_scale is None else float(derisk_scale)
    curve["decay_label"] = decay_label(decay_ratio, recovery_ratio, confirm_days, derisk_scale)
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
            float(first["r2_threshold"]),
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
                row[f"avg_decay_multiplier_effective_{segment}"] = source["avg_decay_multiplier_effective"]
                row[f"avg_decay_multiplier_next_{segment}"] = source["avg_decay_multiplier_next"]
                row[f"decay_day_ratio_{segment}"] = source["decay_day_ratio"]
                row[f"trigger_count_{segment}"] = source["trigger_count"]
                row[f"recovery_count_{segment}"] = source["recovery_count"]

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
    out["_decay_sort"] = out["decay_ratio_threshold"].fillna(-1.0)
    out["_rec_sort"] = out["recovery_ratio_threshold"].fillna(-1.0)
    out["_confirm_sort"] = out["confirm_days"].fillna(0)
    out = out.sort_values(
        ["lookback", "r2_threshold", "switch_buffer", "entry_fraction", "_decay_sort", "_rec_sort", "_confirm_sort", "derisk_scale"]
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


def select_candidate(window_metrics: pd.DataFrame) -> dict[str, object]:
    passed = window_metrics[window_metrics["layer6_pass"].astype(bool)].copy()
    primary_passed = passed[
        passed["lookback"].eq(PRIMARY_LOOKBACK)
        & passed["r2_threshold"].eq(PRIMARY_R2)
        & passed["switch_buffer"].eq(PRIMARY_SWITCH_BUFFER)
        & passed["entry_fraction"].eq(PRIMARY_ENTRY_FRACTION)
    ].copy()
    if not primary_passed.empty:
        selected = primary_passed.sort_values(
            ["ann_return_full", "mdd_improve_full_pp", "decay_day_ratio_full"],
            ascending=[False, False, True],
        ).iloc[0].to_dict()
        decision = "carry_forward_primary_momentum_decay_pass"
        stability = "primary_pass"
    else:
        primary_baseline = window_metrics[
            window_metrics["lookback"].eq(PRIMARY_LOOKBACK)
            & window_metrics["r2_threshold"].eq(PRIMARY_R2)
            & window_metrics["switch_buffer"].eq(PRIMARY_SWITCH_BUFFER)
            & window_metrics["entry_fraction"].eq(PRIMARY_ENTRY_FRACTION)
            & (~window_metrics["momentum_decay_enabled"].astype(bool))
        ]
        selected = primary_baseline.iloc[0].to_dict()
        if not passed.empty:
            decision = "do_not_add_momentum_decay_keep_layer5_carried_primary_watch_nonprimary"
            stability = "nonprimary_watch_only"
        else:
            decision = "do_not_add_momentum_decay_keep_layer5_carried_primary"
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
    row["notes"] = "Full official V1.1 chain including target-vol and overheat; context only, not Layer6 pass baseline"
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
            candidate_label(28, 0.50, 1.00, 0.75, None, None, None, None),
            "layer5_carried_baseline",
            "Layer5 rejected target-vol, so this is the carried Layer4 primary line before momentum decay",
            None,
        ),
        (
            candidate_label(28, 0.50, 1.00, 0.75, 0.55, 0.95, 1, 0.0),
            "primary_55_95_cash_decay",
            "Primary line with score-peak decay 55%, recovery 95%, one-day confirm, derisk to cash",
            None,
        ),
        (
            candidate_label(28, 0.50, 1.00, 0.75, 0.55, 0.95, 1, 0.50),
            "primary_55_95_half_decay",
            "Primary line with score-peak decay 55%, recovery 95%, one-day confirm, derisk to 50%",
            None,
        ),
        (
            str(selected["candidate"]),
            "layer6_selected",
            "Selected Layer6 line under the documented pass rule",
            None,
        ),
        (
            candidate_label(32, 0.50, 1.00, 0.75, 0.55, 0.95, 1, 0.0),
            "return_peak_watch_decay",
            "Return peak watch line with the same momentum-decay tuple",
            None,
        ),
        (
            candidate_label(25, 0.20, 1.05, 0.50, None, None, None, None),
            "original_layer6_same_stage_decay_off",
            "Original first-layer parameter plus original R2 0.20, switch buffer 1.05, initial entry fraction 0.50; no momentum decay in this layer",
            "orig_layer6_lb25_r2_0p20_buf_1p05_entry_0p50_decay_off",
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
    ].copy()
    primary["_enabled_sort"] = primary["momentum_decay_enabled"].astype(int)
    primary["_ann_sort"] = primary["ann_return_full"].fillna(-999.0)
    primary = primary.sort_values(["_enabled_sort", "_ann_sort"], ascending=[True, False]).drop(
        columns=["_enabled_sort", "_ann_sort"]
    )
    primary_display = pd.concat(
        [
            primary[~primary["momentum_decay_enabled"].astype(bool)],
            primary[primary["momentum_decay_enabled"].astype(bool)].sort_values(
                ["layer6_pass", "ann_return_full", "mdd_improve_full_pp"],
                ascending=[False, False, False],
            ).head(12),
        ],
        ignore_index=True,
    )
    top_pass = window_metrics[window_metrics["layer6_pass"].astype(bool)].sort_values(
        ["ann_return_full", "mdd_improve_full_pp"],
        ascending=[False, False],
    ).head(10)
    if top_pass.empty:
        top_pass = window_metrics[window_metrics["momentum_decay_enabled"].astype(bool)].sort_values(
            "mdd_improve_full_pp",
            ascending=False,
        ).head(10)

    lines = [
        "# Sub-D Dynamic ChiNext Proxy Layer 6 Momentum Decay Scan",
        "",
        "## Run Metadata",
        "",
        f"- Run folder: `{run_folder}`",
        "- Layer: `Layer 6`",
        "- Strategy: dynamic ChiNext proxy pool, 2007-2016.",
        "- Entrypoint: `run_subd_proxy_dynamic_cyb_layer6_momentum_decay_scan.py`",
        "",
        "## Research Question",
        "",
        "Add score-peak momentum decay after the carried Layer 5 decision. Since target-vol failed Layer 5, this layer starts from the Layer 4 primary line with no target-vol.",
        "",
        "## Implementation Anchor",
        "",
        "- Data loader reused from `run_subd_proxy_dynamic_cyb_layer0.py`.",
        "- Base staged-entry curves reuse Layer 4's `run_staged_line` helper.",
        "- Momentum decay uses current target holding score divided by the active trade's score peak.",
        "- After recovery, the same trade must set a new score peak before another decay cycle can trigger.",
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
        f"- Lines carried: `{[(lb, r2, buf, entry, role) for lb, r2, buf, entry, role in LINE_GRID]}`.",
        f"- Decay ratios: `{list(DECAY_RATIOS)}`.",
        f"- Recovery ratios: `{list(RECOVERY_RATIOS)}`.",
        f"- Confirm days: `{list(CONFIRM_DAYS)}`.",
        f"- Derisk scales: `{list(DERISK_SCALES)}`.",
        "- Baseline: same `lookback + R2 + switch buffer + entry fraction` with momentum decay disabled.",
        f"- Pass rule: Full maxDD improves by more than `{MDD_IMPROVE_EPS_PP:.2f}pp`; at least 3 of the 4 available windows improve maxDD by more than `{MDD_IMPROVE_EPS_PP:.2f}pp`; Full/5Y annualized return lag <=1pp and 3Y/1Y lag <=3pp versus same-line no-decay baseline.",
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
        "- `daily_outputs/momentum_decay_daily_curves.csv`",
        "- `sources.csv`",
        "",
        "## Primary Line Results",
        "",
        "| Candidate | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Full Ann Delta pp | Full MDD Improve pp | Trigger Full | Decay Days Full | Pass | Reason |",
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
            f"{pct(row['decay_day_ratio_full'])} | {bool(row['layer6_pass'])} | {row['pass_reason']} |"
        )
    lines.extend(
        [
            "",
            "## Passing Or Best Candidates",
            "",
            "| Candidate | Role | Full Ann. | Full MDD | Full MDD Improve pp | DD Improve Windows | Trigger Full | Decay Days Full | Pass |",
            "|---|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for _, row in top_pass.iterrows():
        lines.append(
            "| "
            f"{row['candidate']} | {row['line_role']} | {pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{fmt_num(row['mdd_improve_full_pp'])} | {int(row['dd_improve_window_count'])} | "
            f"{int(row['trigger_count_full']) if pd.notna(row['trigger_count_full']) else 'N/A'} | "
            f"{pct(row['decay_day_ratio_full'])} | {bool(row['layer6_pass'])} |"
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
            "- Stop here before NAV defense.",
            "",
            "## User-Facing Summary",
            "",
            f"Layer 6 selected `{selected['candidate']}` under the documented pass rule. See `window_metrics.csv` for all score-peak decay lines.",
            "",
            "## Source Audit",
            "",
            sources.to_markdown(index=False),
            "",
        ]
    )
    (run_folder / "record.md").write_text("\n".join(lines), encoding="utf-8")


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


def daily_output_frame(curves: list[pd.DataFrame]) -> pd.DataFrame:
    cols = [
        "candidate",
        "line_role",
        "lookback",
        "r2_threshold",
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

    grid = candidate_grid()
    curves = []
    summary_rows = []
    for line, base_curve in base_curves.items():
        lookback, r2_threshold, switch_buffer, entry_fraction, line_role = line
        for decay_ratio, recovery_ratio, confirm_days, derisk_scale in grid:
            curve = apply_momentum_decay_layer(
                base_curve,
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
    daily.to_csv(daily_dir / "momentum_decay_daily_curves.csv", index=False, encoding="utf-8-sig")
    sources.to_csv(run_folder / "sources.csv", index=False, encoding="utf-8-sig")

    metadata_path = run_folder / "scan_meta.json"
    meta = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    command = (
        "python run_subd_proxy_dynamic_cyb_layer6_momentum_decay_scan.py "
        f"--start-date {start_date.date()} --end-date {end_date.date()} --run-folder {run_folder}"
    )
    meta.update(
        {
            "phase": "scan_complete_unfinalized",
            "scan_type": "layer6_grid_scan",
            "parameter_group": "layer6_score_peak_momentum_decay",
            "baseline": {"rule": "same lookback + R2 + switch_buffer + entry_fraction with momentum decay disabled"},
            "candidate_grid": [
                {
                    "lookback": int(lookback),
                    "r2_threshold": float(r2_threshold),
                    "switch_buffer": float(switch_buffer),
                    "entry_fraction": float(entry_fraction),
                    "line_role": line_role,
                    "decay_ratio": None if decay_ratio is None else float(decay_ratio),
                    "recovery_ratio": None if recovery_ratio is None else float(recovery_ratio),
                    "confirm_days": None if confirm_days is None else int(confirm_days),
                    "derisk_scale": None if derisk_scale is None else float(derisk_scale),
                }
                for lookback, r2_threshold, switch_buffer, entry_fraction, line_role in LINE_GRID
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
                "signal": "close-to-close weighted-slope ranking with fixed R2 threshold, switch buffer, and staged entry",
                "momentum_decay": "current target holding score divided by active trade score peak; close signal sets next-session scale",
                "recovery": "ratio must recover to threshold; same trade needs a new score peak before another decay cycle",
                "target_vol": "disabled because Layer 5 rejected target-vol for this branch",
                "nav_defense": "not tested in Layer 6",
                "overheat": "not tested in Layer 6",
                "mixed_market_calendar": "diagnostic A-share calendar with US proxy forward-filled; base trades on stale trade legs blocked",
            },
            "pass_rule": {
                "mdd_improve_eps_pp": MDD_IMPROVE_EPS_PP,
                "available_windows": list(AVAILABLE_PASS_SEGMENTS),
                "return_lag_tolerance_pp": {"full": 1.0, "last_5y": 1.0, "last_3y": 3.0, "last_1y": 3.0},
            },
            "layer6_selection": selection,
            "comparison_reference": {
                "layer5_carried_candidate": candidate_label(28, 0.50, 1.00, 0.75, None, None, None, None),
                "original_layer6_same_stage_candidate": "orig_layer6_lb25_r2_0p20_buf_1p05_entry_0p50_decay_off",
                "original_full_strategy_candidate": "orig_full_v1_1_reference",
            },
            "outputs": {
                "scan_summary": str(run_folder / "scan_summary.csv"),
                "window_metrics": str(run_folder / "window_metrics.csv"),
                "comparison_list": str(run_folder / "comparison_list.csv"),
                "daily_curves": str(daily_dir / "momentum_decay_daily_curves.csv"),
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
    print(f"WROTE {daily_dir / 'momentum_decay_daily_curves.csv'}")
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
        "decay_day_ratio_full",
        "layer6_pass",
        "pass_reason",
    ]
    print(
        primary.sort_values(["layer6_pass", "ann_return_full", "mdd_improve_full_pp"], ascending=[False, False, False])
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
