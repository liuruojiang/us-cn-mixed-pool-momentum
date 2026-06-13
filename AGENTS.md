# Agent Notes

Use this repo-local file as the source of workspace guidance for the mixed US/A-share momentum workspace at `D:\动量策略\美股A股混合池子动量策略`. Do not depend on a user-home `AGENTS.md` or any machine-local Codex configuration path.

## CNFin Notes

- Treat CNFin (`cnfin.com`, API host `quotedata.cnfin.com`) as a usable realtime or near-realtime candidate for A-share quotes, major China indices, ETFs, market-cap sorting, and raw daily/intraday kline probes.
- CNFin raw kline data should be treated as unadjusted unless separately validated.
- ETF `market_value` and `total_shares` may be missing or zero; validate fund-size fields through another source before use.
- CNFin code format is suffix-based, such as `600519.SS`, `000001.SZ`, `000300.SS`, and `510300.SS`; convert explicitly from Eastmoney-style codes.
- For any new data-source decision, compare prices, dates, and row counts against at least one independent source before trusting the result.

## Local Scan Notes

- For Sub-D / weighted-slope / ETF-pool experiments, keep same data slices, cost assumptions, and execution timing when comparing against Strategy A, ADK, or other sleeves.
- Preserve docs records for accepted conclusions; old `outputs/` files are diagnostic unless rebuilt or cited as preserved evidence.
- New strategy tests and candidate promotions must follow `docs/new_strategy_test_standard_process.md`; every display/report must include full sample, 10Y, 5Y, 3Y, and 1Y annualized return plus max drawdown, or explicit `N/A` reasons.
