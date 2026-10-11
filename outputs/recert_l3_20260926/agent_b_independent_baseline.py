"""L3 independent historical naive baseline from the frozen L1 inputs.

No production strategy functions or L2 ledger functions are imported. Run from
the repository root with: python -X utf8 outputs/recert_l3_20260926/agent_b_independent_baseline.py
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
ONE_WAY = 0.001
WINDOWS = (("Full", None), ("10Y", 2520), ("5Y", 1260), ("3Y", 756), ("1Y", 252))


def weighted_score(prices: np.ndarray) -> float:
    """Weighted covariance form of the 25 day annualized log slope."""
    if prices.size != 25 or not np.isfinite(prices).all() or np.any(prices <= 0):
        return math.nan
    logged = np.log(prices)
    if np.ptp(logged) <= 1e-12:
        return math.nan
    day = np.arange(25, dtype=float)
    weight = np.arange(1, 26, dtype=float)
    mean_day = np.sum(weight * day) / np.sum(weight)
    mean_log = np.sum(weight * logged) / np.sum(weight)
    slope = np.sum(weight * (day - mean_day) * (logged - mean_log)) / np.sum(weight * (day - mean_day) ** 2)
    annual_log = slope * 252.0
    return math.expm1(annual_log) if annual_log < 709.0 else math.nan


def compute_scores(prices: pd.DataFrame) -> np.ndarray:
    array = prices.loc[:, ASSETS].to_numpy(dtype=float)
    scores = np.full(array.shape, np.nan)
    for t in range(24, len(array)):
        for j in range(len(ASSETS)):
            scores[t, j] = weighted_score(array[t - 24 : t + 1, j])
    return scores


def choose(row: np.ndarray, lo: float, hi: float) -> str:
    eligible = np.isfinite(row) & (row > lo) & (row < hi)
    if not eligible.any():
        return "CASH"
    return ASSETS[int(np.argmax(np.where(eligible, row, -np.inf)))]


def replay(prices: pd.DataFrame, flags: pd.DataFrame, scores: np.ndarray) -> pd.DataFrame:
    px = prices.loc[:, ASSETS].to_numpy(dtype=float)
    stale = flags.loc[:, ASSETS].to_numpy(dtype=bool)
    asset_index = {asset: j for j, asset in enumerate(ASSETS)}
    position = "CASH"
    cash, shares = 1.0, 0.0
    prior_nav = 1.0
    no_cost_nav = 1.0
    fee_total = 0.0
    rows = []
    for t, day in enumerate(prices.index):
        before = position
        wealth_before_trade = cash if before == "CASH" else shares * px[t, asset_index[before]]
        if not np.isfinite(wealth_before_trade) or wealth_before_trade <= 0:
            raise ValueError(f"Invalid marked wealth on {day}: {before}")
        desired = choose(scores[t], 0.0, 5.0)
        changed = desired != before
        blocked = changed and any(
            bool(stale[t, asset_index[asset]]) for asset in (before, desired) if asset != "CASH"
        )
        after = before if blocked else desired
        turnover = 0 if after == before else int(before != "CASH") + int(after != "CASH")
        fee_rate = ONE_WAY * turnover
        fee_amount = wealth_before_trade * fee_rate
        closing_wealth = wealth_before_trade - fee_amount
        if after == "CASH":
            cash, shares = closing_wealth, 0.0
        else:
            trade_price = px[t, asset_index[after]]
            if not np.isfinite(trade_price) or trade_price <= 0:
                raise ValueError(f"Invalid trade price on {day}: {after}")
            shares, cash = closing_wealth / trade_price, 0.0
        position = after
        nav = cash if position == "CASH" else shares * px[t, asset_index[position]]
        if not np.isclose(nav, closing_wealth, rtol=0, atol=1e-11):
            raise AssertionError(f"Shares plus cash failed on {day}")
        no_cost_nav *= wealth_before_trade / prior_nav
        fee_total += fee_amount
        rows.append({
            "date": day, "position_before": before, "desired": desired, "position": after,
            "stale_blocked": blocked, "eligible_count": int(np.count_nonzero(np.isfinite(scores[t]) & (scores[t] > 0) & (scores[t] < 5))),
            "selected_score": float(scores[t, asset_index[desired]]) if desired != "CASH" else math.nan,
            "shares": shares, "cash": cash, "wealth_before_trade": wealth_before_trade,
            "gross_return": wealth_before_trade / prior_nav - 1.0,
            "turnover": turnover, "cost": fee_rate, "fee_amount": fee_amount,
            "return": nav / prior_nav - 1.0, "nav": nav,
            "fee_amount_cumulative": fee_total,
            "no_cost_nav_same_path": no_cost_nav,
        })
        prior_nav = nav
    result = pd.DataFrame(rows).set_index("date")
    if np.any(result["no_cost_nav_same_path"] + 1e-11 < result["nav"]):
        raise AssertionError("Costed NAV exceeded the same-path no-cost NAV")
    return result


def window_metrics(curve: pd.DataFrame, arm: str) -> list[dict]:
    out = []
    for label, width in WINDOWS:
        sub = curve if width is None else curve.iloc[-width:]
        n = len(sub)
        if n < 2:
            out.append({"arm": arm, "window": label, "reason": "less than 2 rows"})
            continue
        relative_nav = sub.nav.to_numpy(dtype=float) / float(sub.nav.iloc[0])
        peaks = np.maximum.accumulate(relative_nav)
        dd = relative_nav / peaks - 1
        out.append({
            "arm": arm, "window": label, "start": str(sub.index[0].date()),
            "end": str(sub.index[-1].date()), "rows": n,
            "annualized_n_minus_1": float(relative_nav[-1] ** (252.0 / (n - 1)) - 1),
            "max_drawdown": float(dd.min()),
            "window_trades": int((sub.turnover > 0).sum()) if "turnover" in sub else None,
            "window_turnover": float(sub.turnover.sum()) if "turnover" in sub else None,
        })
    return out


def main() -> None:
    price_path = L1 / "prices_aligned_qfq_through_20260924.csv.gz"
    flag_path = L1 / "price_ffill_flags_through_20260924.csv.gz"
    formal_path = L2 / "formal_daily_20260924.csv.gz"
    prices = pd.read_csv(price_path, parse_dates=["date"]).set_index("date")
    flags = pd.read_csv(flag_path, parse_dates=["date"]).set_index("date")
    formal = pd.read_csv(formal_path, parse_dates=["date"]).set_index("date")
    if not prices.index.equals(flags.index) or not prices.index.equals(formal.index) or len(prices) != 3594:
        raise AssertionError("L1 and L2 dates do not match")
    if str(prices.index[-1].date()) != "2026-09-24":
        raise AssertionError("Unexpected data cutoff")
    scores = compute_scores(prices)
    baseline = replay(prices, flags, scores)
    baseline.to_csv(OUT / "agent_b_baseline_daily.csv.gz", compression="gzip", float_format="%.17g")
    formal_metrics = window_metrics(formal, "formal_v1_3")
    baseline_metrics = window_metrics(baseline, "historical_base_0_5_r2_off")
    rows = []
    for b, f in zip(baseline_metrics, formal_metrics):
        if (b["window"], b["start"], b["end"], b["rows"]) != (f["window"], f["start"], f["end"], f["rows"]):
            raise AssertionError("Metric windows diverged")
        rows.append({
            "window": b["window"], "start": b["start"], "end": b["end"], "rows": b["rows"],
            "baseline_annualized_n_minus_1": b["annualized_n_minus_1"],
            "baseline_max_drawdown": b["max_drawdown"],
            "formal_annualized_n_minus_1": f["annualized_n_minus_1"],
            "formal_max_drawdown": f["max_drawdown"],
            "formal_minus_baseline_annual_pp": (f["annualized_n_minus_1"] - b["annualized_n_minus_1"]) * 100,
            "formal_minus_baseline_maxdd_pp": (f["max_drawdown"] - b["max_drawdown"]) * 100,
            "baseline_window_trades": b["window_trades"], "baseline_window_turnover": b["window_turnover"],
            "formal_window_trades": f["window_trades"], "formal_window_turnover": f["window_turnover"],
        })
    pd.DataFrame(rows).to_csv(OUT / "agent_b_five_windows.csv", index=False, float_format="%.17g")

    swap = baseline.loc[baseline.turnover == 2].iloc[0]
    omitted_fee_error = abs(float(swap.gross_return) - float(swap["return"]))
    doubled_fee_error = abs((1.0 + float(swap.gross_return)) * (1.0 - 2.0 * float(swap.cost)) - (1.0 + float(swap["return"])))
    if min(omitted_fee_error, doubled_fee_error) <= 0.001:
        raise AssertionError("Fee mutation was not detected")

    wrong_upper = [(str(day.date()), b, choose(scores[i], 0.0, math.inf))
                   for i, (day, b) in enumerate(zip(prices.index, baseline.desired))
                   if b != choose(scores[i], 0.0, math.inf)]
    wrong_lower = [(str(day.date()), b, choose(scores[i], 0.5, 5.0))
                   for i, (day, b) in enumerate(zip(prices.index, baseline.desired))
                   if b != choose(scores[i], 0.5, 5.0)]
    if not wrong_upper or not wrong_lower:
        raise AssertionError("Threshold mutations did not yield real counterexamples")
    old_path = ROOT / "quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/daily_outputs/r2_off_buffer_1.00.csv.gz"
    old = pd.read_csv(old_path, parse_dates=["date"]).set_index("date")
    if not old.index.equals(baseline.index[: len(old)]):
        raise AssertionError("Old frozen curve dates do not match baseline prefix")
    old_comparison = {"rows": len(old)}
    for name in ("position_before", "position", "turnover", "cost", "gross_return", "return", "nav"):
        left = baseline[name].iloc[: len(old)]
        right = old[name]
        if name.startswith("position"):
            old_comparison[name + "_mismatch"] = int(np.count_nonzero(left.to_numpy() != right.to_numpy()))
        else:
            old_comparison[name + "_max_abs"] = float(np.max(np.abs(left.to_numpy(float) - right.to_numpy(float))))
    a_path = OUT / "agent_a_independent_clean_daily.csv.gz"
    agent_a_comparison = None
    if a_path.exists():
        other = pd.read_csv(a_path, parse_dates=["date"]).set_index("date")
        if not baseline.index.equals(other.index):
            raise AssertionError("Agent A dates do not match")
        agent_a_comparison = {}
        for name in ("position_before", "position", "turnover", "cost", "gross_return", "return", "nav"):
            left, right = baseline[name], other[name]
            if name.startswith("position"):
                agent_a_comparison[name + "_mismatch"] = int(np.count_nonzero(left.to_numpy() != right.to_numpy()))
            else:
                agent_a_comparison[name + "_max_abs"] = float(np.max(np.abs(left.to_numpy(float) - right.to_numpy(float))))
    main_path = OUT / "baseline_daily_20260924.csv.gz"
    main_comparison = None
    if main_path.exists():
        main = pd.read_csv(main_path, parse_dates=["date"]).set_index("date")
        if not baseline.index.equals(main.index):
            raise AssertionError("Main baseline dates do not match")
        main_comparison = {"rows": len(main)}
        for name in ("position_before", "position", "turnover", "cost", "gross_return", "return", "nav"):
            left, right = baseline[name], main[name]
            if name.startswith("position"):
                main_comparison[name + "_mismatch"] = int(np.count_nonzero(left.to_numpy() != right.to_numpy()))
            else:
                main_comparison[name + "_max_abs"] = float(np.max(np.abs(left.to_numpy(float) - right.to_numpy(float))))
        main_comparison["desired_mismatch"] = int(np.count_nonzero(baseline.desired.to_numpy() != main.best_candidate.to_numpy()))
    main_metrics_path = OUT / "matched_metrics_20260924.csv"
    metric_comparison = None
    if main_metrics_path.exists():
        main_metrics = pd.read_csv(main_metrics_path)
        metric_comparison = {}
        for arm, annual_key, dd_key in (
            ("clean_baseline", "baseline_annualized_n_minus_1", "baseline_max_drawdown"),
            ("formal_v1_3", "formal_annualized_n_minus_1", "formal_max_drawdown"),
        ):
            subset = main_metrics.loc[main_metrics.arm == arm].set_index("window")
            metric_comparison[arm] = {
                "annual_max_abs": max(abs(float(row[annual_key]) - float(subset.at[row["window"], "annual_n_minus_1"])) for row in rows),
                "maxdd_max_abs": max(abs(float(row[dd_key]) - float(subset.at[row["window"], "maxdd"])) for row in rows),
            }
    report = {
        "source": {"prices": str(price_path), "flags": str(flag_path), "formal": str(formal_path)},
        "rows": len(baseline), "start": str(baseline.index[0].date()), "end": str(baseline.index[-1].date()),
        "parameters": {"lookback": 25, "linear_weights": "1..25", "score_filter": "strict 0 < Score < 5",
                       "r2_gate": None, "top": 1, "switch_buffer": 1.0, "allocation": 1.0,
                       "one_way_cost": ONE_WAY, "cash_annual_yield": 0.0},
        "trading_days": int((baseline.turnover > 0).sum()), "two_sided_switch_days": int((baseline.turnover == 2).sum()),
        "turnover_sum": float(baseline.turnover.sum()), "fee_rate_sum": float(baseline.cost.sum()),
        "fees_initial_capital_units": float(baseline.fee_amount.sum()),
        "cash_days_end": int((baseline.position == "CASH").sum()),
        "stale_blocked_days": [str(d.date()) for d in baseline.index[baseline.stale_blocked]],
        "nav_end": float(baseline.nav.iloc[-1]), "same_path_no_cost_nav_end": float(baseline.no_cost_nav_same_path.iloc[-1]),
        "fee_counterexample": {"date": str(swap.name.date()), "turnover": int(swap.turnover),
                               "omitted_fee_return_error": omitted_fee_error, "doubled_fee_return_error": doubled_fee_error},
        "score_upper_mutation": {"different_days": len(wrong_upper), "first": wrong_upper[0]},
        "score_lower_mutation": {"different_days": len(wrong_lower), "first": wrong_lower[0]},
        "old_saved_curve_prefix_comparison": old_comparison,
        "agent_a_cross_comparison": agent_a_comparison,
        "main_baseline_comparison": main_comparison,
        "main_metric_comparison": metric_comparison,
        "five_windows": rows,
    }
    (OUT / "agent_b_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
