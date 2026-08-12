# Poe SubD 1.1 / 1.3 P1 Correctness Repair Record

> Superseded status (2026-08-12): V1.1 now has a hard post-drift 1.5x exposure cap, finite/positive NAV guards, bounded live stale-if-error reuse, and symmetric runner/Poe validation. V1.3 continues to provide Poe signals; cross-market timing and FX limitations are advisory and do not globally suppress signals. See `docs/subd_v11_v13_adversarial_repair_20260812.md` for the current state. The deferred statements below are retained as the 2026-07-11 historical record.

Date: 2026-07-11

## Result

The approved correctness-first P1 repair batch is implemented in the current working tree.

- Historical trades using forward-filled buy or sell legs are blocked atomically in the base engine and all exposure overlays.
- Explicit forward-fill masks are validated strictly; live quotes update raw availability instead of being misclassified as stale.
- Final NAV uses the return of the actual carried asset after blocked switches.
- Tencent formal history requires explicit `qfqday`; Yahoo formal history requires explicit `adjclose`.
- Tencent and CNFin pagination failures cannot return partial history/calendar coverage as complete.
- V1.3 formal calendar loss fails closed instead of using `pd.bdate_range`.
- CNFin exchange-holiday boundaries use source-confirmed query coverage; AkShare, forged sources, and old caches remain strict.
- V1.3 proxy output is research-only until cross-market timestamps, executable instruments/fills, and USD/CNY FX are reconciled.
- Performance streamed-response state is request-local through `ContextVar`.

## Files Changed

- `poe_subd_six_etf_v1_1_bot.py`
- `poe_subd_mixed_pool_v1_3_bot.py`
- `tests/test_poe_subd_external_review_regressions.py`
- `tests/test_poe_subd_mixed_pool_v1_3_regressions.py`

The pre-existing modification to `docs/new_strategy_test_standard_process.md` and unrelated research/output files were not changed by this repair batch.

## Backups And Rollback

Primary pre-repair backup:

- `.codex_backups/20260711_022332`

Additional task checkpoints:

- `.codex_backups/20260711_022715`
- `.codex_backups/20260711_024226`
- `.codex_backups/20260711_025927`
- `.codex_backups/20260711_033049`
- `.codex_backups/20260711_091221`

Rollback to the primary backup, if explicitly requested, is a file-for-file restore of the four listed files from `.codex_backups/20260711_022332`. Do not restore the entire repository or delete unrelated user work.

## TDD Evidence

Each production behavior was preceded by an observed failing regression. The RED cases included:

- Tencent `day` accepted as qfq and Yahoo raw `quote.close` accepted as adjusted close.
- Later Tencent pages returning raw-only data or failing after earlier qfq pages.
- CNFin holiday query boundaries rejected, formal V1.3 calendar silently replaced by weekdays, and partial calendar pagination accepted.
- Stale buy, stale sell, staged fill, target-vol, NAV-defense, and overheat transactions completing on forward-filled prices.
- Invalid masks accepted; live quote rows misclassified as stale.
- Actual carried asset NAV calculated from the base strategy asset after a blocked switch.
- Overheat stale exits/re-entries corrupting staged state across recovery days.
- V1.3 formal performance and executable status presented without a reconciled cross-market model.
- Module-global performance-rendered state leaking between request contexts.

The corresponding focused GREEN suites passed after each minimal repair and completed separate specification and code-quality review loops.

## Fresh Integrated Verification

Commands:

```powershell
python -m py_compile poe_subd_six_etf_v1_1_bot.py poe_subd_mixed_pool_v1_3_bot.py
python -m pytest -q
git diff --check
```

Observed result:

- `274 passed, 1 warning in 27.63s`
- Both scripts compiled.
- `git diff --check` exited 0; only existing LF/CRLF conversion warnings were printed.
- The warning is the existing `fastapi_poe` Pydantic V2 deprecation.

## Real-Data Verification

### V1.1 official confirmed build

Attempted `_build_v11_daily` through the official loader for 2026-07-10.

Observed: fail-closed. AkShare/Eastmoney connections were unavailable, and Tencent returned no explicit `qfqday` for `513030.SH`. The loader rejected the raw-only response and did not generate a formal signal or performance curve.

This is safer than the previous mislabeled fallback, but it exposes an operational dependency: V1.1 currently lacks a second available, independently validated qfq provider for every asset.

### V1.3 policy and diagnostic build

- Formal performance returned `BotError` before provider access with the research-only reason.
- The diagnostic build was also fail-closed because no approved qfq source was available for `159985.SZ`.
- No CAGR or drawdown from this blocked run is reported as formal performance.

### Independent recent-source cross-check

For `159915.SZ`, 2026-07-01 through 2026-07-10:

- Tencent explicit `qfqday`: 8 rows, last date 2026-07-10, last close 3.862.
- CNFin raw/unadjusted kline: 8 rows, last date 2026-07-10, last close 3.862.

This validates recent dates, row count, and current price only. It does not prove Tencent's full-history adjustment correctness; CNFin remains raw/unadjusted evidence.

## Market And Execution Assumptions

- V1.1 uses A-share ETF qfq closes, the China trading calendar, a 0.10% one-way cost, and the existing near-close/manual execution convention.
- Historical stale transaction legs are now blocked, but full price-limit, T+1 inventory, liquidity, market-impact, and next-open execution modelling remain deferred.
- V1.1 target-vol may exceed 100% exposure; financing cost and a hard post-drift leverage cap remain deferred and must stay disclosed.
- V1.3 is research-only. It has no formal common-currency NAV, executable proxy mapping, or cross-market next-session fill model.

## Deferred Reviewed Risks

- Rebuild V1.1 target-vol from the drift-aware base curve.
- Rebuild V1.3 NAV defense from the drift-aware base NAV if V1.3 formal research resumes.
- Add financing cost and hard leverage controls.
- Add cache single-flight and a maximum stale-if-error age.
- Reject non-finite performance values and bound relative-date input.
- Add explicit historical price-limit, liquidity, T+1, and executable-price modelling.
- Establish independently validated redundant qfq sources before restoring reliable live availability.

## 2026-08-07 Poe Display Policy Supersession

The V1.3 policy-only Poe display block is superseded. Poe is a reporting surface and does not submit orders, so signal, performance, NAV-curve, and trade-record queries are displayed normally without research-only or non-executable banners.

This does not reverse the P1 data-integrity repairs. Cross-market timestamp alignment, executable-instrument mapping, next-session fill modelling, and USD/CNY conversion remain limitations of the displayed calculations; adjusted-price provenance, calendar validation, partial-response rejection, stale-transaction blocking, and request-local response state remain enforced.

## 2026-08-07 Tencent `day` Field Verification Supersession

Tencent's qfq request currently returns the payload field `day`, rather than `qfqday`, for exactly three V1.1 pool members. Full-history close series were compared against Eastmoney `fqt=1` qfq data through 2026-08-07:

| Code | Coverage | Rows | Maximum close difference |
| --- | --- | ---: | ---: |
| `513030.SH` | 2014-09-05 through 2026-08-07 | 2,895 | 0.001 |
| `513520.SH` | 2019-06-25 through 2026-08-07 | 1,729 | 0.001 |
| `159985.SZ` | 2019-12-05 through 2026-08-07 | 1,618 | 0.001 |

Each comparison had identical date coverage and row count. The only non-zero close differences were five observations from 2020-08-21 through 2020-08-27, all exactly one ETF price tick (0.001). The loader therefore accepts Tencent `day` only for these three explicitly verified codes when the request itself specifies qfq, and records separate provenance for this path.

The fail-closed controls remain in force: non-allowlisted `day` payloads are rejected, a `qfqday`/`day` field change between pages is rejected, partial histories are rejected, and adjusted-close continuity is checked before the data can feed a signal.

## 2026-08-07 159985.SZ Cross-Validated Poe Fallback

V1.1 and V1.3 now retain the original qfq provider order and add one code-specific last resort for `159985.SZ`: the exact-date intersection of direct Sina raw daily closes and CNFin raw daily closes. The fallback requires both sources, listing coverage from 2019-12-05, at least 500 common rows, at least 99% coverage of the shorter series, maximum absolute close difference of 0.001, and the existing continuity guard.

The source is labelled `raw/unadjusted cross-validated`, never qfq. It is not available to any other instrument and fails closed if either provider fails or the two series disagree.

The 2026-08-07 real-source probe produced the same result in both self-contained Poe scripts: Sina returned 1,617 rows from 2019-12-05 through 2026-08-06 with last close 2.119; CNFin returned 1,618 rows from 2019-12-05 through 2026-08-07 with last close 2.118. Their exact-date intersection contained 1,617 rows, covered 100% of the shorter series, and had maximum absolute close difference 0.000. A diagnostic run with all three qfq loaders forced unavailable selected this cross-validated source in both V1.1 and V1.3.
