"""Diagnostic calendar truncation on real archived dates; no market fault asserted."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CODE = ROOT / 'poe_subd_six_etf_v1_3_bot.py'
RAW = ROOT / 'outputs/recert_l1_20260926/prices_raw_qfq_through_20260924.csv.gz'
CAL = ROOT / 'outputs/recert_l1_20260926/calendar_cache_for_audit.csv'


def main():
    spec = importlib.util.spec_from_file_location('calendar_adversarial', CODE)
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)
    prices = pd.read_csv(RAW, parse_dates=['date']).set_index('date')
    calendar = pd.DatetimeIndex(pd.to_datetime(pd.read_csv(CAL).trade_date))
    start, end = prices.index.min(), prices.index.max()
    real_sessions = calendar[(calendar >= start) & (calendar <= end)]
    assert real_sessions.equals(prices.index)
    state = {'truncated': True, 'calls': 0}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return self.payload

    def http(url, **kwargs):
        state['calls'] += 1
        params = kwargs['params']
        sessions = real_sessions[:-1] if state['truncated'] else real_sessions
        sessions = sessions[(sessions >= pd.Timestamp(params['start_date'])) & (sessions <= pd.Timestamp(params['end_date']))]
        sessions = sessions[-2001:]
        response = Response()
        # Only date is consumed by the actual calendar parser.
        response.payload = {'data': {'candle': {'000001.SS': [[int(d.strftime('%Y%m%d'))] for d in sessions]}}}
        return response

    bot._HAS_AKSHARE = False
    bot._http_get = http
    bot._load_cached_cn_trading_days = lambda: None
    bot._write_cached_cn_trading_days = lambda *args, **kwargs: None
    bot.time.sleep = lambda *args: None
    observed = bot._expected_cn_trading_days(start, end)
    output = {'basis': 'diagnostic fault injection; archived true dates with last CNFin bar removed; no actual network/source failure asserted',
              'source_sha256': hashlib.sha256(CODE.read_bytes()).hexdigest(),
              'prices_path': str(RAW), 'prices_sha256': hashlib.sha256(RAW.read_bytes()).hexdigest(),
              'calendar_path': str(CAL), 'calendar_sha256': hashlib.sha256(CAL.read_bytes()).hexdigest(),
              'real_sessions': len(real_sessions), 'required_end': str(end.date()),
              'truncated_calendar_end': str(observed.max().date()), 'initial_http_calls': state['calls']}
    state['truncated'] = False  # The provider has now recovered.
    try:
        bot.align_prices_to_common_valid_date(prices, list(bot.ASSETS))
        output['after_provider_recovers'] = 'accepted'
    except Exception as exc:
        output['after_provider_recovers'] = f'{type(exc).__name__}: {exc}'
    output['http_calls_after_recovery'] = state['calls']
    output['cached_is_usable'] = bot._calendar_is_usable(bot._CN_TRADING_DAY_CACHE, start, end,
        bot._CN_TRADING_DAY_CACHE_COVERAGE_END, bot._CN_TRADING_DAY_CACHE_QUERIED_START, bot._CN_TRADING_DAY_CACHE_QUERIED_END)
    # Control: manually invalidating only the in-memory cache makes the same real input pass.
    bot._CN_TRADING_DAY_CACHE = None
    aligned, common_last, _ = bot.align_prices_to_common_valid_date(prices, list(bot.ASSETS))
    output['after_cache_invalidation'] = {'status': 'accepted', 'rows': len(aligned), 'common_last': str(common_last.date()), 'http_calls': state['calls']}
    output['non_session_negative_controls'] = []
    for bad_day in ('2026-09-19', '2026-01-01'):
        injected = prices.copy()
        injected.loc[pd.Timestamp(bad_day)] = prices.loc[:bad_day].iloc[-1]
        injected = injected.sort_index()
        try:
            bot.align_prices_to_common_valid_date(injected, list(bot.ASSETS))
            outcome = 'accepted'
        except Exception as exc:
            outcome = f'{type(exc).__name__}: {exc}'
        output['non_session_negative_controls'].append({'inserted_date': bad_day, 'outcome': outcome})
    (HERE / 'calendar_cache_result.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
