# US QQQ/GLD R2 Lines with Target Vol Scan

## Run Metadata
- run_id: 20260516_subd_us_nasdaq_gold_raw_momentum_r2_us_qqq_gld_r2_threshold_target_vol
- repo: C:\Users\Administrator.DESKTOP-95I7VVU\Desktop\动量策略\美股A股混合池子动量策略
- branch: main
- commit: d7c3790bd3a4f1b5715f4583b995542f5ad076c2
- decision: exploratory_no_change
- stability: pending_review

## Research Question
For the two selected R2 lines, 0.20 and 0.30, what happens when target volatility is added to the raw QQQ/GLD momentum rule?

## Implementation Anchor
Inline Python harness using Yahoo adjusted close for QQQ/GLD, the existing weighted log-slope formula, and `run_subd_six_etf_v1_1.apply_target_vol_overlay`.

## Data Snapshot
- Assets: QQQ, GLD.
- Source: Yahoo Finance chart API adjusted close.
- Load window: 2010-01-01 to 2026-05-15.
- Evaluation starts: 2015-07-13.

## Cost and Execution Assumptions
- Cost and slippage: 0.
- Target vol: 80-day realized vol, one-day shifted effective scale, max leverage 1.5.
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
| candidate     |   R2_THRESHOLD |   TARGET_VOL |   ann_return |    max_dd |   sharpe_repo |   holding_day_ratio |   avg_weight |   max_weight |
|:--------------|---------------:|-------------:|-------------:|----------:|--------------:|--------------------:|-------------:|-------------:|
| r2_0.20_no_tv |            0.2 |              |     0.237266 | -0.251249 |       1.24278 |            0.916789 |     0.916789 |          1   |
| r2_0.20_tv_20 |            0.2 |         0.2  |     0.261958 | -0.243925 |       1.23172 |            0.916789 |     1.1296   |          1.5 |
| r2_0.30_no_tv |            0.3 |              |     0.228534 | -0.167426 |       1.22775 |            0.859971 |     0.859971 |          1   |
| r2_0.20_tv_25 |            0.2 |         0.25 |     0.293035 | -0.297867 |       1.21475 |            0.916789 |     1.24387  |          1.5 |
| r2_0.20_tv_30 |            0.2 |         0.3  |     0.309471 | -0.348634 |       1.19556 |            0.916789 |     1.30245  |          1.5 |
| r2_0.20_tv_15 |            0.2 |         0.15 |     0.197888 | -0.194354 |       1.19381 |            0.916789 |     0.909016 |          1.5 |
| r2_0.30_tv_20 |            0.3 |         0.2  |     0.245569 | -0.187622 |       1.17678 |            0.859971 |     1.07849  |          1.5 |
| r2_0.30_tv_25 |            0.3 |         0.25 |     0.271763 | -0.201047 |       1.16    |            0.859971 |     1.17563  |          1.5 |
| r2_0.30_tv_30 |            0.3 |         0.3  |     0.290295 | -0.234883 |       1.15717 |            0.859971 |     1.2258   |          1.5 |
| r2_0.30_tv_15 |            0.3 |         0.15 |     0.188442 | -0.174381 |       1.14037 |            0.859971 |     0.881165 |          1.5 |

## Window Results
See `window_metrics.csv` for full/10Y/5Y/3Y/1Y metrics.

## Stability Classification
Pending review. Full-sample top rows are below; recent-window behavior should be reviewed before choosing a default.

| candidate     |   ann_return |    max_dd |   sharpe_repo |   avg_weight |   max_weight |
|:--------------|-------------:|----------:|--------------:|-------------:|-------------:|
| r2_0.20_no_tv |     0.237266 | -0.251249 |       1.24278 |     0.916789 |      1       |
| r2_0.20_tv_20 |     0.261958 | -0.243925 |       1.23172 |     1.1296   |      1.5     |
| r2_0.30_no_tv |     0.228534 | -0.167426 |       1.22775 |     0.859971 |      1       |
| r2_0.20_tv_25 |     0.293035 | -0.297867 |       1.21475 |     1.24387  |      1.5     |
| r2_0.20_tv_40 |     0.332124 | -0.359696 |       1.2015  |     1.35017  |      1.5     |
| r2_0.20_tv_30 |     0.309471 | -0.348634 |       1.19556 |     1.30245  |      1.5     |
| r2_0.20_tv_15 |     0.197888 | -0.194354 |       1.19381 |     0.909016 |      1.5     |
| r2_0.20_tv_35 |     0.321533 | -0.359543 |       1.19013 |     1.33429  |      1.5     |
| r2_0.20_tv_10 |     0.131154 | -0.132369 |       1.18575 |     0.610636 |      1.28534 |
| r2_0.30_tv_40 |     0.315521 | -0.243478 |       1.17715 |     1.26652  |      1.5     |

## Decision
Exploratory no-change.

## User-Facing Summary
Both R2 lines benefit from moderate target-vol scaling. Higher target vol raises return and drawdown until max leverage caps bind; R2 0.30 remains the lower-drawdown line, while R2 0.20 tends to have higher return.
