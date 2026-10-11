"""Run a research-only pure-momentum LOOKBACK sweep on the official ETF engine."""

import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
RUN = Path(__file__).resolve().parent
L1 = ROOT / "outputs/recert_l1_20260926"
L2 = ROOT / "outputs/recert_l2_20260926"
L6 = ROOT / "quant_param_scan_runs/20260926_six_etf_v1_3_l6_parameter_basis_20260924"
BOT = ROOT / "poe_subd_six_etf_v1_3_bot.py"
VALUES = tuple(range(5, 100, 2))
WINDOWS = (("full", None), ("last_10y", 2520), ("last_5y", 1260),
           ("last_3y", 756), ("last_1y", 252))
COMMON_START = pd.Timestamp("2020-01-09")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def pure_run(bot, prices, flags, config, lookback):
    original = (bot.LOOKBACK, bot.SCORE_MIN, bot.SCORE_MAX)
    try:
        bot.LOOKBACK = lookback
        bot.SCORE_MIN = 0.0
        bot.SCORE_MAX = math.inf
        return bot.run_staged_entry(
            prices, config, bot.EntryCase("full_entry", "full_entry", 1.0),
            None, 1.0, price_ffill_flags=flags,
        ).reset_index()
    finally:
        bot.LOOKBACK, bot.SCORE_MIN, bot.SCORE_MAX = original


def main():
    manifest = json.loads((L1 / "capture_manifest.json").read_text(encoding="utf-8"))
    for key in ("aligned", "flags"):
        if sha(manifest[key]["path"]) != manifest[key]["sha256"]:
            raise RuntimeError(f"L1 {key} hash mismatch")
    prices = pd.read_csv(manifest["aligned"]["path"], parse_dates=["date"]).set_index("date")
    flags = pd.read_csv(manifest["flags"]["path"], parse_dates=["date"]).set_index("date").astype(bool)
    if len(prices) != 3594 or prices.index[-1] != pd.Timestamp("2026-09-24") or not prices.index.equals(flags.index):
        raise RuntimeError("L1 coverage/alignment mismatch")
    bot = load_module("six_etf_v13_pure_momentum", BOT)
    helper = load_module("six_etf_v13_l6_helpers_pure", L6 / "run_l6_scan.py")
    if (bot.LOOKBACK, bot.SCORE_MIN, bot.SCORE_MAX, bot.R2_THRESHOLD,
        bot.SWITCH_BUFFER, bot.ONE_WAY_COST, bot.TARGET_VOL_ENABLED,
        bot.OVERHEAT_ENABLED, bot.STAGED_ENTRY_ENABLED) != (25, .5, 5.5, .25, 1., .001, False, False, False):
        raise RuntimeError("Formal constants changed")
    config = bot._build_config(end_date=pd.Timestamp("2026-09-24"))
    score_func = bot.weighted_slope_score_and_r2
    formal = helper.run_one(bot, prices, flags, config,
                            {"group": "lookback", "value": "25"}, score_func)
    official = pd.read_csv(L2 / "formal_daily_20260924.csv.gz", parse_dates=["date"])
    formal_parity = helper.assert_same_path(formal, official, "unchanged_formal_25_vs_L2")
    print("Unchanged formal 25-day parity PASS", flush=True)

    out = RUN / "daily_outputs"
    out.mkdir(exist_ok=True)
    pure25 = pure_run(bot, prices, flags, config, 25)
    if not pd.DatetimeIndex(pure25.date).equals(pd.DatetimeIndex(formal.date)):
        raise RuntimeError("Pure/formal dates diverged")
    pure_vs_formal = {
        "position_diff_days": int((pure25.position.fillna("<NA>").astype(str).to_numpy()
                                   != formal.position.fillna("<NA>").astype(str).to_numpy()).sum()),
        "first_position_diff": "",
        "end_nav_formal": float(formal.nav.iloc[-1]),
        "end_nav_pure": float(pure25.nav.iloc[-1]),
    }
    changed = pure25.position.fillna("<NA>").astype(str).to_numpy() != formal.position.fillna("<NA>").astype(str).to_numpy()
    if changed.any():
        pure_vs_formal["first_position_diff"] = str(pure25.date.iloc[np.flatnonzero(changed)[0]].date())

    long_rows, wide_rows, events = [], [], []
    for i, value in enumerate(VALUES, 1):
        candidate = f"lookback_{value}"
        curve = pure25 if value == 25 else pure_run(bot, prices, flags, config, value)
        if not pd.DatetimeIndex(curve.date).equals(pd.DatetimeIndex(formal.date)):
            raise RuntimeError(f"Date mismatch: {candidate}")
        if not (np.isfinite(curve.nav.to_numpy(float)).all() and (curve.nav > 0).all()):
            raise RuntimeError(f"Invalid NAV: {candidate}")
        if not (curve.holding_fraction.between(0, 1).all() and curve.fraction_before.between(0, 1).all()):
            raise RuntimeError(f"Invalid exposure: {candidate}")
        if curve.buffer_blocked.any() or curve.staged_initial.any() or curve.staged_fill_count.any():
            raise RuntimeError(f"Disabled layer fired: {candidate}")
        path = out / f"{candidate}.csv.gz"
        curve.to_csv(path, index=False, compression="gzip", float_format="%.16g")

        sub = []
        for segment, n in WINDOWS:
            start = None if n is None else pd.Timestamp(curve.date.iloc[-n])
            row = helper.metrics(curve, candidate, "lookback", str(value),
                                 "pure_25_baseline" if value == 25 else "candidate", segment, start)
            row["LOOKBACK"] = value
            sub.append(row)
            long_rows.append(row)
        common = helper.metrics(curve, candidate, "lookback", str(value),
                                "pure_25_baseline" if value == 25 else "candidate",
                                "six_etf_all_scoreable", COMMON_START)
        common["LOOKBACK"] = value
        long_rows.append(common)
        by_window = {row["segment"]: row for row in sub}
        wide = {"candidate": candidate, "LOOKBACK": value,
                "role": "pure_25_baseline" if value == 25 else "candidate"}
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
        pos_diff = curve.position.fillna("<NA>").astype(str).to_numpy() != pure25.position.fillna("<NA>").astype(str).to_numpy()
        events.append({"candidate": candidate, "LOOKBACK": value,
                       "position_diff_days_vs_pure25": int(pos_diff.sum()),
                       "first_position_diff_vs_pure25": str(curve.date.iloc[np.flatnonzero(pos_diff)[0]].date()) if pos_diff.any() else "",
                       "daily_path": str(path.relative_to(ROOT)), "daily_sha256": sha(path)})
        print(f"{i:02d}/{len(VALUES)} {candidate} full_ann={wide['ann_return_full']:.4%} full_dd={wide['max_dd_full']:.4%}", flush=True)

    summary = pd.DataFrame(long_rows)
    wide = pd.DataFrame(wide_rows)
    base = summary.loc[summary.candidate == "lookback_25"].set_index("segment")
    for field in ("ann_return", "max_dd", "trade_days", "turnover_total", "cash_days"):
        summary[f"pure25_{field}"] = summary.segment.map(base[field])
    summary["delta_ann_pp"] = (summary.ann_return - summary.pure25_ann_return) * 100
    summary["dd_improvement_pp"] = (summary.max_dd - summary.pure25_max_dd) * 100
    for segment, _ in WINDOWS:
        wide[f"delta_ann_pp_{segment}"] = (wide[f"ann_return_{segment}"] - wide.loc[wide.LOOKBACK == 25, f"ann_return_{segment}"].iloc[0]) * 100
        wide[f"dd_improvement_pp_{segment}"] = (wide[f"max_dd_{segment}"] - wide.loc[wide.LOOKBACK == 25, f"max_dd_{segment}"].iloc[0]) * 100
    summary.to_csv(RUN / "scan_summary.csv", index=False)
    wide.to_csv(RUN / "window_metrics.csv", index=False)
    pd.DataFrame(events).to_csv(RUN / "candidate_event_counts.csv", index=False)
    (RUN / "parity_checks.json").write_text(json.dumps({
        "unchanged_formal_25_vs_L2": formal_parity,
        "pure25_vs_formal25": pure_vs_formal,
        "formal_code_sha256": sha(BOT),
        "price_sha256": sha(manifest["aligned"]["path"]),
        "flags_sha256": sha(manifest["flags"]["path"]),
        "candidate_count": len(VALUES),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"COMPLETE {len(VALUES)} pure candidates, {len(summary)} window rows", flush=True)


if __name__ == "__main__":
    main()
