# Agent Notes

## QVeris Data Source Defaults

When QVeris is available in this workspace, treat it as the preferred paid data source for market-data probes and research inputs that it supports.

Use QVeris first for:

- Live or near-realtime A-share market data when the required endpoint exists.
- A-share breadth, constituent, industry, and historical-quotation probes where QVeris coverage has been verified.
- Cross-checking public/free sources before trusting an Eastmoney, Sina, CNFin, or other scraped/public response.
- Any workflow where paid-source reliability materially affects a live signal, latest pool, or market-state answer.

Operational rules:

- Read credentials only from environment variables such as `QVERIS_API_KEY`; never print, store, or write API keys into reports.
- For a new QVeris endpoint or schema, run a small probe first and record tool id, parameters, date range, row counts, and freshness.
- Prefer QVeris over free public sources when both cover the same required field and the QVeris response is fresh.
- Still cross-check against an independent source when making a new data-source decision or when freshness is uncertain.
- For live microcap or realtime signal work, keep QVeris as the primary feed when available and use Tencent as a freshness cross-check when feasible.

## CNFin Data Source Defaults

When choosing A-share market data sources in this workspace, treat Xinhua Finance / CNFin (`cnfin.com`) as a usable realtime and near-realtime candidate source.

Observed source:

- Web page: `https://www.cnfin.com/quote/stock/index.html`
- API host: `https://quotedata.cnfin.com`
- Frontend config source: `https://www.cnfin.com/static/js/hs/config.js`
- Local probe script: `probe_cnfin_data_source.py`
- Latest probe output at time of writing: `outputs/cnfin_probe_20260501_142151.md`

Use CNFin for:

- A-share realtime or last-trading-day quotes.
- Major China indices such as `000300.SS` and `000852.SS`.
- Exchange-traded funds such as `510300.SS` and `159915.SZ`, for price fields.
- Whole-market or board-level sorting, including market-cap ranking pools.
- Daily, weekly, monthly, yearly, and intraday raw kline probes.
- Cross-checking Eastmoney when Eastmoney is flaky.

Do not assume CNFin is enough for:

- Backtest-grade adjusted historical data.
- Dividend-adjusted or split-adjusted series.
- Delisting-complete historical universes.
- ETF size or shares-outstanding factors without separate validation.
- Any production signal where corporate actions or point-in-time constituents are central.

Important observed limitations:

- CNFin raw kline data appeared unadjusted in the probe; do not use it as a replacement for a validated adjusted-history source without a separate adjustment check.
- ETF `market_value` and `total_shares` can be `0`; price fields were valid in the sample, but fund-size fields need another source or explicit validation.
- Search endpoints tested as `/quote/v1/search?...` returned unsupported-function errors; use known code mappings or sort results instead.
- Code format is suffix-based: `600519.SS`, `000001.SZ`, `000300.SS`, `510300.SS`. Convert explicitly from Eastmoney-style `1.600519` / `0.000001`.

Useful endpoints:

- Market summary:
  `GET /quote/v1/market/summary?en_finance_mic=SS,SZ`
- Realtime batch:
  `GET /quote/v1/real?en_prod_code=600519.SS,000001.SZ&fields=prod_name,last_px,px_change,px_change_rate,preclose_px,open_px,high_px,low_px,business_amount,business_balance,market_date,trade_status,data_timestamp,market_value,circulation_value,total_shares`
- Market-cap sorting:
  `GET /quote/v1/sort?sort_field_name=market_value&sort_type=0&start_pos=0&data_count=100&en_hq_type_code=SS.ESA.M,SZ.ESA.M,SZ.ESA.SMSE,SZ.ESA.GEM,SS.KSH&fields=prod_name,last_px,market_value,preclose_px,market_date,trade_status,data_timestamp`
- Daily kline:
  `GET /quote/v1/kline?prod_code=600519.SS&candle_period=6&get_type=range&start_date=YYYYMMDD&end_date=YYYYMMDD&fields=open_px,high_px,low_px,close_px,business_amount,business_balance`

Kline periods observed:

- `1`: 1-minute
- `2`: 5-minute
- `3`: 15-minute
- `4`: 30-minute
- `5`: 60-minute
- `6`: daily
- `7`: weekly
- `8`: monthly
- `9`: yearly

Source-selection rule:

- For live microcap or realtime signal work, keep the established QVeris-first rule when QVeris is available, and use Tencent as a freshness cross-check when feasible.
- Use CNFin as an additional fallback or cross-check source, especially when Eastmoney is unstable.
- Use Eastmoney only after checking freshness and response stability for the concrete query.
- For any new data source decision, run or adapt `python .\probe_cnfin_data_source.py` and compare prices, dates, and row counts against at least one independent source before trusting the result.

Evidence from the 2026-05-01 probe:

- CNFin returned `market_date=20260430`, `delay_mins=0` for Shanghai and Shenzhen summaries.
- Batch realtime quotes for `600519.SS`, `000001.SZ`, `000300.SS`, `000852.SS`, `510300.SS`, and `159915.SZ` matched Eastmoney on latest price and percentage change.
- Market-cap sort returned 100 rows in the default probe and 5201 rows when manually tested with `data_count=6000`.
- `600519.SS` daily kline from `20240101` to `20260430` returned 562 rows.
