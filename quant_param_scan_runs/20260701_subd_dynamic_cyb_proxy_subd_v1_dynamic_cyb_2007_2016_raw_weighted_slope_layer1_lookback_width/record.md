# Sub-D Dynamic ChiNext Proxy Layer 1 Lookback Width Scan

## Run Metadata

- Run folder: `quant_param_scan_runs\20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_raw_weighted_slope_layer1_lookback_width`
- Layer: `Layer 1`
- Strategy: dynamic ChiNext proxy pool, 2007-2016.
- Entrypoint: `run_subd_proxy_dynamic_cyb_layer1_scan.py`

## Research Question

Test the raw weighted-slope lookback width before adding R2, staged entry, target-vol, or overheat overlays.

## Implementation Anchor

- Data loader reused from `run_subd_proxy_dynamic_cyb_layer0.py`.
- Raw signal harness holds the highest positive weighted-slope score under `0 < score < 5`.
- No R2 filter, no switch buffer, no staged entry, no target-vol, no overheat.

## Data Snapshot

- Start/end: `2007-01-04` to `2016-12-30`.
- Rows: `2432`.
- Pool: QQQ/EWG/EWJ/GLD from 2007 start; ChiNext joins when its own data exists.

## Cost and Execution Assumptions

- One-way cost: `0.001`.
- Calendar: A-share trading days; US adjusted closes are forward-filled onto that calendar for this proxy diagnostic.
- Trades involving a forward-filled trade leg are blocked for that day.

## Runtime Override Plan

- Lookback grid: `[10, 15, 20, 22, 24, 25, 26, 28, 30, 32, 34, 35, 36, 38, 40, 42, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90]`.
- Width metric: `ann_return_full`.
- Layer 1 pass rule: immediate left and right neighbors must each retain at least 80% of selected line's full-sample annualized return.

## Commands

- `python run_subd_proxy_dynamic_cyb_layer1_scan.py --start-date 2007-01-01 --end-date 2016-12-30 --run-folder quant_param_scan_runs\20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_raw_weighted_slope_layer1_lookback_width`

## Output Files

- `scan_summary.csv`
- `window_metrics.csv`
- `ridge_width.csv`
- `daily_outputs/raw_signal_daily_curves.csv`
- `sources.csv`

## Full-Sample Results

| Lookback | Full Ann. | Full MaxDD | 5Y Ann. | 3Y Ann. | 1Y Ann. | Width Supported |
|---:|---:|---:|---:|---:|---:|---|
| 32 | 11.22% | -42.04% | 3.51% | -5.00% | -16.11% | False |
| 28 | 9.86% | -36.31% | 1.50% | -4.01% | -26.19% | True |
| 30 | 8.81% | -38.50% | 5.01% | -3.05% | -22.97% | True |
| 25 | 8.66% | -46.43% | 0.99% | -8.84% | -29.17% | False |
| 26 | 8.38% | -40.28% | 1.78% | -6.95% | -30.57% | True |
| 34 | 7.66% | -34.83% | 0.95% | -2.13% | -16.42% | False |
| 24 | 5.93% | -44.73% | 1.68% | -7.16% | -21.84% | False |
| 80 | 5.74% | -38.07% | 9.07% | -0.05% | -25.16% | False |

## Comparison List

| Candidate | Type | Full Ann. | Full MaxDD | 5Y Ann. | 3Y Ann. | 1Y Ann. | Notes |
|---|---|---:|---:|---:|---:|---:|---|
| orig_layer1_raw_lb25 | original_layer1_raw | 8.66% | -46.43% | 0.99% | -8.84% | -29.17% | Original first-layer raw momentum: weighted-slope lookback 25, score range 0..5, no R2/overlay |
| lb_28 | layer1_primary | 9.86% | -36.31% | 1.50% | -4.01% | -26.19% | Width-supported Layer1 raw-signal carry line |
| lb_26 | layer1_neighbor | 8.38% | -40.28% | 1.78% | -6.95% | -30.57% | Left confirmation neighbor for lb_28 |
| lb_30 | layer1_neighbor | 8.81% | -38.50% | 5.01% | -3.05% | -22.97% | Right confirmation neighbor for lb_28 |
| lb_32 | return_peak_watch | 11.22% | -42.04% | 3.51% | -5.00% | -16.11% | Full-sample return peak; fails 80% width rule |
| orig_full_v1_1_reference | original_full_strategy_reference | 11.84% | -36.96% | 12.61% | 3.41% | -26.98% | Full official V1.1 chain: lookback 25 + R2 0.20 + switch buffer 1.05 + staged entry + target-vol + overheat |

- `orig_layer1_raw_lb25` is the original first-layer raw momentum line and is the correct original comparator for Layer 1.
- `orig_full_v1_1_reference` uses the full official overlay chain; it is shown only as a strategy reference and is not used for Layer 1 width scoring.
- All rows have 10Y as `N/A` because this 2007-2016 sample has only 2432 A-share sessions, fewer than 2520.
## Window Results

- Recommended candidate: `lb_28`.
- Mandatory windows for recommended: Full `9.86%` / MDD `-36.31%`; 10Y `N/A`; 5Y `1.50%` / MDD `-36.31%`; 3Y `-4.01%` / MDD `-36.31%`; 1Y `-26.19%` / MDD `-33.22%`.

## Stability Classification

- Peak: `lb_32` with full annualized `11.22%`.
- Recommended: `lb_28` with left retention `0.850` and right retention `0.893`.
- Minimum full annualized return for a promotable width-supported line: `8.98%`.
- Best lower-return broad watch: `lb_28` with full annualized `9.86%`.
- Stability label: `width_supported`.

## Decision

- Decision: `carry_forward_width_supported`.
- Carry this Layer 1 primary line plus its immediate neighbors into Layer 2 R2 filter tests.
- Stop here before Layer 2 per standard process.

## User-Facing Summary

Layer 1 recommends `lookback=28` for the raw weighted-slope signal under the dynamic ChiNext proxy pool. The 10Y window remains N/A because 2007-2016 has fewer than 2520 A-share sessions.

## Source Audit

| code          | name                            | source                                  | adjustment                | first_available   | first_used   | last       |   rows | pool_rule                                                  | last_aligned   |   ffill_days_on_cn_calendar |
|:--------------|:--------------------------------|:----------------------------------------|:--------------------------|:------------------|:-------------|:-----------|-------:|:-----------------------------------------------------------|:---------------|----------------------------:|
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY      | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWG           | GERMANY_EWG_ADJ_CLOSE_PROXY     | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWJ           | JAPAN_EWJ_ADJ_CLOSE_PROXY       | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY        | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_ADD | Eastmoney push2his kline secid=0.399006 | index close / price index | 2010-06-01        | 2010-06-01   | 2016-12-30 |   1601 | dynamic asset; no prices before 2010-06-01 and no backfill | 2016-12-30     |                           0 |

## Finalization

- Finalized at: 2026-07-01T19:07:28+08:00
- Decision: carry_forward_width_supported_lb28
- Stability label: width_supported_10y_na_by_sample
- Complete checker: PASS
