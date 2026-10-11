# Sub-D Dynamic ChiNext Proxy Layer 7 NAV Defense Scan

## Run Metadata

- Run folder: `quant_param_scan_runs\20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_nav_defense_layer7_nav_drawdown_gate`
- Layer: `Layer 7`
- Strategy: dynamic ChiNext proxy pool, 2007-2016.
- Entrypoint: `run_subd_proxy_dynamic_cyb_layer7_nav_defense_scan.py`

## Research Question

Add strategy-level NAV drawdown defense after the carried Layer 6 score-peak momentum-decay line.

## Implementation Anchor

- Data loader reused from `run_subd_proxy_dynamic_cyb_layer0.py`.
- Base curves reuse Layer 4 staged entry plus Layer 6 `apply_momentum_decay_layer`.
- NAV defense uses the pre-NAV-defense Layer 6 NAV drawdown as `nav_defense_base_dd`.
- T close base DD determines the next-session defense scale; effective scale is shifted one session.
- NAV/exposure/cost recomputation reuses `_recompute_final_exposure_nav` from `run_subd_six_etf_v1_1.py`.
- No target-vol or overheat in this layer.

## Data Snapshot

- Start/end: `2007-01-04` to `2016-12-30`.
- Rows: `2432`.
- Pool: QQQ/EWG/EWJ/GLD from 2007 start; ChiNext joins when its own data exists.

## Cost and Execution Assumptions

- One-way cost: `0.001`.
- NAV defense cost is charged when the defense scale changes final exposure.
- Calendar: A-share trading days; US adjusted closes are forward-filled onto that calendar for this proxy diagnostic.
- Trades involving a forward-filled trade leg are blocked by the base staged-entry path for that day.

## Runtime Override Plan

- Lines carried: `[(28, 0.5, 1.0, 0.75, 0.55, 0.85, 3, 0.75, 'layer6_carried_primary', True), (28, 0.5, 1.0, 0.75, 0.55, 0.95, 3, 0.75, 'recovery_neighbor', True), (28, 0.5, 1.0, 0.75, 0.55, 0.85, 3, 0.5, 'decay_scale_neighbor', True), (32, 0.5, 1.0, 0.75, 0.55, 0.85, 1, 0.75, 'return_peak_watch', True), (25, 0.2, 1.05, 0.5, None, None, None, None, 'original_layer7_same_stage', False)]`.
- NAV enter thresholds: `[0.075, 0.1, 0.125, 0.15, 0.2]`.
- NAV exit thresholds: `[0.03, 0.05, 0.08, 0.1]`.
- Defense scales: `[0.0, 0.25, 0.5, 0.75]`.
- Baseline: same `lookback + R2 + switch buffer + entry fraction + momentum decay` with NAV defense disabled.
- Pass rule: Full maxDD improves by more than `0.01pp`; at least 3 of the 4 available windows improve maxDD by more than `0.01pp`; Full/5Y annualized return lag <=1pp and 3Y/1Y lag <=3pp versus same-line no-NAV-defense baseline.

## Commands

- `python run_subd_proxy_dynamic_cyb_layer7_nav_defense_scan.py --start-date 2007-01-01 --end-date 2016-12-30 --run-folder quant_param_scan_runs\20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_nav_defense_layer7_nav_drawdown_gate`

## Output Files

- `scan_summary.csv`
- `window_metrics.csv`
- `comparison_list.csv`
- `daily_outputs/nav_defense_daily_curves.csv`
- `sources.csv`

## Primary Line Results

| Candidate | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Full Ann Delta pp | Full MDD Improve pp | Trigger Full | Defense Days Full | Pass | Reason |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c3_scale_0p75_nav_off | 9.11% | -22.53% | N/A | N/A | 9.25% | -18.40% | 7.47% | -18.40% | 3.25% | -18.40% | 0.00 | 0.00 | 0 | 0.00% | False | baseline/no NAV defense |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c3_scale_0p75_nav_enter_0p125_exit_0p03_scale_0p75 | 8.19% | -20.05% | N/A | N/A | 8.67% | -16.94% | 6.54% | -16.94% | 3.33% | -16.94% | -0.92 | 2.48 | 4 | 36.06% | True | pass |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c3_scale_0p75_nav_enter_0p15_exit_0p03_scale_0p75 | 8.18% | -21.42% | N/A | N/A | 8.33% | -17.79% | 5.98% | -17.79% | 2.27% | -17.79% | -0.93 | 1.11 | 3 | 25.37% | True | pass |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c3_scale_0p75_nav_enter_0p15_exit_0p1_scale_0p75 | 8.16% | -21.42% | N/A | N/A | 8.28% | -17.79% | 5.89% | -17.79% | 2.27% | -17.79% | -0.95 | 1.11 | 5 | 15.46% | True | pass |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c3_scale_0p75_nav_enter_0p2_exit_0p1_scale_0p75 | 8.70% | -22.30% | N/A | N/A | 9.25% | -18.40% | 7.47% | -18.40% | 3.25% | -18.40% | -0.40 | 0.23 | 1 | 4.32% | False | full_mdd=True;dd_windows=1;return_tol=True;material=True |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c3_scale_0p75_nav_enter_0p2_exit_0p08_scale_0p75 | 8.64% | -22.30% | N/A | N/A | 9.25% | -18.40% | 7.47% | -18.40% | 3.25% | -18.40% | -0.47 | 0.23 | 1 | 4.81% | False | full_mdd=True;dd_windows=1;return_tol=True;material=True |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c3_scale_0p75_nav_enter_0p2_exit_0p03_scale_0p75 | 8.52% | -22.30% | N/A | N/A | 9.25% | -18.40% | 7.47% | -18.40% | 3.25% | -18.40% | -0.59 | 0.23 | 1 | 4.89% | False | full_mdd=True;dd_windows=1;return_tol=True;material=True |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c3_scale_0p75_nav_enter_0p2_exit_0p05_scale_0p75 | 8.52% | -22.30% | N/A | N/A | 9.25% | -18.40% | 7.47% | -18.40% | 3.25% | -18.40% | -0.59 | 0.23 | 1 | 4.89% | False | full_mdd=True;dd_windows=1;return_tol=True;material=True |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c3_scale_0p75_nav_enter_0p2_exit_0p1_scale_0p50 | 8.28% | -22.14% | N/A | N/A | 9.25% | -18.40% | 7.47% | -18.40% | 3.25% | -18.40% | -0.82 | 0.39 | 1 | 4.32% | False | full_mdd=True;dd_windows=1;return_tol=True;material=True |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c3_scale_0p75_nav_enter_0p2_exit_0p08_scale_0p50 | 8.15% | -22.14% | N/A | N/A | 9.25% | -18.40% | 7.47% | -18.40% | 3.25% | -18.40% | -0.95 | 0.39 | 1 | 4.81% | False | full_mdd=True;dd_windows=1;return_tol=True;material=True |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c3_scale_0p75_nav_enter_0p15_exit_0p08_scale_0p75 | 8.10% | -21.42% | N/A | N/A | 7.95% | -17.82% | 5.36% | -17.79% | 2.27% | -17.79% | -1.01 | 1.11 | 4 | 16.12% | False | full_mdd=True;dd_windows=4;return_tol=False;material=True |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c3_scale_0p75_nav_enter_0p125_exit_0p05_scale_0p75 | 8.05% | -20.05% | N/A | N/A | 8.25% | -16.94% | 5.86% | -16.94% | 3.33% | -16.94% | -1.05 | 2.48 | 5 | 31.50% | False | full_mdd=True;dd_windows=4;return_tol=False;material=True |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c3_scale_0p75_nav_enter_0p2_exit_0p03_scale_0p50 | 7.91% | -22.14% | N/A | N/A | 9.25% | -18.40% | 7.47% | -18.40% | 3.25% | -18.40% | -1.19 | 0.39 | 1 | 4.89% | False | full_mdd=True;dd_windows=1;return_tol=False;material=True |

## Passing Or Best Candidates

| Candidate | Role | Full Ann. | Full MDD | Full MDD Improve pp | DD Improve Windows | Trigger Full | Defense Days Full | Pass |
|---|---|---:|---:|---:|---:|---:|---:|---|
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c1_scale_0p75_nav_enter_0p15_exit_0p03_scale_0p00 | return_peak_watch | 10.45% | -15.26% | 2.89 | 4 | 1 | 6.58% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c1_scale_0p75_nav_enter_0p15_exit_0p05_scale_0p00 | return_peak_watch | 10.45% | -15.26% | 2.89 | 4 | 1 | 6.58% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c1_scale_0p75_nav_enter_0p15_exit_0p08_scale_0p00 | return_peak_watch | 10.45% | -15.26% | 2.89 | 4 | 1 | 6.58% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c1_scale_0p75_nav_enter_0p15_exit_0p1_scale_0p00 | return_peak_watch | 10.45% | -15.26% | 2.89 | 4 | 1 | 6.58% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c1_scale_0p75_nav_enter_0p15_exit_0p03_scale_0p25 | return_peak_watch | 10.39% | -15.97% | 2.18 | 4 | 1 | 6.58% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c1_scale_0p75_nav_enter_0p15_exit_0p05_scale_0p25 | return_peak_watch | 10.39% | -15.97% | 2.18 | 4 | 1 | 6.58% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c1_scale_0p75_nav_enter_0p15_exit_0p08_scale_0p25 | return_peak_watch | 10.39% | -15.97% | 2.18 | 4 | 1 | 6.58% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c1_scale_0p75_nav_enter_0p15_exit_0p1_scale_0p25 | return_peak_watch | 10.39% | -15.97% | 2.18 | 4 | 1 | 6.58% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c1_scale_0p75_nav_enter_0p15_exit_0p03_scale_0p50 | return_peak_watch | 10.33% | -16.68% | 1.47 | 4 | 1 | 6.58% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c1_scale_0p75_nav_enter_0p15_exit_0p05_scale_0p50 | return_peak_watch | 10.33% | -16.68% | 1.47 | 4 | 1 | 6.58% | True |

## Comparison List

| Candidate | Type | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c3_scale_0p75_nav_off | layer6_carried_baseline | 9.11% | -22.53% | N/A | N/A | 9.25% | -18.40% | 7.47% | -18.40% | 3.25% | -18.40% | Layer6 carried primary line before NAV defense |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c3_scale_0p75_nav_enter_0p125_exit_0p03_scale_0p75 | layer7_selected | 8.19% | -20.05% | N/A | N/A | 8.67% | -16.94% | 6.54% | -16.94% | 3.33% | -16.94% | Selected Layer7 line under the documented pass rule |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c3_scale_0p50_nav_off | decay_scale_neighbor_nav_off | 9.06% | -21.96% | N/A | N/A | 8.89% | -17.27% | 7.49% | -17.27% | 4.66% | -17.27% | More defensive Layer6 neighbor before NAV defense |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c1_scale_0p75_nav_off | return_peak_watch_nav_off | 10.19% | -18.15% | N/A | N/A | 9.65% | -18.15% | 8.25% | -18.15% | -2.63% | -18.15% | Return-peak watch line before NAV defense |
| orig_layer7_lb25_r2_0p20_buf_1p05_entry_0p50_decay_off_nav_off | original_layer7_same_stage_nav_off | 8.03% | -28.16% | N/A | N/A | 8.27% | -28.16% | 3.26% | -28.16% | -17.99% | -27.04% | Original first-layer parameter plus original R2 0.20, switch buffer 1.05, initial entry fraction 0.50; no momentum decay and no NAV defense |
| orig_full_v1_1_reference | original_full_strategy_reference | 11.84% | -36.96% | N/A | N/A | 12.61% | -36.96% | 3.41% | -36.96% | -26.98% | -36.96% | Full official V1.1 chain including target-vol and overheat; context only, not Layer7 pass baseline |

## Stability Classification

- Selected candidate: `lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c3_scale_0p75_nav_enter_0p125_exit_0p03_scale_0p75`.
- Decision: `carry_forward_primary_nav_defense_pass`.
- Stability label: `primary_pass`.
- Best non-primary pass: `lb_32_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c1_scale_0p75_nav_enter_0p15_exit_0p03_scale_0p00`.
- 10Y remains N/A by sample length: 2432 sessions is less than 2520 trading days.

## Decision

- Decision: `carry_forward_primary_nav_defense_pass`.
- Stop here before any later overlay.

## User-Facing Summary

Layer 7 selected `lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c3_scale_0p75_nav_enter_0p125_exit_0p03_scale_0p75` under the documented pass rule. See `window_metrics.csv` for all NAV defense lines.

## Source Audit

| code          | name                            | source                                  | adjustment                | first_available   | first_used   | last       |   rows | pool_rule                                                  | last_aligned   |   ffill_days_on_cn_calendar |
|:--------------|:--------------------------------|:----------------------------------------|:--------------------------|:------------------|:-------------|:-----------|-------:|:-----------------------------------------------------------|:---------------|----------------------------:|
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY      | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWG           | GERMANY_EWG_ADJ_CLOSE_PROXY     | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWJ           | JAPAN_EWJ_ADJ_CLOSE_PROXY       | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY        | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_ADD | Eastmoney push2his kline secid=0.399006 | index close / price index | 2010-06-01        | 2010-06-01   | 2016-12-30 |   1601 | dynamic asset; no prices before 2010-06-01 and no backfill | 2016-12-30     |                           0 |

## Finalization

- Finalized at: 2026-07-01T21:23:51+08:00
- Decision: carry_forward_primary_nav_defense_pass
- Stability label: primary_pass
- Complete checker: PASS
