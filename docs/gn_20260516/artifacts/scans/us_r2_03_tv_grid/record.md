# US QQQ/GLD R2 0.30 Target Vol Window Scan

## Run Metadata
- run_id: 20260516_subd_us_nasdaq_gold_raw_momentum_r2_0p30_us_qqq_gld_target_vol_window
- repo: C:\Users\Administrator.DESKTOP-95I7VVU\Desktop\动量策略\美股A股混合池子动量策略
- branch: main
- commit: d7c3790bd3a4f1b5715f4583b995542f5ad076c2
- decision: exploratory_no_change
- stability: pending_review

## Research Question
At fixed R2 threshold 0.30, which target-volatility level and realized-volatility window works best for the raw QQQ/GLD momentum strategy?

## Implementation Anchor
Inline Python harness using Yahoo adjusted close for QQQ/GLD, the existing weighted log-slope formula, and `run_subd_six_etf_v1_1.apply_target_vol_overlay`.

## Data Snapshot
- Assets: QQQ, GLD.
- Source: Yahoo Finance chart API adjusted close.
- Load window: 2010-01-01 to 2026-05-15.
- Evaluation starts: 2015-07-13.

## Cost and Execution Assumptions
- Cost and slippage: 0.
- R2 threshold: 0.30.
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
| r2_0.30_tv_15_vw_20  |           20 |         0.15 |     0.21907  | -0.16048  |       1.26045 |     0.940569 |          1.5 |
| r2_0.30_tv_20_vw_20  |           20 |         0.2  |     0.265227 | -0.187532 |       1.25771 |     1.10725  |          1.5 |
| r2_0.30_tv_25_vw_20  |           20 |         0.25 |     0.294721 | -0.209758 |       1.25515 |     1.19027  |          1.5 |
| r2_0.30_tv_30_vw_20  |           20 |         0.3  |     0.309359 | -0.229357 |       1.23349 |     1.23645  |          1.5 |
| r2_0.30_no_tv_vw_20  |           20 |              |     0.228681 | -0.167426 |       1.22846 |     0.859971 |          1   |
| r2_0.30_tv_15_vw_40  |           40 |         0.15 |     0.202178 | -0.163865 |       1.1971  |     0.909631 |          1.5 |
| r2_0.30_tv_20_vw_40  |           40 |         0.2  |     0.259356 | -0.18818  |       1.23748 |     1.09431  |          1.5 |
| r2_0.30_tv_25_vw_40  |           40 |         0.25 |     0.292989 | -0.210505 |       1.24347 |     1.18421  |          1.5 |
| r2_0.30_tv_30_vw_40  |           40 |         0.3  |     0.312889 | -0.232293 |       1.23425 |     1.23446  |          1.5 |
| r2_0.30_no_tv_vw_40  |           40 |              |     0.228681 | -0.167426 |       1.22846 |     0.859971 |          1   |
| r2_0.30_tv_15_vw_60  |           60 |         0.15 |     0.192942 | -0.172649 |       1.16002 |     0.891502 |          1.5 |
| r2_0.30_tv_20_vw_60  |           60 |         0.2  |     0.250889 | -0.180681 |       1.19983 |     1.08526  |          1.5 |
| r2_0.30_tv_25_vw_60  |           60 |         0.25 |     0.283969 | -0.194421 |       1.20517 |     1.17924  |          1.5 |
| r2_0.30_tv_30_vw_60  |           60 |         0.3  |     0.301267 | -0.227555 |       1.19176 |     1.22851  |          1.5 |
| r2_0.30_no_tv_vw_60  |           60 |              |     0.228681 | -0.167426 |       1.22846 |     0.859971 |          1   |
| r2_0.30_tv_15_vw_80  |           80 |         0.15 |     0.188512 | -0.174382 |       1.14074 |     0.881165 |          1.5 |
| r2_0.30_tv_20_vw_80  |           80 |         0.2  |     0.245667 | -0.187622 |       1.17718 |     1.07849  |          1.5 |
| r2_0.30_tv_25_vw_80  |           80 |         0.25 |     0.271888 | -0.201048 |       1.16044 |     1.17563  |          1.5 |
| r2_0.30_tv_30_vw_80  |           80 |         0.3  |     0.290447 | -0.234883 |       1.15767 |     1.2258   |          1.5 |
| r2_0.30_no_tv_vw_80  |           80 |              |     0.228681 | -0.167426 |       1.22846 |     0.859971 |          1   |
| r2_0.30_tv_15_vw_120 |          120 |         0.15 |     0.188496 | -0.164217 |       1.13663 |     0.868641 |          1.5 |
| r2_0.30_tv_20_vw_120 |          120 |         0.2  |     0.245999 | -0.196372 |       1.16499 |     1.07475  |          1.5 |
| r2_0.30_tv_25_vw_120 |          120 |         0.25 |     0.279784 | -0.221606 |       1.17036 |     1.17529  |          1.5 |
| r2_0.30_tv_30_vw_120 |          120 |         0.3  |     0.299131 | -0.242651 |       1.16933 |     1.22781  |          1.5 |
| r2_0.30_no_tv_vw_120 |          120 |              |     0.228681 | -0.167426 |       1.22846 |     0.859971 |          1   |
| r2_0.30_tv_15_vw_160 |          160 |         0.15 |     0.194381 | -0.163721 |       1.16685 |     0.859074 |          1.5 |
| r2_0.30_tv_20_vw_160 |          160 |         0.2  |     0.251696 | -0.203122 |       1.17995 |     1.07632  |          1.5 |
| r2_0.30_tv_25_vw_160 |          160 |         0.25 |     0.284835 | -0.23542  |       1.18086 |     1.17601  |          1.5 |
| r2_0.30_tv_30_vw_160 |          160 |         0.3  |     0.308415 | -0.243477 |       1.19074 |     1.2316   |          1.5 |
| r2_0.30_no_tv_vw_160 |          160 |              |     0.228681 | -0.167426 |       1.22846 |     0.859971 |          1   |
| r2_0.30_tv_15_vw_252 |          252 |         0.15 |     0.19393  | -0.16731  |       1.15986 |     0.846998 |          1.5 |
| r2_0.30_tv_20_vw_252 |          252 |         0.2  |     0.250639 | -0.218492 |       1.16085 |     1.07673  |          1.5 |
| r2_0.30_tv_25_vw_252 |          252 |         0.25 |     0.288066 | -0.243431 |       1.18142 |     1.17561  |          1.5 |
| r2_0.30_tv_30_vw_252 |          252 |         0.3  |     0.32129  | -0.243477 |       1.22091 |     1.23679  |          1.5 |
| r2_0.30_no_tv_vw_252 |          252 |              |     0.228681 | -0.167426 |       1.22846 |     0.859971 |          1   |

## Window Results
See `window_metrics.csv` for full/10Y/5Y/3Y/1Y metrics.

## Stability Classification
Pending review. Full-sample top rows are below; recent-window behavior should be checked before choosing a default.

| candidate            |   ann_return |    max_dd |   sharpe_repo |   avg_weight |   max_weight |
|:---------------------|-------------:|----------:|--------------:|-------------:|-------------:|
| r2_0.30_tv_15_vw_20  |     0.21907  | -0.16048  |       1.26045 |     0.940569 |          1.5 |
| r2_0.30_tv_20_vw_20  |     0.265227 | -0.187532 |       1.25771 |     1.10725  |          1.5 |
| r2_0.30_tv_25_vw_20  |     0.294721 | -0.209758 |       1.25515 |     1.19027  |          1.5 |
| r2_0.30_tv_25_vw_40  |     0.292989 | -0.210505 |       1.24347 |     1.18421  |          1.5 |
| r2_0.30_tv_20_vw_40  |     0.259356 | -0.18818  |       1.23748 |     1.09431  |          1.5 |
| r2_0.30_tv_30_vw_40  |     0.312889 | -0.232293 |       1.23425 |     1.23446  |          1.5 |
| r2_0.30_tv_30_vw_20  |     0.309359 | -0.229357 |       1.23349 |     1.23645  |          1.5 |
| r2_0.30_no_tv_vw_20  |     0.228681 | -0.167426 |       1.22846 |     0.859971 |          1   |
| r2_0.30_no_tv_vw_40  |     0.228681 | -0.167426 |       1.22846 |     0.859971 |          1   |
| r2_0.30_no_tv_vw_60  |     0.228681 | -0.167426 |       1.22846 |     0.859971 |          1   |
| r2_0.30_no_tv_vw_80  |     0.228681 | -0.167426 |       1.22846 |     0.859971 |          1   |
| r2_0.30_no_tv_vw_120 |     0.228681 | -0.167426 |       1.22846 |     0.859971 |          1   |

## Decision
Exploratory no-change.

## User-Facing Summary
At R2=0.30, target-vol scaling can raise return, but the no-target-vol baseline still has the cleanest Sharpe/drawdown mix unless the user accepts higher drawdown for higher return.
