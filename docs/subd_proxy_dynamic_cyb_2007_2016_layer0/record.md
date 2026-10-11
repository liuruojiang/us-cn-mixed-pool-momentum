# Sub-D Dynamic ChiNext Proxy 2007-2016 Layer 0

## Scope

- Layer: 0 / data availability, dynamic-pool definition, and unchanged V1.0/V1.1 baseline reproduction.
- Pool rule: `QQQ`, `EWG`, `EWJ`, and `GLD` participate from the 2007 start; `CN_CYB_399006` joins only after its own data exists.
- ChiNext is not backfilled and CSI500 is not used as an asset.
- This is proxy research, not a production ETF formal result.

## Data And Execution Assumptions

- Effective sample start: `2007-01-04`.
- End date: `2016-12-30`.
- Calendar: repo-local A-share trading-day cache. US proxy adjusted closes are reindexed to this calendar and forward-filled by rule.
- ChiNext rule: no prices before `2010-06-01`; it can only be ranked once a full 25-trading-day slope window exists.
- Costs and overlays: unchanged V1.1 function chain, one-way cost `0.001`, R2 threshold `0.20`, target vol `0.25`, max leverage `1.5`, 50% staged entry, MA60 same-side overheat.

## Mandatory Window Baseline

| Window | Start | End | Ann. Return | Max Drawdown | Reason |
|---|---:|---:|---:|---:|---|
| Full | 2007-01-04 | 2016-12-30 | 11.84% | -36.96% |  |
| 10Y | N/A | 2016-12-30 | N/A | N/A | insufficient rows: 2432 < 2520 trading days |
| 5Y | 2011-10-28 | 2016-12-30 | 12.61% | -36.96% |  |
| 3Y | 2013-11-29 | 2016-12-30 | 3.41% | -36.96% |  |
| 1Y | 2015-12-22 | 2016-12-30 | -26.98% | -36.96% |  |

## Requested Extra Windows

| Window | Start | End | Ann. Return | Max Drawdown |
|---|---:|---:|---:|---:|
| from_2010_06_01_cyb_available | 2010-06-01 | 2016-12-30 | 15.88% | -36.96% |
| from_2011_01_01 | 2011-01-04 | 2016-12-30 | 16.94% | -36.96% |

## Source Audit

| code          | name                            | source                                  | adjustment                | first_available   | first_used   | last       |   rows | pool_rule                                                  | last_aligned   |   ffill_days_on_cn_calendar |
|:--------------|:--------------------------------|:----------------------------------------|:--------------------------|:------------------|:-------------|:-----------|-------:|:-----------------------------------------------------------|:---------------|----------------------------:|
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY      | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWG           | GERMANY_EWG_ADJ_CLOSE_PROXY     | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWJ           | JAPAN_EWJ_ADJ_CLOSE_PROXY       | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY        | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_ADD | Eastmoney push2his kline secid=0.399006 | index close / price index | 2010-06-01        | 2010-06-01   | 2016-12-30 |   1601 | dynamic asset; no prices before 2010-06-01 and no backfill | 2016-12-30     |                           0 |

## Artifacts

- Summary: `outputs\subd_proxy_dynamic_cyb_2007_2016_layer0\summary.csv`
- Extra windows: `outputs\subd_proxy_dynamic_cyb_2007_2016_layer0\extra_windows.csv`
- Daily curves: `outputs\subd_proxy_dynamic_cyb_2007_2016_layer0\daily_curves.csv`
- Sources: `outputs\subd_proxy_dynamic_cyb_2007_2016_layer0\sources.csv`
- Asset metrics: `outputs\subd_proxy_dynamic_cyb_2007_2016_layer0\asset_metrics.csv`
- Metadata: `outputs\subd_proxy_dynamic_cyb_2007_2016_layer0\metadata.json`

## Stop Point

Layer 0 is complete. Next layer is Layer 1 raw weighted-slope parameter width test; do not continue without explicit approval.
