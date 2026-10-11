import hashlib
import inspect
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[1]
sys.path.insert(0, str(ROOT))
import poe_subd_six_etf_v1_3_bot as bot


def main():
    started = time.perf_counter()
    source = ROOT / 'quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/price_snapshot_qfq.csv.gz'
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert digest == '0cc4af45158d6aaab4594b869b79309a96e8e3cc2f21a0205c38128913bec2aa'
    prices = pd.read_csv(source, parse_dates=['date']).set_index('date')
    saved = pd.read_csv(ROOT / 'quant_comparison_runs/20260904_subd_selected_score_max_5p5/cap_5p5_daily.csv.gz', parse_dates=['date']).set_index('date')
    flags = saved[[f'price_ffill_{c}' for c in bot.ASSETS]].copy()
    flags.columns = list(bot.ASSETS)
    flags = flags.astype(bool)
    config = bot._build_config(prices.index[-1])
    baseline = bot.build_curves(prices, config, flags)[0]
    parity = {'passed': True, 'max_abs_diff': {}}
    for col in ['nav', 'return', 'turnover', 'cost', 'fraction_before', 'holding_fraction']:
        parity['max_abs_diff'][col] = float((baseline[col] - saved[col]).abs().max())
        np.testing.assert_allclose(baseline[col], saved[col], rtol=0, atol=1e-10)
    assert baseline.position.equals(saved.position)
    # Preserve the exact official ledger; inject only a trade-day gate.
    original = bot.run_staged_entry
    original_scorer = bot.calc_scores
    cached = {i: original_scorer(prices, i, bot.R2_THRESHOLD) for i in range(bot.LOOKBACK - 1, len(prices))}
    fn_source = inspect.getsource(original)
    anchor = '        signal_target = ideal if ideal != old_holding else None'
    assert fn_source.count(anchor) == 1
    fn_source = fn_source.replace(anchor, '        if not rebalance_allowed.loc[date]:\n            ideal = old_holding\n' + anchor)
    (RUN / 'ledger_with_weekly_gate.py.txt').write_text(fn_source, encoding='utf-8')
    namespace = dict(bot.__dict__)
    namespace['calc_scores'] = lambda p, i, r2_threshold: cached[i]
    exec(compile(fn_source, str(RUN / 'ledger_with_weekly_gate.py.txt'), 'exec'), namespace)
    curves = {'daily': baseline}
    checks = []
    try:
        bot.run_staged_entry = namespace['run_staged_entry']
        namespace['rebalance_allowed'] = pd.Series(True, index=prices.index)
        identical = bot.build_curves(prices, config, flags)[0]
        np.testing.assert_allclose(identical.nav, baseline.nav, rtol=0, atol=1e-12)
        for weekday, name in enumerate(['mon', 'tue', 'wed', 'thu', 'fri']):
            allowed = pd.Series(False, index=prices.index)
            for week, dates in pd.Series(prices.index, index=prices.index).groupby(prices.index.to_period('W-SUN')):
                target = week.start_time + pd.Timedelta(days=weekday)
                # Do not infer an early rebalance from the truncated final week.
                if target > prices.index[-1]:
                    continue
                prior = dates[dates <= target]
                chosen = prior.iloc[-1] if len(prior) else dates.iloc[0]
                allowed.loc[chosen] = True
            namespace['rebalance_allowed'] = allowed
            curve = bot.build_curves(prices, config, flags)[0]
            curve['rebalance_allowed'] = allowed
            assert not (curve.turnover.gt(0) & ~allowed).any()
            assert (curve.turnover.gt(0).groupby(curve.index.to_period('W-SUN')).sum() <= 1).all()
            assert np.isfinite(curve.nav).all() and curve.nav.gt(0).all()
            np.testing.assert_allclose(curve.cost, curve.turnover * bot.ONE_WAY_COST, atol=1e-12)
            nocost = (1 + curve.gross_return).cumprod()
            assert (curve.nav <= nocost + 1e-10).all()
            cutoff = 2700
            prefix = bot.build_curves(prices.iloc[:cutoff], bot._build_config(prices.index[cutoff-1]), flags.iloc[:cutoff])[0]
            np.testing.assert_allclose(prefix.nav, curve.nav.iloc[:cutoff], rtol=0, atol=1e-12)
            curves['weekly_' + name] = curve
            checks.append({'candidate': 'weekly_' + name, 'off_schedule_trades': 0, 'max_trades_per_week': 1, 'prefix_parity': True, 'cost_identity': True})
    finally:
        bot.run_staged_entry = original
    rows, wide, common = [], [], []
    names = {'full_sample':'full', '10Y':'last_10y', '5Y':'last_5y', '3Y':'last_3y', '1Y':'last_1y'}
    (RUN / 'daily_outputs').mkdir(exist_ok=True)
    for candidate, curve in curves.items():
        curve.to_csv(RUN / 'daily_outputs' / (candidate + '.csv.gz'), index_label='date')
        daily = bot._normalize_daily(curve)
        item = {'candidate':candidate}
        for label, start, end in bot._default_performance_ranges_for_daily(daily, prices.index[-1], prices.index[0])[:5]:
            m = bot.calc_performance(daily, start, end)
            segment = names[label]
            sub = curve.loc[start:end]
            rows.append(dict(candidate=candidate, segment=segment, start=m['start'], end=m['end'], rows=m['rows'], ann_return=m['annual'], max_dd=m['maxdd'], ann_vol=m['vol'], sharpe_repo=m['sharpe'], trade_days=m['trades'], annual_trade_days=m['trades'] * 252 / m['rows'], avg_turnover=sub.turnover.mean(), cost_total=sub.cost.sum(), avg_weight=m['avg_final_exposure']))
            item['ann_return_' + segment] = m['annual']
            item['max_dd_' + segment] = m['maxdd']
        wide.append(item)
        cm = bot.calc_performance(daily, pd.Timestamp('2019-12-05'), prices.index[-1])
        common.append(dict(candidate=candidate, **cm))
    summary = pd.DataFrame(rows)
    base = summary[summary.candidate.eq('daily')].set_index('segment')
    summary['return_delta_pp'] = [100 * (r.ann_return - base.loc[r.segment, 'ann_return']) for r in summary.itertuples()]
    summary['drawdown_improvement_pp'] = [100 * (r.max_dd - base.loc[r.segment, 'max_dd']) for r in summary.itertuples()]
    summary.to_csv(RUN / 'scan_summary.csv', index=False)
    pd.DataFrame(wide).to_csv(RUN / 'window_metrics.csv', index=False)
    pd.DataFrame(common).to_csv(RUN / 'common_lifetime_metrics.csv', index=False)
    pd.DataFrame(checks).to_csv(RUN / 'behavior_checks.csv', index=False)
    (RUN / 'parity.json').write_text(json.dumps(parity, indent=2), encoding='utf-8')
    meta_path = RUN / 'scan_meta.json'
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    meta.update(scan_type='matched_frozen_panel_rebalance_frequency', baseline={'candidate':'daily', 'lookback':25, 'score_min':.5, 'score_max':5.5, 'r2_threshold':.25, 'switch_buffer':1, 'max_lev':1, 'overlays':False}, candidate_grid=list(curves), data_snapshot={'path':str(source), 'sha256':digest, 'start':str(prices.index[0].date()), 'end':str(prices.index[-1].date()), 'rows':len(prices), 'source':'validated Tencent qfq frozen panel', 'adjustment':'forward-adjusted', 'calendar':'China-listed ETF sessions / Asia/Shanghai', 'common_lifetime_start':'2019-12-05', 'source_change_rule':'No refresh, replacement or new fill; preserve accepted flags'}, cost_model={'one_way_cost':.001, 'cash_yield':0, 'timing':'old holding earns close-close; trade at signal-day close; new holding starts next row', 'weekly_rule':'weekday close; holiday uses last session on/before weekday, or first session after if none; incomplete final week never moved earlier', 'risk_exit':'all exits and entries restricted to weekly day', 'excluded':'capacity, QDII premium, tick fill, next-open impact, detailed limit/T+1 simulation'}, parity_check=parity, cache_write_risk='none; frozen input only', warnings=['Full/10Y use assets progressively joining after listing; not six-ETF common lifetime', 'Frozen cutoff 2026-09-02; not latest signal', 'Overlapping fitted history; no new independent OOS'], elapsed_sec=time.perf_counter()-started, source_hashes={'entrypoint':hashlib.sha256((ROOT / 'poe_subd_six_etf_v1_3_bot.py').read_bytes()).hexdigest()})
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    with (RUN / 'command_log.txt').open('a', encoding='utf-8') as f:
        f.write(f'\npython -X utf8 "{Path(__file__).resolve()}"\nElapsed: {meta["elapsed_sec"]:.2f}s; no env overrides; no production/cache writes.\n')
    print(summary[['candidate','segment','ann_return','max_dd','trade_days','return_delta_pp','drawdown_improvement_pp']].to_string(index=False))
    print('Common lifetime:', pd.DataFrame(common)[['candidate','annual','maxdd','trades']].to_string(index=False))


if __name__ == '__main__':
    main()
