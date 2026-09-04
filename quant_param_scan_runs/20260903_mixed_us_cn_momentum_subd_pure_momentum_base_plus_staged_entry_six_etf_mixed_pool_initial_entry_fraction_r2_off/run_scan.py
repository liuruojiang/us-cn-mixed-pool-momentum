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
FRACTIONS = (1.00, 0.90, 0.80, 0.75, 0.67, 0.60, 0.50, 0.40, 0.33, 0.25, 0.10)
WINDOWS = {"full_sample": "full", "10Y": "last_10y", "5Y": "last_5y", "3Y": "last_3y", "1Y": "last_1y"}


def label_for(fraction: float) -> str:
    return "full_entry_1.00" if fraction == 1.0 else f"staged_{fraction:.2f}"


def metrics(curve: pd.DataFrame, start: pd.Timestamp) -> dict[str, object]:
    frame = curve.loc[curve.index >= start].copy()
    ret = v11._daily_returns_for_window(frame)
    wealth = v11._wealth_from_returns(ret)
    std = float(ret.std(ddof=0))
    exposure = frame["fraction_before"].astype(float).fillna(0.0)
    pending = frame["pending_entry_target"].notna()
    return {
        "start": frame.index[0].date().isoformat(), "end": frame.index[-1].date().isoformat(), "rows": len(frame),
        "ann_return": float(wealth.iloc[-1] ** (subd.TRADING_DAYS / len(frame)) - 1.0),
        "ann_vol": std * math.sqrt(subd.TRADING_DAYS),
        "sharpe_repo": float(ret.mean() / std * math.sqrt(subd.TRADING_DAYS)) if std else 0.0,
        "max_dd": float(subd.max_drawdown(wealth)), "avg_weight": float(exposure.mean()),
        "holding_day_ratio": float((exposure > 0).mean()),
        "partial_position_days": int(((exposure > 0) & (exposure < 1)).sum()),
        "pending_days": int(pending.sum()),
        "max_pending_days": int(frame.loc[pending, "pending_entry_days"].max()) if pending.any() else 0,
        "staged_initials": int(frame["staged_initial"].astype(bool).sum()),
        "staged_fills": int(frame["fill_on_down_day"].astype(bool).sum()),
        "avg_turnover": float(frame["turnover"].astype(float).mean()),
        "turnover_total": float(frame["turnover"].astype(float).sum()),
        "cost_total": float(frame["cost"].astype(float).sum()),
    }


def main() -> None:
    started = time.perf_counter()
    prices = pd.read_csv(SOURCE_DIR / "price_snapshot_qfq.csv.gz", parse_dates=["date"]).set_index("date")
    prices = prices[list(subd.ASSETS)].astype(float)
    prior = pd.read_csv(SOURCE_DIR / "daily_outputs" / "r2_off_buffer_1.00.csv.gz", parse_dates=["date"]).set_index("date")
    flag_names = {f"price_ffill_{code}": code for code in subd.ASSETS}
    prices.attrs["price_ffill_flags"] = prior[list(flag_names)].rename(columns=flag_names).astype(bool).reindex(prices.index).fillna(False)
    end = pd.Timestamp(prices.index.max())
    perf_windows = v11.build_performance_windows(prices.index, end, v11.EVAL_START)
    config = subd.RunConfig("akshare_em_qfq", v11.ONE_WAY_COST, prices.index.min(), end, "pure_base_staged_entry", (), subd.DEFAULT_VOL_WINDOW, 1.0)

    original = subd.calc_scores
    cache = [({}, {}) if idx < subd.LOOKBACK - 1 else original(prices, idx, None) for idx in range(len(prices))]

    def cached(_prices, idx, r2_threshold=None):
        score, r2 = cache[idx]
        return dict(score), dict(r2)

    curves: dict[float, pd.DataFrame] = {}
    rows: list[dict[str, object]] = []
    subd.calc_scores = cached
    try:
        for fraction in FRACTIONS:
            case = v11.EntryCase("full_entry_pure", "full_entry", 1.0) if fraction == 1.0 else v11.EntryCase(f"staged_{fraction:.2f}", "all_new_asset_50_wait_down", fraction)
            curve = v11.run_staged_entry(prices, config, case, None, 1.0)
            curves[fraction] = curve
            for source_window, segment in WINDOWS.items():
                row = metrics(curve, perf_windows[source_window])
                row.update({"candidate": label_for(fraction), "segment": segment, "initial_entry_fraction": fraction, "r2_threshold": "off", "switch_buffer": 1.0})
                rows.append(row)
    finally:
        subd.calc_scores = original

    exact_half = v11.run_staged_entry(prices, config, v11.EntryCase("staged_0.50_exact", "all_new_asset_50_wait_down", 0.50), None, 1.0)
    long = pd.DataFrame(rows)
    long.to_csv(RUN_DIR / "scan_summary.csv", index=False)
    wide = long[["candidate", "initial_entry_fraction", "r2_threshold", "switch_buffer"]].drop_duplicates().set_index("candidate")
    metric_names = ("ann_return", "ann_vol", "sharpe_repo", "max_dd", "avg_weight", "holding_day_ratio", "partial_position_days", "pending_days", "max_pending_days", "staged_initials", "staged_fills", "avg_turnover", "cost_total")
    for name in metric_names:
        pivot = long.pivot(index="candidate", columns="segment", values=name).rename(columns=lambda segment: f"{name}_{segment}")
        wide = wide.join(pivot)
    wide = wide.reset_index()
    base = wide.loc[wide.candidate == "full_entry_1.00"].iloc[0]
    for segment in WINDOWS.values():
        wide[f"ann_return_delta_vs_full_{segment}"] = wide[f"ann_return_{segment}"] - base[f"ann_return_{segment}"]
        wide[f"max_dd_delta_vs_full_{segment}"] = wide[f"max_dd_{segment}"] - base[f"max_dd_{segment}"]
    wide["decision_hint"] = "pure_base_staged_entry_ablation"
    wide["stability_label"] = "pending_review"
    wide.to_csv(RUN_DIR / "window_metrics.csv", index=False)

    parity_rows = []
    for check, old, new in (("baseline_vs_prior", prior.reset_index(), curves[1.0].reset_index()), ("cached_half_vs_exact", curves[0.5].reset_index(), exact_half.reset_index())):
        for name in ("return", "nav", "turnover", "holding_fraction"):
            parity_rows.append({"check": check, "metric": name, "max_abs_diff": float(np.max(np.abs(old[name].to_numpy(float) - new[name].to_numpy(float))))})
    parity = pd.DataFrame(parity_rows)
    parity.to_csv(RUN_DIR / "parity_checks.csv", index=False)
    max_diff = float(parity.max_abs_diff.max())
    if max_diff > 1e-12:
        raise RuntimeError(f"Parity failed: {max_diff:.3e}")
    daily_dir = RUN_DIR / "daily_outputs"
    daily_dir.mkdir(exist_ok=True)
    for fraction, curve in curves.items():
        curve.to_csv(daily_dir / f"{label_for(fraction)}.csv.gz", index_label="date", compression="gzip")

    meta_path = RUN_DIR / "scan_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["data_snapshot"] = {"source_run": SOURCE_DIR.name, "start": prices.index.min().date().isoformat(), "end": end.date().isoformat(), "rows": len(prices), "adjustment": "qfq/front-adjusted"}
    meta["parity_check"] = {"max_abs_diff": max_diff, "passed": True}
    meta["elapsed_sec"] = round(time.perf_counter() - started, 3)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"candidates": len(FRACTIONS), "rows": len(prices), "end": end.date().isoformat(), "elapsed_sec": meta["elapsed_sec"], "max_parity_diff": max_diff}))


if __name__ == "__main__":
    main()
