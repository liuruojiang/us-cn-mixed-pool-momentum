# Quant Parameter Scan Record

## Run Metadata

- Run id: `20260903_mixed_us_cn_momentum_subd_pure_momentum_base_plus_overheat_six_etf_mixed_pool_overheat_derisk_scale`
- Created at: 2026-09-03T22:03:57+08:00
- Project: mixed-us-cn-momentum
- Strategy or version: SubD pure momentum base plus overheat
- Sleeve or subsystem: six-etf mixed pool
- Parameter group: `OVERHEAT_DERISK_SCALE`
- Scan type: `single_parameter`
- Repo or workspace path: `D:\动量策略\美股A股混合池子动量策略`
- Target entrypoint: `run_subd_six_etf_v1_1.py`
- Git branch: `codex/previous-research-sync-20260821`
- Git commit: `6bf19204abca54f5ff7d15ec1708cf03a0412669`
- Working tree status before:

```text
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_pure_momentum_base_plus_staged_entry_six_etf_mixed_pool_initial_entry_fraction_r2_off/
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_plus_staged_entry_six_etf_mixed_pool_initial_entry_fraction/
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_extended_at_buffer_1_00/
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/
```

## Research Question

- Baseline: pure momentum base with R2 off, Buffer 1.00, full entry 1.00, 0.10% one-way cost, and overheat scale 1.00 (disabled).
- Candidate grid: overheat derisk scale `1.00 / 0.90 / 0.75 / 0.50 / 0.25 / 0.10 / 0.00`; formal MA60 bias enter 20%, exit 18%, same-side momentum confirmation retained.
- Decision target: isolate whether overheat exposure reduction adds robust value and whether the current full exit scale 0.00 is supported.
- Source-change rule: `research_only_no_source_change`
- Required windows: full, 10Y, 5Y, 3Y, 1Y
- Required metrics: annual return, annualized volatility, Sharpe, max drawdown, and strategy-specific exposure/cost metrics
- Promotion threshold: require multi-window improvement and a neighboring scale plateau; reduced drawdown caused only by reduced exposure is not enough.
- Rerun triggers: baseline parity failure, frozen-input mismatch, missing required window, or accidental activation of R2/Buffer/staging/target-vol.

## Implementation Anchor

- Official entrypoint: `run_subd_six_etf_v1_1.py`.
- Function or command path: accepted pure-base daily curve -> `build_overheat_features` -> official `apply_overheat_overlay`.
- Existing loaders reused: frozen same-session qfq panel and pure-base daily curve.
- Existing metrics reused: official trading-day windows and return/wealth/max-drawdown conventions.
- Default values and source locations: MA60, bias momentum 20 days, enter 0.20, exit 0.18, derisk scale 0.00 in `run_subd_six_etf_v1_1.py`.

| parameter | default | source location |
| --- | ---: | --- |
| `R2_THRESHOLD` | off | pure base |
| `SWITCH_BUFFER` | 1.00 | pure base |
| `INITIAL_ENTRY_FRACTION` | 1.00 | pure base |
| `CN_BIAS_N / CN_MOM_DAY` | 60 / 20 | `run_subd_six_etf_v1_1.py` |
| `OVERHEAT_ENTER / EXIT` | 0.20 / 0.18 | `run_subd_six_etf_v1_1.py` |
| `OVERHEAT_DERISK_SCALE` | 0.00 | `run_subd_six_etf_v1_1.py` |
| `ONE_WAY_COST` | 0.001 | `run_subd_six_etf_v1_1.py` |

## Data Snapshot

- Run timestamp: 2026-09-03 Asia/Shanghai; successful measured runtime 25.440 seconds.
- Raw data start: 2011-12-09.
- Raw data end: 2026-09-02.
- Metrics start after warmup: momentum score first eligible on 2012-01-16; overheat MA60 and bias-momentum warmups remain fail-closed until available.
- Metrics end: 2026-09-02.
- Latest trading date or snapshot: 2026-09-02.
- Data sources: frozen qfq/front-adjusted six-ETF panel from the accepted same-session formal scan.
- Local cache paths: source `price_snapshot_qfq.csv.gz`; accepted pure-base daily curve from the corrected staged-entry scan.
- Cache write risk: none; no remote refresh.
- Missing or stale data: inherited matched boundary through 2026-09-02 because one ETF lagged by one session in the source run.
- Alignment rules: exact 3,578-row panel and forward-fill flags reused.
- Adjustment mode: qfq/front-adjusted only.
- Trading calendar: previously validated China-session index.
- Timezone assumptions: Asia/Shanghai; close-confirmed/close-executed research convention.

## Cost and Execution Assumptions

- Commission: represented inside aggregate one-way cost.
- Slippage: represented inside aggregate one-way cost.
- Open-impact: none separately.
- Financing: none; leverage disabled.
- Borrow or shorting cost: none; long/cash only.
- Rebalance timing: daily close-confirmed overheat state; exposure change applies through the official next-state/effective-state path.
- Fill timing: close convention; new exposure earns return from the next row.
- Leverage or sizing rules: base maximum 1.0; only overheat scale changes exposure.
- Hedge assumptions: no hedge.

## Runtime Override Plan

- Override mechanism: immutable `OverheatCase.derisk_scale` argument. The overlay execution guard internally references the global staged-entry fraction, so it is temporarily set to 1.00 to keep staging disabled as required.
- Values restored after each candidate: the original staged-entry fraction is restored in `finally` after the full grid.
- Default candidate included in same run: yes, current 0.00 and disabled 1.00.
- Parity check against official/default output: scale 1.00 output must match the accepted pure-base daily return/NAV/turnover/exposure.
- If parity check failed, explanation: first attempt exposed a hidden dependency on global staged-entry fraction and was rejected. The corrected run set that runtime value to 1.00 and restored it afterward. Daily return/turnover/exposure parity passed; cumulative NAV differed only by `1.4957e-12`, inside the `1e-10` cumulative tolerance.

## Commands

```powershell
python -X utf8 quant_param_scan_runs\20260903_mixed_us_cn_momentum_subd_pure_momentum_base_plus_overheat_six_etf_mixed_pool_overheat_derisk_scale\run_scan.py
```

## Output Files

- `scan_summary.csv`: 35 rows = 7 scales x 5 required windows.
- `window_metrics.csv`: 7-row wide comparison with deltas versus scale 1.00/off.
- `scan_meta.json`: this run metadata
- `command_log.txt`: commands, rejected hidden-staging attempt, repair, and parity policy.
- `parity_checks.csv`: pure-base disabled-overlay parity.
- `daily_outputs/`: daily output for all seven scales.
- `event_attribution.csv`: 13 trigger-episode contribution audit.

## Full-Sample Results

| overheat scale | annual return | delta vs off | max drawdown | MDD delta | Sharpe | avg exposure |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1.00 / disabled | 23.05% | 0.00pp | -36.47% | 0.00pp | 0.972 | 89.44% |
| 0.90 | 23.21% | +0.16pp | -36.39% | +0.08pp | 0.979 | 89.35% |
| 0.75 | 23.45% | +0.40pp | -36.27% | +0.20pp | 0.989 | 89.21% |
| 0.50 | 23.85% | +0.80pp | -36.08% | +0.38pp | 1.005 | 88.99% |
| 0.25 | 24.24% | +1.20pp | -35.91% | +0.56pp | 1.020 | 88.77% |
| 0.10 | 24.47% | +1.43pp | -35.82% | +0.65pp | 1.028 | 88.63% |
| 0.00 / current | 24.63% | +1.58pp | -35.75% | +0.71pp | 1.033 | 88.54% |

Return and Sharpe improve monotonically as defense becomes stronger. The current boundary value 0.00 is best in this fixed-trigger sample.

## Window Results

Annual-return delta versus disabled:

| scale | Full | 10Y | 5Y | 3Y | 1Y |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.90 | +0.16pp | +0.17pp | +0.32pp | +0.46pp | +0.26pp |
| 0.75 | +0.40pp | +0.43pp | +0.81pp | +1.16pp | +0.63pp |
| 0.50 | +0.80pp | +0.85pp | +1.61pp | +2.30pp | +1.25pp |
| 0.25 | +1.20pp | +1.27pp | +2.41pp | +3.44pp | +1.85pp |
| 0.10 | +1.43pp | +1.52pp | +2.88pp | +4.12pp | +2.20pp |
| 0.00 | +1.58pp | +1.68pp | +3.20pp | +4.57pp | +2.43pp |

Scale 0.00 annual return / max drawdown is 24.63%/-35.75% Full, 35.85%/-19.24% 10Y, 51.60%/-19.24% 5Y, 65.62%/-17.18% 3Y, and 35.79%/-17.18% 1Y. Recent 3Y/1Y max drawdown is unchanged versus disabled despite higher return.

## Stability Classification

- Label: `data_sensitive` because the monotonic scale result rests on only 13 trigger episodes and 32 effective defense days.
- Evidence: every derisk scale below 1.00 improves annual return and Sharpe in all five windows; scale 0.00 is the boundary winner.
- Nearby-candidate behavior: the curve is smooth and monotonic rather than a one-point peak, but no interior optimum exists; stronger defense always looks better in this sample.
- Recent-window behavior: 1Y contains only four triggers and six effective defense days. Its +2.43pp annual-return delta is not an independent large-sample confirmation.
- Cost sensitivity: scale 0.00 raises cumulative modeled cost from 0.691 to 0.707; the measured return benefit survives the fixed 0.10% one-way cost.
- Data sensitivity: 9 of 13 episodes add value and 4 hurt. The three largest positive episodes contribute about 68.3% of summed episode alpha, indicating concentration.
- Leverage or exposure caveat: average exposure falls only from 89.44% to 88.54%; the gain is driven by avoiding specific days rather than broad volatility scaling.

## Decision

- Decision: `watchlist`. Do not delete the overheat mechanism yet because its fixed-threshold scale effect is uniformly positive, but do not accept scale 0.00 as robust until trigger thresholds are varied.
- Recommended next action: stop and wait for user confirmation. If approved, the next test within this same overheat mechanism should scan the enter threshold while holding the 2pp hysteresis width and scale 0.00 fixed; no unrelated parameter should start first.

## User-Facing Summary

The current full-exit overheat scale looks beneficial on the pure base, with higher return/Sharpe across every required window. However, only 13 historical episodes exist and the top three supply about 68% of event alpha. The scale parameter passes its first test but remains high-overfitting-risk until the trigger threshold has a stable neighborhood.

## Finalization

- Finalized at: 2026-09-03T22:10:59+08:00
- Decision: watchlist
- Stability label: data_sensitive
- Complete checker: PASS
