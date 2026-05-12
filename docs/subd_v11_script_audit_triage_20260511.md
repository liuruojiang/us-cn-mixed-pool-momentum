# Sub-D V1.1 Script Audit Triage - 2026-05-11

## Scope

This note records the code-level audit triage for:

- `run_subd_six_etf_v1_1.py`
- `poe_subd_six_etf_v1_1_bot.py`

The first applied patch is intentionally limited to low-risk research-runner hygiene in `run_subd_six_etf_v1_1.py`.

## Applied In First Patch

File: `run_subd_six_etf_v1_1.py`

- Bug 1: output prefix no longer hardcodes `20260509`; it now uses `config.output_tag`.
- Bug 2: output directory creation now uses `mkdir(parents=True, exist_ok=True)`.
- Bug 3: `END_DATE` default is now `pd.Timestamp.today().normalize()`, with `--end-date` CLI override.
- Bug 8: report windows `5Y/3Y/1Y` now use trading-day counts (`1260/756/252`) instead of calendar offsets.
- Bug 9: `OverheatCase` validation now rejects `NaN` and infinite thresholds/scales explicitly.
- Bug 10: import-time sanity check verifies the required `research_subd_six_etf_weighted_slope` contract, including loader, data-quality, and default target-vol symbols.
- Bug 20: daily CSV output now uses `reset_index()` and `index=False`, preserving a normal `date` column.
- Added CLI options: `--start-date`, `--end-date`, `--eval-start`, `--output-tag`, `--source`.

Verification:

- `python -m py_compile .\run_subd_six_etf_v1_1.py` passed.

Backup:

- `.codex_backups/20260511_224039/run_subd_six_etf_v1_1.py`

## Still Open In run_subd_six_etf_v1_1.py

- Bug 7: avoid common-valid-date truncation. This changes historical sample composition and strategy behavior, so it belongs in a separate research validation, not a hygiene patch.

## Applied In Second Patch

Files:

- `run_subd_six_etf_v1_1.py`
- `tests/test_run_subd_v1_1_core.py`

Changes:

- Added focused core tests for `_target_from_scores`, `_recompute_final_exposure_nav`, `apply_overheat_overlay`, and `calc_bias_momentum`.
- Bug 5: `apply_overheat_overlay` now pre-aligns feature frames to the curve index and reads NumPy arrays inside the state-machine loop, avoiding per-row `iterrows()` and `.loc` lookup.
- Bug 6: `calc_bias_momentum` now uses vectorized rolling windows and the closed-form linear-regression slope instead of nested Python loops with per-window `np.polyfit`.

Verification:

- `python .\tests\test_run_subd_v1_1_core.py` passed: 4 tests.
- `python -m py_compile .\run_subd_six_etf_v1_1.py .\tests\test_run_subd_v1_1_core.py` passed.

## Applied In Third Patch

Files:

- `run_subd_six_etf_v1_1.py`
- `tests/test_run_subd_v1_1_core.py`

Changes:

- Bug 4: aligned `base_return` / `base_nav` semantics with the Poe bot.
- `base_return` / `base_nav` now represent the first-layer costed staged-entry curve, matching the user-facing "base strategy NAV" display.
- `base_gross_return` remains the gross-only base return used by overlay recomputation.
- `target_vol_input_return` / `target_vol_input_nav` explicitly record the costed strategy-return series used by the existing target-vol estimator.

Verification:

- `python .\tests\test_run_subd_v1_1_core.py` passed: 7 tests.
- `python -m py_compile .\run_subd_six_etf_v1_1.py .\tests\test_run_subd_v1_1_core.py` passed.

## Applied In Fourth Patch

Files:

- `run_subd_six_etf_v1_1.py`
- `poe_subd_six_etf_v1_1_bot.py`
- `tests/test_run_subd_v1_1_core.py`

Changes:

- R1: `base_return` / `base_nav` semantics are now net/costed in both run script and bot; gross base return is kept separately as `base_gross_return`.
- R2: run script contract check now includes `DEFAULT_VOL_WINDOW`, `DEFAULT_MAX_LEV`, `load_close`, and `data_quality`.
- R3: bot overheat validation now rejects NaN and infinite thresholds/scales, matching the run script.
- R4: target-vol scale calculation now maps zero realized volatility to `max_lev`; warmup NaN still maps to 1.0.

Verification:

- `python .\tests\test_run_subd_v1_1_core.py` passed: 7 tests.
- `python -m py_compile .\run_subd_six_etf_v1_1.py .\tests\test_run_subd_v1_1_core.py .\poe_subd_six_etf_v1_1_bot.py` passed.
- PowerShell heredoc import smoke test passed for bot zero-vol target-vol behavior and nonfinite overheat rejection.

Backup:

- `.codex_backups/20260512_102326/`

## Recorded But Not Changed

- N1: `calc_bias_momentum` intentionally starts at `CN_BIAS_N + CN_MOM_DAY - 1`, skipping the first technically computable window. Run script and bot are consistent; this avoids using the first MA-valid point as the normalization anchor.
- N2: bot `_normalize_daily()` intentionally filters to `V11_SCENARIO`. If a future version changes the scenario name, improve the error message to include available scenario values.
- N3: bot `apply_overheat_overlay()` still uses `iterrows()`. Daily cache limits the user impact to the first query of the day; optimize only if first-query latency becomes material.

## Closeout Cleanup

- The temporary regression test file `tests/test_run_subd_v1_1_core.py` was removed before cloud sync per user request.
- Final closeout verification uses syntax/import compilation instead of retaining the local test file:
  `python -m py_compile .\research_subd_six_etf_weighted_slope.py .\run_subd_six_etf_v1_1.py .\poe_subd_six_etf_v1_1_bot.py`.

Backup:

- `.codex_backups/20260512_094923/`

## Bot Audit Status

File: `poe_subd_six_etf_v1_1_bot.py`

Confirmed or still relevant:

- Bug 11: strategy logic is duplicated in the bot and research script. This is a real long-term drift risk, but importing the research module into Poe may conflict with Poe-native deployment constraints. Needs a design decision.

Already changed or not matching the reviewed version:

- Bug 12: current `load_close()` uses per-code fallback, not Sina all-or-nothing fallback.
- Bug 13: current primary public loaders use qfq/front-adjusted AkShare Eastmoney and Eastmoney HTTP, and `_source_record` records adjustment status. Poe runtime also has CNFin/Tencent raw emergency fallbacks for environments where AkShare is unavailable and Eastmoney disconnects; these are explicitly labeled as raw/unadjusted emergency sources.
- Bug 21: current `_signal_rank_rows()` already includes `raw_score` as the third sort key, so ineligible rows are not purely original-order sorted when raw scores exist.
- Bug 24: local `SettingsResponse` no-op is acceptable.

Bot patch status:

- Bug 14: `_handle_signal`, live `_handle_params`, and `_handle_performance` now use a date-keyed in-memory cache for the daily rebuild.
- Bug 15: `render_nav_curve_png()` now sets Chinese font fallbacks and `axes.unicode_minus=False`.
- Bug 16: yearly performance table now runs from `EVAL_START` to the latest available date, independent of the first chart range.
- Bug 18: query-classification priority is documented in code.
- Bug 19: local `_LocalMessage.overwrite()` now clears the previous terminal line before writing.
- Bug 22: `_overheat_rule_text()` now returns a no-overheat-rule message for blank/none/nan recovery modes.
- Bug 23: CNFin/Tencent raw helpers now reject partial chunk loads and long mid-series gaps instead of silently returning stitched partial history. They are included only after qfq providers fail.
- The file still displays mojibake in PowerShell output, so broader user-facing text edits should remain a separate encoding-safe pass.

Bot verification:

- `python -m py_compile .\poe_subd_six_etf_v1_1_bot.py` passed.
- PowerShell heredoc import smoke test passed for `classify_query()` import path and blank `_overheat_rule_text()` handling.
- PowerShell heredoc import smoke test passed for `_validate_no_partial_raw_history()` partial-error and long-gap rejection.

Backup:

- `.codex_backups/20260511_224252/poe_subd_six_etf_v1_1_bot.py`

## Recommended Next Batch

1. Treat Bug 7 as a research behavior change, not a script hygiene fix.
2. Decide Bug 11 architecture: keep Poe-native self-contained strategy logic or extract a shared engine that Poe can reliably import/deploy.
3. Do a separate encoding-safe pass before editing broader Poe bot user-facing Chinese text.
4. If performance is still material after Bug 5/6, run a focused benchmark on `build_overheat_features()` plus `apply_overheat_overlay()` before further optimization.
