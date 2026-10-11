# Sub-D R2-Removed Final Main EMXC Proxy Pool

## Pool

- Kept: `QQQ`, `GLD`, `EMXC` spliced with `EEM`, `CN_CYB_399006`.
- Removed from this proxy run: `AGG`, `EWG`, `EWJ`, soymeal.
- EMXC rule: `EEM` before `2017-08-01`; scaled `EMXC` after switch.
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
| insample_2007_2016_emxc_proxy_pool | 8.36% | -26.05% | N/A | N/A | 3.69% | -26.05% | 1.41% | -26.05% | -10.41% | -14.80% | insufficient rows: 2432 < 2520 trading days |
| oos_2017_2026_standalone_reset_emxc_proxy_pool | 16.97% | -21.77% | N/A | N/A | 20.74% | -19.99% | 29.17% | -17.14% | 40.81% | -15.87% | insufficient rows: 2302 < 2520 trading days |
| oos_2017_2026_continuous_state_from_2007_emxc_proxy_pool | 15.86% | -21.77% | N/A | N/A | 20.74% | -19.99% | 29.17% | -17.14% | 40.81% | -15.87% | insufficient rows: 2302 < 2520 trading days |

## Yearly Returns

| Mode | Year | Return | Max DD | Days |
|---|---:|---:|---:|---:|
| insample_2007_2016_emxc_proxy_pool | 2007 | 14.81% | -15.23% | 242 |
| insample_2007_2016_emxc_proxy_pool | 2008 | -0.23% | -14.18% | 246 |
| insample_2007_2016_emxc_proxy_pool | 2009 | 13.70% | -9.28% | 244 |
| insample_2007_2016_emxc_proxy_pool | 2010 | 6.41% | -9.83% | 242 |
| insample_2007_2016_emxc_proxy_pool | 2011 | 10.65% | -16.47% | 244 |
| insample_2007_2016_emxc_proxy_pool | 2012 | 8.06% | -14.12% | 243 |
| insample_2007_2016_emxc_proxy_pool | 2013 | 15.61% | -15.12% | 238 |
| insample_2007_2016_emxc_proxy_pool | 2014 | 13.47% | -9.93% | 245 |
| insample_2007_2016_emxc_proxy_pool | 2015 | 9.18% | -22.55% | 244 |
| insample_2007_2016_emxc_proxy_pool | 2016 | -8.53% | -14.80% | 244 |
| oos_2017_2026_standalone_reset_emxc_proxy_pool | 2017 | 1.39% | -7.94% | 244 |
| oos_2017_2026_standalone_reset_emxc_proxy_pool | 2018 | -3.45% | -16.63% | 243 |
| oos_2017_2026_standalone_reset_emxc_proxy_pool | 2019 | 26.66% | -8.35% | 244 |
| oos_2017_2026_standalone_reset_emxc_proxy_pool | 2020 | 14.69% | -21.77% | 243 |
| oos_2017_2026_standalone_reset_emxc_proxy_pool | 2021 | 15.16% | -13.12% | 243 |
| oos_2017_2026_standalone_reset_emxc_proxy_pool | 2022 | 6.82% | -17.07% | 242 |
| oos_2017_2026_standalone_reset_emxc_proxy_pool | 2023 | 13.45% | -16.05% | 242 |
| oos_2017_2026_standalone_reset_emxc_proxy_pool | 2024 | 24.22% | -8.32% | 242 |
| oos_2017_2026_standalone_reset_emxc_proxy_pool | 2025 | 62.17% | -6.62% | 243 |
| oos_2017_2026_standalone_reset_emxc_proxy_pool | 2026 | 4.74% | -15.87% | 116 |
| oos_2017_2026_continuous_state_from_2007_emxc_proxy_pool | 2017 | 5.07% | -4.01% | 244 |
| oos_2017_2026_continuous_state_from_2007_emxc_proxy_pool | 2018 | -1.44% | -8.56% | 243 |
| oos_2017_2026_continuous_state_from_2007_emxc_proxy_pool | 2019 | 12.77% | -4.25% | 244 |
| oos_2017_2026_continuous_state_from_2007_emxc_proxy_pool | 2020 | 11.58% | -21.77% | 243 |
| oos_2017_2026_continuous_state_from_2007_emxc_proxy_pool | 2021 | 15.16% | -13.12% | 243 |
| oos_2017_2026_continuous_state_from_2007_emxc_proxy_pool | 2022 | 6.82% | -17.07% | 242 |
| oos_2017_2026_continuous_state_from_2007_emxc_proxy_pool | 2023 | 13.45% | -16.05% | 242 |
| oos_2017_2026_continuous_state_from_2007_emxc_proxy_pool | 2024 | 24.22% | -8.32% | 242 |
| oos_2017_2026_continuous_state_from_2007_emxc_proxy_pool | 2025 | 62.17% | -6.62% | 243 |
| oos_2017_2026_continuous_state_from_2007_emxc_proxy_pool | 2026 | 4.74% | -15.87% | 116 |

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

| code          | name                               | source                                              | adjustment                                   | first_available   | first_used   | last       |   rows | pool_rule                                                  | proxy_switch_date   | proxy_input_eem_first   | proxy_input_eem_last   | proxy_input_emxc_first   | proxy_input_emxc_last   |   proxy_scale_factor | last_aligned   |   ffill_days_on_cn_calendar | mode                                                     |
|:--------------|:-----------------------------------|:----------------------------------------------------|:---------------------------------------------|:------------------|:-------------|:-----------|-------:|:-----------------------------------------------------------|:--------------------|:------------------------|:-----------------------|:-------------------------|:------------------------|---------------------:|:---------------|----------------------------:|:---------------------------------------------------------|
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY         | Yahoo Finance chart API                             | adjusted close                               | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | nan                 | nan                     | nan                    | nan                      | nan                     |           nan        | 2016-12-30     |                          80 | insample_2007_2016_emxc_proxy_pool                       |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY           | Yahoo Finance chart API                             | adjusted close                               | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | nan                 | nan                     | nan                    | nan                      | nan                     |           nan        | 2016-12-30     |                          80 | insample_2007_2016_emxc_proxy_pool                       |
| EMXC          | EM_EX_CHINA_EMXC_SPLICED_EEM_PROXY | Yahoo Finance chart API; EEM spliced to scaled EMXC | adjusted close; EMXC scaled to EEM at switch | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | EEM proxy before 2017-08-01; scaled EMXC after switch      | 2017-08-01          | 2006-11-02              | 2016-12-30             | nan                      | nan                     |           nan        | 2016-12-30     |                          80 | insample_2007_2016_emxc_proxy_pool                       |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_ADD    | Eastmoney push2his kline secid=0.399006             | index close / price index                    | 2010-06-01        | 2010-06-01   | 2016-12-30 |   1601 | dynamic asset; no prices before 2010-06-01 and no backfill | nan                 | nan                     | nan                    | nan                      | nan                     |           nan        | 2016-12-30     |                           0 | insample_2007_2016_emxc_proxy_pool                       |
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY         | Yahoo Finance chart API                             | adjusted close                               | 2016-11-02        | 2017-01-03   | 2026-06-30 |   2426 | core asset available from 2007 start                       | nan                 | nan                     | nan                    | nan                      | nan                     |           nan        | 2026-06-30     |                          78 | oos_2017_2026_standalone_reset_emxc_proxy_pool           |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY           | Yahoo Finance chart API                             | adjusted close                               | 2016-11-02        | 2017-01-03   | 2026-06-30 |   2426 | core asset available from 2007 start                       | nan                 | nan                     | nan                    | nan                      | nan                     |           nan        | 2026-06-30     |                          78 | oos_2017_2026_standalone_reset_emxc_proxy_pool           |
| EMXC          | EM_EX_CHINA_EMXC_SPLICED_EEM_PROXY | Yahoo Finance chart API; EEM spliced to scaled EMXC | adjusted close; EMXC scaled to EEM at switch | 2016-11-02        | 2017-01-03   | 2026-06-30 |   2426 | EEM proxy before 2017-08-01; scaled EMXC after switch      | 2017-08-01          | 2016-11-02              | 2026-06-30             | 2017-07-26               | 2026-06-30              |             0.875321 | 2026-06-30     |                          78 | oos_2017_2026_standalone_reset_emxc_proxy_pool           |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_ADD    | Eastmoney push2his kline secid=0.399006             | index close / price index                    | 2010-06-01        | 2010-06-01   | 2026-06-30 |   3903 | dynamic asset; no prices before 2010-06-01 and no backfill | nan                 | nan                     | nan                    | nan                      | nan                     |           nan        | 2026-06-30     |                           0 | oos_2017_2026_standalone_reset_emxc_proxy_pool           |
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY         | Yahoo Finance chart API                             | adjusted close                               | 2006-11-02        | 2007-01-03   | 2026-06-30 |   4943 | core asset available from 2007 start                       | nan                 | nan                     | nan                    | nan                      | nan                     |           nan        | 2026-06-30     |                         158 | oos_2017_2026_continuous_state_from_2007_emxc_proxy_pool |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY           | Yahoo Finance chart API                             | adjusted close                               | 2006-11-02        | 2007-01-03   | 2026-06-30 |   4943 | core asset available from 2007 start                       | nan                 | nan                     | nan                    | nan                      | nan                     |           nan        | 2026-06-30     |                         158 | oos_2017_2026_continuous_state_from_2007_emxc_proxy_pool |
| EMXC          | EM_EX_CHINA_EMXC_SPLICED_EEM_PROXY | Yahoo Finance chart API; EEM spliced to scaled EMXC | adjusted close; EMXC scaled to EEM at switch | 2006-11-02        | 2007-01-03   | 2026-06-30 |   4943 | EEM proxy before 2017-08-01; scaled EMXC after switch      | 2017-08-01          | 2006-11-02              | 2026-06-30             | 2017-07-26               | 2026-06-30              |             0.875321 | 2026-06-30     |                         158 | oos_2017_2026_continuous_state_from_2007_emxc_proxy_pool |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_ADD    | Eastmoney push2his kline secid=0.399006             | index close / price index                    | 2010-06-01        | 2010-06-01   | 2026-06-30 |   3903 | dynamic asset; no prices before 2010-06-01 and no backfill | nan                 | nan                     | nan                    | nan                      | nan                     |           nan        | 2026-06-30     |                           0 | oos_2017_2026_continuous_state_from_2007_emxc_proxy_pool |

## Artifacts

- Metrics: `outputs\subd_proxy_dynamic_cyb_r2none_final_main_qqq_gld_emxc_cyb_2007_2026_20260702\metrics.csv`
- Yearly returns: `outputs\subd_proxy_dynamic_cyb_r2none_final_main_qqq_gld_emxc_cyb_2007_2026_20260702\yearly_returns.csv`
- Daily curves: `outputs\subd_proxy_dynamic_cyb_r2none_final_main_qqq_gld_emxc_cyb_2007_2026_20260702\daily_curves.csv`
- Sources: `outputs\subd_proxy_dynamic_cyb_r2none_final_main_qqq_gld_emxc_cyb_2007_2026_20260702\sources.csv`
- Metadata: `outputs\subd_proxy_dynamic_cyb_r2none_final_main_qqq_gld_emxc_cyb_2007_2026_20260702\metadata.json`
