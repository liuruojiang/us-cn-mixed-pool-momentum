"""Independent L2 cash/unit replay from the frozen L1 six-ETF price panel.

Does not import the strategy module or use its signal/account/metric helpers.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
L1 = ROOT / "outputs" / "recert_l1_20260926"
SYMBOLS = ["159915.SZ", "159941.SZ", "513030.SH", "513520.SH", "159985.SZ", "518880.SH"]
LOOKBACK = 25
COST_RATE = .001
TRADING_DAYS = 252


def read_panel(name: str) -> pd.DataFrame:
    frame = pd.read_csv(L1 / name, parse_dates=["date"]).set_index("date")
    assert frame.index.is_unique and frame.index.is_monotonic_increasing
    assert list(frame.columns) == SYMBOLS
    return frame


def independent_signal(window: np.ndarray) -> tuple[float, float]:
    if len(window) != LOOKBACK or not np.isfinite(window).all() or (window <= 0).any():
        return math.nan, math.nan
    y = np.log(window)
    if np.ptp(y) <= 1e-12:
        return math.nan, math.nan
    y -= y[0]
    x = np.arange(LOOKBACK, dtype=float)
    w = np.arange(1, LOOKBACK + 1, dtype=float)
    xbar = np.dot(w, x) / w.sum()
    ybar = np.dot(w, y) / w.sum()
    slope = np.dot(w, (x - xbar) * (y - ybar)) / np.dot(w, (x - xbar) ** 2)
    intercept = ybar - slope * xbar
    sst = np.dot(w, (y - ybar) ** 2)
    if sst <= 0:
        return math.nan, math.nan
    sse = np.dot(w, (y - (intercept + slope * x)) ** 2)
    annual_slope = slope * TRADING_DAYS
    if not math.isfinite(annual_slope) or annual_slope > math.log(np.finfo(float).max):
        return math.nan, max(0.0, 1.0 - sse / sst)
    return math.expm1(annual_slope), max(0.0, 1.0 - sse / sst)


def replay(prices: pd.DataFrame, flags: pd.DataFrame, signal_lag: int = 0,
           cost_rate: float = COST_RATE) -> pd.DataFrame:
    assert signal_lag in (0, 1)
    assert 0 <= cost_rate < .5
    cash = 1.0
    units = 0.0
    held = "CASH"
    prior_nav = 1.0
    records = []
    values = prices.to_numpy(dtype=float)
    blocked_dates = flags.astype(bool)
    for t, day in enumerate(prices.index):
        old_held = held
        old_cash, old_units = cash, units
        px = dict(zip(SYMBOLS, values[t]))
        previous_px = dict(zip(SYMBOLS, values[t-1])) if t else {}
        if old_held != "CASH":
            assert math.isfinite(px[old_held]) and px[old_held] > 0
            before_fee = cash + units * px[old_held]
            old_asset_return = px[old_held] / previous_px[old_held] - 1.0
        else:
            before_fee = cash
            old_asset_return = 0.0

        candidates = {}
        signal_t = t - signal_lag
        if signal_t >= LOOKBACK - 1:
            for j, sym in enumerate(SYMBOLS):
                score, r2 = independent_signal(values[signal_t-LOOKBACK+1:signal_t+1, j].copy())
                if .5 < score < 5.5 and r2 >= .25:
                    candidates[sym] = score
        desired = max(candidates, key=candidates.get) if candidates else "CASH"
        blocked = False
        traded = desired != old_held
        if traded:
            legs = [s for s in (old_held, desired) if s != "CASH"]
            blocked = any(bool(blocked_dates.at[day, s]) for s in legs)
            traded = not blocked
        target = desired if traded else old_held
        turnover = (int(old_held != "CASH") + int(target != "CASH")) if traded else 0
        fee = before_fee * cost_rate * turnover
        post_fee = before_fee - fee
        if target == "CASH":
            cash, units = post_fee, 0.0
        else:
            cash, units = 0.0, post_fee / px[target]
        held = target
        nav = cash + (units * px[held] if held != "CASH" else 0.0)
        assert abs((old_cash + (old_units * px[old_held] if old_held != "CASH" else 0.0)) - fee - nav) < 1e-10
        records.append({
            "date": day, "position_before": old_held, "candidate": desired,
            "position": held, "trade_blocked_by_stale_price": blocked,
            "turnover": turnover, "cost": cost_rate * turnover,
            "cash": cash, "units": units, "equity": nav-cash,
            "pretrade_nav": before_fee, "fee_amount": fee, "nav": nav,
            "asset_return": old_asset_return, "gross_return": before_fee / prior_nav - 1.0,
            "return": nav / prior_nav - 1.0,
        })
        prior_nav = nav
    return pd.DataFrame(records)


def metrics(daily: pd.DataFrame) -> list[dict]:
    out = []
    for name, length in [("Full", None), ("10Y", 2520), ("5Y", 1260), ("3Y", 756), ("1Y", 252)]:
        sub = daily if length is None else daily.tail(length)
        ret = sub["return"].to_numpy(dtype=float).copy()
        ret[0] = 0.0
        wealth = np.cumprod(1 + ret)
        peak = np.maximum.accumulate(np.r_[1.0, wealth])[1:]
        window_nav_ratio = float(sub.nav.iloc[-1] / sub.nav.iloc[0])
        annual_nav_anchor = window_nav_ratio ** (252 / (len(sub) - 1)) - 1 if len(sub) > 1 else math.nan
        out.append({"window": name, "start": sub.date.iloc[0].strftime("%Y-%m-%d"),
                    "end": sub.date.iloc[-1].strftime("%Y-%m-%d"), "rows": len(sub),
                    "annual": float(wealth[-1] ** (252 / len(sub)) - 1),
                    "annual_nav_anchor_n_minus_1": annual_nav_anchor,
                    "maxdd": float(np.min(wealth / peak - 1)),
                    "trades": int((sub.turnover > 0).sum())})
    return out


def main() -> None:
    raw = read_panel("prices_raw_qfq_through_20260924.csv.gz")
    aligned = read_panel("prices_aligned_qfq_through_20260924.csv.gz")
    flags = read_panel("price_ffill_flags_through_20260924.csv.gz")
    assert raw.index.equals(aligned.index) and raw.index.equals(flags.index)
    assert raw.shape == (3594, 6) and str(raw.index[-1].date()) == "2026-09-24"
    assert int(flags.to_numpy(dtype=bool).sum()) == 2
    day = replay(aligned, flags)
    assert np.isfinite(day[["nav", "return", "cash", "equity", "fee_amount"]]).all().all()
    assert (day.nav > 0).all() and (day.cash >= 0).all() and (day.equity >= 0).all()
    assert (day.turnover.isin([0, 1, 2])).all()
    assert np.allclose(day.nav, day.cash + day.equity, atol=1e-11)
    day.to_csv(OUT / "agent_a_daily.csv.gz", index=False, compression="gzip")
    delayed = replay(aligned, flags, signal_lag=1)
    no_cost = replay(aligned, flags, cost_rate=0)
    assert day.position.equals(no_cost.position) and day.turnover.equals(no_cost.turnover)
    assert (day.nav <= no_cost.nav + 1e-10).all()
    result = {"metrics": metrics(day), "trades": int((day.turnover > 0).sum()),
              "switches": int((day.turnover == 2).sum()),
              "fees_total_currency": float(day.fee_amount.sum()),
              "stale_trade_blocks": day.loc[day.trade_blocked_by_stale_price, "date"].dt.strftime("%Y-%m-%d").tolist(),
              "first_trade": day.loc[day.turnover > 0, "date"].iloc[0].strftime("%Y-%m-%d"),
              "latest_position": day.position.iloc[-1],
              "latest_nav": float(day.nav.iloc[-1]),
              "no_cost_same_path_latest_nav": float(no_cost.nav.iloc[-1]),
              "adversarial_t_plus_1_close": {
                  "latest_nav": float(delayed.nav.iloc[-1]),
                  "metrics": metrics(delayed),
                  "first_changed_date": str(day.loc[day.position.ne(delayed.position), "date"].iloc[0].date()),
              }}
    formal_path = OUT / "formal_daily_20260924.csv.gz"
    if formal_path.exists():
        formal = pd.read_csv(formal_path, parse_dates=["date"])
        assert formal.date.equals(day.date)
        exact_fields = {"position_before": "position_before", "candidate": "best_candidate",
                        "position": "position", "trade_blocked_by_stale_price": "trade_blocked_by_stale_price",
                        "turnover": "turnover", "cost": "cost"}
        exact_mismatches = {}
        for left, right in exact_fields.items():
            mismatched = day[left].fillna("NA").astype(str) != formal[right].fillna("NA").astype(str)
            exact_mismatches[left] = int(mismatched.sum())
        numerical = {}
        for field in ("asset_return", "gross_return", "return", "nav"):
            err = np.abs(day[field].to_numpy(dtype=float) - formal[field].to_numpy(dtype=float))
            bad = ~np.isclose(day[field], formal[field], rtol=1e-10, atol=1e-11)
            numerical[field] = {"max_abs": float(err.max()),
                                "first_nonclose_date": str(day.date[bad].iloc[0].date()) if bad.any() else None}
        assert all(v == 0 for v in exact_mismatches.values())
        assert all(v["first_nonclose_date"] is None for v in numerical.values())
        result["formal_parity"] = {"rows": len(formal), "exact_mismatches": exact_mismatches,
                                   "numerical": numerical}
    (OUT / "agent_a_results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
