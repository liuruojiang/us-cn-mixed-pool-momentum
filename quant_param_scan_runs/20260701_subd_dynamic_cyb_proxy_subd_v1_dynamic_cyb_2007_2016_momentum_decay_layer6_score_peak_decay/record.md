# Sub-D Dynamic ChiNext Proxy Layer 6 Momentum Decay Scan

## Run Metadata

- Run folder: `quant_param_scan_runs\20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_momentum_decay_layer6_score_peak_decay`
- Layer: `Layer 6`
- Strategy: dynamic ChiNext proxy pool, 2007-2016.
- Entrypoint: `run_subd_proxy_dynamic_cyb_layer6_momentum_decay_scan.py`

## Research Question

Add score-peak momentum decay after the carried Layer 5 decision. Since target-vol failed Layer 5, this layer starts from the Layer 4 primary line with no target-vol.

## Implementation Anchor

- Data loader reused from `run_subd_proxy_dynamic_cyb_layer0.py`.
- Base staged-entry curves reuse Layer 4's `run_staged_line` helper.
- Momentum decay uses current target holding score divided by the active trade's score peak.
- After recovery, the same trade must set a new score peak before another decay cycle can trigger.
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

- Lines carried: `[(28, 0.5, 1.0, 0.75, 'layer5_carried_primary'), (28, 0.5, 1.0, 0.67, 'entry_neighbor'), (28, 0.4, 1.0, 0.75, 'r2_neighbor'), (32, 0.5, 1.0, 0.75, 'return_peak_watch'), (25, 0.2, 1.05, 0.5, 'original_layer6_same_stage')]`.
- Decay ratios: `[0.45, 0.55, 0.65, 0.75]`.
- Recovery ratios: `[0.85, 0.95]`.
- Confirm days: `[1, 3]`.
- Derisk scales: `[0.0, 0.5, 0.75]`.
- Baseline: same `lookback + R2 + switch buffer + entry fraction` with momentum decay disabled.
- Pass rule: Full maxDD improves by more than `0.01pp`; at least 3 of the 4 available windows improve maxDD by more than `0.01pp`; Full/5Y annualized return lag <=1pp and 3Y/1Y lag <=3pp versus same-line no-decay baseline.

## Commands

- `python run_subd_proxy_dynamic_cyb_layer6_momentum_decay_scan.py --start-date 2007-01-01 --end-date 2016-12-30 --run-folder quant_param_scan_runs\20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_momentum_decay_layer6_score_peak_decay`

## Output Files

- `scan_summary.csv`
- `window_metrics.csv`
- `comparison_list.csv`
- `daily_outputs/momentum_decay_daily_curves.csv`
- `sources.csv`

## Primary Line Results

| Candidate | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Full Ann Delta pp | Full MDD Improve pp | Trigger Full | Decay Days Full | Pass | Reason |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_off | 9.14% | -23.10% | N/A | N/A | 9.57% | -19.53% | 7.43% | -19.53% | 1.84% | -19.53% | 0.00 | 0.00 | 0 | 0.00% | False | baseline/no momentum decay |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c3_scale_0p75 | 9.11% | -22.53% | N/A | N/A | 9.25% | -18.40% | 7.47% | -18.40% | 3.25% | -18.40% | -0.04 | 0.57 | 16 | 3.33% | True | pass |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p95_c3_scale_0p75 | 9.10% | -22.53% | N/A | N/A | 9.23% | -18.40% | 7.59% | -18.40% | 3.25% | -18.40% | -0.05 | 0.57 | 16 | 3.41% | True | pass |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c3_scale_0p50 | 9.06% | -21.96% | N/A | N/A | 8.89% | -17.27% | 7.49% | -17.27% | 4.66% | -17.27% | -0.08 | 1.15 | 16 | 3.33% | True | pass |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p95_c3_scale_0p50 | 9.04% | -21.96% | N/A | N/A | 8.85% | -17.27% | 7.72% | -17.27% | 4.66% | -17.27% | -0.11 | 1.15 | 16 | 3.41% | True | pass |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p65_rec_0p85_c3_scale_0p75 | 8.82% | -22.58% | N/A | N/A | 9.22% | -18.00% | 7.41% | -18.00% | 4.09% | -18.00% | -0.32 | 0.53 | 24 | 4.98% | True | pass |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p65_rec_0p95_c3_scale_0p75 | 8.76% | -22.58% | N/A | N/A | 9.20% | -18.00% | 7.53% | -18.00% | 4.09% | -18.00% | -0.38 | 0.53 | 24 | 5.10% | True | pass |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p45_rec_0p85_c1_scale_0p75 | 8.67% | -22.74% | N/A | N/A | 8.83% | -18.40% | 7.43% | -18.40% | 3.58% | -18.40% | -0.47 | 0.36 | 21 | 2.55% | True | pass |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p45_rec_0p95_c1_scale_0p75 | 8.66% | -22.74% | N/A | N/A | 8.81% | -18.40% | 7.54% | -18.40% | 3.58% | -18.40% | -0.48 | 0.36 | 21 | 2.63% | True | pass |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p65_rec_0p85_c3_scale_0p50 | 8.47% | -22.05% | N/A | N/A | 8.83% | -16.46% | 7.37% | -16.46% | 6.36% | -16.46% | -0.67 | 1.05 | 24 | 4.98% | True | pass |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p65_rec_0p95_c3_scale_0p50 | 8.36% | -22.05% | N/A | N/A | 8.79% | -16.46% | 7.60% | -16.46% | 6.36% | -16.46% | -0.78 | 1.05 | 24 | 5.10% | True | pass |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p75_rec_0p85_c3_scale_0p75 | 8.34% | -23.00% | N/A | N/A | 8.64% | -17.85% | 6.90% | -17.85% | 4.17% | -17.85% | -0.81 | 0.10 | 34 | 7.24% | True | pass |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c3_scale_0p00 | 8.91% | -20.81% | N/A | N/A | 8.11% | -16.21% | 7.45% | -15.02% | 7.46% | -15.02% | -0.24 | 2.29 | 16 | 3.33% | False | full_mdd=True;dd_windows=4;return_tol=False;material=True |

## Passing Or Best Candidates

| Candidate | Role | Full Ann. | Full MDD | Full MDD Improve pp | DD Improve Windows | Trigger Full | Decay Days Full | Pass |
|---|---|---:|---:|---:|---:|---:|---:|---|
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c1_scale_0p75 | return_peak_watch | 10.19% | -18.15% | 1.20 | 4 | 41 | 5.10% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p95_c1_scale_0p75 | return_peak_watch | 10.19% | -18.15% | 1.20 | 4 | 41 | 5.10% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c1_scale_0p50 | return_peak_watch | 10.12% | -16.96% | 2.39 | 4 | 41 | 5.10% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p95_c1_scale_0p50 | return_peak_watch | 10.12% | -16.96% | 2.39 | 4 | 41 | 5.10% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c1_scale_0p00 | return_peak_watch | 9.92% | -14.67% | 4.68 | 4 | 41 | 5.10% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p95_c1_scale_0p00 | return_peak_watch | 9.92% | -14.67% | 4.68 | 4 | 41 | 5.10% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_0p75_rec_0p85_c3_scale_0p75 | return_peak_watch | 9.73% | -18.15% | 1.20 | 4 | 41 | 7.20% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_0p75_rec_0p95_c3_scale_0p75 | return_peak_watch | 9.72% | -18.15% | 1.20 | 4 | 41 | 8.10% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_0p65_rec_0p85_c1_scale_0p75 | return_peak_watch | 9.40% | -18.22% | 1.13 | 4 | 54 | 9.13% | True |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_0p65_rec_0p95_c1_scale_0p75 | return_peak_watch | 9.39% | -18.22% | 1.13 | 4 | 54 | 9.21% | True |

## Comparison List

| Candidate | Type | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_off | layer5_carried_baseline | 9.14% | -23.10% | N/A | N/A | 9.57% | -19.53% | 7.43% | -19.53% | 1.84% | -19.53% | Layer5 rejected target-vol, so this is the carried Layer4 primary line before momentum decay |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p95_c1_scale_0p00 | primary_55_95_cash_decay | 7.01% | -22.48% | N/A | N/A | 5.08% | -18.69% | 7.27% | -14.87% | 13.13% | -12.72% | Primary line with score-peak decay 55%, recovery 95%, one-day confirm, derisk to cash |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p95_c1_scale_0p50 | primary_55_95_half_decay | 8.13% | -22.78% | N/A | N/A | 7.38% | -17.63% | 7.41% | -16.16% | 7.39% | -16.16% | Primary line with score-peak decay 55%, recovery 95%, one-day confirm, derisk to 50% |
| lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c3_scale_0p75 | layer6_selected | 9.11% | -22.53% | N/A | N/A | 9.25% | -18.40% | 7.47% | -18.40% | 3.25% | -18.40% | Selected Layer6 line under the documented pass rule |
| lb_32_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p95_c1_scale_0p00 | return_peak_watch_decay | 9.92% | -14.67% | N/A | N/A | 9.11% | -14.67% | 8.60% | -14.67% | 0.02% | -14.67% | Return peak watch line with the same momentum-decay tuple |
| orig_layer6_lb25_r2_0p20_buf_1p05_entry_0p50_decay_off | original_layer6_same_stage_decay_off | 8.03% | -28.16% | N/A | N/A | 8.27% | -28.16% | 3.26% | -28.16% | -17.99% | -27.04% | Original first-layer parameter plus original R2 0.20, switch buffer 1.05, initial entry fraction 0.50; no momentum decay in this layer |
| orig_full_v1_1_reference | original_full_strategy_reference | 11.84% | -36.96% | N/A | N/A | 12.61% | -36.96% | 3.41% | -36.96% | -26.98% | -36.96% | Full official V1.1 chain including target-vol and overheat; context only, not Layer6 pass baseline |

## Stability Classification

- Selected candidate: `lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c3_scale_0p75`.
- Decision: `carry_forward_primary_momentum_decay_pass`.
- Stability label: `primary_pass`.
- Best non-primary pass: `lb_32_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c1_scale_0p75`.
- 10Y remains N/A by sample length: 2432 sessions is less than 2520 trading days.

## Decision

- Decision: `carry_forward_primary_momentum_decay_pass`.
- Stop here before NAV defense.

## User-Facing Summary

Layer 6 selected `lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c3_scale_0p75` under the documented pass rule. See `window_metrics.csv` for all score-peak decay lines.

## Source Audit

| code          | name                            | source                                  | adjustment                | first_available   | first_used   | last       |   rows | pool_rule                                                  | last_aligned   |   ffill_days_on_cn_calendar |
|:--------------|:--------------------------------|:----------------------------------------|:--------------------------|:------------------|:-------------|:-----------|-------:|:-----------------------------------------------------------|:---------------|----------------------------:|
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY      | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWG           | GERMANY_EWG_ADJ_CLOSE_PROXY     | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWJ           | JAPAN_EWJ_ADJ_CLOSE_PROXY       | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY        | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_ADD | Eastmoney push2his kline secid=0.399006 | index close / price index | 2010-06-01        | 2010-06-01   | 2016-12-30 |   1601 | dynamic asset; no prices before 2010-06-01 and no backfill | 2016-12-30     |                           0 |

## Finalization

- Finalized at: 2026-07-01T21:07:30+08:00
- Decision: carry_forward_primary_momentum_decay_pass
- Stability label: primary_pass
- Complete checker: PASS
