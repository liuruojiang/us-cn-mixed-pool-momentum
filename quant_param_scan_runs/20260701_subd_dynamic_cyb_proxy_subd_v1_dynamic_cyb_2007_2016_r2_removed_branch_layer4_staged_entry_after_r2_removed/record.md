# Sub-D Dynamic ChiNext Proxy R2-Removed Branch Layer 4 Staged-Entry Scan

## Run Metadata

- Run folder: `quant_param_scan_runs\20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_r2_removed_branch_layer4_staged_entry_after_r2_removed`
- Layer: `Layer 4` after resetting Layer 2 to `R2 removed` and Layer 3 to selected switch-buffer lines.
- Strategy: dynamic ChiNext proxy pool, 2007-2016.
- Entrypoint: `run_subd_proxy_dynamic_cyb_r2none_layer4_staged_entry_scan.py`

## Research Question

After removing R2 and selecting switch-buffer lines, test whether staged entry improves drawdown without excessive return drag.

## Implementation Anchor

- Data loader reused from `run_subd_proxy_dynamic_cyb_layer0.py`.
- Staged-entry behavior reuses `EntryCase` and `run_staged_entry` from `run_subd_six_etf_v1_1.py`.
- `R2` is labeled removed; execution threshold is `0.0`, equivalent to no positive R2 filter for this weighted-slope score path.
- No target-vol, momentum decay, NAV defense, or overheat in this layer.

## Data Snapshot

- Start/end: `2007-01-04` to `2016-12-30`.
- Rows: `2432`.
- Pool: QQQ/EWG/EWJ/GLD from 2007 start; ChiNext joins when its own data exists.

## Cost and Execution Assumptions

- One-way cost: `0.001`.
- Calendar: A-share trading days; US adjusted closes are forward-filled onto that calendar for this proxy diagnostic.
- Trades involving a forward-filled trade leg are blocked for that day.

## Runtime Override Plan

- Lines: `[(28, 1.15, 'primary_drawdown_r2_removed'), (28, 1.08, 'return_watch_r2_removed'), (30, 1.03, 'width_confirm_r2_removed')]`.
- Entry-fraction grid: `['full', '0p75', '0p67', '0p50', '0p33', '0p25']`.
- Baseline: same line with `entry_full`.
- Pass rule: Full maxDD improves by more than `0.01pp`; at least 3 of 4 available windows improve maxDD; Full/5Y annualized return lag <=1pp and 3Y/1Y lag <=3pp.

## Commands

- `python run_subd_proxy_dynamic_cyb_r2none_layer4_staged_entry_scan.py --start-date 2007-01-01 --end-date 2016-12-30 --run-folder quant_param_scan_runs\20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_r2_removed_branch_layer4_staged_entry_after_r2_removed`

## Output Files

- `scan_summary.csv`
- `window_metrics.csv`
- `line_selection.csv`
- `comparison_list.csv`
- `daily_outputs/r2none_staged_entry_daily_curves.csv`
- `sources.csv`

## Line-Level Selection

| Line Role | Candidate | Selection | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | MDD Improve pp | Pass Reason |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| primary_drawdown_r2_removed | `lb_28_r2_none_buf_1p15_entry_0p75` | return_watch_pass | 11.27% | -30.37% | N/A | N/A | 4.63% | -30.11% | 2.04% | -30.11% | -18.18% | -26.92% | 1.86 | pass |
| primary_drawdown_r2_removed | `lb_28_r2_none_buf_1p15_entry_0p25` | selected_drawdown_pass | 10.63% | -29.48% | N/A | N/A | 5.49% | -26.22% | 5.72% | -26.22% | -11.11% | -21.36% | 2.75 | pass |
| return_watch_r2_removed | `lb_28_r2_none_buf_1p08_entry_0p75` | return_watch_pass | 11.66% | -33.39% | N/A | N/A | 4.56% | -33.39% | 1.92% | -33.39% | -21.69% | -29.42% | 1.33 | pass |
| return_watch_r2_removed | `lb_28_r2_none_buf_1p08_entry_0p50` | selected_drawdown_pass | 11.19% | -32.22% | N/A | N/A | 5.28% | -32.22% | 4.10% | -32.22% | -19.16% | -26.93% | 2.51 | pass |
| width_confirm_r2_removed | `lb_30_r2_none_buf_1p03_entry_full` | baseline_no_staged_entry_pass | 9.98% | -36.21% | N/A | N/A | 6.74% | -35.33% | 0.31% | -35.33% | -19.00% | -26.82% | 0.00 | baseline/full entry |

## Full-Sample Results

| Candidate | Line Role | Full Ann. | Full MDD | Full Ann Delta pp | Full MDD Improve pp | 5Y Ann. | 3Y Ann. | 1Y Ann. | Partial Days Full | Staged Fills Full | Pass | Reason |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| `lb_28_r2_none_buf_1p15_entry_full` | primary_drawdown_r2_removed | 11.49% | -32.22% | 0.00 | 0.00 | 4.10% | 0.14% | -21.56% | 0 | 0 | False | baseline/full entry |
| `lb_28_r2_none_buf_1p15_entry_0p75` | primary_drawdown_r2_removed | 11.27% | -30.37% | -0.22 | 1.86 | 4.63% | 2.04% | -18.18% | 417 | 178 | True | pass |
| `lb_28_r2_none_buf_1p15_entry_0p67` | primary_drawdown_r2_removed | 11.18% | -30.18% | -0.31 | 2.04 | 4.78% | 2.65% | -17.08% | 417 | 178 | True | pass |
| `lb_28_r2_none_buf_1p15_entry_0p50` | primary_drawdown_r2_removed | 10.98% | -29.89% | -0.51 | 2.34 | 5.09% | 3.91% | -14.70% | 417 | 178 | True | pass |
| `lb_28_r2_none_buf_1p15_entry_0p33` | primary_drawdown_r2_removed | 10.75% | -29.61% | -0.74 | 2.62 | 5.37% | 5.15% | -12.27% | 417 | 178 | True | pass |
| `lb_28_r2_none_buf_1p15_entry_0p25` | primary_drawdown_r2_removed | 10.63% | -29.48% | -0.86 | 2.75 | 5.49% | 5.72% | -11.11% | 417 | 178 | True | pass |
| `lb_28_r2_none_buf_1p08_entry_full` | return_watch_r2_removed | 12.08% | -34.73% | 0.00 | 0.00 | 3.78% | -0.29% | -24.17% | 0 | 0 | False | baseline/full entry |
| `lb_28_r2_none_buf_1p08_entry_0p75` | return_watch_r2_removed | 11.66% | -33.39% | -0.41 | 1.33 | 4.56% | 1.92% | -21.69% | 420 | 183 | True | pass |
| `lb_28_r2_none_buf_1p08_entry_0p67` | return_watch_r2_removed | 11.52% | -33.01% | -0.56 | 1.72 | 4.80% | 2.62% | -20.89% | 420 | 183 | True | pass |
| `lb_28_r2_none_buf_1p08_entry_0p50` | return_watch_r2_removed | 11.19% | -32.22% | -0.89 | 2.51 | 5.28% | 4.10% | -19.16% | 420 | 183 | True | pass |
| `lb_28_r2_none_buf_1p08_entry_0p33` | return_watch_r2_removed | 10.83% | -31.44% | -1.25 | 3.28 | 5.73% | 5.57% | -17.40% | 420 | 183 | False | full_mdd=True;dd_windows=4;return_tol=False |
| `lb_28_r2_none_buf_1p08_entry_0p25` | return_watch_r2_removed | 10.66% | -31.09% | -1.42 | 3.64 | 5.93% | 6.26% | -16.56% | 420 | 183 | False | full_mdd=True;dd_windows=4;return_tol=False |
| `lb_30_r2_none_buf_1p03_entry_full` | width_confirm_r2_removed | 9.98% | -36.21% | 0.00 | 0.00 | 6.74% | 0.31% | -19.00% | 0 | 0 | False | baseline/full entry |
| `lb_30_r2_none_buf_1p03_entry_0p75` | width_confirm_r2_removed | 9.43% | -34.61% | -0.55 | 1.59 | 5.64% | 0.63% | -17.50% | 431 | 172 | False | full_mdd=True;dd_windows=4;return_tol=False |
| `lb_30_r2_none_buf_1p03_entry_0p67` | width_confirm_r2_removed | 9.24% | -34.10% | -0.74 | 2.11 | 5.27% | 0.72% | -17.02% | 431 | 172 | False | full_mdd=True;dd_windows=4;return_tol=False |
| `lb_30_r2_none_buf_1p03_entry_0p50` | width_confirm_r2_removed | 8.82% | -33.00% | -1.17 | 3.21 | 4.47% | 0.87% | -16.01% | 431 | 172 | False | full_mdd=True;dd_windows=4;return_tol=False |
| `lb_30_r2_none_buf_1p03_entry_0p33` | width_confirm_r2_removed | 8.36% | -32.14% | -1.62 | 4.07 | 3.65% | 0.99% | -15.01% | 431 | 172 | False | full_mdd=True;dd_windows=4;return_tol=False |
| `lb_30_r2_none_buf_1p03_entry_0p25` | width_confirm_r2_removed | 8.14% | -31.78% | -1.85 | 4.43 | 3.25% | 1.03% | -14.54% | 431 | 172 | False | full_mdd=True;dd_windows=4;return_tol=False |

## Comparison List

| Candidate | Type | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `lb_28_r2_none_buf_1p15_entry_full` | line_baseline_full_entry | 11.49% | -32.22% | N/A | N/A | 4.10% | -32.22% | 0.14% | -32.22% | -21.56% | -29.59% | Line baseline before staged-entry layer |
| `lb_28_r2_none_buf_1p08_entry_full` | line_baseline_full_entry | 12.08% | -34.73% | N/A | N/A | 3.78% | -34.73% | -0.29% | -34.73% | -24.17% | -31.84% | Line baseline before staged-entry layer |
| `lb_30_r2_none_buf_1p03_entry_full` | line_baseline_full_entry | 9.98% | -36.21% | N/A | N/A | 6.74% | -35.33% | 0.31% | -35.33% | -19.00% | -26.82% | Line baseline before staged-entry layer |
| `lb_28_r2_none_buf_1p15_entry_0p75` | return_watch_pass | 11.27% | -30.37% | N/A | N/A | 4.63% | -30.11% | 2.04% | -30.11% | -18.18% | -26.92% | Line-level selected/watch staged-entry candidate |
| `lb_28_r2_none_buf_1p15_entry_0p25` | selected_drawdown_pass | 10.63% | -29.48% | N/A | N/A | 5.49% | -26.22% | 5.72% | -26.22% | -11.11% | -21.36% | Line-level selected/watch staged-entry candidate |
| `lb_28_r2_none_buf_1p08_entry_0p75` | return_watch_pass | 11.66% | -33.39% | N/A | N/A | 4.56% | -33.39% | 1.92% | -33.39% | -21.69% | -29.42% | Line-level selected/watch staged-entry candidate |
| `lb_28_r2_none_buf_1p08_entry_0p50` | selected_drawdown_pass | 11.19% | -32.22% | N/A | N/A | 5.28% | -32.22% | 4.10% | -32.22% | -19.16% | -26.93% | Line-level selected/watch staged-entry candidate |
| `lb_30_r2_none_buf_1p03_entry_full` | baseline_no_staged_entry_pass | 9.98% | -36.21% | N/A | N/A | 6.74% | -35.33% | 0.31% | -35.33% | -19.00% | -26.82% | Line-level selected/watch staged-entry candidate |
| `orig_full_v1_1_reference` | original_full_strategy_reference | 11.84% | -36.96% | N/A | N/A | 12.61% | -36.96% | 3.41% | -36.96% | -26.98% | -36.96% | Full official V1.1 chain; context only, not Layer4 pass baseline |

## Stability Classification

- Decision: `line_level_selection_after_staged_entry`.
- Stability label: `mixed_pass_keep_line_baselines_when_staged_fails`.
- 10Y remains N/A by sample length and is not fabricated for strict scanner compatibility.

## Decision

- Keep each line's selected row from `line_selection.csv`.
- Stop here before target-vol, momentum decay, NAV defense, or overheat layers.

## User-Facing Summary

Layer 4 completed on the R2-removed branch. See line-level selection above for the carried candidates.

## Source Audit

| code          | name                            | source                                  | adjustment                | first_available   | first_used   | last       |   rows | pool_rule                                                  | last_aligned   |   ffill_days_on_cn_calendar |
|:--------------|:--------------------------------|:----------------------------------------|:--------------------------|:------------------|:-------------|:-----------|-------:|:-----------------------------------------------------------|:---------------|----------------------------:|
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY      | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWG           | GERMANY_EWG_ADJ_CLOSE_PROXY     | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWJ           | JAPAN_EWJ_ADJ_CLOSE_PROXY       | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY        | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_ADD | Eastmoney push2his kline secid=0.399006 | index close / price index | 2010-06-01        | 2010-06-01   | 2016-12-30 |   1601 | dynamic asset; no prices before 2010-06-01 and no backfill | 2016-12-30     |                           0 |

## Finalization

- Finalized at: 2026-07-01T23:29:59+08:00
- Decision: line_level_staged_entry_selection_after_r2_removed
- Stability label: primary_and_return_watch_pass_width_confirm_keeps_full_entry
- Complete checker: PASS
