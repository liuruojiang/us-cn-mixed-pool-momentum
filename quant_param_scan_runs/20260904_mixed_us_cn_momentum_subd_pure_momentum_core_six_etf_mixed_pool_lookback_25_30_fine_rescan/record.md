# Quant Parameter Scan Record

## Run Metadata

- Run id: `20260904_mixed_us_cn_momentum_subd_pure_momentum_core_six_etf_mixed_pool_lookback_25_30_fine_rescan`
- Created at: 2026-09-04T00:06:13+08:00
- Project: mixed-us-cn-momentum
- Strategy or version: SubD pure momentum core
- Sleeve or subsystem: six-etf mixed pool
- Parameter group: `LOOKBACK 25-30 fine rescan`
- Scan type: `single_parameter_fine_rescan`
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
```

## Research Question

- Baseline: current 25-day pure momentum core.
- Candidate grid: integer lookbacks `25, 26, 27, 28, 29, 30`, step 1.
- Decision target: recheck whether moving right from the current 25-day edge improves robustness rather than only the full-sample peak.
- Source-change rule: `research_only_no_source_change`
- Required windows: full, 10Y, 5Y, 3Y, 1Y
- Required metrics: annual return, annualized volatility, Sharpe, max drawdown, and strategy-specific exposure/cost metrics
- Promotion threshold: no promotion from a single winning window; require acceptable return/drawdown trade-offs across Full/10Y/5Y/3Y/1Y and exact current-25 parity.
- Rerun triggers: current-25 parity failure, missing candidate/window, frozen-input mismatch, or accidental activation of R2/staging/overheat/target-vol.

## Implementation Anchor

- Official entrypoint: `run_subd_six_etf_v1_1.py`.
- Function or command path: frozen qfq panel -> official `run_staged_entry(full_entry, R2 off, Buffer 1.00)` -> `calc_scores` -> weighted log-slope Top1.
- Existing loaders reused: frozen six-ETF qfq panel from the accepted stripped-base research path.
- Existing metrics reused: official trading-day windows and return/NAV/max-drawdown conventions.
- Default values and source locations: `LOOKBACK=25` in `research_subd_six_etf_weighted_slope.py`, consumed by `weighted_slope_score_and_r2`, `calc_scores`, and `run_staged_entry`.

| parameter | default | source location |
| --- | ---: | --- |
| `LOOKBACK` | 25 | `research_subd_six_etf_weighted_slope.py` |

## Data Snapshot

- Run timestamp: 2026-09-04 Asia/Shanghai; 115.046 seconds.
- Raw data start: 2011-12-09.
- Raw data end: 2026-09-02 after matched-date clipping.
- Metrics start after warmup: formal leading cash rows are retained until each lookback becomes eligible.
- Metrics end: 2026-09-02.
- Latest trading date or snapshot: 2026-09-02.
- Data sources: frozen Tencent qfq six-ETF panel from the accepted stripped-base scan.
- Local cache paths: source `price_snapshot_qfq.csv.gz`; accepted current-25 curve `daily_outputs/full_entry_1.00.csv.gz` in the referenced source runs.
- Cache write risk: none; this rescan recomputed all six daily outputs into its own run folder.
- Missing or stale data: the frozen panel is clipped to 2026-09-02 because `159915.SZ` ended one session before the other five raw series; no proxy extension or forward-fill beyond the matched endpoint.
- Alignment rules: same six assets, China-session validation, matched end date, and unchanged pre-inception missing-value treatment.
- Adjustment mode: qfq/front-adjusted.
- Trading calendar: China trading-day calendar, 252 sessions per annualization year.
- Timezone assumptions: Asia/Shanghai; daily close-confirmed signal with next-row return realization.

## Cost and Execution Assumptions

- Commission: included in aggregate one-way cost.
- Slippage: included in aggregate one-way cost.
- Aggregate one-way cost: 0.10% on traded notional for every candidate.
- Open-impact: none separately; no open execution modeled.
- Financing: none; leverage disabled.
- Borrow or shorting cost: none; long/cash strategy only.
- Rebalance timing: daily close-confirmed Top1 selection.
- Fill timing: selected holding earns return from the next row under the official close convention.
- Leverage or sizing rules: binary 0/1 exposure; full entry.
- Hedge assumptions: no hedge.

## Runtime Override Plan

- Override mechanism: temporary runtime override of `subd.LOOKBACK`; production source unchanged.
- Values restored after each candidate: original module value restored in `finally` after the grid.
- Default candidate included in same run: yes, current 25 days.
- Parity check against official/default output: current-25 return/NAV/turnover/exposure/position matched the accepted pure-base artifact; runner/Poe matched exactly. Maximum NAV difference was `3.553e-15`, maximum other numeric difference `9.975e-17`, and position mismatch was zero.
- If parity check failed, explanation: not applicable; parity passed.

## Commands

```powershell
python -X utf8 quant_param_scan_runs\20260904_mixed_us_cn_momentum_subd_pure_momentum_core_six_etf_mixed_pool_lookback_25_30_fine_rescan\run_scan.py
```

## Output Files

- `scan_summary.csv`: 6 candidates x 5 required windows with performance, exposure, turnover, and cost metrics.
- `window_metrics.csv`: one row per lookback with Full/10Y/5Y/3Y/1Y metrics and deltas versus 25 days.
- `parity_checks.csv`: current-25 checks versus the accepted pure base and Poe implementation.
- `daily_outputs/*.csv.gz`: six independently rebuilt daily paths.
- `scan_meta.json`: this run metadata
- `command_log.txt`: initialization command and future scan commands

## Full-Sample Results

| lookback | annual return | max drawdown | Sharpe | trade days | cost total |
| ---: | ---: | ---: | ---: | ---: | ---: |
| **25 baseline** | 23.05% | -36.47% | 0.972 | 384 | 0.691 |
| 26 | 25.19% | -45.15% | 1.046 | 363 | 0.659 |
| 27 | 24.74% | -44.03% | 1.027 | 351 | 0.637 |
| 28 | 23.90% | -45.06% | 0.992 | 347 | 0.627 |
| **29** | **28.21%** | -38.09% | **1.127** | 319 | 0.573 |
| 30 | 26.73% | -48.67% | 1.081 | 306 | 0.551 |

## Window Results

| lookback | Full ann./MDD | 10Y ann./MDD | 5Y ann./MDD | 3Y ann./MDD | 1Y ann./MDD |
| ---: | ---: | ---: | ---: | ---: | ---: |
| **25** | 23.05% / -36.47% | 34.17% / -21.48% | 48.40% / -21.48% | **61.05%** / -17.18% | 33.36% / -17.18% |
| **26** | 25.19% / -45.15% | **38.48%** / **-19.46%** | **48.44%** / -19.46% | 56.79% / -18.46% | 21.03% / -18.46% |
| **27** | 24.74% / -44.03% | 36.10% / -20.18% | 46.24% / -20.18% | 54.05% / **-16.26%** | 32.36% / **-16.26%** |
| **28** | 23.90% / -45.06% | 33.31% / -22.15% | 42.12% / -22.15% | 49.63% / -18.00% | 25.71% / -18.00% |
| **29** | **28.21%** / -38.09% | 37.45% / -19.77% | 44.39% / -17.96% | 50.99% / -17.96% | 20.33% / -16.81% |
| **30** | 26.73% / -48.67% | 35.75% / -25.18% | 45.39% / **-17.65%** | 56.44% / -17.65% | 31.14% / -17.65% |

## Stability Classification

- Label: `mixed_window_tradeoff`.
- Evidence: 29 days is the Full return/Sharpe winner and remains strong over 10Y, while 26 wins 10Y/5Y and 25 wins 3Y; no point dominates every required window.
- Nearby-candidate behavior: 26-28 materially deepen Full drawdown to about -44% to -45%; 30 deepens it to -48.67%. The 29-day point is separated from those drawdown failures but does not preserve recent-window returns.
- Recent-window behavior: 29-day 1Y return is 20.33%, 13.03 percentage points below 25 days; 25-day 3Y return remains highest.
- Cost sensitivity: all candidates include 0.10% one-way cost. Modeled total cost falls monotonically from 0.691 at 25 days to 0.551 at 30 days.
- Data sensitivity: the winner changes by window: Full 29, 10Y/5Y 26, 3Y 25, and 1Y 25 within this restricted grid.
- Leverage or exposure caveat: none; binary 0/1 exposure and target volatility disabled.

## Decision

- Decision: `keep_25_formal_base_record_29_as_unpromoted_right_shift_candidate`.
- Recommended next action: retain 25 days in the formal pure base, preserve 29 days as a right-shift return-heavy research candidate, and move to the next single parameter only after the user's 2026-09-04 confirmation to record this result.

## Finalization

- Finalized at: 2026-09-04T00:11:23+08:00
- Decision: retain_25_baseline_and_29_challenger_pending_user_confirmation
- Stability label: mixed_window_tradeoff
- Complete checker: PASS

## Finalization

- Finalized at: 2026-09-04T00:23:28+08:00
- Decision: keep_25_formal_base_record_29_as_unpromoted_right_shift_candidate
- Stability label: mixed_window_tradeoff
- Complete checker: PASS
