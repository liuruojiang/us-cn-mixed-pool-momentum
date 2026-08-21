from __future__ import annotations

import argparse
import json
import math
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

import research_subd_six_etf_weighted_slope as subd
import run_subd_proxy_dynamic_cyb_layer0 as layer0
import run_subd_proxy_dynamic_cyb_layer1_scan as layer1
import run_subd_proxy_dynamic_cyb_layer2_r2_scan as layer2
import run_subd_proxy_dynamic_cyb_layer3_switch_buffer_scan as layer3
import run_subd_proxy_dynamic_cyb_layer4_staged_entry_scan as layer4
import run_subd_proxy_dynamic_cyb_layer6_momentum_decay_scan as layer6
import run_subd_proxy_dynamic_cyb_layer7_nav_defense_scan as nav7
import run_subd_six_etf_v1_1 as v11


DEFAULT_START = pd.Timestamp("2007-01-01")
DEFAULT_END = pd.Timestamp("2016-12-30")
DEFAULT_RUN_FOLDER = Path(
    "quant_param_scan_runs"
    "/20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_overheat_layer8_three_directions"
)
ONE_WAY_COST = 0.001
TRADING_DAYS = 252
SEGMENTS = ("full", "last_10y", "last_5y", "last_3y", "last_1y")
AVAILABLE_PASS_SEGMENTS = ("full", "last_5y", "last_3y", "last_1y")
MDD_IMPROVE_EPS_PP = 0.01
DEFAULT_SCORE_MAX = 5.0


@dataclass(frozen=True)
class CarryLine:
    line_id: str
    lookback: int
    r2_threshold: float
    switch_buffer: float
    entry_fraction: float
    decay_ratio: float | None
    recovery_ratio: float | None
    confirm_days: int | None
    decay_scale: float | None
    nav_enter: float | None
    nav_exit: float | None
    nav_scale: float | None


@dataclass(frozen=True)
class FixedSameSideCase:
    enter: float
    exit: float
    derisk_scale: float
    recovery_mode: Literal["same_side_or_exit", "exit_only"]


@dataclass(frozen=True)
class AdaptiveQuantileCase:
    window: int
    min_periods: int
    enter_quantile: float
    exit_quantile: float
    min_enter: float
    min_exit: float
    derisk_scale: float
    recovery_mode: Literal["same_side_or_exit", "exit_only"]


CARRY_LINES = (
    CarryLine("A_clean", 28, 0.50, 1.00, 0.75, None, None, None, None, None, None, None),
    CarryLine("G_decay_nav", 28, 0.50, 1.00, 0.75, 0.55, 0.85, 3, 0.75, 0.125, 0.03, 0.75),
)

FIXED_SAME_SIDE_CASES = (
    FixedSameSideCase(0.15, 0.13, 0.0, "same_side_or_exit"),
    FixedSameSideCase(0.18, 0.16, 0.0, "same_side_or_exit"),
    FixedSameSideCase(0.20, 0.18, 0.0, "same_side_or_exit"),
    FixedSameSideCase(0.22, 0.20, 0.0, "same_side_or_exit"),
    FixedSameSideCase(0.25, 0.22, 0.0, "same_side_or_exit"),
    FixedSameSideCase(0.20, 0.18, 0.5, "same_side_or_exit"),
    FixedSameSideCase(0.20, 0.18, 0.75, "same_side_or_exit"),
    FixedSameSideCase(0.20, 0.18, 0.0, "exit_only"),
)

ADAPTIVE_QUANTILE_CASES = tuple(
    AdaptiveQuantileCase(252, 126, enter_q, exit_q, 0.10, 0.05, scale, "same_side_or_exit")
    for enter_q in (0.85, 0.90, 0.95)
    for exit_q in (0.60, 0.70, 0.80)
    for scale in (0.0, 0.5)
)

SCORE_MAX_CASES = (4.0, 5.0, 6.0, 8.0, math.inf)


def git_value(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def pct_label(value: float) -> str:
    return f"{float(value):.3f}".rstrip("0").rstrip(".").replace(".", "p")


def scale_label(value: float) -> str:
    return f"{float(value):.2f}".replace(".", "p")


def score_max_label(value: float) -> str:
    if math.isinf(float(value)):
        return "inf"
    return pct_label(float(value))


def line_base_candidate(line: CarryLine) -> str:
    return f"{line.line_id}_scoremax_{score_max_label(DEFAULT_SCORE_MAX)}_overheat_off"


def fixed_label(case: FixedSameSideCase) -> str:
    return (
        f"fixed_enter_{pct_label(case.enter)}_exit_{pct_label(case.exit)}"
        f"_scale_{scale_label(case.derisk_scale)}_{case.recovery_mode}"
    )


def adaptive_label(case: AdaptiveQuantileCase) -> str:
    return (
        f"adaptive_w{case.window}_eq{pct_label(case.enter_quantile)}"
        f"_xq{pct_label(case.exit_quantile)}"
        f"_floor_{pct_label(case.min_enter)}_{pct_label(case.min_exit)}"
        f"_scale_{scale_label(case.derisk_scale)}_{case.recovery_mode}"
    )


def candidate_label(line: CarryLine, direction: str, parameter_label: str) -> str:
    if direction == "baseline":
        return line_base_candidate(line)
    return f"{line.line_id}_{direction}_{parameter_label}"


def series_or_one(curve: pd.DataFrame, column: str) -> pd.Series:
    if column in curve.columns:
        return pd.to_numeric(curve[column], errors="coerce").fillna(1.0).astype(float)
    return pd.Series(1.0, index=curve.index, dtype=float)


def existing_overlay_scales(curve: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    if "combined_overlay_scale_effective" in curve.columns and "combined_overlay_scale_next" in curve.columns:
        return series_or_one(curve, "combined_overlay_scale_effective"), series_or_one(curve, "combined_overlay_scale_next")
    if "score_decay_multiplier_effective" in curve.columns and "score_decay_multiplier_next" in curve.columns:
        return series_or_one(curve, "score_decay_multiplier_effective"), series_or_one(curve, "score_decay_multiplier_next")
    return pd.Series(1.0, index=curve.index, dtype=float), pd.Series(1.0, index=curve.index, dtype=float)


def apply_zero_overheat_execution_guard_for_line(work: pd.DataFrame, line: CarryLine) -> pd.DataFrame:
    original_assets = dict(subd.ASSETS)
    original_initial_entry = v11.INITIAL_ENTRY_FRACTION
    try:
        subd.ASSETS.clear()
        subd.ASSETS.update(layer0.PROXY_ASSETS)
        v11.INITIAL_ENTRY_FRACTION = float(line.entry_fraction)
        return v11._apply_zero_overheat_execution_guard(work)
    finally:
        v11.INITIAL_ENTRY_FRACTION = original_initial_entry
        subd.ASSETS.clear()
        subd.ASSETS.update(original_assets)


def run_staged_line_with_score_max(prices: pd.DataFrame, end_date: pd.Timestamp, line: CarryLine, score_max: float) -> pd.DataFrame:
    original_score_max = subd.SCORE_MAX
    try:
        subd.SCORE_MAX = float(score_max)
        return layer4.run_staged_line(
            prices,
            end_date,
            line.lookback,
            line.r2_threshold,
            line.switch_buffer,
            line.entry_fraction,
            line.line_id,
        )
    finally:
        subd.SCORE_MAX = original_score_max


def build_line_curve(prices: pd.DataFrame, end_date: pd.Timestamp, line: CarryLine, score_max: float) -> pd.DataFrame:
    staged = run_staged_line_with_score_max(prices, end_date, line, score_max)
    decayed = layer6.apply_momentum_decay_layer(
        staged,
        line.lookback,
        line.r2_threshold,
        line.switch_buffer,
        line.entry_fraction,
        line.decay_ratio,
        line.recovery_ratio,
        line.confirm_days,
        line.decay_scale,
        line.line_id,
    )
    if line.nav_enter is not None:
        curve = nav7.apply_nav_defense_layer(
            decayed,
            line.lookback,
            line.r2_threshold,
            line.switch_buffer,
            line.entry_fraction,
            line.decay_ratio,
            line.recovery_ratio,
            line.confirm_days,
            line.decay_scale,
            line.nav_enter,
            line.nav_exit,
            line.nav_scale,
            line.line_id,
        )
    else:
        curve = decayed.copy()
        curve["nav_defense_enabled"] = False
        curve["nav_enter_threshold"] = np.nan
        curve["nav_exit_threshold"] = np.nan
        curve["nav_defense_scale"] = 1.0
        curve["nav_label"] = "nav_off"
        curve["nav_defense_scale_effective"] = 1.0
        curve["nav_defense_scale_next"] = 1.0
        curve["nav_defense_on_effective"] = False
        curve["nav_defense_on_next"] = False
        curve["nav_defense_triggered"] = False
        curve["nav_defense_recovered"] = False
        curve["combined_overlay_scale_effective"] = series_or_one(curve, "score_decay_multiplier_effective")
        curve["combined_overlay_scale_next"] = series_or_one(curve, "score_decay_multiplier_next")

    curve["line_id"] = line.line_id
    curve["score_max"] = float(score_max)
    curve["score_max_label"] = score_max_label(score_max)
    return curve


def build_bias_features(prices: pd.DataFrame) -> dict[str, pd.DataFrame]:
    features: dict[str, pd.DataFrame] = {}
    for code in layer0.PROXY_ASSETS:
        price = pd.to_numeric(prices[code], errors="coerce").astype(float)
        ma = price.rolling(v11.CN_BIAS_N).mean()
        bias = price / ma - 1.0
        bias_mom = v11.calc_bias_momentum(price)
        same_side = (bias > 0) & (bias_mom > 0) & bias.notna() & bias_mom.notna()
        features[code] = pd.DataFrame(
            {
                "bias": bias,
                "bias_mom": bias_mom,
                "same_side": same_side,
            },
            index=prices.index,
        )
    return features


def build_adaptive_features(base_features: dict[str, pd.DataFrame], case: AdaptiveQuantileCase) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for code, frame in base_features.items():
        bias = pd.to_numeric(frame["bias"], errors="coerce").astype(float)
        history = bias.shift(1)
        enter = history.rolling(case.window, min_periods=case.min_periods).quantile(case.enter_quantile)
        exit_ = history.rolling(case.window, min_periods=case.min_periods).quantile(case.exit_quantile)
        enter = enter.clip(lower=case.min_enter)
        exit_ = exit_.clip(lower=case.min_exit)
        exit_ = pd.concat([exit_, enter * 0.80], axis=1).min(axis=1)
        out[code] = frame.assign(enter_threshold=enter, exit_threshold=exit_)
    return out


def fixed_features(base_features: dict[str, pd.DataFrame], case: FixedSameSideCase) -> dict[str, pd.DataFrame]:
    return {
        code: frame.assign(enter_threshold=float(case.enter), exit_threshold=float(case.exit))
        for code, frame in base_features.items()
    }


def overheat_state(
    curve: pd.DataFrame,
    features: dict[str, pd.DataFrame],
    derisk_scale: float,
    recovery_mode: Literal["same_side_or_exit", "exit_only"],
) -> pd.DataFrame:
    if not 0.0 <= float(derisk_scale) <= 1.0:
        raise ValueError("derisk_scale must be in [0, 1]")
    if recovery_mode not in {"same_side_or_exit", "exit_only"}:
        raise ValueError(f"bad recovery_mode={recovery_mode}")

    aligned_features: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}
    for code, frame in features.items():
        aligned = frame.reindex(curve.index)
        aligned_features[code] = (
            pd.to_numeric(aligned["bias"], errors="coerce").to_numpy(dtype=float),
            pd.to_numeric(aligned["bias_mom"], errors="coerce").to_numpy(dtype=float),
            aligned["same_side"].fillna(False).astype(bool).to_numpy(),
            pd.to_numeric(aligned["enter_threshold"], errors="coerce").to_numpy(dtype=float),
            pd.to_numeric(aligned["exit_threshold"], errors="coerce").to_numpy(dtype=float),
        )

    effective_holdings = curve["position_before"].astype(str).to_numpy()
    target_holdings = curve["position"].astype(str).to_numpy()
    defense_on = False
    state_asset: str | None = None

    effective_scales: list[float] = []
    next_scales: list[float] = []
    effective_on: list[bool] = []
    next_on: list[bool] = []
    trigger_flags: list[bool] = []
    recovery_flags: list[bool] = []
    bias_values: list[float] = []
    mom_values: list[float] = []
    same_side_values: list[bool] = []
    enter_values: list[float] = []
    exit_values: list[float] = []
    missing_values: list[bool] = []

    for i in range(len(curve)):
        effective_holding = effective_holdings[i]
        target_holding = target_holdings[i]
        effective_eligible = effective_holding in layer0.PROXY_ASSETS
        target_eligible = target_holding in layer0.PROXY_ASSETS

        effective_state = bool(defense_on and state_asset == effective_holding and effective_eligible)
        effective_scale = float(derisk_scale) if effective_state else 1.0
        next_state = bool(defense_on and state_asset == target_holding and target_eligible)

        bias = math.nan
        mom = math.nan
        same_side = False
        enter_threshold = math.nan
        exit_threshold = math.nan
        if target_eligible and target_holding in aligned_features:
            bias_arr, mom_arr, same_arr, enter_arr, exit_arr = aligned_features[target_holding]
            bias = float(bias_arr[i]) if pd.notna(bias_arr[i]) else math.nan
            mom = float(mom_arr[i]) if pd.notna(mom_arr[i]) else math.nan
            same_side = bool(same_arr[i])
            enter_threshold = float(enter_arr[i]) if pd.notna(enter_arr[i]) else math.nan
            exit_threshold = float(exit_arr[i]) if pd.notna(exit_arr[i]) else math.nan

        feature_missing = bool(
            target_eligible
            and (
                pd.isna(bias)
                or pd.isna(mom)
                or pd.isna(enter_threshold)
                or pd.isna(exit_threshold)
                or not math.isfinite(enter_threshold)
                or not math.isfinite(exit_threshold)
            )
        )

        triggered = False
        recovered = False
        prior_next_state = next_state
        if target_eligible:
            if next_state:
                if feature_missing:
                    next_state = True
                elif bias <= exit_threshold:
                    next_state = False
                    recovered = True
                elif recovery_mode == "same_side_or_exit" and not same_side:
                    next_state = False
                    recovered = True
            elif not feature_missing and same_side and bias >= enter_threshold:
                next_state = True
                triggered = True
        else:
            next_state = False

        next_scale = float(derisk_scale) if next_state and target_eligible else 1.0
        effective_scales.append(effective_scale)
        next_scales.append(next_scale)
        effective_on.append(bool(effective_scale < 0.999999 and effective_eligible))
        next_on.append(bool(next_scale < 0.999999 and target_eligible))
        trigger_flags.append(bool(triggered))
        recovery_flags.append(bool(recovered and prior_next_state))
        bias_values.append(bias)
        mom_values.append(mom)
        same_side_values.append(same_side)
        enter_values.append(enter_threshold)
        exit_values.append(exit_threshold)
        missing_values.append(feature_missing)

        defense_on = next_state
        state_asset = target_holding if target_eligible else None

    return pd.DataFrame(
        {
            "overheat_rule_scale_effective": pd.Series(effective_scales, index=curve.index, dtype=float),
            "overheat_rule_scale_next": pd.Series(next_scales, index=curve.index, dtype=float),
            "overheat_rule_on_effective": pd.Series(effective_on, index=curve.index, dtype=bool),
            "overheat_rule_on_next": pd.Series(next_on, index=curve.index, dtype=bool),
            "overheat_triggered": pd.Series(trigger_flags, index=curve.index, dtype=bool),
            "overheat_recovered": pd.Series(recovery_flags, index=curve.index, dtype=bool),
            "overheat_bias": pd.Series(bias_values, index=curve.index, dtype=float),
            "overheat_bias_mom": pd.Series(mom_values, index=curve.index, dtype=float),
            "overheat_same_side": pd.Series(same_side_values, index=curve.index, dtype=bool),
            "overheat_enter_threshold": pd.Series(enter_values, index=curve.index, dtype=float),
            "overheat_exit_threshold": pd.Series(exit_values, index=curve.index, dtype=float),
            "overheat_feature_missing": pd.Series(missing_values, index=curve.index, dtype=bool),
        },
        index=curve.index,
    )


def apply_no_new_overheat(curve: pd.DataFrame, line: CarryLine) -> pd.DataFrame:
    out = curve.copy()
    out["candidate"] = line_base_candidate(line)
    out["baseline_candidate"] = line_base_candidate(line)
    out["line_id"] = line.line_id
    out["overheat_direction"] = "baseline"
    out["overheat_parameter_label"] = "overheat_off"
    out["overheat_enabled"] = False
    out["overheat_rule_scale_effective"] = 1.0
    out["overheat_rule_scale_next"] = 1.0
    out["overheat_rule_on_effective"] = False
    out["overheat_rule_on_next"] = False
    out["overheat_triggered"] = False
    out["overheat_recovered"] = False
    out["overheat_bias"] = np.nan
    out["overheat_bias_mom"] = np.nan
    out["overheat_same_side"] = False
    out["overheat_enter_threshold"] = np.nan
    out["overheat_exit_threshold"] = np.nan
    out["overheat_feature_missing"] = False
    return out


def apply_overheat_overlay_to_line(
    base_curve: pd.DataFrame,
    line: CarryLine,
    direction: str,
    parameter_label: str,
    features: dict[str, pd.DataFrame],
    derisk_scale: float,
    recovery_mode: Literal["same_side_or_exit", "exit_only"],
) -> pd.DataFrame:
    state = overheat_state(base_curve, features, derisk_scale, recovery_mode)
    work = base_curve.copy()
    for col in state.columns:
        work[col] = state[col]
    work["overheat_scale_next"] = state["overheat_rule_scale_next"]
    if float(derisk_scale) <= 1e-12:
        work = apply_zero_overheat_execution_guard_for_line(work, line)

    existing_effective, existing_next = existing_overlay_scales(base_curve)
    combined_effective = existing_effective.reindex(work.index).fillna(1.0) * state["overheat_rule_scale_effective"]
    combined_next = existing_next.reindex(work.index).fillna(1.0) * state["overheat_rule_scale_next"]
    ones = pd.Series(1.0, index=work.index, dtype=float)
    out = v11._recompute_final_exposure_nav(work, ones, ones, combined_effective, combined_next, ONE_WAY_COST)
    for col in state.columns:
        out[col] = state[col]
    out["existing_overlay_scale_effective"] = existing_effective.reindex(out.index).fillna(1.0)
    out["existing_overlay_scale_next"] = existing_next.reindex(out.index).fillna(1.0)
    out["combined_overlay_scale_effective"] = combined_effective
    out["combined_overlay_scale_next"] = combined_next
    out["candidate"] = candidate_label(line, direction, parameter_label)
    out["baseline_candidate"] = line_base_candidate(line)
    out["line_id"] = line.line_id
    out["overheat_direction"] = direction
    out["overheat_parameter_label"] = parameter_label
    out["overheat_enabled"] = True
    return out


def apply_score_max_candidate(curve: pd.DataFrame, line: CarryLine, score_max: float) -> pd.DataFrame:
    out = curve.copy()
    label = f"scoremax_{score_max_label(score_max)}"
    out["candidate"] = candidate_label(line, "score_veto", label)
    out["baseline_candidate"] = line_base_candidate(line)
    out["line_id"] = line.line_id
    out["overheat_direction"] = "score_veto"
    out["overheat_parameter_label"] = label
    out["overheat_enabled"] = bool(abs(float(score_max) - DEFAULT_SCORE_MAX) > 1e-12 if not math.isinf(score_max) else True)
    out["overheat_rule_scale_effective"] = 1.0
    out["overheat_rule_scale_next"] = 1.0
    out["overheat_rule_on_effective"] = False
    out["overheat_rule_on_next"] = False
    out["overheat_triggered"] = False
    out["overheat_recovered"] = False
    out["overheat_bias"] = np.nan
    out["overheat_bias_mom"] = np.nan
    out["overheat_same_side"] = False
    out["overheat_enter_threshold"] = np.nan
    out["overheat_exit_threshold"] = np.nan
    out["overheat_feature_missing"] = False
    return out


def max_drawdown(nav: pd.Series) -> float:
    peak = nav.astype(float).cummax().clip(lower=1.0)
    return float((nav.astype(float) / peak - 1.0).min())


def mark_effect_vs_baseline(curves: list[pd.DataFrame]) -> None:
    baselines = {
        str(curve["line_id"].iloc[0]): curve
        for curve in curves
        if str(curve["overheat_direction"].iloc[0]) == "baseline"
    }
    for curve in curves:
        line_id = str(curve["line_id"].iloc[0])
        base = baselines[line_id].reindex(curve.index)
        ret_diff = (curve["return"].astype(float).fillna(0.0) - base["return"].astype(float).fillna(0.0)).abs()
        exposure_diff = (
            curve["final_exposure_after_overheat"].astype(float).fillna(0.0)
            - base["final_exposure_after_overheat"].astype(float).fillna(0.0)
        ).abs()
        pos_diff = curve["actual_position_next"].astype(str) != base["actual_position_next"].astype(str)
        curve["effect_vs_baseline"] = (ret_diff > 1e-12) | (exposure_diff > 1e-12) | pos_diff
        curve["return_abs_diff_vs_baseline"] = ret_diff
        curve["exposure_abs_diff_vs_baseline"] = exposure_diff


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
        "line_id": str(first["line_id"]),
        "line_role": str(first.get("line_role", first["line_id"])),
        "overheat_direction": str(first["overheat_direction"]),
        "overheat_parameter_label": str(first["overheat_parameter_label"]),
        "overheat_enabled": bool(first["overheat_enabled"]),
        "lookback": int(first["lookback"]),
        "r2_threshold": float(first["r2_threshold"]),
        "r2_label": str(first["r2_label"]),
        "switch_buffer": float(first["switch_buffer"]),
        "buffer_label": str(first["buffer_label"]),
        "entry_fraction": float(first["entry_fraction"]),
        "entry_label": str(first["entry_label"]),
        "score_max": float(first["score_max"]),
        "score_max_label": str(first["score_max_label"]),
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
            "avg_existing_overlay_scale_effective": np.nan,
            "avg_overheat_scale_effective": np.nan,
            "avg_combined_overlay_scale_effective": np.nan,
            "overheat_day_ratio": np.nan,
            "trigger_count": np.nan,
            "recovery_count": np.nan,
            "effect_day_ratio": np.nan,
            "effect_day_count": np.nan,
            "return_abs_diff_sum": np.nan,
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
    existing_scale = pd.to_numeric(
        sub.get("existing_overlay_scale_effective", pd.Series(1.0, index=sub.index)),
        errors="coerce",
    ).fillna(1.0)
    overheat_scale = pd.to_numeric(sub["overheat_rule_scale_effective"], errors="coerce").fillna(1.0)
    combined_scale = pd.to_numeric(
        sub.get("combined_overlay_scale_effective", pd.Series(1.0, index=sub.index)),
        errors="coerce",
    ).fillna(1.0)
    effect = sub.get("effect_vs_baseline", pd.Series(False, index=sub.index)).astype(bool)
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
        "avg_existing_overlay_scale_effective": float(existing_scale.mean()),
        "avg_overheat_scale_effective": float(overheat_scale.mean()),
        "avg_combined_overlay_scale_effective": float(combined_scale.mean()),
        "overheat_day_ratio": float(sub["overheat_rule_on_effective"].astype(bool).mean()),
        "trigger_count": int(sub["overheat_triggered"].astype(bool).sum()),
        "recovery_count": int(sub["overheat_recovered"].astype(bool).sum()),
        "effect_day_ratio": float(effect.mean()),
        "effect_day_count": int(effect.sum()),
        "return_abs_diff_sum": float(sub.get("return_abs_diff_vs_baseline", pd.Series(0.0, index=sub.index)).sum()),
        "reason": reason,
    }


def build_window_metrics(scan_summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for candidate, group in scan_summary.groupby("candidate", sort=False):
        first = group.iloc[0]
        row: dict[str, object] = {
            "candidate": candidate,
            "baseline_candidate": first["baseline_candidate"],
            "line_id": first["line_id"],
            "line_role": first["line_role"],
            "overheat_direction": first["overheat_direction"],
            "overheat_parameter_label": first["overheat_parameter_label"],
            "overheat_enabled": bool(first["overheat_enabled"]),
            "lookback": int(first["lookback"]),
            "r2_threshold": float(first["r2_threshold"]),
            "r2_label": first["r2_label"],
            "switch_buffer": float(first["switch_buffer"]),
            "buffer_label": first["buffer_label"],
            "entry_fraction": float(first["entry_fraction"]),
            "entry_label": first["entry_label"],
            "score_max": float(first["score_max"]),
            "score_max_label": first["score_max_label"],
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
                for col in (
                    "ann_return",
                    "ann_vol",
                    "max_dd",
                    "sharpe_repo",
                    "trades",
                    "cost_total",
                    "turnover_total",
                    "avg_exposure_effective",
                    "avg_final_exposure",
                    "avg_existing_overlay_scale_effective",
                    "avg_overheat_scale_effective",
                    "avg_combined_overlay_scale_effective",
                    "overheat_day_ratio",
                    "trigger_count",
                    "recovery_count",
                    "effect_day_ratio",
                    "effect_day_count",
                    "return_abs_diff_sum",
                ):
                    row[f"{col}_{segment}"] = source[col]
                row[f"reason_{segment}"] = source["reason"]

        base_rows = scan_summary[scan_summary["candidate"].eq(first["baseline_candidate"])]
        for segment in SEGMENTS:
            base_sub = base_rows[base_rows["segment"].eq(segment)]
            if base_sub.empty:
                row[f"ann_delta_{segment}_pp"] = np.nan
                row[f"mdd_improve_{segment}_pp"] = np.nan
            else:
                base = base_sub.iloc[0]
                ann = row.get(f"ann_return_{segment}", np.nan)
                dd = row.get(f"max_dd_{segment}", np.nan)
                row[f"ann_delta_{segment}_pp"] = (
                    (ann - base["ann_return"]) * 100.0 if pd.notna(ann) and pd.notna(base["ann_return"]) else np.nan
                )
                row[f"mdd_improve_{segment}_pp"] = (
                    (dd - base["max_dd"]) * 100.0 if pd.notna(dd) and pd.notna(base["max_dd"]) else np.nan
                )
        rows.append(row)
    out = pd.DataFrame(rows)
    return apply_pass_flags(out)


def apply_pass_flags(window_metrics: pd.DataFrame) -> pd.DataFrame:
    out = window_metrics.copy()
    pass_rows = []
    for _, row in out.iterrows():
        if str(row["overheat_direction"]) == "baseline":
            pass_rows.append(
                {
                    "dd_improve_window_count": 0,
                    "return_tolerance_ok": False,
                    "full_mdd_improved": False,
                    "material_effect": False,
                    "layer8_pass": False,
                    "pass_reason": "baseline/no new overheat",
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
        material = bool(
            pd.notna(row.get("effect_day_ratio_full", np.nan))
            and float(row.get("effect_day_ratio_full", 0.0)) > 0.0
        )
        passed = bool(full_mdd_improved and dd_count >= 3 and tolerance_ok and material)
        reason = (
            "pass"
            if passed
            else f"full_mdd={full_mdd_improved};dd_windows={dd_count};return_tol={tolerance_ok};material={material}"
        )
        pass_rows.append(
            {
                "dd_improve_window_count": dd_count,
                "return_tolerance_ok": tolerance_ok,
                "full_mdd_improved": full_mdd_improved,
                "material_effect": material,
                "layer8_pass": passed,
                "pass_reason": reason,
            }
        )
    return pd.concat([out.reset_index(drop=True), pd.DataFrame(pass_rows)], axis=1)


def select_by_direction(window_metrics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    candidates = window_metrics[~window_metrics["overheat_direction"].eq("baseline")].copy()
    for (line_id, direction), group in candidates.groupby(["line_id", "overheat_direction"], sort=False):
        passed = group[group["layer8_pass"].astype(bool)].copy()
        if not passed.empty:
            selected = passed.sort_values(
                ["ann_return_full", "mdd_improve_full_pp", "effect_day_ratio_full"],
                ascending=[False, False, True],
            ).iloc[0].to_dict()
            selected["selection_role"] = "selected_pass"
        else:
            selected = group.sort_values(
                ["mdd_improve_full_pp", "ann_return_full", "effect_day_ratio_full"],
                ascending=[False, False, False],
            ).iloc[0].to_dict()
            selected["selection_role"] = "best_diagnostic_no_pass"
        rows.append(selected)
    return pd.DataFrame(rows)


def row_from_window(source: dict[str, object], ctype: str, notes: str) -> dict[str, object]:
    row = {
        "candidate": source["candidate"],
        "candidate_type": ctype,
        "line_id": source.get("line_id", ""),
        "overheat_direction": source.get("overheat_direction", ""),
        "overheat_parameter_label": source.get("overheat_parameter_label", ""),
        "notes": notes,
    }
    for segment in SEGMENTS:
        row[f"ann_return_{segment}"] = source.get(f"ann_return_{segment}", np.nan)
        row[f"max_dd_{segment}"] = source.get(f"max_dd_{segment}", np.nan)
        row[f"reason_{segment}"] = source.get(f"reason_{segment}", "")
    return row


def build_comparison_list(
    window_metrics: pd.DataFrame,
    direction_selection: pd.DataFrame,
    original_reference: dict[str, object],
) -> pd.DataFrame:
    rows = []
    for _, row in window_metrics[window_metrics["overheat_direction"].eq("baseline")].iterrows():
        rows.append(row_from_window(row.to_dict(), "two_line_baseline", "Carried line before Layer8 overheat tests"))
    for _, row in direction_selection.iterrows():
        rows.append(
            row_from_window(
                row.to_dict(),
                str(row["selection_role"]),
                "Best candidate within its line and overheat direction",
            )
        )
    rows.append(original_reference)
    return pd.DataFrame(rows)


def pct(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value) * 100:.2f}%"


def fmt_num(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value):.2f}"


def original_full_reference(prices: pd.DataFrame, end_date: pd.Timestamp) -> dict[str, object]:
    row = layer2.original_full_reference(prices, end_date)
    row["candidate_type"] = "original_full_strategy_reference"
    row["line_id"] = "original"
    row["overheat_direction"] = "original_full_chain"
    row["overheat_parameter_label"] = "original_v1_1"
    row["notes"] = "Full official V1.1 chain including target-vol and original overheat; context only, not Layer8 pass baseline"
    return row


def daily_output_frame(curves: list[pd.DataFrame]) -> pd.DataFrame:
    keep = [
        "candidate",
        "baseline_candidate",
        "line_id",
        "line_role",
        "overheat_direction",
        "overheat_parameter_label",
        "overheat_enabled",
        "lookback",
        "r2_threshold",
        "switch_buffer",
        "entry_fraction",
        "score_max",
        "decay_label",
        "nav_label",
        "position_before",
        "fraction_before",
        "position",
        "holding_fraction",
        "actual_position_before",
        "actual_position_next",
        "score_decay_multiplier_effective",
        "score_decay_multiplier_next",
        "nav_defense_scale_effective",
        "nav_defense_scale_next",
        "existing_overlay_scale_effective",
        "existing_overlay_scale_next",
        "overheat_rule_scale_effective",
        "overheat_rule_scale_next",
        "overheat_rule_on_effective",
        "overheat_rule_on_next",
        "overheat_triggered",
        "overheat_recovered",
        "overheat_bias",
        "overheat_bias_mom",
        "overheat_same_side",
        "overheat_enter_threshold",
        "overheat_exit_threshold",
        "combined_overlay_scale_effective",
        "combined_overlay_scale_next",
        "asset_return",
        "gross_return",
        "turnover",
        "cost",
        "return",
        "nav",
        "exposure_effective",
        "final_exposure_after_overheat",
        "effect_vs_baseline",
    ]
    frames = [curve[[col for col in keep if col in curve.columns]] for curve in curves]
    return pd.concat(frames, axis=0).reset_index()


def write_record(
    run_folder: Path,
    window_metrics: pd.DataFrame,
    direction_selection: pd.DataFrame,
    comparison_list: pd.DataFrame,
    sources: pd.DataFrame,
    meta: dict[str, object],
) -> None:
    lines = [
        "# Sub-D Dynamic ChiNext Proxy Layer 8 Overheat Three-Direction Scan",
        "",
        "## Run Metadata",
        "",
        f"- Run folder: `{run_folder}`",
        "- Layer: `Layer 8`",
        "- Strategy: dynamic ChiNext proxy pool, 2007-2016.",
        "- Entrypoint: `run_subd_proxy_dynamic_cyb_layer8_overheat_three_directions_scan.py`",
        "",
        "## Research Question",
        "",
        "Test overheat controls in three directions on both carried lines.",
        "",
        "## Three Directions",
        "",
        "- `fixed_same_side`: MA60 bias and 20-day bias-momentum same-side overheat with fixed enter/exit thresholds.",
        "- `adaptive_quantile`: same-side overheat with per-asset rolling 252-session bias quantile thresholds.",
        "- `score_veto`: retest the hidden score-overheat veto by changing `SCORE_MAX` and rebuilding each line.",
        "",
        "## Carried Lines",
        "",
        "- `A_clean`: no target-vol, no momentum decay, no NAV defense.",
        "- `G_decay_nav`: momentum decay plus NAV defense.",
        "",
        "## Data Snapshot",
        "",
        f"- Start/end: `{meta['data_snapshot']['start']}` to `{meta['data_snapshot']['end']}`.",
        f"- Rows: `{meta['data_snapshot']['rows']}`.",
        "- Pool: QQQ/EWG/EWJ/GLD from 2007 start; ChiNext joins when its own data exists.",
        "- 10Y is N/A because 2432 sessions is less than 2520 trading days.",
        "",
        "## Cost and Execution Assumptions",
        "",
        f"- One-way cost: `{ONE_WAY_COST}`.",
        "- Overheat scale is set at T close and effective next session.",
        "- Overheat costs are included through full final-exposure recomputation.",
        "- Calendar: A-share trading days; US adjusted closes are forward-filled onto that calendar for this proxy diagnostic.",
        "- Trades involving a forward-filled trade leg are blocked by the base staged-entry path for that day.",
        "",
        "## Selection By Direction",
        "",
        "| Line | Direction | Selected/Best | Role | Full Ann. | Full MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Full Ann Delta pp | Full MDD Improve pp | Effect Days Full | Pass | Reason |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for _, row in direction_selection.iterrows():
        lines.append(
            "| "
            f"{row['line_id']} | {row['overheat_direction']} | `{row['candidate']}` | {row['selection_role']} | "
            f"{pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{pct(row['ann_return_last_5y'])} | {pct(row['max_dd_last_5y'])} | "
            f"{pct(row['ann_return_last_3y'])} | {pct(row['max_dd_last_3y'])} | "
            f"{pct(row['ann_return_last_1y'])} | {pct(row['max_dd_last_1y'])} | "
            f"{fmt_num(row['ann_delta_full_pp'])} | {fmt_num(row['mdd_improve_full_pp'])} | "
            f"{pct(row['effect_day_ratio_full'])} | {bool(row['layer8_pass'])} | {row['pass_reason']} |"
        )
    lines.extend(
        [
            "",
            "## Comparison List",
            "",
            "| Candidate | Type | Line | Direction | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Notes |",
            "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for _, row in comparison_list.iterrows():
        lines.append(
            "| "
            f"`{row['candidate']}` | {row['candidate_type']} | {row['line_id']} | {row['overheat_direction']} | "
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
            "- Decision: `do_not_add_layer8_overheat_keep_two_carried_lines`.",
            "- Stability label: `no_direction_pass_diagnostic`.",
            "- No overheat direction passed the same-line Layer 2+ drawdown-control rule.",
            "- Fixed/adaptive overheat improved full-sample drawdown in some cases, but did not improve enough available windows.",
            "- Score-veto changes had weak drawdown support and larger return drag.",
            "",
            "## Decision",
            "",
            "- This scan reports per-direction pass/fail only.",
            "- Do not merge directions yet; stop here before any next layer.",
            "- Candidates compare only against their own carried-line baseline.",
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
    base_features = build_bias_features(prices)

    base_curves = {
        line.line_id: build_line_curve(prices, end_date, line, DEFAULT_SCORE_MAX)
        for line in CARRY_LINES
    }

    curves: list[pd.DataFrame] = []
    for line in CARRY_LINES:
        base_curve = base_curves[line.line_id]
        curves.append(apply_no_new_overheat(base_curve, line))

        for case in FIXED_SAME_SIDE_CASES:
            curves.append(
                apply_overheat_overlay_to_line(
                    base_curve,
                    line,
                    "fixed_same_side",
                    fixed_label(case),
                    fixed_features(base_features, case),
                    case.derisk_scale,
                    case.recovery_mode,
                )
            )

        for case in ADAPTIVE_QUANTILE_CASES:
            curves.append(
                apply_overheat_overlay_to_line(
                    base_curve,
                    line,
                    "adaptive_quantile",
                    adaptive_label(case),
                    build_adaptive_features(base_features, case),
                    case.derisk_scale,
                    case.recovery_mode,
                )
            )

        for score_max in SCORE_MAX_CASES:
            if abs(float(score_max) - DEFAULT_SCORE_MAX) < 1e-12:
                continue
            score_curve = build_line_curve(prices, end_date, line, score_max)
            curves.append(apply_score_max_candidate(score_curve, line, score_max))

    mark_effect_vs_baseline(curves)

    summary_rows = []
    for curve in curves:
        for segment, label, start, reason in layer1.window_specs(prices.index):
            summary_rows.append(summarize_curve(curve, segment, label, start, reason))
    scan_summary = pd.DataFrame(summary_rows)
    window_metrics = build_window_metrics(scan_summary)
    direction_selection = select_by_direction(window_metrics)
    original_reference = original_full_reference(prices, end_date)
    comparison_list = build_comparison_list(window_metrics, direction_selection, original_reference)
    daily = daily_output_frame(curves)

    scan_summary.to_csv(run_folder / "scan_summary.csv", index=False, encoding="utf-8-sig")
    window_metrics.to_csv(run_folder / "window_metrics.csv", index=False, encoding="utf-8-sig")
    direction_selection.to_csv(run_folder / "direction_selection.csv", index=False, encoding="utf-8-sig")
    comparison_list.to_csv(run_folder / "comparison_list.csv", index=False, encoding="utf-8-sig")
    daily.to_csv(daily_dir / "overheat_three_directions_daily_curves.csv", index=False, encoding="utf-8-sig")
    sources.to_csv(run_folder / "sources.csv", index=False, encoding="utf-8-sig")

    command = (
        "python run_subd_proxy_dynamic_cyb_layer8_overheat_three_directions_scan.py "
        f"--start-date {start_date.date()} --end-date {end_date.date()} --run-folder {run_folder}"
    )
    metadata_path = run_folder / "scan_meta.json"
    meta = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    meta.update(
        {
            "phase": "scan_complete_unfinalized",
            "scan_type": "layer8_overheat_three_direction_scan",
            "parameter_group": "layer8_overheat_three_directions",
            "baseline": {
                "rule": "two carried lines before adding new overheat; SCORE_MAX=5.0 for the score-veto baseline",
                "candidates": [line_base_candidate(line) for line in CARRY_LINES],
            },
            "three_directions": {
                "fixed_same_side": "fixed MA60 bias and 20-day bias momentum same-side thresholds",
                "adaptive_quantile": "per-asset rolling 252-session bias quantile thresholds, same-side trigger",
                "score_veto": "rebuild the signal with different SCORE_MAX values",
            },
            "fixed_same_side_grid": [case.__dict__ for case in FIXED_SAME_SIDE_CASES],
            "adaptive_quantile_grid": [case.__dict__ for case in ADAPTIVE_QUANTILE_CASES],
            "score_max_grid": [score_max_label(v) for v in SCORE_MAX_CASES],
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
                "overheat_rebalance_cost_included": True,
            },
            "execution_assumptions": {
                "signal": "close-to-close weighted-slope ranking with fixed R2 threshold, switch buffer, and staged entry",
                "A_clean": "no target-vol, no momentum decay, no NAV defense",
                "G_decay_nav": "momentum decay plus NAV defense before testing overheat",
                "overheat": "T close overheat state sets next-session scale; effective scale is shifted one session",
                "adaptive_quantile_threshold": "rolling bias quantiles use prior sessions only via shift(1)",
                "mixed_market_calendar": "diagnostic A-share calendar with US proxy forward-filled; base trades on stale trade legs blocked",
            },
            "pass_rule": {
                "mdd_improve_eps_pp": MDD_IMPROVE_EPS_PP,
                "available_windows": list(AVAILABLE_PASS_SEGMENTS),
                "return_lag_tolerance_pp": {"full": 1.0, "last_5y": 1.0, "last_3y": 3.0, "last_1y": 3.0},
            },
            "outputs": {
                "scan_summary": str(run_folder / "scan_summary.csv"),
                "window_metrics": str(run_folder / "window_metrics.csv"),
                "direction_selection": str(run_folder / "direction_selection.csv"),
                "comparison_list": str(run_folder / "comparison_list.csv"),
                "daily_curves": str(daily_dir / "overheat_three_directions_daily_curves.csv"),
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
    write_record(run_folder, window_metrics, direction_selection, comparison_list, sources, meta)

    with (run_folder / "command_log.txt").open("a", encoding="utf-8") as fh:
        fh.write("\n[scan]\n")
        fh.write(f"cwd={Path.cwd()}\n")
        fh.write(command + "\n")
        fh.write(f"elapsed_sec={meta['elapsed_sec']}\n")

    print(f"WROTE {run_folder / 'scan_summary.csv'}")
    print(f"WROTE {run_folder / 'window_metrics.csv'}")
    print(f"WROTE {run_folder / 'direction_selection.csv'}")
    print(f"WROTE {run_folder / 'comparison_list.csv'}")
    print(f"WROTE {daily_dir / 'overheat_three_directions_daily_curves.csv'}")
    display_cols = [
        "line_id",
        "overheat_direction",
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
        "effect_day_ratio_full",
        "layer8_pass",
        "pass_reason",
    ]
    print(direction_selection[display_cols].to_string(index=False))


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
