"""Research-only LOOKBACK sweep on the verified six-ETF V1.3 paper account."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
RUN = Path(__file__).resolve().parent
L1 = ROOT / "outputs/recert_l1_20260926"
L2 = ROOT / "outputs/recert_l2_20260926"
OLD = ROOT / "quant_param_scan_runs/20260926_six_etf_v1_3_l6_parameter_basis_20260924"
BOT = ROOT / "poe_subd_six_etf_v1_3_bot.py"
VALUES = tuple(range(5, 100, 2))
WINDOWS = (("full", None), ("last_10y", 2520), ("last_5y", 1260),
           ("last_3y", 756), ("last_1y", 252))
ALL_SCOREABLE = pd.Timestamp("2020-01-09")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    manifest = json.loads((L1 / "capture_manifest.json").read_text(encoding="utf-8"))
    for key in ("aligned", "flags"):
        if sha(manifest[key]["path"]) != manifest[key]["sha256"]:
            raise RuntimeError(f"L1 {key} hash mismatch")
    prices = pd.read_csv(manifest["aligned"]["path"], parse_dates=["date"]).set_index("date")
    flags = pd.read_csv(manifest["flags"]["path"], parse_dates=["date"]).set_index("date").astype(bool)
    if len(prices) != 3594 or prices.index[-1] != pd.Timestamp("2026-09-24") or not prices.index.equals(flags.index):
        raise RuntimeError("L1 price/flag coverage mismatch")

    bot = load_module("six_etf_v13_lookback_grid", BOT)
    helper = load_module("six_etf_v13_l6_helpers", OLD / "run_l6_scan.py")
    if (bot.LOOKBACK, bot.SCORE_MIN, bot.SCORE_MAX, bot.R2_THRESHOLD,
        bot.SWITCH_BUFFER, bot.ONE_WAY_COST) != (25, .5, 5.5, .25, 1., .001):
        raise RuntimeError("Formal constants changed")
    config = bot._build_config(end_date=pd.Timestamp("2026-09-24"))
    original_score = bot.weighted_slope_score_and_r2
    out = RUN / "daily_outputs"
    out.mkdir(exist_ok=True)

    baseline = helper.run_one(bot, prices, flags, config,
                              {"group": "lookback", "value": "25"}, original_score)
    official = pd.read_csv(L2 / "formal_daily_20260924.csv.gz", parse_dates=["date"])
    parity = helper.assert_same_path(baseline, official, "formal_vs_L2")
    old25 = pd.read_csv(OLD / "daily_outputs/formal_v1_3.csv.gz", parse_dates=["date"])
    helper.assert_same_path(baseline, old25, "formal_vs_L6")
    print("25-day formal parity PASS", flush=True)

    long_rows, wide_rows, event_rows, overlap = [], [], [], []
    for i, value in enumerate(VALUES, 1):
        candidate = f"lookback_{value}"
        curve = baseline if value == 25 else helper.run_one(
            bot, prices, flags, config, {"group": "lookback", "value": str(value)}, original_score)
        if not pd.DatetimeIndex(curve.date).equals(pd.DatetimeIndex(baseline.date)):
            raise RuntimeError(f"Date mismatch: {candidate}")
        if not (np.isfinite(curve.nav.to_numpy(float)).all() and (curve.nav > 0).all()):
            raise RuntimeError(f"Invalid NAV: {candidate}")
        if not (curve.holding_fraction.between(0, 1).all() and curve.fraction_before.between(0, 1).all()):
            raise RuntimeError(f"Invalid exposure: {candidate}")
        path = out / f"{candidate}.csv.gz"
        curve.to_csv(path, index=False, compression="gzip", float_format="%.16g")
        if value in (23, 25, 27, 29):
            old_path = OLD / "daily_outputs" / ("formal_v1_3.csv.gz" if value == 25 else f"{candidate}.csv.gz")
            overlap.append(helper.assert_same_path(curve, pd.read_csv(old_path, parse_dates=["date"]),
                                                   f"{candidate}_vs_L6"))

        sub = []
        for segment, n in WINDOWS:
            start = None if n is None else pd.Timestamp(curve.date.iloc[-n])
            row = helper.metrics(curve, candidate, "lookback", str(value),
                                 "formal" if value == 25 else "candidate", segment, start)
            row["LOOKBACK"] = value
            sub.append(row)
            long_rows.append(row)
        common = helper.metrics(curve, candidate, "lookback", str(value),
                                "formal" if value == 25 else "candidate",
                                "six_etf_all_scoreable", ALL_SCOREABLE)
        common["LOOKBACK"] = value
        long_rows.append(common)
        by_window = {row["segment"]: row for row in sub}
        wide = {"candidate": candidate, "LOOKBACK": value, "role": "formal" if value == 25 else "candidate"}
        for segment, _ in WINDOWS:
            row = by_window[segment]
            wide[f"ann_return_{segment}"] = row["ann_return"]
            wide[f"max_dd_{segment}"] = row["max_dd"]
            wide[f"sharpe_repo_{segment}"] = row["sharpe_repo"]
        wide.update(end_nav_full=by_window["full"]["end_nav"],
                    trade_days_full=by_window["full"]["trade_days"],
                    turnover_total_full=by_window["full"]["turnover_total"],
                    ann_return_six_etf_all_scoreable=common["ann_return"],
                    max_dd_six_etf_all_scoreable=common["max_dd"])
        wide_rows.append(wide)
        pos_diff = curve.position.fillna("<NA>").astype(str).to_numpy() != baseline.position.fillna("<NA>").astype(str).to_numpy()
        event_rows.append({"candidate": candidate, "LOOKBACK": value,
                           "position_diff_days": int(pos_diff.sum()),
                           "first_position_diff": str(curve.date.iloc[np.flatnonzero(pos_diff)[0]].date()) if pos_diff.any() else "",
                           "daily_path": str(path.relative_to(ROOT)), "daily_sha256": sha(path)})
        print(f"{i:02d}/{len(VALUES)} {candidate} full_ann={wide['ann_return_full']:.4%} full_dd={wide['max_dd_full']:.4%}", flush=True)

    summary = pd.DataFrame(long_rows)
    wide = pd.DataFrame(wide_rows)
    base = summary.loc[summary.candidate == "lookback_25"].set_index("segment")
    for field in ("ann_return", "max_dd", "trade_days", "turnover_total", "cash_days"):
        summary[f"formal_{field}"] = summary.segment.map(base[field])
    summary["delta_ann_pp"] = (summary.ann_return - summary.formal_ann_return) * 100
    summary["dd_improvement_pp"] = (summary.max_dd - summary.formal_max_dd) * 100
    for segment, _ in WINDOWS:
        wide[f"delta_ann_pp_{segment}"] = (wide[f"ann_return_{segment}"] - wide.loc[wide.LOOKBACK == 25, f"ann_return_{segment}"].iloc[0]) * 100
        wide[f"dd_improvement_pp_{segment}"] = (wide[f"max_dd_{segment}"] - wide.loc[wide.LOOKBACK == 25, f"max_dd_{segment}"].iloc[0]) * 100
    summary.to_csv(RUN / "scan_summary.csv", index=False)
    wide.to_csv(RUN / "window_metrics.csv", index=False)
    pd.DataFrame(event_rows).to_csv(RUN / "candidate_event_counts.csv", index=False)
    (RUN / "parity_checks.json").write_text(json.dumps({"formal_vs_L2": parity,
        "overlap_vs_L6": overlap, "formal_code_sha256": sha(BOT),
        "price_sha256": sha(manifest["aligned"]["path"]),
        "flags_sha256": sha(manifest["flags"]["path"]),
        "candidate_count": len(VALUES)}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"COMPLETE {len(VALUES)} candidates, {len(summary)} window rows", flush=True)


if __name__ == "__main__":
    main()
