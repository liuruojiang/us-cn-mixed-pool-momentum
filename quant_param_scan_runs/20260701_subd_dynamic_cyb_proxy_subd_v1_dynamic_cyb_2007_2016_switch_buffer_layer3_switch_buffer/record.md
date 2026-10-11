# Sub-D Dynamic ChiNext Proxy Layer 3 Switch-Buffer Scan

## Run Metadata

- Run folder: `quant_param_scan_runs\20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_switch_buffer_layer3_switch_buffer`
- Layer: `Layer 3`
- Strategy: dynamic ChiNext proxy pool, 2007-2016.
- Entrypoint: `run_subd_proxy_dynamic_cyb_layer3_switch_buffer_scan.py`

## Research Question

Add a switch buffer after the Layer 2 R2 filter. A candidate only replaces the current holding when its score is greater than the current holding score times the buffer.

## Implementation Anchor

- Data loader reused from `run_subd_proxy_dynamic_cyb_layer0.py`.
- Score/R2 precompute reused from Layer 2.
- Switch-buffer rule matches `_target_from_scores` in `run_subd_six_etf_v1_1.py`.
- No staged entry, target-vol, or overheat in this layer.

## Data Snapshot

- Start/end: `2007-01-04` to `2016-12-30`.
- Rows: `2432`.
- Pool: QQQ/EWG/EWJ/GLD from 2007 start; ChiNext joins when its own data exists.

## Cost and Execution Assumptions

- One-way cost: `0.001`.
- Calendar: A-share trading days; US adjusted closes are forward-filled onto that calendar for this proxy diagnostic.
- Trades involving a forward-filled trade leg are blocked for that day.

## Runtime Override Plan

- Lines carried: `[(28, 0.5, 'layer2_primary'), (28, 0.4, 'r2_neighbor'), (32, 0.5, 'return_peak_watch'), (25, 0.2, 'original_layer3')]`.
- Switch-buffer grid: `['1p00', '1p02', '1p03', '1p05', '1p08', '1p10', '1p15', '1p20']`.
- Baseline: same `lookback + R2` with switch buffer `1.00`.
- Pass rule: Full maxDD improves by more than `0.01pp`; at least 3 of the 4 available windows improve maxDD by more than `0.01pp`; Full/5Y annualized return lag <=1pp and 3Y/1Y lag <=3pp versus same-line no-buffer baseline.

## Commands

- `python run_subd_proxy_dynamic_cyb_layer3_switch_buffer_scan.py --start-date 2007-01-01 --end-date 2016-12-30 --run-folder quant_param_scan_runs\20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_switch_buffer_layer3_switch_buffer`

## Output Files

- `scan_summary.csv`
- `window_metrics.csv`
- `comparison_list.csv`
- `daily_outputs/switch_buffer_daily_curves.csv`
- `sources.csv`

## Primary Line Results

| Candidate | Full Ann. | Full MDD | Full Ann Delta pp | Full MDD Improve pp | 5Y Ann. | 3Y Ann. | 1Y Ann. | Trades Full | Blocked Days Full | Pass | Reason |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| lb_28_r2_0p50_buf_1p00 | 10.09% | -26.30% | 0.00 | 0.00 | 10.39% | 7.13% | 0.01% | 253 | 0 | False | baseline/no switch buffer |
| lb_28_r2_0p50_buf_1p02 | 10.33% | -27.60% | 0.23 | -1.30 | 11.09% | 7.36% | 0.01% | 247 | 9 | False | full_mdd=False;dd_windows=1;return_tol=True |
| lb_28_r2_0p50_buf_1p03 | 10.57% | -27.60% | 0.47 | -1.30 | 11.24% | 7.61% | 0.67% | 245 | 16 | False | full_mdd=False;dd_windows=1;return_tol=True |
| lb_28_r2_0p50_buf_1p05 | 10.45% | -27.70% | 0.36 | -1.40 | 10.58% | 8.20% | 0.67% | 241 | 28 | False | full_mdd=False;dd_windows=1;return_tol=True |
| lb_28_r2_0p50_buf_1p08 | 11.40% | -27.37% | 1.30 | -1.07 | 11.96% | 9.02% | 0.67% | 236 | 41 | False | full_mdd=False;dd_windows=1;return_tol=True |
| lb_28_r2_0p50_buf_1p10 | 10.68% | -28.81% | 0.59 | -2.51 | 11.59% | 8.48% | 0.94% | 235 | 56 | False | full_mdd=False;dd_windows=1;return_tol=True |
| lb_28_r2_0p50_buf_1p15 | 11.26% | -28.88% | 1.17 | -2.57 | 12.29% | 9.54% | 0.94% | 230 | 68 | False | full_mdd=False;dd_windows=1;return_tol=True |
| lb_28_r2_0p50_buf_1p20 | 11.12% | -28.88% | 1.03 | -2.57 | 12.76% | 9.88% | -1.09% | 229 | 86 | False | full_mdd=False;dd_windows=1;return_tol=True |

## Passing Or Best Candidates

| Candidate | Role | Full Ann. | Full MDD | Full MDD Improve pp | DD Improve Windows | Pass |
|---|---|---:|---:|---:|---:|---|
| lb_25_r2_0p20_buf_1p20 | original_layer3 | 10.94% | -32.92% | 0.39 | 4 | False |
| lb_25_r2_0p20_buf_1p15 | original_layer3 | 11.21% | -33.00% | 0.31 | 4 | False |
| lb_25_r2_0p20_buf_1p03 | original_layer3 | 10.83% | -33.31% | 0.00 | 0 | False |
| lb_25_r2_0p20_buf_1p02 | original_layer3 | 11.45% | -33.31% | 0.00 | 0 | False |
| lb_32_r2_0p50_buf_1p02 | return_peak_watch | 11.31% | -19.61% | 0.00 | 0 | False |
| lb_32_r2_0p50_buf_1p05 | return_peak_watch | 11.73% | -19.61% | 0.00 | 0 | False |
| lb_32_r2_0p50_buf_1p03 | return_peak_watch | 11.61% | -19.61% | -0.00 | 0 | False |
| lb_32_r2_0p50_buf_1p10 | return_peak_watch | 10.66% | -20.24% | -0.63 | 0 | False |
| lb_32_r2_0p50_buf_1p15 | return_peak_watch | 10.14% | -20.24% | -0.63 | 0 | False |
| lb_32_r2_0p50_buf_1p08 | return_peak_watch | 11.19% | -20.24% | -0.63 | 0 | False |

## Comparison List

| Candidate | Type | Full Ann. | Full MDD | 5Y Ann. | 3Y Ann. | 1Y Ann. | Notes |
|---|---|---:|---:|---:|---:|---:|---|
| lb_28_r2_0p50_buf_1p00 | layer2_carried_baseline | 10.09% | -26.30% | 10.39% | 7.13% | 0.01% | Layer2 carried primary line before switch buffer |
| lb_28_r2_0p50_buf_1p05 | layer3_primary_original_buffer | 10.45% | -27.70% | 10.58% | 8.20% | 0.67% | Layer2 primary with original switch buffer 1.05 |
| lb_28_r2_0p40_buf_1p05 | r2_neighbor_original_buffer | 9.51% | -32.66% | 9.58% | 7.42% | -11.57% | R2 neighbor with original switch buffer 1.05 |
| lb_32_r2_0p50_buf_1p05 | return_peak_watch_original_buffer | 11.73% | -19.61% | 11.12% | 8.38% | -3.06% | Return peak watch line with original switch buffer 1.05 |
| orig_layer3_lb25_r2_0p20_buf_1p05 | original_layer3_switch_buffer | 9.71% | -34.54% | 8.36% | -0.51% | -23.28% | Original first-layer parameter plus original R2 0.20 and switch buffer 1.05 |
| orig_full_v1_1_reference | original_full_strategy_reference | 11.84% | -36.96% | 12.61% | 3.41% | -26.98% | Full official V1.1 chain; reference only, not Layer3 pass baseline |

## Stability Classification

- Selected candidate: `lb_28_r2_0p50_buf_1p00`.
- Decision: `do_not_add_switch_buffer_keep_layer2_primary`.
- Stability label: `no_pass_keep_previous`.
- 10Y remains N/A by sample length and is not fabricated for strict scanner compatibility.

## Decision

- Decision: `do_not_add_switch_buffer_keep_layer2_primary`.
- Stop here before any staged-entry, target-vol, or overheat layer.

## User-Facing Summary

Layer 3 selected `lb_28_r2_0p50_buf_1p00` under the documented pass rule. See `window_metrics.csv` for all switch-buffer lines.

## Source Audit

| code          | name                            | source                                  | adjustment                | first_available   | first_used   | last       |   rows | pool_rule                                                  | last_aligned   |   ffill_days_on_cn_calendar |
|:--------------|:--------------------------------|:----------------------------------------|:--------------------------|:------------------|:-------------|:-----------|-------:|:-----------------------------------------------------------|:---------------|----------------------------:|
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY      | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWG           | GERMANY_EWG_ADJ_CLOSE_PROXY     | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWJ           | JAPAN_EWJ_ADJ_CLOSE_PROXY       | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY        | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_ADD | Eastmoney push2his kline secid=0.399006 | index close / price index | 2010-06-01        | 2010-06-01   | 2016-12-30 |   1601 | dynamic asset; no prices before 2010-06-01 and no backfill | 2016-12-30     |                           0 |

## Finalization

- Finalized at: 2026-07-01T20:03:37+08:00
- Decision: do_not_add_switch_buffer_keep_lb28_r2_0p50_buf_1p00
- Stability label: no_primary_or_watch_pass_keep_layer2_primary
- Complete checker: PASS
