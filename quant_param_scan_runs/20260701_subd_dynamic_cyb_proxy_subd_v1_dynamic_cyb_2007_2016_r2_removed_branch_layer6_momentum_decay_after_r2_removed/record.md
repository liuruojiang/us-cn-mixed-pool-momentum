# Sub-D Dynamic ChiNext Proxy R2-Removed Branch Layer 6 Momentum Decay Scan

## Run Metadata

- Run folder: `quant_param_scan_runs\20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_r2_removed_branch_layer6_momentum_decay_after_r2_removed`
- Layer: `Layer 6` after R2 removal, switch-buffer/staged-entry selection, and rejected target-vol.
- Entrypoint: `run_subd_proxy_dynamic_cyb_r2none_layer6_momentum_decay_scan.py`

## Research Question

Test score-peak momentum decay on the two user-confirmed no-target-vol lines.

## Implementation Anchor

- Data loader reused from `run_subd_proxy_dynamic_cyb_layer0.py`.
- Base curves reuse `run_subd_proxy_dynamic_cyb_r2none_layer4_staged_entry_scan.py`.
- Momentum decay state machine reuses `score_peak_decay_state` from the existing Layer 6 script.
- NAV/exposure/cost recomputation reuses `_recompute_final_exposure_nav` from `run_subd_six_etf_v1_1.py`.
- No target-vol, NAV defense, or overheat in this layer.

## Data Snapshot

- Start/end: `2007-01-04` to `2016-12-30`.
- Rows: `2432`.
- Pool: QQQ/EWG/EWJ/GLD from 2007 start; ChiNext joins when its own data exists.

## Cost and Execution Assumptions

- One-way cost: `0.001`.
- Score-decay signal uses close information for the next holding scale; effective scale is shifted one session.
- Calendar: A-share trading days; US adjusted closes are forward-filled onto that calendar for this proxy diagnostic.
- Trades involving a forward-filled trade leg are blocked by the base staged-entry path for that day.

## Runtime Override Plan

- Lines: `[(28, 1.15, 0.25, 'main_line_r2_removed'), (28, 1.15, 0.75, 'return_watch_line_r2_removed')]`.
- Decay ratios: `[0.45, 0.55, 0.65, 0.75]`.
- Recovery ratios: `[0.85, 0.95]`.
- Confirm days: `[1, 3]`.
- Derisk scales: `[0.0, 0.5, 0.75]`.
- Baseline: same `lookback + switch buffer + entry fraction` with momentum decay disabled.
- Pass rule: Full maxDD improves by more than `0.01pp`; at least 3 of 4 available windows improve maxDD; Full/5Y annualized return lag <=1pp and 3Y/1Y lag <=3pp.

## Commands

- `python run_subd_proxy_dynamic_cyb_r2none_layer6_momentum_decay_scan.py --start-date 2007-01-01 --end-date 2016-12-30 --run-folder quant_param_scan_runs\20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_r2_removed_branch_layer6_momentum_decay_after_r2_removed`

## Output Files

- `scan_summary.csv`
- `window_metrics.csv`
- `line_selection.csv`
- `comparison_list.csv`
- `daily_outputs/r2none_momentum_decay_daily_curves.csv`
- `sources.csv`

## Line-Level Selection

| Line Role | Candidate | Selection | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | MDD Improve pp | Trigger Full | Decay Days Full | Pass Reason |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| main_line_r2_removed | `lb_28_r2_none_buf_1p15_entry_0p25_decay_off` | baseline_no_momentum_decay_pass | 10.63% | -29.48% | N/A | N/A | 5.49% | -26.22% | 5.72% | -26.22% | -11.11% | -21.36% | 0.00 | 0 | 0.00% | baseline/no momentum decay |
| return_watch_line_r2_removed | `lb_28_r2_none_buf_1p15_entry_0p75_decay_off` | baseline_no_momentum_decay_pass | 11.27% | -30.37% | N/A | N/A | 4.63% | -30.11% | 2.04% | -30.11% | -18.18% | -26.92% | 0.00 | 0 | 0.00% | baseline/no momentum decay |

## Best Decay Candidates

| Candidate | Role | Full Ann. | Full MDD | Full Ann Delta pp | Full MDD Improve pp | DD Improve Windows | Trigger Full | Decay Days Full | Pass | Reason |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| `lb_28_r2_none_buf_1p15_entry_0p75_decay_0p65_rec_0p85_c1_scale_0p50` | return_watch_line_r2_removed | 6.91% | -27.76% | -4.35 | 2.60 | 4 | 110 | 27.14% | False | full_mdd=True;dd_windows=4;return_tol=False;material=True |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_0p65_rec_0p85_c1_scale_0p50` | main_line_r2_removed | 6.37% | -27.23% | -4.26 | 2.25 | 4 | 110 | 27.14% | False | full_mdd=True;dd_windows=4;return_tol=False;material=True |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_0p65_rec_0p95_c1_scale_0p50` | main_line_r2_removed | 6.10% | -27.23% | -4.53 | 2.25 | 4 | 109 | 27.63% | False | full_mdd=True;dd_windows=4;return_tol=False;material=True |
| `lb_28_r2_none_buf_1p15_entry_0p75_decay_0p65_rec_0p95_c1_scale_0p50` | return_watch_line_r2_removed | 6.64% | -28.23% | -4.63 | 2.13 | 4 | 109 | 27.63% | False | full_mdd=True;dd_windows=4;return_tol=False;material=True |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_0p65_rec_0p85_c3_scale_0p50` | main_line_r2_removed | 8.02% | -27.39% | -2.61 | 2.09 | 2 | 73 | 18.75% | False | full_mdd=True;dd_windows=2;return_tol=False;material=True |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_0p65_rec_0p95_c3_scale_0p50` | main_line_r2_removed | 7.93% | -27.39% | -2.70 | 2.09 | 2 | 72 | 19.20% | False | full_mdd=True;dd_windows=2;return_tol=False;material=True |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_0p65_rec_0p95_c3_scale_0p75` | main_line_r2_removed | 9.31% | -27.44% | -1.32 | 2.04 | 2 | 72 | 19.20% | False | full_mdd=True;dd_windows=2;return_tol=False;material=True |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_0p65_rec_0p85_c3_scale_0p75` | main_line_r2_removed | 9.35% | -27.44% | -1.28 | 2.04 | 2 | 73 | 18.75% | False | full_mdd=True;dd_windows=2;return_tol=False;material=True |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_0p75_rec_0p85_c3_scale_0p75` | main_line_r2_removed | 8.45% | -27.50% | -2.18 | 1.98 | 2 | 88 | 22.94% | False | full_mdd=True;dd_windows=2;return_tol=False;material=True |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_0p75_rec_0p95_c3_scale_0p75` | main_line_r2_removed | 8.33% | -27.50% | -2.30 | 1.98 | 2 | 87 | 23.52% | False | full_mdd=True;dd_windows=2;return_tol=False;material=True |
| `lb_28_r2_none_buf_1p15_entry_0p75_decay_0p65_rec_0p85_c3_scale_0p00` | return_watch_line_r2_removed | 5.78% | -28.61% | -5.49 | 1.76 | 4 | 73 | 18.75% | False | full_mdd=True;dd_windows=4;return_tol=False;material=True |
| `lb_28_r2_none_buf_1p15_entry_0p75_decay_0p65_rec_0p95_c3_scale_0p00` | return_watch_line_r2_removed | 5.60% | -28.61% | -5.67 | 1.76 | 4 | 72 | 19.20% | False | full_mdd=True;dd_windows=4;return_tol=False;material=True |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_0p65_rec_0p95_c1_scale_0p75` | main_line_r2_removed | 8.39% | -27.76% | -2.24 | 1.72 | 4 | 109 | 27.63% | False | full_mdd=True;dd_windows=4;return_tol=False;material=True |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_0p65_rec_0p85_c1_scale_0p75` | main_line_r2_removed | 8.53% | -27.76% | -2.10 | 1.72 | 4 | 110 | 27.14% | False | full_mdd=True;dd_windows=4;return_tol=False;material=True |

## Comparison List

| Candidate | Type | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_off` | line_baseline_no_momentum_decay | 10.63% | -29.48% | N/A | N/A | 5.49% | -26.22% | 5.72% | -26.22% | -11.11% | -21.36% | Same carried line before momentum-decay layer |
| `lb_28_r2_none_buf_1p15_entry_0p75_decay_off` | line_baseline_no_momentum_decay | 11.27% | -30.37% | N/A | N/A | 4.63% | -30.11% | 2.04% | -30.11% | -18.18% | -26.92% | Same carried line before momentum-decay layer |
| `lb_28_r2_none_buf_1p15_entry_0p25_decay_off` | baseline_no_momentum_decay_pass | 10.63% | -29.48% | N/A | N/A | 5.49% | -26.22% | 5.72% | -26.22% | -11.11% | -21.36% | Line-level selected momentum-decay result |
| `lb_28_r2_none_buf_1p15_entry_0p75_decay_off` | baseline_no_momentum_decay_pass | 11.27% | -30.37% | N/A | N/A | 4.63% | -30.11% | 2.04% | -30.11% | -18.18% | -26.92% | Line-level selected momentum-decay result |
| `orig_full_v1_1_reference` | original_full_v1_1_reference | 11.84% | -36.96% | N/A | N/A | 12.61% | -36.96% | 3.41% | -36.96% | -26.98% | -36.96% | Full official V1.1 chain on this proxy panel; includes original lookback 25, R2 0.20, switch buffer 1.05, staged entry 0.50, target-vol 25%, and later overlays. |

## Stability Classification

- Decision: `line_level_selection_after_momentum_decay_on_r2_removed_branch`.
- Stability label: `momentum_decay_pass_if_line_selection_uses_overlay_else_keep_previous`.
- 10Y remains N/A by sample length: 2432 sessions is less than 2520 trading days.

## Decision

- Keep each line's selected row from `line_selection.csv`.
- Stop here before NAV defense.

## Source Audit

| code          | name                            | source                                  | adjustment                | first_available   | first_used   | last       |   rows | pool_rule                                                  | last_aligned   |   ffill_days_on_cn_calendar |
|:--------------|:--------------------------------|:----------------------------------------|:--------------------------|:------------------|:-------------|:-----------|-------:|:-----------------------------------------------------------|:---------------|----------------------------:|
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY      | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWG           | GERMANY_EWG_ADJ_CLOSE_PROXY     | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWJ           | JAPAN_EWJ_ADJ_CLOSE_PROXY       | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY        | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_ADD | Eastmoney push2his kline secid=0.399006 | index close / price index | 2010-06-01        | 2010-06-01   | 2016-12-30 |   1601 | dynamic asset; no prices before 2010-06-01 and no backfill | 2016-12-30     |                           0 |

## Finalization

- Finalized at: 2026-07-02T00:01:45+08:00
- Decision: do_not_add_momentum_decay_keep_layer5_two_lines
- Stability label: no_momentum_decay_pass_keep_previous_two_lines
- Complete checker: PASS
