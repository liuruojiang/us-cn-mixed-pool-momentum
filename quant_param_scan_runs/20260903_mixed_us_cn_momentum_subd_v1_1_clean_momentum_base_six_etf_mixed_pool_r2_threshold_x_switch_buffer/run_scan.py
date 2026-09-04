from __future__ import annotations

import hashlib
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
R2_GRID: tuple[float | None, ...] = (None, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50)
BUFFER_GRID = (1.00, 1.02, 1.03, 1.05, 1.08, 1.10, 1.15, 1.20)
WINDOW_NAMES = {
    "full_sample": "full",
    "10Y": "last_10y",
    "5Y": "last_5y",
    "3Y": "last_3y",
    "1Y": "last_1y",
}


def candidate_name(r2_threshold: float | None, switch_buffer: float) -> str:
    r2 = "off" if r2_threshold is None else f"{r2_threshold:.2f}"
    return f"r2_{r2}_buffer_{switch_buffer:.2f}"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        "buffer_blocked_days": int(sub["buffer_blocked"].astype(bool).sum()),
    }


def main() -> None:
    started = time.perf_counter()
    config = subd.RunConfig(
        source="akshare_em_qfq",
        one_way_cost=v11.ONE_WAY_COST,
        start_date=v11.START_DATE,
        end_date=pd.Timestamp.today().normalize(),
        output_tag="r2_switch_buffer_clean_base_scan",
        target_vols=(),
        vol_window=subd.DEFAULT_VOL_WINDOW,
        max_lev=1.0,
    )
    prices, sources = poe.load_close(config)
    prices = prices.loc[prices.index >= config.start_date].copy()
    raw_last_by_asset = {
        code: pd.Timestamp(prices.index[prices[code].notna()].max()).normalize()
        for code in subd.ASSETS
    }
    matched_raw_end = min(raw_last_by_asset.values())
    prices = prices.loc[:matched_raw_end].copy()
    prices, common_last, last_by_asset = v11.align_prices_to_common_valid_date(
        prices,
        list(subd.ASSETS),
        calendar_validation_mode="required",
    )
    windows = v11.build_performance_windows(prices.index, common_last, v11.EVAL_START)

    price_path = RUN_DIR / "price_snapshot_qfq.csv.gz"
    prices.to_csv(price_path, index_label="date", compression="gzip")
    sources.to_csv(RUN_DIR / "source_snapshot.csv", index=False)

    full_entry = v11.EntryCase("full_entry_clean_base", "full_entry", 1.0)
    scan_rows: list[dict[str, object]] = []
    daily_dir = RUN_DIR / "daily_outputs"
    daily_dir.mkdir(exist_ok=True)
    saved_daily = {
        (None, 1.00),
        (0.20, 1.00),
        (None, 1.05),
        (0.20, 1.05),
    }
    current_pair_curve: pd.DataFrame | None = None

    for r2_threshold in R2_GRID:
        for switch_buffer in BUFFER_GRID:
            label = candidate_name(r2_threshold, switch_buffer)
            curve = v11.run_staged_entry(
                prices,
                config,
                full_entry,
                r2_threshold,
                switch_buffer,
            )
            if r2_threshold == 0.20 and switch_buffer == 1.05:
                current_pair_curve = curve.copy()
            if (r2_threshold, switch_buffer) in saved_daily:
                curve.to_csv(daily_dir / f"{label}.csv.gz", index_label="date", compression="gzip")
            for source_name, segment in WINDOW_NAMES.items():
                row = metrics_for(curve, windows[source_name])
                row.update(
                    {
                        "candidate": label,
                        "segment": segment,
                        "r2_threshold": "off" if r2_threshold is None else r2_threshold,
                        "switch_buffer": switch_buffer,
                        "r2_enabled": r2_threshold is not None,
                        "buffer_enabled": switch_buffer > 1.0,
                    }
                )
                scan_rows.append(row)

    if current_pair_curve is None:
        raise RuntimeError("Current stripped pair was not included in the scan")

    flags = v11._price_ffill_flags_for_prices(prices, list(subd.ASSETS))
    poe_curve = poe.run_staged_entry(
        prices,
        config,
        poe.EntryCase("full_entry_clean_base", "full_entry", 1.0),
        0.20,
        1.05,
        price_ffill_flags=flags,
    )
    parity = pd.DataFrame(
        {
            "date": current_pair_curve.index,
            "runner_return": current_pair_curve["return"].to_numpy(),
            "poe_return": poe_curve["return"].to_numpy(),
            "runner_nav": current_pair_curve["nav"].to_numpy(),
            "poe_nav": poe_curve["nav"].to_numpy(),
        }
    )
    parity["abs_return_diff"] = (parity["runner_return"] - parity["poe_return"]).abs()
    parity["abs_nav_diff"] = (parity["runner_nav"] - parity["poe_nav"]).abs()
    parity.to_csv(RUN_DIR / "parity_checks.csv", index=False)
    max_return_diff = float(parity["abs_return_diff"].max())
    max_nav_diff = float(parity["abs_nav_diff"].max())
    if max_return_diff > 1e-12 or max_nav_diff > 1e-10:
        raise RuntimeError(
            f"Runner/Poe parity failed: return={max_return_diff:.3e}, nav={max_nav_diff:.3e}"
        )

    long = pd.DataFrame(scan_rows)
    ordered_columns = [
        "candidate", "segment", "r2_threshold", "switch_buffer", "r2_enabled", "buffer_enabled",
        "start", "end", "rows", "ann_return", "ann_vol", "sharpe_repo", "max_dd",
        "avg_weight", "held_day_avg_weight", "holding_days", "holding_day_ratio",
        "avg_turnover", "turnover_total", "cost_total", "trade_days", "buffer_blocked_days",
    ]
    long = long[ordered_columns].sort_values(["r2_enabled", "r2_threshold", "switch_buffer", "segment"])
    long.to_csv(RUN_DIR / "scan_summary.csv", index=False)

    params = long[["candidate", "r2_threshold", "switch_buffer", "r2_enabled", "buffer_enabled"]].drop_duplicates()
    wide = params.set_index("candidate")
    for metric in ("ann_return", "ann_vol", "sharpe_repo", "max_dd", "avg_turnover", "holding_day_ratio", "cost_total"):
        pivot = long.pivot(index="candidate", columns="segment", values=metric)
        pivot = pivot.rename(columns={segment: f"{metric}_{segment}" for segment in pivot.columns})
        wide = wide.join(pivot)
    wide = wide.reset_index()
    base = wide.loc[wide["candidate"] == candidate_name(None, 1.00)].iloc[0]
    current = wide.loc[wide["candidate"] == candidate_name(0.20, 1.05)].iloc[0]
    for segment in WINDOW_NAMES.values():
        wide[f"ann_return_delta_vs_base_{segment}"] = wide[f"ann_return_{segment}"] - base[f"ann_return_{segment}"]
        wide[f"max_dd_delta_vs_base_{segment}"] = wide[f"max_dd_{segment}"] - base[f"max_dd_{segment}"]
        wide[f"ann_return_delta_vs_current_pair_{segment}"] = wide[f"ann_return_{segment}"] - current[f"ann_return_{segment}"]
    wide["decision_hint"] = "research_only"
    wide["stability_label"] = "pending_review"
    wide = wide.sort_values(["r2_enabled", "r2_threshold", "switch_buffer"])
    wide.to_csv(RUN_DIR / "window_metrics.csv", index=False)

    meta_path = RUN_DIR / "scan_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["data_snapshot"] = {
        "raw_data_start": prices.index.min().date().isoformat(),
        "raw_data_end": prices.index.max().date().isoformat(),
        "rows": int(len(prices)),
        "assets": list(subd.ASSETS),
        "adjustment": "qfq/front-adjusted",
        "trading_calendar": "China trading-day calendar required",
        "last_by_asset": {code: value.date().isoformat() for code, value in last_by_asset.items()},
        "raw_last_by_asset_before_matched_clip": {
            code: value.date().isoformat() for code, value in raw_last_by_asset.items()
        },
        "matched_raw_end": matched_raw_end.date().isoformat(),
        "price_snapshot": str(price_path.relative_to(RUN_DIR.parent.parent)),
        "price_snapshot_sha256": file_sha256(price_path),
    }
    meta["parity_check"] = {
        "candidate": candidate_name(0.20, 1.05),
        "runner_vs_poe_max_abs_return_diff": max_return_diff,
        "runner_vs_poe_max_abs_nav_diff": max_nav_diff,
        "passed": True,
    }
    meta["elapsed_sec"] = round(time.perf_counter() - started, 3)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "rows": len(prices),
                "start": prices.index.min().date().isoformat(),
                "end": common_last.date().isoformat(),
                "candidates": len(wide),
                "elapsed_sec": meta["elapsed_sec"],
                "max_parity_return_diff": max_return_diff,
                "max_parity_nav_diff": max_nav_diff,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
