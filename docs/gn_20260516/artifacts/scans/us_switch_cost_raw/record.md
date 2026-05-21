# US QQQ/GLD Switch Buffer Scan - Cost Corrected Raw Score

## Run Metadata
- run_id: 20260516_subd_us_nasdaq_gold_raw_momentum_r2_0p30_tv25_vw20_cost001_raw_score_us_qqq_gld_switch_buffer
- repo: C:\Users\Administrator.DESKTOP-95I7VVU\Desktop\动量策略\美股A股混合池子动量策略
- status: complete

## Research Question
At fixed R2=0.30, target_vol=25%, vol_window=20, if only the V1.1 one-way cost 0.001 is restored while raw scores remain unfiltered, what switch buffer is favored?

## Data Snapshot
- Assets: QQQ, GLD.
- Source: Yahoo Finance chart API adjusted close.
- Price rows: 4117, 2010-01-04 to 2026-05-15.
- Evaluation starts: 2015-07-13.

## Cost and Execution Assumptions
- One-way transaction cost: 0.001.
- Slippage/open impact: 0.
- R2 threshold: 0.30.
- Target vol: 25%, 20-day realized vol, one-day shifted effective scale, max leverage 1.5.
- Switch buffer: scanned 1.00 to 1.50 step 0.01 plus 1.60 to 3.00 step 0.10.
- Disabled in this diagnostic pass: score positivity, score cap, staged entry, overheat.

## Selected Full-Window Rows
| candidate   |   SWITCH_BUFFER |   ann_return |    max_dd |   sharpe_repo |   asset_switches |   buffer_blocked_days |   cost_total |   avg_weight |   max_weight |
|:------------|----------------:|-------------:|----------:|--------------:|-----------------:|----------------------:|-------------:|-------------:|-------------:|
| switch_1.00 |            1    |     0.228126 | -0.246673 |       1.01992 |              122 |                     0 |     0.570634 |      1.19017 |          1.5 |
| switch_1.05 |            1.05 |     0.238017 | -0.246673 |       1.05608 |              116 |                    11 |     0.554748 |      1.18948 |          1.5 |
| switch_1.10 |            1.1  |     0.254757 | -0.246673 |       1.11708 |              110 |                    25 |     0.536578 |      1.19219 |          1.5 |
| switch_1.20 |            1.2  |     0.261199 | -0.246673 |       1.13954 |              108 |                    33 |     0.530573 |      1.19162 |          1.5 |
| switch_1.30 |            1.3  |     0.263986 | -0.246673 |       1.14917 |              108 |                    39 |     0.530672 |      1.19177 |          1.5 |
| switch_1.50 |            1.5  |     0.280089 | -0.221699 |       1.20593 |              104 |                    69 |     0.51941  |      1.19232 |          1.5 |
| switch_2.00 |            2    |     0.282589 | -0.221699 |       1.21718 |               98 |                   125 |     0.504728 |      1.19268 |          1.5 |
| switch_2.50 |            2.5  |     0.288944 | -0.221699 |       1.23754 |               94 |                   155 |     0.492951 |      1.19306 |          1.5 |
| switch_3.00 |            3    |     0.283314 | -0.221699 |       1.21999 |               92 |                   157 |     0.486876 |      1.19195 |          1.5 |

## Top Full-Window Rows
| candidate   |   SWITCH_BUFFER |   ann_return |    max_dd |   sharpe_repo |   asset_switches |   buffer_blocked_days |   cost_total |   avg_weight |
|:------------|----------------:|-------------:|----------:|--------------:|-----------------:|----------------------:|-------------:|-------------:|
| switch_2.40 |            2.4  |     0.288944 | -0.221699 |       1.23754 |               94 |                   155 |     0.492951 |      1.19306 |
| switch_2.50 |            2.5  |     0.288944 | -0.221699 |       1.23754 |               94 |                   155 |     0.492951 |      1.19306 |
| switch_2.60 |            2.6  |     0.288775 | -0.221699 |       1.23705 |               94 |                   157 |     0.492951 |      1.19306 |
| switch_2.10 |            2.1  |     0.285783 | -0.221699 |       1.22716 |               96 |                   141 |     0.498766 |      1.19217 |
| switch_2.70 |            2.7  |     0.284397 | -0.221699 |       1.22262 |               94 |                   162 |     0.492921 |      1.19231 |
| switch_1.90 |            1.9  |     0.284309 | -0.221699 |       1.22356 |               98 |                   117 |     0.504621 |      1.19254 |
| switch_2.80 |            2.8  |     0.283589 | -0.221699 |       1.21969 |               94 |                   163 |     0.492921 |      1.19231 |
| switch_3.00 |            3    |     0.283314 | -0.221699 |       1.21999 |               92 |                   157 |     0.486876 |      1.19195 |
| switch_2.00 |            2    |     0.282589 | -0.221699 |       1.21718 |               98 |                   125 |     0.504728 |      1.19268 |
| switch_1.80 |            1.8  |     0.282091 | -0.221699 |       1.21549 |               98 |                   111 |     0.504368 |      1.19291 |
| switch_1.47 |            1.47 |     0.281773 | -0.221699 |       1.21243 |              104 |                    66 |     0.519138 |      1.19181 |
| switch_1.44 |            1.44 |     0.281375 | -0.221699 |       1.21091 |              104 |                    63 |     0.518999 |      1.19175 |
| switch_1.60 |            1.6  |     0.280424 | -0.221699 |       1.20663 |              104 |                    84 |     0.520065 |      1.19231 |
| switch_1.50 |            1.5  |     0.280089 | -0.221699 |       1.20593 |              104 |                    69 |     0.51941  |      1.19232 |
| switch_1.46 |            1.46 |     0.27995  | -0.221699 |       1.20608 |              104 |                    64 |     0.519138 |      1.19181 |

## Decision
This is a cost-corrected diagnostic run, not a final V1.1-compatible selection. Best full-window ann_return in this raw-score pass is switch_2.40 at 0.288944, but score positivity/cap is still intentionally disabled.

## Artifacts
- scan_summary.csv
- window_metrics.csv
- selection.csv
- daily_curves.csv

## Finalization

- Finalized at: 2026-05-16T01:19:19+08:00
- Decision: diagnostic_cost_corrected_keep_raw_scores_no_selection
- Stability label: diagnostic
- Complete checker: FAIL
- Checker errors:
  - record.md missing required marker: stability
- Checker warnings:
  - scan_meta.json missing recommended field: data_snapshot

## Finalization

- Finalized at: 2026-05-16T01:19:51+08:00
- Decision: diagnostic_cost_corrected_keep_raw_scores_no_selection
- Stability label: diagnostic
- Complete checker: PASS
- Checker warnings:
  - scan_meta.json missing recommended field: data_snapshot
