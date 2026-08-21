# SubD Mixed Pool V1.3 Cash-Included Retest

- Run date: 2026-07-02
- Data window: 2007-01-04 to 2026-07-01 (4735 rows)
- Source: Yahoo Finance chart API [total-return/adjusted-close; adjusted close], akshare.stock_zh_index_daily [index close / price index; symbol=sz399006; no pre-2010 backfill]
- Cash yield: 3.00% annual, daily return 0.00011730
- Scenario: v1_3_three_asset_cash3_nav_overheat; one-way cost 0.10%; rolling stats use close-to-close holding period from each buy date to first available trading date on/after anniversary

## Performance Windows
| Window | Period | Rows | Total Return | Annualized | Max Drawdown | Volatility | Sharpe | Avg Exposure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| full_sample | 2007-01-04 to 2026-07-01 | 4735 | 1899.79% | 17.28% | -25.20% | 17.40% | 1.00 | 71.89% |
| 10Y | 2016-07-01 to 2026-07-01 | 2427 | 386.01% | 17.84% | -22.01% | 16.66% | 1.07 | 71.74% |
| 5Y | 2021-07-01 to 2026-07-01 | 1211 | 125.72% | 18.46% | -22.01% | 17.30% | 1.07 | 73.47% |
| 3Y | 2023-07-03 to 2026-07-01 | 726 | 113.83% | 30.19% | -16.73% | 18.07% | 1.55 | 79.82% |
| 1Y | 2025-07-01 to 2026-07-01 | 243 | 50.10% | 52.37% | -13.35% | 19.82% | 2.23 | 71.75% |
| from_2017_eval_start | 2017-01-03 to 2026-07-01 | 2303 | 437.80% | 20.21% | -22.01% | 16.93% | 1.17 | 71.71% |

## Worst Rolling Buy Dates
| Horizon | Valid buy-date range | Samples | Worst buy date | Exit date | Total return | Annualized | Median annualized | 5th pct annualized |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1Y | 2007-01-04 to 2025-07-01 | 4493 | 2015-06-12 | 2016-06-13 | -20.86% | -20.77% | 19.74% | -8.86% |
| 3Y | 2007-01-04 to 2023-06-30 | 4009 | 2015-04-30 | 2018-05-02 | -17.63% | -6.25% | 16.07% | 0.39% |
| 5Y | 2007-01-04 to 2021-07-01 | 3525 | 2013-11-29 | 2018-11-29 | 21.16% | 3.91% | 15.72% | 7.23% |

## Cash Diagnostics
- Average cash exposure over full sample: 28.11%
- Arithmetic sum of daily cash-return components: 15.61%
- Final NAV: 20.000295
