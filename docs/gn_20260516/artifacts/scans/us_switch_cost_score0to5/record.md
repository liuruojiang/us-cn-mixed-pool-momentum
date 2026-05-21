# US QQQ/GLD Switch Buffer Scan - Costed Score 0 to 5

## Run Metadata
- run_id: 20260516_subd_us_nasdaq_gold_raw_momentum_r2_0p30_tv25_vw20_cost001_score0to5_us_qqq_gld_switch_buffer
- repo: C:\Users\Administrator.DESKTOP-95I7VVU\Desktop\动量策略\美股A股混合池子动量策略
- status: complete

## Research Question
At fixed R2=0.30, target_vol=25%, vol_window=20, one-way cost=0.001, and score eligibility 0<score<5, what switch buffer is favored for QQQ/GLD?

## Data Snapshot
- Assets: QQQ, GLD.
- Source: Yahoo Finance chart API adjusted close.
- Price rows: 4117, 2010-01-04 to 2026-05-15.
- Evaluation starts: 2015-07-13.

## Cost and Execution Assumptions
- One-way transaction cost: 0.001.
- Slippage/open impact: 0.
- R2 threshold: 0.30.
- Score eligibility: 0 < score < 5.
- Target vol: 25%, 20-day realized vol, one-day shifted effective scale, max leverage 1.5.
- Switch buffer: scanned 1.00 to 1.50 step 0.01 plus 1.60 to 3.00 step 0.10.
- Disabled in this pass: staged entry, overheat.

## Selected Full-Window Rows
| candidate   |   SWITCH_BUFFER |   ann_return |    max_dd |   sharpe_repo |   asset_switches |   buffer_blocked_days |   cost_total |   avg_weight |   max_weight |
|:------------|----------------:|-------------:|----------:|--------------:|-----------------:|----------------------:|-------------:|-------------:|-------------:|
| switch_1.00 |            1    |     0.168539 | -0.258464 |      0.919744 |               62 |                     0 |     0.382834 |     0.968234 |          1.5 |
| switch_1.05 |            1.05 |     0.177715 | -0.258464 |      0.961728 |               56 |                    11 |     0.367003 |     0.967794 |          1.5 |
| switch_1.10 |            1.1  |     0.194797 | -0.258464 |      1.04085  |               50 |                    25 |     0.34843  |     0.97014  |          1.5 |
| switch_1.20 |            1.2  |     0.200347 | -0.258464 |      1.06356  |               48 |                    33 |     0.342508 |     0.970053 |          1.5 |
| switch_1.30 |            1.3  |     0.202949 | -0.258464 |      1.07482  |               48 |                    39 |     0.342716 |     0.970231 |          1.5 |
| switch_1.50 |            1.5  |     0.216214 | -0.238086 |      1.13736  |               42 |                    69 |     0.32539  |     0.970988 |          1.5 |
| switch_2.00 |            2    |     0.222103 | -0.223771 |      1.1683   |               36 |                   124 |     0.307682 |     0.970656 |          1.5 |
| switch_2.50 |            2.5  |     0.229876 | -0.223771 |      1.19986  |               32 |                   153 |     0.295564 |     0.970968 |          1.5 |
| switch_3.00 |            3    |     0.225988 | -0.223771 |      1.18422  |               30 |                   154 |     0.289193 |     0.970044 |          1.5 |

## Top Full-Window Rows
| candidate   |   SWITCH_BUFFER |   ann_return |    max_dd |   sharpe_repo |   asset_switches |   buffer_blocked_days |   cost_total |   avg_weight |
|:------------|----------------:|-------------:|----------:|--------------:|-----------------:|----------------------:|-------------:|-------------:|
| switch_2.40 |            2.4  |     0.229876 | -0.223771 |       1.19986 |               32 |                   153 |     0.295564 |     0.970968 |
| switch_2.50 |            2.5  |     0.229876 | -0.223771 |       1.19986 |               32 |                   153 |     0.295564 |     0.970968 |
| switch_2.60 |            2.6  |     0.229715 | -0.223771 |       1.19929 |               32 |                   155 |     0.295564 |     0.970968 |
| switch_2.70 |            2.7  |     0.228629 | -0.223771 |       1.19435 |               32 |                   159 |     0.295268 |     0.97041  |
| switch_2.80 |            2.8  |     0.227856 | -0.223771 |       1.19078 |               32 |                   160 |     0.295268 |     0.97041  |
| switch_3.00 |            3    |     0.225988 | -0.223771 |       1.18422 |               30 |                   154 |     0.289193 |     0.970044 |
| switch_2.10 |            2.1  |     0.225521 | -0.223771 |       1.18154 |               34 |                   140 |     0.301653 |     0.970237 |
| switch_1.90 |            1.9  |     0.223707 | -0.223771 |       1.17567 |               36 |                   116 |     0.307621 |     0.970583 |
| switch_2.00 |            2    |     0.222103 | -0.223771 |       1.1683  |               36 |                   124 |     0.307682 |     0.970656 |
| switch_2.90 |            2.9  |     0.221399 | -0.223771 |       1.16221 |               32 |                   165 |     0.295268 |     0.97041  |
| switch_1.47 |            1.47 |     0.220701 | -0.238086 |       1.15549 |               44 |                    66 |     0.330828 |     0.969715 |
| switch_1.44 |            1.44 |     0.2205   | -0.238086 |       1.15431 |               44 |                    63 |     0.330761 |     0.969703 |
| switch_1.80 |            1.8  |     0.220174 | -0.223771 |       1.16014 |               36 |                   111 |     0.30779  |     0.971044 |
| switch_2.20 |            2.2  |     0.220023 | -0.223771 |       1.15616 |               34 |                   142 |     0.301653 |     0.970237 |
| switch_1.46 |            1.46 |     0.218965 | -0.238086 |       1.14785 |               44 |                    64 |     0.330828 |     0.969715 |

## Decision
Exploratory scan complete. Best full-window ann_return is switch_2.40 at 0.229876; selection should compare recent windows and 1.1 structural differences before changing any default.

## Stability
pending - needs direct recent-window comparison before selection.

## Artifacts
- scan_summary.csv
- window_metrics.csv
- selection.csv
- daily_curves.csv
