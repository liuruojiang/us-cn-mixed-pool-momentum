# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pandas", "akshare", "requests"]
# ///
"""Validate the user-selected Score ceiling change on the frozen panel."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path, PureWindowsPath

import numpy as np
import pandas as pd

RUN = Path(__file__).resolve().parent
REPO = RUN.parents[1]
sys.path.insert(0, str(REPO))
import research_subd_six_etf_weighted_slope as subd
import run_subd_six_etf_v1_1 as v11
import poe_subd_six_etf_v1_1_bot as poe


def main() -> None:
    previous = RUN.parent / '20260904_subd_selected_vs_original_v11'
    meta = json.loads((previous / 'metadata.json').read_text(encoding='utf-8'))
    price_path = REPO / 'quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/price_snapshot_qfq.csv.gz'
    assert hashlib.sha256(price_path.read_bytes()).hexdigest() == meta['data']['sha256']
    for path, digest in meta['source_hashes'].items():
        assert hashlib.sha256((REPO / PureWindowsPath(path).name).read_bytes()).hexdigest() == digest
    prices = pd.read_csv(price_path, parse_dates=['date']).set_index('date')[list(subd.ASSETS)]
    saved = pd.read_csv(previous / 'selected_research_daily.csv.gz', parse_dates=['date']).set_index('date')
    assert prices.index.equals(saved.index) and len(prices) == 3578
    flags = saved[[f'price_ffill_{c}' for c in prices]].copy()
    flags.columns = prices.columns
    flags = flags.astype(bool)
    prices.attrs['price_ffill_flags'] = flags
    config = subd.RunConfig(source='akshare_em_qfq', one_way_cost=.001, start_date=prices.index.min(), end_date=prices.index.max(), output_tag='selected_score_max_5p5', target_vols=(), vol_window=80, max_lev=1.)
    checks = []

    def compare(name: str, left: pd.DataFrame, right: pd.DataFrame) -> None:
        assert left.index.equals(right.index)
        for field in ['return', 'nav', 'cost', 'turnover', 'fraction_before']:
            diff = float(np.max(np.abs(left[field].to_numpy(float) - right[field].to_numpy(float))))
            assert np.isfinite(diff) and diff < (1e-10 if field == 'nav' else 1e-12)
            checks.append({'check': name, 'field': field, 'max_abs_diff': diff})
        assert left.position.equals(right.position)

    original_globals = (subd.SCORE_MIN, subd.SCORE_MAX, poe.SCORE_MIN, poe.SCORE_MAX)
    try:
        subd.SCORE_MIN = poe.SCORE_MIN = .5
        subd.SCORE_MAX = 5.
        baseline = v11.run_staged_entry(prices, config, v11.EntryCase('baseline', 'full_entry', 1.), .25, 1.)
        compare('baseline_vs_saved', baseline, saved)
        print('Baseline cap=5 matches saved selected curve', flush=True)
        subd.SCORE_MAX = poe.SCORE_MAX = 5.5
        selected = v11.run_staged_entry(prices, config, v11.EntryCase('selected', 'full_entry', 1.), .25, 1.)
        independent = poe.run_staged_entry(prices, config, poe.EntryCase('selected', 'full_entry', 1.), .25, 1., price_ffill_flags=flags)
        compare('selected_runner_vs_poe', selected, independent)
    finally:
        subd.SCORE_MIN, subd.SCORE_MAX, poe.SCORE_MIN, poe.SCORE_MAX = original_globals
    windows = v11.build_performance_windows(prices.index, prices.index.max(), v11.EVAL_START)
    rows = []
    for name, curve, cap in [('cap_5', baseline, 5.), ('cap_5p5', selected, 5.5)]:
        valid_scores = curve.best_candidate_score.dropna()
        assert ((valid_scores > .5) & (valid_scores < cap)).all()
        assert np.isfinite(curve[['return', 'nav', 'cost', 'turnover']]).all().all()
        assert np.allclose(curve.cost, curve.turnover * .001, atol=1e-14, rtol=0)
        assert curve.fraction_before.between(0, 1).all()
        curve['version'] = 'selected_research'
        curve['scenario'] = name
        curve['exposure_effective'] = curve.fraction_before
        curve['weight'] = curve.fraction_before
        curve.to_csv(RUN / f'{name}_daily.csv.gz', index_label='date')
        for key, display in [('full_sample', 'Full'), ('10Y', '10Y'), ('5Y', '5Y'), ('3Y', '3Y'), ('1Y', '1Y')]:
            rows.append(v11.summarize(curve, windows[key], display))
    metrics = pd.DataFrame(rows)
    metrics.to_csv(RUN / 'metrics.csv', index=False)
    comparison = []
    for window in ['Full', '10Y', '5Y', '3Y', '1Y']:
        b = metrics[(metrics.scenario == 'cap_5') & (metrics.window == window)].iloc[0]
        s = metrics[(metrics.scenario == 'cap_5p5') & (metrics.window == window)].iloc[0]
        comparison.append(dict(window=window, baseline_ann=b.cagr, baseline_mdd=b.maxdd, selected_ann=s.cagr, selected_mdd=s.maxdd, ann_delta_pp=100*(s.cagr-b.cagr), mdd_improvement_pp=100*(s.maxdd-b.maxdd)))
    result = pd.DataFrame(comparison)
    result.to_csv(RUN / 'window_comparison.csv', index=False)
    pd.DataFrame(checks).to_csv(RUN / 'parity_checks.csv', index=False)
    for path, digest in meta['source_hashes'].items():
        assert hashlib.sha256((REPO / PureWindowsPath(path).name).read_bytes()).hexdigest() == digest
    meta['comparison_baseline'] = meta['selected'].copy()
    meta['selected']['score_max'] = 5.5
    meta.pop('original', None)
    meta.pop('elapsed_sec', None)
    meta.pop('created_at', None)
    meta['parity_checks'] = checks
    meta['decision'] = 'user_selected_research_only'
    meta['command'] = 'uv run --no-project --python C:/Python314/python.exe python -X utf8 quant_comparison_runs/20260904_subd_selected_score_max_5p5/run_comparison.py'
    (RUN / 'metadata.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(result.to_string(index=False))
    print('PASS: baseline parity, selected Poe parity, costs, bounds, source hashes')


if __name__ == '__main__':
    main()
