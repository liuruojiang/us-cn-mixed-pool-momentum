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
import poe_subd_six_etf_v1_1_bot as poe


RUN_DIR = Path(__file__).resolve().parent
PRIOR_DIR = RUN_DIR.parent / "20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer"
GRID: tuple[float | None, ...] = (
    None, 0.0, 0.01, 0.025, 0.05, 0.075, 0.10, 0.125, 0.15, 0.175,
    0.20, 0.225, 0.25, 0.275, 0.30, 0.325, 0.35, 0.375, 0.40,
    0.45, 0.50, 0.60, 0.70, 0.80, 0.90,
)
WINDOW_NAMES = {
    "full_sample": "full",
    "10Y": "last_10y",
    "5Y": "last_5y",
    "3Y": "last_3y",
    "1Y": "last_1y",
}


def label_for(threshold: float | None) -> str:
    return "r2_off" if threshold is None else f"r2_{threshold:.3f}"


def metrics_for(curve: pd.DataFrame, start: pd.Timestamp) -> dict[str, float | int | str]:
    sub = curve.loc[curve.index >= start].copy()
    ret = v11._daily_returns_for_window(sub)
    wealth = v11._wealth_from_returns(ret)
    years = len(sub) / subd.TRADING_DAYS
    std = float(ret.std(ddof=0))
    exposure = sub["fraction_before"].astype(float).fillna(0.0)
    return {
        "start": sub.index[0].date().isoformat(),
        "end": sub.index[-1].date().isoformat(),
        "rows": int(len(sub)),
        "ann_return": float(wealth.iloc[-1] ** (1.0 / years) - 1.0),
        "ann_vol": float(std * math.sqrt(subd.TRADING_DAYS)),
        "sharpe_repo": float(ret.mean() / std * math.sqrt(subd.TRADING_DAYS)) if std > 0 else 0.0,
        "max_dd": float(subd.max_drawdown(wealth)),
        "avg_weight": float(exposure.mean()),
        "held_day_avg_weight": float(exposure.loc[exposure > 0].mean()) if (exposure > 0).any() else 0.0,
        "holding_days": int((exposure > 0).sum()),
        "holding_day_ratio": float((exposure > 0).mean()),
        "avg_turnover": float(sub["turnover"].astype(float).mean()),
        "turnover_total": float(sub["turnover"].astype(float).sum()),
        "cost_total": float(sub["cost"].astype(float).sum()),
        "trade_days": int((sub["turnover"].astype(float) > 1e-12).sum()),
    }


def restore_ffill_flags(prices: pd.DataFrame) -> None:
    prior_daily = pd.read_csv(PRIOR_DIR / "daily_outputs" / "r2_off_buffer_1.00.csv.gz", parse_dates=["date"])
    prior_daily = prior_daily.set_index("date")
    columns = {f"price_ffill_{code}": code for code in subd.ASSETS}
    flags = prior_daily[list(columns)].rename(columns=columns).astype(bool)
    flags = flags.reindex(prices.index).fillna(False).astype(bool)
    prices.attrs["price_ffill_flags"] = flags


def main() -> None:
    started = time.perf_counter()
    price_path = PRIOR_DIR / "price_snapshot_qfq.csv.gz"
    prices = pd.read_csv(price_path, parse_dates=["date"]).set_index("date")
    prices = prices[list(subd.ASSETS)].astype(float)
    restore_ffill_flags(prices)
    common_last = pd.Timestamp(prices.index.max())
    windows = v11.build_performance_windows(prices.index, common_last, v11.EVAL_START)
    config = subd.RunConfig(
        source="akshare_em_qfq",
        one_way_cost=v11.ONE_WAY_COST,
        start_date=pd.Timestamp(prices.index.min()),
        end_date=common_last,
        output_tag="no_floor_r2_scan",
        target_vols=(),
        vol_window=subd.DEFAULT_VOL_WINDOW,
        max_lev=1.0,
    )

    original_calc_scores = subd.calc_scores
    original_floor = subd.SCORE_MIN
    assert subd.SCORE_MAX == 5 and subd.LOOKBACK == 25
    assert len(prices) == 3578 and prices.index.is_unique and prices.index.is_monotonic_increasing
    precomputed: list[tuple[dict[str, float], dict[str, float]]] = []
    try:
        subd.SCORE_MIN = -math.inf
        for idx in range(len(prices)):
            if idx < subd.LOOKBACK - 1:
                precomputed.append(({}, {}))
            else:
                precomputed.append(original_calc_scores(prices, idx, r2_threshold=None))

    finally:
        subd.SCORE_MIN = original_floor

    def cached_calc_scores(_prices: pd.DataFrame, idx: int, r2_threshold: float | None = None):
        raw_scores, r2_values = precomputed[idx]
        if r2_threshold is None:
            return dict(raw_scores), dict(r2_values)
        filtered = {
            code: score
            for code, score in raw_scores.items()
            if code in r2_values and r2_values[code] >= r2_threshold
        }
        return filtered, dict(r2_values)

    rows: list[dict[str, object]] = []
    curves: dict[float | None, pd.DataFrame] = {}
    full_entry = v11.EntryCase("full_entry_clean_base", "full_entry", 1.0)
    subd.calc_scores = cached_calc_scores
    try:
        for threshold in GRID:
            curve = v11.run_staged_entry(prices, config, full_entry, threshold, 1.00)
            curves[threshold] = curve
            print(f"Completed {label_for(threshold)}", flush=True)
            for source_name, segment in WINDOW_NAMES.items():
                row = metrics_for(curve, windows[source_name])
                row.update(
                    {
                        "candidate": label_for(threshold),
                        "segment": segment,
                        "r2_threshold": "off" if threshold is None else threshold,
                        "switch_buffer": 1.0,
                    }
                )
                rows.append(row)
    finally:
        subd.calc_scores = original_calc_scores

    long = pd.DataFrame(rows)
    long = long[[
        "candidate", "segment", "r2_threshold", "switch_buffer", "start", "end", "rows",
        "ann_return", "ann_vol", "sharpe_repo", "max_dd", "avg_weight",
        "held_day_avg_weight", "holding_days", "holding_day_ratio", "avg_turnover",
        "turnover_total", "cost_total", "trade_days",
    ]]
    long.to_csv(RUN_DIR / "scan_summary.csv", index=False)

    params = long[["candidate", "r2_threshold", "switch_buffer"]].drop_duplicates().set_index("candidate")
    wide = params.copy()
    for metric in ("ann_return", "ann_vol", "sharpe_repo", "max_dd", "avg_turnover", "holding_day_ratio", "cost_total"):
        pivot = long.pivot(index="candidate", columns="segment", values=metric)
        pivot = pivot.rename(columns={segment: f"{metric}_{segment}" for segment in pivot.columns})
        wide = wide.join(pivot)
    wide = wide.reset_index()
    baseline = wide.loc[wide["candidate"] == "r2_off"].iloc[0]
    for segment in WINDOW_NAMES.values():
        wide[f"ann_return_delta_vs_off_{segment}"] = wide[f"ann_return_{segment}"] - baseline[f"ann_return_{segment}"]
        wide[f"max_dd_delta_vs_off_{segment}"] = wide[f"max_dd_{segment}"] - baseline[f"max_dd_{segment}"]
    wide["decision_hint"] = "boundary_mapping"
    wide["stability_label"] = "pending_review"
    wide.to_csv(RUN_DIR / "window_metrics.csv", index=False)

    parity_rows = []
    def compare(check, expected, observed):
        assert expected.index.equals(observed.index)
        for metric in ("return", "nav", "turnover", "fraction_before"):
            diff = float(np.max(np.abs(expected[metric].to_numpy(float) - observed[metric].to_numpy(float))))
            parity_rows.append({"check": check, "metric": metric, "abs_diff": diff})
        parity_rows.append({"check": check, "metric": "position", "abs_diff": float((expected.position != observed.position).sum())})

    accepted = pd.read_csv(RUN_DIR.parent / "20260904_subd_no_floor_score_max/daily_outputs/score_max_5.csv.gz", parse_dates=["date"]).set_index("date")
    compare("off_vs_accepted_no_floor", accepted, curves[None])
    compare("zero_vs_off", curves[None], curves[0.0])
    try:
        subd.SCORE_MIN = -math.inf
        direct = v11.run_staged_entry(prices, config, full_entry, 0.20, 1.0)
    finally:
        subd.SCORE_MIN = original_floor
    compare("cached_vs_uncached_at_0p20", direct, curves[0.20])
    poe_floor = poe.SCORE_MIN
    try:
        poe.SCORE_MIN = -math.inf
        poe_curve = poe.run_staged_entry(prices, config, poe.EntryCase("parity", "full_entry", 1.0), 0.20, 1.0, price_ffill_flags=prices.attrs["price_ffill_flags"])
    finally:
        poe.SCORE_MIN = poe_floor
    compare("runner_vs_poe_at_0p20", poe_curve, curves[0.20])
    parity = pd.DataFrame(parity_rows)
    parity.to_csv(RUN_DIR / "parity_checks.csv", index=False)
    max_parity_diff = float(parity.abs_diff.max())
    if max_parity_diff > 1e-12:
        raise RuntimeError(f"Parity failed: {max_parity_diff}")

    daily_dir = RUN_DIR / "daily_outputs"
    daily_dir.mkdir(exist_ok=True)
    for threshold in GRID:
        curves[threshold].to_csv(daily_dir / f"{label_for(threshold)}.csv.gz", index_label="date", compression="gzip")

    meta_path = RUN_DIR / "scan_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["data_snapshot"] = {
        "source_run": PRIOR_DIR.name,
        "price_snapshot": str(price_path),
        "start": prices.index.min().date().isoformat(),
        "end": prices.index.max().date().isoformat(),
        "rows": int(len(prices)),
        "adjustment": "qfq/front-adjusted",
        "reuse_reason": "same-session frozen matched panel for exact comparability",
    }
    meta["parity_check"] = {
        "checks": ["accepted_no_floor", "zero_vs_off", "cached_vs_uncached_0.20", "runner_vs_poe_0.20"],
        "daily_thresholds": ["off", 0.20],
        "max_abs_diff": max_parity_diff,
        "passed": True,
    }
    meta["elapsed_sec"] = round(time.perf_counter() - started, 3)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "candidates": len(GRID),
        "rows": len(prices),
        "end": common_last.date().isoformat(),
        "elapsed_sec": meta["elapsed_sec"],
        "max_parity_diff": max_parity_diff,
    }))


if __name__ == "__main__":
    main()
