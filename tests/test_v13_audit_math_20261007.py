"""Adversarial historical-cutoff contracts; constructed prices are not performance data."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def bot():
    spec = importlib.util.spec_from_file_location(
        "v13_math_cutoff_20261007", ROOT / "poe_subd_six_etf_v1_3_bot.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _contract_prices(bot):
    dates = pd.bdate_range("2026-01-05", periods=35)
    prices = pd.DataFrame(10.0, index=dates, columns=list(bot.ASSETS))
    prices.iloc[:, 0] = 10.0 * np.exp(np.arange(len(prices)) * 0.003)
    flags = pd.DataFrame(False, index=dates, columns=list(bot.ASSETS))
    return prices, flags


def test_build_curves_cutoff_truncates_matching_full_snapshot_flags(bot):
    """A full snapshot and its exact mask remain valid with an earlier end date."""
    prices, flags = _contract_prices(bot)
    end_date = prices.index[29]
    full = bot.build_curves(prices, bot._build_config(prices.index[-1]), flags)[0]
    actual = bot.build_curves(prices, bot._build_config(end_date), flags)[0]
    pd.testing.assert_frame_equal(actual, full.loc[:end_date])


def test_build_curves_cutoff_before_first_price_raises_explicit_validation(bot):
    """No data inside the requested cutoff must not leak an internal KeyError."""
    prices, flags = _contract_prices(bot)
    before_first = prices.index[0] - pd.Timedelta(days=1)
    with pytest.raises(ValueError, match="(?i)(empty|no price|no rows|nonempty)"):
        bot.build_curves(prices, bot._build_config(before_first))
