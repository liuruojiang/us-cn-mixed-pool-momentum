from __future__ import annotations

import importlib.util
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd


RUN_DIR = Path(__file__).resolve().parent
REPO_ROOT = RUN_DIR.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import poe_subd_six_etf_v1_1_bot as poe
import research_subd_six_etf_weighted_slope as subd
import run_subd_six_etf_v1_1 as v11


SOURCE_DIR = RUN_DIR.parent / "20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer"
BASE_DIR = RUN_DIR.parent / "20260904_mixed_us_cn_momentum_subd_pure_momentum_core_six_etf_mixed_pool_score_min_absolute_momentum_floor"
HELPER_PATH = RUN_DIR.parent / "20260903_mixed_us_cn_momentum_subd_pure_momentum_core_six_etf_mixed_pool_lookback" / "run_scan.py"
CAPS = (2.0, 3.0, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 8.0, 10.0, math.inf)
WINDOWS = {
    "full_sample": "full",
    "10Y": "last_10y",
    "5Y": "last_5y",
    "3Y": "last_3y",
    "1Y": "last_1y",
}


def load_helpers():
    spec = importlib.util.spec_from_file_location("subd_lookback_scan_helpers", HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load scan helpers: {HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cap_label(cap: float) -> str:
    return "inf" if math.isinf(cap) else f"{cap:g}"


def candidate_label(cap: float) -> str:
    return f"score_max_{cap_label(cap).replace('.', 'p')}"


def main() -> None:
    started = time.perf_counter()
    helpers = load_helpers()
    prices = pd.read_csv(SOURCE_DIR / "price_snapshot_qfq.csv.gz", parse_dates=["date"]).set_index("date")
    prices = prices[list(subd.ASSETS)].astype(float)
    accepted = pd.read_csv(BASE_DIR / "daily_outputs" / "score_min_-inf.csv.gz", parse_dates=["date"]).set_index("date")
    flag_names = {f"price_ffill_{code}": code for code in subd.ASSETS}
    flags = accepted[list(flag_names)].rename(columns=flag_names).astype(bool).reindex(prices.index).fillna(False)
    prices.attrs["price_ffill_flags"] = flags
    assert prices.index.equals(accepted.index)
    assert len(prices) == 3578 and prices.index.is_unique and prices.index.is_monotonic_increasing
    end = pd.Timestamp(prices.index.max())
    windows = v11.build_performance_windows(prices.index, end, v11.EVAL_START)
    config = subd.RunConfig(
        source="akshare_em_qfq",
        one_way_cost=v11.ONE_WAY_COST,
        start_date=pd.Timestamp(prices.index.min()),
        end_date=end,
        output_tag="no_floor_score_max_scan",
        target_vols=(),
        vol_window=subd.DEFAULT_VOL_WINDOW,
        max_lev=1.0,
    )

    curves: dict[float, pd.DataFrame] = {}
    rows: list[dict[str, object]] = []
    daily_dir = RUN_DIR / "daily_outputs"
    daily_dir.mkdir(exist_ok=True)
    original_score_min = subd.SCORE_MIN
    original_score_max = subd.SCORE_MAX
    try:
        subd.SCORE_MIN = -math.inf
        for cap in CAPS:
            subd.SCORE_MAX = cap
            name = candidate_label(cap)
            curve = v11.run_staged_entry(
                prices,
                config,
                v11.EntryCase(name, "full_entry", 1.0),
                None,
                1.0,
            )
            curves[cap] = curve
            print(f"Completed cap={cap_label(cap)}", flush=True)
            curve.to_csv(daily_dir / f"{name}.csv.gz", index_label="date", compression="gzip")
            for source_window, segment in WINDOWS.items():
                row = helpers.metrics(curve, windows[source_window])
                row.update(
                    {
                        "candidate": name,
                        "segment": segment,
                        "score_max": cap_label(cap),
                        "score_min": "-inf",
                        "lookback": 25,
                        "r2": "off",
                        "switch_buffer": 1.0,
                        "initial_entry_fraction": 1.0,
                        "overheat": "off",
                        "target_vol": "off",
                    }
                )
                rows.append(row)
    finally:
        subd.SCORE_MAX = original_score_max
        subd.SCORE_MIN = original_score_min

    long = pd.DataFrame(rows)
    long.to_csv(RUN_DIR / "scan_summary.csv", index=False)
    wide = long[["candidate", "score_max"]].drop_duplicates().set_index("candidate")
    metric_names = (
        "ann_return",
        "ann_vol",
        "sharpe_repo",
        "max_dd",
        "avg_weight",
        "holding_day_ratio",
        "cash_days",
        "trade_days",
        "avg_turnover",
        "cost_total",
    )
    for metric_name in metric_names:
        pivot = long.pivot(index="candidate", columns="segment", values=metric_name)
        wide = wide.join(pivot.rename(columns=lambda segment: f"{metric_name}_{segment}"))
    wide = wide.reset_index()
    baseline = wide.loc[wide.score_max == "5"].iloc[0]
    for segment in WINDOWS.values():
        wide[f"ann_return_delta_vs_current_{segment}"] = wide[f"ann_return_{segment}"] - baseline[f"ann_return_{segment}"]
        wide[f"max_dd_delta_vs_current_{segment}"] = wide[f"max_dd_{segment}"] - baseline[f"max_dd_{segment}"]
    wide["decision_hint"] = "score_max_scan"
    wide["stability_label"] = "pending_review"
    wide.to_csv(RUN_DIR / "window_metrics.csv", index=False)

    parity_rows: list[dict[str, object]] = []
    baseline_curve = curves[5.0]
    for metric_name in ("return", "nav", "turnover", "fraction_before"):
        parity_rows.append(
            {
                "check": "score_max_5_vs_accepted_pure_base",
                "metric": metric_name,
                "max_abs_diff": helpers.max_abs_numeric(baseline_curve[metric_name], accepted[metric_name]),
            }
        )
    parity_rows.append(
        {
            "check": "score_max_5_vs_accepted_pure_base",
            "metric": "position",
            "max_abs_diff": float((baseline_curve["position"].astype(str) != accepted["position"].astype(str)).sum()),
        }
    )

    original_poe_score_min = poe.SCORE_MIN
    original_poe_score_max = poe.SCORE_MAX
    try:
        poe.SCORE_MAX = 5.0
        poe.SCORE_MIN = -math.inf
        poe_curve = poe.run_staged_entry(
            prices,
            config,
            poe.EntryCase("score_max_5", "full_entry", 1.0),
            None,
            1.0,
            price_ffill_flags=flags,
        )
    finally:
        poe.SCORE_MAX = original_poe_score_max
        poe.SCORE_MIN = original_poe_score_min
    for metric_name in ("return", "nav", "turnover", "fraction_before"):
        parity_rows.append(
            {
                "check": "score_max_5_runner_vs_poe",
                "metric": metric_name,
                "max_abs_diff": helpers.max_abs_numeric(baseline_curve[metric_name], poe_curve[metric_name]),
            }
        )
    parity_rows.append(
        {
            "check": "score_max_5_runner_vs_poe",
            "metric": "position",
            "max_abs_diff": float((baseline_curve["position"].astype(str) != poe_curve["position"].astype(str)).sum()),
        }
    )
    parity = pd.DataFrame(parity_rows)
    parity.to_csv(RUN_DIR / "parity_checks.csv", index=False)
    nav_diff = float(parity.loc[parity.metric == "nav", "max_abs_diff"].max())
    other_diff = float(parity.loc[parity.metric != "nav", "max_abs_diff"].max())
    if nav_diff > 1e-10 or other_diff > 1e-12:
        raise RuntimeError(f"Parity failed: nav={nav_diff:.3e}, other={other_diff:.3e}")

    meta_path = RUN_DIR / "scan_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["data_snapshot"] = {
        "source_run": SOURCE_DIR.name,
        "accepted_base_run": BASE_DIR.name,
        "start": prices.index.min().date().isoformat(),
        "end": end.date().isoformat(),
        "rows": len(prices),
        "adjustment": "qfq/front-adjusted",
    }
    meta["parity_check"] = {
        "current_score_max_5_vs_accepted_base_and_runner_vs_poe_nav_max_abs_diff": nav_diff,
        "other_max_abs_diff": other_diff,
        "passed": True,
    }
    meta["elapsed_sec"] = round(time.perf_counter() - started, 3)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "candidates": len(CAPS),
                "rows": len(prices),
                "end": end.date().isoformat(),
                "elapsed_sec": meta["elapsed_sec"],
                "nav_diff": nav_diff,
                "other_diff": other_diff,
            }
        )
    )


if __name__ == "__main__":
    main()
