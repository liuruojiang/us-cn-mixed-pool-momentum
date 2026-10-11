# Quant Parameter Scan Record

## Run Metadata

- Run id: `20260904_mixed_us_cn_momentum_subd_pure_momentum_core_six_etf_mixed_pool_recency_weight_exponent`
- Created at: 2026-09-04T00:31:43+08:00
- Project: mixed-us-cn-momentum
- Strategy or version: SubD pure momentum core
- Sleeve or subsystem: six-etf mixed pool
- Parameter group: `recency weight exponent`
- Scan type: `single_parameter`
- Repo or workspace path: `D:\动量策略\美股A股混合池子动量策略`
- Target entrypoint: `run_subd_six_etf_v1_1.py`
- Git branch: `codex/previous-research-sync-20260821`
- Git commit: `6bf19204abca54f5ff7d15ec1708cf03a0412669`
- Working tree status before:

```text
?? docs/subd_v11_naive_simplification_decisions_20260903.md
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_pure_momentum_base_plus_overheat_six_etf_mixed_pool_overheat_derisk_scale/
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_pure_momentum_base_plus_overheat_six_etf_mixed_pool_overheat_enter_with_2pp_hysteresis/
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_pure_momentum_base_plus_staged_entry_six_etf_mixed_pool_initial_entry_fraction_r2_off/
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_pure_momentum_base_plus_target_vol_six_etf_mixed_pool_target_vol/
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_pure_momentum_core_six_etf_mixed_pool_lookback/
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_plus_staged_entry_six_etf_mixed_pool_initial_entry_fraction/
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_extended_at_buffer_1_00/
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/
?? quant_param_scan_runs/20260904_mixed_us_cn_momentum_subd_pure_momentum_core_six_etf_mixed_pool_lookback_25_30_fine_rescan/
?? quant_param_scan_runs/20260904_mixed_us_cn_momentum_subd_pure_momentum_core_six_etf_mixed_pool_score_max_overheat_veto/
```

## Research Question

- Baseline: current linear recency weighting `w_t=t`, represented by exponent `p=1` in `w_t=t^p`.
- Candidate grid: `p=0, 0.25, 0.5, 0.75, 1, 1.25, 1.5, 2`; `p=0` is equal weighting and larger values emphasize recent observations more strongly.
- Decision target: determine whether the linear weighting is overfit and whether simpler equal weighting or a broad neighboring exponent gives a better same-path trade-off.
- Source-change rule: `research_only_no_source_change`
- Required windows: full, 10Y, 5Y, 3Y, 1Y
- Required metrics: annual return, annualized volatility, Sharpe, max drawdown, and strategy-specific exposure/cost metrics
- Promotion threshold: require competitive Full/10Y/5Y/3Y/1Y returns and drawdowns plus neighboring support; equal weighting is preferred only if simplification does not materially degrade results.
- Rerun triggers: power-1 parity failure, missing candidate/window, frozen-input mismatch, or activation of another overlay.

## Implementation Anchor

- Official entrypoint: `run_subd_six_etf_v1_1.py` with score implementation in `research_subd_six_etf_weighted_slope.py`.
- Function or command path: frozen qfq panel -> official `run_staged_entry` -> monkey-patched research-only `weighted_slope_score_and_r2` with `w_t=t^p` -> `calc_scores` -> Top1.
- Existing loaders reused: frozen six-ETF qfq panel and accepted pure-base curve.
- Existing metrics reused: official performance windows and NAV/max-drawdown conventions.
- Default values and source locations: hard-coded linear weights `np.arange(1, len(y)+1)` in `weighted_slope_score_and_r2`.

| parameter | default | source location |
| --- | ---: | --- |
| recency weight exponent `p` | 1.0 | research-only parameterization of `weighted_slope_score_and_r2` |

## Data Snapshot

- Run timestamp: 2026-09-04 Asia/Shanghai; 128.624 seconds.
- Raw data start: 2011-12-09.
- Raw data end: 2026-09-02 after matched-date clipping.
- Metrics start after warmup: leading cash rows retained through signal warmup.
- Metrics end: 2026-09-02.
- Latest trading date or snapshot: 2026-09-02.
- Data sources: frozen Tencent qfq six-ETF panel from the accepted stripped-base scan.
- Local cache paths: source `price_snapshot_qfq.csv.gz`; accepted current curve `daily_outputs/full_entry_1.00.csv.gz` in the referenced source runs.
- Cache write risk: none; all candidate paths were written only inside this run folder.
- Missing or stale data: frozen panel ends 2026-09-02 at the matched six-asset endpoint; no proxy extension.
- Alignment rules: same six assets, China-session calendar, unchanged pre-inception missing-value treatment.
- Adjustment mode: qfq/front-adjusted.
- Trading calendar: China trading-day calendar, 252 sessions per annualization year.
- Timezone assumptions: Asia/Shanghai; daily close-confirmed selection with next-row return realization.

## Cost and Execution Assumptions

- Commission: included in aggregate one-way cost.
- Slippage: included in aggregate one-way cost.
- Aggregate one-way cost: 0.10% on traded notional.
- Open-impact: none separately.
- Financing: none; leverage disabled.
- Borrow or shorting cost: none; long/cash only.
- Rebalance timing: daily close-confirmed Top1 selection.
- Fill timing: selected holding earns return from the next row under the official close convention.
- Leverage or sizing rules: binary 0/1 exposure; full entry.
- Hedge assumptions: no hedge.

## Runtime Override Plan

- Override mechanism: research-only runtime replacement of `subd.weighted_slope_score_and_r2`; production source unchanged.
- Values restored after each candidate: original scorer restored in `finally` after the grid.
- Default candidate included in same run: yes, current `p=1` linear weights.
- Parity check against official/default output: power 1 matched the accepted pure base within `3.553e-15` NAV and `9.975e-17` other numeric tolerance; runner/Poe matched exactly with zero position mismatch.
- If parity check failed, explanation: not applicable; parity passed.

## Commands

```powershell
python -X utf8 quant_param_scan_runs\20260904_mixed_us_cn_momentum_subd_pure_momentum_core_six_etf_mixed_pool_recency_weight_exponent\run_scan.py
```

## Output Files

- `scan_summary.csv`: 8 candidates x 5 required windows.
- `window_metrics.csv`: one row per exponent with performance/exposure/cost metrics and deltas versus power 1.
- `parity_checks.csv`: current linear-weight checks against accepted pure base and Poe.
- `daily_outputs/*.csv.gz`: rebuilt daily path for every candidate.
- `scan_meta.json`: this run metadata
- `command_log.txt`: initialization command and future scan commands

## Full-Sample Results

| power | Full ann. | Full MDD | Sharpe | trade days | cost total |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 equal | 21.59% | -38.33% | 0.898 | 332 | 0.597 |
| 0.25 | 24.72% | **-31.78%** | 1.014 | 327 | 0.587 |
| 0.50 | 23.38% | -36.39% | 0.979 | 347 | 0.625 |
| 0.75 | **24.80%** | -37.21% | **1.030** | 367 | 0.667 |
| **1 current** | 23.05% | -36.47% | 0.972 | 384 | 0.691 |
| 1.25 | 23.79% | -35.83% | 1.012 | 407 | 0.729 |
| 1.50 | 20.32% | -33.94% | 0.926 | 444 | 0.795 |
| 2.00 | 12.89% | -32.36% | 0.645 | 521 | 0.937 |

## Window Results

| power | Full ann./MDD | 10Y ann./MDD | 5Y ann./MDD | 3Y ann./MDD | 1Y ann./MDD |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 equal | 21.59% / -38.33% | 28.31% / -29.02% | 37.90% / -21.27% | 40.36% / -21.27% | 12.61% / -21.27% |
| 0.25 | 24.72% / **-31.78%** | 33.44% / -22.11% | 41.89% / -19.97% | 43.35% / -19.97% | 15.37% / -19.97% |
| 0.50 | 23.38% / -36.39% | 33.06% / -22.13% | 35.84% / -22.13% | 38.86% / -22.13% | 3.19% / -22.13% |
| 0.75 | **24.80%** / -37.21% | **36.33%** / -21.68% | 44.72% / -21.68% | 49.03% / -21.68% | 13.14% / -21.68% |
| **1** | 23.05% / -36.47% | 34.17% / -21.48% | 48.40% / -21.48% | 61.05% / -17.18% | 33.36% / -17.18% |
| **1.25** | 23.79% / -35.83% | 31.84% / -21.05% | **50.00%** / -21.05% | **62.02%** / -17.03% | 47.15% / -17.03% |
| 1.50 | 20.32% / -33.94% | 26.77% / **-18.44%** | 44.38% / **-17.40%** | 49.21% / **-15.36%** | **61.54%** / **-14.01%** |
| 2.00 | 12.89% / -32.36% | 19.21% / -25.41% | 32.73% / -20.74% | 33.92% / -17.77% | 33.94% / -17.77% |

## Stability Classification

- Label: `broad_0p75_1p25_support_equal_weight_rejected`.
- Evidence: current power 1 is surrounded by economically competitive 0.75 and 1.25 variants; equal weighting loses materially across 10Y/5Y/3Y/1Y and worsens every drawdown window versus current.
- Nearby-candidate behavior: power 1.25 improves Full/5Y/3Y/1Y returns and all drawdowns, but lowers 10Y return by 2.33 percentage points; it is a recent-tilted candidate, not a cross-window dominance result.
- Recent-window behavior: stronger recent emphasis raises 1Y performance sharply at 1.25-1.5, while 10Y and Full decay by 1.5-2.0, showing regime dependence.
- Cost sensitivity: larger powers increase switching; total modeled cost rises from 0.691 at power 1 to 0.729 at 1.25 and 0.795 at 1.5.
- Data sensitivity: the winner shifts from 0.75 on Full/10Y to 1.25 on 5Y/3Y and 1.5 on 1Y; no single retuned exponent dominates across windows.
- Leverage or exposure caveat: none; binary 0/1 exposure and target volatility disabled.

## Decision

- Decision: `keep_linear_weight_power_1_pending_user_confirmation`.
- Recommended next action: keep the simple current linear weighting; reject equal weights as a simplification and retain 1.25 only as a recent-tilted research candidate. Stop for user confirmation.

## Finalization

- Finalized at: 2026-09-04T00:36:56+08:00
- Decision: keep_linear_weight_power_1_pending_user_confirmation
- Stability label: broad_0p75_1p25_support_equal_weight_rejected
- Complete checker: PASS
