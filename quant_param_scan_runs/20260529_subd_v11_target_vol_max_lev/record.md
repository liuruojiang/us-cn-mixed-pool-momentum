# Quant Parameter Scan Record

## Run Metadata

- Run id: `20260529_subd_v11_target_vol_max_lev`
- Project: mixed-us-cn-momentum
- Strategy or version: SubD V1.1
- Sleeve or subsystem: six-etf mixed pool
- Parameter group: `target_vol_max_lev`
- Scan type: grid_scan_rebuilt_from_official_v11_path
- Repo or workspace path: `D:\动量策略\美股A股混合池子动量策略`
- Target entrypoint: `run_subd_six_etf_v1_1.py`
- Git branch: `main`
- Git commit: `77afb7679773adad507d0e1cbed79e64737742ed`
- Working tree status before: captured in `scan_meta.json`.

## Research Question

- Baseline: SubD V1.1 staged 50% entry + MA60 overheat overlay with current default `TARGET_VOL = 0.25` and `DEFAULT_MAX_LEV = 1.5`.
- Candidate grid: target vols `0.100, 0.125, 0.150, 0.175, 0.200, 0.225, 0.250, 0.275, 0.300, 0.325, 0.350, 0.375, 0.400` x max leverage `1.00, 1.25, 1.50, 1.75, 2.00`.
- Decision target: find the best practical target-vol and max-leverage pair while separating pure Sharpe/CAGR ranking from cap-saturation risk.
- Source-change rule: `research_only_no_source_change`.
- Required windows: full, last_10y, last_5y, last_3y, last_1y.
- Required metrics: annual return, annualized volatility, Sharpe, max drawdown, cost, turnover, exposure, and leverage-cap saturation.
- Promotion threshold: do not promote a higher-leverage candidate unless full-sample, 5Y, 3Y, and 1Y behavior stay competitive and cap saturation is acceptable.
- Rerun triggers: data refresh, asset-pool change, cost-model change, target-vol implementation change, leverage financing model change, or V1.1 signal/overheat parameter change.

## Implementation Anchor

- Official entrypoint: `run_subd_six_etf_v1_1.py`.
- Function path: `run_staged_entry(...) -> apply_target_vol_overlay(...) -> apply_overheat_overlay(...)`.
- Existing loaders reused: `research_subd_six_etf_weighted_slope.load_close(...)`.
- Existing metrics reused or matched: repo annualization uses 252 trading days and daily NAV drawdown.

| parameter | default | source location |
| --- | ---: | --- |
| `TARGET_VOL` | 0.25 | `run_subd_six_etf_v1_1.py` |
| `DEFAULT_VOL_WINDOW` | 80 | `research_subd_six_etf_weighted_slope.py` |
| `DEFAULT_MAX_LEV` | 1.50 | `research_subd_six_etf_weighted_slope.py` |
| `ONE_WAY_COST` | 0.0010 | `run_subd_six_etf_v1_1.py` |

## Data Snapshot

- Run timestamp: 2026-05-30T00:01:34.910699
- Raw data start: 2011-12-09
- Raw data end: 2026-05-08
- Metrics end / common valid date: 2026-05-08
- Data sources: akshare.fund_etf_hist_sina raw close
- Data mode: normalized_from_existing_official_daily_artifact
- Loader failure, if any: RuntimeError("All qfq data sources failed. 159915.SZ akshare.fund_etf_hist_em daily close: AkShare Eastmoney qfq returned no rows for 159915.SZ / 159915; last_error=('Connection aborted.', RemoteDisconnected('Remote end closed connection without respo | 159915.SZ Eastmoney push2his kline: Eastmoney returned no rows for 159915.SZ; last_error=('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))")
- Local cache paths: none intentionally written by this script.
- Cache write risk: loader may use provider/network cache outside this run only if the imported dependency does so; no repo cache writes were added.
- Missing or stale data: see `sources.csv` and `data_quality.csv`.
- Alignment rules: truncate to the latest date where every asset has non-null close.
- Adjustment mode: raw/unadjusted as served by Sina in the existing official artifact.
- Trading calendar: A-share ETF trading dates after cross-asset non-null alignment.
- Timezone assumptions: date-level China market closes; no intraday timezone conversion in this scan.

## Cost and Execution Assumptions

- Commission/slippage proxy: one-way cost `0.0010` applied to exposure turnover.
- Open-impact: not separately modeled.
- Financing: not separately modeled, including leverage above 1.0; treat `max_lev > 1.5` rows as sensitivity unless a financing model is added.
- Borrow or shorting cost: not applicable; long-only ETF rotation.
- Rebalance/fill timing: close-to-close return uses previous effective holding; target-vol scale is shifted one day before it affects return.
- Leverage or sizing rules: target_vol / 80-day realized vol, clipped to the candidate max leverage, then combined with staged entry and overheat scale.
- Hedge assumptions: none.

## Runtime Override Plan

- Override mechanism: loop over candidate `target_vol` and `max_lev` values and call the official V1.1 overlay functions directly.
- Values restored after each candidate: no module globals were patched.
- Default candidate included in same run: yes, `TARGET_VOL = 0.25`, `MAX_LEV = 1.5`.
- Parity check against official/default output: same function chain as `build_curves(...)`; default pair is the parity anchor.
- If parity check failed, explanation: not applicable.

## Commands

```powershell
python .\quant_param_scan_runs\20260529_subd_v11_target_vol_max_lev\run_scan.py
```

## Output Files

- `scan_summary.csv`: long-form metrics by candidate and window.
- `window_metrics.csv`: wide comparison table by candidate.
- `daily_curves.csv`: same-run daily NAV/return/exposure rows.
- `sources.csv`: data-source rows from the official loader or fallback artifact.
- `data_quality.csv`: row-count and date coverage by asset.
- `scan_meta.json`: this run metadata.
- `command_log.txt`: initialization and scan commands.

## Full-Sample Results

- Best full-sample Sharpe: `tv_30_lev_1` (`TARGET_VOL=0.300`, `MAX_LEV=1.00`), ann_return 27.73%, max_dd -19.29%, Sharpe 1.366.
- Default `tv_25_lev_1p5` full-sample: ann_return 34.04%, max_dd -28.09%, Sharpe 1.332.

| candidate        |   TARGET_VOL |   MAX_LEV |   ann_return |   ann_vol |   sharpe_repo |    max_dd |   avg_weight |   pct_at_max_lev |
|:-----------------|-------------:|----------:|-------------:|----------:|--------------:|----------:|-------------:|-----------------:|
| tv_30_lev_1      |     0.300000 |  1.000000 |     0.277312 |  0.192807 |      1.366029 | -0.192863 |     0.999031 |         0.987128 |
| tv_22p5_lev_1    |     0.225000 |  1.000000 |     0.266634 |  0.185698 |      1.365829 | -0.192863 |     0.969362 |         0.790046 |
| tv_40_lev_1p25   |     0.400000 |  1.250000 |     0.349223 |  0.240615 |      1.365232 | -0.236999 |     1.243731 |         0.970252 |
| tv_32p5_lev_1    |     0.325000 |  1.000000 |     0.277245 |  0.193037 |      1.364356 | -0.192863 |     1.000000 |         1.000000 |
| tv_35_lev_1      |     0.350000 |  1.000000 |     0.277245 |  0.193037 |      1.364356 | -0.192863 |     1.000000 |         1.000000 |
| tv_40_lev_1      |     0.400000 |  1.000000 |     0.277245 |  0.193037 |      1.364356 | -0.192863 |     1.000000 |         1.000000 |
| tv_37p5_lev_1    |     0.375000 |  1.000000 |     0.277245 |  0.193037 |      1.364356 | -0.192863 |     1.000000 |         1.000000 |
| tv_32p5_lev_1p25 |     0.325000 |  1.250000 |     0.344635 |  0.237812 |      1.364175 | -0.236999 |     1.232755 |         0.895881 |
| tv_35_lev_1p5    |     0.350000 |  1.500000 |     0.404899 |  0.277499 |      1.363748 | -0.269724 |     1.434795 |         0.510870 |
| tv_37p5_lev_1p25 |     0.375000 |  1.250000 |     0.348322 |  0.240399 |      1.363467 | -0.236999 |     1.243095 |         0.963101 |

## Window Results

- Best last_5y Sharpe: `tv_10_lev_1p75` (`TARGET_VOL=0.100`, `MAX_LEV=1.75`), ann_return 23.67%, max_dd -7.85%, Sharpe 2.036.

| candidate      |   TARGET_VOL |   MAX_LEV |   ann_return |   ann_vol |   sharpe_repo |    max_dd |   avg_weight |   pct_at_max_lev |
|:---------------|-------------:|----------:|-------------:|----------:|--------------:|----------:|-------------:|-----------------:|
| tv_10_lev_1p75 |     0.100000 |  1.750000 |     0.236729 |  0.107205 |      2.035976 | -0.078481 |     0.512127 |         0.000000 |
| tv_10_lev_1    |     0.100000 |  1.000000 |     0.236729 |  0.107205 |      2.035976 | -0.078481 |     0.512127 |         0.000000 |
| tv_10_lev_1p25 |     0.100000 |  1.250000 |     0.236729 |  0.107205 |      2.035976 | -0.078481 |     0.512127 |         0.000000 |
| tv_10_lev_1p5  |     0.100000 |  1.500000 |     0.236729 |  0.107205 |      2.035976 | -0.078481 |     0.512127 |         0.000000 |
| tv_10_lev_2    |     0.100000 |  2.000000 |     0.236729 |  0.107205 |      2.035976 | -0.078481 |     0.512127 |         0.000000 |
| tv_15_lev_1    |     0.150000 |  1.000000 |     0.357311 |  0.156635 |      2.029145 | -0.111736 |     0.747912 |         0.000000 |
| tv_25_lev_1p5  |     0.250000 |  1.500000 |     0.623896 |  0.256442 |      2.018633 | -0.180994 |     1.229936 |         0.076984 |
| tv_15_lev_1p25 |     0.150000 |  1.250000 |     0.362161 |  0.159674 |      2.015870 | -0.111736 |     0.762526 |         0.000000 |
| tv_15_lev_1p5  |     0.150000 |  1.500000 |     0.362668 |  0.160002 |      2.014398 | -0.111736 |     0.764373 |         0.000000 |
| tv_15_lev_1p75 |     0.150000 |  1.750000 |     0.362668 |  0.160002 |      2.014398 | -0.111736 |     0.764373 |         0.000000 |

## Balanced Ranking

- Top balanced row by local score: `tv_10_lev_1p75`.
- Balanced score = full Sharpe + 0.30 * minimum recent Sharpe - 0.60 * max recent drawdown abs - 0.10 * cap pressure.

| candidate        |   TARGET_VOL |   MAX_LEV |   ann_return_full |   max_dd_full |   sharpe_repo_full |   ann_return_last_5y |   max_dd_last_5y |   sharpe_repo_last_5y |   pct_at_max_lev_full |   balanced_score |
|:-----------------|-------------:|----------:|------------------:|--------------:|-------------------:|---------------------:|-----------------:|----------------------:|----------------------:|-----------------:|
| tv_10_lev_1p75   |     0.100000 |  1.750000 |          0.152509 |     -0.135886 |           1.312480 |             0.236729 |        -0.078481 |              2.035976 |              0.003719 |         1.875812 |
| tv_10_lev_2      |     0.100000 |  2.000000 |          0.152516 |     -0.135886 |           1.310571 |             0.236729 |        -0.078481 |              2.035976 |              0.003432 |         1.873932 |
| tv_10_lev_1p5    |     0.100000 |  1.500000 |          0.151737 |     -0.135886 |           1.309782 |             0.236729 |        -0.078481 |              2.035976 |              0.014874 |         1.871999 |
| tv_10_lev_1      |     0.100000 |  1.000000 |          0.147933 |     -0.135886 |           1.304602 |             0.236729 |        -0.078481 |              2.035976 |              0.030320 |         1.865274 |
| tv_10_lev_1p25   |     0.100000 |  1.250000 |          0.149780 |     -0.135886 |           1.301115 |             0.236729 |        -0.078481 |              2.035976 |              0.010584 |         1.863760 |
| tv_15_lev_1      |     0.150000 |  1.000000 |          0.208507 |     -0.178528 |           1.320733 |             0.357311 |        -0.111736 |              2.029145 |              0.122426 |         1.850192 |
| tv_12p5_lev_2    |     0.125000 |  2.000000 |          0.185279 |     -0.168305 |           1.289069 |             0.292862 |        -0.093080 |              1.996926 |              0.005435 |         1.831755 |
| tv_12p5_lev_1p75 |     0.125000 |  1.750000 |          0.184191 |     -0.168305 |           1.285811 |             0.292862 |        -0.093080 |              1.996926 |              0.006865 |         1.828354 |
| tv_20_lev_1      |     0.200000 |  1.000000 |          0.250191 |     -0.192508 |           1.351759 |             0.430786 |        -0.146924 |              2.011405 |              0.401316 |         1.826895 |
| tv_17p5_lev_1p25 |     0.175000 |  1.250000 |          0.246238 |     -0.213226 |           1.313388 |             0.421697 |        -0.130991 |              1.997440 |              0.080092 |         1.826016 |
| tv_15_lev_2      |     0.150000 |  2.000000 |          0.220813 |     -0.204328 |           1.286649 |             0.362668 |        -0.111736 |              2.014398 |              0.016876 |         1.822238 |
| tv_12p5_lev_1p5  |     0.125000 |  1.500000 |          0.182131 |     -0.168305 |           1.278863 |             0.292862 |        -0.093080 |              1.996926 |              0.000000 |         1.822092 |

## Stability Classification

- Label: pending_final_review
- Evidence: full CSV tables were generated from the official V1.1 code path or a documented fallback official daily artifact.
- Nearby-candidate behavior: inspect `window_metrics.csv` before promotion.
- Recent-window behavior: inspect last_5y, last_3y, and last_1y columns.
- Cost sensitivity: current run includes repo one-way cost only; no additional open-impact or financing sensitivity.
- Data sensitivity: provider/fallback mode is recorded above; common valid end date controls the run.
- Leverage or exposure caveat: high target-vol or high max-leverage candidates can become cap-saturation regimes rather than true volatility targeting.

## Decision

- Decision: recommend `TARGET_VOL = 0.30`, `MAX_LEV = 1.0` for the risk-adjusted/default production setting; it has the best full-sample Sharpe and materially lower drawdown than the current leveraged default, but behaves mostly like a 1x cap regime rather than precise 30% volatility targeting.
- Recommended next action: keep `TARGET_VOL = 0.25`, `MAX_LEV = 1.5` only if the mandate explicitly prefers higher CAGR with deeper drawdown; treat `TARGET_VOL = 0.35`, `MAX_LEV = 1.5` as an aggressive research candidate, not a default, until financing/open-impact sensitivity is added.

## User-Facing Summary

- Recommended best practical setting: `TARGET_VOL = 0.30`, `MAX_LEV = 1.0`.
- Leveraged balanced alternative: keep current `TARGET_VOL = 0.25`, `MAX_LEV = 1.5`.
- Leveraged aggressive alternative: `TARGET_VOL = 0.35`, `MAX_LEV = 1.5`, with higher return but worse recent drawdown profile.
- Runtime seconds: 50.45.

## Finalization

- Finalized at: 2026-05-30T00:02:53+08:00
- Decision: recommend_tv30_maxlev1_risk_adjusted_keep_tv25_maxlev1p5_as_leveraged_balanced_alt
- Stability label: strict_pass_fallback_data_to_20260508_no_financing_open_impact
- Complete checker: PASS
