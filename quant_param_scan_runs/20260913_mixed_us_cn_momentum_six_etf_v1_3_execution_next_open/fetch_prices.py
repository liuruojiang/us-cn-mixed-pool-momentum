import concurrent.futures
import inspect
import json
import sys
from pathlib import Path
import pandas as pd
RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[1]
sys.path.insert(0, str(ROOT))
import poe_subd_six_etf_v1_3_bot as bot

def fetch(code):
    path = RUN / 'prices' / (code + '.csv.gz')
    if path.exists():
        return code, len(pd.read_csv(path))
    src = inspect.getsource(bot._load_tencent_qfq_one_close)
    pos = src.rfind('    return close')
    assert pos > 0
    src = src[:pos] + '''    df['date'] = pd.to_datetime(df['date'])
    out = df.drop_duplicates('date', keep='last').set_index('date').sort_index().loc[START_DATE:end_date]
    return out.astype(float)
'''
    ns = dict(bot.__dict__)
    exec(src, ns)
    out = ns['_load_tencent_qfq_one_close'](code, pd.Timestamp('2026-09-02'))
    out.to_csv(path, index_label='date')
    return code, len(out)

if __name__ == '__main__':
    (RUN / 'prices').mkdir(exist_ok=True)
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fetch, code):code for code in bot.ASSETS}
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                print(result, flush=True)
                results.append({'code':result[0], 'rows':result[1], 'source':'Tencent qfq full OHLC'})
            except Exception as exc:
                print(futures[future], type(exc).__name__, str(exc), flush=True)
                results.append({'code':futures[future], 'error':str(exc)})
    (RUN / 'fetch_results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
