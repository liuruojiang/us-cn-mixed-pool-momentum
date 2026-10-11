# Sub-D Dynamic ChiNext Proxy R2-Removed Branch Layer 7 NAV Defense Scan

## Run Metadata

- Run folder: `quant_param_scan_runs\20260702_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_r2_removed_branch_layer7_nav_defense_after_r2_removed_no_decay`
- Layer: `Layer 7` after R2 removal, rejected target-vol, and rejected momentum decay.
- Entrypoint: `run_subd_proxy_dynamic_cyb_r2none_layer7_nav_defense_scan.py`

## Research Question

Test standalone NAV drawdown defense on the two user-confirmed carried lines.

## Implementation Anchor

- Data loader reused from `run_subd_proxy_dynamic_cyb_layer0.py`.
- Base curves reuse `run_subd_proxy_dynamic_cyb_r2none_layer4_staged_entry_scan.py` plus no-decay scaffolding from the R2-removed Layer 6 script.
- NAV defense uses the pre-NAV-defense base NAV drawdown as `nav_defense_base_dd`.
- T close base DD determines next-session defense scale; effective scale is shifted one session.
- NAV/exposure/cost recomputation reuses `_recompute_final_exposure_nav` from `run_subd_six_etf_v1_1.py`.

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

- Lines: `[(28, 1.15, 0.25, 'main_line_r2_removed'), (28, 1.15, 0.75, 'return_watch_line_r2_removed')]`.
- NAV enter thresholds: `[0.075, 0.1, 0.125, 0.15, 0.2]`.
- NAV exit thresholds: `[0.03, 0.05, 0.08, 0.1]`.
- Defense scales: `[0.0, 0.25, 0.5, 0.75]`.
- Baseline: same `lookback + switch buffer + entry fraction` with R2 removed, no target-vol, no momentum decay, and no NAV defense.
- Pass rule: Full maxDD improves by more than `0.01pp`; at least 3 of 4 available windows improve maxDD; Full/5Y annualized return lag <=1pp and 3Y/1Y lag <=3pp.

## Commands

- `python run_subd_proxy_dynamic_cyb_r2none_layer7_nav_defense_scan.py --start-date 2007-01-01 --end-date 2016-12-30 --run-folder quant_param_scan_runs\20260702_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_r2_removed_branch_layer7_nav_defense_after_r2_removed_no_decay`

## Output Files

- `scan_summary.csv`
- `window_metrics.csv`
- `line_selection.csv`
- `comparison_list.csv`
- `daily_outputs/r2none_nav_defense_daily_curves.csv`
- `sources.csv`

## Line-Level Selection

| Line Role | Candidate | Selection | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | MDD Improve pp | Trigger Full | Defense Days Full | Pass Reason |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| main_line_r2_removed | `lb_28_r2_none_buf_1p15_entry_0p25_decay_off_nav_enter_0p2_exit_0p05_scale_0p50` | selected_drawdown_nav_defense_pass | 9.94% | -25.06% | N/A | N/A | 6.00% | -22.88% | 6.59% | -22.88% | -5.33% | -11.15% | 4.42 | 2 | 18.83% | pass |
| return_watch_line_r2_removed | `lb_28_r2_none_buf_1p15_entry_0p75_decay_off_nav_enter_0p15_exit_0p1_scale_0p75` | return_watch_nav_defense_pass | 10.42% | -29.05% | N/A | N/A | 3.72% | -29.05% | 1.73% | -29.05% | -16.33% | -23.48% | 1.31 | 8 | 22.57% | pass |

## Best NAV Defense Candidates

| Candidate | Role | Full Ann. | Full MDD | Full Ann Delta pp | Full MDD Improve pp | DD Improve Windows | Trigger Full | Defense Days Full | Pass | Reason |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_off_nav_enter_0p2_exit_0p05_scale_0p50` | main_line_r2_removed | 9.94% | -25.06% | -0.69 | 4.42 | 4 | 2 | 18.83% | True | pass |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_off_nav_enter_0p2_exit_0p03_scale_0p50` | main_line_r2_removed | 9.81% | -25.06% | -0.82 | 4.42 | 4 | 2 | 23.15% | True | pass |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_off_nav_enter_0p2_exit_0p05_scale_0p75` | main_line_r2_removed | 10.31% | -27.27% | -0.31 | 2.21 | 4 | 2 | 18.83% | True | pass |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_off_nav_enter_0p2_exit_0p03_scale_0p75` | main_line_r2_removed | 10.25% | -27.27% | -0.38 | 2.21 | 4 | 2 | 23.15% | True | pass |
| `lb_28_r2_none_buf_1p15_entry_0p75_decay_off_nav_enter_0p15_exit_0p1_scale_0p75` | return_watch_line_r2_removed | 10.42% | -29.05% | -0.85 | 1.31 | 4 | 8 | 22.57% | True | pass |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_off_nav_enter_0p125_exit_0p05_scale_0p25` | main_line_r2_removed | 6.87% | -18.87% | -3.76 | 10.61 | 4 | 7 | 33.59% | False | full_mdd=True;dd_windows=4;return_tol=False;material=True |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_off_nav_enter_0p15_exit_0p05_scale_0p25` | main_line_r2_removed | 7.32% | -19.19% | -3.31 | 10.29 | 4 | 5 | 28.45% | False | full_mdd=True;dd_windows=4;return_tol=False;material=True |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_off_nav_enter_0p125_exit_0p03_scale_0p25` | main_line_r2_removed | 5.51% | -20.35% | -5.12 | 9.12 | 4 | 7 | 38.98% | False | full_mdd=True;dd_windows=4;return_tol=False;material=True |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_off_nav_enter_0p15_exit_0p03_scale_0p25` | main_line_r2_removed | 6.31% | -20.91% | -4.32 | 8.57 | 4 | 5 | 33.06% | False | full_mdd=True;dd_windows=4;return_tol=False;material=True |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_off_nav_enter_0p125_exit_0p05_scale_0p50` | main_line_r2_removed | 8.21% | -21.75% | -2.42 | 7.73 | 4 | 7 | 33.59% | False | full_mdd=True;dd_windows=4;return_tol=False;material=True |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_off_nav_enter_0p2_exit_0p03_scale_0p00` | main_line_r2_removed | 8.68% | -21.83% | -1.95 | 7.65 | 4 | 2 | 23.15% | False | full_mdd=True;dd_windows=4;return_tol=False;material=True |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_off_nav_enter_0p125_exit_0p03_scale_0p50` | main_line_r2_removed | 7.30% | -21.90% | -3.33 | 7.58 | 4 | 7 | 38.98% | False | full_mdd=True;dd_windows=4;return_tol=False;material=True |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_off_nav_enter_0p15_exit_0p05_scale_0p00` | main_line_r2_removed | 6.05% | -22.07% | -4.58 | 7.41 | 4 | 5 | 28.45% | False | full_mdd=True;dd_windows=4;return_tol=False;material=True |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_off_nav_enter_0p15_exit_0p05_scale_0p50` | main_line_r2_removed | 8.50% | -22.64% | -2.13 | 6.84 | 4 | 5 | 28.45% | False | full_mdd=True;dd_windows=4;return_tol=False;material=True |

## Comparison List

| Candidate | Type | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_off_nav_off` | line_baseline_no_nav_defense | 10.63% | -29.48% | N/A | N/A | 5.49% | -26.22% | 5.72% | -26.22% | -11.11% | -21.36% | Same carried line before NAV-defense layer |
| `lb_28_r2_none_buf_1p15_entry_0p75_decay_off_nav_off` | line_baseline_no_nav_defense | 11.27% | -30.37% | N/A | N/A | 4.63% | -30.11% | 2.04% | -30.11% | -18.18% | -26.92% | Same carried line before NAV-defense layer |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_off_nav_enter_0p2_exit_0p05_scale_0p50` | selected_drawdown_nav_defense_pass | 9.94% | -25.06% | N/A | N/A | 6.00% | -22.88% | 6.59% | -22.88% | -5.33% | -11.15% | Line-level selected NAV-defense result |
| `lb_28_r2_none_buf_1p15_entry_0p75_decay_off_nav_enter_0p15_exit_0p1_scale_0p75` | return_watch_nav_defense_pass | 10.42% | -29.05% | N/A | N/A | 3.72% | -29.05% | 1.73% | -29.05% | -16.33% | -23.48% | Line-level selected NAV-defense result |
| `orig_full_v1_1_reference` | original_full_v1_1_reference | 11.84% | -36.96% | N/A | N/A | 12.61% | -36.96% | 3.41% | -36.96% | -26.98% | -36.96% | Full official V1.1 chain on this proxy panel; includes original lookback 25, R2 0.20, switch buffer 1.05, staged entry 0.50, target-vol 25%, and later overlays. |

## Stability Classification

- Decision: `line_level_selection_after_nav_defense_on_r2_removed_branch`.
- Stability label: `nav_defense_pass_if_line_selection_uses_overlay_else_keep_previous`.
- 10Y remains N/A by sample length: 2432 sessions is less than 2520 trading days.

## Decision

- Keep each line's selected row from `line_selection.csv`.
- Stop here before overheat tests.

## Source Audit

| code          | name                            | source                                  | adjustment                | first_available   | first_used   | last       |   rows | pool_rule                                                  | last_aligned   |   ffill_days_on_cn_calendar |
|:--------------|:--------------------------------|:----------------------------------------|:--------------------------|:------------------|:-------------|:-----------|-------:|:-----------------------------------------------------------|:---------------|----------------------------:|
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY      | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWG           | GERMANY_EWG_ADJ_CLOSE_PROXY     | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWJ           | JAPAN_EWJ_ADJ_CLOSE_PROXY       | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY        | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_ADD | Eastmoney push2his kline secid=0.399006 | index close / price index | 2010-06-01        | 2010-06-01   | 2016-12-30 |   1601 | dynamic asset; no prices before 2010-06-01 and no backfill | 2016-12-30     |                           0 |

## Finalization

- Finalized at: 2026-07-02T00:10:20+08:00
- Decision: carry_forward_nav_defense_two_lines
- Stability label: two_line_nav_defense_pass
- Complete checker: PASS
