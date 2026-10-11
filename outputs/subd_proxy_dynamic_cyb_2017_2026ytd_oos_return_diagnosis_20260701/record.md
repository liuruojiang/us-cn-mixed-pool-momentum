# Sub-D OOS Return Diagnosis

## Finding

- The low return in the prior two-line OOS table is caused by the selected `R2=0.50` carried lines being much more defensive than the original mixed-pool momentum strategy.
- It is not explained by 2017 cold start or by `SCORE_MAX=5`; the continuous-state check still shows the same pattern.
- This diagnosis uses 2007 warmup/state history and reports metrics from the 2017 OOS window onward.

## Comparison

| Candidate | Group | R2 | Target Vol | Overheat | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Cash Ratio | Avg Exposure |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `orig_full_v1_1_reference` | original_full_chain | 0.2 | 0.25 | original_ma60 | 16.33% | -33.78% | N/A | N/A | 20.78% | -33.78% | 31.86% | -18.36% | 22.50% | -18.18% | 15.77% | 104.27% |
| `A_clean_scoremax_5_overheat_off` | selected_two_line | 0.5 | off | off | 11.73% | -30.71% | N/A | N/A | 13.01% | -24.68% | 17.42% | -24.68% | 44.74% | -9.13% | 28.45% | 67.62% |
| `G_decay_nav_scoremax_5_overheat_off` | selected_two_line | 0.5 | off | off | 9.68% | -27.09% | N/A | N/A | 11.27% | -21.97% | 15.66% | -21.97% | 40.67% | -9.13% | 28.45% | 59.88% |
| `A_clean_r2_0p0_scoremax_5_overheat_off` | clean_r2_sensitivity | 0.0 | off | off | 23.68% | -20.31% | N/A | N/A | 22.14% | -19.60% | 30.26% | -18.38% | 32.33% | -18.38% | 5.99% | 89.55% |
| `A_clean_r2_0p2_scoremax_5_overheat_off` | clean_r2_sensitivity | 0.2 | off | off | 20.36% | -25.79% | N/A | N/A | 22.25% | -19.19% | 27.67% | -13.76% | 32.41% | -13.76% | 15.20% | 80.35% |
| `A_clean_r2_0p3_scoremax_5_overheat_off` | clean_r2_sensitivity | 0.3 | off | off | 17.17% | -32.33% | N/A | N/A | 20.45% | -20.37% | 25.23% | -15.30% | 31.42% | -15.30% | 18.90% | 76.95% |
| `A_clean_r2_0p4_scoremax_5_overheat_off` | clean_r2_sensitivity | 0.4 | off | off | 14.80% | -33.49% | N/A | N/A | 17.19% | -21.90% | 20.79% | -21.90% | 42.38% | -10.50% | 23.20% | 72.81% |
| `A_clean_r2_0p5_scoremax_5_overheat_off` | clean_r2_sensitivity | 0.5 | off | off | 11.73% | -30.71% | N/A | N/A | 13.01% | -24.68% | 17.42% | -24.68% | 44.74% | -9.13% | 28.45% | 67.62% |

## Window

- Warmup/state start: `2007-01-01`.
- Metric start: `2017-01-01`.
- Effective metric start: `2017-01-03`.
- End: `2026-06-30`.
- OOS rows: `2302`.
- 10Y is N/A because the OOS window has fewer than 2520 A-share sessions.

## Source Audit

| code          | name                            | source                                  | adjustment                | first_available   | first_used   | last       |   rows | pool_rule                                                  | last_aligned   |   ffill_days_on_cn_calendar |
|:--------------|:--------------------------------|:----------------------------------------|:--------------------------|:------------------|:-------------|:-----------|-------:|:-----------------------------------------------------------|:---------------|----------------------------:|
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY      | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2026-06-30 |   4943 | core asset available from 2007 start                       | 2026-06-30     |                         158 |
| EWG           | GERMANY_EWG_ADJ_CLOSE_PROXY     | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2026-06-30 |   4943 | core asset available from 2007 start                       | 2026-06-30     |                         158 |
| EWJ           | JAPAN_EWJ_ADJ_CLOSE_PROXY       | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2026-06-30 |   4943 | core asset available from 2007 start                       | 2026-06-30     |                         158 |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY        | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2026-06-30 |   4943 | core asset available from 2007 start                       | 2026-06-30     |                         158 |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_ADD | Eastmoney push2his kline secid=0.399006 | index close / price index | 2010-06-01        | 2010-06-01   | 2026-06-30 |   3903 | dynamic asset; no prices before 2010-06-01 and no backfill | 2026-06-30     |                           0 |
