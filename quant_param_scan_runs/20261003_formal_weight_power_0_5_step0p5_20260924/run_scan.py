"""Scan recency-weight power with all formal six-ETF V1.3 gates active."""

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
L8 = ROOT / "outputs/recert_l8_20260927"
L6 = ROOT / "quant_param_scan_runs/20260926_six_etf_v1_3_l6_parameter_basis_20260924"
BOT = ROOT / "poe_subd_six_etf_v1_3_bot.py"
POWERS = tuple(i / 2 for i in range(11))
WINDOWS = (("full", None), ("last_10y", 2520), ("last_5y", 1260),
           ("last_3y", 756), ("last_1y", 252),
           ("six_etf_all_scoreable", pd.Timestamp("2020-01-09")))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def label(power):
    return f"weight_p{power:g}".replace(".", "p")


def run_power(bot, helper, prices, flags, config, power):
    original = bot.weighted_slope_score_and_r2
    try:
        if power != 1.0:
            bot.weighted_slope_score_and_r2 = lambda window: helper.score_with_power(
                window, bot.LOOKBACK, power, bot.TRADING_DAYS)
        return bot.run_staged_entry(
            prices, config, bot.EntryCase("full_entry", "full_entry", 1.0),
            bot.R2_THRESHOLD, bot.SWITCH_BUFFER, price_ffill_flags=flags,
        ).reset_index()
    finally:
        bot.weighted_slope_score_and_r2 = original


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
    bot = load_module("six_etf_v13_formal_weight_grid", BOT)
    helper = load_module("six_etf_v13_l6_weight_helpers", L6 / "run_l6_scan.py")
    if (bot.LOOKBACK, bot.SCORE_MIN, bot.SCORE_MAX, bot.R2_THRESHOLD,
        bot.SWITCH_BUFFER, bot.ONE_WAY_COST, bot.TARGET_VOL_ENABLED,
        bot.OVERHEAT_ENABLED, bot.STAGED_ENTRY_ENABLED) != (25, .5, 5.5, .25, 1., .001, False, False, False):
        raise RuntimeError("Formal constants changed")
    config = bot._build_config(end_date=pd.Timestamp("2026-09-24"))
    formal = helper.run_one(bot, prices, flags, config,
                            {"group": "lookback", "value": "25"},
                            bot.weighted_slope_score_and_r2)
    official = pd.read_csv(L2 / "formal_daily_20260924.csv.gz", parse_dates=["date"])
    formal_parity = helper.assert_same_path(formal, official, "formal_p1_r2_on_vs_L2")
    p1 = run_power(bot, helper, prices, flags, config, 1.0)
    p1_parity = helper.assert_same_path(p1, official, "p1_formal_vs_L2")
    print("Formal p=1 parity PASS", flush=True)

    out = RUN / "daily_outputs"
    out.mkdir(exist_ok=True)
    long_rows, wide_rows, events = [], [], []
    paths = []
    for power in POWERS:
        paths.append((label(power), power,
                      "formal" if power == 1.0 else "candidate",
                      p1 if power == 1.0 else run_power(bot, helper, prices, flags, config, power)))
    p0_curve = next(curve for _, power, _, curve in paths if power == 0.0)
    l8_p0 = pd.read_csv(L8 / "daily/weight_p0.csv.gz", parse_dates=["date"])
    p0_parity = helper.assert_same_path(p0_curve, l8_p0, "p0_vs_L8")
    for i, (candidate, power, role, curve) in enumerate(paths, 1):
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
        wide = {"candidate": candidate, "WEIGHT_POWER": power,
                "R2_FILTER": True, "role": role}
        for segment, window in WINDOWS:
            start = (None if window is None else pd.Timestamp(curve.date.iloc[-window])
                     if isinstance(window, int) else window)
            row = helper.metrics(curve, candidate, "WEIGHT_POWER", str(power), role, segment, start)
            row.update(WEIGHT_POWER=power, R2_FILTER=True)
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
        events.append({"candidate": candidate, "WEIGHT_POWER": power,
                       "position_diff_days_vs_formal": int(difference.sum()),
                       "first_diff_vs_formal": str(curve.date.iloc[np.flatnonzero(difference)[0]].date()) if difference.any() else "",
                       "daily_path": str(path.relative_to(ROOT)), "daily_sha256": sha(path)})
        print(f"{i:02d}/{len(paths)} {candidate} full_ann={wide['ann_return_full']:.4%} full_dd={wide['max_dd_full']:.4%}", flush=True)

    summary = pd.DataFrame(long_rows)
    wide = pd.DataFrame(wide_rows)
    formal_metrics = summary.loc[summary.candidate == label(1.0)].set_index("segment")
    for field in ("ann_return", "max_dd", "trade_days", "turnover_total", "cash_days"):
        summary[f"formal_p1_{field}"] = summary.segment.map(formal_metrics[field])
    summary["delta_ann_vs_formal_pp"] = (summary.ann_return - summary.formal_p1_ann_return) * 100
    summary["dd_improvement_vs_formal_pp"] = (summary.max_dd - summary.formal_p1_max_dd) * 100
    summary.to_csv(RUN / "scan_summary.csv", index=False)
    wide.to_csv(RUN / "window_metrics.csv", index=False)
    pd.DataFrame(events).to_csv(RUN / "candidate_event_counts.csv", index=False)
    (RUN / "parity_checks.json").write_text(json.dumps({
        "formal_p1_vs_L2": formal_parity,
        "p1_direct_vs_L2": p1_parity,
        "p0_vs_L8": p0_parity,
        "formal_code_sha256": sha(BOT),
        "price_sha256": sha(manifest["aligned"]["path"]),
        "flags_sha256": sha(manifest["flags"]["path"]),
        "candidate_count": len(POWERS),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"COMPLETE {len(paths)} paths, {len(summary)} window rows", flush=True)


if __name__ == "__main__":
    main()
