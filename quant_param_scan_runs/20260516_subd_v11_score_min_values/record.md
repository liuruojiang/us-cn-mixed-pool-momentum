# Sub-D V1.1 Score-Min Lower-Bound Scan

## Decision

- Decision: research only; no source change made by this scan.
- Tested uniform score lower bound values under official caps and the previously recommended cap map.

## Data

- Common last date: 2026-05-15
- Source: `akshare.fund_etf_hist_sina` raw close.
- Adjustment: raw/unadjusted as served by Sina.
- Baseline parity NAV absolute difference versus official path: 0.0

## Cost And Execution

- One-way cost: 0.1000%
- R2 threshold: 0.20
- Switch buffer: 1.05
- Target volatility: 25%, vol window 80, max leverage 1.5.
- Overheat: MA60 bias enter 20%, exit 18%, derisk scale 0.

## From-2020 Results

| candidate                    | cap_family       |   score_min |   ann_return |    max_dd |   sharpe_repo |   trades |   cash_days |
|:-----------------------------|:-----------------|------------:|-------------:|----------:|--------------:|---------:|------------:|
| official_caps_min_0          | official_caps    |        0    |     0.59322  | -0.180541 |       1.90956 |     1274 |         113 |
| official_caps_min_neg0p25    | official_caps    |       -0.25 |     0.583951 | -0.187156 |       1.88658 |     1298 |          94 |
| official_caps_min_neg0p5     | official_caps    |       -0.5  |     0.53251  | -0.241488 |       1.7547  |     1368 |          44 |
| official_caps_min_neg1       | official_caps    |       -1    |     0.50655  | -0.276401 |       1.68823 |     1396 |           2 |
| official_caps_min_neg2       | official_caps    |       -2    |     0.50655  | -0.276401 |       1.68823 |     1396 |           2 |
| official_caps_min_neg_inf    | official_caps    |     -inf    |     0.50655  | -0.276401 |       1.68823 |     1396 |           2 |
| recommended_caps_min_0       | recommended_caps |        0    |     0.617641 | -0.180541 |       2.04117 |     1248 |         105 |
| recommended_caps_min_neg0p25 | recommended_caps |       -0.25 |     0.611825 | -0.187156 |       2.02564 |     1269 |          93 |
| recommended_caps_min_neg0p5  | recommended_caps |       -0.5  |     0.56049  | -0.241488 |       1.88952 |     1337 |          43 |
| recommended_caps_min_neg1    | recommended_caps |       -1    |     0.534234 | -0.276401 |       1.8193  |     1365 |           1 |
| recommended_caps_min_neg2    | recommended_caps |       -2    |     0.534234 | -0.276401 |       1.8193  |     1365 |           1 |
| recommended_caps_min_neg_inf | recommended_caps |     -inf    |     0.534234 | -0.276401 |       1.8193  |     1365 |           1 |

## Stability

- Label: negative_score_min_worse_than_zero.
- Evidence: see `scan_summary.csv` and `window_metrics.csv`.

## Finalization

- Finalized at: 2026-05-16T11:06:15+08:00
- Decision: Keep score_min at 0. Negative lower bounds reduce cash days but worsen return, drawdown, and Sharpe under both official caps and the recommended cap map.
- Stability label: negative_score_min_worse_than_zero
- Complete checker: PASS
