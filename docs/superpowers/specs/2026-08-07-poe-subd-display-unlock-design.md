# Poe SubD V1.1 / V1.3 Display Unlock Design

Date: 2026-08-07

## Goal

Let the Poe bots display their calculated signals and research outputs normally. The bots do not place orders, so the V1.3 display surfaces must not be blocked solely because a cross-market executable-order model is unavailable.

## Scope

- V1.3 `信号` and `实时信号` display normal signal output without `research-only` or `不可执行` banners.
- V1.3 `表现`, `净值曲线`, and `交易记录` proceed through the existing data loader and report renderer instead of raising the policy-only `poe.BotError`.
- V1.3 parameter and introduction text describe the available queries normally without policy-only warnings.
- V1.1 behavior remains unchanged. Regression coverage confirms its signal and performance handlers are not subject to a policy-only display block.

## Non-Goals

- Do not add broker integration or order submission.
- Do not claim that Poe placed or will place an order.
- Do not undo the P1 fixes for adjusted-price provenance, trading-calendar validation, partial provider responses, forward-filled transaction prices, or request-local response state.
- Do not weaken genuine data-availability, freshness, timestamp, calendar, or provider-integrity errors.
- Do not change strategy parameters, rankings, holdings, exposure, costs, or performance calculations.

## Design

### V1.3 policy separation

Remove the presentation policy that maps an unreconciled cross-market execution model to a global `research_only` state. Poe is a display surface, so this policy must not alter signal visibility, performance visibility, report titles, conclusions, parameter text, or introduction text.

The existing signal and performance data paths remain authoritative:

1. Load the requested confirmed or live data through the current loader.
2. Apply the existing data-quality and calendar checks.
3. Calculate the existing V1.3 signal or performance output without changing calculations.
4. Render the normal Poe response.

### V1.1 regression boundary

V1.1 currently displays both signals and performance without a global research-only policy. Production behavior is not changed. Tests will lock in that the signal and performance handlers reach their data providers and render normally when valid data is supplied.

### Error handling

Policy-only refusal is removed. Genuine failures continue to follow the current behavior:

- data/calendar/provider failures raise their existing errors;
- partial streamed performance reports retain their request-local suppression behavior;
- live data that fails freshness or integrity checks is not silently presented as valid.

## Testing

Implementation follows red-green-refactor:

1. Replace the V1.3 regression that expects policy-only refusal with tests expecting provider access and normal rendering while the previous policy flag is false.
2. Add assertions that V1.3 signal, parameter, and introduction output contain no policy-only banners.
3. Add or retain V1.1 regression coverage proving signal and performance display paths remain open.
4. Run focused V1.3 and V1.1 Poe tests, compile both Poe scripts, run the full test suite, and run `git diff --check`.

## Acceptance Criteria

- V1.3 no longer raises the reported `V1.3 performance unavailable` error solely because the cross-market execution model is unreconciled.
- V1.3 displays signal, performance, NAV-curve, and trade-record responses through their existing paths.
- V1.3 user-facing output contains no `research-only` or `不可执行` policy reminder.
- V1.1 continues to display normally.
- Existing genuine data-integrity safeguards and calculations are unchanged.
