"""Scan the formal six-ETF V1.3 R² eligibility threshold from 0 to 2."""

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
L4 = ROOT / "outputs/recert_l4_20260926"
L6 = ROOT / "quant_param_scan_runs/20260926_six_etf_v1_3_l6_parameter_basis_20260924"
BOT = ROOT / "poe_subd_six_etf_v1_3_bot.py"
GRID = tuple(i / 20 for i in range(41))
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


def label(value):
    return f"r2_{value:.2f}".replace(".", "p")


def metrics(frame, candidate, value, role, segment, start):
    part = frame if start is None else frame.loc[frame.date >= start]
    part = part.reset_index(drop=True)
    nav = part.nav.to_numpy(float)
    if len(nav) < 2 or not np.isfinite(nav).all() or not (nav > 0).all():
        raise RuntimeError(f"Invalid NAV in {candidate}/{segment}")
    returns = nav[1:] / nav[:-1] - 1.0
    ratio = float(nav[-1] / nav[0])
    annual = ratio ** (252.0 / (len(nav) - 1)) - 1.0
    std = float(np.std(returns, ddof=1))
    vol = std * math.sqrt(252.0)
    defined = std > 0
    # Strict artifact schema requires a finite numeric cell. Zero is a schema
    # placeholder where Sharpe is undefined; sharpe_defined makes this explicit.
    sharpe = float(np.mean(returns) / std * math.sqrt(252.0)) if defined else 0.0
    dd = nav / np.maximum.accumulate(nav) - 1.0
    low = int(np.argmin(dd))
    high = int(np.argmax(nav[:low + 1]))
    fee_base = frame.nav.shift(1).fillna(1.0) * (1.0 + frame.gross_return)
    part_index = frame.index[frame.date >= start] if start is not None else frame.index
    paid_fee = float((fee_base.loc[part_index] * frame.loc[part_index, "cost"]).sum())
    return {
        "candidate": candidate, "group": "R2_THRESHOLD", "value": value, "role": role,
        "R2_THRESHOLD": value, "segment": segment,
        "start": str(part.date.iloc[0].date()), "end": str(part.date.iloc[-1].date()),
        "rows": len(part), "nav_changes": len(part) - 1,
        "ann_return": annual, "ann_vol": vol, "sharpe_repo": sharpe,
        "sharpe_defined": defined,
        "max_dd": float(dd[low]), "max_dd_peak": str(part.date.iloc[high].date()),
        "max_dd_trough": str(part.date.iloc[low].date()), "total_return": ratio - 1.0,
        "end_nav": float(nav[-1]), "trade_days": int((part.turnover > 0).sum()),
        "two_sided_switch_days": int((part.turnover == 2).sum()),
        "turnover_total": float(part.turnover.sum()), "cost_rate_total": float(part.cost.sum()),
        "paid_fee_initial_capital_units": paid_fee,
        "cash_days": int((part.position == "CASH").sum()),
        "avg_carried_exposure": float(part.fraction_before.mean()),
        "stale_trade_block_days": int(part.trade_blocked_by_stale_price.sum()),
        "buffer_block_days": int(part.buffer_blocked.sum()),
    }


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
    bot = load_module("six_etf_v13_r2_threshold_grid", BOT)
    helper = load_module("six_etf_v13_l6_r2_helpers", L6 / "run_l6_scan.py")
    if (bot.LOOKBACK, bot.SCORE_MIN, bot.SCORE_MAX, bot.R2_THRESHOLD,
        bot.SWITCH_BUFFER, bot.ONE_WAY_COST, bot.TARGET_VOL_ENABLED,
        bot.OVERHEAT_ENABLED, bot.STAGED_ENTRY_ENABLED) != (25, .5, 5.5, .25, 1., .001, False, False, False):
        raise RuntimeError("Formal constants changed")
    config = bot._build_config(end_date=pd.Timestamp("2026-09-24"))
    formal = bot.run_staged_entry(prices, config, bot.EntryCase("full_entry", "full_entry", 1.0),
                                  .25, 1.0, price_ffill_flags=flags).reset_index()
    official = pd.read_csv(L2 / "formal_daily_20260924.csv.gz", parse_dates=["date"])
    formal_parity = helper.assert_same_path(formal, official, "formal_r2_0p25_vs_L2")
    off = bot.run_staged_entry(prices, config, bot.EntryCase("full_entry", "full_entry", 1.0),
                               0.0, 1.0, price_ffill_flags=flags).reset_index()
    l4_off = pd.read_csv(L4 / "daily_r2_off_20260924.csv.gz", parse_dates=["date"])
    zero_parity = helper.assert_same_path(off, l4_off, "r2_zero_vs_L4_off")
    print("Formal 0.25 and zero-threshold parity PASS", flush=True)

    out = RUN / "daily_outputs"
    out.mkdir(exist_ok=True)
    long_rows, wide_rows, event_rows = [], [], []
    max_r2 = max(float(off[f"r2_{code}"].max()) for code in bot.ASSETS)
    for i, value in enumerate(GRID, 1):
        candidate = label(value)
        curve = (formal if value == .25 else off if value == 0.0 else
                 bot.run_staged_entry(prices, config, bot.EntryCase("full_entry", "full_entry", 1.0),
                                      value, 1.0, price_ffill_flags=flags).reset_index())
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
        role = "formal" if value == .25 else "candidate"
        wide = {"candidate": candidate, "R2_THRESHOLD": value, "role": role}
        for segment, window in WINDOWS:
            start = (None if window is None else pd.Timestamp(curve.date.iloc[-window])
                     if isinstance(window, int) else window)
            row = metrics(curve, candidate, value, role, segment, start)
            long_rows.append(row)
            wide[f"ann_return_{segment}"] = row["ann_return"]
            wide[f"max_dd_{segment}"] = row["max_dd"]
            wide[f"sharpe_repo_{segment}"] = row["sharpe_repo"]
            wide[f"sharpe_defined_{segment}"] = row["sharpe_defined"]
            if segment == "full":
                wide.update(end_nav_full=row["end_nav"], trade_days_full=row["trade_days"],
                            turnover_total_full=row["turnover_total"], cash_days_full=row["cash_days"])
        wide_rows.append(wide)
        difference = curve.position.fillna("<NA>").astype(str).to_numpy() != formal.position.fillna("<NA>").astype(str).to_numpy()
        event_rows.append({"candidate": candidate, "R2_THRESHOLD": value,
                           "position_diff_days_vs_formal": int(difference.sum()),
                           "first_diff_vs_formal": str(curve.date.iloc[np.flatnonzero(difference)[0]].date()) if difference.any() else "",
                           "daily_path": str(path.relative_to(ROOT)), "daily_sha256": sha(path)})
        print(f"{i:02d}/{len(GRID)} {candidate} full_ann={wide['ann_return_full']:.4%} full_dd={wide['max_dd_full']:.4%} trades={wide['trade_days_full']}", flush=True)
    summary = pd.DataFrame(long_rows)
    wide = pd.DataFrame(wide_rows)
    base = summary.loc[summary.candidate == label(.25)].set_index("segment")
    for field in ("ann_return", "max_dd", "trade_days", "turnover_total", "cash_days"):
        summary[f"formal_{field}"] = summary.segment.map(base[field])
    summary["delta_ann_vs_formal_pp"] = (summary.ann_return - summary.formal_ann_return) * 100
    summary["dd_improvement_vs_formal_pp"] = (summary.max_dd - summary.formal_max_dd) * 100
    summary.to_csv(RUN / "scan_summary.csv", index=False)
    wide.to_csv(RUN / "window_metrics.csv", index=False)
    pd.DataFrame(event_rows).to_csv(RUN / "candidate_event_counts.csv", index=False)
    (RUN / "parity_checks.json").write_text(json.dumps({
        "formal_0p25_vs_L2": formal_parity, "zero_vs_L4_off": zero_parity,
        "max_observed_weighted_r2": max_r2,
        "formal_code_sha256": sha(BOT),
        "price_sha256": sha(manifest["aligned"]["path"]),
        "flags_sha256": sha(manifest["flags"]["path"]),
        "candidate_count": len(GRID),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"COMPLETE {len(GRID)} candidates, {len(summary)} window rows; max weighted R2={max_r2:.8f}", flush=True)


if __name__ == "__main__":
    main()
