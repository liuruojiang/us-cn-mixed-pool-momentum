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
TARGET_VOLS: tuple[float | None, ...] = (
    None,
    0.05,
    0.075,
    0.10,
    0.125,
    0.15,
    0.175,
    0.20,
    0.225,
    0.25,
    0.275,
    0.30,
    0.35,
    0.40,
    0.45,
    0.50,
    0.60,
    0.75,
    1.00,
)
VOL_WINDOW = subd.DEFAULT_VOL_WINDOW
MAX_LEV = subd.DEFAULT_MAX_LEV
WINDOWS = {
    "full_sample": "full",
    "10Y": "last_10y",
    "5Y": "last_5y",
    "3Y": "last_3y",
    "1Y": "last_1y",
}


def label(target_vol: float | None) -> str:
    return "target_vol_off" if target_vol is None else f"target_vol_{target_vol:.3f}"


def metrics(curve: pd.DataFrame, start: pd.Timestamp) -> dict[str, object]:
    frame = curve.loc[curve.index >= start].copy()
    ret = v11._daily_returns_for_window(frame)
    wealth = v11._wealth_from_returns(ret)
    std = float(ret.std(ddof=0))
    exposure_col = "exposure_effective" if "exposure_effective" in frame else "fraction_before"
    exposure = frame[exposure_col].astype(float).fillna(0.0)
    if "target_vol_scale_effective" in frame:
        scale = frame["target_vol_scale_effective"].astype(float).fillna(1.0)
        next_scale = frame["target_vol_scale_next"].astype(float).fillna(1.0)
        scale_rebalances = int(next_scale.diff().abs().fillna(0.0).gt(1e-12).sum())
    else:
        scale = pd.Series(1.0, index=frame.index, dtype=float)
        scale_rebalances = 0
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
        "leverage_day_ratio": float(exposure.gt(1.0 + 1e-12).mean()),
        "delevered_holding_day_ratio": float((exposure.gt(1e-12) & exposure.lt(1.0 - 1e-12)).mean()),
        "avg_scale": float(scale.mean()),
        "max_scale": float(scale.max()),
        "scale_cap_day_ratio": float(scale.ge(MAX_LEV - 1e-12).mean()),
        "scale_rebalances": scale_rebalances,
        "avg_turnover": float(frame["turnover"].astype(float).mean()),
        "turnover_total": float(frame["turnover"].astype(float).sum()),
        "cost_total": float(frame["cost"].astype(float).sum()),
    }


def max_abs_diff(left: pd.Series, right: pd.Series) -> float:
    return float(np.max(np.abs(left.to_numpy(dtype=float) - right.to_numpy(dtype=float))))


def main() -> None:
    started = time.perf_counter()
    prices = pd.read_csv(SOURCE_DIR / "price_snapshot_qfq.csv.gz", parse_dates=["date"]).set_index("date")
    prices = prices[list(subd.ASSETS)].astype(float)
    base = pd.read_csv(BASE_DIR / "daily_outputs" / "full_entry_1.00.csv.gz", parse_dates=["date"]).set_index("date")
    flag_names = {f"price_ffill_{code}": code for code in subd.ASSETS}
    flags = base[list(flag_names)].rename(columns=flag_names).astype(bool).reindex(prices.index).fillna(False)
    prices.attrs["price_ffill_flags"] = flags
    end = pd.Timestamp(prices.index.max())
    perf_windows = v11.build_performance_windows(prices.index, end, v11.EVAL_START)

    curves: dict[float | None, pd.DataFrame] = {None: base.copy()}
    rows: list[dict[str, object]] = []
    for target_vol in TARGET_VOLS[1:]:
        curves[target_vol] = v11.apply_target_vol_overlay(
            base,
            target_vol,
            VOL_WINDOW,
            MAX_LEV,
            v11.ONE_WAY_COST,
            price_ffill_flags=flags,
        )

    for target_vol, curve in curves.items():
        for source_window, segment in WINDOWS.items():
            row = metrics(curve, perf_windows[source_window])
            row.update(
                {
                    "candidate": label(target_vol),
                    "segment": segment,
                    "target_vol": "off" if target_vol is None else target_vol,
                    "vol_window": VOL_WINDOW,
                    "max_lev": MAX_LEV,
                    "scale_rebalance_threshold": v11.TARGET_VOL_SCALE_REBALANCE_THRESHOLD,
                }
            )
            rows.append(row)

    long = pd.DataFrame(rows)
    long.to_csv(RUN_DIR / "scan_summary.csv", index=False)
    wide = long[
        ["candidate", "target_vol", "vol_window", "max_lev", "scale_rebalance_threshold"]
    ].drop_duplicates().set_index("candidate")
    metric_names = (
        "ann_return",
        "ann_vol",
        "sharpe_repo",
        "max_dd",
        "avg_weight",
        "holding_day_ratio",
        "leverage_day_ratio",
        "delevered_holding_day_ratio",
        "avg_scale",
        "max_scale",
        "scale_cap_day_ratio",
        "scale_rebalances",
        "avg_turnover",
        "cost_total",
    )
    for name in metric_names:
        pivot = long.pivot(index="candidate", columns="segment", values=name)
        pivot = pivot.rename(columns=lambda segment: f"{name}_{segment}")
        wide = wide.join(pivot)
    wide = wide.reset_index()
    off = wide.loc[wide.candidate == "target_vol_off"].iloc[0]
    for segment in WINDOWS.values():
        wide[f"ann_return_delta_vs_off_{segment}"] = wide[f"ann_return_{segment}"] - off[f"ann_return_{segment}"]
        wide[f"max_dd_delta_vs_off_{segment}"] = wide[f"max_dd_{segment}"] - off[f"max_dd_{segment}"]
        wide[f"ann_vol_delta_vs_off_{segment}"] = wide[f"ann_vol_{segment}"] - off[f"ann_vol_{segment}"]
    wide["decision_hint"] = "target_vol_level_scan"
    wide["stability_label"] = "pending_review"
    wide.to_csv(RUN_DIR / "window_metrics.csv", index=False)

    parity_rows: list[dict[str, object]] = []
    off = curves[None]
    for name, base_name in (
        ("return", "return"),
        ("nav", "nav"),
        ("turnover", "turnover"),
        ("fraction_before", "fraction_before"),
    ):
        parity_rows.append(
            {
                "check": "target_vol_off_vs_pure_base",
                "metric": name,
                "max_abs_diff": max_abs_diff(off[name], base[base_name]),
            }
        )

    current = curves[v11.TARGET_VOL]
    poe_current = poe.apply_target_vol_overlay(
        base,
        v11.TARGET_VOL,
        VOL_WINDOW,
        MAX_LEV,
        v11.ONE_WAY_COST,
        price_ffill_flags=flags,
    )
    for name in ("return", "nav", "turnover", "exposure_effective", "target_vol_scale_next"):
        parity_rows.append(
            {
                "check": "target_vol_0.25_runner_vs_poe",
                "metric": name,
                "max_abs_diff": max_abs_diff(current[name], poe_current[name]),
            }
        )
    parity = pd.DataFrame(parity_rows)
    parity.to_csv(RUN_DIR / "parity_checks.csv", index=False)
    nav_diff = float(parity.loc[parity.metric == "nav", "max_abs_diff"].max())
    other_diff = float(parity.loc[parity.metric != "nav", "max_abs_diff"].max())
    if nav_diff > 1e-10 or other_diff > 1e-12:
        raise RuntimeError(f"Parity failed: nav={nav_diff:.3e}, other={other_diff:.3e}")

    daily_dir = RUN_DIR / "daily_outputs"
    daily_dir.mkdir(exist_ok=True)
    for target_vol, curve in curves.items():
        curve.to_csv(daily_dir / f"{label(target_vol)}.csv.gz", index_label="date", compression="gzip")

    meta_path = RUN_DIR / "scan_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["data_snapshot"] = {
        "source_run": SOURCE_DIR.name,
        "base_run": BASE_DIR.name,
        "start": prices.index.min().date().isoformat(),
        "end": end.date().isoformat(),
        "rows": len(prices),
        "adjustment": "qfq/front-adjusted",
    }
    meta["parity_check"] = {
        "off_vs_pure_base_and_current_runner_vs_poe_nav_max_abs_diff": nav_diff,
        "other_max_abs_diff": other_diff,
        "passed": True,
    }
    meta["elapsed_sec"] = round(time.perf_counter() - started, 3)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "candidates": len(TARGET_VOLS),
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
