# Sub-D Dynamic ChiNext Proxy Layer 2 R2 Signal-Quality Scan

## Run Metadata

- Run folder: `quant_param_scan_runs\20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_r2_signal_quality_layer2_r2_threshold`
- Layer: `Layer 2`
- Strategy: dynamic ChiNext proxy pool, 2007-2016.
- Entrypoint: `run_subd_proxy_dynamic_cyb_layer2_r2_scan.py`

## Research Question

Add an R2 signal-quality threshold to Layer 1 carried raw momentum lines and compare each candidate to its same-lookback no-R2 baseline.

## Implementation Anchor

- Data loader reused from `run_subd_proxy_dynamic_cyb_layer0.py`.
- Score formula and stale-price trade guard match Layer 1.
- No switch buffer, staged entry, target-vol, or overheat in this layer.

## Data Snapshot

- Start/end: `2007-01-04` to `2016-12-30`.
- Rows: `2432`.
- Pool: QQQ/EWG/EWJ/GLD from 2007 start; ChiNext joins when its own data exists.

## Cost and Execution Assumptions

- One-way cost: `0.001`.
- Calendar: A-share trading days; US adjusted closes are forward-filled onto that calendar for this proxy diagnostic.
- Trades involving a forward-filled trade leg are blocked for that day.

## Runtime Override Plan

- Lookbacks carried: `[25, 26, 28, 30, 32]`.
- R2 grid: `['none', '0p10', '0p15', '0p20', '0p25', '0p30', '0p35', '0p40', '0p50', '0p60']`.
- Pass rule: Full maxDD improves; at least 3 of the 4 available windows improve maxDD; Full/5Y annualized return lag <=1pp and 3Y/1Y lag <=3pp versus same-lookback no-R2 baseline.

## Commands

- `python run_subd_proxy_dynamic_cyb_layer2_r2_scan.py --start-date 2007-01-01 --end-date 2016-12-30 --run-folder quant_param_scan_runs\20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_r2_signal_quality_layer2_r2_threshold`

## Output Files

- `scan_summary.csv`
- `window_metrics.csv`
- `comparison_list.csv`
- `daily_outputs/r2_signal_daily_curves.csv`
- `sources.csv`

## Primary Lookback Results

| Candidate | Full Ann. | Full MDD | Full Ann Delta pp | Full MDD Improve pp | 5Y Ann. | 3Y Ann. | 1Y Ann. | Pass | Reason |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| lb_28_r2_0p50 | 10.09% | -26.30% | 0.24 | 10.01 | 10.39% | 7.13% | 0.01% | True | pass |
| lb_28_r2_0p10 | 9.23% | -31.79% | -0.63 | 4.52 | 3.38% | -2.78% | -22.89% | True | pass |
| lb_28_r2_0p40 | 8.86% | -31.35% | -0.99 | 4.96 | 8.78% | 4.88% | -12.16% | True | pass |
| lb_28_r2_0p15 | 8.42% | -34.61% | -1.44 | 1.70 | 2.62% | -5.17% | -22.44% | False | full_mdd=True;dd_windows=4;return_tol=False |
| lb_28_r2_0p35 | 8.34% | -32.66% | -1.52 | 3.65 | 9.81% | 6.49% | -5.30% | False | full_mdd=True;dd_windows=4;return_tol=False |
| lb_28_r2_0p25 | 8.03% | -29.33% | -1.82 | 6.98 | 6.44% | 1.36% | -17.35% | False | full_mdd=True;dd_windows=4;return_tol=False |
| lb_28_r2_0p30 | 7.24% | -37.46% | -2.62 | -1.15 | 7.67% | 2.87% | -12.00% | False | full_mdd=False;dd_windows=3;return_tol=False |
| lb_28_r2_0p20 | 6.01% | -28.67% | -3.85 | 7.64 | 3.08% | -1.51% | -15.75% | False | full_mdd=True;dd_windows=4;return_tol=False |
| lb_28_r2_0p60 | 2.83% | -38.66% | -7.02 | -2.35 | 1.90% | 2.43% | 10.23% | False | full_mdd=False;dd_windows=2;return_tol=False |

## Passing Or Best Candidates

| Candidate | Full Ann. | Full MDD | Full MDD Improve pp | DD Improve Windows | Pass |
|---|---:|---:|---:|---:|---|
| lb_32_r2_0p50 | 11.47% | -19.61% | 22.43 | 4 | True |
| lb_25_r2_0p30 | 11.42% | -30.71% | 15.72 | 4 | True |
| lb_25_r2_0p20 | 11.15% | -33.31% | 13.13 | 4 | True |
| lb_25_r2_0p25 | 10.86% | -35.31% | 11.13 | 4 | True |
| lb_25_r2_0p35 | 10.33% | -28.53% | 17.90 | 4 | True |
| lb_28_r2_0p50 | 10.09% | -26.30% | 10.01 | 4 | True |
| lb_25_r2_0p40 | 10.07% | -27.91% | 18.53 | 4 | True |
| lb_26_r2_0p40 | 9.26% | -28.56% | 11.71 | 4 | True |

## Comparison List

| Candidate | Type | Full Ann. | Full MDD | 5Y Ann. | 3Y Ann. | 1Y Ann. | Notes |
|---|---|---:|---:|---:|---:|---:|---|
| lb_28_r2_none | layer1_carried_baseline | 9.86% | -36.31% | 1.50% | -4.01% | -26.19% | Layer1 carried primary line before R2 |
| lb_28_r2_0p20 | layer2_primary_original_r2 | 6.01% | -28.67% | 3.08% | -1.51% | -15.75% | Layer1 primary with original R2 threshold 0.20 |
| lb_26_r2_0p20 | layer2_neighbor_original_r2 | 8.45% | -39.09% | 5.72% | -2.40% | -29.02% | Left confirmation line with R2 0.20 |
| lb_30_r2_0p20 | layer2_neighbor_original_r2 | 7.16% | -36.30% | 5.45% | -2.85% | -14.82% | Right confirmation line with R2 0.20 |
| lb_32_r2_0p20 | return_peak_watch_original_r2 | 7.68% | -28.60% | 6.82% | 3.29% | -7.84% | Return peak watch line with R2 0.20 |
| orig_layer2_lb25_r2_0p20 | original_layer2_r2 | 11.15% | -33.31% | 10.73% | 2.38% | -21.83% | Original first-layer parameter plus original R2 0.20 |
| orig_full_v1_1_reference | original_full_strategy_reference | 11.84% | -36.96% | 12.61% | 3.41% | -26.98% | Full official V1.1 chain; reference only, not Layer2 pass baseline |

## Stability Classification

- Selected candidate: `lb_28_r2_0p50`.
- Decision: `carry_forward_primary_r2_pass`.
- Stability label: `primary_pass`.
- 10Y remains N/A by sample length and is not fabricated for strict scanner compatibility.

## Decision

- Decision: `carry_forward_primary_r2_pass`.
- Stop here before any switch-buffer, staged-entry, target-vol, or overheat layer.

## User-Facing Summary

Layer 2 selected `lb_28_r2_0p50` under the documented pass rule. See `window_metrics.csv` for all thresholds.

## Source Audit

| code          | name                            | source                                  | adjustment                | first_available   | first_used   | last       |   rows | pool_rule                                                  | last_aligned   |   ffill_days_on_cn_calendar |
|:--------------|:--------------------------------|:----------------------------------------|:--------------------------|:------------------|:-------------|:-----------|-------:|:-----------------------------------------------------------|:---------------|----------------------------:|
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY      | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWG           | GERMANY_EWG_ADJ_CLOSE_PROXY     | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWJ           | JAPAN_EWJ_ADJ_CLOSE_PROXY       | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY        | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_ADD | Eastmoney push2his kline secid=0.399006 | index close / price index | 2010-06-01        | 2010-06-01   | 2016-12-30 |   1601 | dynamic asset; no prices before 2010-06-01 and no backfill | 2016-12-30     |                           0 |

## Finalization

- Finalized at: 2026-07-01T19:33:35+08:00
- Decision: carry_forward_lb28_r2_0p50
- Stability label: primary_pass_r2_0p50_width_supported_by_0p40
- Complete checker: PASS
