# Task State

## Current Focus

SubD V1.1/V1.3 Poe signal-service correctness, formal runner/Poe parity, and data-integrity hardening as of 2026-08-12.

## Key Paths

- V1.1 Poe bot entrypoint: `poe_subd_six_etf_v1_1_bot.py`
- V1.3 mixed-pool Poe bot entrypoint: `poe_subd_mixed_pool_v1_3_bot.py`
- Formal local runner: `run_subd_six_etf_v1_1.py`
- Research module: `research_subd_six_etf_weighted_slope.py`
- Regression tests: `tests/test_poe_subd_external_review_regressions.py`
- V1.3 regression tests: `tests/test_poe_subd_mixed_pool_v1_3_regressions.py`
- Shared `159985.SZ` fallback tests: `tests/test_poe_subd_159985_cross_validated_fallback.py`
- Formal-runner regression tests: `tests/test_subd_runner_regressions.py`
- P1 and source-fallback record: `docs/poe_subd_p1_correctness_repair_20260711.md`
- Current adversarial repair record: `docs/subd_v11_v13_adversarial_repair_20260812.md`
- Formal old/new backtest report: `outputs/subd_v11_v13_repair_formal_comparison_20260812/report.md`
- Target-vol comparison run: `quant_param_scan_runs/20260621_mixed_us_cn_momentum_subd_six_etf_v1_1_poe_bot_target_vol_target_vol_realized_vol_input/`

## Decisions Locked In

- Production target-vol remains the existing strategy-return realized-vol policy, including cash days, until a separate strategy-change review explicitly promotes a new policy.
- The non-cash asset-return realized-vol variant is research-only. The 2026-06-21 comparison lowered return and drawdown, with little Sharpe improvement, and was finalized as `keep_default_pending_user_review`.
- The 50% staged entry / wait-for-down-day rule was intentionally left unchanged.
- Live signal requests must force a fresh live build; confirmed signal requests may use the confirmed cache.
- A-share ETF execution timing is an explicit strategy assumption: realtime signal before close, same-day close execution. Do not relabel this as lookahead without changing the strategy premise.
- QVeris is retired from the current formal path. Keep QVeris scripts/docs only as historical archive evidence.
- The formal historical close chain is AkShare/Eastmoney qfq, validated Tencent fqkline `qfqday/day`, then Eastmoney HTTP qfq. Every accepted formal series passes coverage and continuity checks. The `159985.SZ` Sina/CNFin exact-date raw intersection remains a direct diagnostic helper only and must not enter formal signal or performance paths.
- The formal runner forward-fills single-asset suspension/missing-close dates for NAV continuity, records `price_ffill_*`, and blocks same-day trade legs that depend on a forward-filled price.
- V1.1 runner and Poe use the same carried-exposure ledger. Actual post-drift exposure is capped at `DEFAULT_MAX_LEV=1.5`; cap-only turnover and cost are auditable and NAV must remain finite and positive.
- V1.3 remains a Poe signal service. Cross-market timing, calendar, and FX differences are advisory disclosures, not a global signal-suppression gate; neither Poe file submits broker orders.
- User-facing performance tables must include `full_sample`, `10Y`, `5Y`, `3Y`, and `1Y`; `from_2020` can remain as an extra review window.

## Live/Confirmed Data Safety Notes

- Live quote candidates must pass completeness, temporal quality, source eligibility, and price-quality gates before execution eligibility.
- Stale or unsynchronized but price-valid quotes may be monitor-only; price-invalid quotes must not enter monitor candidates.
- Confirmed close bars require per-asset final fields and current raw asset dates. Forward-filled prices can support historical continuity, but cannot receive same-day final-close stamps or executable confirmation.
- If a trade leg uses a forward-filled/stale asset price, execution is blocked and the report should remain monitor/review only.
- Weekend live signal queries should treat the latest market session as the calendar coverage target, return a non-tradable 休市 status, and must not fail merely because the natural current date is not a trading day.

## Open Items

- Official raw/reference previous-close and exchange limit-up/limit-down fields are still not fully sourced; current live price bands are a fail-closed proxy based on the price matrix. This is separate from the unified成交成本 assumption.
- QDII same-day EOD vendor lag can make 15:30+ confirmed signals unavailable; this is expected conservative behavior until a stronger final-close source is added.
- The Sina/CNFin raw diagnostic helper is code-specific to `159985.SZ`; do not generalize it, label it qfq, or reconnect it to either formal loader.
- Financing cost above 1.0x remains excluded from V1.1. The 1.5x hard exposure cap and transaction cost are implemented, but financing should be added only through a separately reviewed strategy change.
- `analyze_abcde_combo_20260509.py` still points at older fixed sleeve artifacts; refresh it separately before treating combo output as current formal evidence.

## Verification Commands

```powershell
python -m pytest tests -q
python -m py_compile poe_subd_six_etf_v1_1_bot.py poe_subd_mixed_pool_v1_3_bot.py research_subd_six_etf_weighted_slope.py run_subd_six_etf_v1_1.py tests/test_poe_subd_159985_cross_validated_fallback.py tests/test_poe_subd_external_review_regressions.py tests/test_poe_subd_live_signal_freshness.py tests/test_poe_subd_mixed_pool_v1_3_regressions.py tests/test_poe_subd_trade_records.py tests/test_subd_runner_regressions.py
python run_subd_six_etf_v1_1.py --end-date 2026-08-11 --output-tag formal_recheck_20260812
python D:\Codex\home\skills\quant-param-scan\scripts\check_quant_param_scan_artifacts.py --phase complete --strict quant_param_scan_runs\20260621_mixed_us_cn_momentum_subd_six_etf_v1_1_poe_bot_target_vol_target_vol_realized_vol_input
git diff --check
```

Latest full-suite result: `495 passed, 1 warning` on 2026-08-12. The warning is the upstream `fastapi_poe` Pydantic class-config deprecation.
