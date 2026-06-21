# Task State

## Current Focus

SubD six-ETF V1.1 Poe bot live/confirmed-signal hardening and cleanup.

## Key Paths

- Poe bot entrypoint: `poe_subd_six_etf_v1_1_bot.py`
- Formal local runner: `run_subd_six_etf_v1_1.py`
- Research module: `research_subd_six_etf_weighted_slope.py`
- Regression tests: `tests/test_poe_subd_external_review_regressions.py`
- Handoff record: `docs/subd_v11_poe_live_hardening_record_20260621.md`
- Target-vol comparison run: `quant_param_scan_runs/20260621_mixed_us_cn_momentum_subd_six_etf_v1_1_poe_bot_target_vol_target_vol_realized_vol_input/`

## Decisions Locked In

- Production target-vol remains the existing strategy-return realized-vol policy, including cash days, until a separate strategy-change review explicitly promotes a new policy.
- The non-cash asset-return realized-vol variant is research-only. The 2026-06-21 comparison lowered return and drawdown, with little Sharpe improvement, and was finalized as `keep_default_pending_user_review`.
- The 50% staged entry / wait-for-down-day rule was intentionally left unchanged.
- Live signal requests must force a fresh live build; confirmed signal requests may use the confirmed cache.

## Live/Confirmed Data Safety Notes

- Live quote candidates must pass completeness, temporal quality, source eligibility, and price-quality gates before execution eligibility.
- Stale or unsynchronized but price-valid quotes may be monitor-only; price-invalid quotes must not enter monitor candidates.
- Confirmed close bars require per-asset final fields and current raw asset dates. Forward-filled prices can support historical continuity, but cannot receive same-day final-close stamps or executable confirmation.
- If a trade leg uses a forward-filled/stale asset price, execution is blocked and the report should remain monitor/review only.

## Open Items

- Official raw/reference previous-close and exchange limit-up/limit-down fields are still not fully sourced; current live price bands are a fail-closed proxy based on the price matrix.
- QDII same-day EOD vendor lag can make 15:30+ confirmed signals unavailable; this is expected conservative behavior until a stronger final-close source is added.
- CNFin/Tencent historical fallback code was removed rather than promoted; add them back only with independent validation of prices, dates, and rows.

## Verification Commands

```powershell
python -m pytest tests -q
python -m py_compile poe_subd_six_etf_v1_1_bot.py research_subd_six_etf_weighted_slope.py run_subd_six_etf_v1_1.py tests/test_poe_subd_external_review_regressions.py
python D:\Codex\home\skills\quant-param-scan\scripts\check_quant_param_scan_artifacts.py --phase complete --strict quant_param_scan_runs\20260621_mixed_us_cn_momentum_subd_six_etf_v1_1_poe_bot_target_vol_target_vol_realized_vol_input
git diff --check
```
