import concurrent.futures
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import requests
RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[1]
sys.path.insert(0, str(ROOT))
import poe_subd_six_etf_v1_3_bot as bot

def audit(code, frozen):
    primary = pd.read_csv(RUN / 'prices' / (code + '.csv.gz'), parse_dates=['date']).set_index('date')
    paired = primary.close.to_frame('new').join(frozen[code].rename('old')).dropna()
    delta = (paired.new / paired.old - 1).abs()
    result = {'code':code, 'primary_rows':len(primary), 'matched_frozen_rows':len(paired), 'max_close_relative_diff':float(delta.max()), 'close_mismatches':int((delta > 1e-8).sum()), 'missing_frozen_dates':[str(d.date()) for d in frozen[code].dropna().index.difference(primary.index)]}
    symbol = bot._tencent_fq_symbol(code)
    url = 'https://quotes.sina.cn/cn/api/openapi.php/CN_MarketDataService.getKLineData'
    try:
        response = requests.get(url, params={'symbol':symbol, 'scale':240, 'ma':'no', 'datalen':1023}, timeout=20)
        response.raise_for_status()
        payload = response.json()
        rows = payload['result']['data']
        if isinstance(rows, dict):
            rows = rows['data']
        independent = pd.DataFrame(rows)
        independent['date'] = pd.to_datetime(independent['day'])
        independent = independent.set_index('date').sort_index()
        independent[['open','close']] = independent[['open','close']].astype(float)
        independent.to_csv(RUN / 'prices' / (code + '_sina_raw.csv.gz'), index_label='date')
        joined = (primary.open / primary.close).rename('qfq_ratio').to_frame().join((independent.open / independent.close).rename('raw_ratio')).dropna()
        difference = (joined.qfq_ratio / joined.raw_ratio - 1).abs()
        result.update(independent_source='Sina raw OHLC; comparison uses same-day open/close ratio, adjustment cancels', independent_rows=len(independent), independent_overlap=len(joined), max_open_close_ratio_relative_diff=float(difference.max()), ratio_p99=float(difference.quantile(.99)), ratio_mismatches_gt_0p1pct=int((difference > .001).sum()))
    except Exception as exc:
        result['independent_error'] = str(exc)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result

if __name__ == '__main__':
    frozen = pd.read_csv(ROOT / 'quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/price_snapshot_qfq.csv.gz', parse_dates=['date']).set_index('date')
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda c:audit(c, frozen), bot.ASSETS))
    (RUN / 'data_audit.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
