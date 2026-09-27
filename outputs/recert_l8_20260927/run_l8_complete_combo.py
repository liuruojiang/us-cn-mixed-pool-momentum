"""Frozen L8 complete-combination replay on the six-ETF V1.3 paper account."""

import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
BOT_PATH = ROOT / "poe_subd_six_etf_v1_3_bot.py"
L1 = ROOT / "outputs/recert_l1_20260926/capture_manifest.json"
L2 = ROOT / "outputs/recert_l2_20260926/formal_daily_20260924.csv.gz"
L5 = ROOT / "outputs/recert_l5_20260926"
L6_AUDIT = ROOT / "outputs/recert_l6_20260926"
MATRIX = OUT / "agent_a_matrix.csv"
PROTOCOL = OUT / "agent_a_freeze_protocol.md"
EXPECTED_MATRIX_SHA = "2fa744ed1b44825ca47bb5e4e0124fbe024c17cd8823b109319b80608830ed42"
EXPECTED_PROTOCOL_SHA = "f3e1d214356d91b4461d6125360e90a47959deae970e396d4d7594e27a6b6db0"
EXPECTED_BOT_SHA = "b49c86944f0ef843f0eb23eebe396122fee0db5a90c6250789f21b3d110df988"
END = pd.Timestamp("2026-09-24")
WINDOWS = (("Full", None), ("10Y", 2520), ("5Y", 1260), ("3Y", 756), ("1Y", 252))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def score_with_power(window, lookback, power, annual_days):
    values = window.dropna().astype(float)
    if len(values) != lookback or (values <= 0).any() or not np.isfinite(values.to_numpy(float)).all():
        return math.nan, math.nan
    y = np.log(values.to_numpy(float))
    if float(np.ptp(y)) <= 1e-12:
        return math.nan, math.nan
    y = y - y[0]
    x = np.arange(len(y), dtype=float)
    weights = np.arange(1, len(y) + 1, dtype=float) ** power
    slope, intercept = np.polyfit(x, y, 1, w=np.sqrt(weights))
    fit = slope * x + intercept
    mean = float(np.average(y, weights=weights))
    sst = float(np.sum(weights * (y - mean) ** 2))
    if sst <= 0:
        return math.nan, math.nan
    r2 = max(0.0, 1.0 - float(np.sum(weights * (y - fit) ** 2)) / sst)
    annual_log = float(slope) * annual_days
    if not math.isfinite(annual_log) or annual_log > math.log(sys.float_info.max):
        return math.nan, r2
    return math.exp(annual_log) - 1.0, r2


def run_arm(bot, prices, flags, config, row, original_score):
    previous = bot.LOOKBACK, bot.SCORE_MIN, bot.SCORE_MAX, bot.weighted_slope_score_and_r2
    try:
        bot.LOOKBACK = int(row.lookback)
        bot.SCORE_MIN = -math.inf if row.score_floor == "off" else float(row.score_floor)
        bot.SCORE_MAX = math.inf if row.score_ceiling == "off" else float(row.score_ceiling)
        power = float(row.weight_power)
        if power != 1.0:
            bot.weighted_slope_score_and_r2 = lambda window: score_with_power(window, bot.LOOKBACK, power, bot.TRADING_DAYS)
        r2 = None if row.r2_threshold == "off" else float(row.r2_threshold)
        result = bot.run_staged_entry(
            prices, config, bot.EntryCase("full_entry", "full_entry", 1.0),
            r2, float(row.switch_buffer), price_ffill_flags=flags,
        ).reset_index()
        return result
    finally:
        bot.LOOKBACK, bot.SCORE_MIN, bot.SCORE_MAX, bot.weighted_slope_score_and_r2 = previous


def parity(actual, saved, name):
    assert pd.DatetimeIndex(actual.date).equals(pd.DatetimeIndex(saved.date)), name
    result = {"reference": name, "rows": len(actual)}
    for field in ("position_before", "position", "trade_target"):
        if field in actual and field in saved:
            result[field + "_mismatch"] = int((actual[field].fillna("<NA>").astype(str).to_numpy() != saved[field].fillna("<NA>").astype(str).to_numpy()).sum())
            assert result[field + "_mismatch"] == 0, result
    for field in ("turnover", "cost", "return", "nav"):
        result[field + "_max_abs"] = float(np.max(np.abs(actual[field].to_numpy(float) - saved[field].to_numpy(float))))
        assert result[field + "_max_abs"] <= (2e-10 if field == "nav" else 2e-12), result
    return result


def metrics(frame, arm, role, window, start):
    part = frame if start is None else frame.loc[frame.date >= start]
    nav = part.nav.to_numpy(float)
    assert len(nav) >= 2 and np.isfinite(nav).all() and (nav > 0).all()
    dd = nav / np.maximum.accumulate(nav) - 1
    low = int(np.argmin(dd))
    high = int(np.argmax(nav[:low + 1]))
    before_fee = frame.nav.shift(1).fillna(1.0) * (1 + frame.gross_return)
    fee_capital = float((before_fee.loc[part.index] * part.cost).sum())
    return {
        "arm": arm, "role": role, "window": window, "start": str(part.date.iloc[0].date()),
        "end": str(part.date.iloc[-1].date()), "rows": len(part), "nav_changes": len(part)-1,
        "annual_net": float((nav[-1]/nav[0]) ** (252/(len(nav)-1)) - 1),
        "total_net": float(nav[-1]/nav[0] - 1), "maxdd": float(dd[low]),
        "peak_date": str(part.date.iloc[high].date()), "trough_date": str(part.date.iloc[low].date()),
        "end_nav": float(nav[-1]), "trade_days": int((part.turnover > 1e-12).sum()),
        "two_leg_days": int((part.turnover > 1.5).sum()), "turnover": float(part.turnover.sum()),
        "cost_rate_sum": float(part.cost.sum()), "paid_fee_initial_capital": fee_capital,
        "cash_days": int((part.position == "CASH").sum()),
        "average_carried_exposure": float(part.fraction_before.mean()),
        "max_exposure": float(part.holding_fraction.max()),
        "buffer_block_days": int(part.buffer_blocked.sum()),
        "stale_trade_block_days": int(part.trade_blocked_by_stale_price.sum()),
    }


def account_checks(frame, prices, assets):
    nav = frame.nav.to_numpy(float)
    holding = frame.position.fillna("CASH").astype(str).to_numpy()
    shares = np.zeros(len(frame))
    cash = np.zeros(len(frame))
    for i, code in enumerate(holding):
        if code == "CASH":
            cash[i] = nav[i]
        else:
            assert code in assets, code
            price = float(prices.loc[pd.Timestamp(frame.date.iloc[i]), code])
            assert np.isfinite(price) and price > 0
            shares[i] = nav[i] / price
    mark = np.array([cash[i] + (shares[i] * float(prices.loc[pd.Timestamp(frame.date.iloc[i]), holding[i]]) if holding[i] != "CASH" else 0.0) for i in range(len(frame))])
    assert np.min(cash) >= 0 and np.min(shares) >= 0
    assert np.max(np.abs(mark - nav)) <= 1e-10
    assert frame.holding_fraction.between(0, 1).all() and frame.fraction_before.between(0, 1).all()
    assert np.max(np.abs(frame.cost.to_numpy(float) - .001 * frame.turnover.to_numpy(float))) <= 1e-12
    blocked = frame.trade_blocked_by_stale_price.astype(bool)
    assert (frame.loc[blocked, "turnover"].abs() < 1e-12).all()
    return {"min_cash": float(np.min(cash)), "min_shares": float(np.min(shares)),
            "max_mark_error": float(np.max(np.abs(mark-nav))), "max_exposure": float(frame.holding_fraction.max()),
            "blocked_trade_violations": int((frame.loc[blocked, "turnover"].abs() > 1e-12).sum())}


def main():
    assert sha(MATRIX) == EXPECTED_MATRIX_SHA and sha(PROTOCOL) == EXPECTED_PROTOCOL_SHA
    assert sha(BOT_PATH) == EXPECTED_BOT_SHA
    manifest = json.loads(L1.read_text(encoding="utf-8"))
    for item in ("aligned", "flags"):
        assert sha(manifest[item]["path"]) == manifest[item]["sha256"]
    prices = pd.read_csv(manifest["aligned"]["path"], parse_dates=["date"]).set_index("date")
    flags = pd.read_csv(manifest["flags"]["path"], parse_dates=["date"]).set_index("date").astype(bool)
    assert len(prices) == 3594 and prices.index[-1] == END and prices.index.equals(flags.index)
    matrix = pd.read_csv(MATRIX, dtype=str, keep_default_na=False)
    assert len(matrix) == 27 and matrix.arm.is_unique and matrix.iloc[0].arm == "formal_111"
    spec = importlib.util.spec_from_file_location("six_etf_v13_l8", BOT_PATH)
    bot = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = bot
    spec.loader.exec_module(bot)
    assert (bot.LOOKBACK, bot.SCORE_MIN, bot.SCORE_MAX, bot.R2_THRESHOLD, bot.SWITCH_BUFFER, bot.ONE_WAY_COST) == (25, .5, 5.5, .25, 1., .001)
    config = bot._build_config(end_date=END)
    score_func = bot.weighted_slope_score_and_r2
    daily_dir = OUT / "daily"
    daily_dir.mkdir(exist_ok=True)
    all_metrics, triggers, checks, parities = [], [], {}, []
    formal = None
    previous_paths = {
        "formal_111": L2,
        "gate_011": L5 / "daily_score_floor_off.csv.gz",
        "gate_101": L5 / "daily_score_ceiling_off.csv.gz",
        "gate_110": L5 / "daily_r2_off.csv.gz",
        "gate_001": L5 / "daily_floor_ceiling_off.csv.gz",
        "gate_010": L5 / "daily_floor_r2_off.csv.gz",
        "gate_100": L5 / "daily_ceiling_r2_off.csv.gz",
        "gate_000": L5 / "daily_all_three_off.csv.gz",
        "weight_p0": L6_AUDIT / "agent_b_weight_power_0_daily.csv.gz",
        "lookback_29": L6_AUDIT / "agent_b_lookback_29_daily.csv.gz",
    }
    for i, row in enumerate(matrix.itertuples(index=False), 1):
        curve = run_arm(bot, prices, flags, config, row, score_func)
        assert pd.DatetimeIndex(curve.date).equals(prices.index)
        assert np.isfinite(curve.nav.to_numpy(float)).all() and (curve.nav > 0).all()
        if formal is None:
            formal = curve
        checks[row.arm] = account_checks(curve, prices, list(bot.ASSETS))
        if row.arm in previous_paths:
            parities.append(parity(curve, pd.read_csv(previous_paths[row.arm], parse_dates=["date"]), str(previous_paths[row.arm].relative_to(ROOT))))
        for window, n in WINDOWS:
            start = None if n is None else pd.Timestamp(curve.date.iloc[-n])
            all_metrics.append(metrics(curve, row.arm, row.role, window, start))
        all_metrics.append(metrics(curve, row.arm, row.role, "SixScoreable", pd.Timestamp("2020-01-09")))
        target_diff = curve.best_candidate.fillna("<NA>").astype(str).to_numpy() != formal.best_candidate.fillna("<NA>").astype(str).to_numpy()
        holding_diff = curve.position.fillna("<NA>").astype(str).to_numpy() != formal.position.fillna("<NA>").astype(str).to_numpy()
        triggers.append({"arm": row.arm, "role": row.role, "target_diff_days": int(target_diff.sum()),
                         "holding_diff_days": int(holding_diff.sum()),
                         "first_target_diff": str(curve.date.iloc[np.flatnonzero(target_diff)[0]].date()) if target_diff.any() else "",
                         "first_holding_diff": str(curve.date.iloc[np.flatnonzero(holding_diff)[0]].date()) if holding_diff.any() else "",
                         "buffer_block_days": int(curve.buffer_blocked.sum())})
        path = daily_dir / f"{row.arm}.csv.gz"
        curve.to_csv(path, index=False, compression="gzip", float_format="%.16g")
        print(f"{i:02d}/27 {row.arm} NAV={curve.nav.iloc[-1]:.10f}", flush=True)
    pd.DataFrame(all_metrics).to_csv(OUT / "matched_metrics.csv", index=False)
    pd.DataFrame(triggers).to_csv(OUT / "trigger_counts.csv", index=False)
    run = {"code_sha256": sha(BOT_PATH), "git_head_at_L1": manifest["git_head"], "matrix_sha256": sha(MATRIX),
           "protocol_sha256": sha(PROTOCOL), "prices_sha256": sha(manifest["aligned"]["path"]),
           "flags_sha256": sha(manifest["flags"]["path"]), "cutoff": str(END.date()),
           "rows": len(prices), "paths": len(matrix), "account_checks": checks, "old_path_parity": parities,
           "daily_sha256": {p.stem.split(".")[0]: sha(p) for p in daily_dir.glob("*.csv.gz")},
           "metrics_sha256": sha(OUT / "matched_metrics.csv"), "triggers_sha256": sha(OUT / "trigger_counts.csv")}
    (OUT / "run_manifest.json").write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
    print("L8 main replay PASS: 27 arms, 162 windows", flush=True)


if __name__ == "__main__":
    main()
