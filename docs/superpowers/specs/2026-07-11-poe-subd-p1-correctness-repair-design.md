# Poe SubD 1.1 / 1.3 P1 Correctness Repair Design

Date: 2026-07-11

## Goal

Remove the confirmed P1 paths that can create non-executable trades, mislabel raw prices as adjusted prices, silently change the trading calendar, use unavailable cross-market closes, or let concurrent Poe requests suppress each other's errors.

Correctness takes priority over retaining historical metrics. Existing V1.3 proxy results become diagnostic until a timestamp-aware, executable, common-currency model is available.

## Scope

This repair batch covers:

1. Block historical trades whose buy or sell leg uses a forward-filled price in both Poe scripts.
2. Remove V1.3's formal use of same-date US and China closes. Keep the proxy engine available only as explicitly labelled diagnostic research; formal performance and executable-signal surfaces must fail closed.
3. Remove V1.3's silent `pd.bdate_range` fallback from formal paths.
4. Require explicit adjustment provenance: Tencent formal history requires `qfqday`; Yahoo formal history requires `adjclose`.
5. Replace process-global performance-rendered flags with request-local state.
6. Complete the calendar-boundary fix so a legitimate exchange holiday at the requested boundary is not inferred to be missing coverage merely because it is a weekday.

## Deferred Scope

The following reviewed issues remain a second batch and must not be hidden by this repair:

- V1.1 target-vol volatility input uses a virtual fixed-fraction base curve.
- V1.3 NAV defense uses a virtual pre-drift NAV.
- Financing cost and hard leverage exposure limits.
- FX conversion and executable instrument mapping for V1.3.
- Historical price-limit, T+1, liquidity, and next-open execution modelling.
- Cache single-flight, maximum stale-if-error age, finite performance validation, and large date-input bounds.

## Design

### 1. Raw availability remains first-class

Price alignment may forward-fill a held asset to represent an unchanged mark during suspension or a closed venue, but a forward-filled value cannot be used as a transaction price.

Both Poe engines will accept an availability/forward-fill mask before state transitions. If either the sell leg or buy leg is stale, the whole rebalance is cancelled for that row. The engine must preserve the previous holding, fraction, pending staged-entry state, counters, and turnover. This matches the existing formal runner's atomic stale-leg rejection rather than merely adding a warning after the trade.

Regression tests must demonstrate that the current code trades on the stale row before the fix and that the repaired code keeps the old position with zero turnover.

### 2. V1.3 cross-market output is diagnostic-only

The current proxy pool mixes US closes, a China price index, and a China ETF without a shared availability timestamp, common currency, or executable instrument mapping. A date-only shift cannot make its P&L executable.

For this batch:

- V1.3 historical construction may remain available to research helpers as a diagnostic proxy curve.
- Poe `performance` output must refuse to present that curve as formal performance and explain the missing timestamp-aware execution and FX model.
- V1.3 signal output may describe the latest proxy ranking, but must be visibly labelled research-only and must never report the proxy legs as executable.
- Existing non-CN proxy execution status remains fail-closed.

A future formal V1.3 design must define an event timestamp, use only bars published before that timestamp, map proxies to actual tradable instruments, model each leg's next executable session/price, and convert all returns to a declared base currency.

### 3. Calendar failures are explicit

Formal V1.3 construction must not replace a missing exchange calendar with `pd.bdate_range`. Calendar failure raises a clear error. If a weekday-only calendar is retained for research, it must require an explicit diagnostic flag and propagate that status into every report.

Calendar coverage validation will distinguish the API request boundary from the first returned trading session. A requested boundary that is a weekend or exchange holiday is valid when the source confirms it queried the full requested interval. The implementation must not treat `weekday() < 5` as proof that a session should exist.

### 4. Adjustment provenance is fail-closed

Tencent `day` and Yahoo raw `close` are not interchangeable with adjusted series.

- Formal Tencent fallback accepts only a non-empty `qfqday` payload.
- Formal Yahoo history accepts only a non-empty `adjclose` payload aligned with timestamps.
- Raw alternatives raise an adjustment-specific error and may only be exposed by a separately labelled diagnostic helper.
- Source metadata must describe the series actually returned.

Tests use split/dividend-like payloads to prove raw fallbacks are rejected.

### 5. Poe request state is isolated

The response-rendered marker becomes request-local, preferably a `ContextVar` reset with a token in `run()` and restored in `finally`. One request must never read another request's rendered state. Tests will interleave two contexts and prove that an unrendered failing request still raises.

## Error Handling

- Formal data-integrity failures raise `poe.BotError` or a domain-specific exception with the affected source and symbol.
- Diagnostic V1.3 surfaces state why formal performance is unavailable; they do not silently substitute a weaker model.
- Atomic stale-trade rejection records the blocked assets and reason without mutating strategy state.
- No provider payload or exception may be relabelled as a stronger adjustment mode than was received.

## Test Strategy

Every production change follows red-green-refactor:

1. Add one focused regression test and run it to observe the expected failure.
2. Apply the smallest implementation change.
3. Run the focused test, then the related test file.
4. Run the full suite and compile both scripts.

Required regression groups:

- Stale sell leg, stale buy leg, and staged-entry state rollback for both engines.
- V1.3 formal performance refusal and research-only signal labelling.
- Calendar failure without a weekday fallback and holiday boundary acceptance.
- Tencent `day` rejection and Yahoo missing-`adjclose` rejection.
- Concurrent/request-local performance response state.

## Data Verification

After unit tests pass:

- Rebuild V1.1 against the real current qfq source and confirm no trade occurs on a forward-filled trade leg.
- Rebuild V1.3 diagnostic output and confirm its status is research-only; do not publish its CAGR or drawdown as formal.
- Cross-check recent A-share prices, dates, and row counts against CNFin or another independent source.
- Record source, adjustment mode, calendar, row counts, sample range, and any unavailable provider.

## Compatibility And Rollback

These fixes intentionally change or disable previously displayed results. No compatibility flag will restore unsafe formal behavior.

Before production edits, create filesystem backups of both Poe scripts and affected tests using the quant-research backup helper. Git history plus the backup directory provide rollback. Existing user modifications and research outputs remain untouched.

## Acceptance Criteria

- New regression tests fail on the pre-fix behavior and pass after repair.
- No historical trade mutates state when either leg is forward-filled.
- Formal loaders never label Tencent `day` or Yahoo raw close as adjusted.
- V1.3 cannot present the current proxy curve as formal executable performance.
- Missing exchange calendars cannot silently become weekday calendars.
- Concurrent requests cannot share the rendered-response flag.
- Both scripts compile, the full test suite passes, and real-data verification is recorded.
