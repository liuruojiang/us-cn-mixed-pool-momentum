# Sub-D Proxy ZZ500 2007-2016 Layer 0

## Scope

- Layer: 0 / data availability, proxy definition, and unchanged V1.0/V1.1 baseline reproduction.
- A-share leg replacement: CSI500 price index proxy `CN_ZZ500_000905` replaces ChiNext proxy.
- Soymeal leg is removed. Remaining overseas proxies: `QQQ`, `EWG`, `EWJ`, `GLD`.
- This is proxy research, not a production ETF formal result.

## Data And Execution Assumptions

- Formal proxy start: `2007-01-15`.
- End date: `2016-12-30`.
- CSI500 publication evidence: https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000905factsheet.pdf.
- CSI500 data source: Eastmoney `push2his` daily close for `1.000905`; vendor rows before publication are clipped.
- US proxy data source: Yahoo Finance chart API adjusted close.
- Calendar: CSI500 trading dates. US proxy prices are reindexed to this calendar and forward-filled by the official aligner.
- Costs and overlays: unchanged V1.1 function chain, one-way cost `0.001`, R2 threshold `0.20`, target vol `0.25`, max leverage `1.5`, 50% staged entry, MA60 same-side overheat.

## Mandatory Window Baseline

| Window | Start | End | Ann. Return | Max Drawdown | Reason |
|---|---:|---:|---:|---:|---|
| Full | 2007-01-15 | 2016-12-30 | 8.43% | -48.16% |  |
| 10Y | N/A | 2016-12-30 | N/A | N/A | insufficient rows: 2425 < 2520 trading days after 2007-01-15 |
| 5Y | 2011-10-28 | 2016-12-30 | 2.39% | -48.16% |  |
| 3Y | 2013-11-29 | 2016-12-30 | -3.02% | -48.16% |  |
| 1Y | 2015-12-22 | 2016-12-30 | -20.84% | -25.25% |  |

## Source Audit

| code            | name                               | source                                  | adjustment                | publication_or_inception   | raw_first   | first_used   | last       |   rows | note                                                            |
|:----------------|:-----------------------------------|:----------------------------------------|:--------------------------|:---------------------------|:------------|:-------------|:-----------|-------:|:----------------------------------------------------------------|
| CN_ZZ500_000905 | CSI500_INDEX_PROXY_FOR_A_SHARE_LEG | Eastmoney push2his kline secid=1.000905 | index close / price index | 2007-01-15                 | 2007-01-04  | 2007-01-15   | 2016-12-30 |   2425 | Raw vendor rows before CSI publication are clipped.             |
| QQQ             | NASDAQ_QQQ_ADJ_CLOSE_PROXY         | Yahoo Finance chart API                 | adjusted close            | 2006-12-01                 | 2006-12-01  | 2006-12-01   | 2016-12-30 |   2538 | Reindexed to CSI500 trading calendar for this proxy diagnostic. |
| EWG             | GERMANY_EWG_ADJ_CLOSE_PROXY        | Yahoo Finance chart API                 | adjusted close            | 2006-12-01                 | 2006-12-01  | 2006-12-01   | 2016-12-30 |   2538 | Reindexed to CSI500 trading calendar for this proxy diagnostic. |
| EWJ             | JAPAN_EWJ_ADJ_CLOSE_PROXY          | Yahoo Finance chart API                 | adjusted close            | 2006-12-01                 | 2006-12-01  | 2006-12-01   | 2016-12-30 |   2538 | Reindexed to CSI500 trading calendar for this proxy diagnostic. |
| GLD             | GOLD_GLD_ADJ_CLOSE_PROXY           | Yahoo Finance chart API                 | adjusted close            | 2006-12-01                 | 2006-12-01  | 2006-12-01   | 2016-12-30 |   2538 | Reindexed to CSI500 trading calendar for this proxy diagnostic. |

## Artifacts

- Summary: `outputs\subd_proxy_zz500_2007_2016_layer0\summary.csv`
- Daily curves: `outputs\subd_proxy_zz500_2007_2016_layer0\daily_curves.csv`
- Sources: `outputs\subd_proxy_zz500_2007_2016_layer0\sources.csv`
- Asset metrics: `outputs\subd_proxy_zz500_2007_2016_layer0\asset_metrics.csv`
- Metadata: `outputs\subd_proxy_zz500_2007_2016_layer0\metadata.json`

## Stop Point

Layer 0 is complete. Next layer is Layer 1 raw weighted-slope parameter width test; do not continue without explicit approval.
