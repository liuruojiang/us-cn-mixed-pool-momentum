"""Cross-check the independent cash/share reconstruction against L4 main curves."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
PAIRS = {
    "formal_rebuilt": "formal_v1_3",
    "lower_off": "score_floor_off",
    "upper_off": "score_ceiling_off",
    "r2_off": "r2_off",
}
ASSETS = ("159915.SZ", "159941.SZ", "513030.SH", "513520.SH", "159985.SZ", "518880.SH")


def frame(path: Path) -> pd.DataFrame:
    result = pd.read_csv(path, parse_dates=["date"]).set_index("date")
    if not result.index.is_unique or not result.index.is_monotonic_increasing:
        raise AssertionError(f"Invalid dates: {path}")
    return result


def main() -> None:
    expected_metrics = pd.read_csv(OUT / "matched_metrics.csv")
    independent_metrics = pd.read_csv(OUT / "agent_b_metrics.csv")
    prices = frame(ROOT / "outputs/recert_l1_20260926/prices_aligned_qfq_through_20260924.csv.gz")
    comparison = {}
    for ours, theirs in PAIRS.items():
        a = frame(OUT / f"agent_b_{ours}_daily.csv.gz")
        b = frame(OUT / f"daily_{theirs}_20260924.csv.gz")
        if not a.index.equals(b.index) or not a.index.equals(prices.index):
            raise AssertionError(f"Date mismatch: {ours}")
        check = {"rows": len(a), "start": str(a.index[0].date()), "end": str(a.index[-1].date())}
        for name in ("position_before", "position"):
            check[f"{name}_mismatch"] = int(np.count_nonzero(a[name].to_numpy() != b[name].to_numpy()))
        check["desired_vs_best_mismatch"] = int(np.count_nonzero(a.desired.to_numpy() != b.best_candidate.to_numpy()))
        for name in ("turnover", "cost", "gross_return", "return", "nav"):
            check[f"{name}_max_abs"] = float(np.max(np.abs(a[name].to_numpy(float) - b[name].to_numpy(float))))
        check["stale_block_mismatch"] = int(np.count_nonzero(a.trade_blocked_by_stale_price.to_numpy(bool) != b.trade_blocked_by_stale_price.to_numpy(bool)))
        measure_fields = ("annual_n_minus_1", "maxdd", "trade_days", "turnover_sum", "cash_days")
        x = independent_metrics.loc[independent_metrics.arm.eq(ours)].set_index("window")
        y = expected_metrics.loc[expected_metrics.arm.eq(theirs)].set_index("window").loc[x.index]
        if list(x.index) != list(y.index) or not x.start.equals(y.start) or not x.end.equals(y.end):
            raise AssertionError(f"Window mismatch: {ours}")
        for key in measure_fields:
            ykey = "cash_end_days" if key == "cash_days" else key
            check[f"five_window_{key}_max_abs"] = float(np.max(np.abs(x[key].to_numpy(float) - y[ykey].to_numpy(float))))
        check["five_window_fee_amount_max_abs"] = float(np.max(np.abs(
            x.fee_amount_initial_capital_units.to_numpy(float) - y.fees_initial_capital_units.to_numpy(float)
        )))
        if any(check[k] for k in ("position_before_mismatch", "position_mismatch", "desired_vs_best_mismatch", "stale_block_mismatch")):
            raise AssertionError(f"Signal or position divergence: {ours}: {check}")
        if any(check[f"{k}_max_abs"] > 1e-11 for k in ("turnover", "cost", "gross_return", "return", "nav")):
            raise AssertionError(f"Ledger divergence: {ours}: {check}")
        if any(check[f"five_window_{k}_max_abs"] > 1e-11 for k in measure_fields):
            raise AssertionError(f"Metric divergence: {ours}: {check}")
        if check["five_window_fee_amount_max_abs"] > 1e-11:
            raise AssertionError(f"Fee cash divergence: {ours}: {check}")
        if np.any(a.same_path_no_cost_nav.to_numpy(float) < a.nav.to_numpy(float) - 1e-9):
            raise AssertionError(f"Costed NAV above no-cost path: {ours}")
        if not np.allclose(a.fee_amount.to_numpy(float), a.cost.to_numpy(float) * (a.nav.shift().fillna(1.0).to_numpy(float)) * (1 + a.gross_return.to_numpy(float)), rtol=0, atol=1e-10):
            raise AssertionError(f"Fee cash bridge failed: {ours}")
        comparison[ours] = check

    # A two-sided replacement must pay both sell and buy fees in the net return.
    formal = frame(OUT / "agent_b_formal_rebuilt_daily.csv.gz")
    swaps = formal.loc[(formal.turnover.eq(2)) & (formal.index >= pd.Timestamp("2025-01-01"))]
    swap = swaps.iloc[0]
    fee_counterexample = {
        "date": str(swaps.index[0].date()), "before": swap.position_before, "after": swap.position,
        "turnover": int(swap.turnover), "gross_return": float(swap.gross_return),
        "cost_fraction": float(swap.cost), "net_return": float(swap["return"]),
        "omitted_fee_return_overstatement": float(swap.gross_return - swap["return"]),
    }

    # At a cash-to-asset T-close entry, the current paper model earns the next
    # close-to-close move; execution at T+1 close would miss exactly that gross move.
    entries = []
    for arm in ("formal_rebuilt", "lower_off", "upper_off", "r2_off"):
        curve = frame(OUT / f"agent_b_{arm}_daily.csv.gz")
        for i in range(len(curve) - 1):
            row = curve.iloc[i]
            next_row = curve.iloc[i + 1]
            if row.position_before != "CASH" or row.position == "CASH" or row.position != next_row.desired:
                continue
            code = row.position
            p0 = float(prices.iloc[i][code])
            p1 = float(prices.iloc[i + 1][code])
            if np.isfinite(p0) and np.isfinite(p1) and p0 > 0:
                entries.append({"arm": arm, "signal_date": str(curve.index[i].date()),
                                "next_close_date": str(curve.index[i + 1].date()), "asset": code,
                                "one_day_gross_move_missed_by_t_plus_1_close": p1 / p0 - 1.0,
                                "paper_next_day_gross_return": float(next_row.gross_return)})
    if not entries:
        raise AssertionError("No T/T+1 execution counterexample found")
    recent_entries = [entry for entry in entries if entry["signal_date"] >= "2025-09-11"]
    if not recent_entries:
        raise AssertionError("No recent T/T+1 timing counterexample found")
    timing = max(recent_entries, key=lambda z: abs(z["one_day_gross_move_missed_by_t_plus_1_close"]))
    if abs(timing["one_day_gross_move_missed_by_t_plus_1_close"] - timing["paper_next_day_gross_return"]) > 1e-12:
        raise AssertionError("Timing counterexample does not reconcile")

    # Mutation: crediting the newly bought ETF with its signal-day close-to-close
    # return is impossible under the stated T-close fill clock. The prior holding
    # was cash, so signal-day gross return must be exactly zero.
    entry_day = pd.Timestamp("2026-02-10")
    entry = formal.loc[entry_day]
    prior_day = prices.index[prices.index.get_loc(entry_day) - 1]
    if entry.position_before != "CASH" or entry.position != "513520.SH":
        raise AssertionError("Expected concrete entry event changed")
    signal_day_new_asset_return = float(prices.at[entry_day, entry.position] / prices.at[prior_day, entry.position] - 1)
    wrong_gross = signal_day_new_asset_return
    wrong_net = (1 + wrong_gross) * (1 - float(entry.cost)) - 1
    timing_mutation = {
        "date": str(entry_day.date()), "prior_date": str(prior_day.date()),
        "prior_holding": entry.position_before, "new_holding": entry.position,
        "independent_signal_day_gross": float(entry.gross_return),
        "wrong_new_asset_signal_day_gross": wrong_gross,
        "independent_signal_day_net": float(entry["return"]),
        "wrong_new_asset_signal_day_net": wrong_net,
        "wrong_net_overstatement": wrong_net - float(entry["return"]),
    }
    if abs(timing_mutation["wrong_net_overstatement"]) < 0.01:
        raise AssertionError("Signal-day new-position mutation was not detected")
    result = {"main_curve_comparison": comparison, "fee_counterexample": fee_counterexample,
              "same_close_t_plus_1_counterexample": timing,
              "signal_day_new_position_mutation": timing_mutation}
    (OUT / "agent_b_crosscheck.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
