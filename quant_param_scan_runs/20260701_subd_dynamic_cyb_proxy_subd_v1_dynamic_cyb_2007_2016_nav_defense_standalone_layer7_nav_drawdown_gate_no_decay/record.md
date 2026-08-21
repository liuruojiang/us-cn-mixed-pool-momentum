# Sub-D Dynamic ChiNext Proxy Standalone NAV Defense Scan

## Run Metadata

- Run folder: `quant_param_scan_runs\20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_nav_defense_standalone_layer7_nav_drawdown_gate_no_decay`
- Layer: `Layer 7 standalone correction`
- Strategy: dynamic ChiNext proxy pool, 2007-2016.
- Entrypoint: `run_subd_proxy_dynamic_cyb_layer7_nav_defense_standalone_scan.py`

## Research Question

Test NAV drawdown defense by itself, without carrying Layer 6 momentum decay.

## Implementation Anchor

- Data loader reused from `run_subd_proxy_dynamic_cyb_layer0.py`.
- Base curves reuse Layer 4 staged entry only; target-vol remains rejected and momentum decay is disabled.
- NAV defense uses the pre-NAV-defense base NAV drawdown as `nav_defense_base_dd`.
- T close base DD determines the next-session defense scale; effective scale is shifted one session.
- NAV/exposure/cost recomputation reuses `_recompute_final_exposure_nav` from `run_subd_six_etf_v1_1.py` via the Layer 7 helper.

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

- Lines carried: `[(28, 0.5, 1.0, 0.75, 'layer5_carried_primary_no_decay', True), (28, 0.5, 1.0, 0.67, 'entry_neighbor_no_decay', True), (28, 0.4, 1.0, 0.75, 'r2_neighbor_no_decay', True), (32, 0.5, 1.0, 0.75, 'return_peak_watch_no_decay', True), (25, 0.2, 1.05, 0.5, 'original_same_stage_no_decay', False)]`.
- NAV enter thresholds: `[0.075, 0.1, 0.125, 0.15, 0.2]`.
- NAV exit thresholds: `[0.03, 0.05, 0.08, 0.1]`.
- Defense scales: `[0.0, 0.25, 0.5, 0.75]`.
- Baseline: same `lookback + R2 + switch buffer + entry fraction` with no target-vol, no momentum decay, and no NAV defense.
- Pass rule: Full maxDD improves by more than `0.01pp`; at least 3 of the 4 available windows improve maxDD by more than `0.01pp`; Full/5Y annualized return lag <=1pp and 3Y/1Y lag <=3pp versus same-line no-NAV-defense baseline.

## Commands

- `python run_subd_proxy_dynamic_cyb_layer7_nav_defense_standalone_scan.py --start-date 2007-01-01 --end-date 2016-12-30 --run-folder quant_param_scan_runs\20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_nav_defense_standalone_layer7_nav_drawdown_gate_no_decay`

## Primary Line Results

| Candidate | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Full Ann Delta pp | Full MDD Improve pp | Trigger Full | Defense Days Full | Pass | Reason |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_off | 9.14% | -23.10% | N/A | N/A | 9.57% | -19.53% | 7.43% | -19.53% | 1.84% | -19.53% | 0.00 | 0.00 | 0 | 0.00% | False | baseline/no NAV defense |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_enter_0p125_exit_0p05_scale_0p75 | 8.33% | -20.50% | N/A | N/A | 8.98% | -18.09% | 6.47% | -18.09% | 1.91% | -18.09% | -0.81 | 2.61 | 4 | 35.90% | True | pass |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_enter_0p15_exit_0p05_scale_0p75 | 8.27% | -22.01% | N/A | N/A | 8.78% | -18.63% | 6.15% | -18.63% | 1.24% | -18.63% | -0.87 | 1.10 | 3 | 25.45% | True | pass |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_enter_0p15_exit_0p03_scale_0p75 | 8.20% | -22.01% | N/A | N/A | 8.73% | -18.63% | 6.07% | -18.63% | 1.24% | -18.63% | -0.94 | 1.10 | 3 | 25.58% | True | pass |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_enter_0p125_exit_0p03_scale_0p75 | 8.19% | -20.50% | N/A | N/A | 8.93% | -18.09% | 6.39% | -18.09% | 1.91% | -18.09% | -0.96 | 2.61 | 4 | 36.10% | True | pass |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_enter_0p2_exit_0p1_scale_0p75 | 8.73% | -22.88% | N/A | N/A | 9.57% | -19.53% | 7.43% | -19.53% | 1.83% | -19.53% | -0.41 | 0.22 | 1 | 4.32% | False | full_mdd=True;dd_windows=1;return_tol=True;material=True |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_enter_0p2_exit_0p08_scale_0p75 | 8.67% | -22.88% | N/A | N/A | 9.57% | -19.53% | 7.43% | -19.53% | 1.83% | -19.53% | -0.47 | 0.22 | 1 | 4.81% | False | full_mdd=True;dd_windows=1;return_tol=True;material=True |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_enter_0p2_exit_0p05_scale_0p75 | 8.55% | -22.88% | N/A | N/A | 9.57% | -19.53% | 7.43% | -19.53% | 1.83% | -19.53% | -0.59 | 0.22 | 1 | 4.89% | False | full_mdd=True;dd_windows=1;return_tol=True;material=True |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_enter_0p2_exit_0p03_scale_0p75 | 8.51% | -22.88% | N/A | N/A | 9.57% | -19.53% | 7.43% | -19.53% | 1.83% | -19.53% | -0.64 | 0.22 | 1 | 4.93% | False | full_mdd=True;dd_windows=1;return_tol=True;material=True |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_enter_0p2_exit_0p1_scale_0p50 | 8.31% | -22.72% | N/A | N/A | 9.57% | -19.53% | 7.43% | -19.53% | 1.83% | -19.53% | -0.83 | 0.38 | 1 | 4.32% | False | full_mdd=True;dd_windows=1;return_tol=True;material=True |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_enter_0p15_exit_0p08_scale_0p75 | 8.26% | -22.01% | N/A | N/A | 8.53% | -18.88% | 5.73% | -18.63% | 1.24% | -18.63% | -0.88 | 1.10 | 4 | 20.72% | False | full_mdd=True;dd_windows=4;return_tol=False;material=True |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_enter_0p2_exit_0p08_scale_0p50 | 8.18% | -22.72% | N/A | N/A | 9.57% | -19.53% | 7.43% | -19.53% | 1.83% | -19.53% | -0.96 | 0.38 | 1 | 4.81% | False | full_mdd=True;dd_windows=1;return_tol=True;material=True |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_enter_0p125_exit_0p08_scale_0p75 | 7.97% | -22.88% | N/A | N/A | 8.88% | -18.10% | 6.30% | -18.09% | 1.91% | -18.09% | -1.18 | 0.22 | 8 | 27.30% | False | full_mdd=True;dd_windows=4;return_tol=False;material=True |

## Passing Or Best Candidates

| Candidate | Role | Full Ann. | Full MDD | Full MDD Improve pp | DD Improve Windows | Trigger Full | Defense Days Full | Pass |
|---|---|---:|---:|---:|---:|---:|---:|---|
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_enter_0p15_exit_0p03_scale_0p00 | return_peak_watch_no_decay | 10.61% | -15.64% | 3.71 | 4 | 1 | 6.70% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_enter_0p15_exit_0p05_scale_0p00 | return_peak_watch_no_decay | 10.61% | -15.64% | 3.71 | 4 | 1 | 6.70% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_enter_0p15_exit_0p08_scale_0p00 | return_peak_watch_no_decay | 10.61% | -15.64% | 3.71 | 4 | 1 | 6.70% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_enter_0p15_exit_0p1_scale_0p00 | return_peak_watch_no_decay | 10.61% | -15.64% | 3.71 | 4 | 1 | 6.70% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_enter_0p15_exit_0p03_scale_0p25 | return_peak_watch_no_decay | 10.52% | -16.57% | 2.78 | 4 | 1 | 6.70% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_enter_0p15_exit_0p05_scale_0p25 | return_peak_watch_no_decay | 10.52% | -16.57% | 2.78 | 4 | 1 | 6.70% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_enter_0p15_exit_0p08_scale_0p25 | return_peak_watch_no_decay | 10.52% | -16.57% | 2.78 | 4 | 1 | 6.70% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_enter_0p15_exit_0p1_scale_0p25 | return_peak_watch_no_decay | 10.52% | -16.57% | 2.78 | 4 | 1 | 6.70% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_enter_0p15_exit_0p03_scale_0p50 | return_peak_watch_no_decay | 10.43% | -17.50% | 1.85 | 4 | 1 | 6.70% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_enter_0p15_exit_0p05_scale_0p50 | return_peak_watch_no_decay | 10.43% | -17.50% | 1.85 | 4 | 1 | 6.70% | True |

## Comparison List

| Candidate | Type | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_off | layer5_carried_baseline_no_decay | 9.14% | -23.10% | N/A | N/A | 9.57% | -19.53% | 7.43% | -19.53% | 1.84% | -19.53% | Layer5 carried primary line; target-vol rejected and momentum decay disabled for standalone NAV-defense test |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_enter_0p125_exit_0p05_scale_0p75 | standalone_nav_defense_selected | 8.33% | -20.50% | N/A | N/A | 8.98% | -18.09% | 6.47% | -18.09% | 1.91% | -18.09% | Selected standalone NAV-defense line under the documented pass rule |
| lb_28_r2_0p50_buf_1p00_entry_0p67_decay_off_nav_off | entry_neighbor_no_decay_nav_off | 8.83% | -22.52% | N/A | N/A | 9.30% | -19.19% | 7.52% | -19.19% | 2.42% | -19.19% | Entry-fraction neighbor before standalone NAV defense |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_off | return_peak_watch_no_decay_nav_off | 10.24% | -19.35% | N/A | N/A | 9.78% | -19.35% | 8.10% | -19.35% | -3.54% | -19.35% | Return-peak watch line before standalone NAV defense |
| orig_layer7_standalone_lb25_r2_0p20_buf_1p05_entry_0p50_nav_off | original_same_stage_no_decay_nav_off | 8.03% | -28.16% | N/A | N/A | 8.27% | -28.16% | 3.26% | -28.16% | -17.99% | -27.04% | Original first-layer parameter plus original R2 0.20, switch buffer 1.05, initial entry fraction 0.50; no momentum decay and no NAV defense |
| orig_full_v1_1_reference | original_full_strategy_reference | 11.84% | -36.96% | N/A | N/A | 12.61% | -36.96% | 3.41% | -36.96% | -26.98% | -36.96% | Full official V1.1 chain including target-vol and overheat; context only, not standalone NAV-defense pass baseline |

## Stability Classification

- Selected candidate: `lb_28_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_enter_0p125_exit_0p05_scale_0p75`.
- Decision: `carry_forward_standalone_nav_defense_pass`.
- Stability label: `primary_pass_no_decay`.
- Best non-primary pass: `lb_32_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_enter_0p15_exit_0p03_scale_0p00`.
- 10Y remains N/A by sample length: 2432 sessions is less than 2520 trading days.

## Decision

- Decision: `carry_forward_standalone_nav_defense_pass`.
- The prior NAV-defense-after-momentum-decay run is diagnostic only and superseded for this standalone layer decision.

## User-Facing Summary

Standalone NAV defense selected `lb_28_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_enter_0p125_exit_0p05_scale_0p75` under the documented pass rule. See `window_metrics.csv` for all lines.

## Source Audit

| code          | name                            | source                                  | adjustment                | first_available   | first_used   | last       |   rows | pool_rule                                                  | last_aligned   |   ffill_days_on_cn_calendar |
|:--------------|:--------------------------------|:----------------------------------------|:--------------------------|:------------------|:-------------|:-----------|-------:|:-----------------------------------------------------------|:---------------|----------------------------:|
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY      | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWG           | GERMANY_EWG_ADJ_CLOSE_PROXY     | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWJ           | JAPAN_EWJ_ADJ_CLOSE_PROXY       | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY        | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_ADD | Eastmoney push2his kline secid=0.399006 | index close / price index | 2010-06-01        | 2010-06-01   | 2016-12-30 |   1601 | dynamic asset; no prices before 2010-06-01 and no backfill | 2016-12-30     |                           0 |

## Finalization

- Finalized at: 2026-07-01T21:35:25+08:00
- Decision: carry_forward_standalone_nav_defense_pass
- Stability label: primary_pass_no_decay
- Complete checker: PASS
