# Sub-D Dynamic ChiNext Proxy Layer 4 Staged-Entry Scan

## Run Metadata

- Run folder: `quant_param_scan_runs\20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_staged_entry_layer4_initial_entry_fraction`
- Layer: `Layer 4`
- Strategy: dynamic ChiNext proxy pool, 2007-2016.
- Entrypoint: `run_subd_proxy_dynamic_cyb_layer4_staged_entry_scan.py`

## Research Question

Add staged entry after the Layer 3 carried line. The strategy enters a new asset with the configured initial fraction and fills to 100% on a later down day if the signal remains unchanged.

## Implementation Anchor

- Data loader reused from `run_subd_proxy_dynamic_cyb_layer0.py`.
- Staged-entry behavior reuses `EntryCase` and `run_staged_entry` from `run_subd_six_etf_v1_1.py`.
- No target-vol or overheat in this layer.

## Data Snapshot

- Start/end: `2007-01-04` to `2016-12-30`.
- Rows: `2432`.
- Pool: QQQ/EWG/EWJ/GLD from 2007 start; ChiNext joins when its own data exists.

## Cost and Execution Assumptions

- One-way cost: `0.001`.
- Calendar: A-share trading days; US adjusted closes are forward-filled onto that calendar for this proxy diagnostic.
- Trades involving a forward-filled trade leg are blocked for that day.

## Runtime Override Plan

- Lines carried: `[(28, 0.5, 1.0, 'layer3_primary'), (28, 0.4, 1.0, 'r2_neighbor'), (32, 0.5, 1.0, 'return_peak_watch'), (25, 0.2, 1.05, 'original_layer4')]`.
- Entry-fraction grid: `['full', '0p75', '0p67', '0p50', '0p33', '0p25']`.
- Baseline: same `lookback + R2 + switch buffer` with `full_entry`.
- Pass rule: Full maxDD improves by more than `0.01pp`; at least 3 of the 4 available windows improve maxDD by more than `0.01pp`; Full/5Y annualized return lag <=1pp and 3Y/1Y lag <=3pp versus same-line full-entry baseline.

## Commands

- `python run_subd_proxy_dynamic_cyb_layer4_staged_entry_scan.py --start-date 2007-01-01 --end-date 2016-12-30 --run-folder quant_param_scan_runs\20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_staged_entry_layer4_initial_entry_fraction`

## Output Files

- `scan_summary.csv`
- `window_metrics.csv`
- `comparison_list.csv`
- `daily_outputs/staged_entry_daily_curves.csv`
- `sources.csv`

## Primary Line Results

| Candidate | Full Ann. | Full MDD | Full Ann Delta pp | Full MDD Improve pp | 5Y Ann. | 3Y Ann. | 1Y Ann. | Partial Days Full | Staged Fills Full | Pass | Reason |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| lb_28_r2_0p50_buf_1p00_entry_full | 10.09% | -26.30% | 0.00 | 0.00 | 10.39% | 7.13% | 0.01% | 0 | 0 | False | baseline/full entry |
| lb_28_r2_0p50_buf_1p00_entry_0p75 | 9.14% | -23.10% | -0.95 | 3.20 | 9.57% | 7.43% | 1.84% | 393 | 151 | True | pass |
| lb_28_r2_0p50_buf_1p00_entry_0p67 | 8.83% | -22.52% | -1.26 | 3.79 | 9.30% | 7.52% | 2.42% | 393 | 151 | False | full_mdd=True;dd_windows=4;return_tol=False |
| lb_28_r2_0p50_buf_1p00_entry_0p50 | 8.14% | -21.28% | -1.95 | 5.03 | 8.71% | 7.69% | 3.69% | 393 | 151 | False | full_mdd=True;dd_windows=4;return_tol=False |
| lb_28_r2_0p50_buf_1p00_entry_0p33 | 7.44% | -20.13% | -2.65 | 6.17 | 8.10% | 7.83% | 4.96% | 393 | 151 | False | full_mdd=True;dd_windows=4;return_tol=False |
| lb_28_r2_0p50_buf_1p00_entry_0p25 | 7.10% | -19.69% | -2.99 | 6.62 | 7.80% | 7.89% | 5.56% | 393 | 151 | False | full_mdd=True;dd_windows=4;return_tol=False |

## Passing Or Best Candidates

| Candidate | Role | Full Ann. | Full MDD | Full MDD Improve pp | DD Improve Windows | Pass |
|---|---|---:|---:|---:|---:|---|
| lb_28_r2_0p50_buf_1p00_entry_0p75 | layer3_primary | 9.14% | -23.10% | 3.20 | 4 | True |
| lb_25_r2_0p20_buf_1p05_entry_0p75 | original_layer4 | 8.89% | -31.42% | 3.13 | 4 | True |
| lb_28_r2_0p40_buf_1p00_entry_0p75 | r2_neighbor | 8.39% | -28.53% | 2.83 | 4 | True |
| lb_28_r2_0p40_buf_1p00_entry_0p67 | r2_neighbor | 8.22% | -27.76% | 3.60 | 4 | True |

## Comparison List

| Candidate | Type | Full Ann. | Full MDD | 5Y Ann. | 3Y Ann. | 1Y Ann. | Notes |
|---|---|---:|---:|---:|---:|---:|---|
| lb_28_r2_0p50_buf_1p00_entry_full | layer3_carried_baseline | 10.09% | -26.30% | 10.39% | 7.13% | 0.01% | Layer3 carried primary line before staged entry |
| lb_28_r2_0p50_buf_1p00_entry_0p50 | layer4_primary_original_entry_fraction | 8.14% | -21.28% | 8.71% | 7.69% | 3.69% | Layer3 primary with original initial entry fraction 0.50 |
| lb_28_r2_0p50_buf_1p00_entry_0p75 | layer4_selected | 9.14% | -23.10% | 9.57% | 7.43% | 1.84% | Selected Layer4 line under the documented pass rule |
| lb_28_r2_0p40_buf_1p00_entry_0p50 | r2_neighbor_original_entry_fraction | 7.84% | -26.44% | 8.70% | 7.91% | -2.78% | R2 neighbor with original initial entry fraction 0.50 |
| lb_32_r2_0p50_buf_1p00_entry_0p50 | return_peak_watch_original_entry_fraction | 8.98% | -20.05% | 8.03% | 7.04% | -5.05% | Return peak watch line with original initial entry fraction 0.50 |
| orig_layer4_lb25_r2_0p20_buf_1p05_entry_0p50 | original_layer4_staged_entry | 8.03% | -28.16% | 8.27% | 3.26% | -17.99% | Original first-layer parameter plus original R2 0.20, switch buffer 1.05, and initial entry fraction 0.50 |
| orig_full_v1_1_reference | original_full_strategy_reference | 11.84% | -36.96% | 12.61% | 3.41% | -26.98% | Full official V1.1 chain; reference only, not Layer4 pass baseline |

## Stability Classification

- Selected candidate: `lb_28_r2_0p50_buf_1p00_entry_0p75`.
- Decision: `carry_forward_primary_staged_entry_pass`.
- Stability label: `primary_pass`.
- 10Y remains N/A by sample length and is not fabricated for strict scanner compatibility.

## Decision

- Decision: `carry_forward_primary_staged_entry_pass`.
- Stop here before any target-vol or overheat layer.

## User-Facing Summary

Layer 4 selected `lb_28_r2_0p50_buf_1p00_entry_0p75` under the documented pass rule. See `window_metrics.csv` for all staged-entry lines.

## Source Audit

| code          | name                            | source                                  | adjustment                | first_available   | first_used   | last       |   rows | pool_rule                                                  | last_aligned   |   ffill_days_on_cn_calendar |
|:--------------|:--------------------------------|:----------------------------------------|:--------------------------|:------------------|:-------------|:-----------|-------:|:-----------------------------------------------------------|:---------------|----------------------------:|
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY      | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWG           | GERMANY_EWG_ADJ_CLOSE_PROXY     | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWJ           | JAPAN_EWJ_ADJ_CLOSE_PROXY       | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY        | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_ADD | Eastmoney push2his kline secid=0.399006 | index close / price index | 2010-06-01        | 2010-06-01   | 2016-12-30 |   1601 | dynamic asset; no prices before 2010-06-01 and no backfill | 2016-12-30     |                           0 |

## Finalization

- Finalized at: 2026-07-01T20:28:29+08:00
- Decision: carry_forward_lb28_r2_0p50_buf_1p00_entry_0p75
- Stability label: primary_pass_entry_0p75_neighbor_tradeoff
- Complete checker: PASS
