from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('no_floor_scan', ROOT / 'run_scan.py')
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


def main():
    long = pd.read_csv(ROOT / 'scan_summary.csv')
    wide = pd.read_csv(ROOT / 'window_metrics.csv')
    assert len(long) == 60 and len(wide) == 12
    base = wide.loc[wide.candidate == 'score_max_5'].iloc[0]
    baseline_curve = pd.read_csv(ROOT / 'daily_outputs/score_max_5.csv.gz', parse_dates=['date']).set_index('date')
    assert int((baseline_curve.best_candidate_score < 0).sum()) > 0
    hashes = {}
    paths = [scan.REPO_ROOT / name for name in ('research_subd_six_etf_weighted_slope.py', 'run_subd_six_etf_v1_1.py', 'poe_subd_six_etf_v1_1_bot.py')]
    paths.append(scan.SOURCE_DIR / 'price_snapshot_qfq.csv.gz')
    for path in paths:
        hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    assert hashes[str(paths[-1])] == '0cc4af45158d6aaab4594b869b79309a96e8e3cc2f21a0205c38128913bec2aa'
    checks = []
    for row in wide.itertuples():
        curve = pd.read_csv(ROOT / 'daily_outputs' / f'{row.candidate}.csv.gz', parse_dates=['date']).set_index('date')
        assert curve.index.equals(baseline_curve.index)
        assert np.isfinite(curve[['nav', 'return', 'turnover', 'cost']]).all().all()
        assert not curve[['buffer_blocked', 'staged_initial', 'fill_on_down_day', 'stop_triggered']].any().any()
        assert set(curve.holding_fraction.unique()).issubset({0., 1.})
        assert np.allclose(curve.cost, curve.turnover * 0.001, rtol=0, atol=1e-14)
        assert (curve.position_before.iloc[1:].to_numpy() == curve.position.iloc[:-1].to_numpy()).all()
        official_curve = curve.copy()
        official_curve['version'] = 'no_floor_research'
        official_curve['scenario'] = row.candidate
        official_curve['exposure_effective'] = curve.fraction_before
        official_curve['weight'] = curve.fraction_before
        official_curve['overheat_on'] = False
        for result in long.loc[long.candidate == row.candidate].itertuples():
            official = scan.v11.summarize(official_curve, pd.Timestamp(result.start), result.segment)
            for field, key in [('ann_return', 'cagr'), ('max_dd', 'maxdd'), ('ann_vol', 'vol'), ('sharpe_repo', 'sharpe')]:
                diff = abs(float(getattr(result, field)) - float(official[key]))
                assert diff < 1e-12, (row.candidate, result.segment, field, diff)
                checks.append({'candidate': row.candidate, 'segment': result.segment, 'metric': field, 'max_abs_diff': diff})
    pd.DataFrame(checks).to_csv(ROOT / 'metric_parity_checks.csv', index=False)
    wide['full_cagr_retention_vs_5'] = wide.ann_return_full / base.ann_return_full
    wide['passes_full_80pct'] = wide.full_cagr_retention_vs_5 >= 0.8
    windows = list(scan.WINDOWS.values())
    wide['return_wins'] = sum(wide[f'ann_return_delta_vs_current_{w}'] > 1e-12 for w in windows)
    wide['dd_wins'] = sum(wide[f'max_dd_delta_vs_current_{w}'] > 1e-12 for w in windows)
    tolerance_ok = pd.Series(True, index=wide.index)
    for w in windows:
        tolerance_ok &= wide[f'ann_return_delta_vs_current_{w}'] >= (-0.01 if w in ('full', 'last_10y', 'last_5y') else -0.03)
    wide['passes_predeclared_dd_rule'] = tolerance_ok & (wide.max_dd_delta_vs_current_full > 1e-12) & (wide.dd_wins >= 3)
    wide[['candidate', 'score_max', 'full_cagr_retention_vs_5', 'passes_full_80pct', 'return_wins', 'dd_wins', 'passes_predeclared_dd_rule']].to_csv(ROOT / 'width_checks.csv', index=False)
    lines = ['# Complete grid results', '', 'Each cell: annual return / max drawdown. All results are retrospective research.', '', '| Cap | Full | 10Y | 5Y | 3Y | 1Y |', '| --- | ---: | ---: | ---: | ---: | ---: |']
    for row in wide.to_dict('records'):
        lines.append('| ' + str(row['score_max']) + ' | ' + ' | '.join(f"{row[f'ann_return_{w}']:.2%} / {row[f'max_dd_{w}']:.2%}" for w in windows) + ' |')
    lines.extend(['', '## Deltas versus cap 5, no lower floor', '', 'Each cell: annual-return delta / max-drawdown improvement, percentage points.', '', '| Cap | Full | 10Y | 5Y | 3Y | 1Y |', '| --- | ---: | ---: | ---: | ---: | ---: |'])
    for row in wide.to_dict('records'):
        lines.append('| ' + str(row['score_max']) + ' | ' + ' | '.join(f"{100*row[f'ann_return_delta_vs_current_{w}']:+.2f} / {100*row[f'max_dd_delta_vs_current_{w}']:+.2f}" for w in windows) + ' |')
    (ROOT / 'result_tables.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    info = {'passed': True, 'metric_parity_max_abs_diff': max(x['max_abs_diff'] for x in checks), 'negative_best_score_days_baseline': int((baseline_curve.best_candidate_score < 0).sum()), 'source_sha256': hashes, 'production_module_defaults_readonly': {'score_min': scan.subd.SCORE_MIN, 'score_max': scan.subd.SCORE_MAX}}
    (ROOT / 'integrity_checks.json').write_text(json.dumps(info, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(info, ensure_ascii=False))
    print(wide[['candidate', 'full_cagr_retention_vs_5', 'return_wins', 'dd_wins', 'passes_predeclared_dd_rule']].to_string(index=False))


if __name__ == '__main__':
    main()
