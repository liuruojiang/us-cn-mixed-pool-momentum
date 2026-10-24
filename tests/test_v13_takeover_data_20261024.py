"""Takeover data adversary: real frozen qfq prices with named calendar faults.

No network, trades, or production mutation. Injections are diagnostic only.
"""
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
PRICE_PATH = ROOT / 'outputs/doublecheck_script_audit_20261007/final_network/raw_prices_qfq.csv.gz'
CALENDAR_PATH = ROOT / 'outputs/script_audit_20261007/calendar_cache_for_replay.csv'


@pytest.fixture
def bot(monkeypatch):
    spec = importlib.util.spec_from_file_location('takeover_data_v13', ROOT / 'poe_subd_six_etf_v1_3_bot.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, '_http_get', lambda *a, **k: pytest.fail('Unexpected network'))
    monkeypatch.setattr(module, '_HAS_AKSHARE', False)
    monkeypatch.setattr(module, '_load_cached_cn_trading_days', lambda: None)
    monkeypatch.setattr(module, '_write_cached_cn_trading_days', lambda *a, **k: None)
    return module


@pytest.fixture(scope='module')
def prices():
    return pd.read_csv(PRICE_PATH, parse_dates=['date']).set_index('date').loc[:'2026-09-24']


@pytest.fixture(scope='module')
def calendar():
    return pd.DatetimeIndex(pd.to_datetime(pd.read_csv(CALENDAR_PATH).trade_date))


def seed(bot, calendar):
    bot._CN_TRADING_DAY_CACHE = calendar
    bot._CN_TRADING_DAY_CACHE_COVERAGE_END = calendar.max()
    bot._CN_TRADING_DAY_CACHE_QUERIED_START = calendar.min()
    bot._CN_TRADING_DAY_CACHE_QUERIED_END = calendar.max()


def test_unchanged_real_history_and_reference_calendar_pass(bot, prices, calendar):
    seed(bot, calendar)
    aligned, end, _ = bot.align_prices_to_common_valid_date(prices, list(bot.ASSETS))
    assert aligned.index.equals(prices.index)
    assert end == prices.index[-1]


def test_price_only_hole_is_rejected(bot, prices, calendar):
    omitted = pd.Timestamp('2026-09-22')
    seed(bot, calendar)
    assert omitted in bot._load_official_cn_trading_calendar_2026(omitted, omitted)[0]
    with pytest.raises(ValueError, match='missing common trading dates'):
        bot.align_prices_to_common_valid_date(prices.drop(omitted), list(bot.ASSETS))


def test_calendar_only_hole_is_recovered_from_official_reference(bot, prices, calendar, monkeypatch):
    omitted = pd.Timestamp('2026-09-22')
    broken = calendar.drop(omitted)
    seed(bot, broken)
    monkeypatch.setattr(bot, '_load_cnfin_trading_calendar', lambda *a: (broken, broken.max(), broken.min(), broken.max()))
    aligned, end, _ = bot.align_prices_to_common_valid_date(prices, list(bot.ASSETS))
    assert omitted in aligned.index
    assert end == prices.index[-1]


def test_matching_price_and_calendar_hole_must_not_hide_official_session(bot, prices, calendar):
    omitted = pd.Timestamp('2026-09-22')
    assert omitted in bot._load_official_cn_trading_calendar_2026(omitted, omitted)[0]
    seed(bot, calendar.drop(omitted))
    with pytest.raises((ValueError, RuntimeError), match='missing common trading dates|calendar|日历'):
        bot.align_prices_to_common_valid_date(prices.drop(omitted), list(bot.ASSETS))


def test_spurious_calendar_holiday_should_not_reject_real_complete_prices(bot, prices, calendar):
    holiday = pd.Timestamp('2026-01-01')
    assert holiday not in bot._load_official_cn_trading_calendar_2026(holiday, holiday)[0]
    seed(bot, calendar.union(pd.DatetimeIndex([holiday])).sort_values())
    aligned, end, _ = bot.align_prices_to_common_valid_date(prices, list(bot.ASSETS))
    assert aligned.index.equals(prices.index)
    assert end == prices.index[-1]


def test_formal_provider_to_build_rejects_matching_calendar_and_price_hole(bot, prices, calendar, monkeypatch):
    """Runs actual provider validation, load_close and formal _build_v13_daily."""
    from datetime import datetime
    omitted = pd.Timestamp('2026-09-22')
    broken = prices.drop(omitted)
    seed(bot, calendar.drop(omitted))
    monkeypatch.setattr(bot, '_load_akshare_eastmoney_qfq_one_close', lambda code, end: broken[code].dropna().copy())
    monkeypatch.setattr(bot, '_load_tencent_qfq_one_close', lambda *a: pytest.fail('Unexpected provider fallback'))
    monkeypatch.setattr(bot, '_load_eastmoney_one_close', lambda *a: pytest.fail('Unexpected provider fallback'))
    with pytest.raises((ValueError, RuntimeError), match='missing common trading dates|calendar|日历'):
        bot._build_v13_daily(end_date=prices.index[-1], data_state='confirmed', now=datetime(2026, 9, 24, 16, tzinfo=bot.CN_TZ))
