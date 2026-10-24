"""Diagnostic time travel on preserved real prices/calendar; no network or orders."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys
from datetime import datetime
import pandas as pd

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
ENTRY = ROOT / 'poe_subd_six_etf_v1_3_bot.py'
spec = importlib.util.spec_from_file_location('weekend_audit', ENTRY)
bot = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bot
spec.loader.exec_module(bot)
source = ROOT / 'outputs/script_audit_20261007/current_network/confirmed_daily.csv.gz'
calendar_source = ROOT / 'outputs/script_audit_20261007/calendar_cache_for_replay.csv'
daily = pd.read_csv(source, parse_dates=['date'])
calendar = pd.DatetimeIndex(pd.to_datetime(pd.read_csv(calendar_source).iloc[:, 0]))
calendar_copy = OUT / 'weekend_calendar.csv'
calendar_copy.write_bytes(calendar_source.read_bytes())
bot.TRADING_CALENDAR_CACHE_PATH = calendar_copy
def forbidden(*args, **kwargs):
    raise RuntimeError('Offline diagnostic: network disabled')
bot._http_get = forbidden
if bot._HAS_AKSHARE:
    bot.ak.tool_trade_date_hist_sina = forbidden

cases = []
for timestamp, cutoff in [
    ('2026-09-19T16:00:00', '2026-09-18'),
    ('2026-09-19T16:00:00', '2026-09-17'),
    ('2026-09-20T16:00:00', '2026-09-17'),
    ('2026-09-28T16:00:00', '2026-09-24'),
    ('2026-10-03T16:00:00', '2026-09-30'),
    ('2026-10-24T16:00:00', '2026-09-30'),
]:
    now = datetime.fromisoformat(timestamp).replace(tzinfo=bot.CN_TZ)
    sample = daily.loc[daily.date <= cutoff].copy()
    bot._now_bj = lambda: now
    actual = bot.signal_data_status(sample, live=False, now=now)
    sessions = bot._status_calendar_sessions(now, sample.date.max())
    expected = calendar[calendar <= pd.Timestamp(now.date())].max()
    report = bot.format_signal_report(sample, 'preserved real qfq; diagnostic clock', live=False, now=now)
    name = timestamp[:10] + '_' + cutoff
    (OUT / (name + '_signal.txt')).write_text(report, encoding='utf-8')
    cases.append({'now_bj': now.isoformat(), 'data_cutoff': cutoff,
                  'independent_expected': str(expected.date()),
                  'actual_calendar_sessions': sessions,
                  'status': actual})
old_status_function = bot._status_calendar_sessions
import inspect
function_source = inspect.getsource(old_status_function)
old_branch = '''    if today.weekday() >= 5 and (latest_market is None or latest_market <= today):
        required_end = latest_market if latest_market is not None else _fallback_previous_business_day(today)
    else:
        required_end = today
        if latest_market is not None:
            required_end = max(required_end, latest_market)
'''
new_branch = '''    required_end = today
    if latest_market is not None:
        required_end = max(required_end, latest_market)
'''
assert old_branch in function_source
exec(compile(function_source.replace(old_branch, new_branch), '<diagnostic_candidate_only>', 'exec'), bot.__dict__)
for case in cases:
    now = datetime.fromisoformat(case['now_bj'])
    sample = daily.loc[daily.date <= case['data_cutoff']].copy()
    bot._now_bj = lambda: now
    candidate = bot.signal_data_status(sample, live=False, now=now)
    case['diagnostic_candidate_status'] = candidate
    case['should_be_valid'] = str(sample.date.max().date()) == case['independent_expected']
    assert candidate['signal_valid'] == case['should_be_valid']
bot._status_calendar_sessions = old_status_function
result = {'diagnostic': True, 'production_modified': False,
          'source_sha256': hashlib.sha256(ENTRY.read_bytes()).hexdigest(),
          'daily_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
          'calendar_sha256': hashlib.sha256(calendar_source.read_bytes()).hexdigest(),
          'cases': cases}
(OUT / 'weekend_results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
for c in cases:
    print(c['now_bj'], c['data_cutoff'], 'expected', c['independent_expected'],
          'actual', c['actual_calendar_sessions']['expected_confirmed_session'],
          'signal_valid', c['status']['signal_valid'], 'label', c['status'].get('label'))
