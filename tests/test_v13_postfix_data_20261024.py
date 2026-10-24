"""Independent diagnostic fault injections on actual frozen prices; no live fault asserted."""
import importlib.util
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
import threading
import time

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def bot(monkeypatch):
    spec = importlib.util.spec_from_file_location('independent_data_postfix', ROOT / 'poe_subd_six_etf_v1_3_bot.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    monkeypatch.setattr(m, '_http_get', lambda *a, **k: pytest.fail('Unexpected network'))
    monkeypatch.setattr(m, '_HAS_AKSHARE', False)
    monkeypatch.setattr(m, '_load_cached_cn_trading_days', lambda: None)
    monkeypatch.setattr(m, '_write_cached_cn_trading_days', lambda *a, **k: None)
    return m


@pytest.fixture(scope='module')
def prices():
    return pd.read_csv(ROOT / 'outputs/doublecheck_script_audit_20261007/final_network/raw_prices_qfq.csv.gz', parse_dates=['date']).set_index('date').loc[:'2026-09-24']


@pytest.fixture(scope='module')
def calendar():
    return pd.DatetimeIndex(pd.to_datetime(pd.read_csv(ROOT / 'outputs/script_audit_20261007/calendar_cache_for_replay.csv').trade_date))


def seed(bot, dates):
    bot._CN_TRADING_DAY_CACHE = dates[:-1]
    bot._CN_TRADING_DAY_CACHE_COVERAGE_END = dates[-2]
    bot._CN_TRADING_DAY_CACHE_QUERIED_START = dates[0]
    bot._CN_TRADING_DAY_CACHE_QUERIED_END = dates[-1]


@pytest.mark.parametrize('fault', ['network', 'still_truncated'])
def test_provider_to_alignment_recovers_under_persistent_fault(bot, prices, monkeypatch, fault):
    dates = prices.index
    seed(bot, dates)
    calls = []
    def loader(start, end):
        calls.append((start, end))
        if fault == 'network':
            raise RuntimeError('Diagnostic calendar network outage')
        return dates[:-1], dates[-2], dates[0], dates[-1]
    monkeypatch.setattr(bot, '_load_cnfin_trading_calendar', loader)
    monkeypatch.setattr(bot, '_load_akshare_eastmoney_qfq_one_close', lambda code, end: prices[code].dropna())
    monkeypatch.setattr(bot, '_load_tencent_qfq_one_close', lambda *a: pytest.fail('Unexpected price-provider fallback'))
    loaded, _ = bot._load_public_close_with_per_code_fallback(list(bot.ASSETS), dates[-1])
    aligned, end, _ = bot.align_prices_to_common_valid_date(loaded, list(bot.ASSETS))
    assert end == dates[-1]
    assert len(aligned) == len(prices)
    assert len(calls) <= 3


def test_recovery_retains_missing_session_rejection(bot, prices, monkeypatch):
    dates = prices.index
    seed(bot, dates)
    monkeypatch.setattr(bot, '_load_cnfin_trading_calendar', lambda a, z: (dates, dates[-1], dates[0], dates[-1]))
    injected = prices.drop(pd.Timestamp('2026-09-22'))
    with pytest.raises(ValueError, match='missing common trading dates'):
        bot.align_prices_to_common_valid_date(injected, list(bot.ASSETS))


@pytest.mark.parametrize('day', ['2026-01-01', '2026-09-19'])
def test_bad_dates_are_not_repaired_with_valid_conflict(bot, prices, monkeypatch, day):
    dates = prices.index
    seed(bot, dates)
    monkeypatch.setattr(bot, '_load_cnfin_trading_calendar', lambda *a: pytest.fail('Known closure should not refresh'))
    injected = prices.copy()
    injected.loc[pd.Timestamp(day)] = injected.loc[:day].iloc[-1]
    with pytest.raises(ValueError, match='unexpected non-trading'):
        bot.align_prices_to_common_valid_date(injected.sort_index(), list(bot.ASSETS))


def test_preofficial_conflict_fails_closed(bot, prices, monkeypatch):
    prices = prices.loc[:'2025-09-24']
    dates = prices.index
    seed(bot, dates)
    monkeypatch.setattr(bot, '_load_cnfin_trading_calendar', lambda *a: pytest.fail('Unverifiable historical conflict must not refresh'))
    with pytest.raises(ValueError, match='unexpected non-trading'):
        bot.align_prices_to_common_valid_date(prices, list(bot.ASSETS))


def test_force_refresh_serializes_and_bypasses_both_caches(bot, prices, monkeypatch):
    dates = prices.index
    seed(bot, dates)
    state = {'active': 0, 'peak': 0, 'calls': 0}
    lock = threading.Lock()
    monkeypatch.setattr(bot, '_load_cached_cn_trading_days', lambda: pytest.fail('Forced refresh read disk cache'))
    def loader(start, end):
        with lock:
            state['active'] += 1
            state['peak'] = max(state['active'], state['peak'])
            state['calls'] += 1
        time.sleep(.02)
        with lock:
            state['active'] -= 1
        return dates, dates[-1], dates[0], dates[-1]
    monkeypatch.setattr(bot, '_load_cnfin_trading_calendar', loader)
    def load(_):
        return bot._load_cn_trading_calendar(dates[0], dates[-1], force_refresh=True)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(load, range(4)))
    assert state == {'active': 0, 'peak': 1, 'calls': 4}
    assert all(r[0].equals(dates) and r[1] == dates[-1] for r in results)


def test_january_weekend_uses_official_recent_session_across_year(bot, calendar, monkeypatch):
    daily = pd.read_csv(ROOT / 'outputs/doublecheck_script_audit_20261007/final_network/confirmed_daily.csv.gz', parse_dates=['date'])
    def truncated(start, end):
        dates = calendar[(calendar >= start) & (calendar <= pd.Timestamp('2026-01-08'))]
        return dates, dates.max(), start, end
    monkeypatch.setattr(bot, '_load_cnfin_trading_calendar', truncated)
    status = bot.signal_data_status(daily[daily.date <= '2026-01-08'], False, datetime(2026, 1, 10, 16, tzinfo=bot.CN_TZ))
    assert status['expected_confirmed_session'] == '2026-01-09'
    assert not status['signal_valid']


def test_status_beyond_official_coverage_does_not_trust_query_end(bot, calendar, monkeypatch):
    daily = pd.read_csv(ROOT / 'outputs/doublecheck_script_audit_20261007/final_network/confirmed_daily.csv.gz', parse_dates=['date'])
    daily = daily[daily.date <= '2026-09-24']
    def truncated(start, end):
        dates = calendar[(calendar >= start) & (calendar <= pd.Timestamp('2026-09-24'))]
        return dates, dates.max(), start, end
    monkeypatch.setattr(bot, '_load_cnfin_trading_calendar', truncated)
    try:
        status = bot.signal_data_status(daily, False, datetime(2027, 1, 9, 16, tzinfo=bot.CN_TZ))
    except RuntimeError:
        return
    assert not status['signal_valid']


def test_january_holiday_preserves_previous_year_session(bot, calendar, monkeypatch):
    dates = calendar[calendar <= pd.Timestamp('2025-12-31')]
    monkeypatch.setattr(bot, '_load_cn_trading_calendar', lambda *a, **k: (dates, dates.max(), dates.min(), pd.Timestamp('2026-01-03')))
    sessions = bot._status_calendar_sessions(datetime(2026, 1, 3, 16, tzinfo=bot.CN_TZ), pd.Timestamp('2025-12-31'))
    assert sessions['calendar_available']
    assert sessions['expected_confirmed_session'] == pd.Timestamp('2025-12-31')
