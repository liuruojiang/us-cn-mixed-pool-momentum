# No-floor Score upper-veto retest

- Research-only. Test one parameter, stop for user confirmation. No R2 scan in this run.
- Baseline: SCORE_MIN=-inf; SCORE_MAX=5; LOOKBACK=25; linear recency weights; Top1; full entry; Buffer=1; R2, overheat, target-vol OFF; cash yield zero; 0.10% one-way cost.
- Grid: 2, 3, 4, 4.5, 5, 5.5, 6, 6.5, 7, 8, 10, infinity.
- Frozen historical Tencent qfq panel, 2011-12-09 to 2026-09-02, 3578 rows; preserve pre-inception missing values and stale-price flags. Full-history sample inherits expanding availability and is not a fixed-six common-history test.
- Reuse official run_staged_entry and calc_scores; runtime globals restored in finally. Match prior no-floor artifact and independent Poe implementation at cap 5. Fail if NAV difference exceeds 1e-10 or other daily fields exceed 1e-12.
- Evaluate all five required windows. Benchmark is no-floor/cap-5, not old floor-zero curve. Do not pick a Full/1Y maximum without neighbors.
- Core width diagnostic: connected sampled neighbors each side must retain 80% of cap-5 Full CAGR. Explicitly report whether both sides pass; do not infer continuous stability between grid points.
- Alternative DD-control rule predeclared: Full/10Y/5Y CAGR loss <=1pp, 3Y/1Y <=3pp, positive Full MDD improvement and improvements in at least three windows. Pareto and return-heavy candidates may be watchlist only. No automatic production promotion.
- Cash and execution exposure, modeled cost and turnover included; no orderbook liquidity, detailed limit-price/T+1 simulation or separate open-impact. Close-signal/close-fill research convention does not establish executable live fills.
- Five windows overlap; no untouched OOS and no universe-survivorship validation in this run.
