import importlib.util
import math
import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "run_subd_six_etf_v1_1.py"
BOT_PATH = ROOT / "poe_subd_six_etf_v1_1_bot.py"


def load_runner_module():
    spec = importlib.util.spec_from_file_location("run_subd_v11_under_test", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_bot_module():
    spec = importlib.util.spec_from_file_location("poe_subd_v11_perf_windows_under_test", BOT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _unit_config(module, end_date):
    return module.subd.RunConfig(
        source="akshare_em_qfq",
        one_way_cost=0.001,
        start_date=pd.Timestamp("2026-01-01"),
        end_date=pd.Timestamp(end_date),
        output_tag="unit",
        target_vols=(),
        vol_window=80,
        max_lev=1.5,
    )


def test_runner_align_prices_forward_fills_single_asset_suspension_with_metadata(monkeypatch):
    module = load_runner_module()
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-05"])
    assets = list(module.subd.ASSETS)
    suspended = assets[0]
    prices = pd.DataFrame(1.0, index=dates, columns=assets)
    prices.loc[dates[1], suspended] = math.nan
    prices.loc[dates[2], suspended] = 1.2

    monkeypatch.setattr(module, "_expected_cn_trading_days", lambda start, end: pd.DatetimeIndex(dates))

    aligned, common_last, last_by_asset = module.align_prices_to_common_valid_date(prices, assets)
    flags = aligned.attrs["price_ffill_flags"]

    assert common_last == dates[-1]
    assert last_by_asset[suspended] == dates[-1]
    assert aligned.loc[dates[1], suspended] == pytest.approx(1.0)
    assert bool(flags.loc[dates[1], suspended]) is True
    assert bool(flags.loc[dates[1], assets[1]]) is False


def test_runner_blocks_trade_when_target_price_is_forward_filled(monkeypatch):
    module = load_runner_module()
    assets = list(module.subd.ASSETS)
    held = assets[0]
    target = assets[1]
    dates = pd.to_datetime(["2026-01-01", "2026-01-02"])
    prices = pd.DataFrame(1.0, index=dates, columns=assets)
    flags = pd.DataFrame(False, index=dates, columns=assets)
    flags.loc[dates[1], target] = True
    prices.attrs["price_ffill_flags"] = flags

    monkeypatch.setattr(module.subd, "LOOKBACK", 1)

    def fake_scores(_prices, idx, r2_threshold=None):
        if idx == 0:
            return {held: 1.0}, {held: 0.9}
        return {held: 1.0, target: 2.0}, {held: 0.9, target: 0.9}

    monkeypatch.setattr(module.subd, "calc_scores", fake_scores)

    out = module.run_staged_entry(
        prices,
        _unit_config(module, dates[-1]),
        module.EntryCase("full_entry", "full_entry", 1.0),
        r2_threshold=0.2,
        switch_buffer=1.0,
    )

    assert out.loc[dates[0], "position"] == held
    assert bool(out.loc[dates[1], "trade_blocked_by_stale_price"]) is True
    assert out.loc[dates[1], "stale_price_trade_assets"] == target
    assert out.loc[dates[1], "position"] == held
    assert out.loc[dates[1], "turnover"] == pytest.approx(0.0)


def test_runner_mandatory_performance_windows_include_full_and_10y():
    module = load_runner_module()
    dates = pd.bdate_range("2012-01-02", "2026-06-26")

    windows = module.build_performance_windows(
        dates,
        pd.Timestamp("2026-06-26"),
        pd.Timestamp("2020-01-02"),
    )

    labels = list(windows)
    assert labels[:5] == ["full_sample", "10Y", "5Y", "3Y", "1Y"]
    assert windows["full_sample"] == dates[0]
    assert windows["10Y"] == module.trading_day_window_start(
        dates,
        pd.Timestamp("2026-06-26"),
        10 * module.subd.TRADING_DAYS,
    )
    assert windows["from_2020"] == pd.Timestamp("2020-01-02")


def test_runner_expected_cn_trading_days_uses_local_cache_when_research_helper_missing(tmp_path, monkeypatch):
    module = load_runner_module()
    cache_path = tmp_path / "cn_trading_days_cache.csv"
    pd.DataFrame(
        {
            "trade_date": ["2026-01-01", "2026-01-02", "2026-01-05"],
            "coverage_end": ["2026-12-31"] * 3,
            "source": ["unit"] * 3,
        }
    ).to_csv(cache_path, index=False)
    monkeypatch.setattr(module, "TRADING_CALENDAR_CACHE_PATH", cache_path, raising=False)
    monkeypatch.setattr(module.subd, "ak", None)

    days = module._expected_cn_trading_days(pd.Timestamp("2026-01-02"), pd.Timestamp("2026-01-05"))

    assert days.tolist() == [pd.Timestamp("2026-01-02"), pd.Timestamp("2026-01-05")]


def test_poe_default_performance_ranges_include_mandatory_windows_when_sample_start_known():
    module = load_bot_module()

    ranges = module.resolve_performance_ranges(
        "",
        latest_date=pd.Timestamp("2026-06-26"),
        earliest_date=pd.Timestamp("2011-12-09"),
    )

    labels = [label for label, _start, _end in ranges]
    assert labels[:5] == ["full_sample", "10Y", "5Y", "3Y", "1Y"]
    assert ranges[0] == ("full_sample", pd.Timestamp("2011-12-09"), pd.Timestamp("2026-06-26"))
