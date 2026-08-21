# Sub-D R2-Removed Final Main Three-Asset Pool

## Pool

- Kept: `QQQ`, `GLD`, `CN_CYB_399006`.
- Removed from this proxy run: `EWG`, `EWJ`, soymeal.
- ChiNext still joins dynamically from its own first usable data; no CSI500 substitute and no backfill.

## Frozen Parameter

- Candidate: `lb_28_r2_none_buf_1p15_entry_0p25_decay_off_nav_enter_0p2_exit_0p05_scale_0p50_fixed_same_side_fixed_enter_0p15_exit_0p13_scale_0p00_same_side_or_exit`
- R2 removed; target-vol off; momentum decay off.
- Lookback `28`, switch buffer `1.15`, entry fraction `0.25`.
- NAV defense enter `20%`, exit `5%`, scale `0.50`.
- Fixed same-side overheat enter `15%`, exit `13%`, scale `0`, recovery `same_side_or_exit`.

## Mandatory Windows

| Mode | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | 10Y Reason |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| insample_2007_2016_three_asset_pool | 13.24% | -25.60% | N/A | N/A | 9.21% | -25.60% | 4.37% | -25.60% | -11.06% | -13.25% | insufficient rows: 2432 < 2520 trading days |
| oos_2017_2026_standalone_reset_three_asset_pool | 18.26% | -23.57% | N/A | N/A | 18.34% | -23.57% | 31.19% | -17.10% | 53.25% | -13.54% | insufficient rows: 2302 < 2520 trading days |
| oos_2017_2026_continuous_state_from_2007_three_asset_pool | 17.83% | -23.57% | N/A | N/A | 18.34% | -23.57% | 31.19% | -17.10% | 53.25% | -13.54% | insufficient rows: 2302 < 2520 trading days |

## Yearly Returns

| Mode | Year | Return | Max DD | Days |
|---|---:|---:|---:|---:|
| insample_2007_2016_three_asset_pool | 2007 | 13.53% | -8.47% | 242 |
| insample_2007_2016_three_asset_pool | 2008 | -1.06% | -22.73% | 246 |
| insample_2007_2016_three_asset_pool | 2009 | 19.36% | -8.81% | 244 |
| insample_2007_2016_three_asset_pool | 2010 | 20.76% | -5.79% | 242 |
| insample_2007_2016_three_asset_pool | 2011 | 19.92% | -12.97% | 244 |
| insample_2007_2016_three_asset_pool | 2012 | 8.61% | -14.82% | 243 |
| insample_2007_2016_three_asset_pool | 2013 | 27.48% | -14.78% | 238 |
| insample_2007_2016_three_asset_pool | 2014 | 19.09% | -9.93% | 245 |
| insample_2007_2016_three_asset_pool | 2015 | 11.85% | -20.42% | 244 |
| insample_2007_2016_three_asset_pool | 2016 | -7.26% | -9.84% | 244 |
| oos_2017_2026_standalone_reset_three_asset_pool | 2017 | 7.29% | -7.38% | 244 |
| oos_2017_2026_standalone_reset_three_asset_pool | 2018 | 4.26% | -9.40% | 243 |
| oos_2017_2026_standalone_reset_three_asset_pool | 2019 | 24.53% | -8.59% | 244 |
| oos_2017_2026_standalone_reset_three_asset_pool | 2020 | 23.62% | -18.14% | 243 |
| oos_2017_2026_standalone_reset_three_asset_pool | 2021 | 19.05% | -11.23% | 243 |
| oos_2017_2026_standalone_reset_three_asset_pool | 2022 | -4.04% | -21.99% | 242 |
| oos_2017_2026_standalone_reset_three_asset_pool | 2023 | -0.39% | -16.01% | 242 |
| oos_2017_2026_standalone_reset_three_asset_pool | 2024 | 28.06% | -8.32% | 242 |
| oos_2017_2026_standalone_reset_three_asset_pool | 2025 | 60.31% | -6.62% | 243 |
| oos_2017_2026_standalone_reset_three_asset_pool | 2026 | 15.01% | -13.54% | 116 |
| oos_2017_2026_continuous_state_from_2007_three_asset_pool | 2017 | 6.87% | -3.74% | 244 |
| oos_2017_2026_continuous_state_from_2007_three_asset_pool | 2018 | 1.23% | -9.30% | 243 |
| oos_2017_2026_continuous_state_from_2007_three_asset_pool | 2019 | 24.53% | -8.59% | 244 |
| oos_2017_2026_continuous_state_from_2007_three_asset_pool | 2020 | 23.62% | -18.14% | 243 |
| oos_2017_2026_continuous_state_from_2007_three_asset_pool | 2021 | 19.05% | -11.23% | 243 |
| oos_2017_2026_continuous_state_from_2007_three_asset_pool | 2022 | -4.04% | -21.99% | 242 |
| oos_2017_2026_continuous_state_from_2007_three_asset_pool | 2023 | -0.39% | -16.01% | 242 |
| oos_2017_2026_continuous_state_from_2007_three_asset_pool | 2024 | 28.06% | -8.32% | 242 |
| oos_2017_2026_continuous_state_from_2007_three_asset_pool | 2025 | 60.31% | -6.62% | 243 |
| oos_2017_2026_continuous_state_from_2007_three_asset_pool | 2026 | 15.01% | -13.54% | 116 |

## Data And Execution Assumptions

- Requested start: `2007-01-01`.
- Split date: `2017-01-01`.
- Requested end: `2026-06-30`.
- This is proxy diagnostic research, not formal production ETF execution.
- Calendar: repo-local A-share trading-day cache.
- US proxies: Yahoo Finance adjusted close, reindexed to the A-share calendar and forward-filled by rule.
- ChiNext proxy: Eastmoney `0.399006` index close / price index.
- Cost model: one-way cost `0.001`; stale trade legs on forward-filled prices are blocked by the base staged-entry path.
- Execution: close-to-close diagnostic helper path, same as the 2007-2016 proxy layered tests.

## Source Audit

| code          | name                            | source                                  | adjustment                | first_available   | first_used   | last       |   rows | pool_rule                                                  | last_aligned   |   ffill_days_on_cn_calendar | mode                                                      |
|:--------------|:--------------------------------|:----------------------------------------|:--------------------------|:------------------|:-------------|:-----------|-------:|:-----------------------------------------------------------|:---------------|----------------------------:|:----------------------------------------------------------|
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY      | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 | insample_2007_2016_three_asset_pool                       |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY        | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 | insample_2007_2016_three_asset_pool                       |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_ADD | Eastmoney push2his kline secid=0.399006 | index close / price index | 2010-06-01        | 2010-06-01   | 2016-12-30 |   1601 | dynamic asset; no prices before 2010-06-01 and no backfill | 2016-12-30     |                           0 | insample_2007_2016_three_asset_pool                       |
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY      | Yahoo Finance chart API                 | adjusted close            | 2016-11-02        | 2017-01-03   | 2026-06-30 |   2426 | core asset available from 2007 start                       | 2026-06-30     |                          78 | oos_2017_2026_standalone_reset_three_asset_pool           |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY        | Yahoo Finance chart API                 | adjusted close            | 2016-11-02        | 2017-01-03   | 2026-06-30 |   2426 | core asset available from 2007 start                       | 2026-06-30     |                          78 | oos_2017_2026_standalone_reset_three_asset_pool           |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_ADD | Eastmoney push2his kline secid=0.399006 | index close / price index | 2010-06-01        | 2010-06-01   | 2026-06-30 |   3903 | dynamic asset; no prices before 2010-06-01 and no backfill | 2026-06-30     |                           0 | oos_2017_2026_standalone_reset_three_asset_pool           |
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY      | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2026-06-30 |   4943 | core asset available from 2007 start                       | 2026-06-30     |                         158 | oos_2017_2026_continuous_state_from_2007_three_asset_pool |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY        | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2026-06-30 |   4943 | core asset available from 2007 start                       | 2026-06-30     |                         158 | oos_2017_2026_continuous_state_from_2007_three_asset_pool |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_ADD | Eastmoney push2his kline secid=0.399006 | index close / price index | 2010-06-01        | 2010-06-01   | 2026-06-30 |   3903 | dynamic asset; no prices before 2010-06-01 and no backfill | 2026-06-30     |                           0 | oos_2017_2026_continuous_state_from_2007_three_asset_pool |

## Artifacts

- Metrics: `outputs\subd_proxy_dynamic_cyb_r2none_final_main_qqq_gld_cyb_2007_2026_20260702\metrics.csv`
- Yearly returns: `outputs\subd_proxy_dynamic_cyb_r2none_final_main_qqq_gld_cyb_2007_2026_20260702\yearly_returns.csv`
- Daily curves: `outputs\subd_proxy_dynamic_cyb_r2none_final_main_qqq_gld_cyb_2007_2026_20260702\daily_curves.csv`
- Sources: `outputs\subd_proxy_dynamic_cyb_r2none_final_main_qqq_gld_cyb_2007_2026_20260702\sources.csv`
- Metadata: `outputs\subd_proxy_dynamic_cyb_r2none_final_main_qqq_gld_cyb_2007_2026_20260702\metadata.json`
