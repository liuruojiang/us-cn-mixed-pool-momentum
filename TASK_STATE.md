# Task State

## Current Focus

SubD six-ETF V1.1 formal runner and Poe live-signal hardening after the 2026-06-28 quant review.

## Key Paths

- Poe bot entrypoint: `poe_subd_six_etf_v1_1_bot.py`
- Formal local runner: `run_subd_six_etf_v1_1.py`
- Research module: `research_subd_six_etf_weighted_slope.py`
- Regression tests: `tests/test_poe_subd_external_review_regressions.py`
- Formal-runner regression tests: `tests/test_subd_runner_regressions.py`
- Handoff record: `docs/subd_v11_poe_live_hardening_record_20260621.md`
- Cleanup/sync record: `docs/cleanup_test_files_20260628.md`
- Target-vol comparison run: `quant_param_scan_runs/20260621_mixed_us_cn_momentum_subd_six_etf_v1_1_poe_bot_target_vol_target_vol_realized_vol_input/`

## Decisions Locked In

- Production target-vol remains the existing strategy-return realized-vol policy, including cash days, until a separate strategy-change review explicitly promotes a new policy.
- The non-cash asset-return realized-vol variant is research-only. The 2026-06-21 comparison lowered return and drawdown, with little Sharpe improvement, and was finalized as `keep_default_pending_user_review`.
- The 50% staged entry / wait-for-down-day rule was intentionally left unchanged.
- Live signal requests must force a fresh live build; confirmed signal requests may use the confirmed cache.
- A-share ETF execution timing is an explicit strategy assumption: realtime signal before close, same-day close execution. Do not relabel this as lookahead without changing the strategy premise.
- QVeris is retired from the current formal path. Keep QVeris scripts/docs only as historical archive evidence.
- The public historical close chain is AkShare/Eastmoney qfq, then validated Tencent fqkline `qfqday/day` with a continuity guard, then Eastmoney HTTP qfq.
- The formal runner forward-fills single-asset suspension/missing-close dates for NAV continuity, records `price_ffill_*`, and blocks same-day trade legs that depend on a forward-filled price.
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
- CNFin historical fallback remains removed. Tencent fqkline is promoted only for the validated `qfqday/day` historical close path; keep any raw CNFin/Tencent fallback out unless independently revalidated.
- `analyze_abcde_combo_20260509.py` still points at older fixed sleeve artifacts; refresh it separately before treating combo output as current formal evidence.

## Verification Commands

```powershell
python -m pytest tests -q
python -m py_compile poe_subd_six_etf_v1_1_bot.py research_subd_six_etf_weighted_slope.py run_subd_six_etf_v1_1.py tests/test_poe_subd_external_review_regressions.py tests/test_poe_subd_live_signal_freshness.py tests/test_poe_subd_trade_records.py tests/test_subd_runner_regressions.py
python run_subd_six_etf_v1_1.py --end-date 2026-06-26 --output-tag codex_repair_20260628
python D:\Codex\home\skills\quant-param-scan\scripts\check_quant_param_scan_artifacts.py --phase complete --strict quant_param_scan_runs\20260621_mixed_us_cn_momentum_subd_six_etf_v1_1_poe_bot_target_vol_target_vol_realized_vol_input
git diff --check
```
