# Sub-D Poe Test-File Cleanup And Remote Sync Record - 2026-08-07

> Superseded status (2026-08-12): the 14 V1.1 target-vol validation failures recorded below are fixed. The current full suite is `495 passed, 1 warning`; the remaining warning is the upstream `fastapi_poe` Pydantic deprecation. This file remains as a dated cleanup record.

## Scope

This cleanup closed the V1.1/V1.3 Poe display and `159985.SZ` source-fallback pass before remote synchronization. It removed generated test/runtime caches from the active workspace and preserved all source-code regression tests, strategy/research outputs, documentation, and rollback evidence.

Preserved active regression tests:

- `tests/test_poe_subd_159985_cross_validated_fallback.py`
- `tests/test_poe_subd_external_review_regressions.py`
- `tests/test_poe_subd_live_signal_freshness.py`
- `tests/test_poe_subd_mixed_pool_v1_3_regressions.py`
- `tests/test_poe_subd_trade_records.py`
- `tests/test_subd_runner_regressions.py`

## Removed From The Active Workspace

The following reproducible paths were moved to `.codex_backups/20260807_121256/removed_caches/` so the cleanup remains recoverable:

```text
.pytest_cache/
__pycache__/
tests/__pycache__/
quant_param_scan_runs/20260618_subd_v11_same_slice_ablation/__pycache__/
outputs/cn_trading_days_cache.csv
```

The backup directory also contains the pre-sync copies of `README.md` and `TASK_STATE.md`.

## Verification

- `py_compile` passed for both Poe bots, the formal runner/research module, and all six active test files.
- The new `159985.SZ` contract plus V1.3 regression suite passed: `70 passed`.
- The V1.1 focused suites passed with the known target-vol cases excluded: `228 passed, 17 deselected`.
- The full suite reported `306 passed, 14 failed, 1 warning`. The 14 failures are the pre-existing V1.1 target-vol initial-scale/input-validation cases recorded in `TASK_STATE.md`; the cleanup and `159985.SZ` changes introduced no additional failing node IDs.
- Generated caches created by verification were removed again before staging and push.

## Remote Sync Scope

Only the V1.1/V1.3 Poe correctness/display changes, their regression tests, current README/task-state records, and this cleanup record belong to the sync commit. Untracked strategy scans, research outputs, helper scripts, and unrelated `docs/new_strategy_test_standard_process.md` edits remain local and unstaged.
