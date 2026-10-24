"""Additional invariant attacks on real archived prices; no parameter selection.

Transformed prices and alternative costs are diagnostics, never performance claims.
"""
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "outputs/doublecheck_script_audit_20261007/final_network"


@pytest.fixture(scope="module")
def replay():
    spec = importlib.util.spec_from_file_location(
        "takeover_math_v13", ROOT / "poe_subd_six_etf_v1_3_bot.py"
    )
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)
    def forbidden(*args, **kwargs):
        pytest.fail("Frozen invariant tests must not access network")
    bot._http_get = forbidden
    manifest = json.loads((ARCHIVE / "manifest.json").read_text(encoding="utf-8"))
    path = ARCHIVE / "raw_prices_qfq.csv.gz"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest["files"][path.name]
    raw = pd.read_csv(path, parse_dates=["date"]).set_index("date").tail(500)
    prices = raw.ffill()
    flags = prices.notna() & raw.isna()
    config = bot._build_config(prices.index[-1])
    curve = bot.build_curves(prices, config, flags)[0]
    return bot, prices, flags, config, curve


def test_real_trade_day_return_belongs_to_previous_holding(replay):
    bot, prices, _, _, curve = replay
    asset_returns = prices.pct_change(fill_method=None)
    expected = pd.Series(0.0, index=curve.index)
    for code in bot.ASSETS:
        held = curve.position_before.eq(code)
        expected.loc[held] = asset_returns.loc[held, code]
    np.testing.assert_allclose(curve.gross_return, expected, rtol=0, atol=1e-14)
    np.testing.assert_allclose(curve["return"], (1 + expected) * (1 - curve.cost) - 1,
                               rtol=0, atol=1e-14)
    switch = curve.position_before.ne("CASH") & curve.position.ne("CASH") & curve.position_before.ne(curve.position)
    assert switch.any(), "Real slice must include asset-to-asset switches"
    distinct = [dt for dt in curve.index[switch] if not np.isclose(
        asset_returns.at[dt, curve.at[dt, "position_before"]],
        asset_returns.at[dt, curve.at[dt, "position"]], atol=1e-8)]
    assert distinct, "Test must distinguish old holding from newly selected holding"


@pytest.mark.parametrize("diagnostic_cost", [0.0, 0.002])
def test_cost_change_preserves_trade_path_and_multiplicative_ledger(replay, diagnostic_cost):
    bot, prices, flags, config, curve = replay
    changed = bot.build_curves(prices, replace(config, one_way_cost=diagnostic_cost), flags)[0]
    for column in ("position", "position_before", "turnover", "trade_count"):
        pd.testing.assert_series_equal(changed[column], curve[column], check_exact=True)
    ratio = ((1 - changed.cost) / (1 - curve.cost)).cumprod()
    np.testing.assert_allclose(changed.nav / curve.nav, ratio, rtol=0, atol=2e-13)
    if diagnostic_cost == 0:
        assert (changed.nav >= curve.nav - 1e-13).all()
    else:
        assert (changed.nav <= curve.nav + 1e-13).all()


def test_per_asset_unit_changes_preserve_real_decisions(replay):
    bot, prices, flags, config, curve = replay
    factors = pd.Series([0.001, 0.1, 10.0, 1000.0, 1e6, 1e-6], index=list(bot.ASSETS))
    changed = bot.build_curves(prices * factors, config, flags)[0]
    for column in ("position", "position_before", "turnover", "trade_count"):
        pd.testing.assert_series_equal(changed[column], curve[column], check_exact=True)
    np.testing.assert_allclose(changed.nav, curve.nav, rtol=0, atol=2e-12)


def test_future_tail_mutation_cannot_change_any_prior_engine_column(replay):
    bot, prices, flags, config, curve = replay
    cutoff = 300
    changed_prices = prices.copy()
    # Diagnostic discontinuity lives strictly after cutoff; all earlier cells are real.
    changed_prices.iloc[cutoff:] *= np.geomspace(0.25, 4.0, len(prices) - cutoff)[:, None]
    changed = bot.build_curves(changed_prices, config, flags)[0]
    pd.testing.assert_frame_equal(changed.iloc[:cutoff], curve.iloc[:cutoff], check_exact=True)


def test_input_column_order_has_no_effect_on_tie_order_or_ledger(replay):
    bot, prices, flags, config, curve = replay
    changed = bot.build_curves(prices.iloc[:, ::-1], config, flags.iloc[:, ::-1])[0]
    pd.testing.assert_frame_equal(changed, curve, check_exact=True)
