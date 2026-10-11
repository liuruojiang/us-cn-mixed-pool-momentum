# Sub-D Dynamic ChiNext Proxy R2-Removed Branch Layer 3 Switch Buffer Scan

## Run Metadata

- Run folder: `quant_param_scan_runs\20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_r2_removed_branch_layer3_switch_buffer_after_r2_removed`
- Layer: `Layer 3` after resetting Layer 2 to `R2 removed`.
- Strategy: dynamic ChiNext proxy pool, 2007-2016.
- Entrypoint: `run_subd_proxy_dynamic_cyb_r2none_layer3_switch_buffer_scan.py`

## Research Question

After removing the R2 signal-quality filter, test whether adding a switch buffer improves drawdown without giving back too much return.

## Implementation Anchor

- Data loader reused from `run_subd_proxy_dynamic_cyb_layer0.py`.
- Score precompute reused from `run_subd_proxy_dynamic_cyb_layer2_r2_scan.py`.
- Target switch rule reused from `run_subd_proxy_dynamic_cyb_layer3_switch_buffer_scan.py`.
- R2 is not used to filter scores in this branch.
- No staged entry, target-vol, momentum decay, NAV defense, or overheat in this layer.

## Data Snapshot

- Start/end: `2007-01-04` to `2016-12-30`.
- Rows: `2432`.
- Pool: QQQ/EWG/EWJ/GLD from 2007 start; ChiNext joins when its own data exists.

## Cost and Execution Assumptions

- One-way cost: `0.001`.
- Calendar: A-share trading days; US adjusted closes are forward-filled onto that calendar for this proxy diagnostic.
- Trades involving a forward-filled trade leg are blocked for that day.

## Runtime Override Plan

- Lines: `[(28, 'layer1_primary_r2_removed'), (26, 'layer1_left_neighbor_r2_removed'), (30, 'layer1_right_neighbor_r2_removed'), (32, 'layer1_return_peak_watch_r2_removed'), (25, 'original_lookback_r2_removed')]`.
- Switch-buffer grid: `['1p00', '1p02', '1p03', '1p05', '1p08', '1p10', '1p15', '1p20']`.
- Baseline: same lookback with `r2_none` and switch buffer `1.00`.
- Pass rule: Full maxDD improves by more than `0.01pp`; at least 3 of 4 available windows improve maxDD; Full/5Y annualized return lag <=1pp and 3Y/1Y lag <=3pp.

## Commands

- `python run_subd_proxy_dynamic_cyb_r2none_layer3_switch_buffer_scan.py --start-date 2007-01-01 --end-date 2016-12-30 --run-folder quant_param_scan_runs\20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_r2_removed_branch_layer3_switch_buffer_after_r2_removed`

## Output Files

- `scan_summary.csv`
- `window_metrics.csv`
- `comparison_list.csv`
- `daily_outputs/r2none_switch_buffer_daily_curves.csv`
- `sources.csv`

## Full-Sample Results

| Candidate | Full Ann. | Full MDD | Full Ann Delta pp | Full MDD Improve pp | 5Y Ann. | 3Y Ann. | 1Y Ann. | Trades Full | Blocked Days Full | Pass | Reason |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| `lb_28_r2_none_buf_1p00` | 9.86% | -36.31% | 0.00 | 0.00 | 1.50% | -4.01% | -26.19% | 262 | 0 | False | baseline/no switch buffer |
| `lb_28_r2_none_buf_1p02` | 10.20% | -36.31% | 0.34 | 0.00 | 1.84% | -3.83% | -26.19% | 255 | 11 | False | full_mdd=False;dd_windows=0;return_tol=True |
| `lb_28_r2_none_buf_1p03` | 11.18% | -34.56% | 1.33 | 1.75 | 3.38% | -1.17% | -24.17% | 251 | 25 | True | pass |
| `lb_28_r2_none_buf_1p05` | 11.02% | -34.73% | 1.17 | 1.58 | 2.50% | -1.04% | -24.17% | 247 | 39 | True | pass |
| `lb_28_r2_none_buf_1p08` | 12.08% | -34.73% | 2.22 | 1.58 | 3.78% | -0.29% | -24.17% | 240 | 55 | True | pass |
| `lb_28_r2_none_buf_1p10` | 11.31% | -34.39% | 1.46 | 1.92 | 3.36% | -0.68% | -23.97% | 239 | 72 | True | pass |
| `lb_28_r2_none_buf_1p15` | 11.49% | -32.22% | 1.63 | 4.08 | 4.10% | 0.14% | -21.56% | 234 | 95 | True | pass |
| `lb_28_r2_none_buf_1p20` | 11.47% | -34.67% | 1.61 | 1.64 | 4.51% | 0.58% | -24.40% | 234 | 124 | True | pass |

## Passing Or Best Candidates

| Candidate | Role | Full Ann. | Full MDD | Full MDD Improve pp | DD Improve Windows | Pass |
|---|---|---:|---:|---:|---:|---|
| `lb_28_r2_none_buf_1p08` | layer1_primary_r2_removed | 12.08% | -34.73% | 1.58 | 4 | True |
| `lb_32_r2_none_buf_1p03` | layer1_return_peak_watch_r2_removed | 11.86% | -41.00% | 1.04 | 3 | True |
| `lb_32_r2_none_buf_1p02` | layer1_return_peak_watch_r2_removed | 11.66% | -41.00% | 1.04 | 3 | True |
| `lb_32_r2_none_buf_1p05` | layer1_return_peak_watch_r2_removed | 11.55% | -41.81% | 0.22 | 3 | True |
| `lb_28_r2_none_buf_1p15` | layer1_primary_r2_removed | 11.49% | -32.22% | 4.08 | 4 | True |
| `lb_28_r2_none_buf_1p20` | layer1_primary_r2_removed | 11.47% | -34.67% | 1.64 | 4 | True |
| `lb_28_r2_none_buf_1p10` | layer1_primary_r2_removed | 11.31% | -34.39% | 1.92 | 4 | True |
| `lb_32_r2_none_buf_1p10` | layer1_return_peak_watch_r2_removed | 11.30% | -40.49% | 1.55 | 4 | True |
| `lb_28_r2_none_buf_1p03` | layer1_primary_r2_removed | 11.18% | -34.56% | 1.75 | 4 | True |
| `lb_28_r2_none_buf_1p05` | layer1_primary_r2_removed | 11.02% | -34.73% | 1.58 | 4 | True |
| `lb_26_r2_none_buf_1p20` | layer1_left_neighbor_r2_removed | 10.63% | -39.00% | 1.27 | 4 | True |
| `lb_30_r2_none_buf_1p02` | layer1_right_neighbor_r2_removed | 10.09% | -36.21% | 2.29 | 4 | True |
| `lb_30_r2_none_buf_1p03` | layer1_right_neighbor_r2_removed | 9.98% | -36.21% | 2.29 | 4 | True |
| `lb_26_r2_none_buf_1p08` | layer1_left_neighbor_r2_removed | 9.90% | -39.09% | 1.19 | 4 | True |
| `lb_26_r2_none_buf_1p05` | layer1_left_neighbor_r2_removed | 9.83% | -39.76% | 0.52 | 4 | True |
| `lb_30_r2_none_buf_1p05` | layer1_right_neighbor_r2_removed | 9.46% | -37.33% | 1.17 | 4 | True |
| `lb_26_r2_none_buf_1p15` | layer1_left_neighbor_r2_removed | 9.23% | -39.56% | 0.72 | 3 | True |
| `lb_26_r2_none_buf_1p10` | layer1_left_neighbor_r2_removed | 9.22% | -40.00% | 0.27 | 4 | True |

## Comparison List

| Candidate | Type | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `lb_28_r2_none_buf_1p00` | r2_removed_layer2_baseline | 9.86% | -36.31% | N/A | N/A | 1.50% | -36.31% | -4.01% | -36.31% | -26.19% | -33.22% | R2 removed baseline carried from Layer2 reset |
| `lb_28_r2_none_buf_1p05` | r2_removed_original_buffer | 11.02% | -34.73% | N/A | N/A | 2.50% | -34.73% | -1.04% | -34.73% | -24.17% | -31.84% | R2 removed primary with original switch buffer 1.05 |
| `lb_28_r2_none_buf_1p08` | return_watch_buffer | 12.08% | -34.73% | N/A | N/A | 3.78% | -34.73% | -0.29% | -34.73% | -24.17% | -31.84% | R2 removed primary with strongest full-sample annualized return among passing buffers |
| `lb_28_r2_none_buf_1p15` | drawdown_watch_buffer | 11.49% | -32.22% | N/A | N/A | 4.10% | -32.22% | 0.14% | -32.22% | -21.56% | -29.59% | R2 removed primary with strongest full-sample drawdown improvement among passing buffers |
| `lb_26_r2_none_buf_1p00` | left_neighbor_baseline | 8.38% | -40.28% | N/A | N/A | 1.78% | -40.28% | -6.95% | -40.28% | -30.57% | -35.55% | Layer1 left neighbor with R2 removed |
| `lb_30_r2_none_buf_1p00` | right_neighbor_baseline | 8.81% | -38.50% | N/A | N/A | 5.01% | -38.50% | -3.05% | -38.50% | -22.97% | -30.40% | Layer1 right neighbor with R2 removed |
| `lb_32_r2_none_buf_1p00` | return_peak_watch_baseline | 11.22% | -42.04% | N/A | N/A | 3.51% | -42.04% | -5.00% | -42.04% | -16.11% | -24.49% | Layer1 return peak watch with R2 removed |
| `lb_25_r2_none_buf_1p05` | original_lookback_r2_removed_buffer | 7.12% | -48.57% | N/A | N/A | -1.67% | -48.57% | -11.41% | -48.57% | -30.48% | -35.96% | Original lookback with R2 removed and buffer 1.05 |
| `orig_full_v1_1_reference` | original_full_strategy_reference | 11.84% | -36.96% | N/A | N/A | 12.61% | -36.96% | 3.41% | -36.96% | -26.98% | -36.96% | Full official V1.1 chain; context only, not Layer3 pass baseline |

## Window Results

- Selected candidate: `lb_28_r2_none_buf_1p15`.
- Selected Full: `11.49%` / MDD `-32.22%`.
- Selected 10Y: `N/A` because sample rows are below 2520.
- Selected 5Y: `4.10%` / MDD `-32.22%`.
- Selected 3Y: `0.14%` / MDD `-32.22%`.
- Selected 1Y: `-21.56%` / MDD `-29.59%`.

## Stability Classification

- Decision: `carry_forward_r2_removed_switch_buffer_pass`.
- Stability label: `primary_drawdown_pass`.
- 10Y remains N/A by sample length and is not fabricated for strict scanner compatibility.

## Decision

- Decision: `carry_forward_r2_removed_switch_buffer_pass`.
- Stop here before staged-entry, target-vol, momentum decay, NAV defense, or overheat layers.

## User-Facing Summary

R2 is removed. Layer 3 selected `lb_28_r2_none_buf_1p15` under the documented pass rule.

## Source Audit

| code          | name                            | source                                  | adjustment                | first_available   | first_used   | last       |   rows | pool_rule                                                  | last_aligned   |   ffill_days_on_cn_calendar |
|:--------------|:--------------------------------|:----------------------------------------|:--------------------------|:------------------|:-------------|:-----------|-------:|:-----------------------------------------------------------|:---------------|----------------------------:|
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY      | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWG           | GERMANY_EWG_ADJ_CLOSE_PROXY     | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWJ           | JAPAN_EWJ_ADJ_CLOSE_PROXY       | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY        | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_ADD | Eastmoney push2his kline secid=0.399006 | index close / price index | 2010-06-01        | 2010-06-01   | 2016-12-30 |   1601 | dynamic asset; no prices before 2010-06-01 and no backfill | 2016-12-30     |                           0 |

## Finalization

- Finalized at: 2026-07-01T23:17:55+08:00
- Decision: carry_forward_r2_removed_lb28_buf1p15_keep_buf1p08_watch
- Stability label: primary_drawdown_pass_return_watch
- Complete checker: PASS
