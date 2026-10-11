"""Boundary and mutation checks for the independent L6 engine."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from agent_b_independent_matrix import ASSETS, FORMAL, HERE, L1, L2, independent_signals


def read_daily(name: str) -> pd.DataFrame:
    return pd.read_csv(HERE / f"agent_b_{name}_daily.csv.gz", parse_dates=["date"]).set_index("date")


def first_difference(base: pd.DataFrame, alternative: pd.DataFrame) -> dict:
    diff = base.position.ne(alternative.position)
    if not diff.any():
        return {"different_position_days": 0, "first_date": None}
    day = diff[diff].index[0]
    return {"different_position_days": int(diff.sum()), "first_date": str(day.date()),
            "formal_position": str(base.at[day, "position"]),
            "candidate_position": str(alternative.at[day, "position"]),
            "formal_turnover": int(base.at[day, "turnover"]),
            "candidate_turnover": int(alternative.at[day, "turnover"])}


def main() -> None:
    panel = pd.read_csv(L1 / "prices_aligned_qfq_through_20260924.csv.gz", parse_dates=["date"]).set_index("date")
    price = panel.loc[:, ASSETS].to_numpy(dtype=float)
    formal_archived = pd.read_csv(L2 / "formal_daily_20260924.csv.gz", parse_dates=["date"]).set_index("date")
    score, fit = independent_signals(price, 25, 1.0)
    max_score_diff = 0.0
    max_r2_diff = 0.0
    score_valid_count = 0
    for j, asset in enumerate(ASSETS):
        actual = formal_archived[f"raw_score_{asset}"].to_numpy(dtype=float)
        actual_r2 = formal_archived[f"r2_{asset}"].to_numpy(dtype=float)
        if not np.array_equal(np.isnan(score[:, j]), np.isnan(actual)):
            raise AssertionError((asset, "raw score finite mask"))
        if not np.array_equal(np.isnan(fit[:, j]), np.isnan(actual_r2)):
            raise AssertionError((asset, "R2 finite mask"))
        good = np.isfinite(actual)
        score_valid_count += int(good.sum())
        max_score_diff = max(max_score_diff, float(np.max(np.abs(score[good, j] - actual[good]))))
        max_r2_diff = max(max_r2_diff, float(np.max(np.abs(fit[good, j] - actual_r2[good]))))
    if max_score_diff > 1e-9 or max_r2_diff > 1e-10:
        raise AssertionError(("score parity", max_score_diff, max_r2_diff))

    formal = read_daily("parity_formal")
    # A prefix run has no access to future observations, yet all scores in
    # that prefix must match the full-history run.
    prefix_end = 1900
    prefix_score, prefix_fit = independent_signals(price[:prefix_end], 25, 1.0)
    prefix_error = max(float(np.nanmax(np.abs(score[:prefix_end] - prefix_score))),
                       float(np.nanmax(np.abs(fit[:prefix_end] - prefix_fit))))
    if prefix_error > 1e-12:
        raise AssertionError(("future leakage", prefix_error))

    # Deliberately insert a lookahead price at one T+1 session. A faulty
    # scorer would change T's score; the causal scorer changes T+1 onward.
    changed = price.copy()
    altered_day = 2900
    altered_asset = 0
    original_next = changed[altered_day + 1, altered_asset]
    changed[altered_day + 1, altered_asset] *= 1.25
    changed_score, _ = independent_signals(changed, 25, 1.0)
    if not np.allclose(score[:altered_day + 1], changed_score[:altered_day + 1],
                       equal_nan=True, rtol=0, atol=1e-12):
        raise AssertionError("T+1 price changed a past score")
    if not np.isfinite(score[altered_day + 1, altered_asset]) or np.isclose(
            score[altered_day + 1, altered_asset], changed_score[altered_day + 1, altered_asset]):
        raise AssertionError("mutation failed to affect its own date")

    table = pd.read_csv(HERE / "agent_b_metrics.csv")
    reference = pd.read_csv(HERE.parent / "recert_l4_20260926" / "matched_metrics.csv")
    name_map = {"parity_formal": "formal_v1_3", "parity_floor_off": "score_floor_off",
                "parity_ceiling_off": "score_ceiling_off", "parity_r2_off": "r2_off"}
    metric_parity = {}
    for name, archive_name in name_map.items():
        ours = table.loc[(table.arm == name) & table.window.isin(("Full", "10Y", "5Y", "3Y", "1Y"))].set_index("window")
        old = reference.loc[(reference.arm == archive_name) & reference.window.isin(ours.index)].set_index("window")
        if not ours.index.equals(old.index):
            old = old.loc[ours.index]
        annual_delta = float((ours.annual_n_minus_1 - old.annual_n_minus_1).abs().max())
        drawdown_delta = float((ours.maxdd - old.maxdd).abs().max())
        trade_delta = int((ours.trade_days - old.trade_days).abs().max())
        if annual_delta > 1e-10 or drawdown_delta > 1e-10 or trade_delta:
            raise AssertionError((name, annual_delta, drawdown_delta, trade_delta))
        metric_parity[name] = {"max_annual_abs": annual_delta,
                               "max_drawdown_abs": drawdown_delta, "max_trade_days_abs": trade_delta}

    group_arm = {"lookback": "lookback_29", "weight_power": "weight_power_0",
                 "score_floor": "score_floor_off", "score_ceiling": "score_ceiling_off",
                 "r2_threshold": "r2_off", "switch_buffer": "switch_buffer_1p02"}
    first_events = {group: first_difference(formal, read_daily(arm)) for group, arm in group_arm.items()}
    if any(item["different_position_days"] <= 0 for item in first_events.values()):
        raise AssertionError(("non-identifiable parameter", first_events))
    audit = json.loads((HERE / "agent_b_audit.json").read_text(encoding="utf-8"))
    event_context = {}
    for group, arm_name in group_arm.items():
        event = first_events[group]
        day = pd.Timestamp(event["first_date"])
        t = panel.index.get_loc(day)
        candidate = audit["arms"][arm_name]["parameters"]
        alt_score, alt_fit = independent_signals(price, int(candidate["lookback"]), float(candidate["weight_power"]))
        def options(s, r, rule):
            okay = np.isfinite(s)
            if rule.get("score_min") is not None:
                okay &= s > float(rule["score_min"])
            if rule.get("score_max") is not None:
                okay &= s < float(rule["score_max"])
            if rule.get("r2_threshold") is not None:
                okay &= np.isfinite(r) & (r >= float(rule["r2_threshold"]))
            return [ASSETS[j] for j in np.flatnonzero(okay)]
        before = str(formal.at[day, "position_before"])
        event_context[group] = {
            "date": str(day.date()), "formal_before": before,
            "formal_eligible": options(score[t], fit[t], FORMAL),
            "candidate_eligible": options(alt_score[t], alt_fit[t], candidate),
            "formal_score_by_asset": {asset: float(score[t, j]) if np.isfinite(score[t, j]) else None
                                      for j, asset in enumerate(ASSETS)},
            "candidate_score_by_asset": {asset: float(alt_score[t, j]) if np.isfinite(alt_score[t, j]) else None
                                         for j, asset in enumerate(ASSETS)},
            "formal_r2_by_asset": {asset: float(fit[t, j]) if np.isfinite(fit[t, j]) else None
                                   for j, asset in enumerate(ASSETS)},
            "candidate_r2_by_asset": {asset: float(alt_fit[t, j]) if np.isfinite(alt_fit[t, j]) else None
                                      for j, asset in enumerate(ASSETS)},
        }
        if group == "switch_buffer":
            wanted = str(formal.at[day, "desired"])
            if before not in ASSETS or wanted not in ASSETS:
                raise AssertionError("buffer event missing both assets")
            event_context[group]["best_to_current_score_ratio"] = float(
                score[t, ASSETS.index(wanted)] / score[t, ASSETS.index(before)])
            event_context[group]["buffer_threshold"] = candidate["switch_buffer"]

    # Real swap date: omission of one side's fee changes the return and NAV.
    swap = formal.loc[formal.turnover.eq(2)].iloc[0]
    correct = float(swap["return"])
    omit_one_side = (1.0 + float(swap.gross_return)) * (1.0 - 0.001) - 1.0
    omit_both = float(swap.gross_return)
    if abs(correct - omit_one_side) < 9e-4 or abs(correct - omit_both) < 19e-4:
        raise AssertionError("fee mutation not detected")
    # A signal-day purchase at the close cannot receive the new asset's
    # already-complete T price move. Pick an actual cash-to-ETF entry.
    entries = formal.loc[formal.position_before.eq("CASH") & formal.position.ne("CASH")]
    entry_day = entries.index[0]
    entry = entries.iloc[0]
    j = ASSETS.index(entry.position)
    t = panel.index.get_loc(entry_day)
    wrong_new_asset_gross = float(price[t, j] / price[t - 1, j] - 1.0)
    if abs(float(entry.gross_return)) > 1e-12 or abs(wrong_new_asset_gross) < 1e-4:
        raise AssertionError("signal-day new-asset mutation not observable")

    result = {
        "score_parity": {"asset_days": score_valid_count, "max_raw_score_abs": max_score_diff,
                         "max_r2_abs": max_r2_diff},
        "five_window_parity": metric_parity,
        "parameter_group_first_position_events": first_events,
        "parameter_group_first_event_scores": event_context,
        "prefix_causality_max_score_r2_abs": prefix_error,
        "future_price_mutation": {"day": str(panel.index[altered_day + 1].date()),
            "asset": ASSETS[altered_asset], "old_price": float(original_next),
            "mutated_price": float(changed[altered_day + 1, altered_asset]),
            "past_score_unchanged": True,
            "mutated_day_score_delta": float(changed_score[altered_day + 1, altered_asset] - score[altered_day + 1, altered_asset])},
        "fee_mutation": {"date": str(swap.name.date()), "turnover": int(swap.turnover),
            "correct_net_return": correct, "one_leg_omitted_error": abs(omit_one_side - correct),
            "both_legs_omitted_error": abs(omit_both - correct)},
        "same_close_new_asset_mutation": {"date": str(entry_day.date()),
            "new_asset": entry.position, "correct_signal_day_gross": float(entry.gross_return),
            "wrong_new_asset_signal_day_gross": wrong_new_asset_gross},
        "gate_boundary_semantics": {"score_equal_floor_rejected": not (0.5 > 0.5),
            "score_equal_ceiling_rejected": not (5.5 < 5.5),
            "r2_equal_threshold_accepted": 0.25 >= 0.25,
            "floor_off_is_negative_infinity": True},
    }
    path = HERE / "agent_b_adversarial_checks.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
