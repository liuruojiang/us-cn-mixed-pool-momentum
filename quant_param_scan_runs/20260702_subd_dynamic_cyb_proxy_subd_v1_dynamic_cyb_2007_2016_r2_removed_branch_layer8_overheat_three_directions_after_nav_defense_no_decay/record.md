# Sub-D Dynamic ChiNext Proxy R2-Removed Branch Layer 8 Overheat Three-Direction Scan

## Run Metadata

- Run folder: `quant_param_scan_runs\20260702_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_r2_removed_branch_layer8_overheat_three_directions_after_nav_defense_no_decay`
- Layer: `Layer 8` after R2 removal, rejected target-vol, rejected momentum decay, and selected NAV defense.
- Entrypoint: `run_subd_proxy_dynamic_cyb_r2none_layer8_overheat_three_directions_scan.py`

## Research Question

Test three overheat-control directions on the two Layer 7 selected NAV-defense lines.

## Three Directions

- `fixed_same_side`: MA60 bias and 20-day bias-momentum same-side overheat with fixed enter/exit thresholds.
- `adaptive_quantile`: same-side overheat with per-asset rolling 252-session bias quantile thresholds.
- `score_veto`: rebuild the signal with different `SCORE_MAX` values.

## Carried Lines

- `main_nav_r2_removed`: `lb_28_r2_none_buf_1p15_entry_0p25_decay_off_nav_enter_0p2_exit_0p05_scale_0p50`.
- `return_watch_nav_r2_removed`: `lb_28_r2_none_buf_1p15_entry_0p75_decay_off_nav_enter_0p15_exit_0p1_scale_0p75`.

## Data Snapshot

- Start/end: `2007-01-04` to `2016-12-30`.
- Rows: `2432`.
- Pool: QQQ/EWG/EWJ/GLD from 2007 start; ChiNext joins when its own data exists.
- 10Y is N/A because 2432 sessions is less than 2520 trading days.

## Cost and Execution Assumptions

- One-way cost: `0.001`.
- Overheat scale is set at T close and effective next session.
- Overheat costs are included through final-exposure recomputation.
- Calendar: A-share trading days; US adjusted closes are forward-filled onto that calendar for this proxy diagnostic.
- Trades involving a forward-filled trade leg are blocked by the base staged-entry path for that day.

## Selection By Direction

| Line | Direction | Selected/Best | Role | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Full Ann Delta pp | Full MDD Improve pp | Effect Days Full | Pass | Reason |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| main_nav_r2_removed | fixed_same_side | `lb_28_r2_none_buf_1p15_entry_0p25_decay_off_nav_enter_0p2_exit_0p05_scale_0p50_fixed_same_side_fixed_enter_0p15_exit_0p13_scale_0p00_same_side_or_exit` | best_diagnostic_no_pass | 11.22% | -25.06% | N/A | N/A | 7.61% | -21.90% | 6.55% | -21.90% | -5.33% | -11.15% | 1.28 | 0.00 | 4.69% | False | full_mdd=False;dd_windows=2;return_tol=True;material=True |
| main_nav_r2_removed | adaptive_quantile | `lb_28_r2_none_buf_1p15_entry_0p25_decay_off_nav_enter_0p2_exit_0p05_scale_0p50_adaptive_quantile_adaptive_w252_eq0p95_xq0p6_floor_0p1_0p05_scale_0p50_same_side_or_exit` | best_diagnostic_no_pass | 7.94% | -23.44% | N/A | N/A | 4.39% | -23.44% | 4.66% | -23.44% | -6.01% | -11.15% | -2.00 | 1.62 | 11.35% | False | full_mdd=True;dd_windows=1;return_tol=False;material=True |
| main_nav_r2_removed | score_veto | `lb_28_r2_none_buf_1p15_entry_0p25_decay_off_nav_enter_0p2_exit_0p05_scale_0p50_score_veto_scoremax_4` | best_diagnostic_no_pass | 8.09% | -25.78% | N/A | N/A | 3.53% | -25.78% | -0.21% | -25.78% | -8.39% | -11.72% | -1.85 | -0.72 | 9.13% | False | full_mdd=False;dd_windows=0;return_tol=False;material=True |
| return_watch_nav_r2_removed | fixed_same_side | `lb_28_r2_none_buf_1p15_entry_0p75_decay_off_nav_enter_0p15_exit_0p1_scale_0p75_fixed_same_side_fixed_enter_0p22_exit_0p2_scale_0p00_same_side_or_exit` | selected_pass | 11.80% | -28.09% | N/A | N/A | 5.54% | -23.48% | 4.72% | -23.48% | -16.32% | -23.48% | 1.38 | 0.96 | 0.37% | True | pass |
| return_watch_nav_r2_removed | adaptive_quantile | `lb_28_r2_none_buf_1p15_entry_0p75_decay_off_nav_enter_0p15_exit_0p1_scale_0p75_adaptive_quantile_adaptive_w252_eq0p85_xq0p6_floor_0p1_0p05_scale_0p50_same_side_or_exit` | best_diagnostic_no_pass | 8.47% | -29.59% | N/A | N/A | 2.42% | -29.59% | -0.25% | -29.59% | -16.96% | -23.48% | -1.94 | -0.54 | 14.72% | False | full_mdd=False;dd_windows=0;return_tol=False;material=True |
| return_watch_nav_r2_removed | score_veto | `lb_28_r2_none_buf_1p15_entry_0p75_decay_off_nav_enter_0p15_exit_0p1_scale_0p75_score_veto_scoremax_inf` | best_diagnostic_no_pass | 14.24% | -29.06% | N/A | N/A | 13.63% | -28.24% | 19.19% | -28.24% | -18.86% | -23.48% | 3.83 | -0.00 | 14.76% | False | full_mdd=False;dd_windows=2;return_tol=True;material=True |

## Comparison List

| Candidate | Type | Line | Direction | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Notes |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_off_nav_enter_0p2_exit_0p05_scale_0p50_scoremax_5_overheat_off` | two_line_baseline | main_nav_r2_removed | baseline | 9.94% | -25.06% | N/A | N/A | 6.00% | -22.88% | 6.59% | -22.88% | -5.33% | -11.15% | Carried line before Layer8 overheat tests |
| `lb_28_r2_none_buf_1p15_entry_0p75_decay_off_nav_enter_0p15_exit_0p1_scale_0p75_scoremax_5_overheat_off` | two_line_baseline | return_watch_nav_r2_removed | baseline | 10.42% | -29.05% | N/A | N/A | 3.72% | -29.05% | 1.73% | -29.05% | -16.32% | -23.48% | Carried line before Layer8 overheat tests |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_off_nav_enter_0p2_exit_0p05_scale_0p50_fixed_same_side_fixed_enter_0p15_exit_0p13_scale_0p00_same_side_or_exit` | best_diagnostic_no_pass | main_nav_r2_removed | fixed_same_side | 11.22% | -25.06% | N/A | N/A | 7.61% | -21.90% | 6.55% | -21.90% | -5.33% | -11.15% | Best candidate within its line and overheat direction |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_off_nav_enter_0p2_exit_0p05_scale_0p50_adaptive_quantile_adaptive_w252_eq0p95_xq0p6_floor_0p1_0p05_scale_0p50_same_side_or_exit` | best_diagnostic_no_pass | main_nav_r2_removed | adaptive_quantile | 7.94% | -23.44% | N/A | N/A | 4.39% | -23.44% | 4.66% | -23.44% | -6.01% | -11.15% | Best candidate within its line and overheat direction |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_off_nav_enter_0p2_exit_0p05_scale_0p50_score_veto_scoremax_4` | best_diagnostic_no_pass | main_nav_r2_removed | score_veto | 8.09% | -25.78% | N/A | N/A | 3.53% | -25.78% | -0.21% | -25.78% | -8.39% | -11.72% | Best candidate within its line and overheat direction |
| `lb_28_r2_none_buf_1p15_entry_0p75_decay_off_nav_enter_0p15_exit_0p1_scale_0p75_fixed_same_side_fixed_enter_0p22_exit_0p2_scale_0p00_same_side_or_exit` | selected_pass | return_watch_nav_r2_removed | fixed_same_side | 11.80% | -28.09% | N/A | N/A | 5.54% | -23.48% | 4.72% | -23.48% | -16.32% | -23.48% | Best candidate within its line and overheat direction |
| `lb_28_r2_none_buf_1p15_entry_0p75_decay_off_nav_enter_0p15_exit_0p1_scale_0p75_adaptive_quantile_adaptive_w252_eq0p85_xq0p6_floor_0p1_0p05_scale_0p50_same_side_or_exit` | best_diagnostic_no_pass | return_watch_nav_r2_removed | adaptive_quantile | 8.47% | -29.59% | N/A | N/A | 2.42% | -29.59% | -0.25% | -29.59% | -16.96% | -23.48% | Best candidate within its line and overheat direction |
| `lb_28_r2_none_buf_1p15_entry_0p75_decay_off_nav_enter_0p15_exit_0p1_scale_0p75_score_veto_scoremax_inf` | best_diagnostic_no_pass | return_watch_nav_r2_removed | score_veto | 14.24% | -29.06% | N/A | N/A | 13.63% | -28.24% | 19.19% | -28.24% | -18.86% | -23.48% | Best candidate within its line and overheat direction |
| `orig_full_v1_1_reference` | original_full_v1_1_reference | original | original_full_chain | 11.84% | -36.96% | N/A | N/A | 12.61% | -36.96% | 3.41% | -36.96% | -26.98% | -36.96% | Full official V1.1 proxy-chain reference: original lookback 25, R2 0.20, switch buffer 1.05, staged entry 0.50, target-vol 25%, and original overheat. |

## Stability Classification

- Decision: `carry_forward_overheat_pass_candidates`.
- Stability label: `overheat_direction_pass`.
- Passing direction count: `1`.

## Decision

- This scan reports per-direction pass/fail only.
- Candidates compare only against their own Layer 7 NAV-defense baseline.
- Stop here before combining overheat directions or moving to a later layer.

## Source Audit

| code          | name                            | source                                  | adjustment                | first_available   | first_used   | last       |   rows | pool_rule                                                  | last_aligned   |   ffill_days_on_cn_calendar |
|:--------------|:--------------------------------|:----------------------------------------|:--------------------------|:------------------|:-------------|:-----------|-------:|:-----------------------------------------------------------|:---------------|----------------------------:|
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY      | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWG           | GERMANY_EWG_ADJ_CLOSE_PROXY     | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWJ           | JAPAN_EWJ_ADJ_CLOSE_PROXY       | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY        | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_ADD | Eastmoney push2his kline secid=0.399006 | index close / price index | 2010-06-01        | 2010-06-01   | 2016-12-30 |   1601 | dynamic asset; no prices before 2010-06-01 and no backfill | 2016-12-30     |                           0 |

## Finalization

- Finalized at: 2026-07-02T00:21:16+08:00
- Decision: carry_forward_main_nav_no_overheat_return_watch_fixed_same_side_overheat
- Stability label: one_direction_pass_return_watch_only
- Complete checker: PASS
