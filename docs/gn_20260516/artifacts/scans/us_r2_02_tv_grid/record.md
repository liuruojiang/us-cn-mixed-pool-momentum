# US QQQ/GLD R2 0.20 Target Vol Window Scan

## Run Metadata
- run_id: 20260516_subd_us_nasdaq_gold_raw_momentum_r2_0p20_us_qqq_gld_target_vol_window
- repo: C:\Users\Administrator.DESKTOP-95I7VVU\Desktop\动量策略\美股A股混合池子动量策略
- branch: main
- commit: d7c3790bd3a4f1b5715f4583b995542f5ad076c2
- decision: exploratory_no_change
- stability: pending_review

## Research Question
At fixed R2 threshold 0.20, which target-volatility level and realized-volatility window works best for the raw QQQ/GLD momentum strategy?

## Implementation Anchor
Inline Python harness using Yahoo adjusted close for QQQ/GLD, the existing weighted log-slope formula, and `run_subd_six_etf_v1_1.apply_target_vol_overlay`.

## Data Snapshot
- Assets: QQQ, GLD.
- Source: Yahoo Finance chart API adjusted close.
- Load window: 2010-01-01 to 2026-05-15.
- Evaluation starts: 2015-07-13.

## Cost and Execution Assumptions
- Cost and slippage: 0.
- R2 threshold: 0.20.
- Target vol: scanned target-vol levels with 20/40/60/80/120/160/252 realized-vol windows, one-day shifted effective scale, max leverage 1.5.
- Disabled: score positivity, score cap, switch buffer, staged entry, overheat.

## Runtime Override Plan
No production files changed. This is a scratch scan under `quant_param_scan_runs`.

## Commands
See `command_log.txt`.

## Output Files
- `scan_summary.csv`
- `window_metrics.csv`
- `selection.csv`
- `daily_curves.csv`

## Full-Sample Results
| candidate            |   VOL_WINDOW |   TARGET_VOL |   ann_return |    max_dd |   sharpe_repo |   avg_weight |   max_weight |
|:---------------------|-------------:|-------------:|-------------:|----------:|--------------:|-------------:|-------------:|
| r2_0.20_tv_15_vw_20  |           20 |         0.15 |     0.231176 | -0.208374 |       1.31125 |     0.973141 |          1.5 |
| r2_0.20_tv_20_vw_20  |           20 |         0.2  |     0.282244 | -0.267301 |       1.30305 |     1.161    |          1.5 |
| r2_0.20_tv_25_vw_20  |           20 |         0.25 |     0.313193 | -0.314743 |       1.29029 |     1.26029  |          1.5 |
| r2_0.20_tv_30_vw_20  |           20 |         0.3  |     0.328997 | -0.344501 |       1.26956 |     1.31216  |          1.5 |
| r2_0.20_no_tv_vw_20  |           20 |              |     0.237405 | -0.251248 |       1.24343 |     0.916789 |          1   |
| r2_0.20_tv_15_vw_40  |           40 |         0.15 |     0.210221 | -0.200852 |       1.24205 |     0.938652 |          1.5 |
| r2_0.20_tv_20_vw_40  |           40 |         0.2  |     0.278418 | -0.246978 |       1.29942 |     1.14515  |          1.5 |
| r2_0.20_tv_25_vw_40  |           40 |         0.25 |     0.315605 | -0.301614 |       1.29776 |     1.2535   |          1.5 |
| r2_0.20_tv_30_vw_40  |           40 |         0.3  |     0.334352 | -0.347673 |       1.27764 |     1.30961  |          1.5 |
| r2_0.20_no_tv_vw_40  |           40 |              |     0.237405 | -0.251248 |       1.24343 |     0.916789 |          1   |
| r2_0.20_tv_15_vw_60  |           60 |         0.15 |     0.204695 | -0.190597 |       1.22392 |     0.920541 |          1.5 |
| r2_0.20_tv_20_vw_60  |           60 |         0.2  |     0.269602 | -0.231196 |       1.26269 |     1.13577  |          1.5 |
| r2_0.20_tv_25_vw_60  |           60 |         0.25 |     0.303841 | -0.28172  |       1.25167 |     1.24755  |          1.5 |
| r2_0.20_tv_30_vw_60  |           60 |         0.3  |     0.32187  | -0.329448 |       1.23241 |     1.30481  |          1.5 |
| r2_0.20_no_tv_vw_60  |           60 |              |     0.237405 | -0.251248 |       1.24343 |     0.916789 |          1   |
| r2_0.20_tv_15_vw_80  |           80 |         0.15 |     0.197951 | -0.194356 |       1.19414 |     0.909016 |          1.5 |
| r2_0.20_tv_20_vw_80  |           80 |         0.2  |     0.262047 | -0.243925 |       1.23208 |     1.1296   |          1.5 |
| r2_0.20_tv_25_vw_80  |           80 |         0.25 |     0.293148 | -0.297867 |       1.21514 |     1.24387  |          1.5 |
| r2_0.20_tv_30_vw_80  |           80 |         0.3  |     0.309609 | -0.348633 |       1.19599 |     1.30245  |          1.5 |
| r2_0.20_no_tv_vw_80  |           80 |              |     0.237405 | -0.251248 |       1.24343 |     0.916789 |          1   |
| r2_0.20_tv_15_vw_120 |          120 |         0.15 |     0.198424 | -0.1973   |       1.19488 |     0.895842 |          1.5 |
| r2_0.20_tv_20_vw_120 |          120 |         0.2  |     0.2581   | -0.249451 |       1.20637 |     1.12586  |          1.5 |
| r2_0.20_tv_25_vw_120 |          120 |         0.25 |     0.297301 | -0.303268 |       1.21394 |     1.24334  |          1.5 |
| r2_0.20_tv_30_vw_120 |          120 |         0.3  |     0.3138   | -0.344621 |       1.19594 |     1.3038   |          1.5 |
| r2_0.20_no_tv_vw_120 |          120 |              |     0.237405 | -0.251248 |       1.24343 |     0.916789 |          1   |
| r2_0.20_tv_15_vw_160 |          160 |         0.15 |     0.202623 | -0.206328 |       1.21458 |     0.886748 |          1.5 |
| r2_0.20_tv_20_vw_160 |          160 |         0.2  |     0.264252 | -0.26699  |       1.22073 |     1.12749  |          1.5 |
| r2_0.20_tv_25_vw_160 |          160 |         0.25 |     0.301296 | -0.322278 |       1.22019 |     1.24477  |          1.5 |
| r2_0.20_tv_30_vw_160 |          160 |         0.3  |     0.322306 | -0.350941 |       1.21369 |     1.308    |          1.5 |
| r2_0.20_no_tv_vw_160 |          160 |              |     0.237405 | -0.251248 |       1.24343 |     0.916789 |          1   |
| r2_0.20_tv_15_vw_252 |          252 |         0.15 |     0.197827 | -0.233191 |       1.18524 |     0.874061 |          1.5 |
| r2_0.20_tv_20_vw_252 |          252 |         0.2  |     0.263418 | -0.300439 |       1.20613 |     1.12151  |          1.5 |
| r2_0.20_tv_25_vw_252 |          252 |         0.25 |     0.300392 | -0.347852 |       1.20555 |     1.24636  |          1.5 |
| r2_0.20_tv_30_vw_252 |          252 |         0.3  |     0.333775 | -0.357011 |       1.2386  |     1.31495  |          1.5 |
| r2_0.20_no_tv_vw_252 |          252 |              |     0.237405 | -0.251248 |       1.24343 |     0.916789 |          1   |

## Window Results
See `window_metrics.csv` for full/10Y/5Y/3Y/1Y metrics.

## Stability Classification
Pending review. Full-sample top rows are below; compare with the R2=0.30 scan before choosing a default.

| candidate           |   ann_return |    max_dd |   sharpe_repo |   avg_weight |   max_weight |
|:--------------------|-------------:|----------:|--------------:|-------------:|-------------:|
| r2_0.20_tv_15_vw_20 |     0.231176 | -0.208374 |       1.31125 |     0.973141 |          1.5 |
| r2_0.20_tv_20_vw_20 |     0.282244 | -0.267301 |       1.30305 |     1.161    |          1.5 |
| r2_0.20_tv_20_vw_40 |     0.278418 | -0.246978 |       1.29942 |     1.14515  |          1.5 |
| r2_0.20_tv_25_vw_40 |     0.315605 | -0.301614 |       1.29776 |     1.2535   |          1.5 |
| r2_0.20_tv_25_vw_20 |     0.313193 | -0.314743 |       1.29029 |     1.26029  |          1.5 |
| r2_0.20_tv_30_vw_40 |     0.334352 | -0.347673 |       1.27764 |     1.30961  |          1.5 |
| r2_0.20_tv_30_vw_20 |     0.328997 | -0.344501 |       1.26956 |     1.31216  |          1.5 |
| r2_0.20_tv_20_vw_60 |     0.269602 | -0.231196 |       1.26269 |     1.13577  |          1.5 |
| r2_0.20_tv_25_vw_60 |     0.303841 | -0.28172  |       1.25167 |     1.24755  |          1.5 |
| r2_0.20_no_tv_vw_20 |     0.237405 | -0.251248 |       1.24343 |     0.916789 |          1   |
| r2_0.20_no_tv_vw_40 |     0.237405 | -0.251248 |       1.24343 |     0.916789 |          1   |
| r2_0.20_no_tv_vw_60 |     0.237405 | -0.251248 |       1.24343 |     0.916789 |          1   |

## Decision
Exploratory no-change.

## User-Facing Summary
At R2=0.20, target-vol scaling raises returns strongly but drawdown rises faster than in the R2=0.30 defensive line.
