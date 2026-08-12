# Poe SubD V1.1 / V1.3 External Review Repair Design

## Goal

Verify the external review against the current V1.1 and V1.3 Poe bot implementations, repair confirmed correctness and low-risk engineering defects without changing strategy assumptions, and isolate performance or architecture work that requires separate evidence.

## Scope

The production files in scope are:

- `poe_subd_six_etf_v1_1_bot.py`
- `poe_subd_mixed_pool_v1_3_bot.py`

Regression coverage will stay in the existing Poe test files unless a focused new test file makes the review mapping clearer. The audit outcome will be recorded in a repo-local document so accepted, rejected, and deferred findings remain traceable.

The following strategy assumptions remain unchanged:

- Mandatory 1Y/3Y/5Y/10Y windows continue to mean 252/756/1260/2520 trading rows, matching the repository's established testing standard and prior accepted audit decision.
- V1.3 target-vol remains disabled in the formal build path.
- SELL legs remain fail-closed unless verified sellable quantity is supplied; this round adds disclosure but does not add a broker position source.
- Cross-market signal alignment, holiday compression, cash return, and official-exchange final-close integration are not changed.
- Existing costs, execution timing, data slices, adjustment modes, and live execution permissions are preserved.

## Review Disposition

### Repair in the correctness and hardening patch

1. Replace V1.3's misleading `from_2020` label with an evaluation-start-derived label while preserving `EVAL_START = 2017-01-01`.
2. Make V1.3 mandatory trading-row windows report `N/A` when the requested row count is unavailable instead of accepting a clipped start as a complete window.
4. Generate V1.3 score and R-squared explanatory text from `LOOKBACK`, `SCORE_MIN`, `SCORE_MAX`, and `R2_THRESHOLD`.
5. Update V1.1 historical-source disclosure to describe the existing Sina plus CNFin cross-validated raw fallback accurately.
6. Replace V1.3 live-quote string matching with a dedicated unsupported-symbol exception that is caught consistently at both live-quote entry points.
7. Disclose that SELL legs remain non-actionable without verified sellable quantity.
8. Return `(NaN, NaN)` when V1.3 price-limit bounds are requested for a non-CN symbol instead of allowing `Decimal('NaN')` to raise `InvalidOperation`.
9. Add an explicit source-detail warning before the fixed Sina history cap is exhausted. Do not weaken listing-date validation or silently switch the formal source returned by the cross-validation path.
10. Harden V1.3's dormant target-vol helpers to the validated V1.1 input contract while leaving the formal V1.3 build path at scale 1.0.
11. Derive both AkShare and Eastmoney qfq history start parameters from V1.3 `START_DATE` rather than `20100101`.
12-14. Add visible V1.3 disclosures for US-to-CN timestamp non-executability, CN-holiday compression of US returns, and the monitor-only semantics of Yahoo pre-market/overnight one-minute quotes. These are disclosure changes only.
15. Calculate annual rows from one continuous return series so the first session of each year after the first is not reset to zero. Keep one intentional rebase at the requested report start.
16. Remove the process-global calendar-failure fallback and rely on request-local `ContextVar` state. Protect mutable in-memory cache read/write/clear operations with reentrant locks without holding a lock across unnecessary report formatting.
17. Give V1.1 and V1.3 distinct calendar-cache paths keyed to their required history starts so they cannot overwrite incompatible query-boundary metadata.
18. Preserve retry backoff after price-quality rejection and fetch the V1.3 Yahoo frame once per outer live snapshot rather than once per Eastmoney endpoint attempt.
19. Short-circuit Tencent retries for deterministic missing/changed qfq payload keys while retaining retries for transport and provider failures.
20. Sort daily rows by `date` inside `_execution_legs_status` before selecting the latest row.
21. Use `_bj_today_naive()` for `_build_config()` defaults in both scripts.
23. Change both introduction messages from “query-time refresh” to wording that accurately describes the five-minute confirmed-state cache and live force refresh.
24. Parse an explicit standalone `YYYY-MM-DD` before month/range patterns and return the same date as both start and end.
28. Parse `out['date']` once per metadata-attachment function rather than once per asset.

### Reject or narrow

- Finding 3 is rejected for this workspace. The reviewer assumed calendar-year labels, but the repository explicitly standardized mandatory windows on 252 trading rows per nominal year. The bug is insufficient-history clipping, not the 252-row convention.
- Finding 7 is narrowed to disclosure. Removing the SELL gate without verified broker quantity would weaken live-trading safety.
- Finding 9 is narrowed to warning and audit visibility. A different history-provider contract needs independent-source validation before adoption.
- Finding 10 is resolved by hardening rather than deleting a potentially useful research helper.
- Finding 22 does not justify blanket deletion. Unused-name cleanup will be considered only after a caller/import audit proves the symbols are not compatibility surfaces.

### Benchmark or design follow-up

- Finding 25 has an existing vectorized reference in `run_subd_six_etf_v1_1.py`. It will receive exact-value parity tests and an isolated benchmark before being promoted into either Poe bot.
- Findings 26 and 27 alter state-machine implementation details. They require output-frame parity tests and measured runtime evidence before adoption.
- Finding 29 is architecturally sound as a drift warning, but a shared-core/generator refactor is outside this correctness patch and must be designed separately.

## Implementation Shape

The patch will remain narrow and symmetric:

1. Add regression tests grouped by review finding and watch them fail for the expected current behavior.
2. Back up the two bot scripts before production edits using the quant-research backup tool.
3. Apply correctness fixes one behavior at a time, rerunning the smallest relevant test after each change.
4. Apply paired engineering fixes to both scripts where their implementations are duplicated.
5. Add an audit record mapping each of the 29 findings to `fixed`, `documented`, `rejected`, or `deferred` with the supporting test or source location.
6. Run both focused test files, all repository tests, Python compilation, and the smallest feasible real-data build through each official bot path.

No output artifact, scan result, unrelated documentation change, or existing user modification will be altered.

## Error Handling and Safety

- Live unsupported-symbol handling uses a typed exception, not error-message text.
- Target-vol validation rejects booleans, non-finite values, invalid warmup windows, and non-finite post-warmup returns consistently with V1.1.
- Deterministic Tencent schema failures fail immediately; transient network failures retain retries and backoff.
- Calendar and daily caches remain fail-closed. Locks prevent partial in-memory updates, and request-local failure reasons prevent one request from clearing another request's diagnostic state.
- The Sina cap warning must not make incomplete history appear valid.
- Cross-market disclosures must not change dates, returns, signals, or execution permissions.

## Testing

Regression tests will cover at least:

- V1.3 evaluation-start label generation.
- Short 1Y/3Y/5Y/10Y histories returning explicit `N/A` reasons.
- The preserved 252-row window convention.
- Dynamic V1.3 score/R-squared text and V1.1 source disclosure.
- Typed unsupported-symbol fallback.
- Permanent SELL fail-closed disclosure.
- Non-CN price-limit bounds.
- Sina cap warning propagation.
- V1.3 target-vol input validation parity.
- Dynamic qfq start dates.
- Cross-market and Yahoo live-semantics disclosures.
- Annual-return compounding across a year boundary.
- Request-local calendar failure reasons and cache locking behavior.
- Separate versioned calendar-cache paths.
- Retry backoff, Yahoo fetch reuse, and deterministic Tencent short-circuiting.
- Latest-row selection from unsorted daily input.
- Beijing-date config defaults.
- Confirmed-cache introduction wording.
- Standalone date parsing in both scripts.
- Single date conversion per metadata-attachment call.

Fresh verification will include:

- Focused red/green tests for each repaired behavior.
- `python -m pytest tests/test_poe_subd_external_review_regressions.py tests/test_poe_subd_mixed_pool_v1_3_regressions.py -q`
- `python -m pytest -q`
- `python -m py_compile poe_subd_six_etf_v1_1_bot.py poe_subd_mixed_pool_v1_3_bot.py`
- Official-path real-data rebuilds when the current providers are available; otherwise each blocked provider and the resulting `N/A` status will be recorded without substituting raw data into a formal qfq result.

## Rollback

Rollback uses the filesystem backup created immediately before bot edits. Tests and audit documentation can be reverted independently; no existing research outputs are regenerated or deleted by this change.
