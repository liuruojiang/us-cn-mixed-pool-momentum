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
SCALE_DIR = RUN_DIR.parent / "20260903_mixed_us_cn_momentum_subd_pure_momentum_base_plus_overheat_six_etf_mixed_pool_overheat_derisk_scale"
THRESHOLDS: tuple[float | None, ...] = (
    None, 0.05, 0.075, 0.10, 0.125, 0.15, 0.175,
    0.18, 0.185, 0.19, 0.195, 0.20, 0.205, 0.21, 0.215, 0.22,
    0.225, 0.23, 0.235, 0.24, 0.25, 0.275, 0.30, 0.35, 0.40, 0.45, 0.50,
)
WINDOWS = {"full_sample": "full", "10Y": "last_10y", "5Y": "last_5y", "3Y": "last_3y", "1Y": "last_1y"}


def label(value: float | None) -> str:
    return "overheat_off" if value is None else f"enter_{value:.3f}"


def metrics(curve: pd.DataFrame, start: pd.Timestamp) -> dict[str, object]:
    frame = curve.loc[curve.index >= start].copy()
    ret = v11._daily_returns_for_window(frame)
    wealth = v11._wealth_from_returns(ret)
    std = float(ret.std(ddof=0))
    exposure_col = "exposure_effective" if "exposure_effective" in frame else "fraction_before"
    exposure = frame[exposure_col].astype(float).fillna(0.0)
    return {
        "start": frame.index[0].date().isoformat(), "end": frame.index[-1].date().isoformat(), "rows": len(frame),
        "ann_return": float(wealth.iloc[-1] ** (subd.TRADING_DAYS / len(frame)) - 1.0),
        "ann_vol": std * math.sqrt(subd.TRADING_DAYS),
        "sharpe_repo": float(ret.mean() / std * math.sqrt(subd.TRADING_DAYS)) if std else 0.0,
        "max_dd": float(subd.max_drawdown(wealth)), "avg_weight": float(exposure.mean()),
        "holding_day_ratio": float((exposure > 0).mean()),
        "overheat_days": int(frame["overheat_on_effective"].astype(bool).sum()) if "overheat_on_effective" in frame else 0,
        "overheat_triggers": int(frame["overheat_triggered"].astype(bool).sum()) if "overheat_triggered" in frame else 0,
        "overheat_recoveries": int(frame["overheat_recovered"].astype(bool).sum()) if "overheat_recovered" in frame else 0,
        "avg_turnover": float(frame["turnover"].astype(float).mean()),
        "turnover_total": float(frame["turnover"].astype(float).sum()),
        "cost_total": float(frame["cost"].astype(float).sum()),
    }


def episode_stats(candidate: pd.DataFrame, base: pd.DataFrame) -> dict[str, object]:
    active = candidate["overheat_triggered"].astype(bool) | candidate["overheat_on_effective"].astype(bool) | candidate["overheat_on"].astype(bool) | candidate["overheat_recovered"].astype(bool)
    ids = active.ne(active.shift(fill_value=False)).cumsum()
    alphas = []
    for _, frame in candidate.loc[active].groupby(ids.loc[active]):
        loc = frame.index
        log_alpha = (np.log1p(candidate.loc[loc, "return"].astype(float)) - np.log1p(base.loc[loc, "return"].astype(float))).sum()
        alphas.append(float(np.expm1(log_alpha)))
    total = float(sum(alphas))
    top3 = float(sum(sorted(alphas, reverse=True)[:3]) / total) if alphas and abs(total) > 1e-15 else 0.0
    return {"episodes": len(alphas), "positive_episodes": sum(x > 0 for x in alphas), "negative_episodes": sum(x < 0 for x in alphas), "event_alpha_sum": total, "top3_alpha_share": top3}


def main() -> None:
    started = time.perf_counter()
    prices = pd.read_csv(SOURCE_DIR / "price_snapshot_qfq.csv.gz", parse_dates=["date"]).set_index("date")
    prices = prices[list(subd.ASSETS)].astype(float)
    base = pd.read_csv(BASE_DIR / "daily_outputs" / "full_entry_1.00.csv.gz", parse_dates=["date"]).set_index("date")
    names = {f"price_ffill_{code}": code for code in subd.ASSETS}
    flags = base[list(names)].rename(columns=names).astype(bool).reindex(prices.index).fillna(False)
    prices.attrs["price_ffill_flags"] = flags
    features = v11.build_overheat_features(prices)
    end = pd.Timestamp(prices.index.max())
    perf_windows = v11.build_performance_windows(prices.index, end, v11.EVAL_START)

    curves: dict[float | None, pd.DataFrame] = {None: base.copy()}
    original_fraction = v11.INITIAL_ENTRY_FRACTION
    v11.INITIAL_ENTRY_FRACTION = 1.0
    try:
        for enter in THRESHOLDS[1:]:
            curves[enter] = v11.apply_overheat_overlay(
                base, features, v11.OverheatCase(label(enter), enter, enter - 0.02, 0.0),
                v11.ONE_WAY_COST, recovery_mode="same_side_or_exit", price_ffill_flags=flags,
            )
    finally:
        v11.INITIAL_ENTRY_FRACTION = original_fraction

    rows = []
    event_rows = []
    for enter, curve in curves.items():
        stats = {"episodes": 0, "positive_episodes": 0, "negative_episodes": 0, "event_alpha_sum": 0.0, "top3_alpha_share": 0.0} if enter is None else episode_stats(curve, base)
        event_rows.append({"candidate": label(enter), "overheat_enter": "off" if enter is None else enter, "overheat_exit": "off" if enter is None else enter - 0.02, **stats})
        for source_window, segment in WINDOWS.items():
            row = metrics(curve, perf_windows[source_window])
            row.update({"candidate": label(enter), "segment": segment, "overheat_enter": "off" if enter is None else enter, "overheat_exit": "off" if enter is None else enter - 0.02, "overheat_derisk_scale": 0.0, **stats})
            rows.append(row)
    long = pd.DataFrame(rows)
    long.to_csv(RUN_DIR / "scan_summary.csv", index=False)
    pd.DataFrame(event_rows).to_csv(RUN_DIR / "threshold_event_summary.csv", index=False)

    wide = long[["candidate", "overheat_enter", "overheat_exit", "overheat_derisk_scale"]].drop_duplicates().set_index("candidate")
    for name in ("ann_return", "ann_vol", "sharpe_repo", "max_dd", "avg_weight", "holding_day_ratio", "overheat_days", "overheat_triggers", "avg_turnover", "cost_total"):
        pivot = long.pivot(index="candidate", columns="segment", values=name).rename(columns=lambda s: f"{name}_{s}")
        wide = wide.join(pivot)
    wide = wide.reset_index()
    off = wide.loc[wide.candidate == "overheat_off"].iloc[0]
    for segment in WINDOWS.values():
        wide[f"ann_return_delta_vs_off_{segment}"] = wide[f"ann_return_{segment}"] - off[f"ann_return_{segment}"]
        wide[f"max_dd_delta_vs_off_{segment}"] = wide[f"max_dd_{segment}"] - off[f"max_dd_{segment}"]
    wide["decision_hint"] = "overheat_enter_scan"
    wide["stability_label"] = "pending_review"
    wide.to_csv(RUN_DIR / "window_metrics.csv", index=False)

    prior = pd.read_csv(SCALE_DIR / "daily_outputs" / "scale_0.00.csv.gz")
    current = curves[0.20].reset_index()
    parity_rows = []
    for name in ("return", "nav", "turnover", "exposure_effective"):
        parity_rows.append({"check": "enter_0.20_vs_prior_scale_scan", "metric": name, "max_abs_diff": float(np.max(np.abs(prior[name].to_numpy(float) - current[name].to_numpy(float))))})
    parity = pd.DataFrame(parity_rows)
    parity.to_csv(RUN_DIR / "parity_checks.csv", index=False)
    nav_diff = float(parity.loc[parity.metric == "nav", "max_abs_diff"].max())
    other_diff = float(parity.loc[parity.metric != "nav", "max_abs_diff"].max())
    if nav_diff > 1e-10 or other_diff > 1e-12:
        raise RuntimeError(f"Parity failed: nav={nav_diff:.3e}, other={other_diff:.3e}")

    daily_dir = RUN_DIR / "daily_outputs"
    daily_dir.mkdir(exist_ok=True)
    for enter, curve in curves.items():
        curve.to_csv(daily_dir / f"{label(enter)}.csv.gz", index_label="date", compression="gzip")
    meta_path = RUN_DIR / "scan_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["data_snapshot"] = {"source_run": SOURCE_DIR.name, "base_run": BASE_DIR.name, "start": prices.index.min().date().isoformat(), "end": end.date().isoformat(), "rows": len(prices), "adjustment": "qfq/front-adjusted"}
    meta["parity_check"] = {"nav_max_abs_diff": nav_diff, "other_max_abs_diff": other_diff, "passed": True}
    meta["elapsed_sec"] = round(time.perf_counter() - started, 3)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"candidates": len(THRESHOLDS), "rows": len(prices), "end": end.date().isoformat(), "elapsed_sec": meta["elapsed_sec"], "nav_diff": nav_diff, "other_diff": other_diff}))


if __name__ == "__main__":
    main()
