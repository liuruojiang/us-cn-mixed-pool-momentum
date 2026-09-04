from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

RUN = Path(__file__).resolve().parent
REPO = RUN.parents[1]
sys.path.insert(0, str(REPO))
import research_subd_six_etf_weighted_slope as subd
import run_subd_six_etf_v1_1 as v11
import poe_subd_six_etf_v1_1_bot as poe

SOURCE = REPO / 'quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer'
ACCEPTED = REPO / 'quant_param_scan_runs/20260904_subd_floor_0p5_r2/daily_outputs/r2_0.250.csv.gz'
WINDOWS = {'full_sample': 'Full', '10Y': '10Y', '5Y': '5Y', '3Y': '3Y', '1Y': '1Y'}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO, encoding='utf-8').strip()


def main():
    started = time.perf_counter()
    code_paths = [REPO / p for p in ('research_subd_six_etf_weighted_slope.py', 'run_subd_six_etf_v1_1.py', 'poe_subd_six_etf_v1_1_bot.py')]
    source_hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in code_paths}
    meta = {'created_at': datetime.now().astimezone().isoformat(), 'git_commit': git('rev-parse', 'HEAD'), 'git_status_before': git('status', '--short'), 'source_hashes': source_hashes, 'mode': 'research_only_no_source_change'}
    price_path = SOURCE / 'price_snapshot_qfq.csv.gz'
    price_hash = hashlib.sha256(price_path.read_bytes()).hexdigest()
    assert price_hash == '0cc4af45158d6aaab4594b869b79309a96e8e3cc2f21a0205c38128913bec2aa'
    prices = pd.read_csv(price_path, parse_dates=['date']).set_index('date')[list(subd.ASSETS)].astype(float)
    saved = pd.read_csv(ACCEPTED, parse_dates=['date']).set_index('date')
    assert prices.index.equals(saved.index) and len(prices) == 3578
    assert prices.index.is_unique and prices.index.is_monotonic_increasing
    assert not (prices <= 0).any().any()
    cols = {f'price_ffill_{c}': c for c in subd.ASSETS}
    flags = saved[list(cols)].rename(columns=cols).astype(bool)
    prices.attrs['price_ffill_flags'] = flags
    config = subd.RunConfig(source='akshare_em_qfq', one_way_cost=v11.ONE_WAY_COST, start_date=prices.index.min(), end_date=prices.index.max(), output_tag='selected_vs_original_v11', target_vols=(), vol_window=subd.DEFAULT_VOL_WINDOW, max_lev=subd.DEFAULT_MAX_LEV)
    assert (subd.SCORE_MIN, subd.SCORE_MAX, subd.LOOKBACK) == (0., 5., 25)
    assert (v11.R2_THRESHOLD, v11.SWITCH_BUFFER, v11.INITIAL_ENTRY_FRACTION, v11.TARGET_VOL, config.vol_window, config.max_lev, v11.TARGET_VOL_SCALE_REBALANCE_THRESHOLD) == (.2,1.05,.5,.25,80,1.5,.075)
    all_curves = v11.build_curves(prices, config)
    matches = [c for c in all_curves if c.version.iloc[0] == '1.1']
    assert len(matches) == 1
    original = matches[0]
    print('Original V1.1 full official build_curves completed', flush=True)
    poe_original = poe.build_curves(prices, config, price_ffill_flags=flags)[0]
    print('Original Poe full overlay path completed', flush=True)
    selected_config = replace(config, max_lev=1.)
    old_floor = subd.SCORE_MIN
    try:
        subd.SCORE_MIN = .5
        selected = v11.run_staged_entry(prices, selected_config, v11.EntryCase('selected', 'full_entry', 1.), .25, 1.)
    finally:
        subd.SCORE_MIN = old_floor
    print('Selected research line rerun completed', flush=True)
    old_poe_floor = poe.SCORE_MIN
    try:
        poe.SCORE_MIN = .5
        poe_selected = poe.run_staged_entry(prices, selected_config, poe.EntryCase('selected', 'full_entry', 1.), .25, 1., price_ffill_flags=flags)
    finally:
        poe.SCORE_MIN = old_poe_floor
    checks = []
    def compare(name, left, right, numeric):
        assert left.index.equals(right.index)
        for col in numeric:
            a, b = left[col].to_numpy(float), right[col].to_numpy(float)
            assert np.isfinite(a).all() and np.isfinite(b).all()
            diff = float(np.max(np.abs(a-b)))
            checks.append({'check':name, 'field':col, 'max_abs_diff':diff})
            assert diff <= (1e-10 if col == 'nav' else 1e-12), (name, col, diff)
        mismatch = int((left.position != right.position).sum())
        checks.append({'check':name, 'field':'position', 'max_abs_diff':mismatch})
        assert mismatch == 0
    compare('original_runner_vs_poe', original, poe_original, ['return','nav','turnover','cost','exposure_effective','overheat_scale_effective'])
    compare('selected_vs_accepted', selected, saved, ['return','nav','turnover','cost','fraction_before'])
    compare('selected_runner_vs_poe', selected, poe_selected, ['return','nav','turnover','cost','fraction_before'])
    selected['version'] = 'selected_research'
    selected['scenario'] = 'score_min_0.5_r2_0.25_no_overlays'
    selected['exposure_effective'] = selected.fraction_before
    selected['weight'] = selected.fraction_before
    selected['overheat_on'] = False
    selected['overheat_on_effective'] = False
    curves = {'original_v11':original, 'selected_research':selected}
    windows = v11.build_performance_windows(prices.index, prices.index.max(), v11.EVAL_START)
    rows = []
    for label, curve in curves.items():
        assert np.isfinite(curve[['return','nav','cost','turnover','exposure_effective']]).all().all()
        assert np.allclose(curve.cost, curve.turnover*.001, atol=1e-14, rtol=0)
        assert curve.exposure_effective.min() >= -1e-12
        assert curve.exposure_effective.max() <= (1.5 if label == 'original_v11' else 1.) + 1e-12
        curve.to_csv(RUN / f'{label}_daily.csv.gz', index_label='date', compression='gzip')
        for key, display in WINDOWS.items():
            row = v11.summarize(curve, windows[key], display)
            segment = curve.loc[windows[key]:]
            row['candidate'] = label
            row['invested_day_ratio'] = float(segment.exposure_effective.gt(1e-12).mean())
            row['over_1x_day_ratio'] = float(segment.exposure_effective.gt(1+1e-12).mean())
            row['max_exposure'] = float(segment.exposure_effective.max())
            rows.append(row)
    metrics = pd.DataFrame(rows)
    metrics.to_csv(RUN/'metrics.csv', index=False)
    results = []
    for w in WINDOWS.values():
        o = metrics[(metrics.candidate=='original_v11') & (metrics.window==w)].iloc[0]
        s = metrics[(metrics.candidate=='selected_research') & (metrics.window==w)].iloc[0]
        results.append({'window':w,'start':s.start,'end':s.end,'rows':int(s.days),'original_ann':o.cagr,'original_mdd':o.maxdd,'selected_ann':s.cagr,'selected_mdd':s.maxdd,'ann_delta_pp':100*(s.cagr-o.cagr),'mdd_improvement_pp':100*(s.maxdd-o.maxdd)})
    comparison = pd.DataFrame(results)
    comparison.to_csv(RUN/'window_comparison.csv',index=False)
    pd.DataFrame(checks).to_csv(RUN/'parity_checks.csv',index=False)
    for p in code_paths:
        assert hashlib.sha256(p.read_bytes()).hexdigest() == source_hashes[str(p)]
    meta.update({'data':{'source':'Tencent fqkline qfq frozen panel','path':str(price_path),'sha256':price_hash,'rows':len(prices),'start':str(prices.index.min().date()),'end':str(prices.index.max().date()),'first_observation_by_asset':{c:str(prices[c].first_valid_index().date()) for c in prices},'calendar':'China ETF sessions, Asia/Shanghai, 252 sessions/year','status':'historical available-asset comparison, not fixed-six common-history formal evidence'},'cost_model':{'one_way':.001,'cash_yield':0,'financing':0,'open_impact':'not separately simulated','execution':'official close convention; current return on old holding, next-row return on new holding','limits_liquidity_T1':'not independently simulated'},'original':{'score_min':0,'score_max':5,'r2':.2,'lookback':25,'recency_p':1,'buffer':1.05,'initial_fraction':.5,'target_vol':.25,'vol_window':80,'max_lev':1.5,'scale_deadband':.075,'overheat_enter':.2,'overheat_exit':.18,'overheat_scale':0,'recovery':'same_side_or_exit','bias_window':60,'bias_momentum_window':20},'selected':{'score_min':.5,'score_max':5,'r2':.25,'lookback':25,'recency_p':1,'buffer':1,'initial_fraction':1,'target_vol':'off','max_lev':1,'overheat':'off'},'parity_passed':True,'max_parity_abs_diff':max(x['max_abs_diff'] for x in checks),'source_code_unchanged':True,'elapsed_sec':round(time.perf_counter()-started,3),'git_status_after':git('status','--short'),'limitations':['No untouched OOS; repeatedly used overlapping windows','Financing cost excluded even for original leveraged line, consistent with original implementation','Full history inherits changing asset availability','No automatic production promotion']})
    (RUN/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines = ['# Matched comparison','', '| Window | Original ann/MDD | Selected ann/MDD | Annual delta pp | MDD improvement pp |','| --- | ---: | ---: | ---: | ---: |']
    for r in results:
        lines.append(f"| {r['window']} | {r['original_ann']:.2%} / {r['original_mdd']:.2%} | {r['selected_ann']:.2%} / {r['selected_mdd']:.2%} | {r['ann_delta_pp']:+.2f} | {r['mdd_improvement_pp']:+.2f} |")
    (RUN/'result_tables.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(comparison.to_string(index=False))
    print(json.dumps({'passed':True,'elapsed_sec':meta['elapsed_sec'],'parity_max_abs_diff':meta['max_parity_abs_diff']}))


if __name__ == '__main__':
    main()
