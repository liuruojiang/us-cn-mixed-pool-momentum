# Quant Parameter Scan Record

## Run Metadata

- Run id: `20260903_mixed_us_cn_momentum_subd_pure_momentum_base_plus_staged_entry_six_etf_mixed_pool_initial_entry_fraction_r2_off`
- Created at: 2026-09-03T21:57:24+08:00
- Project: mixed-us-cn-momentum
- Strategy or version: SubD pure momentum base plus staged entry
- Sleeve or subsystem: six-etf mixed pool
- Parameter group: `INITIAL_ENTRY_FRACTION R2 OFF`
- Scan type: `single_parameter`
- Repo or workspace path: `D:\动量策略\美股A股混合池子动量策略`
- Target entrypoint: `run_subd_six_etf_v1_1.py`
- Git branch: `codex/previous-research-sync-20260821`
- Git commit: `6bf19204abca54f5ff7d15ec1708cf03a0412669`
- Working tree status before:

```text
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_plus_staged_entry_six_etf_mixed_pool_initial_entry_fraction/
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_extended_at_buffer_1_00/
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/
```

## Research Question

- Baseline: pure 25-day weighted-log-slope Top1 momentum, R2 off, Switch Buffer 1.00, full entry, and 0.10% one-way cost; every overlay disabled.
- Candidate grid: initial fraction `1.00 / 0.90 / 0.80 / 0.75 / 0.67 / 0.60 / 0.50 / 0.40 / 0.33 / 0.25 / 0.10`; values below 1.00 wait without timeout for the first down day before filling to 100%.
- Decision target: isolate staged entry on the user-specified pure momentum base.
- Source-change rule: `research_only_no_source_change`
- Required windows: full, 10Y, 5Y, 3Y, 1Y
- Required metrics: annual return, annualized volatility, Sharpe, max drawdown, and strategy-specific exposure/cost metrics
- Promotion threshold: require multi-window return/drawdown evidence and a neighboring plateau; no production promotion without user confirmation.
- Rerun triggers: parity failure, frozen-input mismatch, missing required window, or accidental activation of R2/Buffer/other overlays.

## Implementation Anchor

- Official entrypoint: `run_subd_six_etf_v1_1.py`.
- Function or command path: frozen formal qfq panel -> official `calc_scores(r2_threshold=None)` -> official `run_staged_entry`.
- Existing loaders reused: frozen same-session qfq panel from the formal R2 x Buffer scan.
- Existing metrics reused: official trading-day windows and return/wealth/max-drawdown conventions.
- Default values and source locations: staged-entry implementation in `run_subd_six_etf_v1_1.py`; research override disables R2 and Buffer.

| parameter | default | source location |
| --- | ---: | --- |
| `LOOKBACK` | 25 | pure momentum base |
| `R2_THRESHOLD` | off | user-required isolation |
| `SWITCH_BUFFER` | 1.00 | disabled |
| `INITIAL_ENTRY_FRACTION` | 0.50 | `run_subd_six_etf_v1_1.py` |
| `ONE_WAY_COST` | 0.001 | `run_subd_six_etf_v1_1.py` |

## Data Snapshot

- Run timestamp: 2026-09-03 Asia/Shanghai; measured runtime 68.292 seconds.
- Raw data start: 2011-12-09.
- Raw data end: 2026-09-02.
- Metrics start after warmup: score first eligible on 2012-01-16; full window retains prior cash warmup rows.
- Metrics end: 2026-09-02.
- Latest trading date or snapshot: 2026-09-02.
- Data sources: frozen qfq/front-adjusted six-ETF panel from the accepted same-session formal scan.
- Local cache paths: `price_snapshot_qfq.csv.gz` in the preceding R2 x Buffer run folder.
- Cache write risk: none; no data/calendar refresh.
- Missing or stale data: inherited matched boundary through 2026-09-02 because one ETF lagged the other five by one session in the source run.
- Alignment rules: exact 3,578-row panel and stored forward-fill flags reused.
- Adjustment mode: qfq/front-adjusted only.
- Trading calendar: previously validated China-session index.
- Timezone assumptions: Asia/Shanghai; close-confirmed/close-executed research convention.

## Cost and Execution Assumptions

- Commission: represented inside aggregate one-way cost.
- Slippage: represented inside aggregate one-way cost.
- Open-impact: none separately.
- Financing: none; leverage disabled.
- Borrow or shorting cost: none; long/cash only.
- Rebalance timing: daily close-confirmed signal.
- Fill timing: close convention; initial fraction on selection, remainder on first later down close, no timeout.
- Leverage or sizing rules: maximum 1.0; target-vol and leverage disabled.
- Hedge assumptions: no hedge.

## Runtime Override Plan

- Override mechanism: immutable `EntryCase.initial_fraction`; official R2-off scores cached by date and passed through official execution logic.
- Values restored after each candidate: original score function restored in `finally`.
- Default candidate included in same run: yes, current staged fraction 0.50 and disabled/full entry 1.00.
- Parity check against official/default output: full-entry baseline versus prior exact R2-off daily curve; cached 0.50 versus uncached official-function rerun.
- If parity check failed, explanation: not applicable. Pure-base baseline matched the prior exact R2-off curve, and cached 0.50 matched an uncached official-function rerun within `3.5527e-15`.

## Commands

```powershell
python -X utf8 quant_param_scan_runs\20260903_mixed_us_cn_momentum_subd_pure_momentum_base_plus_staged_entry_six_etf_mixed_pool_initial_entry_fraction_r2_off\run_scan.py
```

## Output Files

- `scan_summary.csv`: 55 rows = 11 fractions x 5 required windows.
- `window_metrics.csv`: 11-row wide comparison with deltas versus full entry.
- `scan_meta.json`: this run metadata
- `command_log.txt`: exact command, corrected base, source, runtime, and parity evidence.
- `parity_checks.csv`: pure-base and cached-score parity.
- `daily_outputs/`: daily output for all 11 fractions.

## Full-Sample Results

| initial fraction | annual return | delta vs full | max drawdown | MDD delta | Sharpe | avg exposure |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1.00 / disabled | 23.05% | 0.00pp | -36.47% | 0.00pp | 0.972 | 89.44% |
| 0.90 | 22.73% | -0.32pp | -36.42% | +0.04pp | 0.978 | 87.63% |
| 0.75 | 22.22% | -0.83pp | -36.38% | +0.08pp | 0.984 | 84.91% |
| 0.67 | 21.93% | -1.11pp | -36.37% | +0.09pp | 0.985 | 83.47% |
| 0.50 / current | 21.30% | -1.75pp | -36.39% | +0.08pp | 0.983 | 80.39% |
| 0.33 | 20.62% | -2.43pp | -36.44% | +0.03pp | 0.973 | 77.32% |
| 0.10 | 19.63% | -3.41pp | -36.70% | -0.24pp | 0.946 | 73.16% |

Full-sample annual return falls monotonically as the initial fraction falls. Full-sample drawdown barely changes because the staged rule does not protect the historical drawdown that dominates the pure base.

## Window Results

Annual return / max drawdown:

| initial fraction | Full | 10Y | 5Y | 3Y | 1Y |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1.00 / disabled | 23.05% / -36.47% | 34.17% / -21.48% | 48.40% / -21.48% | 61.05% / -17.18% | 33.36% / -17.18% |
| 0.50 / current | 21.30% / -36.39% | 30.55% / -18.50% | 45.59% / -18.50% | 54.99% / -13.61% | 34.18% / -13.61% |

At 0.50, annual-return deltas versus full entry are -1.75/-3.62/-2.80/-6.06/+0.82 percentage points across Full/10Y/5Y/3Y/1Y. Drawdown improves by only 0.08pp Full, versus 2.98pp/2.98pp/3.57pp/3.57pp in the shorter windows.

## Stability Classification

- Label: `recent_only` for the staged-entry feature; long-window return deterioration is broad and monotonic.
- Evidence: full entry has the highest annual return in Full, 10Y, 5Y, and 3Y. No staged fraction improves Full return, and the current 0.50 barely changes Full drawdown.
- Nearby-candidate behavior: all fractions below 1.00 lose Full/10Y/5Y/3Y return as staging becomes stronger; there is no useful return plateau.
- Recent-window behavior: 1Y improves modestly for all staged fractions, peaking around 0.33-0.40, but this does not persist into 3Y or longer windows.
- Cost sensitivity: cumulative modeled cost falls from 0.691 at full entry to 0.637 at 0.50; savings do not offset the long-window underexposure.
- Data sensitivity: exact frozen qfq panel and forward-fill flags reused; parity passed.
- Leverage or exposure caveat: 0.50 reduces average exposure from 89.44% to 80.39%. Recent drawdown improvement is partly mechanical underexposure rather than independent entry alpha.

## Decision

- Decision: `promote_candidate` for research approval only: disable staged entry and use full entry 1.00 on the pure base. No production source is changed.
- Recommended next action: stop and wait for user confirmation. If accepted, retain the same pure base with full entry for the next single-parameter test.

## User-Facing Summary

On the correctly specified pure momentum base, the current 50% staged-entry rule is even less attractive: it sacrifices long-window return, adds only a recent-1Y benefit, and barely improves Full drawdown. Full entry 1.00 is the simplification candidate. Stop here pending confirmation.

## Finalization

- Finalized at: 2026-09-03T22:01:34+08:00
- Decision: promote_candidate
- Stability label: recent_only
- Complete checker: PASS
