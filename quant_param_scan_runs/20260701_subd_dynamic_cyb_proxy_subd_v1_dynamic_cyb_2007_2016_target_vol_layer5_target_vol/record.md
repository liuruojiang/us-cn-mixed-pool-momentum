# Sub-D Dynamic ChiNext Proxy Layer 5 Target-Vol Scan

## Run Metadata

- Run folder: `quant_param_scan_runs\20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_target_vol_layer5_target_vol`
- Layer: `Layer 5`
- Strategy: dynamic ChiNext proxy pool, 2007-2016.
- Entrypoint: `run_subd_proxy_dynamic_cyb_layer5_target_vol_scan.py`

## Research Question

Add target-vol scaling after the Layer 4 staged-entry line and compare each target-vol candidate to the same line with no target-vol overlay.

## Implementation Anchor

- Data loader reused from `run_subd_proxy_dynamic_cyb_layer0.py`.
- Base staged-entry curves reuse Layer 4's `run_staged_line` helper.
- Target-vol behavior reuses `apply_target_vol_overlay` from `run_subd_six_etf_v1_1.py`.
- No overheat in this layer.

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

- Lines carried: `[(28, 0.5, 1.0, 0.75, 'layer4_primary'), (28, 0.5, 1.0, 0.67, 'entry_neighbor'), (28, 0.4, 1.0, 0.75, 'r2_neighbor'), (32, 0.5, 1.0, 0.75, 'return_peak_watch'), (25, 0.2, 1.05, 0.5, 'original_layer5')]`.
- Target-vol grid: `['no_tv', 'tv15', 'tv18', 'tv20', 'tv22', 'tv25', 'tv28', 'tv30', 'tv35']`.
- Baseline: same `lookback + R2 + switch buffer + entry fraction` with no target-vol overlay.
- Pass rule: Full maxDD improves by more than `0.01pp`; at least 3 of the 4 available windows improve maxDD by more than `0.01pp`; Full/5Y annualized return lag <=1pp and 3Y/1Y lag <=3pp versus same-line no-target-vol baseline.

## Commands

- `python run_subd_proxy_dynamic_cyb_layer5_target_vol_scan.py --start-date 2007-01-01 --end-date 2016-12-30 --run-folder quant_param_scan_runs\20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_target_vol_layer5_target_vol`

## Output Files

- `scan_summary.csv`
- `window_metrics.csv`
- `comparison_list.csv`
- `daily_outputs/target_vol_daily_curves.csv`
- `sources.csv`

## Primary Line Results

| Candidate | Full Ann. | Full MDD | Full Ann Delta pp | Full MDD Improve pp | 5Y Ann. | 3Y Ann. | 1Y Ann. | Avg Scale Full | Avg Exposure Full | Pass | Reason |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| lb_28_r2_0p50_buf_1p00_entry_0p75_no_tv | 9.14% | -23.10% | 0.00 | 0.00 | 9.57% | 7.43% | 1.84% | 1.00 | 0.56 | False | baseline/no target-vol |
| lb_28_r2_0p50_buf_1p00_entry_0p75_tv15 | 7.77% | -27.21% | -1.38 | -4.11 | 9.20% | 5.29% | 3.49% | 0.98 | 0.54 | False | full_mdd=False;dd_windows=3;return_tol=False |
| lb_28_r2_0p50_buf_1p00_entry_0p75_tv18 | 8.84% | -30.63% | -0.30 | -7.53 | 10.39% | 6.30% | 4.13% | 1.14 | 0.63 | False | full_mdd=False;dd_windows=0;return_tol=True |
| lb_28_r2_0p50_buf_1p00_entry_0p75_tv20 | 9.57% | -32.62% | 0.43 | -9.51 | 11.12% | 6.99% | 3.57% | 1.22 | 0.68 | False | full_mdd=False;dd_windows=0;return_tol=True |
| lb_28_r2_0p50_buf_1p00_entry_0p75_tv22 | 10.39% | -32.39% | 1.25 | -9.29 | 11.43% | 7.69% | 2.72% | 1.29 | 0.71 | False | full_mdd=False;dd_windows=0;return_tol=True |
| lb_28_r2_0p50_buf_1p00_entry_0p75_tv25 | 11.36% | -33.14% | 2.21 | -10.03 | 13.02% | 9.57% | 4.12% | 1.37 | 0.76 | False | full_mdd=False;dd_windows=0;return_tol=True |
| lb_28_r2_0p50_buf_1p00_entry_0p75_tv28 | 11.94% | -33.35% | 2.79 | -10.24 | 13.24% | 9.58% | 2.29% | 1.42 | 0.79 | False | full_mdd=False;dd_windows=0;return_tol=True |
| lb_28_r2_0p50_buf_1p00_entry_0p75_tv30 | 12.19% | -33.45% | 3.04 | -10.35 | 13.38% | 9.73% | 2.22% | 1.44 | 0.80 | False | full_mdd=False;dd_windows=0;return_tol=True |
| lb_28_r2_0p50_buf_1p00_entry_0p75_tv35 | 12.07% | -33.45% | 2.92 | -10.35 | 13.15% | 9.92% | 2.04% | 1.44 | 0.80 | False | full_mdd=False;dd_windows=0;return_tol=True |

## Passing Or Best Candidates

| Candidate | Role | Full Ann. | Full MDD | Full MDD Improve pp | DD Improve Windows | Pass |
|---|---|---:|---:|---:|---:|---|
| lb_25_r2_0p20_buf_1p05_entry_0p50_tv15 | original_layer5 | 7.06% | -27.98% | 0.18 | 4 | True |

## Comparison List

| Candidate | Type | Full Ann. | Full MDD | 5Y Ann. | 3Y Ann. | 1Y Ann. | Notes |
|---|---|---:|---:|---:|---:|---:|---|
| lb_28_r2_0p50_buf_1p00_entry_0p75_no_tv | layer4_carried_baseline | 9.14% | -23.10% | 9.57% | 7.43% | 1.84% | Layer4 carried primary line before target-vol |
| lb_28_r2_0p50_buf_1p00_entry_0p75_tv25 | layer5_primary_original_target_vol | 11.36% | -33.14% | 13.02% | 9.57% | 4.12% | Layer4 primary with original target-vol 25% |
| lb_28_r2_0p50_buf_1p00_entry_0p67_tv25 | entry_neighbor_original_target_vol | 10.96% | -32.42% | 12.47% | 9.48% | 5.14% | Entry-fraction neighbor with original target-vol 25% |
| lb_32_r2_0p50_buf_1p00_entry_0p75_tv25 | return_peak_watch_original_target_vol | 13.17% | -25.48% | 13.00% | 9.58% | -3.78% | Return peak watch line with original target-vol 25% |
| orig_layer5_lb25_r2_0p20_buf_1p05_entry_0p50_tv25 | original_layer5_target_vol | 10.13% | -38.66% | 10.72% | 2.37% | -26.98% | Original first-layer parameter plus original R2 0.20, switch buffer 1.05, initial entry fraction 0.50, and target-vol 25% |
| orig_full_v1_1_reference | original_full_strategy_reference | 11.84% | -36.96% | 12.61% | 3.41% | -26.98% | Full official V1.1 chain including overheat; reference only, not Layer5 pass baseline |

## Stability Classification

- Selected candidate: `lb_28_r2_0p50_buf_1p00_entry_0p75_no_tv`.
- Decision: `do_not_add_target_vol_keep_layer4_primary_watch_nonprimary`.
- Stability label: `nonprimary_watch_only`.
- Best non-primary pass: `lb_25_r2_0p20_buf_1p05_entry_0p50_tv15`.
- 10Y remains N/A by sample length and is not fabricated for strict scanner compatibility.

## Decision

- Decision: `do_not_add_target_vol_keep_layer4_primary_watch_nonprimary`.
- Stop here before any overheat layer.

## User-Facing Summary

Layer 5 selected `lb_28_r2_0p50_buf_1p00_entry_0p75_no_tv` under the documented pass rule. See `window_metrics.csv` for all target-vol lines.

## Source Audit

| code          | name                            | source                                  | adjustment                | first_available   | first_used   | last       |   rows | pool_rule                                                  | last_aligned   |   ffill_days_on_cn_calendar |
|:--------------|:--------------------------------|:----------------------------------------|:--------------------------|:------------------|:-------------|:-----------|-------:|:-----------------------------------------------------------|:---------------|----------------------------:|
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY      | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWG           | GERMANY_EWG_ADJ_CLOSE_PROXY     | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWJ           | JAPAN_EWJ_ADJ_CLOSE_PROXY       | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY        | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_ADD | Eastmoney push2his kline secid=0.399006 | index close / price index | 2010-06-01        | 2010-06-01   | 2016-12-30 |   1601 | dynamic asset; no prices before 2010-06-01 and no backfill | 2016-12-30     |                           0 |

## Finalization

- Finalized at: 2026-07-01T20:45:05+08:00
- Decision: do_not_add_target_vol_keep_lb28_r2_0p50_buf_1p00_entry_0p75
- Stability label: no_primary_pass_nonprimary_watch_only
- Complete checker: PASS
