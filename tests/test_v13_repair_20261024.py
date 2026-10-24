"""Real archived data plus explicitly diagnostic faults for the October audit."""
import importlib.util
import io
import os
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SAVED = ROOT / 'outputs/doublecheck_script_audit_20261007/final_network'


@pytest.fixture
def bot(monkeypatch):
    path = Path(os.environ.get('V13_REPAIR_CODE_PATH', ROOT / 'poe_subd_six_etf_v1_3_bot.py'))
    spec = importlib.util.spec_from_file_location('v13_repair', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, '_http_get', lambda *a, **k: pytest.fail('Unexpected network'))
    return module


@pytest.fixture(scope='module')
def daily():
    return pd.read_csv(SAVED / 'confirmed_daily.csv.gz', parse_dates=['date'])


@pytest.fixture(scope='module')
def raw():
    return pd.read_csv(SAVED / 'raw_prices_qfq.csv.gz', parse_dates=['date']).set_index('date')


@pytest.fixture(scope='module')
def calendar():
    return pd.DatetimeIndex(pd.to_datetime(pd.read_csv(
        ROOT / 'outputs/script_audit_20261007/calendar_cache_for_replay.csv')['trade_date']))


def use_calendar(bot, monkeypatch, calendar):
    monkeypatch.setattr(bot, '_load_cn_trading_calendar',
                        lambda start, end, **kwargs: (calendar, calendar.max(), calendar.min(), calendar.max()))


@pytest.mark.parametrize('day,asset', [
    ('2026-09-24', '159941.SZ'),  # CASH -> ETF
    ('2026-07-30', '159985.SZ'),  # ETF -> CASH, still exits after missing-price fill
    ('2026-09-01', '518880.SH'),  # ETF -> ETF
])
def test_missing_price_block_survives_real_build_and_report(bot, raw, calendar, monkeypatch, day, asset):
    day = pd.Timestamp(day)
    prices = raw.loc[:day].copy()
    prices.loc[day, asset] = float('nan')
    sources = pd.read_csv(SAVED / 'sources.csv')
    use_calendar(bot, monkeypatch, calendar)
    monkeypatch.setattr(bot, 'load_close', lambda config: (prices.copy(), sources.copy()))
    monkeypatch.setattr(bot, '_load_live_quotes_for_prices', lambda *a, **k: pd.DataFrame())
    now = datetime(day.year, day.month, day.day, 14, 55, tzinfo=bot.CN_TZ)
    frame, source = bot._build_v13_daily(end_date=day, data_state='live', now=now)
    assert frame.iloc[-1].trade_blocked_by_stale_price
    assert frame.iloc[-1].turnover == 0
    status = bot.signal_data_status(frame, live=True, now=now)
    assert not status['signal_valid']
    assert not status['strategy_actionable_now']
    assert asset in status['stale_price_trade_assets']
    report = bot.format_signal_report(frame, source, live=True, now=now)
    params = bot.format_live_params_snapshot(frame, source, live=True, now=now)
    assert '信号有效，无需下单。' not in report
    assert '缺价阻止调仓' in report and asset in report
    assert '缺价阻止调仓' in params


@pytest.mark.parametrize('when,cutoff,valid,expected', [
    ('2026-09-19', '2026-09-18', True, '2026-09-18'),
    ('2026-09-19', '2026-09-17', False, '2026-09-18'),
    ('2026-09-20', '2026-09-17', False, '2026-09-18'),
    ('2026-09-28', '2026-09-24', False, '2026-09-28'),
    ('2026-10-03', '2026-09-30', True, '2026-09-30'),
    ('2026-10-24', '2026-09-30', False, '2026-10-23'),
])
def test_status_uses_calendar_independent_of_price_cutoff(bot, daily, calendar, monkeypatch, when, cutoff, valid, expected):
    use_calendar(bot, monkeypatch, calendar)
    now = datetime.fromisoformat(when + 'T16:00:00').replace(tzinfo=bot.CN_TZ)
    frame = daily.loc[daily.date <= cutoff]
    status = bot.signal_data_status(frame, live=False, now=now)
    assert status['expected_confirmed_session'] == expected
    assert status['signal_valid'] == valid
    assert not status['strategy_actionable_now']


def install_truncated_calendar(bot, raw, calendar, monkeypatch):
    start, end = raw.index.min(), pd.Timestamp('2026-09-24')
    dates = calendar[(calendar >= start) & (calendar <= end)]
    state = {'truncated': True, 'calls': 0}
    def http(url, **kwargs):
        state['calls'] += 1
        p = kwargs['params']
        sessions = dates[:-1] if state['truncated'] else dates
        sessions = sessions[(sessions >= pd.Timestamp(p['start_date'])) & (sessions <= pd.Timestamp(p['end_date']))][-2001:]
        payload = {'data': {'candle': {'000001.SS': [[int(d.strftime('%Y%m%d'))] for d in sessions]}}}
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)
    monkeypatch.setattr(bot, '_HAS_AKSHARE', False)
    monkeypatch.setattr(bot, '_http_get', http)
    monkeypatch.setattr(bot, '_load_cached_cn_trading_days', lambda: None)
    monkeypatch.setattr(bot, '_write_cached_cn_trading_days', lambda *a, **k: None)
    monkeypatch.setattr(bot.time, 'sleep', lambda *a: None)
    initial = bot._expected_cn_trading_days(start, end)
    assert initial.max() == pd.Timestamp('2026-09-23')
    return state, dates


@pytest.mark.parametrize('path', ['alignment', 'provider'])
def test_truncated_calendar_recovers_before_rejecting_valid_prices(bot, raw, calendar, monkeypatch, path):
    state, dates = install_truncated_calendar(bot, raw, calendar, monkeypatch)
    first_calls = state['calls']
    state['truncated'] = False
    prices = raw.loc[:dates.max()]
    if path == 'alignment':
        aligned, end, _ = bot.align_prices_to_common_valid_date(prices, list(bot.ASSETS))
        assert end == dates.max() and len(aligned) == len(prices)
    else:
        monkeypatch.setattr(bot, '_load_akshare_eastmoney_qfq_one_close', lambda code, end: prices[code].dropna())
        monkeypatch.setattr(bot, '_load_tencent_qfq_one_close', lambda *a: pytest.fail('Unnecessary provider fallback'))
        loaded, _ = bot._load_public_close_with_per_code_fallback(list(bot.ASSETS), dates.max())
        pd.testing.assert_frame_equal(loaded, prices, check_freq=False)
    assert state['calls'] > first_calls
    assert state['calls'] <= first_calls + 2


def test_disk_calendar_cannot_mask_forced_refresh(bot, raw, calendar, monkeypatch):
    state, dates = install_truncated_calendar(bot, raw, calendar, monkeypatch)
    stale = (dates[:-1], dates[-2], dates[0], dates[-1])
    monkeypatch.setattr(bot, '_load_cached_cn_trading_days', lambda: stale)
    first_calls = state['calls']
    state['truncated'] = False
    aligned, end, _ = bot.align_prices_to_common_valid_date(raw.loc[:dates[-1]], list(bot.ASSETS))
    assert end == dates[-1] and len(aligned) == len(dates)
    assert state['calls'] > first_calls


@pytest.mark.parametrize('bad_date', ['2026-09-19', '2026-01-01'])
def test_calendar_recovery_keeps_non_session_rejection(bot, raw, calendar, monkeypatch, bad_date):
    state, dates = install_truncated_calendar(bot, raw, calendar, monkeypatch)
    state['truncated'] = False
    prices = raw.loc[:dates[-1]].copy()
    day = pd.Timestamp(bad_date)
    prices.loc[day] = prices.loc[:day].iloc[-1]
    with pytest.raises(ValueError, match='non-trading'):
        bot.align_prices_to_common_valid_date(prices.sort_index(), list(bot.ASSETS))


class Capture:
    BotError = RuntimeError
    def __init__(self, query):
        self.query = SimpleNamespace(text=query)
        self.writes, self.attachments = [], []
    def start_message(self): return self
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def write(self, text): self.writes.append(text)
    def attach_file(self, **kwargs): self.attachments.append(kwargs)


@pytest.mark.parametrize('query,count', [
    ('交易记录 2024年、2025年', 2),
    ('交易记录 2025年、2025年', 1),
    ('交易记录 2025年、2025年1月', 2),
    ('交易记录 2025年、2025-01-02到2025-12-31', 2),
    ('交易记录 2026-10-07、2025年', 2),
    ('交易记录 2025年', 1),
    ('表现', 1),
])
def test_each_explicit_record_window_is_exported(bot, daily, monkeypatch, query, count):
    now = datetime(2026, 10, 24, 16, 0, tzinfo=bot.CN_TZ)
    monkeypatch.setattr(bot, '_now_bj', lambda: now)
    capture = Capture(query)
    monkeypatch.setattr(bot, 'poe', capture)
    monkeypatch.setattr(bot, '_get_daily_for_today', lambda **kwargs: (daily.copy(), 'archived real qfq'))
    monkeypatch.setattr(bot, '_write_nav_curve', lambda *a, **k: None)
    bot.SubDSixEtfV13Bot().run()
    exports = [x for x in capture.attachments if 'trade_records' in x['name']]
    assert len(exports) == count
    assert len({item['name'] for item in exports}) == count
    parsed = bot.parse_all_date_ranges(query, now=now)
    ranges = parsed or [(daily.date.min(), daily.date.max())]
    for item, (start, end) in zip(exports, ranges):
        expected = daily.loc[daily.date.between(start, end) & daily.turnover.gt(1e-12), 'date']
        actual = pd.read_csv(io.BytesIO(item['contents']))
        assert sorted(pd.to_datetime(actual['date'])) == sorted(expected)
    if count > 1:
        text = ''.join(capture.writes)
        assert all(f'{s.date()}~{e.date()}' in text for s, e in ranges)
