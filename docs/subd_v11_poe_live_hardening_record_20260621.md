# SubD V1.1 Poe Live Hardening Record - 2026-06-21

## Scope

This record closes the 2026-06-21 external-review hardening pass for `poe_subd_six_etf_v1_1_bot.py`, the matching local runner, and the research module naming cleanup.

Primary files:

- `poe_subd_six_etf_v1_1_bot.py`
- `run_subd_six_etf_v1_1.py`
- `research_subd_six_etf_weighted_slope.py`
- `tests/test_poe_subd_external_review_regressions.py`
- `tests/test_poe_subd_live_signal_freshness.py`
- `tests/test_poe_subd_trade_records.py`

## Production Decisions

- Kept the existing target-vol realized-vol input: strategy return including cash days.
- Did not change the 50% initial entry / wait-for-down-day staged-entry rule.
- Kept non-cash asset-return realized-vol as a research-only candidate pending explicit strategy approval.
- Live signal requests force fresh live data; confirmed signal requests can use the confirmed cache.

## Live Quote and Price Gates

- Live quote price validation now runs inside the endpoint candidate fallback path.
- Price-invalid candidates are excluded before monitor-candidate selection.
- Candidate quality covers completeness, temporal quality, source execution eligibility, and price quality.
- Vendor `prev_close` must be ETF-tick valid and match the independent price-matrix reference within one 0.001 CNY tick using `Decimal`, avoiding binary-float one-tick boundary failures.
- ETF price-limit bounds use 0.001 CNY tick rounding and per-code ratios, including 20% for `159915.SZ`.
- The price-limit wording is now explicit: it is a temporary proxy band based on the price matrix, not an official exchange reference band.
- Missing vendor previous close demotes live output to monitor/review instead of automatic execution eligibility.

## Confirmed Close and Stale Data Gates

- Confirmed close metadata is produced only when all six assets have current raw asset dates and valid per-asset final fields.
- Forward-filled prices are marked with `price_ffill_{code}` metadata.
- A forward-filled or stale trade-leg asset blocks execution eligibility.
- Final close verification remains strict: invalid booleans such as `2`, `"garbage"`, or missing `bar_final_*` evaluate to false.
- Same-day QDII EOD vendor lag can make confirmed mode fall back to the prior verified day. This is intentional conservative behavior because cross-sectional ranking needs all six current closes.

## Historical and Reporting Cleanup

- Removed unused raw historical fallback helpers and stale display helpers from the Poe bot.
- Canonicalized source names to `akshare_em_qfq` / `akshare_sina_raw` while preserving legacy CLI aliases in the research module.
- Added reusable HTTP sessions in the Poe and research paths.
- Stopped swallowing `stderr` in `__main__`.
- Removed the dead `_handle_performance` `chart_args` branch.
- Kept CNFin/Tencent historical fallbacks out of production until a future independently validated integration is done.

## Performance Math Fixes

- Drawdown windows now rebase from the selected window instead of forcing the high-water mark to at least 1.0.
- Window returns set the first in-window return to zero to avoid counting the entry-day move without the previous close.
- Gross return, turnover, cost, and NAV consistency are covered by regression tests.

## Target-Vol Old/New Full-Period Comparison

Run folder:

`quant_param_scan_runs/20260621_mixed_us_cn_momentum_subd_six_etf_v1_1_poe_bot_target_vol_target_vol_realized_vol_input/`

Data caveat:

- Current remote qfq loading failed during the run.
- The comparison fell back to the local same-slice artifact at `quant_param_scan_runs/20260618_subd_v11_same_slice_ablation/daily_curves.csv`.
- This is a strategy-mouth diagnostic, not a refreshed formal qfq production performance report.

Decision:

- `keep_default_pending_user_review`
- Stability label: `needs_review`
- Baseline parity check against the local full V1.1 candidate: `max_abs_nav_diff = 0.0`

Summary:

| Window | Baseline ann. return | Candidate ann. return | Delta | Baseline max DD | Candidate max DD | DD delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Full / 10Y | 65.88% | 55.62% | -10.26 pp | -17.50% | -14.71% | +2.79 pp |
| 5Y | 79.35% | 65.63% | -13.71 pp | -17.50% | -14.59% | +2.91 pp |
| 3Y | 99.18% | 81.06% | -18.12 pp | -16.30% | -13.74% | +2.56 pp |
| 1Y | 133.29% | 107.49% | -25.80 pp | -12.86% | -11.63% | +1.23 pp |

Scale diagnostics:

- Baseline average scale: `1.1776`; cap days at 1.5x: `97`; average exposure: `93.51%`.
- Candidate average scale: `1.0449`; cap days at 1.5x: `0`; average exposure: `83.03%`.
- Candidate reduced leverage, return, and drawdown; Sharpe changed little and did not justify production promotion in this pass.

## Preserved Evidence

- `quant_param_scan_runs/20260618_subd_v11_same_slice_ablation/`
- `quant_param_scan_runs/20260621_mixed_us_cn_momentum_subd_six_etf_v1_1_poe_bot_target_vol_target_vol_realized_vol_input/`
- `.codex_backups/20260621_225856/`
- `.codex_backups/20260621_231116/`
- `.codex_backups/20260621_232800/`

## Cleanup Notes

Removed only generated test/cache artifacts:

- root `__pycache__/`
- `tests/__pycache__/`
- `.pytest_cache/`
- scan-run `__pycache__/`
- transient `outputs/cn_trading_days_cache.csv` when regenerated by tests

Regression tests and durable scan artifacts were preserved.

## Verification

Commands to verify before cloud sync:

```powershell
python -m pytest tests -q
python -m py_compile poe_subd_six_etf_v1_1_bot.py research_subd_six_etf_weighted_slope.py run_subd_six_etf_v1_1.py tests/test_poe_subd_external_review_regressions.py
python D:\Codex\home\skills\quant-param-scan\scripts\check_quant_param_scan_artifacts.py --phase complete --strict quant_param_scan_runs\20260621_mixed_us_cn_momentum_subd_six_etf_v1_1_poe_bot_target_vol_target_vol_realized_vol_input
git diff --check
```
