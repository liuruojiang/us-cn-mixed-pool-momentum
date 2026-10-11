"""Offline math/ledger adversarial audit of the actual six-ETF V1.3 code.

Constructed prices exercise failure contracts only; no constructed-series
performance is reported. Real prices are the preserved 2026-09-24 qfq snapshot.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
BOT_PATH = ROOT / "poe_subd_six_etf_v1_3_bot.py"
L1 = ROOT / "outputs/recert_l1_20260926"


def load_bot(source_bytes):
    spec = importlib.util.spec_from_file_location("v13_math_audit_20261007", BOT_PATH)
    bot = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = bot
    # Execute the exact bytes hashed by main, even while another agent is editing.
    exec(compile(source_bytes, str(BOT_PATH), "exec", dont_inherit=True), bot.__dict__)

    def forbidden_network(*args, **kwargs):
        raise AssertionError("This audit must remain offline")

    bot._http_get = forbidden_network
    return bot


def independently_score(values):
    """Weighted covariance and squared correlation, without polyfit/SSE."""
    values = np.asarray(values, dtype=float)
    if len(values) != 25 or not np.isfinite(values).all() or np.any(values <= 0):
        return math.nan, math.nan
    y = np.log(values)
    if np.ptp(y) <= 1e-12:
        return math.nan, math.nan
    x = np.arange(25, dtype=float)
    w = np.arange(1, 26, dtype=float)
    x = x - np.sum(w * x) / np.sum(w)
    y = y - np.sum(w * y) / np.sum(w)
    xx = np.sum(w * x * x)
    yy = np.sum(w * y * y)
    xy = np.sum(w * x * y)
    slope = float(xy / xx)
    r2 = float(xy * xy / (xx * yy))
    annual_log = slope * 252
    score = math.expm1(annual_log) if annual_log < math.log(np.finfo(float).max) else math.nan
    return score, r2


def max_difference(left, right):
    left, right = np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    if not np.array_equal(np.isnan(left), np.isnan(right)):
        raise AssertionError("NaN availability differs")
    difference = np.abs(left - right)
    return float(np.nanmax(difference)) if np.isfinite(difference).any() else 0.0


def independently_replay(prices, flags, scores, r2, assets, cost):
    """Actual cash/ETF units ledger under the documented fee-on-marked-NAV convention."""
    px = prices.loc[:, assets].to_numpy(dtype=float)
    stale = flags.loc[:, assets].to_numpy(dtype=bool)
    position = "CASH"
    shares = 0.0
    cash = 1.0
    prior_nav = 1.0
    no_cost_nav = 1.0
    asset_index = {code: j for j, code in enumerate(assets)}
    rows = []
    for i, date in enumerate(prices.index):
        before = position
        wealth = cash if before == "CASH" else shares * px[i, asset_index[before]]
        eligible = np.isfinite(scores[i]) & (scores[i] > 0.5) & (scores[i] < 5.5) & (r2[i] >= 0.25)
        desired = assets[int(np.argmax(np.where(eligible, scores[i], -np.inf)))] if eligible.any() else "CASH"
        changed = desired != before
        blocked = changed and any(
            stale[i, asset_index[code]] for code in (before, desired) if code != "CASH"
        )
        after = before if blocked else desired
        turnover = 0.0 if after == before else float(int(before != "CASH") + int(after != "CASH"))
        fee_rate = turnover * cost
        net_wealth = wealth * (1.0 - fee_rate)
        if after != before:
            if after == "CASH":
                cash, shares = net_wealth, 0.0
            else:
                shares, cash = net_wealth / px[i, asset_index[after]], 0.0
        # No rebalance on unchanged full exposure; this independently keeps ETF units.
        nav = cash if after == "CASH" else shares * px[i, asset_index[after]]
        if not math.isclose(nav, net_wealth, rel_tol=2e-12, abs_tol=2e-12):
            raise AssertionError("Share/cash self-financing identity differs")
        no_cost_nav *= wealth / prior_nav
        rows.append({
            "date": date,
            "position_before": before,
            "position": after,
            "best_candidate": desired,
            "trade_blocked_by_stale_price": bool(blocked),
            "turnover": turnover,
            "cost": fee_rate,
            "gross_return": wealth / prior_nav - 1,
            "return": nav / prior_nav - 1,
            "nav": nav,
            "no_cost_nav_same_path": no_cost_nav,
            "shares": shares,
            "cash": cash,
        })
        position, prior_nav = after, nav
    return pd.DataFrame(rows).set_index("date")


def adversarial_cases(bot):
    assets = list(bot.ASSETS)
    dates = pd.bdate_range("2026-01-05", periods=35)
    prices = pd.DataFrame(10.0, index=dates, columns=assets)
    prices[assets[0]] = 10 * np.exp(np.arange(len(prices)) * 0.003)
    flags = pd.DataFrame(False, index=dates, columns=assets)
    config = bot._build_config(dates[-1])
    checks = {}
    for label, value in (("NaN", math.nan), ("positive_infinity", math.inf), ("negative_infinity", -math.inf), ("zero", 0.0), ("negative", -1.0)):
        window = pd.Series(np.exp(np.arange(25) * 0.003))
        window.iloc[12] = value
        score, r2 = bot.weighted_slope_score_and_r2(window)
        checks["invalid_window_" + label] = math.isnan(score) and math.isnan(r2)
    score, r2 = bot.weighted_slope_score_and_r2(pd.Series(np.exp(np.linspace(-500, 500, 25))))
    checks["exponential_overflow_returns_nan_score_without_exception"] = math.isnan(score) and math.isfinite(r2)
    overflow_prices = prices.copy()
    overflow_prices.loc[dates[:25], assets[1]] = np.exp(np.linspace(-500, 500, 25))
    eligible, _, raw = bot.calc_scores(overflow_prices, 24, bot.R2_THRESHOLD)
    checks["overflow_asset_does_not_abort_pool_or_block_valid_asset"] = assets[0] in eligible and assets[1] not in raw
    all_nan = prices * math.nan
    nan_curve = bot.build_curves(all_nan, config)[0]
    checks["all_nan_pool_remains_cash_nav_one"] = bool(nan_curve.position.eq("CASH").all() and nan_curve.nav.eq(1).all())
    warmup_curve = bot.build_curves(prices.iloc[:24], bot._build_config(dates[23]))[0]
    checks["24_row_warmup_cash_nav_one"] = bool(warmup_curve.position.eq("CASH").all() and warmup_curve.nav.eq(1).all())
    bad_held = prices.copy()
    bad_held.loc[dates[25], assets[0]] = math.nan
    try:
        bot.build_curves(bad_held, config)
    except RuntimeError as exc:
        checks["missing_held_close_fails_explicitly"] = "missing close for held asset" in str(exc)
    else:
        checks["missing_held_close_fails_explicitly"] = False
    for bad in (math.nan, math.inf, -0.001, 0.5):
        try:
            bot.build_curves(prices, replace(config, one_way_cost=bad))
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid cost accepted: " + str(bad))
    checks["nonfinite_negative_or_nav_erasing_cost_rejected"] = True
    scores = {assets[0]: 1.0, assets[1]: 1.0}
    target, *_ = bot._target_from_scores(scores, assets[1], 1.0)
    checks["tie_uses_asset_order_consistently_with_frozen_core"] = target == assets[0]
    for end_label, end in (("earlier_end_with_full_flags", dates[29]), ("empty_after_cutoff", dates[0] - pd.Timedelta(days=1))):
        try:
            result = bot.build_curves(prices, bot._build_config(end), flags)[0]
        except Exception as exc:
            checks[end_label] = {"outcome": "exception", "type": type(exc).__name__, "message": str(exc)}
        else:
            checks[end_label] = {"outcome": "returned", "rows": len(result)}
    try:
        bot.run_staged_entry(prices, bot._build_config(dates[0] - pd.Timedelta(days=1)), bot.EntryCase("full", "full_entry"), .25, 1.)
    except Exception as exc:
        checks["direct_engine_empty_after_cutoff"] = {"type": type(exc).__name__, "message": str(exc)}
    for label, status in checks.items():
        if isinstance(status, bool) and not status:
            raise AssertionError("Adversarial check failed: " + label)
    return checks


def main():
    source_bytes = BOT_PATH.read_bytes()
    bot_sha = hashlib.sha256(source_bytes).hexdigest()
    bot = load_bot(source_bytes)
    price_path = L1 / "prices_aligned_qfq_through_20260924.csv.gz"
    flag_path = L1 / "price_ffill_flags_through_20260924.csv.gz"
    prices = pd.read_csv(price_path, parse_dates=["date"]).set_index("date")
    flags = pd.read_csv(flag_path, parse_dates=["date"]).set_index("date")
    assets = list(bot.ASSETS)
    if not prices.index.equals(flags.index):
        raise AssertionError("Real prices and fill flags dates differ")
    scores = np.full((len(prices), len(assets)), math.nan)
    r2 = scores.copy()
    px = prices.loc[:, assets].to_numpy(dtype=float)
    for i in range(24, len(px)):
        for j in range(len(assets)):
            scores[i, j], r2[i, j] = independently_score(px[i-24:i+1, j])
    prod = bot.build_curves(prices, bot._build_config(prices.index[-1]), flags)[0]
    independent = independently_replay(prices, flags, scores, r2, assets, bot.ONE_WAY_COST)
    checks = {}
    for column in ("position_before", "position", "best_candidate", "trade_blocked_by_stale_price"):
        checks[column + "_different_rows"] = int((prod[column] != independent[column]).sum())
        if checks[column + "_different_rows"]:
            raise AssertionError(column + " differs")
    for column in ("nav", "return", "gross_return", "turnover", "cost"):
        difference = max_difference(prod[column], independent[column])
        checks[column + "_max_abs_difference"] = difference
        np.testing.assert_allclose(prod[column], independent[column], rtol=1e-11, atol=1e-11)
    prod_raw = prod[["raw_score_" + asset for asset in assets]].to_numpy(dtype=float)
    prod_r2 = prod[["r2_" + asset for asset in assets]].to_numpy(dtype=float)
    checks["raw_score_max_abs_difference"] = max_difference(prod_raw, scores)
    checks["r2_max_abs_difference"] = max_difference(prod_r2, r2)
    np.testing.assert_allclose(prod_raw, scores, rtol=2e-11, atol=2e-11, equal_nan=True)
    np.testing.assert_allclose(prod_r2, r2, rtol=2e-11, atol=2e-11, equal_nan=True)
    checks["costed_nav_never_exceeds_same_path_no_cost"] = bool((prod.nav <= independent.no_cost_nav_same_path + 1e-11).all())
    checks["cost_enters_return_as_multiplicative_deduction"] = bool(np.allclose(prod["return"], (1+prod.gross_return)*(1-prod.cost)-1, rtol=0, atol=2e-15))
    checks["buy_plus_sell_equals_turnover"] = bool(np.allclose(prod.buy_delta + prod.sell_delta, prod.turnover, atol=1e-12, rtol=0))
    checks["fee_equals_turnover_times_one_way_cost"] = bool(np.allclose(prod.cost, prod.turnover * .001, atol=1e-12, rtol=0))
    checks["exposure_binary"] = bool(set(prod.holding_fraction) <= {0., 1.} and set(prod.fraction_before) <= {0., 1.})
    checks["cash_has_zero_shares"] = bool((independent.loc[independent.position.eq("CASH"), "shares"] == 0).all())
    checks["ETF_holding_has_zero_cash"] = bool((independent.loc[independent.position.ne("CASH"), "cash"] == 0).all())
    checks["prefix_causality"] = []
    for width in (25, 550, 1600, len(prices)-1):
        prefix = bot.build_curves(prices.iloc[:width], bot._build_config(prices.index[width-1]), flags.iloc[:width])[0]
        for column in ("position", "nav", "turnover", "return"):
            pd.testing.assert_series_equal(prefix[column], prod[column].iloc[:width])
        checks["prefix_causality"].append({"rows": width, "passed": True})
    adversarial = adversarial_cases(bot)
    result = {
        "scope": "Latest local formal six-ETF V1.3, offline script math and paper ledger audit; not deployment or execution certification",
        "entrypoint": str(BOT_PATH), "entrypoint_sha256": bot_sha,
        "data": {"prices": str(price_path), "prices_sha256": hashlib.sha256(price_path.read_bytes()).hexdigest(), "flags": str(flag_path), "flags_sha256": hashlib.sha256(flag_path.read_bytes()).hexdigest(), "rows": len(prices), "start": str(prices.index[0].date()), "end": str(prices.index[-1].date()), "adjustment": "preserved qfq/front-adjusted snapshot", "network_refreshed": False},
        "formal_frozen_parameters": {"lookback": bot.LOOKBACK, "score_min_strict": bot.SCORE_MIN, "score_max_strict": bot.SCORE_MAX, "r2_threshold_inclusive": bot.R2_THRESHOLD, "switch_buffer": bot.SWITCH_BUFFER, "one_way_cost": bot.ONE_WAY_COST, "initial_entry": bot.INITIAL_ENTRY_FRACTION},
        "timing": "Old holding earns today's close-close return, then paper switch at same final close; new asset starts next row",
        "independent_real_snapshot_checks": checks,
        "constructed_contract_checks_not_performance": adversarial,
        "limitations": ["Data cutoff is 2026-09-24; no claim of current prices", "Price snapshots and adjustment labels are preserved evidence, no point-in-time corporate-action recertification", "No actual orders, broker fills, liquidity, T+1, limit-up/down execution, QDII premium or hosted Poe runtime certification", "Only full-entry formal path is audited; legacy inactive overlays retain separate assumptions"],
    }
    out_path = OUT / "math_evidence.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"artifact": str(out_path), "rows": len(prices), "checks": checks, "adversarial": adversarial}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
