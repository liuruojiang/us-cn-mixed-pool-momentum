"""Independent six-ETF L2 price-to-ledger and performance audit.

Does not import the production strategy. Data and model conventions are frozen
in the accompanying L0/L1 records. Run with Python from repository root.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
L1 = ROOT / "outputs/recert_l1_20260926"
PRICES = L1 / "prices_aligned_qfq_through_20260924.csv.gz"
FLAGS = L1 / "price_ffill_flags_through_20260924.csv.gz"
FORMAL = OUT / "formal_daily_20260924.csv.gz"
OLD = ROOT / "outputs/subd_six_etf_v1_3_acceptance_20260904/daily.csv.gz"
ASSETS = ("159915.SZ", "159941.SZ", "513030.SH", "513520.SH", "159985.SZ", "518880.SH")
COST_RATE = 0.001
ANNUAL_DAYS = 252
EPS = 1e-11


def independent_score(raw: np.ndarray) -> tuple[float, float]:
    """Weighted OLS via moments, separate from the production polyfit call."""
    if raw.shape[0] != 25 or not np.isfinite(raw).all() or (raw <= 0).any():
        return math.nan, math.nan
    y = np.log(raw)
    if np.ptp(y) <= 1e-12:
        return math.nan, math.nan
    y -= y[0]
    x = np.arange(25, dtype=float)
    w = np.arange(1, 26, dtype=float)
    sw = w.sum()
    mx = np.dot(w, x) / sw
    my = np.dot(w, y) / sw
    dx, dy = x - mx, y - my
    sxx = np.dot(w, dx * dx)
    sxy = np.dot(w, dx * dy)
    syy = np.dot(w, dy * dy)
    if syy <= 0:
        return math.nan, math.nan
    slope = sxy / sxx
    residual = dy - slope * dx
    r2 = max(0.0, 1.0 - np.dot(w, residual * residual) / syy)
    score = math.expm1(slope * ANNUAL_DAYS)
    return score, r2


def rebuild(prices: pd.DataFrame, flags: pd.DataFrame) -> pd.DataFrame:
    """Reconstruct signals, shares, cash, fees, and NAV from only L1 inputs."""
    p = prices.loc[:, ASSETS].to_numpy(dtype=float)
    f = flags.loc[:, ASSETS].to_numpy(dtype=bool)
    dates = prices.index
    held = "CASH"
    shares = 0.0
    cash = 1.0
    fee_total = 0.0
    rows = []
    for i, day in enumerate(dates):
        old = held
        prev_wealth = cash if old == "CASH" else shares * p[i - 1, ASSETS.index(old)]
        if i == 0:
            prev_wealth = 1.0
        marked_wealth = cash if old == "CASH" else shares * p[i, ASSETS.index(old)]
        gross_ret = marked_wealth / prev_wealth - 1.0
        eligible = {}
        if i >= 24:
            for j, asset in enumerate(ASSETS):
                score, r2 = independent_score(p[i - 24 : i + 1, j])
                if 0.5 < score < 5.5 and r2 >= 0.25:
                    eligible[asset] = score
        desired = max(eligible, key=eligible.get) if eligible else "CASH"
        blocked = False
        if desired != old:
            old_stale = old != "CASH" and f[i, ASSETS.index(old)]
            new_stale = desired != "CASH" and f[i, ASSETS.index(desired)]
            blocked = bool(old_stale or new_stale)
        target = old if blocked else desired
        turnover = float((old != "CASH") + (target != "CASH")) if old != target else 0.0
        fee_fraction = turnover * COST_RATE
        fee_cash = marked_wealth * fee_fraction
        after_fee = marked_wealth - fee_cash
        if target == "CASH":
            held, shares, cash = "CASH", 0.0, after_fee
        else:
            held, shares, cash = target, after_fee / p[i, ASSETS.index(target)], 0.0
        fee_total += fee_cash
        nav = cash if held == "CASH" else shares * p[i, ASSETS.index(held)]
        net_ret = nav / prev_wealth - 1.0
        rows.append({
            "date": day, "position_before": old, "position": held,
            "desired": desired, "stale_blocked": blocked,
            "shares": shares, "cash": cash, "marked_wealth": marked_wealth,
            "fee_cash": fee_cash, "fee_cash_cumulative": fee_total,
            "turnover": turnover, "cost": fee_fraction,
            "gross_return": gross_ret, "return": net_ret, "nav": nav,
        })
    return pd.DataFrame(rows).set_index("date")


def metrics(curve: pd.DataFrame) -> list[dict]:
    results = []
    for label, width in (("Full", None), ("10Y", 2520), ("5Y", 1260), ("3Y", 756), ("1Y", 252)):
        sub = curve if width is None else curve.iloc[-width:]
        n = len(sub)
        if n < 2:
            results.append({"window": label, "reason": "fewer than two price rows"})
            continue
        # The first row of a window is an already established NAV base.
        # Thus its return is excluded, and annualization uses N-1 changes.
        rel = sub["nav"].to_numpy(dtype=float) / float(sub["nav"].iloc[0])
        peak = np.maximum.accumulate(np.r_[1.0, rel])
        dd = np.r_[1.0, rel] / peak - 1.0
        trough = int(np.argmin(dd)) - 1
        peak_idx = int(np.argmax(rel[: trough + 1])) if trough >= 0 else -1
        total = float(rel[-1] - 1.0)
        annual_corrected = (1.0 + total) ** (252.0 / (n - 1)) - 1.0
        annual_formal_convention = (1.0 + total) ** (252.0 / n) - 1.0
        results.append({
            "window": label, "start": str(sub.index[0].date()),
            "end": str(sub.index[-1].date()), "rows": n,
            "total": total, "annual_n_minus_1": annual_corrected,
            "annual_formal_n": annual_formal_convention,
            "annual_denominator_difference_pp": 100 * (annual_corrected - annual_formal_convention),
            "maxdd_with_initial_one": float(np.min(dd)),
            "peak_date": str(sub.index[peak_idx].date()) if peak_idx >= 0 else "initial_nav_1",
            "trough_date": str(sub.index[trough].date()) if trough >= 0 else "initial_nav_1",
        })
    return results


def compare(a: pd.DataFrame, b: pd.DataFrame, label: str) -> dict:
    b = b.copy()
    if "date" in b.columns:
        b["date"] = pd.to_datetime(b["date"])
        b = b.set_index("date")
    b.index = pd.to_datetime(b.index)
    common = a.index.intersection(b.index)
    result = {"label": label, "rows_common": len(common), "rows_a": len(a), "rows_b": len(b)}
    first = None
    for key in ("position_before", "position", "turnover", "cost", "gross_return", "return", "nav"):
        if key not in b:
            result[key] = {"missing_formal_column": True}
            continue
        x, y = a.loc[common, key], b.loc[common, key]
        if key.startswith("position"):
            bad = x.astype(str).to_numpy() != y.astype(str).to_numpy()
            maximum = None
        else:
            delta = np.abs(x.to_numpy(dtype=float) - y.to_numpy(dtype=float))
            bad = ~np.isfinite(delta) | (delta > EPS)
            maximum = float(np.nanmax(delta))
        dates = common[bad]
        result[key] = {"bad_count": int(np.count_nonzero(bad)), "max_abs": maximum,
                       "first_bad": str(dates[0].date()) if len(dates) else None}
        if len(dates) and (first is None or dates[0] < first):
            first = dates[0]
    result["first_difference"] = str(first.date()) if first is not None else None
    return result


def main() -> None:
    p = pd.read_csv(PRICES, parse_dates=["date"]).set_index("date")
    f = pd.read_csv(FLAGS, parse_dates=["date"]).set_index("date")
    if not p.index.equals(f.index) or len(p) != 3594:
        raise RuntimeError("L1 price and flag calendars diverged")
    if not p[list(ASSETS)].notna().any(axis=1).all():
        raise RuntimeError("No listed ETF on an input day")
    a = rebuild(p, f)
    a.to_csv(OUT / "agent_b_rebuilt_daily.csv.gz", compression="gzip", float_format="%.17g")
    comparisons = []
    for label, path in (("old_frozen_3578", OLD), ("new_formal_3594", FORMAL)):
        if path.exists():
            comparisons.append(compare(a, pd.read_csv(path), label))
    fee_days = a.loc[a.cost > 0]
    if fee_days.empty:
        raise RuntimeError("No trade fees appeared")
    # Inject omitted and doubled fees into one actual swap. Both must fail
    # the price-to-NAV identity against our independent result.
    swap = fee_days.loc[fee_days.turnover == 2].iloc[0]
    omitted_fee_error = abs((1 + float(swap.gross_return)) - (1 + float(swap["return"])))
    doubled_fee_error = abs((1 + float(swap.gross_return)) * (1 - 2 * float(swap.cost)) - (1 + float(swap["return"])))
    if omitted_fee_error < 0.001 or doubled_fee_error < 0.001:
        raise RuntimeError("Fee counterexamples did not separate")
    report = {
        "inputs": {"prices": str(PRICES), "flags": str(FLAGS), "formal": str(FORMAL), "old": str(OLD)},
        "rows": len(a), "start": str(a.index[0].date()), "end": str(a.index[-1].date()),
        "transactions": int((a.turnover > 0).sum()),
        "switches_double_sided": int((a.turnover == 2).sum()),
        "turnover_sum": float(a.turnover.sum()), "cost_fraction_sum": float(a.cost.sum()),
        "fee_cash_sum": float(a.fee_cash.sum()),
        "cost_factor_same_path": float(np.prod(1.0 - a.cost.to_numpy(dtype=float))),
        "no_cost_nav_same_path": float(a.nav.iloc[-1] / np.prod(1.0 - a.cost.to_numpy(dtype=float))),
        "stale_blocked_days": [str(x.date()) for x in a.index[a.stale_blocked]],
        "cash_days_end": int((a.position == "CASH").sum()),
        "nav_end": float(a.nav.iloc[-1]),
        "asset_account_invariant_max_abs": float(np.max(np.abs(a.nav.to_numpy() - (a.cash.to_numpy() + a.shares.to_numpy() * np.array([p.at[d, h] if h != "CASH" else 0.0 for d, h in zip(a.index, a.position)]))))),
        "fee_counterexample": {"date": str(swap.name.date()), "turnover": float(swap.turnover),
                               "cost": float(swap.cost), "omitted_fee_return_error": omitted_fee_error,
                               "double_fee_return_error": doubled_fee_error},
        "windows": metrics(a), "comparisons": comparisons,
    }
    (OUT / "agent_b_independent_ledger.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
