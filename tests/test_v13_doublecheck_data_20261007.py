"""Independent second audit of data contracts.

Prices are the real frozen qfq input. Removed/inserted dates and remote response
ordering are deliberately injected faults; they are not market observations.
"""
import importlib.util
import os
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "outputs/recert_l1_20260926/prices_raw_qfq_through_20260924.csv.gz"


@pytest.fixture
def bot():
    code_path = Path(os.environ.get("V13_DOUBLECHECK_DATA_CODE_PATH", str(ROOT / "poe_subd_six_etf_v1_3_bot.py")))
    spec = importlib.util.spec_from_file_location(
        "v13_doublecheck_data_20261007", code_path
    )
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


@pytest.fixture(scope="module")
def real_prices():
    return pd.read_csv(RAW, parse_dates=["date"]).set_index("date")


def _calendar(bot, real_prices, monkeypatch):
    # The frozen real panel's dates are the unchanged-baseline session set. Only
    # the test provider faults modify prices; the session reference stays fixed.
    monkeypatch.setattr(
        bot, "_expected_cn_trading_days",
        lambda start, end: real_prices.index[
            (real_prices.index >= start) & (real_prices.index <= end)
        ],
    )


@pytest.mark.parametrize("bad_date", ["2012-06-09", "2012-10-01", "2026-09-19", "2026-01-01"])
def test_provider_nontrading_dates_use_available_good_backup(
    bot, real_prices, monkeypatch, bad_date
):
    target = "159915.SZ"
    inserted = pd.Timestamp(bad_date)
    calls = []

    def primary(**kwargs):
        code = next(code for code in bot.ASSETS if code.split(".")[0] == kwargs["symbol"])
        close = real_prices[code].dropna().copy()
        if code == target:
            close.loc[inserted] = close.loc[:inserted].iloc[-1]
            close = close.sort_index()
        return pd.DataFrame({"日期": close.index, "收盘": close.values})

    def backup(code, end):
        calls.append(code)
        close = real_prices[code].dropna().rename(code)
        close.attrs["source_detail"] = bot.SOURCE_DETAIL_TENCENT_QFQ
        return close

    _calendar(bot, real_prices, monkeypatch)
    monkeypatch.setattr(bot, "_HAS_AKSHARE", True)
    monkeypatch.setattr(bot, "ak", SimpleNamespace(fund_etf_hist_em=primary), raising=False)
    monkeypatch.setattr(bot, "_load_tencent_qfq_one_close", backup)
    loaded, sources = bot.load_close(bot._build_config(real_prices.index.max()))
    assert target in calls, "A price on a non-session must reject that provider and use a valid backup."
    assert inserted not in loaded.index
    assert sources.set_index("code").loc[target, "source"] == "Tencent fqkline"


@pytest.mark.parametrize("bad_date", ["2012-06-09", "2012-10-01"])
def test_alignment_rejects_nontrading_row_before_all_six_have_history(
    bot, real_prices, monkeypatch, bad_date
):
    injected = real_prices.copy()
    weekend = pd.Timestamp(bad_date)
    assert weekend not in real_prices.index
    injected.loc[weekend] = injected.loc[:weekend].iloc[-1]
    injected = injected.sort_index()
    _calendar(bot, real_prices, monkeypatch)
    with pytest.raises(ValueError, match="non-trading"):
        bot.align_prices_to_common_valid_date(injected, list(bot.ASSETS))


@pytest.mark.parametrize("extent", ["single_date", "whole_month"])
def test_alignment_rejects_missing_market_row_before_all_six_have_history(
    bot, real_prices, monkeypatch, extent
):
    # Only CYB ETF is available on this genuine session. Removing its row removes
    # the entire market date from the panel, without changing any first/last date.
    omitted = pd.Timestamp("2012-06-11")
    assert real_prices.loc[omitted].notna().sum() == 1
    missing = (pd.DatetimeIndex([omitted]) if extent == "single_date" else
               real_prices.loc["2012-06-01":"2012-06-30"].index)
    assert real_prices.loc[missing].notna().sum(axis=1).eq(1).all()
    injected = real_prices.drop(index=missing)
    _calendar(bot, real_prices, monkeypatch)
    with pytest.raises(ValueError, match="missing common trading dates"):
        bot.align_prices_to_common_valid_date(injected, list(bot.ASSETS))


def test_real_prelisting_nans_and_two_existing_single_asset_gaps_are_preserved(
    bot, real_prices, monkeypatch
):
    _calendar(bot, real_prices, monkeypatch)
    aligned, end, last_dates = bot.align_prices_to_common_valid_date(real_prices, list(bot.ASSETS))
    flags = bot._price_forward_fill_flags(real_prices, aligned, list(bot.ASSETS))
    assert aligned.index.equals(real_prices.index)
    assert int(flags.to_numpy().sum()) == 2
    assert end == real_prices.index[-1]
    for code in bot.ASSETS:
        assert aligned[code].first_valid_index() == real_prices[code].first_valid_index()
        assert last_dates[code] == real_prices[code].last_valid_index()


class _Response:
    def __init__(self, rows):
        self.rows = rows

    def raise_for_status(self):
        return None

    def json(self):
        return {"code": 0, "data": {"sz159915": {"qfqday": self.rows}}}


def _rows(close):
    return [
        [str(day.date()), str(price), str(price), str(price), str(price), "100"]
        for day, price in close.items()
    ]


@pytest.mark.parametrize("reverse", [False, True])
def test_complete_tencent_exact_full_page_history_reaches_anchor_before_empty_page(
    bot, real_prices, monkeypatch, reverse
):
    # 2,560 genuine historical observations = four pages at the actual 640 size.
    # A final empty page is valid after reaching the verified first observation.
    close = real_prices["159915.SZ"].dropna().iloc[:2560]
    calls = []

    def provider(url, **kwargs):
        end = pd.Timestamp(kwargs["params"]["param"].split(",")[3])
        page = close.loc[:end].iloc[-bot.TENCENT_FQKLINE_PAGE_SIZE:]
        calls.append(end)
        if reverse:
            page = page.iloc[::-1]
        return _Response(_rows(page))

    monkeypatch.setattr(bot, "_http_get", provider)
    monkeypatch.setattr(bot.time, "sleep", lambda _: None)
    actual = bot._load_tencent_qfq_one_close("159915.SZ", close.index.max())
    pd.testing.assert_series_equal(actual, close, check_names=False, check_freq=False)
    assert len(calls) >= 5


@pytest.mark.parametrize("bad", [np.inf, 0.0, -1.0, "not-a-price"])
def test_bad_text_and_prices_reject_even_before_six_have_history(bot, real_prices, monkeypatch, bad):
    injected = real_prices.astype(object).copy()
    injected.loc[pd.Timestamp("2012-06-11"), "159915.SZ"] = bad
    _calendar(bot, real_prices, monkeypatch)
    with pytest.raises(ValueError, match="non-finite|non-positive"):
        bot.align_prices_to_common_valid_date(injected, list(bot.ASSETS))


@pytest.mark.parametrize("mode", ["required", "warning"])
def test_empty_calendar_rejects_false_bar_even_in_warning_mode(bot, monkeypatch, mode):
    prices = pd.DataFrame(1.0, index=pd.DatetimeIndex(["2026-10-07"]), columns=list(bot.ASSETS))
    monkeypatch.setattr(bot, "_expected_cn_trading_days", lambda *_: pd.DatetimeIndex([]))
    with pytest.raises(ValueError, match="non-trading"):
        bot.align_prices_to_common_valid_date(prices, list(bot.ASSETS), calendar_validation_mode=mode)


def test_official_calendar_fallback_outside_2026_keeps_execution_closed(bot, monkeypatch):
    monkeypatch.setattr(bot, "_expected_cn_trading_days", lambda *_: None)
    status = bot._status_calendar_sessions(
        datetime(2027, 1, 4, 16, 0, tzinfo=bot.CN_TZ), pd.Timestamp("2026-12-31")
    )
    assert not status["calendar_available"]


@pytest.mark.parametrize("age_seconds,should_refresh", [(-1, True), (0, False), (300, False), (301, True)])
def test_cache_time_interval_is_closed_and_excludes_future_entries(
    bot, monkeypatch, age_seconds, should_refresh
):
    now = datetime(2026, 9, 30, 16, 0, tzinfo=bot.CN_TZ)
    key = bot._daily_cache_key("2026-09-30", "confirmed")
    bot._DAILY_CACHE[key] = (
        now - timedelta(seconds=age_seconds), pd.DataFrame({"marker": ["cached"]}), "cache"
    )
    builds = []

    def build(*args):
        builds.append(True)
        return pd.DataFrame({"marker": ["fresh"]}), "provider"

    monkeypatch.setattr(bot, "_now_bj", lambda: now)
    monkeypatch.setattr(bot, "_call_build_v13_daily", build)
    result, _ = bot._cached_daily("2026-09-30", "confirmed")
    assert bool(builds) == should_refresh
    assert result.marker.iloc[0] == ("fresh" if should_refresh else "cached")


@pytest.mark.parametrize("invalid_primary", [False, True])
def test_provider_calendar_reuses_legal_actual_start_cache_once(
    bot, real_prices, monkeypatch, invalid_primary
):
    # A legal cache need only cover actual observed history. There is no need to
    # refresh a 2010 calendar when the first real ETF close is 2011-12-09.
    bot._CN_TRADING_DAY_CACHE = real_prices.index.copy()
    bot._CN_TRADING_DAY_CACHE_COVERAGE_END = real_prices.index.max()
    bot._CN_TRADING_DAY_CACHE_QUERIED_START = None
    bot._CN_TRADING_DAY_CACHE_QUERIED_END = None
    actual_expected = bot._expected_cn_trading_days
    calls = []
    backups = []

    def expected(start, end):
        calls.append((pd.Timestamp(start), pd.Timestamp(end)))
        return actual_expected(start, end)

    def primary(**kwargs):
        code = next(code for code in bot.ASSETS if code.split(".")[0] == kwargs["symbol"])
        values = real_prices[code].dropna()
        if invalid_primary and code == "159915.SZ":
            values = values.iloc[-20:]
        return pd.DataFrame({"日期": values.index, "收盘": values.values})

    def backup(code, end):
        backups.append(code)
        close = real_prices[code].dropna().rename(code)
        close.attrs["source_detail"] = bot.SOURCE_DETAIL_TENCENT_QFQ
        return close

    def unexpected_http(*args, **kwargs):
        raise AssertionError("A usable actual-history calendar must not trigger any HTTP refresh.")

    monkeypatch.setattr(bot, "_HAS_AKSHARE", True)
    monkeypatch.setattr(bot, "ak", SimpleNamespace(fund_etf_hist_em=primary), raising=False)
    monkeypatch.setattr(bot, "_http_get", unexpected_http)
    monkeypatch.setattr(bot, "_load_tencent_qfq_one_close", backup)
    monkeypatch.setattr(bot, "_expected_cn_trading_days", expected)
    loaded, _ = bot.load_close(bot._build_config(real_prices.index.max()))
    assert len(calls) <= 1
    assert all(start == real_prices.index.min() and end == real_prices.index.max() for start, end in calls)
    assert backups == (["159915.SZ"] if invalid_primary else [])
    pd.testing.assert_frame_equal(loaded, real_prices, check_freq=False, check_names=False)


def test_provider_calendar_extends_only_when_later_candidate_has_earlier_history(
    bot, real_prices, monkeypatch
):
    codes = ["159985.SZ", "159915.SZ"]
    calls = []

    def expected(start, end):
        calls.append((pd.Timestamp(start), pd.Timestamp(end)))
        return real_prices.index[(real_prices.index >= start) & (real_prices.index <= end)]

    def primary(code, end):
        return real_prices[code].dropna().rename(code)

    monkeypatch.setattr(bot, "_load_akshare_eastmoney_qfq_one_close", primary)
    monkeypatch.setattr(bot, "_expected_cn_trading_days", expected)
    loaded, _ = bot._load_public_close_with_per_code_fallback(codes, real_prices.index.max())
    assert len(calls) <= 2
    if calls:
        assert calls == [
            (real_prices[codes[0]].first_valid_index(), real_prices.index.max()),
            (real_prices[codes[1]].first_valid_index(), real_prices.index.max()),
        ]
    pd.testing.assert_frame_equal(loaded, real_prices[codes], check_freq=False, check_names=False)


@pytest.mark.parametrize("calendar_kind", ["unavailable", "known_empty"])
def test_optional_provider_calendar_preserves_required_alignment_guard(
    bot, real_prices, monkeypatch, calendar_kind
):
    def primary(code, end):
        return real_prices[code].dropna().rename(code)

    monkeypatch.setattr(bot, "_load_akshare_eastmoney_qfq_one_close", primary)
    monkeypatch.setattr(bot, "_load_tencent_qfq_one_close", primary)
    monkeypatch.setattr(bot, "_load_eastmoney_one_close", primary)
    reference = None if calendar_kind == "unavailable" else pd.DatetimeIndex([])
    monkeypatch.setattr(bot, "_expected_cn_trading_days", lambda *_: reference)
    try:
        loaded, _ = bot.load_close(bot._build_config(real_prices.index.max()))
    except RuntimeError as exc:
        assert calendar_kind == "known_empty"
        assert "All historical data sources failed" in str(exc)
        return
    pd.testing.assert_frame_equal(loaded, real_prices, check_freq=False, check_names=False)
    with pytest.raises((RuntimeError, ValueError), match="交易日历|non-trading"):
        bot.align_prices_to_common_valid_date(loaded, list(bot.ASSETS))
