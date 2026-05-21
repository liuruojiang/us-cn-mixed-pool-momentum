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

| candidate                 | cap_family       |   score_min |   ann_return |     max_dd |   sharpe_repo |   trades |   cash_days |
|:--------------------------|:-----------------|------------:|-------------:|-----------:|--------------:|---------:|------------:|
| official_caps_min_4       | official_caps    |        4    |    0.0412809 | -0.0869552 |      0.567358 |      131 |        1434 |
| official_caps_min_3       | official_caps    |        3    |    0.115818  | -0.181527  |      0.789423 |      189 |        1286 |
| official_caps_min_2       | official_caps    |        2    |    0.214417  | -0.175407  |      1.05184  |      330 |        1045 |
| official_caps_min_1p5     | official_caps    |        1.5  |    0.251937  | -0.184896  |      1.09085  |      531 |         826 |
| official_caps_min_1       | official_caps    |        1    |    0.352059  | -0.178519  |      1.3294   |      775 |         541 |
| official_caps_min_0p75    | official_caps    |        0.75 |    0.475619  | -0.202695  |      1.63106  |      973 |         387 |
| official_caps_min_0p5     | official_caps    |        0.5  |    0.571252  | -0.184401  |      1.86907  |     1147 |         231 |
| official_caps_min_0p3     | official_caps    |        0.3  |    0.575377  | -0.186063  |      1.87185  |     1234 |         148 |
| official_caps_min_0p2     | official_caps    |        0.2  |    0.596416  | -0.182294  |      1.91787  |     1267 |         123 |
| official_caps_min_0p1     | official_caps    |        0.1  |    0.59322   | -0.180541  |      1.90956  |     1274 |         113 |
| official_caps_min_0       | official_caps    |        0    |    0.59322   | -0.180541  |      1.90956  |     1274 |         113 |
| recommended_caps_min_5    | recommended_caps |        5    |    0.0423745 | -0.0882046 |      0.541289 |       41 |        1434 |
| recommended_caps_min_4    | recommended_caps |        4    |    0.100429  | -0.106743  |      0.872023 |      129 |        1337 |
| recommended_caps_min_3    | recommended_caps |        3    |    0.201417  | -0.181527  |      1.13621  |      197 |        1198 |
| recommended_caps_min_2    | recommended_caps |        2    |    0.283681  | -0.175407  |      1.29849  |      384 |         965 |
| recommended_caps_min_1p5  | recommended_caps |        1.5  |    0.334123  | -0.171352  |      1.39719  |      565 |         770 |
| recommended_caps_min_1    | recommended_caps |        1    |    0.4199    | -0.170547  |      1.5601   |      816 |         503 |
| recommended_caps_min_0p75 | recommended_caps |        0.75 |    0.51493   | -0.193006  |      1.79379  |     1007 |         368 |
| recommended_caps_min_0p5  | recommended_caps |        0.5  |    0.594949  | -0.184401  |      1.99878  |     1124 |         222 |
| recommended_caps_min_0p3  | recommended_caps |        0.3  |    0.600926  | -0.186063  |      2.00598  |     1209 |         140 |
| recommended_caps_min_0p2  | recommended_caps |        0.2  |    0.621094  | -0.182294  |      2.05043  |     1241 |         115 |
| recommended_caps_min_0p1  | recommended_caps |        0.1  |    0.617641  | -0.180541  |      2.04117  |     1248 |         105 |
| recommended_caps_min_0    | recommended_caps |        0    |    0.617641  | -0.180541  |      2.04117  |     1248 |         105 |

## Stability

- Label: negative_score_min_worse_than_zero.
- Evidence: see `scan_summary.csv` and `window_metrics.csv`.

## Finalization

- Finalized at: 2026-05-16T11:18:38+08:00
- Decision: Research-only result: score_min=0.20 is the best broad 0-5 lower-bound candidate under both official caps and the recommended cap map, with only a small gain over 0 and slightly deeper drawdown; score_min above 0.30 quickly degrades returns and Sharpe.
- Stability label: score_min_0p2_small_improvement
- Complete checker: PASS
