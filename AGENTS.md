# Agent Notes

Common rules live in `C:\Users\Administrator.DESKTOP-95I7VVU\AGENTS.md`. This file only adds local rules for the mixed US/A-share momentum workspace.

## CNFin Notes

- Treat CNFin (`cnfin.com`, API host `quotedata.cnfin.com`) as a usable realtime or near-realtime candidate for A-share quotes, major China indices, ETFs, market-cap sorting, and raw daily/intraday kline probes.
- CNFin raw kline data should be treated as unadjusted unless separately validated.
- ETF `market_value` and `total_shares` may be missing or zero; validate fund-size fields through another source before use.
- CNFin code format is suffix-based, such as `600519.SS`, `000001.SZ`, `000300.SS`, and `510300.SS`; convert explicitly from Eastmoney-style codes.
- For any new data-source decision, compare prices, dates, and row counts against at least one independent source before trusting the result.

## Local Scan Notes

- For Sub-D / weighted-slope / ETF-pool experiments, keep same data slices, cost assumptions, and execution timing when comparing against Strategy A, ADK, or other sleeves.
- Preserve docs records for accepted conclusions; old `outputs/` files are diagnostic unless rebuilt or cited as preserved evidence.
