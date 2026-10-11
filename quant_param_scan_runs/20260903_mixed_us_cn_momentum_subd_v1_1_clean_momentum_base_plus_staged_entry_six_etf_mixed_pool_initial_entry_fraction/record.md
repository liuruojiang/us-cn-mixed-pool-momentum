# Quant Parameter Scan Record

> **SUPERSEDED — WRONG BASELINE:** This run retained `R2=0.20`, but the user required the pure momentum base with R2 disabled. Do not use its result for the staged-entry simplification decision. A corrected run is required.

## Run Metadata

- Run id: `20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_plus_staged_entry_six_etf_mixed_pool_initial_entry_fraction`
- Created at: 2026-09-03T21:49:36+08:00
- Project: mixed-us-cn-momentum
- Strategy or version: SubD V1.1 clean momentum base plus staged entry
- Sleeve or subsystem: six-etf mixed pool
- Parameter group: `INITIAL_ENTRY_FRACTION`
- Scan type: `single_parameter`
- Repo or workspace path: `D:\动量策略\美股A股混合池子动量策略`
- Target entrypoint: `run_subd_six_etf_v1_1.py`
- Git branch: `codex/previous-research-sync-20260821`
- Git commit: `6bf19204abca54f5ff7d15ec1708cf03a0412669`
- Working tree status before:

```text
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_extended_at_buffer_1_00/
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/
```

## Research Question

- Baseline: full entry 1.00 on the accepted clean base: 25-day weighted slope, R2 0.20, Switch Buffer 1.00, 0.10% one-way cost.
- Candidate grid: initial fraction `1.00 / 0.90 / 0.80 / 0.75 / 0.67 / 0.60 / 0.50 / 0.40 / 0.33 / 0.25 / 0.10`; any value below 1.00 waits without timeout for the first down day in the newly selected asset, then fills to 100%.
- Decision target: test whether staged entry itself and the current 0.50 fraction add robust value versus immediate full entry.
- Source-change rule: `research_only_no_source_change`
- Required windows: full, 10Y, 5Y, 3Y, 1Y
- Required metrics: annual return, annualized volatility, Sharpe, max drawdown, and strategy-specific exposure/cost metrics
- Promotion threshold: require return/drawdown improvement across long and recent windows plus a neighboring fraction plateau; isolated benefit is insufficient.
- Rerun triggers: parity failure, frozen-input mismatch, missing required window, or any change to R2/cost/execution/base assumptions.

## Implementation Anchor

- Official entrypoint: `run_subd_six_etf_v1_1.py`.
- Function or command path: frozen formal qfq panel -> official score function -> official `run_staged_entry` with `EntryCase(all_new_asset_50_wait_down)`.
- Existing loaders reused: frozen same-session formal qfq panel from the accepted R2 scan.
- Existing metrics reused: official trading-day windows and return/wealth/max-drawdown conventions.
- Default values and source locations: `INITIAL_ENTRY_FRACTION=0.50` in `run_subd_six_etf_v1_1.py`; no-timeout down-day fill logic in `run_staged_entry`.

| parameter | default | source location |
| --- | ---: | --- |
| `R2_THRESHOLD` | 0.20 | accepted clean base |
| `SWITCH_BUFFER` | 1.00 | accepted clean base |
| `INITIAL_ENTRY_FRACTION` | 0.50 | `run_subd_six_etf_v1_1.py` |
| `ONE_WAY_COST` | 0.001 | `run_subd_six_etf_v1_1.py` |

## Data Snapshot

- Run timestamp: 2026-09-03 Asia/Shanghai; measured runtime 69.298 seconds.
- Raw data start: 2011-12-09.
- Raw data end: 2026-09-02.
- Metrics start after warmup: score first eligible on 2012-01-16; full window retains prior cash warmup rows.
- Metrics end: 2026-09-02.
- Latest trading date or snapshot: 2026-09-02.
- Data sources: frozen qfq/front-adjusted six-ETF panel from the accepted same-session formal scan.
- Local cache paths: source `price_snapshot_qfq.csv.gz` in the preceding R2 x Buffer run folder.
- Cache write risk: none; no data or calendar refresh.
- Missing or stale data: inherited matched boundary through 2026-09-02 because one ETF lagged the other five by one session in the source run.
- Alignment rules: exact 3,578-row panel and stored forward-fill flags reused.
- Adjustment mode: qfq/front-adjusted only.
- Trading calendar: previously validated China-session index.
- Timezone assumptions: Asia/Shanghai; close-confirmed/close-executed research convention.

## Cost and Execution Assumptions

- Commission: represented inside the aggregate one-way cost.
- Slippage: represented inside the aggregate one-way cost.
- Open-impact: none separately.
- Financing: none; leverage disabled.
- Borrow or shorting cost: none; long/cash only.
- Rebalance timing: daily close-confirmed signal.
- Fill timing: close convention; initial fraction on a new asset, then remaining fraction at the first later down close with no timeout.
- Leverage or sizing rules: maximum 1.0 exposure; target-vol and leverage overlays disabled.
- Hedge assumptions: no hedge.

## Runtime Override Plan

- Override mechanism: immutable `EntryCase.initial_fraction` argument; official score outputs cached by date to avoid redundant regression calculations.
- Values restored after each candidate: original score function restored in `finally`.
- Default candidate included in same run: yes, current 0.50 and disabled/full-entry 1.00.
- Parity check against official/default output: baseline daily curve versus accepted R2 scan; cached 0.50 curve versus an uncached official-function rerun.
- If parity check failed, explanation: not applicable. Baseline versus the accepted prior curve and cached 0.50 versus an uncached official-function rerun matched within `7.1054e-15`.

## Commands

```powershell
python -X utf8 quant_param_scan_runs\20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_plus_staged_entry_six_etf_mixed_pool_initial_entry_fraction\run_scan.py
```

## Output Files

- `scan_summary.csv`: 55 rows = 11 fractions x 5 required windows.
- `window_metrics.csv`: 11-row wide comparison with return/drawdown deltas versus full entry.
- `scan_meta.json`: this run metadata
- `command_log.txt`: initialization, frozen-input assumptions, command, parity, and runtime.
- `parity_checks.csv`: baseline and cached-score parity evidence.
- `daily_outputs/`: daily output for all 11 fractions.

## Full-Sample Results

| initial fraction | annual return | delta vs full | max drawdown | MDD delta | Sharpe | avg exposure |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1.00 / disabled | 29.46% | 0.00pp | -24.40% | 0.00pp | 1.263 | 79.26% |
| 0.90 | 28.89% | -0.57pp | -23.54% | +0.86pp | 1.271 | 77.52% |
| 0.75 | 28.00% | -1.46pp | -22.45% | +1.95pp | 1.278 | 74.92% |
| 0.67 | 27.51% | -1.95pp | -21.89% | +2.51pp | 1.279 | 73.53% |
| 0.50 / current | 26.45% | -3.01pp | -20.70% | +3.70pp | 1.273 | 70.57% |
| 0.33 | 25.35% | -4.11pp | -19.69% | +4.70pp | 1.255 | 67.61% |
| 0.10 | 23.79% | -5.67pp | -18.95% | +5.45pp | 1.210 | 63.62% |

Annual return decreases monotonically and drawdown becomes shallower monotonically as the initial fraction falls. There is no return-improving staged-entry region.

## Window Results

Annual return / max drawdown:

| initial fraction | Full | 10Y | 5Y | 3Y | 1Y |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1.00 / disabled | 29.46% / -24.40% | 34.28% / -21.83% | 53.36% / -21.83% | 68.20% / -15.87% | 52.73% / -15.87% |
| 0.50 / current | 26.45% / -20.70% | 30.15% / -16.46% | 48.92% / -16.46% | 56.62% / -13.23% | 42.49% / -13.23% |

The 0.50 rule loses 3.01/4.13/4.43/11.58/10.24 percentage points of annual return over Full/10Y/5Y/3Y/1Y. Its drawdown improves by 3.70/5.38/5.38/2.64/2.64 percentage points respectively.

## Stability Classification

- Label: `wide_stable` evidence for disabling staged entry; the monotonic trade-off is broad rather than a parameter peak.
- Evidence: full entry has the highest annual return in every required window. Lower fractions only exchange exposure/return for shallower drawdown; no fraction creates a free improvement.
- Nearby-candidate behavior: all fractions from 0.90 through 0.10 follow the same monotonic shape. Full-sample Sharpe has a shallow maximum near 0.60-0.75, but the gain over full entry is only about 0.015 and comes with materially lower return.
- Recent-window behavior: the current 0.50 rule loses 11.58pp in 3Y and 10.24pp in 1Y annual return for only 2.64pp shallower drawdown in each window.
- Cost sensitivity: cumulative modeled cost falls from 0.653 at full entry to 0.602 at 0.50, but the saving does not offset underexposure.
- Data sensitivity: exact frozen qfq panel reused and parity checks passed.
- Leverage or exposure caveat: the drawdown improvement is mechanically linked to lower average exposure: 79.26% at full entry versus 70.57% at 0.50. This is not independent timing alpha.

## Decision

- Decision: `rerun_required`. The result is superseded because R2 was incorrectly retained.
- Recommended next action: rerun the same staged-entry grid on the pure momentum base with R2 disabled and Switch Buffer 1.00.

## User-Facing Summary

This result must not be used for the requested decision because the baseline scope was wrong. See the corrected pure-base run instead.

## Finalization

- Finalized at: 2026-09-03T21:54:22+08:00
- Decision: rerun_required
- Stability label: invalid_scope
- Complete checker: PASS
