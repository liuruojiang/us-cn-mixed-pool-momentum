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

import poe_subd_six_etf_v1_1_bot as poe
import research_subd_six_etf_weighted_slope as subd
import run_subd_six_etf_v1_1 as v11


RUN_DIR = Path(__file__).resolve().parent
SOURCE_DIR = RUN_DIR.parent / "20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer"
BASE_DIR = RUN_DIR.parent / "20260903_mixed_us_cn_momentum_subd_pure_momentum_base_plus_staged_entry_six_etf_mixed_pool_initial_entry_fraction_r2_off"
LOOKBACKS = tuple(range(10, 51))
WINDOWS = {
    "full_sample": "full",
    "10Y": "last_10y",
    "5Y": "last_5y",
    "3Y": "last_3y",
    "1Y": "last_1y",
}


def label(lookback: int) -> str:
    return f"lookback_{lookback:03d}"


def metrics(curve: pd.DataFrame, start: pd.Timestamp) -> dict[str, object]:
    frame = curve.loc[curve.index >= start].copy()
    ret = v11._daily_returns_for_window(frame)
    wealth = v11._wealth_from_returns(ret)
    std = float(ret.std(ddof=0))
    exposure = frame["fraction_before"].astype(float).fillna(0.0)
    turnover = frame["turnover"].astype(float).fillna(0.0)
    return {
        "start": frame.index[0].date().isoformat(),
        "end": frame.index[-1].date().isoformat(),
        "rows": len(frame),
        "ann_return": float(wealth.iloc[-1] ** (subd.TRADING_DAYS / len(frame)) - 1.0),
        "ann_vol": std * math.sqrt(subd.TRADING_DAYS),
        "sharpe_repo": float(ret.mean() / std * math.sqrt(subd.TRADING_DAYS)) if std else 0.0,
        "max_dd": float(subd.max_drawdown(wealth)),
        "avg_weight": float(exposure.mean()),
        "holding_day_ratio": float(exposure.gt(1e-12).mean()),
        "cash_days": int(exposure.le(1e-12).sum()),
        "trade_days": int(turnover.gt(1e-12).sum()),
        "avg_turnover": float(turnover.mean()),
        "turnover_total": float(turnover.sum()),
        "cost_total": float(frame["cost"].astype(float).sum()),
    }


def max_abs_numeric(left: pd.Series, right: pd.Series) -> float:
    return float(np.max(np.abs(left.to_numpy(dtype=float) - right.to_numpy(dtype=float))))


def main() -> None:
    started = time.perf_counter()
    prices = pd.read_csv(SOURCE_DIR / "price_snapshot_qfq.csv.gz", parse_dates=["date"]).set_index("date")
    prices = prices[list(subd.ASSETS)].astype(float)
    accepted = pd.read_csv(BASE_DIR / "daily_outputs" / "full_entry_1.00.csv.gz", parse_dates=["date"]).set_index("date")
    flag_names = {f"price_ffill_{code}": code for code in subd.ASSETS}
    flags = accepted[list(flag_names)].rename(columns=flag_names).astype(bool).reindex(prices.index).fillna(False)
    prices.attrs["price_ffill_flags"] = flags
    end = pd.Timestamp(prices.index.max())
    windows = v11.build_performance_windows(prices.index, end, v11.EVAL_START)
    config = subd.RunConfig(
        source="akshare_em_qfq",
        one_way_cost=v11.ONE_WAY_COST,
        start_date=pd.Timestamp(prices.index.min()),
        end_date=end,
        output_tag="lookback_pure_momentum_scan",
        target_vols=(),
        vol_window=subd.DEFAULT_VOL_WINDOW,
        max_lev=1.0,
    )

    curves: dict[int, pd.DataFrame] = {}
    rows: list[dict[str, object]] = []
    daily_dir = RUN_DIR / "daily_outputs"
    daily_dir.mkdir(exist_ok=True)
    original_lookback = subd.LOOKBACK
    try:
        for lookback in LOOKBACKS:
            daily_path = daily_dir / f"{label(lookback)}.csv.gz"
            if daily_path.exists():
                curve = pd.read_csv(daily_path, parse_dates=["date"]).set_index("date")
            else:
                subd.LOOKBACK = lookback
                curve = v11.run_staged_entry(
                    prices,
                    config,
                    v11.EntryCase(label(lookback), "full_entry", 1.0),
                    None,
                    1.0,
                )
                curve.to_csv(daily_path, index_label="date", compression="gzip")
            curves[lookback] = curve
            for source_window, segment in WINDOWS.items():
                row = metrics(curve, windows[source_window])
                row.update(
                    {
                        "candidate": label(lookback),
                        "segment": segment,
                        "lookback": lookback,
                        "r2": "off",
                        "switch_buffer": 1.0,
                        "initial_entry_fraction": 1.0,
                        "overheat": "off",
                        "target_vol": "off",
                    }
                )
                rows.append(row)
    finally:
        subd.LOOKBACK = original_lookback

    long = pd.DataFrame(rows)
    long.to_csv(RUN_DIR / "scan_summary.csv", index=False)
    wide = long[["candidate", "lookback"]].drop_duplicates().set_index("candidate")
    for name in (
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
    ):
        pivot = long.pivot(index="candidate", columns="segment", values=name)
        wide = wide.join(pivot.rename(columns=lambda segment: f"{name}_{segment}"))
    wide = wide.reset_index()
    current = wide.loc[wide.lookback == 25].iloc[0]
    for segment in WINDOWS.values():
        wide[f"ann_return_delta_vs_current_{segment}"] = wide[f"ann_return_{segment}"] - current[f"ann_return_{segment}"]
        wide[f"max_dd_delta_vs_current_{segment}"] = wide[f"max_dd_{segment}"] - current[f"max_dd_{segment}"]
    wide["decision_hint"] = "lookback_scan"
    wide["stability_label"] = "pending_review"
    wide.to_csv(RUN_DIR / "window_metrics.csv", index=False)

    parity_rows: list[dict[str, object]] = []
    current_curve = curves[25]
    for name in ("return", "nav", "turnover", "fraction_before"):
        parity_rows.append(
            {
                "check": "lookback_25_vs_accepted_pure_base",
                "metric": name,
                "max_abs_diff": max_abs_numeric(current_curve[name], accepted[name]),
            }
        )
    parity_rows.append(
        {
            "check": "lookback_25_vs_accepted_pure_base",
            "metric": "position",
            "max_abs_diff": float((current_curve["position"].astype(str) != accepted["position"].astype(str)).sum()),
        }
    )

    original_poe_lookback = poe.LOOKBACK
    try:
        poe.LOOKBACK = 25
        poe_curve = poe.run_staged_entry(
            prices,
            config,
            poe.EntryCase("lookback_025", "full_entry", 1.0),
            None,
            1.0,
            price_ffill_flags=flags,
        )
    finally:
        poe.LOOKBACK = original_poe_lookback
    for name in ("return", "nav", "turnover", "fraction_before"):
        parity_rows.append(
            {
                "check": "lookback_25_runner_vs_poe",
                "metric": name,
                "max_abs_diff": max_abs_numeric(current_curve[name], poe_curve[name]),
            }
        )
    parity_rows.append(
        {
            "check": "lookback_25_runner_vs_poe",
            "metric": "position",
            "max_abs_diff": float((current_curve["position"].astype(str) != poe_curve["position"].astype(str)).sum()),
        }
    )
    parity = pd.DataFrame(parity_rows)
    parity.to_csv(RUN_DIR / "parity_checks.csv", index=False)
    nav_diff = float(parity.loc[parity.metric == "nav", "max_abs_diff"].max())
    other_diff = float(parity.loc[parity.metric != "nav", "max_abs_diff"].max())
    if nav_diff > 1e-10 or other_diff > 1e-12:
        raise RuntimeError(f"Parity failed: nav={nav_diff:.3e}, other={other_diff:.3e}")

    for lookback, curve in curves.items():
        curve.to_csv(daily_dir / f"{label(lookback)}.csv.gz", index_label="date", compression="gzip")

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
        "current_25_vs_accepted_base_and_runner_vs_poe_nav_max_abs_diff": nav_diff,
        "other_max_abs_diff": other_diff,
        "passed": True,
    }
    meta["elapsed_sec"] = round(time.perf_counter() - started, 3)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "candidates": len(LOOKBACKS),
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
