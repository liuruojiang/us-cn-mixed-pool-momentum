"""Independent eight-path single-account replay for the L5 audit.

Only L1 prices and stale-price flags enter the calculations. Production
signal, account, and metric functions are not imported.
"""

from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


OUT = Path(__file__).resolve().parent
L1 = OUT.parent / "recert_l1_20260926"
L2 = OUT.parent / "recert_l2_20260926"
L4 = OUT.parent / "recert_l4_20260926"
ASSETS = ("159915.SZ", "159941.SZ", "513030.SH", "513520.SH", "159985.SZ", "518880.SH")
ONE_WAY_FEE = 0.001
WINDOWS = (("Full", None), ("10Y", 2520), ("5Y", 1260), ("3Y", 756), ("1Y", 252))


def signals(price: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    score = np.full(price.shape, np.nan, dtype=float)
    fit = np.full(price.shape, np.nan, dtype=float)
    x = np.arange(25, dtype=float)
    w = np.arange(1, 26, dtype=float)
    mx = np.sum(w * x) / np.sum(w)
    dx2 = np.sum(w * (x - mx) ** 2)
    for t in range(24, len(price)):
        for j in range(price.shape[1]):
            segment = price[t - 24:t + 1, j]
            if not (np.isfinite(segment).all() and (segment > 0).all()):
                continue
            y = np.log(segment)
            if np.ptp(y) <= 1e-12:
                continue
            y -= y[0]
            my = np.sum(w * y) / np.sum(w)
            slope = np.sum(w * (x - mx) * (y - my)) / dx2
            intercept = my - slope * mx
            total = np.sum(w * (y - my) ** 2)
            if total <= 0:
                continue
            residual = y - slope * x - intercept
            fit[t, j] = max(0.0, 1.0 - np.sum(w * residual ** 2) / total)
            exponent = slope * 252.0
            if np.isfinite(exponent) and exponent <= math.log(np.finfo(float).max):
                score[t, j] = np.expm1(exponent)
    return score, fit


def gate_matrix(score: np.ndarray, fit: np.ndarray, floor: bool, ceiling: bool, quality: bool) -> np.ndarray:
    eligible = np.isfinite(score)
    if floor:
        eligible &= score > 0.5
    if ceiling:
        eligible &= score < 5.5
    if quality:
        eligible &= np.isfinite(fit) & (fit >= 0.25)
    return eligible


def replay(index: pd.DatetimeIndex, price: np.ndarray, stale: np.ndarray,
           score: np.ndarray, fit: np.ndarray, switches: tuple[bool, bool, bool]) -> pd.DataFrame:
    elig = gate_matrix(score, fit, *switches)
    cash = 1.0
    shares = 0.0
    asset = -1
    old_nav = 1.0
    zero_fee_equivalent = 1.0
    rows: list[dict] = []
    worst_identity_error = 0.0
    for t, day in enumerate(index):
        before = asset
        before_name = ASSETS[before] if before >= 0 else "CASH"
        marked = cash + (shares * price[t, asset] if asset >= 0 else 0.0)
        if not (np.isfinite(marked) and marked > 0):
            raise AssertionError((day, "invalid mark"))
        qualified = np.where(elig[t])[0]
        desired = int(qualified[np.argmax(score[t, qualified])]) if len(qualified) else -1
        blocked = False
        if desired != asset:
            touched = [j for j in (asset, desired) if j >= 0]
            blocked = any(stale[t, j] for j in touched)
        if blocked:
            desired = asset
        turn = int(asset >= 0 and desired != asset) + int(desired >= 0 and desired != asset)
        fee = marked * ONE_WAY_FEE * turn
        if desired != asset:
            # Mark old shares, sell at this close, then buy at this same close.
            # Each buy/sell leg pays its own fee from this one cash account.
            if asset >= 0:
                cash += shares * price[t, asset]
                shares = 0.0
                cash -= marked * ONE_WAY_FEE
            if desired >= 0:
                buy_fee = marked * ONE_WAY_FEE
                spend = cash - buy_fee
                if spend < -1e-12:
                    raise AssertionError((day, "negative buying power"))
                shares = spend / price[t, desired]
                cash -= spend + buy_fee
            asset = desired
        if cash < -1e-11 or shares < -1e-11:
            raise AssertionError((day, "borrow or short", cash, shares))
        nav = cash + (shares * price[t, asset] if asset >= 0 else 0.0)
        bridge = marked - fee
        identity_error = abs(nav - bridge)
        worst_identity_error = max(worst_identity_error, identity_error)
        if identity_error > 1e-10 * max(1.0, nav):
            raise AssertionError((day, "cash/share/fee bridge", nav, bridge))
        # Same positions and marks, with fees removed from that day's return.
        zero_fee_equivalent *= marked / old_nav
        if nav > zero_fee_equivalent + 1e-9:
            raise AssertionError((day, "fees increased NAV"))
        rows.append({
            "date": day, "position_before": before_name,
            "desired": ASSETS[desired] if desired >= 0 else "CASH",
            "position": ASSETS[asset] if asset >= 0 else "CASH",
            "qualified_count": len(qualified), "blocked_stale": blocked,
            "cash": cash, "shares": shares, "marked_pre_trade": marked,
            "turnover": turn, "cost": ONE_WAY_FEE * turn,
            "fee_amount": fee, "nav": nav, "return": nav / old_nav - 1.0,
            "no_fee_same_path_nav": zero_fee_equivalent,
        })
        old_nav = nav
    result = pd.DataFrame(rows).set_index("date")
    result.attrs["max_accounting_error"] = worst_identity_error
    return result


def metrics(curve: pd.DataFrame, name: str) -> list[dict]:
    records = []
    for label, count in WINDOWS:
        part = curve if count is None else curve.tail(count)
        relative = part.nav.to_numpy(dtype=float) / float(part.nav.iloc[0])
        peak = np.maximum.accumulate(relative)
        dd = relative / peak - 1.0
        records.append({
            "arm": name, "window": label, "start": str(part.index[0].date()),
            "end": str(part.index[-1].date()), "rows": len(part),
            "annual_n_minus_1": float(relative[-1] ** (252.0 / (len(part) - 1)) - 1.0),
            "maxdd": float(dd.min()), "end_nav": float(part.nav.iloc[-1]),
            "trade_days": int((part.turnover > 0).sum()),
            "turnover_sum": float(part.turnover.sum()),
            "fee_amount_initial_capital_units": float(part.fee_amount.sum()),
            "cash_days": int((part.position == "CASH").sum()),
        })
    return records


def compare(actual: pd.DataFrame, archived: pd.DataFrame) -> dict:
    result: dict[str, float | int] = {}
    for col in ("position_before", "position", "turnover", "cost", "nav"):
        if col in ("position_before", "position"):
            result[col + "_mismatch_days"] = int((actual[col] != archived[col]).sum())
        else:
            result[col + "_max_abs"] = float((actual[col] - archived[col]).abs().max())
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    panel = pd.read_csv(L1 / "prices_aligned_qfq_through_20260924.csv.gz", parse_dates=["date"]).set_index("date")
    flags = pd.read_csv(L1 / "price_ffill_flags_through_20260924.csv.gz", parse_dates=["date"]).set_index("date")
    if not panel.index.equals(flags.index) or len(panel) != 3594 or str(panel.index[-1].date()) != "2026-09-24":
        raise AssertionError("L1 freeze mismatch")
    px = panel.loc[:, ASSETS].to_numpy(dtype=float)
    stale = flags.loc[:, ASSETS].to_numpy(dtype=bool)
    score, fit = signals(px)
    curves = {}
    metric_rows = []
    summary: dict = {"source": str(L1), "end_date": "2026-09-24", "rows": len(panel), "arms": {}}
    for switches in itertools.product((False, True), repeat=3):
        name = "".join("1" if item else "0" for item in switches)  # floor, ceiling, R2
        daily = replay(panel.index, px, stale, score, fit, switches)
        daily.to_csv(OUT / f"agent_b_{name}_daily.csv.gz", compression="gzip", float_format="%.17g")
        curves[name] = daily
        metric_rows.extend(metrics(daily, name))
        summary["arms"][name] = {
            "gates_on": list(switches),
            "end_nav": float(daily.nav.iloc[-1]),
            "trade_days": int((daily.turnover > 0).sum()),
            "two_leg_swaps": int((daily.turnover == 2).sum()),
            "turnover_sum": float(daily.turnover.sum()),
            "fee_amount_initial_capital_units": float(daily.fee_amount.sum()),
            "cash_days": int((daily.position == "CASH").sum()),
            "stale_block_days": int(daily.blocked_stale.sum()),
            "max_accounting_error": daily.attrs["max_accounting_error"],
            "min_cash": float(daily.cash.min()), "min_shares": float(daily.shares.min()),
        }
    metric_table = pd.DataFrame(metric_rows)
    metric_table.to_csv(OUT / "agent_b_metrics.csv", index=False, float_format="%.17g")
    interactions = []
    for window in (label for label, _ in WINDOWS):
        part = metric_table.loc[metric_table.window.eq(window)].set_index("arm")
        for left_off, right_off, pair_off in (("011", "101", "001"), ("011", "110", "010"), ("101", "110", "100")):
            additive = float(part.at[left_off, "annual_n_minus_1"] + part.at[right_off, "annual_n_minus_1"] - part.at["111", "annual_n_minus_1"])
            actual = float(part.at[pair_off, "annual_n_minus_1"])
            different_from_both = curves[pair_off].position.ne(curves[left_off].position) & curves[pair_off].position.ne(curves[right_off].position)
            interactions.append({
                "window": window, "left_single_off": left_off, "right_single_off": right_off, "pair_off": pair_off,
                "pair_annual_n_minus_1": actual, "single_effect_additive_annual": additive,
                "annual_interaction_vs_additive": actual - additive,
                "pair_maxdd": float(part.at[pair_off, "maxdd"]),
                "pair_minus_formal_annual": actual - float(part.at["111", "annual_n_minus_1"]),
                "pair_position_diff_from_both_single_days_full": int(different_from_both.sum()),
                "first_such_day_full": str(different_from_both[different_from_both].index[0].date()) if different_from_both.any() else "",
            })
    pd.DataFrame(interactions).to_csv(OUT / "agent_b_interactions.csv", index=False, float_format="%.17g")
    archive = {
        "111": L2 / "formal_daily_20260924.csv.gz",
        "011": L4 / "daily_score_floor_off_20260924.csv.gz",
        "101": L4 / "daily_score_ceiling_off_20260924.csv.gz",
        "110": L4 / "daily_r2_off_20260924.csv.gz",
    }
    summary["prior_layer_parity"] = {}
    for name, path in archive.items():
        old = pd.read_csv(path, parse_dates=["date"]).set_index("date")
        summary["prior_layer_parity"][name] = compare(curves[name], old)
    # Capital stacking counterexample: two independently funded sleeves require
    # two units of starting capital, while a single unified Top1 path has one.
    formal, floor_off, all_off = curves["111"], curves["011"], curves["000"]
    differing = formal.position.ne(floor_off.position)
    first = differing[differing].index[0]
    naive_blend = (formal.nav + floor_off.nav) / 2.0
    summary["separate_nav_stacking_counterexample"] = {
        "first_position_disagreement": str(first.date()),
        "formal_position": str(formal.at[first, "position"]),
        "floor_off_position": str(floor_off.at[first, "position"]),
        "separate_full_capital_required": 2.0,
        "allowed_single_capital": 1.0,
        "half_and_half_end_nav": float(naive_blend.iloc[-1]),
        "unified_all_gates_off_end_nav": float(all_off.nav.iloc[-1]),
        "difference": float(naive_blend.iloc[-1] - all_off.nav.iloc[-1]),
    }
    (OUT / "agent_b_audit.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
