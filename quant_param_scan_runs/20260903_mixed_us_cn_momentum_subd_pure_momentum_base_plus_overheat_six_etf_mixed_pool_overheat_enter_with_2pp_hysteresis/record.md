# Quant Parameter Scan Record

## Run Metadata

- Run id: `20260903_mixed_us_cn_momentum_subd_pure_momentum_base_plus_overheat_six_etf_mixed_pool_overheat_enter_with_2pp_hysteresis`
- Created at: 2026-09-03T22:24:12+08:00
- Project: mixed-us-cn-momentum
- Strategy or version: SubD pure momentum base plus overheat
- Sleeve or subsystem: six-etf mixed pool
- Parameter group: `OVERHEAT_ENTER with 2pp hysteresis`
- Scan type: `single_parameter`
- Repo or workspace path: `D:\动量策略\美股A股混合池子动量策略`
- Target entrypoint: `run_subd_six_etf_v1_1.py`
- Git branch: `codex/previous-research-sync-20260821`
- Git commit: `6bf19204abca54f5ff7d15ec1708cf03a0412669`
- Working tree status before:

```text
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_pure_momentum_base_plus_overheat_six_etf_mixed_pool_overheat_derisk_scale/
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_pure_momentum_base_plus_staged_entry_six_etf_mixed_pool_initial_entry_fraction_r2_off/
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_plus_staged_entry_six_etf_mixed_pool_initial_entry_fraction/
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_extended_at_buffer_1_00/
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/
```

## Research Question

- Baseline: pure momentum with overheat disabled; R2 off, Buffer 1.00, full entry, one-way cost 0.10%.
- Candidate grid: broad scan `off / 5% / 7.5% / 10% / 12.5% / 15% / 17.5% / 20% / 22.5% / 25% / 27.5% / 30% / 35% / 40% / 45% / 50%`, plus dense refinement every 0.5 percentage point from 18% through 24%; exit equals enter minus 2 percentage points, scale fixed at 0.00.
- Decision target: test whether the current 20% trigger has a stable neighborhood and map performance/event-count boundaries.
- Source-change rule: `research_only_no_source_change`
- Required windows: full, 10Y, 5Y, 3Y, 1Y
- Required metrics: annual return, annualized volatility, Sharpe, max drawdown, and strategy-specific exposure/cost metrics
- Promotion threshold: require multi-window consistency, neighboring support, and enough independent trigger episodes; isolated event-driven gains are insufficient.
- Rerun triggers: current-20% parity failure, frozen-input mismatch, missing required window, or accidental activation of R2/Buffer/staging/target-vol.

## Implementation Anchor

- Official entrypoint: `run_subd_six_etf_v1_1.py`.
- Function or command path: accepted pure-base curve -> `build_overheat_features` -> official `apply_overheat_overlay`.
- Existing loaders reused: frozen qfq panel and pure-base daily curve.
- Existing metrics reused: official trading-day windows and return/wealth/max-drawdown conventions.
- Default values and source locations: MA60, 20-day bias momentum, enter 0.20, exit 0.18, scale 0.00 in `run_subd_six_etf_v1_1.py`.

| parameter | default | source location |
| --- | ---: | --- |
| `R2_THRESHOLD` | off | pure base |
| `SWITCH_BUFFER` | 1.00 | pure base |
| `INITIAL_ENTRY_FRACTION` | 1.00 | pure base |
| `CN_BIAS_N / CN_MOM_DAY` | 60 / 20 | fixed formal definition |
| `OVERHEAT_ENTER` | 0.20 | scanned |
| `OVERHEAT_EXIT` | enter - 0.02 | fixed hysteresis width |
| `OVERHEAT_DERISK_SCALE` | 0.00 | accepted scale candidate |

## Data Snapshot

- Run timestamp: 2026-09-03 Asia/Shanghai; final 27-candidate dense run took 99.458 seconds.
- Raw data start: 2011-12-09.
- Raw data end: 2026-09-02 after matched-date clipping.
- Metrics start after warmup: score first becomes eligible on 2012-01-16; the formal full window starts 2011-12-09 and retains the preceding cash warmup rows.
- Metrics end: 2026-09-02.
- Latest trading date or snapshot: 2026-09-02.
- Data sources: frozen Tencent qfq six-ETF price panel from the accepted stripped-base scan; no network refresh in this threshold scan.
- Local cache paths: source run `price_snapshot_qfq.csv.gz`, SHA256 `0cc4af45158d6aaab4594b869b79309a96e8e3cc2f21a0205c38128913bec2aa`; pure-base curve `daily_outputs/full_entry_1.00.csv.gz` from the corrected R2-off staged-entry scan.
- Cache write risk: none in this run; inputs were read-only frozen artifacts and all outputs were isolated in this run folder.
- Missing or stale data: the matched panel ends one session behind five of the six raw series because `159915.SZ` ended on 2026-09-02; no 2026-09-03 forward-filled price was traded.
- Alignment rules: same six assets, same China-session validation, same matched end date, and the same pre-inception missing-value treatment as the pure base.
- Adjustment mode: qfq/front-adjusted only.
- Trading calendar: China trading-day calendar, 252 sessions per annualization year.
- Timezone assumptions: Asia/Shanghai; daily close-confirmed research path.

## Cost and Execution Assumptions

- Commission: represented inside aggregate one-way cost.
- Slippage: represented inside aggregate one-way cost.
- Aggregate one-way cost: 0.10% on traded notional, unchanged for every candidate.
- Open-impact: none separately; no open execution is modeled.
- Financing: none; leverage disabled.
- Borrow or shorting cost: none; long/cash strategy only.
- Rebalance timing: daily close-confirmed overheat state.
- Fill timing: close convention through official next/effective exposure path.
- Leverage or sizing rules: pure-base full exposure or overheat cash; no target-vol/leverage.
- Hedge assumptions: no hedge.

## Runtime Override Plan

- Override mechanism: immutable `OverheatCase(enter, exit, scale=0)` arguments; runtime staged fraction forced to 1.00 because the overlay guard otherwise reads the production 0.50 global.
- Values restored after each candidate: original staged fraction restored in `finally`.
- Default candidate included in same run: yes, current 20%/18% and disabled baseline.
- Parity check against official/default output: 20% candidate daily return/NAV/turnover/exposure must match the accepted overheat-scale scan.
- If parity check failed, explanation: not applicable. Maximum absolute NAV difference was `3.553e-15`; return/exposure difference was at most `9.975e-17`; turnover difference was exactly zero.

## Commands

```powershell
python -X utf8 quant_param_scan_runs\20260903_mixed_us_cn_momentum_subd_pure_momentum_base_plus_overheat_six_etf_mixed_pool_overheat_enter_with_2pp_hysteresis\run_scan.py
```

## Output Files

- `scan_summary.csv`: 27 candidates x 5 required windows, with return, volatility, Sharpe, drawdown, exposure, turnover, cost, and trigger metrics.
- `window_metrics.csv`: one row per threshold with Full/10Y/5Y/3Y/1Y metrics and deltas versus overheat-off.
- `threshold_event_summary.csv`: independent event counts, positive/negative event counts, summed event alpha, and top-three concentration.
- `parity_checks.csv`: exact current-20% comparison against the prior accepted scale scan.
- `daily_outputs/*.csv.gz`: daily paths for the disabled baseline and every threshold candidate.
- `scan_meta.json`: this run metadata
- `command_log.txt`: initialization, refinement, run, and finalization commands.

## Full-Sample Results

| enter threshold | annual return | delta vs off | max drawdown | Sharpe | overheat days | trigger rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| off | 23.05% | 0.00pp | -36.47% | 0.972 | 0 | 0 |
| 17.5% | 20.91% | -2.14pp | -36.63% | 0.930 | 75 | 21 |
| 18.0% | 23.91% | +0.87pp | -36.63% | 1.006 | 63 | 20 |
| 18.5% | 23.34% | +0.29pp | -36.63% | 0.987 | 53 | 14 |
| 19.0% | 24.36% | +1.31pp | -35.75% | 1.025 | 40 | 15 |
| 19.5% | 24.65% | +1.61pp | -35.75% | 1.036 | 35 | 14 |
| **20.0% current** | **24.63%** | **+1.58pp** | **-35.75%** | **1.033** | **32** | **13** |
| 20.5% | 24.31% | +1.26pp | -35.72% | 1.021 | 27 | 11 |
| 21.0% | 24.56% | +1.52pp | -35.72% | 1.029 | 23 | 10 |
| 22.0% | 24.37% | +1.33pp | -35.72% | 1.021 | 14 | 6 |
| 22.5% / 23.0% | 24.53% | +1.48pp | -35.72% | 1.027 | 9 | 4 |
| 23.5% / 24.0% | 23.61% | +0.57pp | -35.72% | 0.992 | 5 | 3 |
| 25.0% | 23.47% | +0.42pp | -35.72% | 0.987 | 4 | 2 |
| 30.0% and above | 23.05% | 0.00pp | -36.47% | 0.972 | 0 | 0 |

The full-sample local plateau is roughly 19.0%-23.0%. The current 20% value is near the middle and is not the isolated best point; retuning to the in-sample best 19.5% is therefore not supported.

## Window Results

Current 20%/18% candidate versus the same pure momentum base:

| window | off annual return | current annual return | return delta | off max drawdown | current max drawdown | drawdown delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | 23.05% | 24.63% | +1.58pp | -36.47% | -35.75% | +0.71pp |
| 10Y | 34.17% | 35.85% | +1.68pp | -21.48% | -19.24% | +2.24pp |
| 5Y | 48.40% | 51.60% | +3.20pp | -21.48% | -19.24% | +2.24pp |
| 3Y | 61.05% | 65.62% | +4.57pp | -17.18% | -17.18% | 0.00pp |
| 1Y | 33.36% | 35.79% | +2.43pp | -17.18% | -17.18% | 0.00pp |

All five return windows improve at 20%. However, the 1Y result contains only four trigger rows and the full sample contains 13 trigger rows (13 event episodes, 9 positive and 4 negative), so window agreement is not equivalent to a large independent sample.

## Stability Classification

- Label: `data_sensitive` (locally supported threshold band, sparse-event evidence).
- Evidence: 19.0%-23.0% all beat overheat-off on Full/10Y/5Y/3Y annual return, and 20.0%-23.0% also beat it on 1Y. Current 20% improves full-sample annual return by 1.58pp and max drawdown by 0.71pp.
- Nearby-candidate behavior: 18.5% retains only +0.29pp full-sample improvement and loses on 10Y/5Y/3Y/1Y; 17.5% loses 2.14pp full-sample. Above 23%, event count collapses to three or fewer and the advantage fades. This is a real local platform, but not a broad insensitive range.
- Recent-window behavior: current 20% improves 1Y by 2.43pp, while 19.0% and 19.5% are each 2.96pp below off. Small threshold changes alter which few recent events are selected.
- Event concentration: current 20% has only 13 episodes across 3,578 rows; the top three positive episodes contribute 68.3% of summed event alpha. A diagnostic that replaces those three episode returns with base returns reduces annual return to 23.54% and worsens max drawdown to -38.77%; this is a concentration stress, not an executable alternative strategy.
- Cost sensitivity: not separately scanned; all candidates use the same 0.10% one-way rate. Current total modeled cost is 0.707 versus 0.691 for off, so the reported advantage is already net of its extra transitions but is not certified under higher costs.
- Data sensitivity: frozen data through 2026-09-02 only; no out-of-sample or walk-forward split was introduced in this one-parameter scan.
- Leverage or exposure caveat: none; the candidate switches between full pure-base exposure and cash, with target-vol/leverage disabled.

## Decision

- Decision: `confirmed_off`; the user confirmed on 2026-09-03 that the overheat mechanism is disabled in the V1.1 naive-mainline decision set.
- Recommended next action: keep overheat **off** in the pure/naive baseline. Preserve the pre-existing 20%/18%, full-exit definition only as a research candidate; do not retune it to 19.5%, 21%, or 22.5%. This records a research/mainline decision and does not by itself edit the existing production runner or Poe bot.

## Finalization

- Finalized at: 2026-09-03T22:35:03+08:00
- Decision: confirmed_off (user-confirmed after the scan; supersedes the provisional watchlist label)
- Stability label: data_sensitive
- Complete checker: PASS
