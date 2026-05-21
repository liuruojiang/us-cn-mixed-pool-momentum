# US QQQ/GLD Switch Buffer Scan

## Run Metadata
- run_id: 20260516_subd_us_nasdaq_gold_raw_momentum_r2_0p30_tv25_vw20_us_qqq_gld_switch_buffer
- repo: C:\Users\Administrator.DESKTOP-95I7VVU\Desktop\动量策略\美股A股混合池子动量策略
- branch: main
- commit: d7c3790bd3a4f1b5715f4583b995542f5ad076c2
- decision: exploratory_no_change
- stability: pending_review

## Research Question
At fixed R2=0.30, target_vol=25%, vol_window=20, does adding a switch buffer improve the QQQ/GLD raw momentum strategy?

## Implementation Anchor
Inline Python harness using Yahoo adjusted close for QQQ/GLD, weighted log-slope scores, switch-buffer logic equivalent to `_target_from_scores`, and `run_subd_six_etf_v1_1.apply_target_vol_overlay`.

## Data Snapshot
- Assets: QQQ, GLD.
- Source: Yahoo Finance chart API adjusted close.
- Load window: 2010-01-01 to 2026-05-15.
- Evaluation starts: 2015-07-13.

## Cost and Execution Assumptions
- Cost and slippage: 0.
- R2 threshold: 0.30.
- Target vol: 25%, 20-day realized vol, one-day shifted effective scale, max leverage 1.5.
- Switch buffer: scanned 1.00 to 1.50 step 0.01 plus 1.60 to 3.00 step 0.10.
- Disabled: score positivity, score cap, staged entry, overheat.

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
| candidate   |   SWITCH_BUFFER |   ann_return |    max_dd |   sharpe_repo |   asset_switches |   buffer_blocked_days |   avg_weight |   max_weight |
|:------------|----------------:|-------------:|----------:|--------------:|-----------------:|----------------------:|-------------:|-------------:|
| switch_1.00 |            1    |     0.294439 | -0.209756 |       1.2541  |              276 |                     0 |      1.19027 |          1.5 |
| switch_1.05 |            1.05 |     0.303062 | -0.209756 |       1.28437 |              270 |                    11 |      1.18972 |          1.5 |
| switch_1.10 |            1.1  |     0.318387 | -0.209756 |       1.33811 |              264 |                    25 |      1.19226 |          1.5 |
| switch_1.20 |            1.2  |     0.324256 | -0.209756 |       1.35706 |              262 |                    33 |      1.1918  |          1.5 |
| switch_1.30 |            1.3  |     0.327109 | -0.209756 |       1.36641 |              262 |                    39 |      1.19186 |          1.5 |
| switch_1.40 |            1.4  |     0.332804 | -0.209756 |       1.38565 |              260 |                    58 |      1.19175 |          1.5 |
| switch_1.50 |            1.5  |     0.342485 | -0.204069 |       1.41782 |              258 |                    69 |      1.19236 |          1.5 |
| switch_1.60 |            1.6  |     0.342905 | -0.204069 |       1.41895 |              258 |                    84 |      1.19246 |          1.5 |
| switch_1.80 |            1.8  |     0.342685 | -0.204069 |       1.42209 |              252 |                   111 |      1.19304 |          1.5 |
| switch_2.00 |            2    |     0.343331 | -0.204069 |       1.42427 |              252 |                   125 |      1.19262 |          1.5 |
| switch_2.50 |            2.5  |     0.348505 | -0.204069 |       1.43963 |              248 |                   155 |      1.19305 |          1.5 |
| switch_3.00 |            3    |     0.342079 | -0.204069 |       1.42079 |              246 |                   157 |      1.19209 |          1.5 |

## Window Results
See `window_metrics.csv` for full/10Y/5Y/3Y/1Y metrics.

## Stability Classification
Pending review. Full-sample top rows are below; recent-window metrics should be checked before choosing a default.

| candidate   |   ann_return |    max_dd |   sharpe_repo |   asset_switches |   buffer_blocked_days |   avg_weight |
|:------------|-------------:|----------:|--------------:|-----------------:|----------------------:|-------------:|
| switch_2.40 |     0.348505 | -0.204069 |       1.43963 |              248 |                   155 |      1.19305 |
| switch_2.50 |     0.348505 | -0.204069 |       1.43963 |              248 |                   155 |      1.19305 |
| switch_2.60 |     0.348328 | -0.204069 |       1.43904 |              248 |                   157 |      1.19305 |
| switch_2.10 |     0.345983 | -0.204069 |       1.4317  |              250 |                   141 |      1.19221 |
| switch_1.90 |     0.344937 | -0.204069 |       1.42989 |              252 |                   117 |      1.1926  |
| switch_2.70 |     0.343969 | -0.204069 |       1.42541 |              248 |                   162 |      1.19244 |
| switch_1.47 |     0.344208 | -0.204069 |       1.42437 |              258 |                    66 |      1.19184 |
| switch_2.00 |     0.343331 | -0.204069 |       1.42427 |              252 |                   125 |      1.19262 |
| switch_1.44 |     0.343757 | -0.204069 |       1.4231  |              258 |                    63 |      1.19177 |
| switch_2.80 |     0.343124 | -0.204069 |       1.4225  |              248 |                   163 |      1.19244 |
| switch_1.80 |     0.342685 | -0.204069 |       1.42209 |              252 |                   111 |      1.19304 |
| switch_3.00 |     0.342079 | -0.204069 |       1.42079 |              246 |                   157 |      1.19209 |
| switch_1.60 |     0.342905 | -0.204069 |       1.41895 |              258 |                    84 |      1.19246 |
| switch_1.45 |     0.342297 | -0.204069 |       1.41841 |              258 |                    64 |      1.19184 |
| switch_1.46 |     0.342297 | -0.204069 |       1.41841 |              258 |                    64 |      1.19184 |

## Decision
Exploratory no-change.

## User-Facing Summary
The first pass topped out at 1.50, so the scan was extended to 3.00. Very high buffers improve full-sample metrics in this no-cost harness, but they may create stale holdings and should be checked by recent windows before selection.
