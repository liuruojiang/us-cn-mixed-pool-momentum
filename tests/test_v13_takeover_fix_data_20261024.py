"""Independent verification of calendar repair; all mutations are diagnostic.

Shared fixtures load actual frozen ETF prices and saved independent calendar.
"""
import pandas as pd
import pytest

from test_v13_takeover_data_20261024 import bot, calendar, prices, seed


@pytest.mark.parametrize('bad_date', ['2026-01-01', '2026-09-19'])
@pytest.mark.parametrize('also_remove_session', [False, True])
def test_shared_false_price_bar_and_calendar_session_are_rejected(bot, prices, calendar, monkeypatch, bad_date, also_remove_session):
    bad = pd.Timestamp(bad_date)
    broken_prices = prices.copy()
    broken_prices.loc[bad] = broken_prices.loc[:bad].iloc[-1]
    broken_calendar = calendar.union(pd.DatetimeIndex([bad])).sort_values()
    if also_remove_session:
        omitted = pd.Timestamp('2026-09-22')
        broken_prices = broken_prices.drop(omitted)
        broken_calendar = broken_calendar.drop(omitted)
    seed(bot, broken_calendar)
    monkeypatch.setattr(bot, '_load_cnfin_trading_calendar', lambda *a: pytest.fail('Invalid dates must not trigger network repair'))
    with pytest.raises(ValueError, match='missing common trading dates|unexpected non-trading'):
        bot.align_prices_to_common_valid_date(broken_prices.sort_index(), list(bot.ASSETS))


def test_repair_does_not_invent_preofficial_sessions(bot, prices, calendar, monkeypatch):
    past_hole = pd.Timestamp('2025-09-22')
    official_hole = pd.Timestamp('2026-09-22')
    assert past_hole in prices.index and official_hole in prices.index
    broken_calendar = calendar.drop([past_hole, official_hole])
    broken_prices = prices.drop([past_hole, official_hole])
    monkeypatch.setattr(bot, '_load_cnfin_trading_calendar', lambda *a: pytest.fail('Matching holes need no network'))
    result = bot._recover_calendar_price_conflict(prices.index.min(), prices.index.max(), broken_prices.index, broken_calendar)
    assert official_hole in result
    assert past_hole not in result
    before = broken_calendar[(broken_calendar >= prices.index.min()) & (broken_calendar < pd.Timestamp('2026-01-01'))]
    assert result[result < pd.Timestamp('2026-01-01')].equals(before)


def test_preofficial_only_call_preserves_provider_exactly(bot, prices, calendar):
    start, end = pd.Timestamp('2025-01-01'), pd.Timestamp('2025-12-31')
    expected = calendar[(calendar >= start) & (calendar <= end)]
    observed = prices.index[(prices.index >= start) & (prices.index <= end)]
    assert bot._recover_calendar_price_conflict(start, end, observed, expected) is expected


def test_matching_official_calendar_preserves_cache_identity(bot, prices, calendar, monkeypatch):
    start, end = prices.index.min(), prices.index.max()
    expected = calendar[(calendar >= start) & (calendar <= end)]
    seed(bot, calendar)
    original_cache = bot._CN_TRADING_DAY_CACHE
    monkeypatch.setattr(bot, '_load_cnfin_trading_calendar', lambda *a: pytest.fail('Correct calendar must not refresh'))
    result = bot._recover_calendar_price_conflict(start, end, prices.index, expected)
    assert result is expected
    assert bot._CN_TRADING_DAY_CACHE is original_cache


def test_repaired_composite_is_reused_in_memory_not_written_as_vendor(bot, prices, calendar, monkeypatch):
    omitted = pd.Timestamp('2026-09-22')
    start, end = prices.index.min(), prices.index.max()
    broken = calendar.drop(omitted)
    seed(bot, broken)
    monkeypatch.setattr(bot, '_write_cached_cn_trading_days', lambda *a, **k: pytest.fail('Composite must not be written as vendor cache'))
    monkeypatch.setattr(bot, '_load_cnfin_trading_calendar', lambda *a: pytest.fail('Matching holes need no network'))
    result = bot._recover_calendar_price_conflict(start, end, prices.drop(omitted).index, broken)
    assert omitted in result
    assert omitted in bot._CN_TRADING_DAY_CACHE
    assert bot._expected_cn_trading_days(start, end).equals(result)


def test_no_calendar_remains_fail_closed(bot, prices):
    assert bot._recover_calendar_price_conflict(prices.index.min(), prices.index.max(), prices.index, None) is None


def test_normal_formal_build_matches_prefixed_commit(bot, prices, calendar, monkeypatch):
    """Paired real-data replay against the audited immutable pre-fix commit."""
    import importlib.util
    import hashlib
    from datetime import datetime
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    baseline_path = root / 'outputs/takeover_fix_20261024/source_snapshots/before_fix.py'
    assert hashlib.sha256(baseline_path.read_bytes()).hexdigest() == '8354e9c4b835c77f11809d5d0b727f54e75e7f7bc5a1fc5aa282ccb73bfd1f57'
    spec = importlib.util.spec_from_file_location('takeover_data_prefixed', baseline_path)
    before = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(before)
    frames = []
    for module in (before, bot):
        seed(module, calendar)
        monkeypatch.setattr(module, '_http_get', lambda *a, **k: pytest.fail('Unexpected network'))
        monkeypatch.setattr(module, '_HAS_AKSHARE', False)
        monkeypatch.setattr(module, '_load_akshare_eastmoney_qfq_one_close', lambda code, end: prices[code].dropna().copy())
        monkeypatch.setattr(module, '_load_tencent_qfq_one_close', lambda *a: pytest.fail('Unexpected provider fallback'))
        frame, source_name = module._build_v13_daily(end_date=prices.index[-1], data_state='confirmed', now=datetime(2026, 9, 24, 16, tzinfo=module.CN_TZ))
        frames.append((frame, source_name))
    pd.testing.assert_frame_equal(frames[0][0], frames[1][0], check_exact=True)
    assert frames[0][1] == frames[1][1]
