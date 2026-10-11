from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import research_subd_six_etf_weighted_slope as subd
import run_subd_six_etf_v1_1 as v11

RUN_DIR = Path(__file__).resolve().parent
SOURCE_DIR = RUN_DIR.parent / "20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer"
BASE_DIR = RUN_DIR.parent / "20260903_mixed_us_cn_momentum_subd_pure_momentum_base_plus_staged_entry_six_etf_mixed_pool_initial_entry_fraction_r2_off"
SCALES = (1.00, 0.90, 0.75, 0.50, 0.25, 0.10, 0.00)
WINDOWS = {"full_sample": "full", "10Y": "last_10y", "5Y": "last_5y", "3Y": "last_3y", "1Y": "last_1y"}


def label(scale: float) -> str:
    return "scale_1.00_off" if scale == 1.0 else f"scale_{scale:.2f}"


def metrics(curve: pd.DataFrame, start: pd.Timestamp) -> dict[str, object]:
    frame = curve.loc[curve.index >= start].copy()
    ret = v11._daily_returns_for_window(frame)
    wealth = v11._wealth_from_returns(ret)
    std = float(ret.std(ddof=0))
    exposure = frame["exposure_effective"].astype(float).fillna(0.0)
    return {
        "start": frame.index[0].date().isoformat(), "end": frame.index[-1].date().isoformat(), "rows": len(frame),
        "ann_return": float(wealth.iloc[-1] ** (subd.TRADING_DAYS / len(frame)) - 1.0),
        "ann_vol": std * math.sqrt(subd.TRADING_DAYS),
        "sharpe_repo": float(ret.mean() / std * math.sqrt(subd.TRADING_DAYS)) if std else 0.0,
        "max_dd": float(subd.max_drawdown(wealth)),
        "avg_weight": float(exposure.mean()), "holding_day_ratio": float((exposure > 0).mean()),
        "overheat_days": int(frame["overheat_on_effective"].astype(bool).sum()),
        "overheat_triggers": int(frame["overheat_triggered"].astype(bool).sum()),
        "overheat_recoveries": int(frame["overheat_recovered"].astype(bool).sum()),
        "avg_turnover": float(frame["turnover"].astype(float).mean()),
        "turnover_total": float(frame["turnover"].astype(float).sum()),
        "cost_total": float(frame["cost"].astype(float).sum()),
    }


def main() -> None:
    started = time.perf_counter()
    prices = pd.read_csv(SOURCE_DIR / "price_snapshot_qfq.csv.gz", parse_dates=["date"]).set_index("date")
    prices = prices[list(subd.ASSETS)].astype(float)
    base = pd.read_csv(BASE_DIR / "daily_outputs" / "full_entry_1.00.csv.gz", parse_dates=["date"]).set_index("date")
    flag_names = {f"price_ffill_{code}": code for code in subd.ASSETS}
    flags = base[list(flag_names)].rename(columns=flag_names).astype(bool).reindex(prices.index).fillna(False)
    prices.attrs["price_ffill_flags"] = flags
    features = v11.build_overheat_features(prices)
    end = pd.Timestamp(prices.index.max())
    perf_windows = v11.build_performance_windows(prices.index, end, v11.EVAL_START)

    curves: dict[float, pd.DataFrame] = {}
    rows: list[dict[str, object]] = []
    original_initial_fraction = v11.INITIAL_ENTRY_FRACTION
    v11.INITIAL_ENTRY_FRACTION = 1.0
    try:
        for scale in SCALES:
            curve = v11.apply_overheat_overlay(
                base,
                features,
                v11.OverheatCase(label(scale), v11.OVERHEAT_ENTER, v11.OVERHEAT_EXIT, scale),
                v11.ONE_WAY_COST,
                recovery_mode="same_side_or_exit",
                price_ffill_flags=flags,
            )
            curves[scale] = curve
            for source_window, segment in WINDOWS.items():
                row = metrics(curve, perf_windows[source_window])
                row.update({
                    "candidate": label(scale), "segment": segment, "overheat_derisk_scale": scale,
                    "overheat_enter": v11.OVERHEAT_ENTER, "overheat_exit": v11.OVERHEAT_EXIT,
                    "bias_ma": v11.CN_BIAS_N, "bias_momentum_days": v11.CN_MOM_DAY,
                })
                rows.append(row)
    finally:
        v11.INITIAL_ENTRY_FRACTION = original_initial_fraction

    long = pd.DataFrame(rows)
    long.to_csv(RUN_DIR / "scan_summary.csv", index=False)
    wide = long[["candidate", "overheat_derisk_scale", "overheat_enter", "overheat_exit", "bias_ma", "bias_momentum_days"]].drop_duplicates().set_index("candidate")
    for name in ("ann_return", "ann_vol", "sharpe_repo", "max_dd", "avg_weight", "holding_day_ratio", "overheat_days", "overheat_triggers", "overheat_recoveries", "avg_turnover", "cost_total"):
        pivot = long.pivot(index="candidate", columns="segment", values=name).rename(columns=lambda segment: f"{name}_{segment}")
        wide = wide.join(pivot)
    wide = wide.reset_index()
    baseline = wide.loc[wide.candidate == "scale_1.00_off"].iloc[0]
    for segment in WINDOWS.values():
        wide[f"ann_return_delta_vs_off_{segment}"] = wide[f"ann_return_{segment}"] - baseline[f"ann_return_{segment}"]
        wide[f"max_dd_delta_vs_off_{segment}"] = wide[f"max_dd_{segment}"] - baseline[f"max_dd_{segment}"]
    wide["decision_hint"] = "overheat_scale_ablation"
    wide["stability_label"] = "pending_review"
    wide.to_csv(RUN_DIR / "window_metrics.csv", index=False)

    off = curves[1.0]
    parity_rows = []
    for name, base_name in (("return", "return"), ("nav", "nav"), ("turnover", "turnover"), ("exposure_effective", "fraction_before")):
        parity_rows.append({
            "check": "scale_1_off_vs_pure_base", "metric": name,
            "max_abs_diff": float(np.max(np.abs(off[name].to_numpy(float) - base[base_name].to_numpy(float)))),
        })
    parity = pd.DataFrame(parity_rows)
    parity.to_csv(RUN_DIR / "parity_checks.csv", index=False)
    max_diff = float(parity.max_abs_diff.max())
    nav_diff = float(parity.loc[parity.metric == "nav", "max_abs_diff"].max())
    non_nav_diff = float(parity.loc[parity.metric != "nav", "max_abs_diff"].max())
    if nav_diff > 1e-10 or non_nav_diff > 1e-12:
        raise RuntimeError(f"Parity failed: nav={nav_diff:.3e}, non_nav={non_nav_diff:.3e}")
    daily_dir = RUN_DIR / "daily_outputs"
    daily_dir.mkdir(exist_ok=True)
    for scale, curve in curves.items():
        curve.to_csv(daily_dir / f"{label(scale)}.csv.gz", index_label="date", compression="gzip")

    off_curve = curves[1.0]
    zero_curve = curves[0.0]
    active = (
        zero_curve["overheat_triggered"].astype(bool)
        | zero_curve["overheat_on_effective"].astype(bool)
        | zero_curve["overheat_on"].astype(bool)
        | zero_curve["overheat_recovered"].astype(bool)
    )
    episode_ids = active.ne(active.shift(fill_value=False)).cumsum()
    episode_rows = []
    for episode_id, frame in zero_curve.loc[active].groupby(episode_ids.loc[active]):
        loc = frame.index
        log_alpha = (
            np.log1p(zero_curve.loc[loc, "return"].astype(float))
            - np.log1p(off_curve.loc[loc, "return"].astype(float))
        ).sum()
        episode_rows.append({
            "episode": int(episode_id),
            "start": loc[0].date().isoformat(),
            "end": loc[-1].date().isoformat(),
            "rows": len(loc),
            "main_asset": str(frame["position_before"].mode().iat[0]),
            "alpha_vs_off": float(np.expm1(log_alpha)),
            "base_compound_return": float(np.prod(1.0 + off_curve.loc[loc, "return"].astype(float)) - 1.0),
            "scale_zero_compound_return": float(np.prod(1.0 + zero_curve.loc[loc, "return"].astype(float)) - 1.0),
        })
    episodes = pd.DataFrame(episode_rows)
    episodes.to_csv(RUN_DIR / "event_attribution.csv", index=False)
    positive_episodes = int((episodes["alpha_vs_off"] > 0.0).sum())
    top3_share = float(
        episodes["alpha_vs_off"].nlargest(3).sum()
        / episodes["alpha_vs_off"].sum()
    )

    meta_path = RUN_DIR / "scan_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["data_snapshot"] = {"source_run": SOURCE_DIR.name, "base_run": BASE_DIR.name, "start": prices.index.min().date().isoformat(), "end": end.date().isoformat(), "rows": len(prices), "adjustment": "qfq/front-adjusted"}
    meta["parity_check"] = {"max_abs_diff": max_diff, "nav_tolerance": 1e-10, "non_nav_tolerance": 1e-12, "passed": True}
    meta["event_concentration"] = {"episodes": len(episodes), "positive_episodes": positive_episodes, "top3_alpha_share": top3_share}
    meta["elapsed_sec"] = round(time.perf_counter() - started, 3)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"candidates": len(SCALES), "rows": len(prices), "end": end.date().isoformat(), "elapsed_sec": meta["elapsed_sec"], "max_parity_diff": max_diff}))


if __name__ == "__main__":
    main()
