"""Independent L4 score-gate ablation and cash/share ledger.

Run from the repository root. This file imports no production strategy code.
The frozen L1 price panel and stale-price flags are the only market inputs.
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
L2 = ROOT / "outputs/recert_l2_20260926"
ASSETS = ("159915.SZ", "159941.SZ", "513030.SH", "513520.SH", "159985.SZ", "518880.SH")
FEE = 0.001
PERIODS = (("Full", None), ("10Y", 2520), ("5Y", 1260), ("3Y", 756), ("1Y", 252))
ARMS = {
    "formal_rebuilt": (0.5, 5.5, 0.25),
    "lower_off": (-math.inf, 5.5, 0.25),
    "upper_off": (0.5, math.inf, 0.25),
    "r2_off": (0.5, 5.5, -math.inf),
}


def weighted_regression(panel: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Closed-form weighted slope and residual R², independently of bot functions."""
    price = panel.loc[:, ASSETS].to_numpy(float)
    scores = np.full(price.shape, np.nan)
    r2 = np.full(price.shape, np.nan)
    x = np.arange(25, dtype=float)
    weights = np.arange(1, 26, dtype=float)
    sw = float(np.sum(weights))
    xbar = float(np.dot(weights, x) / sw)
    den = float(np.dot(weights, (x - xbar) ** 2))
    for day in range(24, len(price)):
        for j in range(len(ASSETS)):
            window = price[day - 24 : day + 1, j]
            if not np.isfinite(window).all() or np.any(window <= 0):
                continue
            y = np.log(window)
            if float(np.ptp(y)) <= 1e-12:
                continue
            y = y - y[0]
            ybar = float(np.dot(weights, y) / sw)
            slope = float(np.dot(weights, (x - xbar) * (y - ybar)) / den)
            intercept = ybar - slope * xbar
            ss_total = float(np.dot(weights, (y - ybar) ** 2))
            if ss_total <= 0:
                continue
            residual = y - (slope * x + intercept)
            ss_residual = float(np.dot(weights, residual**2))
            r2[day, j] = max(0.0, 1.0 - ss_residual / ss_total)
            exponent = slope * 252.0
            if np.isfinite(exponent) and exponent <= math.log(np.finfo(float).max):
                scores[day, j] = math.expm1(exponent)
    return scores, r2


def desired_asset(score: np.ndarray, quality: np.ndarray, filters: tuple[float, float, float]) -> tuple[str, int]:
    lower, upper, r2_min = filters
    eligible = np.isfinite(score) & np.isfinite(quality) & (score > lower) & (score < upper) & (quality >= r2_min)
    count = int(np.count_nonzero(eligible))
    if count == 0:
        return "CASH", count
    return ASSETS[int(np.argmax(np.where(eligible, score, -np.inf)))], count


def eligibility_matrix(scores: np.ndarray, quality: np.ndarray, filters: tuple[float, float, float]) -> np.ndarray:
    lower, upper, r2_min = filters
    return np.isfinite(scores) & np.isfinite(quality) & (scores > lower) & (scores < upper) & (quality >= r2_min)


def replay(panel: pd.DataFrame, flags: pd.DataFrame, scores: np.ndarray, r2: np.ndarray,
           filters: tuple[float, float, float]) -> pd.DataFrame:
    px = panel.loc[:, ASSETS].to_numpy(float)
    stale = flags.loc[:, ASSETS].to_numpy(bool)
    lookup = {asset: j for j, asset in enumerate(ASSETS)}
    position = "CASH"
    cash = 1.0
    shares = 0.0
    prev_nav = 1.0
    no_cost_nav = 1.0
    rows = []
    for t, date in enumerate(panel.index):
        before = position
        marked = cash if before == "CASH" else shares * px[t, lookup[before]]
        if not np.isfinite(marked) or marked <= 0:
            raise AssertionError(f"Invalid carried mark at {date}: {before}")
        desired, eligible_count = desired_asset(scores[t], r2[t], filters)
        would_trade = desired != before
        touched = [asset for asset in (before, desired) if asset != "CASH"] if would_trade else []
        blocked = bool(any(stale[t, lookup[asset]] for asset in touched))
        after = before if blocked else desired
        turnover = 0 if after == before else int(before != "CASH") + int(after != "CASH")
        cost_fraction = turnover * FEE
        fee_amount = marked * cost_fraction
        net_wealth = marked - fee_amount
        if after == "CASH":
            cash, shares = net_wealth, 0.0
        else:
            trade_price = px[t, lookup[after]]
            if not np.isfinite(trade_price) or trade_price <= 0:
                raise AssertionError(f"Invalid trade price at {date}: {after}")
            shares, cash = net_wealth / trade_price, 0.0
        position = after
        nav = cash if after == "CASH" else shares * px[t, lookup[after]]
        gross_return = marked / prev_nav - 1.0
        if abs(nav - prev_nav * (1.0 + gross_return) * (1.0 - cost_fraction)) > 1e-10 * max(1.0, nav):
            raise AssertionError(f"NAV bridge failed at {date}")
        no_cost_nav *= marked / prev_nav
        if nav > no_cost_nav + 1e-9:
            raise AssertionError(f"Costed curve exceeded same-path no-cost curve at {date}")
        rows.append({
            "date": date, "position_before": before, "desired": desired, "position": after,
            "eligible_count": eligible_count,
            "selected_score": float(scores[t, lookup[desired]]) if desired != "CASH" else math.nan,
            "selected_r2": float(r2[t, lookup[desired]]) if desired != "CASH" else math.nan,
            "trade_blocked_by_stale_price": blocked,
            "shares": shares, "cash": cash, "gross_return": gross_return,
            "turnover": turnover, "cost": cost_fraction, "fee_amount": fee_amount,
            "return": nav / prev_nav - 1.0, "nav": nav, "same_path_no_cost_nav": no_cost_nav,
        })
        prev_nav = nav
    return pd.DataFrame(rows).set_index("date")


def metrics(curve: pd.DataFrame, arm: str) -> list[dict]:
    out = []
    for period, width in PERIODS:
        part = curve if width is None else curve.iloc[-width:]
        relative = part.nav.to_numpy(float) / float(part.nav.iloc[0])
        running_peak = np.maximum.accumulate(relative)
        drawdown = relative / running_peak - 1.0
        out.append({
            "arm": arm, "window": period, "start": str(part.index[0].date()),
            "end": str(part.index[-1].date()), "rows": len(part),
            "annual_n_minus_1": float(relative[-1] ** (252.0 / (len(part) - 1)) - 1.0),
            "maxdd": float(drawdown.min()),
            "trade_days": int(np.count_nonzero(part.turnover.to_numpy(float) > 0)),
            "turnover_sum": float(part.turnover.sum()),
            "fee_amount_initial_capital_units": float(part.fee_amount.sum()),
            "cash_days": int(np.count_nonzero(part.position.to_numpy() == "CASH")),
        })
    return out


def main() -> None:
    OUT.mkdir(exist_ok=True, parents=True)
    panel = pd.read_csv(L1 / "prices_aligned_qfq_through_20260924.csv.gz", parse_dates=["date"]).set_index("date")
    flags = pd.read_csv(L1 / "price_ffill_flags_through_20260924.csv.gz", parse_dates=["date"]).set_index("date")
    formal = pd.read_csv(L2 / "formal_daily_20260924.csv.gz", parse_dates=["date"]).set_index("date")
    if not panel.index.equals(flags.index) or not panel.index.equals(formal.index):
        raise AssertionError("L1/L2 date index divergence")
    if len(panel) != 3594 or str(panel.index[-1].date()) != "2026-09-24":
        raise AssertionError("Unexpected frozen input boundary")
    scores, quality = weighted_regression(panel)
    curves = {}
    all_metrics = []
    for name, filters in ARMS.items():
        curve = replay(panel, flags, scores, quality, filters)
        curve.to_csv(OUT / f"agent_b_{name}_daily.csv.gz", compression="gzip", float_format="%.17g")
        curves[name] = curve
        all_metrics.extend(metrics(curve, name))
    metric_frame = pd.DataFrame(all_metrics)
    metric_frame.to_csv(OUT / "agent_b_metrics.csv", index=False, float_format="%.17g")
    base = curves["formal_rebuilt"]
    base_eligible = eligibility_matrix(scores, quality, ARMS["formal_rebuilt"])
    formal_comparison = {}
    for field in ("position_before", "position", "turnover", "cost", "gross_return", "return", "nav"):
        actual, expected = base[field].to_numpy(), formal[field].to_numpy()
        if field.startswith("position"):
            formal_comparison[field + "_mismatches"] = int(np.count_nonzero(actual != expected))
        else:
            formal_comparison[field + "_max_abs"] = float(np.max(np.abs(actual.astype(float) - expected.astype(float))))
    summary = {
        "data_end": str(panel.index[-1].date()), "rows": len(panel), "formal_rebuild_parity": formal_comparison,
        "arms": {},
    }
    for name, curve in curves.items():
        newly_eligible = eligibility_matrix(scores, quality, ARMS[name]) & ~base_eligible
        desired_diff = int(np.count_nonzero(curve.desired.to_numpy() != base.desired.to_numpy()))
        position_diff = int(np.count_nonzero(curve.position.to_numpy() != base.position.to_numpy()))
        mismatches = curve.loc[curve.desired.ne(base.desired)]
        lower, upper, quality_floor = ARMS[name]
        summary["arms"][name] = {
            "filters": {
                "score_lower_strict": lower if math.isfinite(lower) else "off",
                "score_upper_strict": upper if math.isfinite(upper) else "off",
                "r2_min_inclusive": quality_floor if math.isfinite(quality_floor) else "off",
            },
            "end_nav": float(curve.nav.iloc[-1]),
            "trade_days": int(np.count_nonzero(curve.turnover.to_numpy(float) > 0)),
            "two_sided_switches": int(np.count_nonzero(curve.turnover.to_numpy(float) == 2)),
            "turnover_sum": float(curve.turnover.sum()), "cost_rate_sum": float(curve.cost.sum()),
            "fee_amount_initial_capital_units": float(curve.fee_amount.sum()),
            "cash_days": int(np.count_nonzero(curve.position.to_numpy() == "CASH")),
            "stale_blocked_days": [str(d.date()) for d in curve.index[curve.trade_blocked_by_stale_price]],
            "new_eligible_asset_days": int(np.count_nonzero(newly_eligible)),
            "days_with_new_eligible_asset": int(np.count_nonzero(newly_eligible.any(axis=1))),
            "desired_diff_days_vs_formal": desired_diff, "position_diff_days_vs_formal": position_diff,
            "first_desired_diff": str(mismatches.index[0].date()) if len(mismatches) else None,
            "same_path_no_cost_end_nav": float(curve.same_path_no_cost_nav.iloc[-1]),
        }
    # Real counterexamples for each mutation; each changed filter must be exercised.
    if any(summary["arms"][arm]["desired_diff_days_vs_formal"] == 0 for arm in ("lower_off", "upper_off", "r2_off")):
        raise AssertionError("An ablation has no signal counterexample")
    (OUT / "agent_b_audit.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
