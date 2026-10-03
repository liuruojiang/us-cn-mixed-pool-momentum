import hashlib
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

def ledger(prices, opens, flags, scores, delay, cost=.001):
    holding = 'CASH'
    nav = 1.
    rows = []
    for i, date in enumerate(prices.index):
        old = holding
        signal_i = i - delay
        eligible = scores[signal_i] if signal_i >= 0 else {}
        target = bot._target_from_scores(eligible, old, bot.SWITCH_BUFFER)[0]
        blocked = []
        if target != old:
            for asset in {old, target} - {'CASH'}:
                if flags.loc[date, asset] or not np.isfinite(opens.loc[date, asset]) or opens.loc[date, asset] <= 0:
                    blocked.append(asset)
            if blocked:
                target = old
        night = 0.
        if old != 'CASH' and i > 0:
            if target == old:
                # No trade: exact close-close valuation, no invented open needed.
                night = prices.loc[date, old] / prices.iloc[i-1][old] - 1
            else:
                night = opens.loc[date, old] / prices.iloc[i-1][old] - 1
        day = 0.
        if target != old and target != 'CASH':
            day = prices.loc[date, target] / opens.loc[date, target] - 1
        turnover = (float(old != 'CASH') + float(target != 'CASH')) if old != target else 0.
        fee = turnover * cost
        factor = (1 + night) * (1 - fee) * (1 + day)
        nav *= factor
        holding = target
        rows.append(dict(date=date, position_before=old, position=target, fraction_before=float(old!='CASH'), holding_fraction=float(target!='CASH'), exposure_effective=float(old!='CASH'), final_exposure_after_overheat=float(target!='CASH'), weight=1., overheat_on=False, turnover=turnover, cost=fee, gross_return=(1+night)*(1+day)-1, overnight_return=night, intraday_return=day, return_net=factor-1, nav=nav, signal_date=str(prices.index[signal_i].date()) if signal_i>=0 else '', blocked_assets=','.join(blocked)))
    out = pd.DataFrame(rows).set_index('date')
    out['return'] = out.return_net
    out['version'] = bot.VERSION
    out['scenario'] = bot.V13_SCENARIO
    return out

def main():
    started = time.perf_counter()
    source = ROOT / 'quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/price_snapshot_qfq.csv.gz'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == '0cc4af45158d6aaab4594b869b79309a96e8e3cc2f21a0205c38128913bec2aa'
    prices = pd.read_csv(source, parse_dates=['date']).set_index('date')
    saved = pd.read_csv(ROOT / 'quant_comparison_runs/20260904_subd_selected_score_max_5p5/cap_5p5_daily.csv.gz', parse_dates=['date']).set_index('date')
    flags = saved[[f'price_ffill_{c}' for c in bot.ASSETS]].copy()
    flags.columns = list(bot.ASSETS)
    flags = flags.astype(bool)
    opens = pd.DataFrame(index=prices.index)
    audits = json.loads((RUN/'data_audit.json').read_text(encoding='utf-8'))
    assert all(a['close_mismatches']==0 and a.get('independent_overlap',0)>=1000 and a['ratio_mismatches_gt_0p1pct']==0 for a in audits)
    for c in bot.ASSETS:
        data = pd.read_csv(RUN/'prices'/(c+'.csv.gz'),parse_dates=['date']).set_index('date')
        bot._validate_adjusted_close_continuity(c, data.close, 'Tencent OHLC')
        assert (data[['open','close','high','low']] > 0).all().all()
        assert (data.high >= data[['open','close','low']].max(axis=1)-1e-9).all()
        assert (data.low <= data[['open','close','high']].min(axis=1)+1e-9).all()
        opens[c] = data.open.reindex(prices.index)
    baseline = bot.build_curves(prices, bot._build_config(prices.index[-1]), flags)[0]
    parity = {'passed':True,'baseline_max_nav_diff':float((baseline.nav-saved.nav).abs().max())}
    np.testing.assert_allclose(baseline.nav,saved.nav,rtol=0,atol=1e-10)
    assert baseline.position.equals(saved.position)
    scores = [{c:float(row[f'score_{c}']) for c in bot.ASSETS if pd.notna(row[f'score_{c}'])} for _,row in baseline.iterrows()]
    control = ledger(prices,prices,flags,scores,0)
    np.testing.assert_allclose(control.nav,baseline.nav,rtol=0,atol=1e-10)
    assert control.position.equals(baseline.position)
    parity['independent_close_ledger_max_nav_diff'] = float((control.nav-baseline.nav).abs().max())
    candidate = ledger(prices,opens,flags,scores,1)
    prefix = ledger(prices.iloc[:2700],opens.iloc[:2700],flags.iloc[:2700],scores[:2700],1)
    np.testing.assert_allclose(prefix.nav,candidate.nav.iloc[:2700],atol=1e-12,rtol=0)
    no_cost = ledger(prices,opens,flags,scores,1,0)
    assert no_cost.position.equals(candidate.position)
    assert (candidate.nav <= no_cost.nav+1e-10).all()
    assert np.isfinite(candidate.nav).all() and candidate.nav.gt(0).all()
    # Independently value a cash/share account across each open trade.
    wealth = 1.
    old = 'CASH'
    for i, (date,row) in enumerate(candidate.iterrows()):
        new = row.position
        if old == new:
            if old != 'CASH' and i:
                wealth *= prices.loc[date,old]/prices.iloc[i-1][old]
        else:
            if old != 'CASH' and i:
                wealth *= opens.loc[date,old]/prices.iloc[i-1][old]
            wealth *= 1-row.cost
            if new != 'CASH':
                units = wealth/opens.loc[date,new]
                wealth = units*prices.loc[date,new]
        assert abs(wealth-row.nav) < 1e-10
        old = new
    parity.update(prefix_passed=True, independent_share_account_passed=True, no_cost_dominance_passed=True, signal_lag_sessions=1)
    curves = {'same_close':baseline, 'next_open':candidate}
    rows, wide = [], []
    names = {'full_sample':'full','10Y':'last_10y','5Y':'last_5y','3Y':'last_3y','1Y':'last_1y'}
    (RUN/'daily_outputs').mkdir(exist_ok=True)
    common = []
    for name, curve in curves.items():
        curve.to_csv(RUN/'daily_outputs'/(name+'.csv.gz'),index_label='date')
        daily = bot._normalize_daily(curve)
        item = {'candidate':name}
        for label,start,end in bot._default_performance_ranges_for_daily(daily,prices.index[-1],prices.index[0])[:5]:
            m = bot.calc_performance(daily,start,end)
            seg=names[label]
            rows.append(dict(candidate=name,segment=seg,start=m['start'],end=m['end'],rows=m['rows'],ann_return=m['annual'],max_dd=m['maxdd'],ann_vol=m['vol'],sharpe_repo=m['sharpe'],trade_days=m['trades']))
            item['ann_return_'+seg]=m['annual']
            item['max_dd_'+seg]=m['maxdd']
        wide.append(item)
        common.append(dict(candidate=name,**bot.calc_performance(daily,pd.Timestamp('2019-12-05'),prices.index[-1])))
    table=pd.DataFrame(rows)
    base=table[table.candidate.eq('same_close')].set_index('segment')
    table['return_delta_pp']=[100*(r.ann_return-base.loc[r.segment,'ann_return']) for r in table.itertuples()]
    table['drawdown_improvement_pp']=[100*(r.max_dd-base.loc[r.segment,'max_dd']) for r in table.itertuples()]
    table.to_csv(RUN/'scan_summary.csv',index=False)
    pd.DataFrame(wide).to_csv(RUN/'window_metrics.csv',index=False)
    pd.DataFrame(common).to_csv(RUN/'common_lifetime_metrics.csv',index=False)
    (RUN/'parity.json').write_text(json.dumps(parity,indent=2),encoding='utf-8')
    meta=json.loads((RUN/'scan_meta.json').read_text(encoding='utf-8'))
    meta.update(scan_type='matched_close_vs_next_open',baseline={'candidate':'same_close','lookback':25,'score_min':.5,'score_max':5.5,'r2':.25,'buffer':1,'max_lev':1,'overlays':False},candidate_grid=list(curves),data_snapshot={'close':str(source),'close_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'opens':'prices/*.csv.gz Tencent qfq','independent_check':'Sina raw open/close ratio, at least 1016 overlaps per ETF','start':'2011-12-09','end':'2026-09-02','rows':len(prices),'source_change_rule':'No replacement of frozen close, no filled opens, no raw prices used for performance','adjustment':'qfq','calendar':'China ETF sessions / Asia/Shanghai','common_start':'2019-12-05'},cost_model={'one_way':.001,'cash_yield':0,'next_open':'T close signal, next listed session open trade; old holding earns overnight, new holding earns intraday; cost on wealth at open','blocked_trade':'missing/filled execution price blocks whole switch; reevaluate prior-close signal each morning','untraded_missing_open':'use preserved close-close valuation without inventing open','excluded':'capacity, QDII premium, detailed price limit/T+1 fills, extra open impact beyond unified cost'},parity_check=parity,cache_write_risk='none; fetched OHLC saved only in this run',warnings=['Full/10Y are expanding-availability research history','Frozen cutoff 2026-09-02','No independent OOS','Final close signal unexecuted; requires next-session open'],elapsed_sec=time.perf_counter()-started,source_hashes={'entrypoint':hashlib.sha256((ROOT/'poe_subd_six_etf_v1_3_bot.py').read_bytes()).hexdigest()})
    (RUN/'scan_meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print(table.to_string(index=False),flush=True)
    print(pd.DataFrame(common)[['candidate','annual','maxdd','trades']].to_string(index=False),flush=True)
    print('Blocked opens:',candidate.blocked_assets.ne('').sum(),flush=True)
    with (RUN/'command_log.txt').open('a',encoding='utf-8') as f:
        for script in ['fetch_prices.py','audit_data.py','run_scan.py']:
            f.write(f'\npython -X utf8 "{RUN/script}"\n')
        f.write(f'Elapsed replay {meta["elapsed_sec"]:.2f}s; no env overrides; production untouched.\n')

if __name__=='__main__':
    main()
