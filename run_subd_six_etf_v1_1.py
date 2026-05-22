import argparse
import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

import research_subd_six_etf_weighted_slope as subd


VERSION = "1.1"
START_DATE = pd.Timestamp("2010-01-01")
EVAL_START = pd.Timestamp("2020-01-02")
END_DATE = pd.Timestamp.today().normalize()
R2_THRESHOLD = 0.20
TARGET_VOL = 0.25
TARGET_VOL_SCALE_REBALANCE_THRESHOLD = 0.075
V10_BASELINE_SWITCH_BUFFER = 1.00
SWITCH_BUFFER = 1.05
INITIAL_ENTRY_FRACTION = 0.50
OVERHEAT_ENTER = 0.20
OVERHEAT_EXIT = 0.18
OVERHEAT_DERISK_SCALE = 0.0
ONE_WAY_COST = 0.001
CN_BIAS_N = 60
CN_MOM_DAY = 20


def _sanity_check_subd_contract() -> None:
    required = {
        "ASSETS": dict,
        "LOOKBACK": int,
        "TRADING_DAYS": int,
        "DEFAULT_VOL_WINDOW": int,
        "DEFAULT_MAX_LEV": (int, float),
        "OUTPUT_DIR": object,
        "RunConfig": type,
        "calc_scores": object,
        "max_drawdown": object,
        "load_close": object,
        "data_quality": object,
    }
    for name, expected_type in required.items():
        if not hasattr(subd, name):
            raise RuntimeError(f"research_subd_six_etf_weighted_slope missing {name}")
        value = getattr(subd, name)
        if expected_type is not object and not isinstance(value, expected_type):
            raise RuntimeError(f"Unexpected type for subd.{name}: {type(value)!r}")
    if not subd.ASSETS:
        raise RuntimeError("subd.ASSETS is empty")
    if subd.LOOKBACK <= 0 or subd.TRADING_DAYS <= 0:
        raise RuntimeError("subd.LOOKBACK and subd.TRADING_DAYS must be positive")


_sanity_check_subd_contract()


@dataclass(frozen=True)
class EntryCase:
    label: str
    mode: Literal["full_entry", "all_new_asset_50_wait_down"]
    initial_fraction: float = 1.0


@dataclass(frozen=True)
class OverheatCase:
    label: str
    enter: float
    exit: float
    derisk_scale: float


def _target_from_scores(
    scores: dict[str, float],
    prev_holding: str,
    switch_buffer: float,
) -> tuple[str, str, float, float, bool]:
    if not scores:
        return "CASH", "CASH", math.nan, math.nan, False
    best = max(scores, key=scores.get)
    best_score = float(scores[best])
    current_score = float(scores[prev_holding]) if prev_holding in scores else math.nan
    blocked = False
    target = best
    if (
        prev_holding in scores
        and prev_holding != best
        and switch_buffer > 1.0
        and best_score <= current_score * switch_buffer
    ):
        target = prev_holding
        blocked = True
    return target, best, best_score, current_score, blocked


def run_staged_entry(
    prices: pd.DataFrame,
    config: subd.RunConfig,
    case: EntryCase,
    r2_threshold: float,
    switch_buffer: float,
) -> pd.DataFrame:
    prices = prices.loc[: config.end_date].copy()
    holding = "CASH"
    holding_fraction = 0.0
    pending_entry_target: str | None = None
    pending_entry_since: pd.Timestamp | None = None
    pending_entry_days = 0
    nav = 1.0
    trade_count = 0
    staged_initial_count = 0
    staged_fill_count = 0
    buffer_blocked_count = 0
    rows = []

    for idx, date in enumerate(prices.index):
        old_holding = holding
        old_fraction = holding_fraction

        scores: dict[str, float] = {}
        r2_values: dict[str, float] = {}
        if idx >= subd.LOOKBACK - 1:
            scores, r2_values = subd.calc_scores(prices, idx, r2_threshold=r2_threshold)
        ideal, best_candidate, best_score, current_score, buffer_blocked = _target_from_scores(
            scores, old_holding, switch_buffer
        )
        if buffer_blocked:
            buffer_blocked_count += 1

        signal_target = ideal if ideal != old_holding else None
        trade_target: str | None = None
        trade_fraction = old_fraction
        fill_on_down_day = False
        staged_initial = False

        if case.mode == "full_entry":
            if signal_target is not None:
                trade_target = signal_target
                trade_fraction = 0.0 if signal_target == "CASH" else 1.0
                pending_entry_target = None
                pending_entry_since = None
                pending_entry_days = 0
        elif old_holding == "CASH":
            if ideal != "CASH":
                initial = float(np.clip(case.initial_fraction, 0.0, 1.0))
                trade_target = ideal
                trade_fraction = initial
                staged_initial = initial < 1.0 - 1e-12
                if staged_initial:
                    pending_entry_target = ideal
                    pending_entry_since = date
                    pending_entry_days = 0
                    staged_initial_count += 1
                else:
                    pending_entry_target = None
                    pending_entry_since = None
                    pending_entry_days = 0
        else:
            is_partial_pending = (
                pending_entry_target is not None
                and old_holding == pending_entry_target
                and old_fraction < 1.0 - 1e-12
            )
            if is_partial_pending:
                if signal_target is not None:
                    if signal_target != "CASH":
                        initial = float(np.clip(case.initial_fraction, 0.0, 1.0))
                        trade_target = signal_target
                        trade_fraction = initial
                        pending_entry_target = signal_target if initial < 1.0 - 1e-12 else None
                        pending_entry_since = date if pending_entry_target is not None else None
                        pending_entry_days = 0
                        staged_initial = pending_entry_target is not None
                        if staged_initial:
                            staged_initial_count += 1
                    else:
                        trade_target = signal_target
                        trade_fraction = 0.0
                        pending_entry_target = None
                        pending_entry_since = None
                        pending_entry_days = 0
                else:
                    prev_close = prices.iloc[idx - 1][pending_entry_target] if idx > 0 else np.nan
                    curr_close = prices.iloc[idx][pending_entry_target]
                    is_down_day = (
                        pd.notna(prev_close)
                        and pd.notna(curr_close)
                        and float(curr_close) < float(prev_close)
                    )
                    if is_down_day:
                        trade_target = pending_entry_target
                        trade_fraction = 1.0
                        pending_entry_target = None
                        pending_entry_since = None
                        pending_entry_days = 0
                        fill_on_down_day = True
                        staged_fill_count += 1
                    else:
                        pending_entry_days += 1
            elif signal_target is not None:
                if signal_target != "CASH":
                    initial = float(np.clip(case.initial_fraction, 0.0, 1.0))
                    trade_target = signal_target
                    trade_fraction = initial
                    staged_initial = initial < 1.0 - 1e-12
                    if staged_initial:
                        pending_entry_target = signal_target
                        pending_entry_since = date
                        pending_entry_days = 0
                        staged_initial_count += 1
                    else:
                        pending_entry_target = None
                        pending_entry_since = None
                        pending_entry_days = 0
                else:
                    trade_target = signal_target
                    trade_fraction = 0.0
                    pending_entry_target = None
                    pending_entry_since = None
                    pending_entry_days = 0

        if old_holding == "CASH" or old_fraction <= 1e-12 or idx == 0:
            gross_return = 0.0
            asset_component = 0.0
        else:
            prev_px = prices.iloc[idx - 1].get(old_holding, np.nan)
            cur_px = prices.iloc[idx].get(old_holding, np.nan)
            asset_ret = float(cur_px / prev_px - 1.0) if pd.notna(prev_px) and pd.notna(cur_px) and prev_px > 0 else 0.0
            asset_component = old_fraction * asset_ret
            gross_return = asset_component

        turnover = 0.0
        cost = 0.0
        if trade_target is not None:
            if old_holding == trade_target:
                turnover = abs(float(trade_fraction) - old_fraction)
            else:
                turnover = (old_fraction if old_holding != "CASH" else 0.0) + (
                    float(trade_fraction) if trade_target != "CASH" else 0.0
                )
            cost = turnover * config.one_way_cost
            holding = trade_target if float(trade_fraction) > 1e-12 else "CASH"
            holding_fraction = float(trade_fraction) if holding != "CASH" else 0.0
            if turnover > 1e-12:
                trade_count += 1
        else:
            holding_fraction = old_fraction

        nav *= (1.0 + gross_return) * (1.0 - cost)
        net_return = nav / rows[-1]["nav"] - 1.0 if rows else nav - 1.0
        score_row = {f"score_{code}": scores.get(code, math.nan) for code in subd.ASSETS}
        r2_row = {f"r2_{code}": r2_values.get(code, math.nan) for code in subd.ASSETS}
        rows.append(
            {
                "date": date,
                "entry_case": case.label,
                "position_before": old_holding,
                "fraction_before": old_fraction,
                "position": holding,
                "holding_fraction": holding_fraction,
                "pending_entry_target": pending_entry_target,
                "pending_entry_since": pending_entry_since,
                "pending_entry_days": pending_entry_days,
                "trade_target": trade_target,
                "trade_fraction": trade_fraction if trade_target is not None else math.nan,
                "staged_initial": staged_initial,
                "fill_on_down_day": fill_on_down_day,
                "best_candidate": best_candidate,
                "best_candidate_score": best_score,
                "current_score": current_score,
                "buffer_blocked": buffer_blocked,
                "gross_return": gross_return,
                "asset_component": asset_component,
                "turnover": turnover,
                "cost": cost,
                "return": net_return,
                "nav": nav,
                "trade_count": trade_count,
                "stop_count": 0,
                "stop_triggered": False,
                "staged_initial_count": staged_initial_count,
                "staged_fill_count": staged_fill_count,
                **score_row,
                **r2_row,
                "buffer_blocked_count": buffer_blocked_count,
            }
        )

    return pd.DataFrame(rows).set_index("date")


def align_prices_to_common_valid_date(
    prices: pd.DataFrame,
    asset_cols: list[str] | tuple[str, ...],
) -> tuple[pd.DataFrame, pd.Timestamp, dict[str, pd.Timestamp]]:
    asset_cols = list(asset_cols)
    missing = [col for col in asset_cols if col not in prices.columns]
    if missing:
        raise ValueError(f"Missing asset columns: {missing}")
    last_by_asset: dict[str, pd.Timestamp] = {}
    for col in asset_cols:
        valid_dates = prices.index[prices[col].notna()]
        last_by_asset[col] = pd.Timestamp(valid_dates.max()) if len(valid_dates) else pd.NaT
    valid_all = prices[asset_cols].notna().all(axis=1)
    if not valid_all.any():
        raise ValueError("No date has valid close prices for all assets")
    common_last = pd.Timestamp(prices.index[valid_all].max())
    return prices.loc[:common_last].copy(), common_last, last_by_asset


def _float_series(curve: pd.DataFrame, column: str, default: float) -> pd.Series:
    if column in curve.columns:
        return curve[column].astype(float).fillna(default)
    return pd.Series(default, index=curve.index, dtype=float)


def apply_target_vol_scale_rebalance_threshold(
    raw_next_scale: pd.Series,
    threshold: float = TARGET_VOL_SCALE_REBALANCE_THRESHOLD,
) -> pd.Series:
    raw = raw_next_scale.astype(float).replace([np.inf, -np.inf], np.nan).fillna(1.0)
    confirmed = []
    last_confirmed = 1.0
    for value in raw:
        value = float(value)
        if threshold <= 0 or abs(value - last_confirmed) >= threshold:
            last_confirmed = value
        confirmed.append(last_confirmed)
    return pd.Series(confirmed, index=raw.index, dtype=float)


def _compute_target_vol_scales(
    curve: pd.DataFrame,
    target_vol: float,
    vol_window: int,
    max_lev: float,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    base_ret = curve["return"].astype(float).fillna(0.0)
    realized_vol = base_ret.rolling(vol_window, min_periods=vol_window).std(ddof=0) * math.sqrt(subd.TRADING_DAYS)
    next_scale = (target_vol / realized_vol).replace([np.inf, -np.inf], max_lev)
    next_scale = next_scale.clip(lower=0.0, upper=max_lev).fillna(1.0)
    next_scale = apply_target_vol_scale_rebalance_threshold(next_scale)
    effective_scale = next_scale.shift(1).fillna(1.0)
    return realized_vol, effective_scale.astype(float), next_scale.astype(float)


def _recompute_final_exposure_nav(
    curve: pd.DataFrame,
    target_vol_effective: pd.Series,
    target_vol_next: pd.Series,
    overheat_effective: pd.Series,
    overheat_next: pd.Series,
    one_way_cost: float,
) -> pd.DataFrame:
    out = curve.copy()
    if "base_gross_return" not in out.columns:
        out["base_gross_return"] = out["gross_return"].astype(float).fillna(0.0)
    if "base_return" not in out.columns:
        out["base_return"] = out["return"].astype(float).fillna(0.0)
    if "base_nav" not in out.columns:
        out["base_nav"] = out["nav"].astype(float)
    if "base_turnover" not in out.columns:
        out["base_turnover"] = _float_series(out, "turnover", 0.0)
    if "base_cost" not in out.columns:
        out["base_cost"] = _float_series(out, "cost", 0.0)

    position_before = out["position_before"].astype(str)
    position_next = out["position"].astype(str)
    fraction_before = _float_series(out, "fraction_before", 0.0)
    holding_fraction = _float_series(out, "holding_fraction", 0.0)

    target_vol_effective = target_vol_effective.reindex(out.index).astype(float).fillna(1.0)
    target_vol_next = target_vol_next.reindex(out.index).astype(float).fillna(1.0)
    overheat_effective = overheat_effective.reindex(out.index).astype(float).fillna(1.0)
    overheat_next = overheat_next.reindex(out.index).astype(float).fillna(1.0)

    exposure_effective = fraction_before * target_vol_effective * overheat_effective
    exposure_effective = exposure_effective.where(position_before != "CASH", 0.0)
    final_exposure = holding_fraction * target_vol_next
    final_exposure = final_exposure.where(position_next != "CASH", 0.0)
    final_exposure_after_overheat = final_exposure * overheat_next

    same_asset = (position_before == position_next) & (position_before != "CASH")
    turnover = pd.Series(
        np.where(
            same_asset,
            (final_exposure_after_overheat - exposure_effective).abs(),
            exposure_effective + final_exposure_after_overheat,
        ),
        index=out.index,
        dtype=float,
    )
    cost = turnover * float(one_way_cost)
    gross_return = out["base_gross_return"].astype(float).fillna(0.0) * target_vol_effective * overheat_effective
    net_return = (1.0 + gross_return) * (1.0 - cost) - 1.0

    out["target_vol_scale_effective"] = target_vol_effective
    out["target_vol_scale_next"] = target_vol_next
    out["weight"] = target_vol_next
    out["overheat_scale_effective"] = overheat_effective
    out["overheat_scale_next"] = overheat_next
    out["overheat_scale"] = overheat_next
    out["exposure_effective"] = exposure_effective
    out["final_exposure"] = final_exposure
    out["final_exposure_after_overheat"] = final_exposure_after_overheat
    out["turnover"] = turnover
    out["cost"] = cost
    out["gross_return"] = gross_return
    out["return"] = net_return
    out["nav"] = (1.0 + net_return).cumprod()
    out["effective_trade_count"] = (turnover > 1e-12).cumsum()
    return out


def apply_target_vol_overlay(
    curve: pd.DataFrame,
    target_vol: float,
    vol_window: int,
    max_lev: float,
    one_way_cost: float = ONE_WAY_COST,
) -> pd.DataFrame:
    result = curve.copy()
    realized_vol, effective_scale, next_scale = _compute_target_vol_scales(
        result, target_vol, vol_window, max_lev
    )
    result["target_vol_input_return"] = result["return"].astype(float).fillna(0.0)
    result["target_vol_input_nav"] = result["nav"].astype(float)
    result["base_gross_return"] = result["gross_return"].astype(float).fillna(0.0)
    result["base_return"] = result["return"].astype(float).fillna(0.0)
    result["base_nav"] = result["nav"].astype(float)
    result["base_turnover"] = _float_series(result, "turnover", 0.0)
    result["base_cost"] = _float_series(result, "cost", 0.0)
    result["realized_vol"] = realized_vol
    ones = pd.Series(1.0, index=result.index, dtype=float)
    result = _recompute_final_exposure_nav(
        result, effective_scale, next_scale, ones, ones, one_way_cost
    )
    result["target_vol"] = target_vol
    result["vol_window"] = vol_window
    result["max_lev"] = max_lev
    return result


def calc_bias_momentum(close_series: pd.Series) -> pd.Series:
    prices = close_series.values.astype(float)
    n = len(prices)
    result = np.full(n, np.nan)
    ma = close_series.rolling(CN_BIAS_N).mean().values
    total_lookback = CN_BIAS_N + CN_MOM_DAY - 1
    if n <= total_lookback:
        return pd.Series(result, index=close_series.index)

    with np.errstate(divide="ignore", invalid="ignore"):
        bias_ratio = np.where((ma >= 1e-10) & np.isfinite(prices), prices / ma, np.nan)

    windows = np.lib.stride_tricks.sliding_window_view(bias_ratio, CN_MOM_DAY)
    starts = windows[:, 0]
    valid = np.isfinite(windows).all(axis=1) & (starts >= 1e-10)
    end_indices = np.arange(CN_MOM_DAY - 1, n)
    valid &= end_indices >= total_lookback
    if valid.any():
        x = np.arange(CN_MOM_DAY, dtype=float)
        x_centered = x - x.mean()
        denom = float(np.sum(x_centered * x_centered))
        normalized = windows[valid] / starts[valid, None]
        y_centered = normalized - normalized.mean(axis=1, keepdims=True)
        slopes = (y_centered @ x_centered) / denom
        result[end_indices[valid]] = slopes * 10000
    return pd.Series(result, index=close_series.index)


def build_overheat_features(prices: pd.DataFrame) -> dict[str, pd.DataFrame]:
    features: dict[str, pd.DataFrame] = {}
    for code in subd.ASSETS:
        price = prices[code].astype(float)
        ma = price.rolling(CN_BIAS_N).mean()
        bias = price / ma - 1.0
        bias_mom = calc_bias_momentum(price)
        same_side = (bias > 0) & (bias_mom > 0) & bias.notna() & bias_mom.notna()
        features[code] = pd.DataFrame(
            {"bias": bias, "bias_mom": bias_mom, "same_side": same_side},
            index=prices.index,
        )
    return features


def apply_overheat_overlay(
    curve: pd.DataFrame,
    features: dict[str, pd.DataFrame],
    case: OverheatCase,
    one_way_cost: float,
    recovery_mode: Literal["same_side_or_exit", "exit_only"] = "same_side_or_exit",
) -> pd.DataFrame:
    if (
        not math.isfinite(float(case.enter))
        or not math.isfinite(float(case.exit))
        or not 0 < case.exit < case.enter
    ):
        raise ValueError(f"Bad overheat thresholds: {case}")
    if not math.isfinite(float(case.derisk_scale)) or not 0 <= case.derisk_scale <= 1:
        raise ValueError(f"Bad derisk scale: {case}")
    if recovery_mode not in {"same_side_or_exit", "exit_only"}:
        raise ValueError(f"Bad overheat recovery mode: {recovery_mode}")

    out = curve.copy()
    defense_on = False
    state_asset: str | None = None
    effective_scales = []
    next_scales = []
    effective_on_vals = []
    next_on_vals = []
    trigger_vals = []
    recover_vals = []
    bias_vals = []
    mom_vals = []
    same_side_vals = []

    aligned_features: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for code, frame in features.items():
        aligned = frame.reindex(out.index)
        bias_arr = aligned["bias"].to_numpy(dtype=float)
        mom_arr = aligned["bias_mom"].to_numpy(dtype=float)
        same_side_arr = aligned["same_side"].fillna(False).astype(bool).to_numpy()
        aligned_features[code] = (bias_arr, mom_arr, same_side_arr)

    effective_holdings = out["position_before"].astype(str).to_numpy()
    target_holdings = out["position"].astype(str).to_numpy()

    for i in range(len(out)):
        effective_holding = effective_holdings[i]
        target_holding = target_holdings[i]
        effective_eligible = effective_holding in subd.ASSETS
        target_eligible = target_holding in subd.ASSETS

        effective_state = bool(defense_on and state_asset == effective_holding and effective_eligible)
        effective_scale = float(case.derisk_scale) if effective_state else 1.0
        next_state = bool(defense_on and state_asset == target_holding and target_eligible)

        bias = math.nan
        mom = math.nan
        same_side = False
        if target_eligible and target_holding in aligned_features:
            bias_arr, mom_arr, same_side_arr = aligned_features[target_holding]
            bias = float(bias_arr[i]) if pd.notna(bias_arr[i]) else math.nan
            mom = float(mom_arr[i]) if pd.notna(mom_arr[i]) else math.nan
            same_side = bool(same_side_arr[i])

        triggered = False
        recovered = False
        prior_next_state = next_state
        if target_eligible:
            if next_state:
                if pd.notna(bias) and bias <= case.exit:
                    next_state = False
                    recovered = True
                elif recovery_mode == "same_side_or_exit" and not same_side:
                    next_state = False
                    recovered = True
            elif pd.notna(bias) and same_side and bias >= case.enter:
                next_state = True
                triggered = True
        else:
            next_state = False

        next_scale = float(case.derisk_scale) if next_state and target_eligible else 1.0
        effective_scales.append(effective_scale)
        next_scales.append(next_scale)
        effective_on_vals.append(bool(effective_scale < 0.999999 and effective_eligible))
        next_on_vals.append(bool(next_scale < 0.999999 and target_eligible))
        trigger_vals.append(triggered)
        recover_vals.append(bool(recovered and prior_next_state))
        bias_vals.append(bias)
        mom_vals.append(mom)
        same_side_vals.append(same_side)
        defense_on = next_state
        state_asset = target_holding if target_eligible else None

    out.insert(0, "scenario", case.label)
    out["overheat_enter"] = case.enter
    out["overheat_exit"] = case.exit
    out["overheat_derisk_scale"] = case.derisk_scale
    out["overheat_recovery_mode"] = recovery_mode
    out["nav_before_overheat"] = out["nav"]
    out["return_before_overheat"] = out["return"]
    out["overheat_scale_effective"] = pd.Series(effective_scales, index=out.index, dtype=float)
    out["overheat_scale_next"] = pd.Series(next_scales, index=out.index, dtype=float)
    out["overheat_scale"] = out["overheat_scale_next"]
    out["overheat_on_effective"] = pd.Series(effective_on_vals, index=out.index, dtype=bool)
    out["overheat_on"] = pd.Series(next_on_vals, index=out.index, dtype=bool)
    out["overheat_triggered"] = pd.Series(trigger_vals, index=out.index, dtype=bool)
    out["overheat_recovered"] = pd.Series(recover_vals, index=out.index, dtype=bool)
    out["overheat_bias"] = pd.Series(bias_vals, index=out.index, dtype=float)
    out["overheat_bias_mom"] = pd.Series(mom_vals, index=out.index, dtype=float)
    out["overheat_same_side"] = pd.Series(same_side_vals, index=out.index, dtype=bool)
    out["overheat_tc"] = 0.0
    target_vol_effective = _float_series(out, "target_vol_scale_effective", 1.0)
    target_vol_next = _float_series(out, "target_vol_scale_next", 1.0)
    out = _recompute_final_exposure_nav(
        out,
        target_vol_effective,
        target_vol_next,
        out["overheat_scale_effective"],
        out["overheat_scale_next"],
        one_way_cost,
    )
    return out


def summarize(curve: pd.DataFrame, start: pd.Timestamp, label: str) -> dict[str, object]:
    sub = curve.loc[curve.index >= start].copy()
    nav = sub["nav"] / float(sub["nav"].iloc[0])
    ret = nav.pct_change().fillna(0.0)
    years = len(sub) / subd.TRADING_DAYS
    std = ret.std(ddof=0)
    exposure_col = "final_exposure_after_overheat" if "final_exposure_after_overheat" in sub.columns else "final_exposure"
    final_exposure = sub[exposure_col].astype(float).fillna(0.0)
    return {
        "version": curve["version"].iloc[0],
        "scenario": curve["scenario"].iloc[0],
        "window": label,
        "start": sub.index[0].date().isoformat(),
        "end": sub.index[-1].date().isoformat(),
        "days": len(sub),
        "total": float(nav.iloc[-1] - 1.0),
        "cagr": float(nav.iloc[-1] ** (1.0 / years) - 1.0),
        "maxdd": subd.max_drawdown(nav),
        "sharpe": float(ret.mean() / std * math.sqrt(subd.TRADING_DAYS)) if std > 0 else math.nan,
        "vol": float(std * math.sqrt(subd.TRADING_DAYS)),
        "cash_days": int((sub["position"] == "CASH").sum()),
        "half_position_days": int(((sub["holding_fraction"] > 1e-12) & (sub["holding_fraction"] < 1.0 - 1e-12)).sum()),
        "pending_days": int(sub["pending_entry_target"].notna().sum()),
        "staged_initials": int(sub["staged_initial"].astype(bool).sum()),
        "staged_fills": int(sub["fill_on_down_day"].astype(bool).sum()),
        "overheat_days": int(sub["overheat_on"].astype(bool).sum()) if "overheat_on" in sub.columns else 0,
        "overheat_triggers": int(sub["overheat_triggered"].astype(bool).sum()) if "overheat_triggered" in sub.columns else 0,
        "overheat_recoveries": int(sub["overheat_recovered"].astype(bool).sum()) if "overheat_recovered" in sub.columns else 0,
        "trades": int((sub["turnover"].astype(float) > 1e-12).sum()),
        "cost_sum": float(sub["cost"].sum()),
        "turnover_sum": float(sub["turnover"].sum()),
        "avg_scale": float(sub["weight"].mean()),
        "avg_final_exposure": float(final_exposure.mean()),
        "max_final_exposure": float(final_exposure.max()),
    }


def tag_original(curve: pd.DataFrame) -> pd.DataFrame:
    out = curve.copy()
    out.insert(0, "scenario", "v1_0_original_full_entry")
    out.insert(0, "version", "1.0")
    out["overheat_enter"] = np.nan
    out["overheat_exit"] = np.nan
    out["overheat_derisk_scale"] = 1.0
    out["overheat_recovery_mode"] = ""
    out["overheat_scale_effective"] = 1.0
    out["overheat_scale_next"] = 1.0
    out["overheat_scale"] = 1.0
    out["overheat_on"] = False
    out["overheat_on_effective"] = False
    out["overheat_triggered"] = False
    out["overheat_recovered"] = False
    out["overheat_tc"] = 0.0
    out["nav_before_overheat"] = out["nav"]
    return out


def trading_day_window_start(index: pd.Index, end: pd.Timestamp, trading_days: int) -> pd.Timestamp:
    ordered = pd.DatetimeIndex(index).sort_values()
    eligible = ordered[ordered <= pd.Timestamp(end)]
    if eligible.empty:
        raise ValueError(f"No trading dates on or before {end}")
    pos = len(eligible) - 1
    start_pos = max(0, pos - trading_days + 1)
    return pd.Timestamp(eligible[start_pos])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Sub-D six ETF V1.1 backtest.")
    parser.add_argument("--start-date", default=START_DATE.date().isoformat())
    parser.add_argument("--end-date", default=END_DATE.date().isoformat())
    parser.add_argument("--eval-start", default=EVAL_START.date().isoformat())
    parser.add_argument("--output-tag", default=None)
    parser.add_argument("--source", choices=["sina", "eastmoney"], default="eastmoney")
    return parser.parse_args()


def build_curves(prices: pd.DataFrame, config: subd.RunConfig) -> list[pd.DataFrame]:
    original = apply_target_vol_overlay(
        run_staged_entry(
            prices,
            config,
            EntryCase("full_entry_baseline", "full_entry", 1.0),
            R2_THRESHOLD,
            V10_BASELINE_SWITCH_BUFFER,
        ),
        TARGET_VOL,
        config.vol_window,
        config.max_lev,
        config.one_way_cost,
    )
    staged = apply_target_vol_overlay(
        run_staged_entry(
            prices,
            config,
            EntryCase("all_new_asset_50_wait_down_no_timeout", "all_new_asset_50_wait_down", INITIAL_ENTRY_FRACTION),
            R2_THRESHOLD,
            SWITCH_BUFFER,
        ),
        TARGET_VOL,
        config.vol_window,
        config.max_lev,
        config.one_way_cost,
    )
    v11 = apply_overheat_overlay(
        staged,
        build_overheat_features(prices),
        OverheatCase("v1_1_staged_50_plus_ma60_overheat", OVERHEAT_ENTER, OVERHEAT_EXIT, OVERHEAT_DERISK_SCALE),
        config.one_way_cost,
    )
    v11.insert(0, "version", VERSION)
    v11["scenario"] = "v1_1_staged_50_plus_ma60_overheat"
    return [tag_original(original), v11]


def main() -> None:
    args = parse_args()
    start_date = pd.Timestamp(args.start_date).normalize()
    end_date = pd.Timestamp(args.end_date).normalize()
    eval_start = pd.Timestamp(args.eval_start).normalize()
    output_tag = args.output_tag or f"v1_1_{end_date.strftime('%Y%m%d')}"
    config = subd.RunConfig(
        source=args.source,
        one_way_cost=ONE_WAY_COST,
        start_date=start_date,
        end_date=end_date,
        output_tag=output_tag,
        target_vols=(),
        vol_window=subd.DEFAULT_VOL_WINDOW,
        max_lev=subd.DEFAULT_MAX_LEV,
    )
    prices, sources = subd.load_close(config)
    prices = prices.loc[prices.index >= config.start_date]
    prices, common_last, _last_by_asset = align_prices_to_common_valid_date(prices, list(subd.ASSETS))
    curves = build_curves(prices, config)
    windows = {
        "from_2020": eval_start,
        "5Y": trading_day_window_start(prices.index, common_last, 5 * subd.TRADING_DAYS),
        "3Y": trading_day_window_start(prices.index, common_last, 3 * subd.TRADING_DAYS),
        "1Y": trading_day_window_start(prices.index, common_last, subd.TRADING_DAYS),
    }
    summary = pd.DataFrame([summarize(curve, start, label) for curve in curves for label, start in windows.items()])

    prefix = f"subd_six_etf_{config.output_tag}"
    subd.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.concat(curves).reset_index().to_csv(subd.OUTPUT_DIR / f"{prefix}_daily.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(subd.OUTPUT_DIR / f"{prefix}_summary.csv", index=False, encoding="utf-8-sig")
    sources.to_csv(subd.OUTPUT_DIR / f"{prefix}_sources.csv", index=False, encoding="utf-8-sig")
    subd.data_quality(prices).to_csv(subd.OUTPUT_DIR / f"{prefix}_data_quality.csv", index=False, encoding="utf-8-sig")

    print("SUBD SIX ETF V1.1 SUMMARY")
    print(summary.to_string(index=False))
    print(f"\nWROTE {subd.OUTPUT_DIR / (prefix + '_summary.csv')}")
    print(f"WROTE {subd.OUTPUT_DIR / (prefix + '_daily.csv')}")


if __name__ == "__main__":
    main()
