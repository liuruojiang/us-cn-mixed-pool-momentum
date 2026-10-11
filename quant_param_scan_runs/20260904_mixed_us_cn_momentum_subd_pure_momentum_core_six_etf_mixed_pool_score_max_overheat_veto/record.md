# Quant Parameter Scan Record

## Run Metadata

- Run id: `20260904_mixed_us_cn_momentum_subd_pure_momentum_core_six_etf_mixed_pool_score_max_overheat_veto`
- Created at: 2026-09-04T00:23:37+08:00
- Project: mixed-us-cn-momentum
- Strategy or version: SubD pure momentum core
- Sleeve or subsystem: six-etf mixed pool
- Parameter group: `SCORE_MAX overheat veto`
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
```

## Research Question

- Baseline: pure 25-day momentum core with current `SCORE_MAX=5`.
- Candidate grid: `2, 3, 4, 5, 6, 7, 8, 10, inf`; `inf` removes the upper veto.
- Decision target: determine whether the empirical upper score veto can be removed or simplified without degrading the pure base.
- Source-change rule: `research_only_no_source_change`
- Required windows: full, 10Y, 5Y, 3Y, 1Y
- Required metrics: annual return, annualized volatility, Sharpe, max drawdown, and strategy-specific exposure/cost metrics
- Promotion threshold: removal or retuning must remain competitive across Full/10Y/5Y/3Y/1Y returns and drawdowns, with neighboring support rather than a single-point win.
- Rerun triggers: score-max-5 parity failure, missing window/candidate, frozen-input mismatch, or accidental activation of another overlay.

## Implementation Anchor

- Official entrypoint: `run_subd_six_etf_v1_1.py`.
- Function or command path: frozen qfq panel -> official `run_staged_entry(full_entry, R2 off, Buffer 1.00)` -> `calc_scores` -> `SCORE_MIN < score < SCORE_MAX` -> weighted-log-slope Top1.
- Existing loaders reused: frozen six-ETF qfq panel and accepted pure-base curve.
- Existing metrics reused: official performance windows and NAV/max-drawdown conventions.
- Default values and source locations: `SCORE_MAX=5.0` in `research_subd_six_etf_weighted_slope.py`, consumed by `calc_scores`.

| parameter | default | source location |
| --- | ---: | --- |
| `SCORE_MAX` | 5.0 | `research_subd_six_etf_weighted_slope.py` |

## Data Snapshot

- Run timestamp: 2026-09-04 Asia/Shanghai; 141.737 seconds.
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

- Override mechanism: temporary runtime override of `subd.SCORE_MAX`; production source unchanged.
- Values restored after each candidate: original module value restored in `finally` after the grid.
- Default candidate included in same run: yes, current value 5.
- Parity check against official/default output: score-max-5 matched accepted pure base within `3.553e-15` NAV and `9.975e-17` other numeric tolerance; runner/Poe matched exactly with zero position mismatch.
- If parity check failed, explanation: not applicable; parity passed.

## Commands

```powershell
python -X utf8 quant_param_scan_runs\20260904_mixed_us_cn_momentum_subd_pure_momentum_core_six_etf_mixed_pool_score_max_overheat_veto\run_scan.py
```

## Output Files

- `scan_summary.csv`: 9 candidates x 5 required windows.
- `window_metrics.csv`: one row per score cap with performance/exposure/cost metrics and deltas versus 5.
- `parity_checks.csv`: current-5 checks against accepted pure base and Poe.
- `daily_outputs/*.csv.gz`: rebuilt daily path for every candidate.
- `scan_meta.json`: this run metadata
- `command_log.txt`: initialization command and future scan commands

## Full-Sample Results

| Score max | Full ann. | Full MDD | Sharpe | holding ratio | trade days | cost total |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2 | 7.62% | -52.13% | 0.462 | 85.94% | 542 | 0.969 |
| 3 | 15.10% | -44.13% | 0.740 | 88.01% | 473 | 0.855 |
| 4 | 18.46% | -45.55% | 0.831 | 88.76% | 419 | 0.755 |
| **5 current** | **23.05%** | -36.47% | **0.972** | 89.44% | 384 | 0.691 |
| 6 | 23.03% | **-35.71%** | 0.965 | 89.69% | 365 | 0.653 |
| 7 | 22.14% | -42.21% | 0.921 | 90.19% | 346 | 0.619 |
| 8 | 24.01% | -42.46% | 0.968 | 90.58% | 341 | 0.607 |
| 10 | 23.03% | -41.87% | 0.932 | 90.86% | 315 | 0.563 |
| inf | 21.57% | -38.55% | 0.830 | 91.14% | 272 | 0.481 |

## Window Results

| Score max | Full ann./MDD | 10Y ann./MDD | 5Y ann./MDD | 3Y ann./MDD | 1Y ann./MDD |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2 | 7.62% / -52.13% | 16.35% / -24.77% | 20.75% / -24.77% | 28.91% / -24.77% | 4.05% / -24.77% |
| 3 | 15.10% / -44.13% | 24.34% / -24.99% | 30.00% / -24.99% | 39.37% / -14.78% | 11.97% / -14.67% |
| 4 | 18.46% / -45.55% | 28.13% / -22.18% | 39.72% / -22.18% | 46.53% / -15.85% | 10.81% / -15.85% |
| **5** | **23.05% / -36.47%** | **34.17% / -21.48%** | 48.40% / -21.48% | 61.05% / -17.18% | 33.36% / -17.18% |
| **6** | 23.03% / **-35.71%** | 33.17% / -21.45% | 48.55% / -20.43% | 58.34% / -17.22% | 36.99% / -17.22% |
| 7 | 22.14% / -42.21% | 31.10% / -20.57% | 46.11% / -20.43% | 58.76% / -16.89% | 35.82% / -16.89% |
| 8 | **24.01%** / -42.46% | 31.68% / -23.68% | **49.66%** / -20.43% | **69.31%** / **-16.20%** | **56.08%** / **-16.12%** |
| 10 | 23.03% / -41.87% | 29.77% / -23.68% | 45.29% / -20.43% | 61.14% / -16.92% | 41.89% / -16.92% |
| inf | 21.57% / -38.55% | 23.26% / -30.05% | 31.55% / -30.05% | 36.68% / -30.05% | 19.29% / -19.96% |

## Stability Classification

- Label: `supported_5_6_plateau_cap_required`.
- Evidence: values 5 and 6 are economically near-identical on Full return and drawdown, while removing the cap degrades every required return window and every required drawdown window versus 5.
- Nearby-candidate behavior: 6 supports the current 5 as a neighboring plateau. Values 3-4 are materially weaker; 7 worsens Full drawdown, and the strong recent result at 8 is not supported by both neighbors.
- Recent-window behavior: 8 wins 3Y/1Y but has -42.46% Full drawdown and weaker 10Y return than 5; treat it as a sample-sensitive isolated point.
- Cost sensitivity: looser caps reduce trade days/cost, but the no-cap line still loses return and drawdown despite having the lowest cost.
- Data sensitivity: old QVeris evidence also favored the 4-6 area, but this run's conclusion relies on the current frozen Tencent qfq panel and exact pure-base path.
- Leverage or exposure caveat: none; binary 0/1 exposure and target volatility disabled.

## Decision

- Decision: `keep_score_max_5_user_confirmed`.
- Recommended next action: retain the score veto at 5, as confirmed by the user on 2026-09-04; proceed to the next single high-risk parameter while keeping all other overlays disabled.

## Finalization

- Finalized at: 2026-09-04T00:28:43+08:00
- Decision: keep_score_max_5_pending_user_confirmation
- Stability label: supported_5_6_plateau_cap_required
- Complete checker: PASS

## Finalization

- Finalized at: 2026-09-04T00:31:43+08:00
- Decision: keep_score_max_5_user_confirmed
- Stability label: supported_5_6_plateau_cap_required
- Complete checker: PASS
