# Target-Vol Realized-Vol Input Comparison

## Run Metadata

- Run id: 20260621_mixed_us_cn_momentum_subd_six_etf_v1_1_poe_bot_target_vol_target_vol_realized_vol_input
- Run date: 2026-06-21T23:40:45.083491+08:00
- Timezone: Asia/Shanghai
- Operator: Codex
- Project: mixed_us_cn_momentum
- Repo or workspace path: D:\动量策略\美股A股混合池子动量策略
- Version or strategy family: subd_six_etf_v1_1
- Sleeve or subsystem: poe_bot_target_vol
- Parameter group: target_vol_realized_vol_input
- Scan type: paired strategy-mouth comparison
- Target entrypoint: poe_subd_six_etf_v1_1_bot.py
- Git branch: main
- Git commit: 3c83a03ee62b45371f79836d4a0ac56db0f701c6
- Working tree status before: dirty; see scan_meta.json
- Working tree status after: dirty; see scan_meta.json

## Research Question

- Baseline: current production target-vol realized volatility from strategy return including cash days.
- Candidate grid: non-cash asset-return realized volatility, using only days where position_before is not CASH and fraction_before > 0.
- Decision target: quantify full-period impact before deciding whether to promote.
- Source-change rule: no production source constants were changed by this run; candidate is implemented only inside this diagnostic harness.
- Required windows: full, last_10y, last_5y, last_3y, last_1y.
- Required metrics: annualized return, annualized vol, Sharpe, max drawdown, exposure/scale/turnover.
- Promotion threshold: not set; promotion requires user approval after reviewing the result.
- Rerun triggers: source code changes, data-source changes, target-vol constants changes, or official path changes.

## Implementation Anchor

- Official entrypoint: `poe_subd_six_etf_v1_1_bot.py`.
- Function path: `load_close -> align_prices_to_common_valid_date -> run_staged_entry -> target-vol overlay -> apply_overheat_overlay`.
- Existing loaders reused: AkShare/Eastmoney qfq -> Eastmoney HTTP qfq fallback.
- Existing metrics reused: `calc_performance`.

| parameter | default | source location |
| --- | ---: | --- |
| TARGET_VOL | 0.250000 | poe_subd_six_etf_v1_1_bot.py |
| vol_window | 80 | RunConfig |
| max_lev | 1.500000 | RunConfig |
| one_way_cost | 0.001000 | RunConfig |

## Data Snapshot

- Run timestamp: 2026-06-21T23:40:45.083491+08:00
- Raw data start: 2019-12-05
- Raw data end: 2026-06-17
- Metrics start after warmup: 2019-12-05
- Metrics end: 2026-06-17
- Latest trading date or snapshot: 2026-06-17
- Data mode: local_same_slice_fallback
- Data sources: akshare.fund_etf_hist_sina [sina_raw_unadjusted_no_detected_split_patch; ], akshare.fund_etf_hist_sina [sina_raw_split_continuity_159941_pre_20220705_x0.25; ]
- Local cache paths: ['outputs\\cn_trading_days_cache.csv']
- Remote load failure: All qfq data sources failed. 159915.SZ akshare.fund_etf_hist_em daily close: AkShare Eastmoney qfq returned no rows for 159915.SZ / 159915; last_error=('Connection aborted.', RemoteDisconnected('Remote end closed connection without respo | 159915.SZ Eastmoney push2his kline: Eastmoney returned no data for 159915.SZ; last_error=('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
- Cache write risk: trading calendar cache may be refreshed by official calendar helper
- Missing or stale data: remote qfq failed; local fallback is stale vs current date
- Alignment rules: common valid date with current repo ffill tolerance and last_by_asset metadata.
- Adjustment mode: qfq/front-adjusted historical ETF close.
- Trading calendar: A-share trading calendar via repo helper.
- Timezone assumptions: Asia/Shanghai.

## Cost and Execution Assumptions

- Commission: one-way cost 0.1000%.
- Slippage: none beyond one-way cost.
- Open-impact: none.
- Financing: none explicit.
- Borrow or shorting cost: none; long-only ETF strategy.
- Rebalance timing: daily close-to-close model path.
- Fill timing: historical close price assumption from official strategy path.
- Leverage or sizing rules: target-vol cap 1.50x, target vol 25%.
- Hedge assumptions: none.

## Runtime Override Plan

- Override mechanism: diagnostic harness applies candidate overlay after the same base staged-entry curve.
- Values restored after each candidate: yes; no monkey-patch persisted.
- Default candidate included in same run: yes.
- Parity check against official/default output: True.
- If parity check failed, explanation: 0.0

## Commands

```powershell
python quant_param_scan_runs\20260621_mixed_us_cn_momentum_subd_six_etf_v1_1_poe_bot_target_vol_target_vol_realized_vol_input\run_old_new_target_vol_compare.py
```

## Output Files

- `record.md`: this file
- `scan_summary.csv`: long-form metrics
- `window_metrics.csv`: wide window metrics
- `scan_meta.json`: machine metadata
- `command_log.txt`: command log
- Additional artifacts: `scale_diagnostics.csv`, `sources.csv`, `daily_outputs/daily_curves.csv`

## Full-Sample Results

| candidate                    |   ann_return |   ann_vol |   sharpe_repo |    max_dd |   avg_weight |   avg_turnover |   holding_day_ratio |
|:-----------------------------|-------------:|----------:|--------------:|----------:|-------------:|---------------:|--------------------:|
| baseline_strategy_return_vol |     0.6588   |   0.26025 |       2.07525 | -0.174998 |      1.17757 |       0.262498 |             0.90443 |
| candidate_non_cash_asset_vol |     0.556185 |   0.22951 |       2.04216 | -0.147147 |      1.04492 |       0.232273 |             0.90443 |

## Window Results

| candidate                    |   ann_return_last_10y |   max_dd_last_10y |   ann_return_last_5y |   max_dd_last_5y |   ann_return_last_3y |   max_dd_last_3y |   ann_return_last_1y |   max_dd_last_1y |
|:-----------------------------|----------------------:|------------------:|---------------------:|-----------------:|---------------------:|-----------------:|---------------------:|-----------------:|
| baseline_strategy_return_vol |              0.6588   |         -0.174998 |             0.79346  |        -0.174998 |             0.991783 |        -0.163025 |              1.33287 |        -0.128616 |
| candidate_non_cash_asset_vol |              0.556185 |         -0.147147 |             0.656323 |        -0.145928 |             0.810627 |        -0.137426 |              1.0749  |        -0.116289 |

## Stability Classification

- Label: needs_review
- Evidence: see full/window tables and scale diagnostics.
- Nearby-candidate behavior: not scanned; this is a binary old/new comparison.
- Recent-window behavior: see last_3y and last_1y rows.
- Cost sensitivity: not re-scanned; same one-way cost was used for both variants.
- Data sensitivity: dependent on current qfq loader output and calendar alignment.
- Leverage or exposure caveat: candidate changes realized-vol input, so scale/exposure/NAV are strategy-identity changes.

## Decision

- Decision: keep_default_pending_user_review
- Recommended next action: review numbers; promote only in a separate strategy-change commit if desired.
- If `keep_default`, why: current production identity remains baseline until the strategy-level口径 change is explicitly approved.
- If `watchlist`, what would upgrade it: explicit approval after reviewing full-period and recent-window effects.
- If `promote_candidate`, exact constants/config/docs to change: target-vol realized-vol function in Poe bot plus docs and all published performance references.
- If `rerun_required`, exact blocker: rerun if source data was stale or code changes after this run.

## User-Facing Summary

Decision: keep default for now; candidate is research-only pending review. See `scan_summary.csv` and `window_metrics.csv` for exact metrics.

## Finalization

- Finalized at: 2026-06-21T23:41:09+08:00
- Decision: keep_default_pending_user_review
- Stability label: needs_review
- Complete checker: PASS
