"""Adversarial data contracts for the six-ETF V1.3.

Remote faults are injected explicitly. Historical values come from the real
existing frozen panel; these tests do not certify current provider prices.
"""
import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "outputs/recert_l1_20260926/prices_raw_qfq_through_20260924.csv.gz"


@pytest.fixture
def bot():
    spec = importlib.util.spec_from_file_location("v13_data_audit_20261007", ROOT / "poe_subd_six_etf_v1_3_bot.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def real_raw():
    return pd.read_csv(RAW_PATH, parse_dates=["date"]).set_index("date")


@pytest.mark.parametrize("partial_rows", [20, 640])
def test_primary_truncated_history_uses_existing_full_backup(bot, real_raw, monkeypatch, partial_rows):
    target = "159915.SZ"
    fallback_calls = []

    def provider(**kwargs):
        code = next(code for code in bot.ASSETS if code.split(".")[0] == kwargs["symbol"])
        values = real_raw[code].dropna()
        if code == target:
            values = values.iloc[-partial_rows:]
        return pd.DataFrame({"日期": values.index, "收盘": values.values})

    def backup(code, _end):
        fallback_calls.append(code)
        values = real_raw[code].dropna().rename(code)
        values.attrs["source_detail"] = bot.SOURCE_DETAIL_TENCENT_QFQ
        return values

    monkeypatch.setattr(bot, "_HAS_AKSHARE", True)
    monkeypatch.setattr(bot, "ak", SimpleNamespace(fund_etf_hist_em=provider), raising=False)
    monkeypatch.setattr(bot, "_load_tencent_qfq_one_close", backup)
    loaded, sources = bot.load_close(bot._build_config(real_raw.index.max()))
    assert target in fallback_calls, "A primary history prefix loss must trigger the existing full backup."
    assert loaded[target].first_valid_index() == real_raw[target].first_valid_index()
    assert int(sources.loc[sources.code == target, "rows"].iloc[0]) == int(real_raw[target].notna().sum())


@pytest.mark.parametrize("fault", ["duplicate_date", "NaT", "constant_zero", "constant_infinite"])
def test_primary_invalid_history_structure_uses_existing_backup(bot, real_raw, monkeypatch, fault):
    target = "159915.SZ"
    fallback_calls = []

    def provider(**kwargs):
        code = next(code for code in bot.ASSETS if code.split(".")[0] == kwargs["symbol"])
        values = real_raw[code].dropna()
        frame = pd.DataFrame({"日期": values.index, "收盘": values.values})
        if code == target:
            if fault == "duplicate_date":
                frame = pd.concat([frame, frame.tail(1)], ignore_index=True)
            elif fault == "NaT":
                frame.loc[10, "日期"] = pd.NaT
            elif fault == "constant_zero":
                frame["收盘"] = 0.0
            elif fault == "constant_infinite":
                frame["收盘"] = np.inf
        return frame

    def backup(code, _end):
        fallback_calls.append(code)
        return real_raw[code].dropna().rename(code)

    monkeypatch.setattr(bot, "_HAS_AKSHARE", True)
    monkeypatch.setattr(bot, "ak", SimpleNamespace(fund_etf_hist_em=provider), raising=False)
    monkeypatch.setattr(bot, "_load_tencent_qfq_one_close", backup)
    loaded, _ = bot.load_close(bot._build_config(real_raw.index.max()))
    assert target in fallback_calls, "An invalid primary sequence must not block an existing valid fallback."
    pd.testing.assert_series_equal(loaded[target].dropna(), real_raw[target].dropna(), check_freq=False, check_names=False)


class _TencentResponse:
    def __init__(self, rows):
        self.rows = rows

    def raise_for_status(self):
        return None

    def json(self):
        return {"code": 0, "data": {"sz159915": {"qfqday": self.rows}}}


def _tencent_rows(series):
    return [[str(day.date()), str(price), str(price), str(price), str(price), "100"] for day, price in series.items()]


@pytest.mark.parametrize("fault", ["empty", "repeated"])
def test_tencent_incomplete_pagination_is_rejected(bot, real_raw, monkeypatch, fault):
    first_page = _tencent_rows(real_raw["159915.SZ"].dropna().iloc[-640:])
    calls = []

    def provider(_url, **kwargs):
        calls.append(kwargs["params"]["param"])
        rows = first_page if len(calls) == 1 or fault == "repeated" else []
        return _TencentResponse(rows)

    monkeypatch.setattr(bot, "_http_get", provider)
    monkeypatch.setattr(bot.time, "sleep", lambda _: None)
    with pytest.raises(RuntimeError, match="partial|coverage|history|page"):
        bot._load_tencent_qfq_one_close("159915.SZ", real_raw.index.max())


def test_tencent_complete_real_history_pagination_is_accepted(bot, real_raw, monkeypatch):
    values = real_raw["159915.SZ"].dropna()
    calls = []

    def provider(_url, **kwargs):
        calls.append(kwargs["params"]["param"])
        end_text = calls[-1].split(",")[3]
        page = values.loc[:pd.Timestamp(end_text)].iloc[-640:]
        return _TencentResponse(_tencent_rows(page))

    monkeypatch.setattr(bot, "_http_get", provider)
    monkeypatch.setattr(bot.time, "sleep", lambda _: None)
    actual = bot._load_tencent_qfq_one_close("159915.SZ", values.index.max())
    pd.testing.assert_series_equal(actual, values, check_names=False, check_freq=False)
    assert len(calls) >= 5


@pytest.mark.parametrize("bad", [0.0, -1.0, np.inf, -np.inf, "not-a-price"])
def test_alignment_rejects_nonempty_invalid_prices(bot, monkeypatch, bad):
    index = pd.date_range("2026-09-28", periods=3, freq="B")
    prices = pd.DataFrame(1.0, index=index, columns=list(bot.ASSETS))
    code = "159915.SZ"
    prices[code] = prices[code].astype(object)
    prices.loc[index[1], code] = bad
    monkeypatch.setattr(bot, "_expected_cn_trading_days", lambda *_: index)
    with pytest.raises(ValueError):
        bot.align_prices_to_common_valid_date(prices, list(bot.ASSETS))


@pytest.mark.parametrize("date", ["2026-10-03", "2026-10-07"])
def test_alignment_rejects_nontrading_row_when_expected_sessions_is_empty(bot, monkeypatch, date):
    prices = pd.DataFrame(1.0, index=pd.DatetimeIndex([date]), columns=list(bot.ASSETS))
    monkeypatch.setattr(bot, "_expected_cn_trading_days", lambda *_: pd.DatetimeIndex([]))
    with pytest.raises(ValueError, match="non-trading|trading date"):
        bot.align_prices_to_common_valid_date(prices, list(bot.ASSETS))


def test_alignment_rejects_whole_market_missing_session(bot, monkeypatch):
    index = pd.date_range("2026-09-28", periods=3, freq="B")
    prices = pd.DataFrame(1.0, index=index, columns=list(bot.ASSETS))
    prices.loc[index[1], :] = np.nan
    monkeypatch.setattr(bot, "_expected_cn_trading_days", lambda *_: index)
    with pytest.raises(ValueError, match="missing common trading dates"):
        bot.align_prices_to_common_valid_date(prices, list(bot.ASSETS))


def test_alignment_records_single_asset_missing_as_stale_fill(bot, monkeypatch):
    index = pd.date_range("2026-09-28", periods=3, freq="B")
    prices = pd.DataFrame(1.0, index=index, columns=list(bot.ASSETS))
    code = "159915.SZ"
    prices.loc[index[1], code] = np.nan
    monkeypatch.setattr(bot, "_expected_cn_trading_days", lambda *_: index)
    aligned, common_last, last_dates = bot.align_prices_to_common_valid_date(prices, list(bot.ASSETS))
    flags = bot._price_forward_fill_flags(prices, aligned, list(bot.ASSETS))
    assert flags.loc[index[1], code]
    assert aligned.loc[index[1], code] == 1.0
    assert common_last == index[-1]
    assert last_dates[code] == index[-1]


def test_official_2026_calendar_preserves_holiday_when_remote_calendar_fails(bot, monkeypatch):
    monkeypatch.setattr(bot, "_expected_cn_trading_days", lambda *_: None)
    status = bot._status_calendar_sessions(datetime(2026, 10, 7, 16, 0, tzinfo=bot.CN_TZ), pd.Timestamp("2026-09-30"))
    assert status["calendar_available"]
    assert not status["expected_today_session"]
    assert status["expected_confirmed_session"] == pd.Timestamp("2026-09-30")


def test_normal_live_cache_rejects_negative_age(bot, monkeypatch):
    now = datetime(2026, 10, 7, 16, 0, tzinfo=bot.CN_TZ)
    key = bot._daily_cache_key("2026-10-07", "live")
    bot._DAILY_CACHE[key] = (now + timedelta(minutes=3), pd.DataFrame({"marker": ["future-cache"]}), "injected")
    calls = []

    def build(*_args):
        calls.append(True)
        return pd.DataFrame({"marker": ["fresh-build"]}), "new"

    monkeypatch.setattr(bot, "_now_bj", lambda: now)
    monkeypatch.setattr(bot, "_call_build_v13_daily", build)
    daily, _ = bot._cached_daily("2026-10-07", data_state="live")
    assert calls
    assert daily.marker.iloc[0] == "fresh-build"
