# V1.3 Rotation Pool Candidate Asset Sign Test

- Baseline: QQQ + GLD + CN_CYB_399006; full annualized 17.28%, MDD -25.20%, final NAV 20.0003.
- Test: add each non-baseline candidate one at a time; added assets join from first available date; V1.3 scoring, cash yield, NAV defense, overheat, staged entry, and 0.10% one-way cost unchanged.

| Code | Source group | Held return sign | Held days | Held compound return | Pool effect | Delta ann. vs base | Full ann. | Full MDD | 10Y ann. | 5Y ann. | 3Y ann. | 1Y ann. |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| KMLM | Sub-B macro | positive | 260 | 28.23% | positive | 2.25% | 19.53% | -25.20% | 22.29% | 29.78% | 38.37% | 74.30% |
| BTC-USD | Sub-B IBIT proxy + US long custom | positive | 503 | 82.83% | positive | 1.88% | 19.16% | -32.37% | 17.04% | -0.39% | 7.84% | 17.53% |
| DBMF | Sub-B macro | negative | 226 | -0.35% | positive | 0.76% | 18.04% | -25.20% | 19.33% | 21.54% | 29.46% | 54.46% |
| SPY | US long custom | positive | 577 | 17.24% | positive | 0.36% | 17.65% | -24.92% | 19.78% | 22.47% | 26.48% | 53.89% |
| DBC | Sub-B + US long custom | positive | 869 | 39.04% | positive | 0.22% | 17.51% | -22.62% | 20.54% | 27.16% | 29.05% | 53.62% |
| VT | US long custom | positive | 488 | 8.85% | negative | -0.26% | 17.02% | -25.46% | 20.04% | 24.35% | 28.49% | 52.37% |
| EWG | SubD proxy research | positive | 957 | 61.13% | negative | -1.07% | 16.21% | -23.49% | 17.52% | 22.50% | 28.19% | 50.83% |
| EFA | Sub-B VEA proxy | positive | 624 | 4.72% | negative | -1.16% | 16.13% | -23.51% | 18.18% | 24.79% | 28.09% | 55.07% |
| AGG | recent final-main variant | negative | 355 | -3.03% | negative | -1.65% | 15.64% | -26.59% | 16.87% | 16.58% | 27.85% | 49.46% |
| EWJ | SubD proxy research | negative | 693 | -13.84% | negative | -2.95% | 14.33% | -27.18% | 15.30% | 16.09% | 16.08% | 17.78% |
| EMXC_PROXY | recent final-main variant + Sub-B | positive | 850 | 28.63% | negative | -3.15% | 14.14% | -23.09% | 16.95% | 20.87% | 25.85% | 38.72% |
| TLT | Sub-B VGLT proxy / inflation check | negative | 816 | -4.33% | negative | -3.48% | 13.81% | -21.02% | 14.31% | 13.53% | 22.89% | 49.61% |
| UUP | Sub-B macro | negative | 712 | -11.95% | negative | -4.02% | 13.26% | -25.81% | 15.42% | 17.94% | 29.67% | 51.33% |
| QQQ | V1.3 baseline | positive | 1864 | 171.15% | neutral | 0.00% | 17.28% | -25.20% | 17.84% | 18.46% | 30.19% | 52.37% |
| GLD | V1.3 baseline | positive | 1296 | 115.17% | neutral | 0.00% | 17.28% | -25.20% | 17.84% | 18.46% | 30.19% | 52.37% |
| CN_CYB_399006 | V1.3 baseline | positive | 960 | 226.16% | neutral | 0.00% | 17.28% | -25.20% | 17.84% | 18.46% | 30.19% | 52.37% |

## Errors
- 159915.SZ: RuntimeError("All qfq data sources failed. 159915.SZ akshare.fund_etf_hist_em daily close: AkShare Eastmoney qfq returned no rows for 159915.SZ / 159915; last_error=('Connection aborted.', RemoteDisconnected('Remote end closed connection without respo | 159915.SZ Tencent fqkline: '159915.SZ' | 159915.SZ Eastmoney push2his kline: Eastmoney returned no data for 159915.SZ; last_error=('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))")
- 159941.SZ: RuntimeError("All qfq data sources failed. 159941.SZ akshare.fund_etf_hist_em daily close: AkShare Eastmoney qfq returned no rows for 159941.SZ / 159941; last_error=('Connection aborted.', RemoteDisconnected('Remote end closed connection without respo | 159941.SZ Tencent fqkline: '159941.SZ' | 159941.SZ Eastmoney push2his kline: Eastmoney returned no data for 159941.SZ; last_error=('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))")
- 513030.SH: RuntimeError("All qfq data sources failed. 513030.SH akshare.fund_etf_hist_em daily close: AkShare Eastmoney qfq returned no rows for 513030.SH / 513030; last_error=('Connection aborted.', RemoteDisconnected('Remote end closed connection without respo | 513030.SH Tencent fqkline: '513030.SH' | 513030.SH Eastmoney push2his kline: Eastmoney returned no data for 513030.SH; last_error=('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))")
- 513520.SH: RuntimeError("All qfq data sources failed. 513520.SH akshare.fund_etf_hist_em daily close: AkShare Eastmoney qfq returned no rows for 513520.SH / 513520; last_error=('Connection aborted.', RemoteDisconnected('Remote end closed connection without respo | 513520.SH Tencent fqkline: '513520.SH' | 513520.SH Eastmoney push2his kline: Eastmoney returned no data for 513520.SH; last_error=('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))")
- 159985.SZ: RuntimeError("All qfq data sources failed. 159985.SZ akshare.fund_etf_hist_em daily close: AkShare Eastmoney qfq returned no rows for 159985.SZ / 159985; last_error=('Connection aborted.', RemoteDisconnected('Remote end closed connection without respo | 159985.SZ Tencent fqkline: '159985.SZ' | 159985.SZ Eastmoney push2his kline: Eastmoney returned no data for 159985.SZ; last_error=('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))")
- 518880.SH: RuntimeError("All qfq data sources failed. 518880.SH akshare.fund_etf_hist_em daily close: AkShare Eastmoney qfq returned no rows for 518880.SH / 518880; last_error=('Connection aborted.', RemoteDisconnected('Remote end closed connection without respo | 518880.SH Tencent fqkline: '518880.SH' | 518880.SH Eastmoney push2his kline: Eastmoney returned no data for 518880.SH; last_error=('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))")
