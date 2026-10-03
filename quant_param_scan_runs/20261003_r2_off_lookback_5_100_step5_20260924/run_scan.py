"""R²-off LOOKBACK scan on the formal six-ETF V1.3 paper account."""

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
L4 = ROOT / "outputs/recert_l4_20260926"
L6 = ROOT / "quant_param_scan_runs/20260926_six_etf_v1_3_l6_parameter_basis_20260924"
BOT = ROOT / "poe_subd_six_etf_v1_3_bot.py"
GRID = tuple(range(5, 101, 5))
WINDOWS = (("full", None), ("last_10y", 2520), ("last_5y", 1260),
           ("last_3y", 756), ("last_1y", 252),
           ("six_etf_all_scoreable", pd.Timestamp("2020-05-07")))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def r2_off_run(bot, prices, flags, config, lookback):
    original = bot.LOOKBACK
    try:
        bot.LOOKBACK = lookback
        return bot.run_staged_entry(
            prices, config, bot.EntryCase("full_entry", "full_entry", 1.0),
            None, bot.SWITCH_BUFFER, price_ffill_flags=flags,
        ).reset_index()
    finally:
        bot.LOOKBACK = original


def main():
    manifest = json.loads((L1 / "capture_manifest.json").read_text(encoding="utf-8"))
    for key in ("aligned", "flags"):
        if sha(manifest[key]["path"]) != manifest[key]["sha256"]:
            raise RuntimeError(f"L1 {key} hash mismatch")
    prices = pd.read_csv(manifest["aligned"]["path"], parse_dates=["date"]).set_index("date")
    flags = pd.read_csv(manifest["flags"]["path"], parse_dates=["date"]).set_index("date").astype(bool)
    if (len(prices) != 3594 or prices.index[-1] != pd.Timestamp("2026-09-24")
            or not prices.index.equals(flags.index)):
        raise RuntimeError("L1 price or flag coverage mismatch")
    bot = load_module("six_etf_v13_r2_off_grid", BOT)
    helper = load_module("six_etf_v13_l6_helpers_r2off_grid", L6 / "run_l6_scan.py")
    if (bot.LOOKBACK, bot.SCORE_MIN, bot.SCORE_MAX, bot.R2_THRESHOLD,
        bot.SWITCH_BUFFER, bot.ONE_WAY_COST, bot.TARGET_VOL_ENABLED,
        bot.OVERHEAT_ENABLED, bot.STAGED_ENTRY_ENABLED) != (25, .5, 5.5, .25, 1., .001, False, False, False):
        raise RuntimeError("Formal constants changed")
    config = bot._build_config(end_date=pd.Timestamp("2026-09-24"))
    formal = helper.run_one(bot, prices, flags, config,
                            {"group": "lookback", "value": "25"},
                            bot.weighted_slope_score_and_r2)
    official = pd.read_csv(L2 / "formal_daily_20260924.csv.gz", parse_dates=["date"])
    parity_formal = helper.assert_same_path(formal, official, "formal_25_r2_on_vs_L2")
    off25 = r2_off_run(bot, prices, flags, config, 25)
    l4_off = pd.read_csv(L4 / "daily_r2_off_20260924.csv.gz", parse_dates=["date"])
    parity_r2off = helper.assert_same_path(off25, l4_off, "r2_off_25_vs_L4")
    print("25-day formal and R2-off parity PASS", flush=True)

    out = RUN / "daily_outputs"
    out.mkdir(exist_ok=True)
    curves = [("formal_25_r2_on", 25, "formal_reference", formal)]
    curves += [(f"r2_off_{n}", n, "r2_off_baseline" if n == 25 else "candidate",
                off25 if n == 25 else r2_off_run(bot, prices, flags, config, n))
               for n in GRID]
    long_rows, wide_rows, event_rows = [], [], []
    for i, (candidate, value, role, curve) in enumerate(curves, 1):
        if not pd.DatetimeIndex(curve.date).equals(pd.DatetimeIndex(formal.date)):
            raise RuntimeError(f"Date mismatch: {candidate}")
        if not np.isfinite(curve.nav.to_numpy(float)).all() or not (curve.nav > 0).all():
            raise RuntimeError(f"Invalid NAV: {candidate}")
        if not (curve.holding_fraction.between(0, 1).all()
                and curve.fraction_before.between(0, 1).all()):
            raise RuntimeError(f"Invalid exposure: {candidate}")
        if curve.buffer_blocked.any() or curve.staged_initial.any() or curve.staged_fill_count.any():
            raise RuntimeError(f"Disabled layer fired: {candidate}")
        path = out / f"{candidate}.csv.gz"
        curve.to_csv(path, index=False, compression="gzip", float_format="%.16g")
        wide = {"candidate": candidate, "LOOKBACK": value, "R2_FILTER": role == "formal_reference", "role": role}
        for segment, window in WINDOWS:
            start = (None if window is None else pd.Timestamp(curve.date.iloc[-window])
                     if isinstance(window, int) else window)
            row = helper.metrics(curve, candidate, "LOOKBACK_R2_OFF", str(value), role, segment, start)
            row.update(LOOKBACK=value, R2_FILTER=role == "formal_reference")
            long_rows.append(row)
            wide[f"ann_return_{segment}"] = row["ann_return"]
            wide[f"max_dd_{segment}"] = row["max_dd"]
            wide[f"sharpe_repo_{segment}"] = row["sharpe_repo"]
            if segment == "full":
                wide.update(end_nav_full=row["end_nav"], trade_days_full=row["trade_days"],
                            turnover_total_full=row["turnover_total"],
                            cost_rate_total_full=row["cost_rate_total"])
        wide_rows.append(wide)
        difference = curve.position.fillna("<NA>").astype(str).to_numpy() != formal.position.fillna("<NA>").astype(str).to_numpy()
        event_rows.append({"candidate": candidate, "LOOKBACK": value,
                           "position_diff_days_vs_formal": int(difference.sum()),
                           "first_diff_vs_formal": str(curve.date.iloc[np.flatnonzero(difference)[0]].date()) if difference.any() else "",
                           "daily_path": str(path.relative_to(ROOT)), "daily_sha256": sha(path)})
        print(f"{i:02d}/{len(curves)} {candidate} full_ann={wide['ann_return_full']:.4%} full_dd={wide['max_dd_full']:.4%}", flush=True)

    summary = pd.DataFrame(long_rows)
    wide = pd.DataFrame(wide_rows)
    formal_metrics = summary.loc[summary.candidate == "formal_25_r2_on"].set_index("segment")
    off25_metrics = summary.loc[summary.candidate == "r2_off_25"].set_index("segment")
    for label, frame in (("formal25", formal_metrics), ("r2off25", off25_metrics)):
        for field in ("ann_return", "max_dd", "trade_days", "turnover_total", "cash_days"):
            summary[f"{label}_{field}"] = summary.segment.map(frame[field])
    summary["delta_ann_vs_formal_pp"] = (summary.ann_return - summary.formal25_ann_return) * 100
    summary["dd_improvement_vs_formal_pp"] = (summary.max_dd - summary.formal25_max_dd) * 100
    summary.to_csv(RUN / "scan_summary.csv", index=False)
    wide.to_csv(RUN / "window_metrics.csv", index=False)
    pd.DataFrame(event_rows).to_csv(RUN / "candidate_event_counts.csv", index=False)
    (RUN / "parity_checks.json").write_text(json.dumps({
        "formal_25_r2_on_vs_L2": parity_formal,
        "r2_off_25_vs_L4": parity_r2off,
        "formal_code_sha256": sha(BOT),
        "price_sha256": sha(manifest["aligned"]["path"]),
        "flags_sha256": sha(manifest["flags"]["path"]),
        "r2_off_candidate_count": len(GRID),
        "same_batch_formal_reference_count": 1,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"COMPLETE {len(curves)} paths, {len(summary)} window rows", flush=True)


if __name__ == "__main__":
    main()
