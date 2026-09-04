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
R2_DIR = RUN_DIR.parent / "20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_extended_at_buffer_1_00"
SOURCE_DIR = RUN_DIR.parent / "20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer"
FRACTIONS = (1.00, 0.90, 0.80, 0.75, 0.67, 0.60, 0.50, 0.40, 0.33, 0.25, 0.10)
WINDOW_NAMES = {
    "full_sample": "full",
    "10Y": "last_10y",
    "5Y": "last_5y",
    "3Y": "last_3y",
    "1Y": "last_1y",
}


def label_for(fraction: float) -> str:
    return "full_entry_1.00" if fraction == 1.0 else f"staged_{fraction:.2f}"


def metrics_for(curve: pd.DataFrame, start: pd.Timestamp) -> dict[str, float | int | str]:
    sub = curve.loc[curve.index >= start].copy()
    ret = v11._daily_returns_for_window(sub)
    wealth = v11._wealth_from_returns(ret)
    years = len(sub) / subd.TRADING_DAYS
    std = float(ret.std(ddof=0))
    exposure = sub["fraction_before"].astype(float).fillna(0.0)
    pending = sub["pending_entry_target"].notna()
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
        "partial_position_days": int(((exposure > 0) & (exposure < 1.0)).sum()),
        "pending_days": int(pending.sum()),
        "max_pending_days": int(sub.loc[pending, "pending_entry_days"].max()) if pending.any() else 0,
        "staged_initials": int(sub["staged_initial"].astype(bool).sum()),
        "staged_fills": int(sub["fill_on_down_day"].astype(bool).sum()),
        "avg_turnover": float(sub["turnover"].astype(float).mean()),
        "turnover_total": float(sub["turnover"].astype(float).sum()),
        "cost_total": float(sub["cost"].astype(float).sum()),
        "trade_days": int((sub["turnover"].astype(float) > 1e-12).sum()),
    }


def main() -> None:
    started = time.perf_counter()
    price_path = SOURCE_DIR / "price_snapshot_qfq.csv.gz"
    prices = pd.read_csv(price_path, parse_dates=["date"]).set_index("date")
    prices = prices[list(subd.ASSETS)].astype(float)
    prior_daily = pd.read_csv(R2_DIR / "daily_outputs" / "r2_0.200.csv.gz", parse_dates=["date"]).set_index("date")
    flag_columns = {f"price_ffill_{code}": code for code in subd.ASSETS}
    flags = prior_daily[list(flag_columns)].rename(columns=flag_columns).astype(bool)
    prices.attrs["price_ffill_flags"] = flags.reindex(prices.index).fillna(False).astype(bool)
    common_last = pd.Timestamp(prices.index.max())
    windows = v11.build_performance_windows(prices.index, common_last, v11.EVAL_START)
    config = subd.RunConfig(
        source="akshare_em_qfq",
        one_way_cost=v11.ONE_WAY_COST,
        start_date=pd.Timestamp(prices.index.min()),
        end_date=common_last,
        output_tag="initial_entry_fraction_clean_base",
        target_vols=(),
        vol_window=subd.DEFAULT_VOL_WINDOW,
        max_lev=1.0,
    )

    original_calc_scores = subd.calc_scores
    precomputed: list[tuple[dict[str, float], dict[str, float]]] = []
    for idx in range(len(prices)):
        precomputed.append(({}, {}) if idx < subd.LOOKBACK - 1 else original_calc_scores(prices, idx, 0.20))

    def cached_calc_scores(_prices: pd.DataFrame, idx: int, r2_threshold: float | None = None):
        scores, r2_values = precomputed[idx]
        return dict(scores), dict(r2_values)

    curves: dict[float, pd.DataFrame] = {}
    rows: list[dict[str, object]] = []
    subd.calc_scores = cached_calc_scores
    try:
        for fraction in FRACTIONS:
            case = (
                v11.EntryCase("full_entry_clean_base", "full_entry", 1.0)
                if fraction == 1.0
                else v11.EntryCase(f"staged_{fraction:.2f}_no_timeout", "all_new_asset_50_wait_down", fraction)
            )
            curve = v11.run_staged_entry(prices, config, case, 0.20, 1.00)
            curves[fraction] = curve
            for source_name, segment in WINDOW_NAMES.items():
                row = metrics_for(curve, windows[source_name])
                row.update({
                    "candidate": label_for(fraction),
                    "segment": segment,
                    "initial_entry_fraction": fraction,
                    "r2_threshold": 0.20,
                    "switch_buffer": 1.00,
                })
                rows.append(row)
    finally:
        subd.calc_scores = original_calc_scores

    exact_half = v11.run_staged_entry(
        prices,
        config,
        v11.EntryCase("staged_0.50_exact", "all_new_asset_50_wait_down", 0.50),
        0.20,
        1.00,
    )

    long = pd.DataFrame(rows)
    long.to_csv(RUN_DIR / "scan_summary.csv", index=False)
    params = long[["candidate", "initial_entry_fraction", "r2_threshold", "switch_buffer"]].drop_duplicates().set_index("candidate")
    wide = params.copy()
    for metric in (
        "ann_return", "ann_vol", "sharpe_repo", "max_dd", "avg_weight", "avg_turnover",
        "holding_day_ratio", "partial_position_days", "pending_days", "max_pending_days",
        "staged_initials", "staged_fills", "cost_total",
    ):
        pivot = long.pivot(index="candidate", columns="segment", values=metric)
        pivot = pivot.rename(columns={segment: f"{metric}_{segment}" for segment in pivot.columns})
        wide = wide.join(pivot)
    wide = wide.reset_index()
    baseline = wide.loc[wide["candidate"] == "full_entry_1.00"].iloc[0]
    for segment in WINDOW_NAMES.values():
        wide[f"ann_return_delta_vs_full_{segment}"] = wide[f"ann_return_{segment}"] - baseline[f"ann_return_{segment}"]
        wide[f"max_dd_delta_vs_full_{segment}"] = wide[f"max_dd_{segment}"] - baseline[f"max_dd_{segment}"]
    wide["decision_hint"] = "staged_entry_ablation"
    wide["stability_label"] = "pending_review"
    wide.to_csv(RUN_DIR / "window_metrics.csv", index=False)

    baseline_old = prior_daily.reset_index()
    baseline_new = curves[1.0].reset_index()
    parity_rows = []
    for check, old, new in (
        ("baseline_vs_prior", baseline_old, baseline_new),
        ("cached_half_vs_exact", curves[0.50].reset_index(), exact_half.reset_index()),
    ):
        for metric in ("return", "nav", "turnover", "holding_fraction"):
            parity_rows.append({
                "check": check,
                "metric": metric,
                "max_abs_diff": float(np.max(np.abs(old[metric].to_numpy(float) - new[metric].to_numpy(float)))),
            })
    parity = pd.DataFrame(parity_rows)
    parity.to_csv(RUN_DIR / "parity_checks.csv", index=False)
    max_parity_diff = float(parity["max_abs_diff"].max())
    if max_parity_diff > 1e-12:
        raise RuntimeError(f"Parity failed: max abs diff={max_parity_diff:.3e}")

    daily_dir = RUN_DIR / "daily_outputs"
    daily_dir.mkdir(exist_ok=True)
    for fraction, curve in curves.items():
        curve.to_csv(daily_dir / f"{label_for(fraction)}.csv.gz", index_label="date", compression="gzip")

    meta_path = RUN_DIR / "scan_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["data_snapshot"] = {
        "source_run": SOURCE_DIR.name,
        "price_snapshot": str(price_path),
        "start": prices.index.min().date().isoformat(),
        "end": prices.index.max().date().isoformat(),
        "rows": int(len(prices)),
        "adjustment": "qfq/front-adjusted",
    }
    meta["parity_check"] = {"max_abs_diff": max_parity_diff, "passed": True}
    meta["elapsed_sec"] = round(time.perf_counter() - started, 3)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "candidates": len(FRACTIONS),
        "rows": len(prices),
        "end": common_last.date().isoformat(),
        "elapsed_sec": meta["elapsed_sec"],
        "max_parity_diff": max_parity_diff,
    }))


if __name__ == "__main__":
    main()
