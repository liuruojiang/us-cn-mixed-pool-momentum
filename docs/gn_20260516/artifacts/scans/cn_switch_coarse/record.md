# CN Gold/Nasdaq Switch Buffer Coarse Scan

## Run Metadata
- run_id: 20260516_subd_cn_gold_nasdaq_v11_defaults_nohalf_nooverheat_rawscore_cn_159941_518880_switch_buffer_coarse
- repo: C:\Users\Administrator.DESKTOP-95I7VVU\Desktop\动量策略\美股A股混合池子动量策略
- status: complete

## Scope
A-share 159941/518880 with V1.1 defaults, full entry, no overheat, no 0-to-5 score gate.

## Data Snapshot
- Source: akshare.fund_etf_hist_sina.
- 159941 pre-2022-07-05 multiplied by 0.25 for split continuity.

## Cost And Execution
- R2 threshold: 0.20.
- Target vol: 25%, vol window 80, max leverage 1.5.
- One-way cost: 0.001.
- Full entry; half-entry removed.
- Overheat removed.
- Raw scores allowed.

## Full Window Results
| candidate   |   SWITCH_BUFFER |   ann_return |    max_dd |   sharpe_repo |   asset_switches |   buffer_blocked_days |   cost_total |   avg_weight |
|:------------|----------------:|-------------:|----------:|--------------:|-----------------:|----------------------:|-------------:|-------------:|
| switch_1.00 |            1    |     0.272173 | -0.262697 |       1.13037 |              122 |                     0 |     0.496938 |      1.20435 |
| switch_1.05 |            1.05 |     0.265094 | -0.262697 |       1.1067  |              122 |                     5 |     0.496715 |      1.20317 |
| switch_1.10 |            1.1  |     0.260474 | -0.262697 |       1.09146 |              122 |                    15 |     0.4968   |      1.20374 |
| switch_1.20 |            1.2  |     0.261615 | -0.262697 |       1.09538 |              120 |                    22 |     0.493361 |      1.20385 |
| switch_1.30 |            1.3  |     0.257813 | -0.251999 |       1.08117 |              120 |                    34 |     0.493369 |      1.20306 |
| switch_1.50 |            1.5  |     0.243689 | -0.253062 |       1.03444 |              120 |                    49 |     0.493399 |      1.20289 |
| switch_2.00 |            2    |     0.247931 | -0.259065 |       1.05096 |              116 |                    81 |     0.481377 |      1.20338 |
| switch_2.50 |            2.5  |     0.25908  | -0.256239 |       1.0905  |              113 |                   119 |     0.473612 |      1.20501 |
| switch_3.00 |            3    |     0.266695 | -0.256239 |       1.11433 |              111 |                   145 |     0.466879 |      1.20319 |

## Top Rows
| candidate   |   SWITCH_BUFFER |   ann_return |    max_dd |   sharpe_repo |   asset_switches |   buffer_blocked_days |   cost_total |   avg_weight |
|:------------|----------------:|-------------:|----------:|--------------:|-----------------:|----------------------:|-------------:|-------------:|
| switch_1.00 |            1    |     0.272173 | -0.262697 |       1.13037 |              122 |                     0 |     0.496938 |      1.20435 |
| switch_3.00 |            3    |     0.266695 | -0.256239 |       1.11433 |              111 |                   145 |     0.466879 |      1.20319 |
| switch_1.05 |            1.05 |     0.265094 | -0.262697 |       1.1067  |              122 |                     5 |     0.496715 |      1.20317 |
| switch_1.20 |            1.2  |     0.261615 | -0.262697 |       1.09538 |              120 |                    22 |     0.493361 |      1.20385 |
| switch_1.10 |            1.1  |     0.260474 | -0.262697 |       1.09146 |              122 |                    15 |     0.4968   |      1.20374 |

## Stability
pending - coarse scan only.

## Artifacts
- scan_summary.csv
- window_metrics.csv
- daily_curves.csv
- selection.csv
- sources.csv

## Finalization

- Finalized at: 2026-05-16T02:04:18+08:00
- Decision: coarse_scan_prefers_1p00_or_1p00_to_1p05_not_high_buffer
- Stability label: coarse_stable_against_high_buffer
- Complete checker: FAIL
- Checker errors:
  - record.md missing required marker: decision

## Finalization

- Finalized at: 2026-05-16T02:04:36+08:00
- Decision: coarse_scan_prefers_1p00_or_1p00_to_1p05_not_high_buffer
- Stability label: coarse_stable_against_high_buffer
- Complete checker: PASS
