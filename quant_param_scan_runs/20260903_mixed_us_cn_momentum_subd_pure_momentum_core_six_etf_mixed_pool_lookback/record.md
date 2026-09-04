# Quant Parameter Scan Record

## Run Metadata

- Run id: `20260903_mixed_us_cn_momentum_subd_pure_momentum_core_six_etf_mixed_pool_lookback`
- Created at: 2026-09-03T23:32:46+08:00
- Project: mixed-us-cn-momentum
- Strategy or version: SubD pure momentum core
- Sleeve or subsystem: six-etf mixed pool
- Parameter group: `LOOKBACK momentum window`
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
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_plus_staged_entry_six_etf_mixed_pool_initial_entry_fraction/
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_extended_at_buffer_1_00/
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/
```

## Research Question

- Baseline: current 25-day pure momentum core; R2 off, Buffer 1.00, full entry, overheat off, target vol off, one-way cost 0.10%.
- Candidate grid: user-requested exhaustive integer grid from `10` through `50` trading days. Earlier coarse points outside this range remain only as preliminary diagnostics and are excluded from the final result tables.
- Decision target: test whether the current 25-day momentum lookback has a broad neighboring plateau or is an isolated fitted point.
- Source-change rule: `research_only_no_source_change`
- Required windows: full, 10Y, 5Y, 3Y, 1Y
- Required metrics: annual return, annualized volatility, Sharpe, max drawdown, and strategy-specific exposure/cost metrics
- Promotion threshold: current 25 days should retain multi-window competitiveness with neighboring support; a single full-sample maximum is insufficient.
- Rerun triggers: current-25 parity failure, runner/Poe mismatch, frozen-input mismatch, missing required window, or accidental activation of R2/Buffer/staging/overheat/target-vol.

## Implementation Anchor

- Official entrypoint: `run_subd_six_etf_v1_1.py` with `research_subd_six_etf_weighted_slope.py` score calculation.
- Function or command path: frozen qfq panel -> official `run_staged_entry(full_entry, R2 off, Buffer 1.00)` -> `calc_scores` -> weighted log-slope Top1.
- Existing loaders reused: frozen six-ETF qfq panel and accepted 25-day pure-base daily curve.
- Existing metrics reused: official trading-day windows and return/wealth/max-drawdown conventions.
- Default values and source locations: `LOOKBACK=25` in `research_subd_six_etf_weighted_slope.py`; consumed by `weighted_slope_score_and_r2`, `calc_scores`, and `run_staged_entry`.

| parameter | default | source location |
| --- | ---: | --- |
| `LOOKBACK` | 25 | `research_subd_six_etf_weighted_slope.py` |
| recency weights | `1..LOOKBACK` | `weighted_slope_score_and_r2` |
| score bounds | `0 < score < 5` | `calc_scores` |

## Data Snapshot

- Run timestamp: 2026-09-03 Asia/Shanghai; coarse, refinement, and final exhaustive 10-50 pass took 792.753 seconds in total, with same-run daily-output reuse.
- Raw data start: 2011-12-09.
- Raw data end: 2026-09-02 after matched-date clipping.
- Metrics start after warmup: each candidate retains formal leading cash rows until its own lookback becomes eligible.
- Metrics end: 2026-09-02.
- Latest trading date or snapshot: 2026-09-02.
- Data sources: frozen Tencent qfq six-ETF panel from the accepted stripped-base scan.
- Local cache paths: source `price_snapshot_qfq.csv.gz`; accepted current-25 curve `daily_outputs/full_entry_1.00.csv.gz`.
- Cache write risk: none; frozen inputs are read-only and outputs stay inside this run folder.
- Missing or stale data: the frozen panel is clipped to 2026-09-02 because `159915.SZ` ended one session before the other five raw series; no proxy extension or forward-filled 2026-09-03 trade was introduced.
- Alignment rules: same six assets, China-session validation, matched end date, and unchanged pre-inception missing-value treatment.
- Adjustment mode: qfq/front-adjusted only.
- Trading calendar: China trading-day calendar, 252 sessions per annualization year.
- Timezone assumptions: Asia/Shanghai; daily close-confirmed signal with next-row return realization.

## Cost and Execution Assumptions

- Commission: represented inside aggregate one-way cost.
- Slippage: represented inside aggregate one-way cost.
- Aggregate one-way cost: 0.10% on traded notional for every candidate.
- Open-impact: none separately; no open execution modeled.
- Financing: none; leverage disabled.
- Borrow or shorting cost: none; long/cash strategy only.
- Rebalance timing: daily close-confirmed Top1 selection.
- Fill timing: signal-selected holding earns its return from the next row under the official close convention.
- Leverage or sizing rules: binary 0/1 exposure; full entry.
- Hedge assumptions: no hedge.

## Runtime Override Plan

- Override mechanism: temporary runtime override of `subd.LOOKBACK`; no production-source edit.
- Values restored after each candidate: original module value restored in `finally` after the grid.
- Default candidate included in same run: yes, current 25 days.
- Parity check against official/default output: current-25 return/NAV/turnover/exposure/position must match the accepted pure-base artifact and the Poe implementation.
- If parity check failed, explanation: not applicable. Current-25 versus the accepted pure base had maximum absolute NAV difference `7.105e-15`, return difference `9.975e-17`, and zero turnover/exposure/position mismatch; runner/Poe differences were exactly zero.

## Commands

```powershell
python -X utf8 quant_param_scan_runs\20260903_mixed_us_cn_momentum_subd_pure_momentum_core_six_etf_mixed_pool_lookback\run_scan.py
```

## Output Files

- `scan_summary.csv`: 41 integer candidates from 10 through 50 days x 5 required windows, with return, volatility, Sharpe, drawdown, exposure, cash, turnover, and cost metrics.
- `window_metrics.csv`: one row per lookback with Full/10Y/5Y/3Y/1Y metrics and deltas versus current 25 days.
- `parity_checks.csv`: current-25 comparisons against the accepted pure base and the Poe implementation.
- `daily_outputs/*.csv.gz`: daily path for every lookback candidate; refinement passes reuse same-run files and compute only new candidates.
- `lookback_10_50_sensitivity.png`: Full/10Y/5Y/3Y/1Y annual-return and max-drawdown curves for the exhaustive integer grid.
- `scan_meta.json`: this run metadata
- `command_log.txt`: initialization, coarse scan, refinement, cache policy, and finalization commands.

## Full-Sample Results

| lookback | annual return | delta vs 25D | max drawdown | drawdown delta | Sharpe |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | -3.47% | -26.51pp | -78.65% | -42.19pp | -0.074 |
| 15 | 5.69% | -17.36pp | -54.96% | -18.49pp | 0.356 |
| 20 | 14.62% | -8.43pp | -27.91% | +8.56pp | 0.722 |
| 22 | 15.35% | -7.70pp | -35.49% | +0.98pp | 0.742 |
| 23 | 19.88% | -3.17pp | -33.94% | +2.53pp | 0.888 |
| 24 | 24.17% | +1.13pp | -34.64% | +1.83pp | 1.025 |
| **25 current** | **23.05%** | **0.00pp** | **-36.47%** | **0.00pp** | **0.972** |
| 26 | 25.19% | +2.15pp | -45.15% | -8.69pp | 1.049 |
| 27 | 24.74% | +1.70pp | -44.03% | -7.56pp | 1.031 |
| 28 | 23.90% | +0.86pp | -45.06% | -8.59pp | 0.994 |
| 29 | 28.21% | +5.17pp | -38.09% | -1.62pp | 1.127 |
| 30 | 26.73% | +3.69pp | -48.67% | -12.20pp | 1.081 |
| 31 | 26.10% | +3.05pp | -34.96% | +1.51pp | 1.074 |
| 32 | 24.15% | +1.11pp | -40.57% | -4.10pp | 1.012 |
| 33 | 23.26% | +0.22pp | -43.26% | -6.79pp | 0.963 |
| 34 | 20.07% | -2.97pp | -39.88% | -3.42pp | 0.852 |
| 40 | 14.21% | -8.84pp | -26.52% | +9.95pp | 0.638 |
| 50 | 11.75% | -11.29pp | -32.64% | +3.83pp | 0.555 |

The exhaustive 10-50 grid confirms that the only strong full-sample cluster is approximately 24-33 trading days; 34-35 remain just above 20% but are already decaying. The current 25 days is not an isolated spike, while the sharp deterioration below 24 and beyond 33-35 shows that this is a narrow regime rather than a globally insensitive parameter.

## Window Results

Representative candidates around the local band:

| lookback | Full ann. | 10Y ann. | 5Y ann. | 3Y ann. | 1Y ann. | Full MDD |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 23 | 19.88% | 26.98% | 38.76% | 44.43% | 31.19% | -33.94% |
| 24 | 24.17% | 31.91% | 44.84% | 56.83% | 34.07% | -34.64% |
| **25 current** | **23.05%** | **34.17%** | **48.40%** | **61.05%** | **33.36%** | **-36.47%** |
| 26 | 25.19% | 38.48% | 48.44% | 56.79% | 21.03% | -45.15% |
| 29 | 28.21% | 37.45% | 44.39% | 50.99% | 20.33% | -38.09% |
| 31 | 26.10% | 31.25% | 42.14% | 53.03% | 39.74% | -34.96% |
| 33 | 23.26% | 28.85% | 41.65% | 56.43% | 26.50% | -43.26% |

The best annual-return lookback shifts materially by window: Full `29`, 10Y/5Y `26`, 3Y `25`, and 1Y `15`. No single retuned value has cross-window authority. Current 25 days remains the best 3Y value, is effectively tied with 26 on 5Y, and avoids the much deeper full-sample drawdown of 26/27/28/30.

## Stability Classification

- Label: `narrow_stable_core`.
- Evidence: the exhaustive integer grid from 10 through 50 confirms that 24-33 days form the sole supported full-sample return cluster, so 25 days is not an isolated optimum. The current value also reproduces the accepted pure base and Poe path within numerical tolerance.
- Cross-window dominance: no alternative from 10 through 50 matches or beats current 25 days on all five annual-return windows, all five max-drawdown windows, or both sets together.
- Nearby-candidate behavior: 24 and 26-day paths differ from current positions on only 4.16% and 3.52% of rows, with return correlations 0.961 and 0.969. Both raise full-sample return, but 26 worsens drawdown by 8.69pp; 24 lowers 10Y/5Y/3Y return. There is no unambiguous adjacent replacement.
- Recent-window behavior: the 1Y optimum moves to 15 days while the 3Y optimum is current 25 days. This large drift argues against retuning to any recent winner.
- Cost sensitivity: all candidates include 0.10% one-way cost. Full-sample modeled cost declines from 0.729 at 24 days to 0.691 at 25, 0.659 at 26, and 0.573 at 29; longer-window return gains partly benefit from lower turnover. Higher-cost sensitivity was not separately scanned.
- Data sensitivity: the Full/10Y/5Y/3Y/1Y winners are 29/26/26/25/15 days. The exact optimum is sample-sensitive even though the 24-33 region is supported.
- Formula interaction: `SCORE_MAX=5` is held fixed. Changing lookback also changes the distribution of annualized slope scores relative to that veto, so sharp boundary behavior cannot be attributed to horizon alone without a later score-cap scan.
- Leverage or exposure caveat: none; binary 0/1 exposure, target volatility disabled.

## Decision

- Decision: `keep_current_pending_user_confirmation`.
- Recommended next action: retain the simple 25-trading-day core lookback and do not retune to 29 (Full winner), 26 (10Y/5Y winner), or 15 (1Y winner). Treat the exact optimum as data-sensitive; proceed to the next parameter only after user confirmation.

## Finalization

- Finalized at: 2026-09-03T23:56:12+08:00 after the user-requested exhaustive 10-50 expansion
- Decision: keep_current_pending_user_confirmation
- Stability label: narrow_stable_core
- Complete checker: PASS
