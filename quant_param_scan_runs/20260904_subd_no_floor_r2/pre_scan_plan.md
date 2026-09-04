# R2 retest on no-floor baseline

- Single parameter: R2 threshold. Keep 25-day window, SCORE_MIN=-inf, SCORE_MAX=5, linear recency weights, Top1, full entry, Buffer=1, overheat/target-vol OFF. No production changes.
- Grid: off, 0, .01, .025, .05, .075, .10, .125, .15, .175, .20, .225, .25, .275, .30, .325, .35, .375, .40, .45, .50, .60, .70, .80, .90.
- Reuse frozen Tencent qfq panel 2011-12-09 to 2026-09-02, 3578 rows. Preserve available-asset history and stale-price flags. This is not a fixed-six common-history formal sample. No data refresh.
- One-way cost .001 inclusive of aggregate fees/slippage, cash return zero, no leverage, close signal/close fill with new holding earning next-row return. No detailed liquidity/price-limit/T+1 or opening-impact modeling.
- Precompute official score function outputs with no lower floor, filter cached results by R2, execute official runner. Verify off curve against accepted no-floor artifact, zero vs off, uncached .20 and independent Poe .20. Fail on any daily absolute difference >1e-12.
- Five required windows; compare against R2-off on same no-floor baseline. Predeclared filter acceptance: Full/10Y/5Y annualized losses <=1pp, 3Y/1Y losses <=3pp; Full MDD improvement positive and at least 3 windows' MDD improved. No post-result widening of tolerance; seek adjacent passing thresholds, not isolated best point.
- The R2 window remains tied to fixed 25-day momentum regression; independently varying window is a separate parameter and is not part of this turn.
- Diagnose negative-momentum selections as R2 is sign-agnostic. Do not add a sign gate or reintroduce the score floor during this test.
- No independent OOS; repeated overlapping retrospective windows. Stop after results and await user confirmation.
