# Sub-D R2-Removed Final Main OOS Test

## Frozen Parameter

- Candidate: `lb_28_r2_none_buf_1p15_entry_0p25_decay_off_nav_enter_0p2_exit_0p05_scale_0p50_fixed_same_side_fixed_enter_0p15_exit_0p13_scale_0p00_same_side_or_exit`
- Observation line is dropped.
- R2 removed; target-vol off; momentum decay off.
- Main line: lookback `28`, switch buffer `1.15`, entry fraction `0.25`.
- NAV defense: enter `20%`, exit `5%`, scale `0.50`.
- Fixed same-side overheat: enter `15%`, exit `13%`, scale `0`, recovery `same_side_or_exit`.

## OOS Results

| Mode | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Cash | Avg Exposure | NAV Defense Days | Overheat Days | 10Y Reason |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| standalone_reset_2017 | 13.56% | -25.13% | N/A | N/A | 11.51% | -25.13% | 17.47% | -20.26% | 14.53% | -20.26% | 9.34% | 75.99% | 5.08% | 2.17% | insufficient rows: 2302 < 2520 trading days |
| continuous_state_from_2007 | 12.75% | -25.13% | N/A | N/A | 11.51% | -25.13% | 17.47% | -20.26% | 14.53% | -20.26% | 8.17% | 67.18% | 28.97% | 2.17% | insufficient rows: 2302 < 2520 trading days |

## Yearly Returns

| Mode | Year | Return | Max DD | Days |
|---|---:|---:|---:|---:|
| standalone_reset_2017 | 2017 | 2.96% | -8.42% | 244 |
| standalone_reset_2017 | 2018 | -4.49% | -14.16% | 243 |
| standalone_reset_2017 | 2019 | 31.16% | -5.73% | 244 |
| standalone_reset_2017 | 2020 | 25.01% | -15.91% | 243 |
| standalone_reset_2017 | 2021 | 11.23% | -16.16% | 243 |
| standalone_reset_2017 | 2022 | 4.55% | -18.86% | 242 |
| standalone_reset_2017 | 2023 | 9.91% | -13.29% | 242 |
| standalone_reset_2017 | 2024 | 11.68% | -11.13% | 242 |
| standalone_reset_2017 | 2025 | 46.61% | -8.72% | 243 |
| standalone_reset_2017 | 2026 | -5.33% | -20.26% | 116 |
| continuous_state_from_2007 | 2017 | 3.70% | -4.29% | 244 |
| continuous_state_from_2007 | 2018 | -2.00% | -7.26% | 243 |
| continuous_state_from_2007 | 2019 | 18.87% | -5.73% | 244 |
| continuous_state_from_2007 | 2020 | 25.01% | -15.91% | 243 |
| continuous_state_from_2007 | 2021 | 11.23% | -16.16% | 243 |
| continuous_state_from_2007 | 2022 | 4.55% | -18.86% | 242 |
| continuous_state_from_2007 | 2023 | 9.91% | -13.29% | 242 |
| continuous_state_from_2007 | 2024 | 11.68% | -11.13% | 242 |
| continuous_state_from_2007 | 2025 | 46.61% | -8.72% | 243 |
| continuous_state_from_2007 | 2026 | -5.33% | -20.26% | 116 |

## Data And Execution Assumptions

- Metric start: `2017-01-01`.
- Requested end: `2026-06-30`.
- Standalone effective start/end: `2017-01-03` to `2026-06-30`.
- Continuous warmup/effective metric window: `2007-01-04` warmup, metrics from `2017-01-03` to `2026-06-30`.
- This is proxy diagnostic research, not formal production ETF execution.
- Calendar: repo-local A-share trading-day cache.
- US proxies: Yahoo Finance adjusted close, reindexed to the A-share calendar and forward-filled by rule.
- ChiNext proxy: Eastmoney `0.399006` index close / price index.
- Cost model: one-way cost `0.001`; stale trade legs on forward-filled prices are blocked by the base staged-entry path.
- Execution: close-to-close diagnostic helper path, same as the 2007-2016 proxy layered tests.

## Source Audit

### standalone_reset_2017

| code          | name                            | source                                  | adjustment                | first_available   | first_used   | last       |   rows | pool_rule                                                  | last_aligned   |   ffill_days_on_cn_calendar |
|:--------------|:--------------------------------|:----------------------------------------|:--------------------------|:------------------|:-------------|:-----------|-------:|:-----------------------------------------------------------|:---------------|----------------------------:|
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY      | Yahoo Finance chart API                 | adjusted close            | 2016-11-02        | 2017-01-03   | 2026-06-30 |   2426 | core asset available from 2007 start                       | 2026-06-30     |                          78 |
| EWG           | GERMANY_EWG_ADJ_CLOSE_PROXY     | Yahoo Finance chart API                 | adjusted close            | 2016-11-02        | 2017-01-03   | 2026-06-30 |   2426 | core asset available from 2007 start                       | 2026-06-30     |                          78 |
| EWJ           | JAPAN_EWJ_ADJ_CLOSE_PROXY       | Yahoo Finance chart API                 | adjusted close            | 2016-11-02        | 2017-01-03   | 2026-06-30 |   2426 | core asset available from 2007 start                       | 2026-06-30     |                          78 |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY        | Yahoo Finance chart API                 | adjusted close            | 2016-11-02        | 2017-01-03   | 2026-06-30 |   2426 | core asset available from 2007 start                       | 2026-06-30     |                          78 |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_ADD | Eastmoney push2his kline secid=0.399006 | index close / price index | 2010-06-01        | 2010-06-01   | 2026-06-30 |   3903 | dynamic asset; no prices before 2010-06-01 and no backfill | 2026-06-30     |                           0 |

### continuous_state_from_2007

| code          | name                            | source                                  | adjustment                | first_available   | first_used   | last       |   rows | pool_rule                                                  | last_aligned   |   ffill_days_on_cn_calendar |
|:--------------|:--------------------------------|:----------------------------------------|:--------------------------|:------------------|:-------------|:-----------|-------:|:-----------------------------------------------------------|:---------------|----------------------------:|
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY      | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2026-06-30 |   4943 | core asset available from 2007 start                       | 2026-06-30     |                         158 |
| EWG           | GERMANY_EWG_ADJ_CLOSE_PROXY     | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2026-06-30 |   4943 | core asset available from 2007 start                       | 2026-06-30     |                         158 |
| EWJ           | JAPAN_EWJ_ADJ_CLOSE_PROXY       | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2026-06-30 |   4943 | core asset available from 2007 start                       | 2026-06-30     |                         158 |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY        | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2026-06-30 |   4943 | core asset available from 2007 start                       | 2026-06-30     |                         158 |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_ADD | Eastmoney push2his kline secid=0.399006 | index close / price index | 2010-06-01        | 2010-06-01   | 2026-06-30 |   3903 | dynamic asset; no prices before 2010-06-01 and no backfill | 2026-06-30     |                           0 |

## Artifacts

- Metrics: `outputs\subd_proxy_dynamic_cyb_r2none_final_main_oos_2017_2026ytd_20260702\metrics.csv`
- Yearly returns: `outputs\subd_proxy_dynamic_cyb_r2none_final_main_oos_2017_2026ytd_20260702\yearly_returns.csv`
- Daily curves: `outputs\subd_proxy_dynamic_cyb_r2none_final_main_oos_2017_2026ytd_20260702\daily_curves.csv`
- Sources: `outputs\subd_proxy_dynamic_cyb_r2none_final_main_oos_2017_2026ytd_20260702\sources.csv`
- Metadata: `outputs\subd_proxy_dynamic_cyb_r2none_final_main_oos_2017_2026ytd_20260702\metadata.json`
