"""Independent oracle on real frozen prices; injected faults are diagnostic only."""
from pathlib import Path
import hashlib
import importlib.util
import json
from datetime import datetime
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
INPUT = ROOT / "outputs/doublecheck_script_audit_20261007/final_network"
SOURCE = ROOT / "poe_subd_six_etf_v1_3_bot.py"
spec = importlib.util.spec_from_file_location("independent_math_20261024", SOURCE)
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)
raw = pd.read_csv(INPUT / "raw_prices_qfq.csv.gz", parse_dates=["date"]).set_index("date")
sources = pd.read_csv(INPUT / "sources.csv")
saved = pd.read_csv(INPUT / "confirmed_daily.csv.gz", parse_dates=["date"]).set_index("date")
calendar = pd.DatetimeIndex(pd.to_datetime(pd.read_csv(ROOT / "outputs/doublecheck_script_audit_20261007/math_calendar_final.csv")["trade_date"]))
manifest = json.loads((INPUT / "manifest.json").read_text(encoding="utf-8"))
for name in ("raw_prices_qfq.csv.gz", "sources.csv", "confirmed_daily.csv.gz"):
    assert hashlib.sha256((INPUT / name).read_bytes()).hexdigest() == manifest["files"][name]

# Only network inputs are replaced by archived real provider data and calendar.
bot.load_close = lambda config: (raw.copy(), sources.copy())
bot._expected_cn_trading_days = lambda start, end: calendar[(calendar >= start) & (calendar <= end)]
daily, source_name = bot._build_v13_daily(raw.index[-1], now=datetime(2026, 10, 24, 12, tzinfo=bot.CN_TZ))
curve = daily.set_index("date")
prices = raw.ffill()
flags = prices.notna() & raw.isna()
codes = list(bot.ASSETS)
weights = np.arange(1, 26, dtype=float)
x = np.arange(25, dtype=float)
xc = x - np.average(x, weights=weights)
denominator = np.dot(weights, xc * xc)

def independent_scores(frame):
    score = pd.DataFrame(np.nan, index=frame.index, columns=codes)
    r2 = score.copy()
    for code in codes:
        for k in range(24, len(frame)):
            v = frame[code].iloc[k-24:k+1].to_numpy(float)
            if not np.isfinite(v).all() or (v <= 0).any():
                continue
            y = np.log(v)
            yc = y - np.average(y, weights=weights)
            if np.ptp(y) <= 1e-12:
                continue
            slope = np.dot(weights * xc, yc) / denominator
            residual = yc - slope * xc
            ss = np.dot(weights, yc * yc)
            score.iat[k, score.columns.get_loc(code)] = np.expm1(slope * 252)
            r2.iat[k, r2.columns.get_loc(code)] = max(0., 1 - np.dot(weights, residual * residual) / ss)
    return score, r2

score, r2 = independent_scores(prices)
holding = "CASH"
cash = 1.0
shares = 0.0
previous_nav = 1.0
ledger = []
for k, dt in enumerate(prices.index):
    eligible = [c for c in codes if .5 < score.at[dt, c] < 5.5 and r2.at[dt, c] >= .25]
    target = max(eligible, key=lambda c: score.at[dt, c]) if eligible else "CASH"
    old = holding
    before_cost = cash if old == "CASH" else shares * prices.at[dt, old]
    turnover = 0.0
    blocked = False
    if old != target:
        legs = [c for c in (old, target) if c != "CASH"]
        blocked = any(flags.at[dt, c] for c in legs)
        if not blocked:
            turnover = float(len(legs))
            after_cost = before_cost * (1 - .001 * turnover)
            holding = target
            if target == "CASH":
                cash, shares = after_cost, 0.0
            else:
                cash, shares = 0.0, after_cost / prices.at[dt, target]
    nav = cash if holding == "CASH" else shares * prices.at[dt, holding]
    ledger.append({"date": dt, "position_before": old, "position": holding, "best_candidate": target,
                   "turnover": turnover, "cost": .001 * turnover, "nav": nav,
                   "return": nav / previous_nav - 1, "trade_blocked_by_stale_price": blocked})
    previous_nav = nav
oracle = pd.DataFrame(ledger).set_index("date")
diffs = {}
for col in ["position_before", "position", "best_candidate", "trade_blocked_by_stale_price"]:
    diffs[col] = int((curve[col] != oracle[col]).sum())
    assert diffs[col] == 0, col
for col in ["turnover", "cost", "nav", "return"]:
    diffs[col] = float((curve[col] - oracle[col]).abs().max())
    np.testing.assert_allclose(curve[col], oracle[col], rtol=0, atol=1e-11)
score_diffs = {}
for code in codes:
    score_diffs[code] = float((curve[f"raw_score_{code}"] - score[code]).abs().max())
    np.testing.assert_allclose(curve[f"raw_score_{code}"], score[code], atol=1e-10, rtol=1e-12, equal_nan=True)
    np.testing.assert_allclose(curve[f"r2_{code}"], r2[code], atol=1e-12, rtol=1e-12, equal_nan=True)
saved_diffs = {c: float((curve[c] - saved[c]).abs().max()) for c in ["nav", "return", "cost", "turnover"]}
assert all(v < 1e-11 for v in saved_diffs.values())
assert curve.position.equals(saved.position)

prefix_results = []
for k in [23, 24, 25, 500, 1800, 3000, len(prices)-2]:
    part = bot.build_curves(prices.iloc[:k+1], bot._build_config(prices.index[k]), flags.iloc[:k+1])[0]
    for c in ["position", "position_before", "turnover", "cost", "nav", "return"]:
        pd.testing.assert_series_equal(part[c], curve[c].iloc[:k+1], check_names=False)
    prefix_results.append({"date": str(prices.index[k].date()), "rows": k+1, "passed": True})

# Cost monotonicity for identical positions using the independent gross return stream.
gross = (1 + curve["return"]) / (1 - curve["cost"]) - 1
nocost_nav = (1 + gross).cumprod()
assert (curve.nav <= nocost_nav + 1e-11).all()

# Fault injection uses an observed real asset switch; mark a traded price as ffilled.
switch = curve.index[(curve.position_before != curve.position) & curve.position.ne("CASH")][-1]
switch_loc = prices.index.get_loc(switch)
fault_flags = flags.iloc[:switch_loc+1].copy()
asset = curve.at[switch, "position"]
fault_flags.at[switch, asset] = True
fault = bot.build_curves(prices.iloc[:switch_loc+1], bot._build_config(switch), fault_flags)[0].iloc[-1]
assert fault.trade_blocked_by_stale_price and fault.turnover == 0 and fault.position == fault.position_before

metrics = []
for label, start, end in bot._default_performance_ranges_for_daily(daily, prices.index[-1], prices.index[0])[:5]:
    actual = bot.calc_performance(daily, start, end)
    sub = oracle.loc[start:end]
    rebased = sub.nav / sub.nav.iloc[0]
    annual = float(rebased.iloc[-1] ** (252/(len(sub)-1)) - 1)
    mdd = float((rebased / rebased.cummax() - 1).min())
    assert abs(actual["annual"] - annual) < 1e-12
    assert abs(actual["maxdd"] - mdd) < 1e-12
    metrics.append({"window": label, "start": actual["start"], "end": actual["end"], "rows": len(sub), "annual": annual, "maxdd": mdd})

oracle.to_csv(OUT / "independent_ledger.csv.gz", index_label="date")
pd.DataFrame(metrics).to_csv(OUT / "window_metrics.csv", index=False)
result = {"status": "PASS", "new_confirmed_math_bugs": [], "code_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
          "input": str(INPUT), "raw_sha256": manifest["files"]["raw_prices_qfq.csv.gz"], "rows": len(raw),
          "start": str(raw.index[0].date()), "end": str(raw.index[-1].date()), "source": source_name,
          "oracle": "closed-form centered WLS and independent shares/cash ledger; same documented multiplicative cost convention",
          "oracle_max_diff": diffs, "score_max_abs_diff": score_diffs, "saved_official_parity": saved_diffs,
          "prefix_checks": prefix_results, "cost_monotonicity": True,
          "diagnostic_stale_leg_injection": {"date": str(switch.date()), "asset": asset, "blocked": True, "not_actual_market_fault": True},
          "metrics": metrics,
          "limitations": ["frozen historical replay through 2026-09-30, not current quotes", "same-close paper convention retained", "No point-in-time corporate-action or actual fill certification", "Network download replaced only with hash-verified real archive; archived calendar used"]}
(OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
