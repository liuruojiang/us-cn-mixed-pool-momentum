# Sub-D Proxy CYB Dynamic 2007-2016 Layer 0

## Scope

- Layer: 0 / data availability, dynamic proxy pool definition, and unchanged V1.0/V1.1 baseline reproduction.
- Dynamic rule: before ChiNext exists, run the four overseas proxies `QQQ`, `EWG`, `EWJ`, `GLD`; after ChiNext official publication, `CN_CYB_399006` joins naturally once enough lookback data exists.
- Soymeal leg is removed.
- This is proxy research, not a production ETF formal result.

## Data And Execution Assumptions

- Test start: `2007-01-04`.
- End date: `2016-12-30`.
- ChiNext official evidence: https://www.cnindex.com.cn/zh_information/notices_news/2010/201207/P020191213351726460465.pdf.
- Calendar: China trading sessions from SSE Composite `1.000001`, used only as a session calendar.
- US proxy data source: Yahoo Finance chart API adjusted close.
- ChiNext source: Eastmoney `0.399006` daily close; no pre-publication data is used.
- Costs and overlays: unchanged V1.1 function chain, one-way cost `0.001`, R2 threshold `0.20`, target vol `0.25`, max leverage `1.5`, 50% staged entry, MA60 same-side overheat.

## Mandatory Window Baseline

| Window | Start | End | Ann. Return | Max Drawdown | Reason |
|---|---:|---:|---:|---:|---|
| Full | 2007-01-04 | 2016-12-30 | 11.84% | -36.96% |  |
| 10Y | N/A | 2016-12-30 | N/A | N/A | insufficient rows: 2432 < 2520 trading days after 2007-01-04 |
| 5Y | 2011-10-28 | 2016-12-30 | 12.61% | -36.96% |  |
| 3Y | 2013-11-29 | 2016-12-30 | 3.41% | -36.96% |  |
| 1Y | 2015-12-22 | 2016-12-30 | -26.98% | -36.96% |  |

## Dynamic Join Dates

- ChiNext official publication date: `2010-06-01`.
- First post-filter selectable score dates: `{"QQQ": "2007-02-26", "EWG": "2007-02-07", "EWJ": "2007-02-07", "GLD": "2007-02-07", "CN_CYB_399006": "2010-07-28"}`.

## Source Audit

| code          | name                                        | source                                  | adjustment                  | publication_or_inception   | raw_first   | first_used   | last       |   rows | note                                                                                         |
|:--------------|:--------------------------------------------|:----------------------------------------|:----------------------------|:---------------------------|:------------|:-------------|:-----------|-------:|:---------------------------------------------------------------------------------------------|
| CN_CALENDAR   | SSE_COMPOSITE_CALENDAR_ONLY                 | Eastmoney push2his kline secid=1.000001 | index close / calendar only |                            | 2007-01-04  | 2007-01-04   | 2016-12-30 |   2432 | Used only to define China trading sessions before ChiNext exists.                            |
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY                  | Yahoo Finance chart API                 | adjusted close              | 2006-12-01                 | 2006-12-01  | 2006-12-01   | 2016-12-30 |   2538 | Reindexed to China trading sessions for this proxy diagnostic.                               |
| EWG           | GERMANY_EWG_ADJ_CLOSE_PROXY                 | Yahoo Finance chart API                 | adjusted close              | 2006-12-01                 | 2006-12-01  | 2006-12-01   | 2016-12-30 |   2538 | Reindexed to China trading sessions for this proxy diagnostic.                               |
| EWJ           | JAPAN_EWJ_ADJ_CLOSE_PROXY                   | Yahoo Finance chart API                 | adjusted close              | 2006-12-01                 | 2006-12-01  | 2006-12-01   | 2016-12-30 |   2538 | Reindexed to China trading sessions for this proxy diagnostic.                               |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY                    | Yahoo Finance chart API                 | adjusted close              | 2006-12-01                 | 2006-12-01  | 2006-12-01   | 2016-12-30 |   2538 | Reindexed to China trading sessions for this proxy diagnostic.                               |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_FROM_2010_06_01 | Eastmoney push2his kline secid=0.399006 | index close / price index   | 2010-06-01                 | 2010-06-01  | 2010-06-01   | 2016-12-30 |   1601 | Not eligible before official publication; naturally joins after enough lookback data exists. |

## Artifacts

- Summary: `outputs\subd_proxy_cyb_dynamic_2007_2016_layer0\summary.csv`
- Daily curves: `outputs\subd_proxy_cyb_dynamic_2007_2016_layer0\daily_curves.csv`
- Sources: `outputs\subd_proxy_cyb_dynamic_2007_2016_layer0\sources.csv`
- Asset metrics: `outputs\subd_proxy_cyb_dynamic_2007_2016_layer0\asset_metrics.csv`
- Metadata: `outputs\subd_proxy_cyb_dynamic_2007_2016_layer0\metadata.json`

## Stop Point

Layer 0 is complete. Next layer is Layer 1 raw weighted-slope parameter width test; do not continue without explicit approval.
