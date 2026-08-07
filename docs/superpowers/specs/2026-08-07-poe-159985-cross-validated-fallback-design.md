# Poe 159985 Cross-Validated Fallback Design

Date: 2026-08-07

## Goal

Keep the V1.1 and V1.3 Poe report paths available when every approved qfq provider for `159985.SZ` is unavailable, without relabelling an unadjusted series as qfq or weakening the historical-source policy for any other instrument.

## Observed Failure

The Poe runtime reported this provider chain:

- AkShare unavailable because the package is not installed.
- Tencent returned neither an accepted `qfqday` nor the locally verified `day` payload.
- Eastmoney `push2his` disconnected before returning data.

Direct probes on 2026-08-07 established:

- Sina direct daily kline: 1,617 raw rows, `2019-12-05` through `2026-08-06`.
- CNFin daily kline: 1,618 raw rows, `2019-12-05` through `2026-08-07`.
- Tencent locally verified daily series: 1,618 rows over the same full range as CNFin.
- Tencent versus CNFin maximum absolute close difference: `0.001`.
- Eastmoney `push2his` disconnected and the alternate `push2` host returned HTTP 502.
- Sina's qianfuquan endpoint returned an empty payload, so Sina must not be described as an adjusted source.

## Scope

- Add a Poe-native direct Sina daily-close loader to both self-contained bot scripts.
- Add a Poe-native CNFin daily-close loader for `159985.SZ` to both scripts.
- Add a code-specific cross-validator that returns only the intersection of dates present in both sources.
- Add the cross-validated raw pair as the last provider for `159985.SZ` after AkShare qfq, Tencent, and Eastmoney qfq fail.
- Preserve transparent source and adjustment metadata.
- Add matching regression coverage for V1.1 and V1.3.

## Non-Goals

- Do not accept Sina raw or CNFin raw for any code other than `159985.SZ`.
- Do not accept either raw source alone.
- Do not add Yahoo adjusted close in this change.
- Do not change strategy parameters, scores, holdings, exposure, costs, calendars, or performance calculations.
- Do not weaken the existing qfq validation for the original three providers.
- Do not add AkShare or any other dependency to Poe.

## Design

### Direct source loaders

`_load_sina_raw_one_close()` calls Sina's public daily-kline endpoint directly with `requests`, normalizes `day` and `close`, rejects empty/non-finite/non-positive data, removes duplicate dates, and clips to the requested end date. It does not use AkShare.

`_load_cnfin_raw_one_close()` calls `https://quotedata.cnfin.com/quote/v1/kline` with CNFin code `159985.SZ`, daily candle period `6`, explicit date bounds, and close fields. It normalizes `min_time` and `close_px`, rejects malformed pages and partial pagination, removes duplicate dates, and clips to the requested interval.

Both loaders label their output as raw/unadjusted.

### Runtime cross-validation

`_load_cross_validated_raw_one_close()` is restricted to `159985.SZ` and performs these checks:

1. Both loaders must succeed independently.
2. Both series must include the listing date `2019-12-05`; no pre-listing backfill is allowed.
3. Use only the exact date intersection; a newer row present in only one source is excluded.
4. The intersection must contain at least 500 rows and at least 99% of the shorter source's rows.
5. The absolute close difference on every common date must be at most `0.001` plus floating-point tolerance.
6. The accepted intersection must pass the existing adjusted-close continuity guard, including finite, positive prices and the 35% maximum one-day absolute-return check.

If any check fails, the fallback fails closed and the original provider error remains visible with Sina/CNFin diagnostics appended.

### Provider routing and metadata

The existing qfq provider order remains unchanged:

1. AkShare Eastmoney qfq
2. Tencent qfq or independently verified Tencent `day`
3. Eastmoney `fqt=1`
4. Sina + CNFin cross-validated raw, only for `159985.SZ`

The fourth source uses a distinct adjustment label such as `raw/unadjusted cross-validated`, not `qfq/front-adjusted`. The historical-source validator accepts that label only when all of these match exactly:

- code: `159985.SZ`
- source: `Sina direct + CNFin quote kline`
- source detail: the cross-validation contract identifier
- adjustment: `raw/unadjusted cross-validated`

All other rows still have to satisfy the existing qfq allowlist.

### Shared-script consistency

V1.1 and V1.3 remain self-contained Poe scripts, so the loader, validator, constants, provider routing, and tests are applied symmetrically. The source code is duplicated intentionally to preserve Poe deployment compatibility.

## Error Handling

- HTTP errors, malformed payloads, empty rows, pagination failures, missing listing coverage, insufficient overlap, date mismatches, price disagreements, and continuity failures all reject the fallback.
- Provider exceptions are truncated in the final Poe error as today, while unit tests retain the precise rejection reason.
- A single-source raw result is never silently used.
- No user-facing research-only or non-executable reminder is reintroduced.

## Testing

Implementation follows red-green-refactor:

1. Direct Sina parsing and validation tests without AkShare.
2. CNFin parsing, pagination, and malformed-payload tests.
3. Cross-validator acceptance for matching sources with a one-row freshness difference.
4. Rejection tests for unsupported codes, missing listing coverage, insufficient overlap, close differences above `0.001`, and discontinuities.
5. Provider-chain tests proving the cross-validated source is attempted only after all qfq sources fail and that its metadata passes the code-specific validator.
6. Equivalent focused tests for both Poe scripts.
7. Real remote probes recording rows, date range, last common date, and maximum source difference.
8. Script compilation, focused regression suites, full pytest, and `git diff --check`.

## Acceptance Criteria

- V1.1 and V1.3 can load `159985.SZ` without AkShare when qfq providers fail but Sina and CNFin agree.
- The accepted fallback contains only common dates and never labels raw data as qfq.
- No other instrument can use the raw fallback.
- Any source disagreement or incomplete history fails closed.
- Existing strategy calculations and display behavior are unchanged.
