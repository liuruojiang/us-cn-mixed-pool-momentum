# Quant Parameter Scan Record

## Run Metadata

- Run id: `20260618_subd_v11_same_slice_ablation`
- Created/updated at: 2026-06-18T22:14:12+08:00
- Project: SubD six ETF
- Strategy or version: V1.1 ablation chain
- Sleeve or subsystem: ablation_chain
- Parameter group: `same_slice_ablation`
- Scan type: `ablation_chain`
- Repo or workspace path: `D:\动量策略\美股A股混合池子动量策略`
- Target entrypoint: `quant_param_scan_runs\20260618_subd_v11_same_slice_ablation\run_scan.py`
- Git branch: `main`
- Git commit: `3c83a03ee62b45371f79836d4a0ac56db0f701c6`

## Research Question

- Compare the V1.1 component chain on one identical data slice: score gate, R2, switch buffer, staged entry, target-vol, and overheat.
- Source-change rule: `research_only_no_source_change`
- Required windows: full, 10Y, 5Y, 3Y, 1Y
- Required metrics: annual return, annualized volatility, Sharpe, max drawdown, exposure, turnover, and cost.

## Data Snapshot

- Primary source: `akshare.fund_etf_hist_sina` daily close.
- Adjustment policy: `sina_raw_split_continuity_159941_pre_20220705_x0.25`.
- Evaluation start: `2020-01-02`.
- Evaluation end: `2026-06-17`.
- Independent check: Yahoo Finance chart adjusted close, recent closes only; Yahoo is not used for returns.
- Caveat: this is not qfq parity. It is a single-source split-continuity research slice because QVeris and Eastmoney qfq are unavailable in this environment.

## Sources

| code      | name        | source                     | adjustment                                          | first      | last       |   rows |
|:----------|:------------|:---------------------------|:----------------------------------------------------|:-----------|:-----------|-------:|
| 159915.SZ | CYB100_ETF  | akshare.fund_etf_hist_sina | sina_raw_unadjusted_no_detected_split_patch         | 2011-12-09 | 2026-06-17 |   3523 |
| 159941.SZ | NASDAQ_ETF  | akshare.fund_etf_hist_sina | sina_raw_split_continuity_159941_pre_20220705_x0.25 | 2015-07-13 | 2026-06-17 |   2655 |
| 513030.SH | GERMANY_ETF | akshare.fund_etf_hist_sina | sina_raw_unadjusted_no_detected_split_patch         | 2014-09-05 | 2026-06-17 |   2859 |
| 513520.SH | NIKKEI_ETF  | akshare.fund_etf_hist_sina | sina_raw_unadjusted_no_detected_split_patch         | 2019-06-25 | 2026-06-17 |   1693 |
| 159985.SZ | SOYMEAL_ETF | akshare.fund_etf_hist_sina | sina_raw_unadjusted_no_detected_split_patch         | 2019-12-05 | 2026-06-17 |   1582 |
| 518880.SH | GOLD_ETF    | akshare.fund_etf_hist_sina | sina_raw_unadjusted_no_detected_split_patch         | 2013-07-29 | 2026-06-17 |   3132 |

## Source Validation

| code      | independent_source                 | validation_status   |   primary_rows |   independent_rows | primary_first   | primary_last   | independent_first   | independent_last   |   common_rows |   recent_common_rows | last_common_date   |   last_common_close_diff_pct |   max_abs_recent_close_diff_pct | note                                                                     |
|:----------|:-----------------------------------|:--------------------|---------------:|-------------------:|:----------------|:---------------|:--------------------|:-------------------|--------------:|---------------------:|:-------------------|-----------------------------:|--------------------------------:|:-------------------------------------------------------------------------|
| 159915.SZ | Yahoo Finance chart adjusted close | ok                  |           1580 |               3536 | 2019-12-05      | 2026-06-17     | 2011-09-20          | 2026-06-17         |          1579 |                   78 | 2026-06-17         |                 -2.09749e-08 |                     5.73709e-08 |                                                                          |
| 159941.SZ | Yahoo Finance chart adjusted close | ok                  |           1580 |               2662 | 2019-12-05      | 2026-06-17     | 2015-06-10          | 2026-06-17         |          1580 |                   78 | 2026-06-17         |                  2.6959e-08  |                     4.41912e-08 | Yahoo has a known 159941 split-point glitch; it is not used for returns. |
| 513030.SH | Yahoo Finance chart adjusted close | ok                  |           1580 |               2863 | 2019-12-05      | 2026-06-17     | 2014-08-08          | 2026-06-17         |          1580 |                   78 | 2026-06-17         |                  6.93387e-09 |                     3.31812e-08 |                                                                          |
| 513520.SH | Yahoo Finance chart adjusted close | ok                  |           1580 |               1696 | 2019-12-05      | 2026-06-17     | 2019-06-12          | 2026-06-17         |          1579 |                   78 | 2026-06-17         |                 -4.49883e-08 |                     5.57649e-08 |                                                                          |
| 159985.SZ | Yahoo Finance chart adjusted close | ok                  |           1580 |               1593 | 2019-12-05      | 2026-06-17     | 2019-09-24          | 2026-06-17         |          1579 |                   78 | 2026-06-17         |                 -5.73709e-08 |                     5.76575e-08 |                                                                          |
| 518880.SH | Yahoo Finance chart adjusted close | ok                  |           1580 |               3133 | 2019-12-05      | 2026-06-17     | 2013-07-18          | 2026-06-17         |          1579 |                   78 | 2026-06-17         |                  2.47016e-08 |                     5.11257e-08 |                                                                          |

## Cost and Execution Assumptions

- One-way cost: `0.0010`.
- Rebalance/fill timing: close-to-close, same as existing V1.1 research harness.
- Target-vol: `0.25`, vol window `80`, max leverage `1.5`.
- Overheat: enter `0.20`, exit `0.18`, derisk scale `0.0`.

## Full-Sample Results

| candidate                | ann_return   | max_dd   |   sharpe_repo | avg_effective_exposure   |   turnover_sum | cost_total   |   trades |
|:-------------------------|:-------------|:---------|--------------:|:-------------------------|---------------:|:-------------|---------:|
| 01_score_gate_full_entry | 55.57%       | -21.56%  |          1.78 | 97.25%                   |         403    | 40.30%       |      207 |
| 02_add_r2_full_entry     | 56.86%       | -21.97%  |          1.85 | 92.76%                   |         393    | 39.30%       |      217 |
| 03_add_switch_buffer     | 58.06%       | -23.45%  |          1.88 | 92.76%                   |         383    | 38.30%       |      212 |
| 04_add_staged_entry      | 50.58%       | -18.13%  |          1.92 | 81.33%                   |         346    | 34.60%       |      367 |
| 05_add_target_vol        | 61.43%       | -20.90%  |          1.93 | 96.30%                   |         406.57 | 40.66%       |     1424 |
| 06_full_v11_add_overheat | 66.90%       | -17.50%  |          2.09 | 94.65%                   |         414.75 | 41.47%       |     1413 |

## Window Results

| candidate                | ann_return_full   | max_dd_full   | ann_return_last_10y   | max_dd_last_10y   | ann_return_last_5y   | max_dd_last_5y   | ann_return_last_3y   | max_dd_last_3y   | ann_return_last_1y   | max_dd_last_1y   |
|:-------------------------|:------------------|:--------------|:----------------------|:------------------|:---------------------|:-----------------|:---------------------|:-----------------|:---------------------|:-----------------|
| 01_score_gate_full_entry | 55.57%            | -21.56%       | 55.57%                | -21.56%           | 53.75%               | -21.56%          | 71.76%               | -17.18%          | 73.94%               | -17.18%          |
| 02_add_r2_full_entry     | 56.86%            | -21.97%       | 56.86%                | -21.97%           | 58.96%               | -21.97%          | 79.52%               | -15.84%          | 99.41%               | -15.84%          |
| 03_add_switch_buffer     | 58.06%            | -23.45%       | 58.06%                | -23.45%           | 60.17%               | -23.45%          | 82.23%               | -15.56%          | 100.47%              | -15.56%          |
| 04_add_staged_entry      | 50.58%            | -18.13%       | 50.58%                | -18.13%           | 55.91%               | -18.13%          | 69.81%               | -11.87%          | 88.03%               | -11.87%          |
| 05_add_target_vol        | 61.43%            | -20.90%       | 61.43%                | -20.90%           | 71.70%               | -20.90%          | 86.75%               | -16.30%          | 118.76%              | -12.86%          |
| 06_full_v11_add_overheat | 66.90%            | -17.50%       | 66.90%                | -17.50%           | 79.24%               | -17.50%          | 98.83%               | -16.30%          | 136.49%              | -12.86%          |

## Stability Classification

- Label: `same_slice_directional_only_non_qfq`
- Evidence: all candidates share the same primary source, common trading calendar, cost model, and execution timing.
- Data sensitivity: source is not qfq parity; repeat on restored qfq data before production promotion.
- Recent-window behavior: full V1.1 remains strongest on full, 5Y, 3Y, and 1Y windows in this slice.

## Decision

- Decision: `research_only_no_promotion`
- Recommended next action: rerun the same ablation on a restored qfq source before any live-trading parameter change.

## Finalization

- Finalized at: 2026-06-18T22:14:38+08:00
- Decision: research_only_no_promotion
- Stability label: same_slice_directional_only_non_qfq
- Complete checker: PASS
