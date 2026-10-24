"""Independent report/export adversarial checks on archived real market data."""
import importlib.util
import io
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SAVED = ROOT / 'outputs/doublecheck_script_audit_20261007/final_network'
EVIDENCE = ROOT / 'outputs/repair_audit_20261024/reporting'


@pytest.fixture
def context(monkeypatch):
    spec = importlib.util.spec_from_file_location('independent_reporting', ROOT / 'poe_subd_six_etf_v1_3_bot.py')
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)
    daily = pd.read_csv(SAVED / 'confirmed_daily.csv.gz', parse_dates=['date'])
    calendar = pd.DatetimeIndex(pd.to_datetime(pd.read_csv(ROOT / 'outputs/script_audit_20261007/calendar_cache_for_replay.csv')['trade_date']))
    monkeypatch.setattr(bot, '_http_get', lambda *a, **k: pytest.fail('Network not allowed in archived replay'))
    monkeypatch.setattr(bot, '_HAS_AKSHARE', False)
    # Enter at the archived input boundary, retaining the real loader's cache
    # publication and coverage semantics used by independent freshness checks.
    monkeypatch.setattr(bot, '_load_cached_cn_trading_days', lambda: (calendar, calendar.max(), calendar.min(), calendar.max()))
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    return bot, daily


class Capture:
    BotError = RuntimeError

    def __init__(self, query, failed_attachment=None):
        self.query = SimpleNamespace(text=query)
        self.writes, self.attachments, self.attempts = [], [], []
        self.failed_attachment = failed_attachment

    def start_message(self): return self
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def write(self, text): self.writes.append(text)
    def overwrite(self, text): self.writes = [text]
    def attach_file(self, **item):
        self.attempts.append(item['name'])
        if self.failed_attachment and self.failed_attachment in item['name']:
            raise RuntimeError('diagnostic attachment unavailable')
        self.attachments.append(item)


def run_query(context, monkeypatch, query, failed_attachment=None):
    bot, daily = context
    cap = Capture(query, failed_attachment)
    monkeypatch.setattr(bot, '_now_bj', lambda: datetime(2026, 10, 24, 16, tzinfo=bot.CN_TZ))
    monkeypatch.setattr(bot, 'poe', cap)
    monkeypatch.setattr(bot, '_get_daily_for_today', lambda **k: (daily.copy(), 'archived qfq diagnostic replay'))
    monkeypatch.setattr(bot, '_write_nav_curve', lambda *a, **k: None)
    bot.SubDSixEtfV13Bot().run()
    return cap


@pytest.mark.parametrize('query,windows', [
    ('交易记录 2024年；2025年；2024年', [('2024-01-01', '2024-12-31'), ('2025-01-01', '2025-12-31')]),
    ('交易记录 2024-12-01到2025-01-31、2025年1月', [('2024-12-01', '2025-01-31'), ('2025-01-01', '2025-01-31')]),
    ('交易记录 2024-02-29、2025-01-01、2026-10-24', [('2024-02-29', '2024-02-29'), ('2025-01-01', '2025-01-01'), ('2026-10-24', '2026-10-24')]),
    ('交易记录 2000年、2025年、2030年', [('2000-01-01', '2000-12-31'), ('2025-01-01', '2025-12-31'), ('2030-01-01', '2030-12-31')]),
    ('交易记录 2024年、2025年和2026年', [('2024-01-01', '2024-12-31'), ('2025-01-01', '2025-12-31'), ('2026-01-01', '2026-12-31')]),
    ('交易记录 2024年、2025年、2026年', [('2024-01-01', '2024-12-31'), ('2025-01-01', '2025-12-31'), ('2026-01-01', '2026-12-31')]),
    ('交易记录 2024年、2025年和2024年', [('2024-01-01', '2024-12-31'), ('2025-01-01', '2025-12-31')]),
])
def test_export_requested_sets_without_parser_oracle(context, monkeypatch, query, windows):
    _, daily = context
    cap = run_query(context, monkeypatch, query)
    actual = {a['name']: pd.read_csv(io.BytesIO(a['contents'])) for a in cap.attachments}
    expected_names = {f'subd_v13_trade_records_{start}_{end}.csv' for start, end in windows}
    assert set(actual) == expected_names
    for start, end in windows:
        rows = actual[f'subd_v13_trade_records_{start}_{end}.csv']
        expected = daily.loc[daily.date.between(start, end) & daily.turnover.gt(1e-12)]
        assert set(pd.to_datetime(rows.date)) == set(expected.date)
        assert len(rows) == len(expected)
        assert rows.cost.sum() == pytest.approx(expected.cost.sum())


def test_attachment_failure_is_local_and_does_not_claim_success(context, monkeypatch):
    cap = run_query(context, monkeypatch, '交易记录 2024年、2025年', '2025-01-01')
    assert len(cap.attempts) == 2 and len(cap.attachments) == 1
    assert '2024-01-01' in cap.attachments[0]['name']
    text = ''.join(cap.writes)
    assert 'CSV: N/A: diagnostic attachment unavailable' in text
    assert '完整调仓记录CSV: **subd_v13_trade_records_2025' not in text
    (EVIDENCE / 'attachment_failure.txt').write_text(text, encoding='utf-8')


@pytest.mark.parametrize('when,cutoff,expected,valid', [
    ('2025-01-01T16:00:00+08:00', '2024-12-31', '2024-12-31', True),
    ('2025-01-04T16:00:00+08:00', '2024-12-31', '2025-01-03', False),
    ('2025-01-04T16:00:00+08:00', '2025-01-03', '2025-01-03', True),
    ('2026-01-01T16:00:00+08:00', '2025-12-31', '2025-12-31', True),
    ('2026-01-04T16:00:00+08:00', '2025-12-30', '2025-12-31', False),
    ('2026-01-04T16:00:00+08:00', '2025-12-31', '2025-12-31', True),
    ('2026-10-07T16:00:00+08:00', '2026-09-29', '2026-09-30', False),
    ('2026-10-07T16:00:00+08:00', '2026-09-30', '2026-09-30', True),
])
def test_cross_year_holiday_and_timezone_equivalence(context, when, cutoff, expected, valid):
    bot, daily = context
    frame = daily.loc[daily.date <= cutoff]
    local = datetime.fromisoformat(when)
    for now in (local, local.astimezone(timezone.utc)):
        status = bot.signal_data_status(frame, live=False, now=now)
        assert status['expected_confirmed_session'] == expected
        assert status['signal_valid'] is valid
        assert not status['strategy_actionable_now']
        rendered = bot.format_signal_report(frame, 'archived qfq', now=now)
        if not valid:
            assert '信号有效，无需下单。' not in rendered
            assert '数据滞后' in rendered


@pytest.mark.parametrize('day,missing', [
    ('2026-09-01', ['518880.SH', '159985.SZ']),
    ('2026-09-24', ['159941.SZ']),
    ('2026-07-30', ['159985.SZ']),
])
def test_blocked_output_survives_csv_and_time_rollover(context, monkeypatch, day, missing):
    bot, _ = context
    raw = pd.read_csv(SAVED / 'raw_prices_qfq.csv.gz', parse_dates=['date']).set_index('date').loc[:day]
    sources = pd.read_csv(SAVED / 'sources.csv')
    # Explicit diagnostic fault: only selected current-day raw prices removed.
    raw.loc[pd.Timestamp(day), missing] = float('nan')
    monkeypatch.setattr(bot, 'load_close', lambda config: (raw.copy(), sources.copy()))
    monkeypatch.setattr(bot, '_load_live_quotes_for_prices', lambda *a, **k: pd.DataFrame())
    now = datetime.fromisoformat(day + 'T14:55:00').replace(tzinfo=bot.CN_TZ)
    daily, source = bot._build_v13_daily(end_date=pd.Timestamp(day), data_state='live', now=now)
    assert daily.iloc[-1].trade_blocked_by_stale_price
    assert daily.iloc[-1].turnover == 0
    reloaded = pd.read_csv(io.StringIO(daily.to_csv(index=False)), parse_dates=['date'])
    for frame in (daily, reloaded):
        status = bot.signal_data_status(frame, live=True, now=now)
        assert status['trade_blocked_by_stale_price']
        for field in ('signal_valid', 'strategy_actionable_now', 'actionable_now', 'tradable', 'action_required_now'):
            assert status[field] is False
        assert set(missing).issubset(status['stale_price_trade_assets'])
        rendered = bot.format_signal_report(frame, source, live=True, now=now)
        assert '缺价阻止调仓' in rendered
        assert '信号有效，无需下单。' not in rendered
        (EVIDENCE / f'blocked_{day}.txt').write_text(rendered, encoding='utf-8')
        # The next-day stale-data reason may take priority, but never a valid/no-trade claim.
        next_day = now + pd.Timedelta(days=1)
        follow = bot.signal_data_status(frame, live=False, now=next_day)
        assert not follow['signal_valid']
