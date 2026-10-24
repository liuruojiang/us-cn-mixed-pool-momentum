"""Offline audit: preserved actual prices, clearly separated diagnostic missing quote."""
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace
import importlib.util
import sys
import io
import json
import hashlib
import pandas as pd

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
ENTRY = ROOT / 'poe_subd_six_etf_v1_3_bot.py'
SAVED = ROOT / 'outputs/doublecheck_script_audit_20261007/final_network'
spec = importlib.util.spec_from_file_location('reporting_audit_v13', ENTRY)
bot = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bot
spec.loader.exec_module(bot)
daily = pd.read_csv(SAVED / 'confirmed_daily.csv.gz', parse_dates=['date'])
raw = pd.read_csv(SAVED / 'raw_prices_qfq.csv.gz', parse_dates=['date']).set_index('date')
sources = pd.read_csv(SAVED / 'sources.csv')
calfile = ROOT / 'outputs/script_audit_20261007/calendar_cache_for_replay.csv'
cal = pd.DatetimeIndex(pd.to_datetime(pd.read_csv(calfile)['trade_date']))
bot._load_cn_trading_calendar = lambda start, end: (cal, cal.min(), cal.max(), cal.max())
results = {'entry_sha256': hashlib.sha256(ENTRY.read_bytes()).hexdigest(),
           'input_sha256': {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [SAVED/'confirmed_daily.csv.gz',SAVED/'raw_prices_qfq.csv.gz',calfile]},
           'input_basis': 'preserved actual qfq 2011-12-09..2026-09-30; no current-market claim',
           'fault_injection': [], 'multi_window': {}}

class Capture:
    BotError = RuntimeError
    def __init__(self, query):
        self.query = SimpleNamespace(text=query)
        self.writes = []
        self.attachments = []
    def start_message(self): return self
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def write(self, text): self.writes.append(text)
    def attach_file(self, **kwargs): self.attachments.append(kwargs)

# Normal user request: both years parsed, only one year's records attached.
query = '交易记录 2024年、2025年'
capture = Capture(query)
bot.poe = capture
bot._now_bj = lambda: datetime(2026, 10, 24, 16, 0, tzinfo=bot.CN_TZ)
bot._get_daily_for_today = lambda **kwargs: (daily.copy(), 'preserved actual qfq')
bot._write_nav_curve = lambda *args, **kwargs: None  # only avoid unrelated raster work
bot.SubDSixEtfV13Bot().run()
exports = [x for x in capture.attachments if 'trade_records' in x['name']]
expected = daily.loc[daily.date.dt.year.isin([2024,2025]) & daily.turnover.gt(1e-12)]
actual = pd.concat([pd.read_csv(io.BytesIO(x['contents'])) for x in exports], ignore_index=True)
results['multi_window'] = {'query':query, 'parsed':[list(map(str,r)) for r in bot.parse_all_date_ranges(query)],
                         'expected_records':len(expected),'actual_records':len(actual),
                         'expected_by_year':expected.groupby(expected.date.dt.year).size().to_dict(),
                         'actual_years':sorted(pd.to_datetime(actual.date).dt.year.unique().tolist()),
                         'attachments':[x['name'] for x in exports]}
(OUT/'multi_window_response.txt').write_text(''.join(capture.writes), encoding='utf-8')
for x in exports: (OUT/x['name']).write_bytes(x['contents'])

# Diagnostic fault: remove only latest selected BUY asset's actual price.
# Production loader then forward-fills, blocks the trade, and renders its own result.
day = pd.Timestamp('2026-09-24')
now = datetime(2026,9,24,14,55,tzinfo=bot.CN_TZ)
bot._now_bj = lambda: now
bot._load_live_quotes_for_prices = lambda *args, **kwargs: pd.DataFrame()
for fault in [False, True]:
    prices = raw.loc[:day].copy()
    if fault: prices.loc[day,'159941.SZ'] = float('nan')
    bot.load_close = lambda config, prices=prices: (prices.copy(), sources.copy())
    frame, source_note = bot._build_v13_daily(end_date=day, data_state='live', now=now)
    if not fault:
        core = ['date','position_before','position','holding_fraction','turnover','cost','return','nav']
        expected_baseline = daily.loc[daily.date.le(day),core].reset_index(drop=True)
        pd.testing.assert_frame_equal(frame[core].reset_index(drop=True),expected_baseline,
                                      check_dtype=False,atol=1e-12,rtol=1e-12)
        results['unchanged_baseline_parity'] = {'passed':True,'rows':len(frame),'columns':core,
                                              'reference':str(SAVED/'confirmed_daily.csv.gz')}
    row = frame.iloc[-1]
    status = bot.signal_data_status(frame, live=True, now=now)
    report = bot.format_signal_report(frame, source_note, live=True, now=now)
    name = 'missing_quote' if fault else 'unchanged_baseline'
    (OUT/f'{name}_signal.txt').write_text(report, encoding='utf-8')
    (OUT/f'{name}_last_row.json').write_text(row.to_json(force_ascii=False, indent=2), encoding='utf-8')
    results['fault_injection'].append({'case':name,
        'intervention':'159941.SZ 2026-09-24 close -> NaN' if fault else 'none',
        'production_fields':{k:row[k] for k in ['position_before','position','best_candidate','trade_blocked_by_stale_price','blocked_trade_target','stale_price_trade_assets','turnover','price_ffill_159941.SZ']},
        'status_fields':{k:status[k] for k in ['signal_valid','raw_signal_has_trade','stale_price_trade_assets','execution_note','strategy_actionable_now']},
        'report_claims_valid_no_trade':'信号有效，无需下单。' in report,
        'report_warns_stale_block':'前值填充' in report or '停牌' in report or 'blocked_trade' in report})

(OUT/'reporting_results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
