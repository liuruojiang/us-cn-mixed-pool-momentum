# Sub-D Dynamic ChiNext Proxy OOS Two-Line Test

## Scope

- Freeze the two carried lines selected from the 2007-2016 layered test.
- Apply them unchanged to the next available window: 2017 start through the latest confirmed end date used in this run.
- This is proxy OOS research, not a production ETF formal result.

## Frozen Parameters

| Line | Lookback | R2 | Switch Buffer | Entry | Score Max | Target Vol | Decay | NAV Defense | Overheat |
|---|---:|---:|---:|---:|---:|---|---|---|---|
| `A_clean` | 28 | 0.50 | 1.00 | 75.00% | 5.00 | off | off | off | off |
| `G_decay_nav` | 28 | 0.50 | 1.00 | 75.00% | 5.00 | off | ratio 0.55, recover 0.85, confirm 3, scale 0.75 | enter 12.50%, exit 3.00%, scale 0.75 | off |

## OOS Mandatory Windows

| Line | Candidate | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | 10Y Reason |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `A_clean` | `A_clean_scoremax_5_overheat_off` | 11.16% | -30.71% | N/A | N/A | 13.01% | -24.68% | 17.42% | -24.68% | 44.74% | -9.13% | insufficient rows: 2302 < 2520 trading days |
| `G_decay_nav` | `G_decay_nav_scoremax_5_overheat_off` | 9.43% | -27.09% | N/A | N/A | 11.27% | -21.97% | 15.66% | -21.97% | 40.67% | -9.13% | insufficient rows: 2302 < 2520 trading days |

## Yearly Returns

| Line | Year | Return | Max DD | Days |
|---|---:|---:|---:|---:|
| `A_clean` | 2017 | 11.25% | -5.00% | 244 |
| `A_clean` | 2018 | -25.47% | -30.71% | 243 |
| `A_clean` | 2019 | 25.72% | -5.66% | 244 |
| `A_clean` | 2020 | 32.55% | -15.20% | 243 |
| `A_clean` | 2021 | 0.20% | -13.32% | 243 |
| `A_clean` | 2022 | 13.52% | -12.66% | 242 |
| `A_clean` | 2023 | 13.98% | -7.95% | 242 |
| `A_clean` | 2024 | -10.32% | -24.68% | 242 |
| `A_clean` | 2025 | 35.63% | -9.13% | 243 |
| `A_clean` | 2026 | 20.64% | -8.35% | 116 |
| `G_decay_nav` | 2017 | 10.81% | -5.00% | 244 |
| `G_decay_nav` | 2018 | -22.23% | -27.09% | 243 |
| `G_decay_nav` | 2019 | 19.29% | -4.27% | 244 |
| `G_decay_nav` | 2020 | 26.99% | -14.55% | 243 |
| `G_decay_nav` | 2021 | -0.84% | -13.15% | 243 |
| `G_decay_nav` | 2022 | 10.19% | -9.63% | 242 |
| `G_decay_nav` | 2023 | 13.09% | -7.95% | 242 |
| `G_decay_nav` | 2024 | -8.37% | -21.97% | 242 |
| `G_decay_nav` | 2025 | 26.57% | -9.13% | 243 |
| `G_decay_nav` | 2026 | 21.70% | -7.76% | 116 |

## Data And Execution Assumptions

- Requested start: `2017-01-01`.
- Effective start: `2017-01-03`.
- Effective end: `2026-06-30`.
- Rows: `2302` A-share sessions.
- Pool rule: `QQQ`, `EWG`, `EWJ`, and `GLD`; `CN_CYB_399006` is available throughout this OOS window.
- Calendar: repo-local A-share trading-day cache.
- US proxies: Yahoo Finance adjusted close, reindexed to the A-share calendar and forward-filled by rule.
- ChiNext proxy: Eastmoney `0.399006` index close / price index.
- Cost model: one-way cost `0.001`; stale trade legs on forward-filled prices are blocked by the base staged-entry path.
- Execution: close-to-close diagnostic helper path, same as the 2007-2016 proxy layered tests.

## Source Audit

| code          | name                            | source                                  | adjustment                | first_available   | first_used   | last       |   rows | pool_rule                                                  | last_aligned   |   ffill_days_on_cn_calendar |
|:--------------|:--------------------------------|:----------------------------------------|:--------------------------|:------------------|:-------------|:-----------|-------:|:-----------------------------------------------------------|:---------------|----------------------------:|
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY      | Yahoo Finance chart API                 | adjusted close            | 2016-11-02        | 2017-01-03   | 2026-06-30 |   2426 | core asset available from 2007 start                       | 2026-06-30     |                          78 |
| EWG           | GERMANY_EWG_ADJ_CLOSE_PROXY     | Yahoo Finance chart API                 | adjusted close            | 2016-11-02        | 2017-01-03   | 2026-06-30 |   2426 | core asset available from 2007 start                       | 2026-06-30     |                          78 |
| EWJ           | JAPAN_EWJ_ADJ_CLOSE_PROXY       | Yahoo Finance chart API                 | adjusted close            | 2016-11-02        | 2017-01-03   | 2026-06-30 |   2426 | core asset available from 2007 start                       | 2026-06-30     |                          78 |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY        | Yahoo Finance chart API                 | adjusted close            | 2016-11-02        | 2017-01-03   | 2026-06-30 |   2426 | core asset available from 2007 start                       | 2026-06-30     |                          78 |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_ADD | Eastmoney push2his kline secid=0.399006 | index close / price index | 2010-06-01        | 2010-06-01   | 2026-06-30 |   3903 | dynamic asset; no prices before 2010-06-01 and no backfill | 2026-06-30     |                           0 |

## Artifacts

- Parameters: `outputs\subd_proxy_dynamic_cyb_2017_2026ytd_oos_two_lines_20260701\line_params.csv`
- Window metrics: `outputs\subd_proxy_dynamic_cyb_2017_2026ytd_oos_two_lines_20260701\window_metrics.csv`
- Scan-style summary: `outputs\subd_proxy_dynamic_cyb_2017_2026ytd_oos_two_lines_20260701\scan_summary.csv`
- Daily curves: `outputs\subd_proxy_dynamic_cyb_2017_2026ytd_oos_two_lines_20260701\daily_curves.csv`
- Yearly returns: `outputs\subd_proxy_dynamic_cyb_2017_2026ytd_oos_two_lines_20260701\yearly_returns.csv`
- Sources: `outputs\subd_proxy_dynamic_cyb_2017_2026ytd_oos_two_lines_20260701\sources.csv`
- Metadata: `outputs\subd_proxy_dynamic_cyb_2017_2026ytd_oos_two_lines_20260701\metadata.json`
