# Sub-D V1.1 Test-File Cleanup Record - 2026-06-28

## Scope

This cleanup closed the 2026-06-28 Sub-D V1.1 repair pass before remote sync. It removed generated runtime/test caches from the active workspace and preserved source-code regression tests, formal strategy outputs, docs, and rollback backups.

Preserved active regression tests:

- `tests/test_poe_subd_external_review_regressions.py` - Poe live/confirmed signal, calendar, data-source, and external-review regressions, including the 2026-06-28 weekend live-calendar case.
- `tests/test_poe_subd_live_signal_freshness.py` - live/confirmed freshness and cache behavior.
- `tests/test_poe_subd_trade_records.py` - trade-record formatting and export behavior.
- `tests/test_subd_runner_regressions.py` - formal runner regressions for single-ETF suspension forward-fill metadata, stale-price trade blocking, calendar cache fallback, and mandatory performance windows.

Preserved formal repair artifacts:

- `outputs/subd_six_etf_codex_repair_20260628_summary.csv`
- `outputs/subd_six_etf_codex_repair_20260628_daily.csv`
- `outputs/subd_six_etf_codex_repair_20260628_sources.csv`
- `outputs/subd_six_etf_codex_repair_20260628_data_quality.csv`

## Removed Paths

Generated cache files/directories removed from the active workspace:

```text
.pytest_cache/
__pycache__/
tests/__pycache__/
outputs/cn_trading_days_cache.csv
```

These paths are reproducible local runtime artifacts. `.codex_backups/` was intentionally preserved for rollback evidence.

## Verification

Commands run before cleanup and sync preparation:

```powershell
python -m pytest tests -q
python -m py_compile poe_subd_six_etf_v1_1_bot.py research_subd_six_etf_weighted_slope.py run_subd_six_etf_v1_1.py tests/test_poe_subd_external_review_regressions.py tests/test_poe_subd_live_signal_freshness.py tests/test_poe_subd_trade_records.py tests/test_subd_runner_regressions.py
python run_subd_six_etf_v1_1.py --end-date 2026-06-26 --output-tag codex_repair_20260628
git diff --check
```

Observed results:

- Full pytest suite: `183 passed`, with one upstream `fastapi_poe` / Pydantic deprecation warning.
- `py_compile`: passed.
- Formal runner: completed and wrote the preserved `codex_repair_20260628` outputs.
- `git diff --check`: no whitespace errors; Git reported LF/CRLF conversion warnings only.
