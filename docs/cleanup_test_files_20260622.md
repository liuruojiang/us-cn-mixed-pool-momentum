# Sub-D V1.1 Test-File Cleanup Record - 2026-06-22

## Scope

This cleanup removed generated test/runtime cache files from the active workspace. It did not remove active pytest suites, production strategy code, research outputs, scan artifacts, or backup evidence.

Preserved active test suites:

- `tests/test_poe_subd_external_review_regressions.py` - active regression suite, 148 test symbols at cleanup time.
- `tests/test_poe_subd_live_signal_freshness.py` - active live freshness suite, 6 test symbols at cleanup time.
- `tests/test_poe_subd_trade_records.py` - active trade-record suite, 6 test symbols at cleanup time.

Preserved evidence and artifacts:

- `outputs/`
- `quant_param_scan_runs/`
- `docs/`
- `.codex_backups/`

## Removed Paths

Generated cache directories removed from the active workspace:

```text
.pytest_cache/
__pycache__/
tests/__pycache__/
outputs/cn_trading_days_cache.csv
```

These paths are already ignored by `.gitignore`, so their removal is a local workspace cleanup rather than a tracked source-code deletion.

## Verification

Commands run during cleanup:

```powershell
git status --short --branch
git ls-files tests
Get-ChildItem -Force -Recurse -Directory | Where-Object { ... cache dirs outside .codex_backups ... }
Remove-Item -LiteralPath <verified-cache-paths> -Recurse -Force
python -m pytest tests -q
git diff --check
```

Observed results:

- Active tracked test files remained in place.
- No `.pytest_cache/` or `__pycache__/` directories remained outside `.codex_backups/` immediately after cache cleanup.
- Full pytest suite passed after the related signal-report and data-source changes.
