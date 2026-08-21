# Custom US Long 20Y NAV Chart

- Run date: 2026-07-01
- Code path: `run_us_long_custom_20y_chart.py`
- Production source inspected/imported: `mnt_bot V 7.6 plus.py`
- Strategy identity: Sub-C US long production parameters; current source has timing disabled and target-vol scaling enabled.
- Window: 2006-07-03 to 2026-06-30 (5029 US sessions).
- Market/session: US ETF trading sessions; BTC is aligned to US sessions with forward-filled crypto closes on ETF session dates.
- Price mode: Yahoo/yfinance adjusted close (`auto_adjust=True`).
- Frictions: annual rebalance one-way commission 0.10%; strategy additionally applies Sub-C target-vol financing/rebalance costs from source parameters.

## Proxy Rules

- SP500 leg: SPY.
- Bond leg: AGG.
- VT before VT data exists: synthetic 60% SPY / 30% EFA / 10% EEM daily-return proxy, scaled to VT on VT first valid date.
- VT first valid date: 2008-06-26.
- BTC first valid US session: 2014-09-17; before that, BTC is excluded and the remaining target weights are normalized.

## Metrics

| Curve | Window | Start | End | Years | Annualized Return | Max Drawdown |
|---|---:|---:|---:|---:|---:|---:|
| strategy_return | Full | 2006-07-03 | 2026-06-30 | 19.99 | 15.00% | -33.25% |
| strategy_return | 10Y | 2016-06-30 | 2026-06-30 | 10.00 | 21.94% | -25.06% |
| strategy_return | 5Y | 2021-06-30 | 2026-06-30 | 5.00 | 14.97% | -25.06% |
| strategy_return | 3Y | 2023-06-30 | 2026-06-30 | 3.00 | 23.01% | -14.60% |
| strategy_return | 1Y | 2025-06-30 | 2026-06-30 | 1.00 | 19.77% | -12.32% |
| buy_hold_return | Full | 2006-07-03 | 2026-06-30 | 19.99 | 14.17% | -36.59% |
| buy_hold_return | 10Y | 2016-06-30 | 2026-06-30 | 10.00 | 21.08% | -24.86% |
| buy_hold_return | 5Y | 2021-06-30 | 2026-06-30 | 5.00 | 13.57% | -24.86% |
| buy_hold_return | 3Y | 2023-06-30 | 2026-06-30 | 3.00 | 21.74% | -12.82% |
| buy_hold_return | 1Y | 2025-06-30 | 2026-06-30 | 1.00 | 19.75% | -8.84% |

## Data Manifest

| Symbol | First Date | Last Date | Rows | First Close | Last Close | Source | Note |
|---|---:|---:|---:|---:|---:|---|---|
| SPY | 2006-07-03 | 2026-06-30 | 5029 | 88.494675 | 746.77002 | Yahoo Finance via yfinance auto_adjust=True |  |
| QQQ | 2006-07-03 | 2026-06-30 | 5029 | 33.347115 | 736.400024 | Yahoo Finance via yfinance auto_adjust=True |  |
| VT | 2008-06-26 | 2026-06-30 | 4530 | 33.874264 | 156.949997 | Yahoo Finance via yfinance auto_adjust=True |  |
| GLD | 2006-07-03 | 2026-06-30 | 5029 | 62.18 | 368.380005 | Yahoo Finance via yfinance auto_adjust=True |  |
| AGG | 2006-07-03 | 2026-06-30 | 5029 | 52.327484 | 98.980003 | Yahoo Finance via yfinance auto_adjust=True |  |
| DBC | 2006-07-03 | 2026-06-30 | 5029 | 20.588303 | 26.66 | Yahoo Finance via yfinance auto_adjust=True |  |
| BTC-USD | 2014-09-17 | 2026-07-01 | 4306 | 457.334015 | 58301.0 | Yahoo Finance via yfinance auto_adjust=True |  |
| EFA | 2006-07-03 | 2026-06-30 | 5029 | 35.979572 | 103.879997 | Yahoo Finance via yfinance auto_adjust=True |  |
| EEM | 2006-07-03 | 2026-06-30 | 5029 | 21.116686 | 68.410004 | Yahoo Finance via yfinance auto_adjust=True |  |
| BIL | 2007-05-30 | 2026-06-30 | 4802 | 70.794579 | 91.639999 | Yahoo Finance via yfinance auto_adjust=True |  |
| VT_PROXY | 2006-07-03 | 2026-06-30 | 5029 | 30.770441 | 156.949997 | Synthetic before VT inception, Yahoo VT afterward | 60% SPY / 30% EFA / 10% EEM before first VT date |

## Cross-Check

- Nasdaq historical API was used for June 2026 close/row-count checks on SPY, QQQ, GLD, and AGG.
- Stooq was attempted as a broader independent source, but returned an anti-automation verification page followed by `Access denied` in this environment.

| Symbol | Nasdaq Rows | Yahoo Rows | Nasdaq Latest | Yahoo Latest | Close Diff | Error |
|---|---:|---:|---:|---:|---:|---|
| SPY | 21 | 21 | 746.77 | 746.77001953125 | 1.9531250018189894e-05 |  |
| QQQ | 21 | 21 | 736.4 | 736.4000244140625 | 2.4414062522737368e-05 |  |
| GLD | 21 | 21 | 368.38 | 368.3800048828125 | 4.8828125045474735e-06 |  |
| AGG | 21 | 21 | 98.98 | 98.9800033569336 | 3.3569335897709607e-06 |  |

## Output Files

- `nav_chart.png`
- `daily_curves.csv`
- `window_metrics.csv`
- `source_manifest.csv`
- `nasdaq_crosscheck.csv`
- `run_info.json`

## Caveats

- This is a research/proxy chart, not a pure seven-ticker live-tradable 20-year history.
- The 2006-2008 VT segment is synthetic, and the 2006-2014 BTC segment is phase-excluded.
- Nasdaq cross-check validates recent raw closes and row counts only; the backtest return path uses Yahoo adjusted close.
