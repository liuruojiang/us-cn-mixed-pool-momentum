"""Offline double-check on the preserved 9/30 real qfq run; never overwrites it."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
SAVED = ROOT / "outputs/script_audit_20261007/current_network"
ENTRY = ROOT / "poe_subd_six_etf_v1_3_bot.py"
VERSIONS = {
    "before_first_audit": ROOT / ".codex_backups/20261007_163920/poe_subd_six_etf_v1_3_bot.py",
    "before_doublecheck": ROOT / ".codex_backups/20261007_200248/poe_subd_six_etf_v1_3_bot.py",
    "final": ENTRY,
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    bot = importlib.util.module_from_spec(spec)
    sys.modules[name] = bot
    source_bytes = path.read_bytes()
    exec(compile(source_bytes, str(path), "exec", dont_inherit=True), bot.__dict__)
    return bot, hashlib.sha256(source_bytes).hexdigest()


def independent_score(prices):
    """Direct weighted moments; does not call production scoring or polyfit."""
    result = np.full((len(prices), prices.shape[1]), np.nan)
    r2 = result.copy()
    weights = np.arange(1.0, 26.0)
    x = np.arange(25.0)
    xbar = np.dot(weights, x) / weights.sum()
    xx = np.dot(weights, (x - xbar) ** 2)
    for row in range(24, len(prices)):
        for col in range(prices.shape[1]):
            observations = prices[row - 24:row + 1, col]
            if not np.isfinite(observations).all() or (observations <= 0).any():
                continue
            logs = np.log(observations)
            if np.ptp(logs) <= 1e-12:
                continue
            ybar = np.dot(weights, logs) / weights.sum()
            yy = np.dot(weights, (logs - ybar) ** 2)
            xy = np.dot(weights, (x - xbar) * (logs - ybar))
            result[row, col] = math.expm1(252.0 * xy / xx)
            r2[row, col] = xy * xy / (xx * yy)
    return result, r2


def independent_units_ledger(prices, flags, score, r2, assets):
    """Cash/ETF units with fees charged on marked wealth, matching the frozen rule."""
    wealth, cash, units, previous = 1.0, 1.0, 0.0, "CASH"
    asset_index = {asset: i for i, asset in enumerate(assets)}
    rows = []
    for row in range(len(prices)):
        before = previous
        marked = cash if before == "CASH" else units * prices[row, asset_index[before]]
        eligible = (score[row] > 0.5) & (score[row] < 5.5) & (r2[row] >= 0.25)
        candidate = assets[np.argmax(np.where(eligible, score[row], -np.inf))] if eligible.any() else "CASH"
        blocked = candidate != before and any(
            flags[row, asset_index[code]] for code in (before, candidate) if code != "CASH"
        )
        after = before if blocked else candidate
        legs = 0.0 if before == after else float((before != "CASH") + (after != "CASH"))
        fee = legs * 0.001
        after_fee = marked * (1.0 - fee)
        if after != before:
            if after == "CASH":
                cash, units = after_fee, 0.0
            else:
                cash, units = 0.0, after_fee / prices[row, asset_index[after]]
        actual = cash if after == "CASH" else units * prices[row, asset_index[after]]
        rows.append({"position_before": before, "position": after, "best_candidate": candidate,
                     "trade_blocked_by_stale_price": bool(blocked), "turnover": legs, "cost": fee,
                     "gross_return": marked / wealth - 1.0, "return": actual / wealth - 1.0,
                     "nav": actual})
        previous, wealth = after, actual
    return pd.DataFrame(rows)


def max_diff(left, right):
    left, right = np.asarray(left, float), np.asarray(right, float)
    np.testing.assert_array_equal(np.isnan(left), np.isnan(right))
    finite = np.isfinite(left) & np.isfinite(right)
    return float(np.max(np.abs(left[finite] - right[finite]))) if finite.any() else 0.0


def main():
    manifest = json.loads((SAVED / "manifest.json").read_text(encoding="utf-8"))
    for name, recorded in manifest["files"].items():
        assert sha(SAVED / name) == recorded, name
    raw = pd.read_csv(SAVED / "raw_prices_qfq.csv.gz", parse_dates=["date"]).set_index("date")
    sources = pd.read_csv(SAVED / "sources.csv")
    saved = pd.read_csv(SAVED / "confirmed_daily.csv.gz", parse_dates=["date"])
    calendar_source = ROOT / "outputs/script_audit_20261007/calendar_cache_for_replay.csv"
    calendar_sha = sha(calendar_source)
    runs, bots, hashes = {}, {}, {}

    def forbidden_network(*args, **kwargs):
        raise AssertionError("Double-check uses the frozen real input; no network allowed")

    for label, path in VERSIONS.items():
        bot, code_hash = load(path, "doublecheck_math_" + label)
        bots[label], hashes[label] = bot, code_hash
        bot._http_get = forbidden_network
        bot.load_close = lambda config: (raw.copy(), sources.copy())
        # Preserve the existing independently sourced calendar without refreshing
        # or mutating the original archive. Only the download is replaced.
        calendar_copy = OUT / ("math_calendar_" + label + ".csv")
        calendar_copy.write_bytes(calendar_source.read_bytes())
        bot.TRADING_CALENDAR_CACHE_PATH = calendar_copy
        if bot._HAS_AKSHARE:
            bot.ak.tool_trade_date_hist_sina = forbidden_network
        runs[label], _ = bot._build_v13_daily(
            end_date=raw.index.max(), data_state="confirmed",
            now=datetime(2026, 10, 7, 16, 56, tzinfo=bot.CN_TZ),
        )
    assert sha(calendar_source) == calendar_sha
    final, bot = runs["final"], bots["final"]
    params = ("LOOKBACK", "SCORE_MIN", "SCORE_MAX", "R2_THRESHOLD", "SWITCH_BUFFER",
              "INITIAL_ENTRY_FRACTION", "ONE_WAY_COST", "DEFAULT_MAX_LEV", "TARGET_VOL_ENABLED",
              "OVERHEAT_ENABLED", "STAGED_ENTRY_ENABLED")
    assert all({p: getattr(bots[label], p) for p in params} == {p: getattr(bot, p) for p in params}
               for label in bots)
    discrete = ("position", "position_before", "best_candidate", "trade_blocked_by_stale_price")
    numeric = ("nav", "return", "gross_return", "turnover", "cost", "buy_delta", "sell_delta",
               "holding_fraction", "fraction_before")
    parity = {}
    for label, comparison in {**runs, "preserved_current_download": saved}.items():
        assert final.date.equals(comparison.date), label
        for col in discrete:
            pd.testing.assert_series_equal(final[col], comparison[col], check_dtype=False)
        differences = {col: max_diff(final[col], comparison[col]) for col in numeric}
        for col in numeric:
            np.testing.assert_allclose(final[col], comparison[col], rtol=0.0, atol=1e-12)
        parity[label] = differences

    assets = list(bot.ASSETS)
    # Independently fill the raw matrix and derive its stale mask, then reconcile
    # both with the official output before independent signal/ledger arithmetic.
    prices = raw[assets].ffill()
    flags = raw[assets].isna() & prices.notna()
    for code in assets:
        np.testing.assert_allclose(prices[code], final["signal_price_" + code], equal_nan=True, rtol=0, atol=0)
        np.testing.assert_array_equal(flags[code], final["price_ffill_" + code])
    score, r2 = independent_score(prices.to_numpy(float))
    np.testing.assert_allclose(score, final[["raw_score_" + c for c in assets]], equal_nan=True, rtol=2e-11, atol=2e-11)
    np.testing.assert_allclose(r2, final[["r2_" + c for c in assets]], equal_nan=True, rtol=2e-11, atol=2e-11)
    ledger = independent_units_ledger(prices.to_numpy(float), flags.to_numpy(bool), score, r2, assets)
    for col in discrete:
        pd.testing.assert_series_equal(final[col], ledger[col], check_dtype=False)
    ledger_differences = {c: max_diff(final[c], ledger[c]) for c in ledger.columns if c not in discrete}
    for col in ledger_differences:
        np.testing.assert_allclose(final[col], ledger[col], rtol=2e-11, atol=2e-11)
    prefixes = []
    for width in (1, 24, 25, 29, 501, 1350, 1960, 2500, len(prices) - 1):
        end = prices.index[width - 1]
        actual = bot.build_curves(prices, bot._build_config(end), flags)[0]
        for col in (*discrete, *numeric):
            pd.testing.assert_series_equal(actual[col].reset_index(drop=True), final[col].iloc[:width], check_dtype=False)
        prefixes.append({"rows": width, "end": str(end.date()), "passed": True})
    result = {"status": "PASS", "basis": "preserved 2026-09-30 real qfq input; offline, no fresh download",
              "rows": len(raw), "start": str(raw.index.min().date()), "end": str(raw.index.max().date()),
              "code_sha256": hashes, "input_sha256": {"raw": sha(SAVED / "raw_prices_qfq.csv.gz"),
              "daily": sha(SAVED / "confirmed_daily.csv.gz"), "calendar": calendar_sha},
              "formal_parameters_unchanged": True, "same_input_max_abs_differences": parity,
              "independent_score_max_abs_difference": max_diff(score, final[["raw_score_" + c for c in assets]]),
              "independent_r2_max_abs_difference": max_diff(r2, final[["r2_" + c for c in assets]]),
              "independent_ledger_max_abs_differences": ledger_differences,
              "prefix_and_full_mask_cutoff_checks": prefixes,
              "limitations": "Paper same-close model only; no broker fills or point-in-time corporate-action certification"}
    (OUT / "math_replay_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": result["status"], "rows": len(raw), "hashes": hashes,
                      "independent_ledger_max_abs_differences": ledger_differences,
                      "prefixes": len(prefixes)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
