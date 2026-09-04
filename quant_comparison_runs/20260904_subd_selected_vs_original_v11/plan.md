# Selected research line versus original V1.1

- User-requested matched-data comparison; no scan, no promotion, no production writes.
- Original V1.1: call official runner build_curves and select version1.1 (not its V1.0 baseline). Score0..5, R2.20, Buffer1.05,50% staged entry, target vol.25/window80/max leverage1.5/deadband.075, MA60 bias20%/18% derisk0 and original same_side_or_exit recovery.
- Selected line: strict .5<Score<5, R2>=.25,25-day linear regression, Top1 full entry, Buffer1, vol/overheat OFF, no leverage.
- Same frozen Tencent qfq panel2011-12-09 to2026-09-02/3578 rows; existing availability and stale flags; Chinese ETF calendar/Asia-Shanghai. Full/10Y inherit expanding asset availability; not fixed-six common-history formal evidence.
- Both: single-way cost.001, official close-signal/close-trade convention, next-row new-position returns, zero cash yield; no separate financing, open-impact, detailed liquidity/limit-price/T+1 model. Original leverage financing remains excluded as in its existing model, making this a model comparison, not broker-executable PnL.
- Compare Full/10Y/5Y/3Y/1Y official summarize metrics; deltas selected minus original; positive DD delta means shallower.
- Verify original runner/Poe complete overlay parity; selected runner/Poe .5/.25 full-entry parity; selected daily curve against saved accepted r2_0.250. Validate hashes, dates, finite values, costs and final exposure. Abort on mismatch above1e-10 NAV or1e-12 other numeric series.
- Keep code/metadata/metrics/daily curves and report. Five windows overlap; same repeatedly used research sample, no new OOS.
