# Sub-D Dynamic ChiNext Proxy R2-Removed Branch Layer 5 Target-Vol Scan

## Run Metadata

- Run folder: `quant_param_scan_runs\20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_r2_removed_branch_layer5_target_vol_after_r2_removed`
- Layer: `Layer 5` after R2 removal, switch-buffer selection, and staged-entry selection.
- Strategy: dynamic ChiNext proxy pool, 2007-2016.
- Entrypoint: `run_subd_proxy_dynamic_cyb_r2none_layer5_target_vol_scan.py`

## Research Question

Test target-vol scaling on the two user-confirmed carried lines: main line `entry_0p25` and return watch line `entry_0p75`.

## Implementation Anchor

- Data loader reused from `run_subd_proxy_dynamic_cyb_layer0.py`.
- Base curves reuse `run_subd_proxy_dynamic_cyb_r2none_layer4_staged_entry_scan.py`.
- Target-vol behavior reuses `apply_target_vol_overlay` from `run_subd_six_etf_v1_1.py`.
- No momentum decay, NAV defense, or overheat in this layer.

## Data Snapshot

- Start/end: `2007-01-04` to `2016-12-30`.
- Rows: `2432`.
- Pool: QQQ/EWG/EWJ/GLD from 2007 start; ChiNext joins when its own data exists.

## Cost and Execution Assumptions

- One-way cost: `0.001`.
- Target-vol window: `80` trading days.
- Max leverage: `1.5`.
- Rebalance threshold: `0.075` scale points.
- Calendar: A-share trading days; US adjusted closes are forward-filled onto that calendar for this proxy diagnostic.
- Trades involving a forward-filled trade leg are blocked for that day.

## Runtime Override Plan

- Lines: `[(28, 1.15, 0.25, 'main_line_r2_removed'), (28, 1.15, 0.75, 'return_watch_line_r2_removed')]`.
- Target-vol grid: `['no_tv', 'tv15', 'tv18', 'tv20', 'tv22', 'tv25', 'tv28', 'tv30', 'tv35']`.
- Baseline: same `lookback + switch buffer + entry fraction` with no target-vol overlay.
- Pass rule: Full maxDD improves by more than `0.01pp`; at least 3 of 4 available windows improve maxDD; Full/5Y annualized return lag <=1pp and 3Y/1Y lag <=3pp.

## Commands

- `python run_subd_proxy_dynamic_cyb_r2none_layer5_target_vol_scan.py --start-date 2007-01-01 --end-date 2016-12-30 --run-folder quant_param_scan_runs\20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_r2_removed_branch_layer5_target_vol_after_r2_removed`

## Output Files

- `scan_summary.csv`
- `window_metrics.csv`
- `line_selection.csv`
- `comparison_list.csv`
- `daily_outputs/r2none_target_vol_daily_curves.csv`
- `sources.csv`

## Line-Level Selection

| Line Role | Candidate | Selection | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | MDD Improve pp | Avg Scale Full | Pass Reason |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| main_line_r2_removed | `lb_28_r2_none_buf_1p15_entry_0p25_no_tv` | baseline_no_target_vol_pass | 10.63% | -29.48% | N/A | N/A | 5.49% | -26.22% | 5.72% | -26.22% | -11.11% | -21.36% | 0.00 | 1.00 | baseline/no target-vol |
| return_watch_line_r2_removed | `lb_28_r2_none_buf_1p15_entry_0p75_no_tv` | baseline_no_target_vol_pass | 11.27% | -30.37% | N/A | N/A | 4.63% | -30.11% | 2.04% | -30.11% | -18.18% | -26.92% | 0.00 | 1.00 | baseline/no target-vol |

## Full-Sample Target-Vol Grid

| Candidate | Line Role | Full Ann. | Full MDD | Full Ann Delta pp | Full MDD Improve pp | 5Y Ann. | 3Y Ann. | 1Y Ann. | Avg Scale Full | Avg Exposure Full | Pass | Reason |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| `lb_28_r2_none_buf_1p15_entry_0p25_no_tv` | main_line_r2_removed | 10.63% | -29.48% | 0.00 | 0.00 | 5.49% | 5.72% | -11.11% | 1.00 | 0.78 | False | baseline/no target-vol |
| `lb_28_r2_none_buf_1p15_entry_0p25_tv15` | main_line_r2_removed | 8.17% | -26.64% | -2.46 | 2.84 | 3.63% | 2.18% | -13.85% | 0.81 | 0.63 | False | full_mdd=True;dd_windows=2;return_tol=False |
| `lb_28_r2_none_buf_1p15_entry_0p25_tv18` | main_line_r2_removed | 9.38% | -30.05% | -1.25 | -0.58 | 3.96% | 2.26% | -15.86% | 0.96 | 0.75 | False | full_mdd=False;dd_windows=0;return_tol=False |
| `lb_28_r2_none_buf_1p15_entry_0p25_tv20` | main_line_r2_removed | 10.38% | -31.13% | -0.25 | -1.65 | 4.56% | 3.25% | -15.77% | 1.06 | 0.83 | False | full_mdd=False;dd_windows=0;return_tol=False |
| `lb_28_r2_none_buf_1p15_entry_0p25_tv22` | main_line_r2_removed | 11.11% | -32.40% | 0.48 | -2.92 | 4.98% | 4.15% | -16.02% | 1.14 | 0.90 | False | full_mdd=False;dd_windows=0;return_tol=False |
| `lb_28_r2_none_buf_1p15_entry_0p25_tv25` | main_line_r2_removed | 11.90% | -33.62% | 1.27 | -4.14 | 5.46% | 6.05% | -16.19% | 1.25 | 0.98 | False | full_mdd=False;dd_windows=0;return_tol=False |
| `lb_28_r2_none_buf_1p15_entry_0p25_tv28` | main_line_r2_removed | 12.43% | -35.68% | 1.80 | -6.20 | 5.92% | 6.23% | -16.80% | 1.33 | 1.04 | False | full_mdd=False;dd_windows=0;return_tol=False |
| `lb_28_r2_none_buf_1p15_entry_0p25_tv30` | main_line_r2_removed | 13.15% | -37.60% | 2.52 | -8.12 | 6.25% | 6.54% | -16.07% | 1.37 | 1.07 | False | full_mdd=False;dd_windows=0;return_tol=False |
| `lb_28_r2_none_buf_1p15_entry_0p25_tv35` | main_line_r2_removed | 13.76% | -40.20% | 3.13 | -10.72 | 6.70% | 6.60% | -18.16% | 1.44 | 1.13 | False | full_mdd=False;dd_windows=0;return_tol=False |
| `lb_28_r2_none_buf_1p15_entry_0p75_no_tv` | return_watch_line_r2_removed | 11.27% | -30.37% | 0.00 | 0.00 | 4.63% | 2.04% | -18.18% | 1.00 | 0.87 | False | baseline/no target-vol |
| `lb_28_r2_none_buf_1p15_entry_0p75_tv15` | return_watch_line_r2_removed | 8.48% | -27.23% | -2.79 | 3.14 | 3.27% | 0.39% | -18.50% | 0.77 | 0.67 | False | full_mdd=True;dd_windows=4;return_tol=False |
| `lb_28_r2_none_buf_1p15_entry_0p75_tv18` | return_watch_line_r2_removed | 9.90% | -32.18% | -1.37 | -1.82 | 3.57% | -0.07% | -22.03% | 0.92 | 0.80 | False | full_mdd=False;dd_windows=0;return_tol=False |
| `lb_28_r2_none_buf_1p15_entry_0p75_tv20` | return_watch_line_r2_removed | 10.54% | -33.76% | -0.72 | -3.40 | 3.66% | -0.13% | -23.19% | 1.01 | 0.88 | False | full_mdd=False;dd_windows=0;return_tol=False |
| `lb_28_r2_none_buf_1p15_entry_0p75_tv22` | return_watch_line_r2_removed | 11.69% | -34.65% | 0.43 | -4.29 | 4.36% | 0.61% | -23.23% | 1.09 | 0.95 | False | full_mdd=False;dd_windows=0;return_tol=False |
| `lb_28_r2_none_buf_1p15_entry_0p75_tv25` | return_watch_line_r2_removed | 12.47% | -37.32% | 1.21 | -6.96 | 4.55% | 1.26% | -25.09% | 1.21 | 1.05 | False | full_mdd=False;dd_windows=0;return_tol=False |
| `lb_28_r2_none_buf_1p15_entry_0p75_tv28` | return_watch_line_r2_removed | 13.05% | -38.46% | 1.78 | -8.10 | 4.86% | 1.99% | -24.89% | 1.29 | 1.13 | False | full_mdd=False;dd_windows=0;return_tol=False |
| `lb_28_r2_none_buf_1p15_entry_0p75_tv30` | return_watch_line_r2_removed | 13.72% | -39.92% | 2.45 | -9.55 | 5.36% | 2.11% | -25.75% | 1.33 | 1.16 | False | full_mdd=False;dd_windows=0;return_tol=False |
| `lb_28_r2_none_buf_1p15_entry_0p75_tv35` | return_watch_line_r2_removed | 14.21% | -42.94% | 2.95 | -12.57 | 5.37% | 1.52% | -26.98% | 1.42 | 1.23 | False | full_mdd=False;dd_windows=0;return_tol=False |

## Comparison List

| Candidate | Type | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `lb_28_r2_none_buf_1p15_entry_0p25_no_tv` | line_baseline_no_target_vol | 10.63% | -29.48% | N/A | N/A | 5.49% | -26.22% | 5.72% | -26.22% | -11.11% | -21.36% | Same carried line before target-vol layer |
| `lb_28_r2_none_buf_1p15_entry_0p75_no_tv` | line_baseline_no_target_vol | 11.27% | -30.37% | N/A | N/A | 4.63% | -30.11% | 2.04% | -30.11% | -18.18% | -26.92% | Same carried line before target-vol layer |
| `lb_28_r2_none_buf_1p15_entry_0p25_no_tv` | baseline_no_target_vol_pass | 10.63% | -29.48% | N/A | N/A | 5.49% | -26.22% | 5.72% | -26.22% | -11.11% | -21.36% | Line-level selected target-vol result |
| `lb_28_r2_none_buf_1p15_entry_0p75_no_tv` | baseline_no_target_vol_pass | 11.27% | -30.37% | N/A | N/A | 4.63% | -30.11% | 2.04% | -30.11% | -18.18% | -26.92% | Line-level selected target-vol result |
| `orig_full_v1_1_reference` | original_full_v1_1_reference | 11.84% | -36.96% | N/A | N/A | 12.61% | -36.96% | 3.41% | -36.96% | -26.98% | -36.96% | Full official V1.1 chain on this proxy panel; includes original lookback 25, R2 0.20, switch buffer 1.05, staged entry 0.50, target-vol 25%, and later overlays. |

## Stability Classification

- Decision: `line_level_selection_after_target_vol_on_r2_removed_branch`.
- Stability label: `target_vol_pass_if_line_selection_uses_overlay_else_keep_previous`.
- 10Y remains N/A by sample length and is not fabricated for strict scanner compatibility.

## Decision

- Keep each line's selected row from `line_selection.csv`.
- Stop here before momentum decay, NAV defense, or overheat layers.

## User-Facing Summary

Layer 5 completed on the R2-removed branch. See line-level selection above for carried candidates.

## Source Audit

| code          | name                            | source                                  | adjustment                | first_available   | first_used   | last       |   rows | pool_rule                                                  | last_aligned   |   ffill_days_on_cn_calendar |
|:--------------|:--------------------------------|:----------------------------------------|:--------------------------|:------------------|:-------------|:-----------|-------:|:-----------------------------------------------------------|:---------------|----------------------------:|
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY      | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWG           | GERMANY_EWG_ADJ_CLOSE_PROXY     | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWJ           | JAPAN_EWJ_ADJ_CLOSE_PROXY       | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY        | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_ADD | Eastmoney push2his kline secid=0.399006 | index close / price index | 2010-06-01        | 2010-06-01   | 2016-12-30 |   1601 | dynamic asset; no prices before 2010-06-01 and no backfill | 2016-12-30     |                           0 |

## Finalization

- Finalized at: 2026-07-01T23:49:53+08:00
- Decision: do_not_add_target_vol_keep_layer4_two_lines
- Stability label: no_target_vol_pass_keep_previous_two_lines
- Complete checker: PASS
