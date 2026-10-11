# V1.3 Rotation Pool Candidate Asset Sign Test

- Formal/proxy baseline to 2026-07-01: see `candidate_summary.csv`.
- A-share six-ETF diagnostic baseline to 2026-06-17: full annualized 17.04%, final NAV 19.1134.
- Method: add each candidate one at a time to QQQ + GLD + CN_CYB_399006; added assets join from first available date; V1.3 rules/cash/cost unchanged.
- CN six-ETF caveat: uses existing 2026-06-18 research fallback `akshare.fund_etf_hist_sina`; 159941 pre-split prices x0.25. This is diagnostic, not qfq formal evidence.

| Code | Pool type | Source group | Held sign | Held days | Held compound | Pool effect | Delta ann. | Full ann. | Full MDD | 10Y ann. | 5Y ann. | 3Y ann. | 1Y ann. |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| KMLM | added_to_baseline | Sub-B macro | positive | 260 | 28.23% | positive | 2.25% | 19.53% | -25.20% | 22.29% | 29.78% | 38.37% | 74.30% |
| BTC-USD | added_to_baseline | Sub-B IBIT proxy + US long custom | positive | 503 | 82.83% | positive | 1.88% | 19.16% | -32.37% | 17.04% | -0.39% | 7.84% | 17.53% |
| DBMF | added_to_baseline | Sub-B macro | negative | 226 | -0.35% | positive | 0.76% | 18.04% | -25.20% | 19.33% | 21.54% | 29.46% | 54.46% |
| SPY | added_to_baseline | US long custom | positive | 577 | 17.24% | positive | 0.36% | 17.65% | -24.92% | 19.78% | 22.47% | 26.48% | 53.89% |
| DBC | added_to_baseline | Sub-B + US long custom | positive | 869 | 39.04% | positive | 0.22% | 17.51% | -22.62% | 20.54% | 27.16% | 29.05% | 53.62% |
| VT | added_to_baseline | US long custom | positive | 488 | 8.85% | negative | -0.26% | 17.02% | -25.46% | 20.04% | 24.35% | 28.49% | 52.37% |
| EWG | added_to_baseline | SubD proxy research | positive | 957 | 61.13% | negative | -1.07% | 16.21% | -23.49% | 17.52% | 22.50% | 28.19% | 50.83% |
| EFA | added_to_baseline | Sub-B VEA proxy | positive | 624 | 4.72% | negative | -1.16% | 16.13% | -23.51% | 18.18% | 24.79% | 28.09% | 55.07% |
| AGG | added_to_baseline | recent final-main variant | negative | 355 | -3.03% | negative | -1.65% | 15.64% | -26.59% | 16.87% | 16.58% | 27.85% | 49.46% |
| EWJ | added_to_baseline | SubD proxy research | negative | 693 | -13.84% | negative | -2.95% | 14.33% | -27.18% | 15.30% | 16.09% | 16.08% | 17.78% |
| EMXC_PROXY | added_to_baseline | recent final-main variant + Sub-B | positive | 850 | 28.63% | negative | -3.15% | 14.14% | -23.09% | 16.95% | 20.87% | 25.85% | 38.72% |
| TLT | added_to_baseline | Sub-B VGLT proxy / inflation check | negative | 816 | -4.33% | negative | -3.48% | 13.81% | -21.02% | 14.31% | 13.53% | 22.89% | 49.61% |
| UUP | added_to_baseline | Sub-B macro | negative | 712 | -11.95% | negative | -4.02% | 13.26% | -25.81% | 15.42% | 17.94% | 29.67% | 51.33% |
| 159985.SZ | added_to_baseline_cn_sina_diagnostic | SubD V1.1 six ETF | positive | 325 | 40.53% | positive | 2.09% | 19.12% | -25.20% | 22.05% | 26.09% | 36.68% | 49.43% |
| 518880.SH | added_to_baseline_cn_sina_diagnostic | SubD V1.1 six ETF | positive | 394 | 23.24% | positive | 1.62% | 18.66% | -22.16% | 21.14% | 19.66% | 25.97% | 43.05% |
| 513520.SH | added_to_baseline_cn_sina_diagnostic | SubD V1.1 six ETF | positive | 281 | 18.93% | positive | 1.44% | 18.48% | -25.20% | 20.76% | 23.38% | 28.02% | 53.12% |
| 159941.SZ | added_to_baseline_cn_sina_diagnostic | SubD V1.1 six ETF | positive | 620 | 63.79% | positive | 0.61% | 17.64% | -26.02% | 19.82% | 21.69% | 37.74% | 68.77% |
| 513030.SH | added_to_baseline_cn_sina_diagnostic | SubD V1.1 six ETF | positive | 438 | 22.70% | negative | -0.80% | 16.23% | -23.10% | 16.58% | 20.66% | 32.19% | 52.86% |
| 159915.SZ | added_to_baseline_cn_sina_diagnostic | SubD V1.1 six ETF | positive | 431 | 52.06% | negative | -1.31% | 15.73% | -25.06% | 16.23% | 17.65% | 28.56% | 50.34% |
| QQQ | baseline_existing | V1.3 baseline | positive | 1864 | 171.15% | neutral | 0.00% | 17.28% | -25.20% | 17.84% | 18.46% | 30.19% | 52.37% |
| GLD | baseline_existing | V1.3 baseline | positive | 1296 | 115.17% | neutral | 0.00% | 17.28% | -25.20% | 17.84% | 18.46% | 30.19% | 52.37% |
| CN_CYB_399006 | baseline_existing | V1.3 baseline | positive | 960 | 226.16% | neutral | 0.00% | 17.28% | -25.20% | 17.84% | 18.46% | 30.19% | 52.37% |
