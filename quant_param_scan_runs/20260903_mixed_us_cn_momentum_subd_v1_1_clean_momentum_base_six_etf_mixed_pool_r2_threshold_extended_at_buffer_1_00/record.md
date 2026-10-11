# Quant Parameter Scan Record

## Run Metadata

- Run id: `20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_extended_at_buffer_1_00`
- Created at: 2026-09-03T21:36:59+08:00
- Project: mixed-us-cn-momentum
- Strategy or version: SubD V1.1 clean momentum base
- Sleeve or subsystem: six-etf mixed pool
- Parameter group: `R2_THRESHOLD extended at buffer 1.00`
- Scan type: `single_parameter`
- Repo or workspace path: `D:\动量策略\美股A股混合池子动量策略`
- Target entrypoint: `run_subd_six_etf_v1_1.py`
- Git branch: `codex/previous-research-sync-20260821`
- Git commit: `6bf19204abca54f5ff7d15ec1708cf03a0412669`
- Working tree status before:

```text
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/
```

## Research Question

- Baseline: R2 off, Switch Buffer 1.00, 25-day weighted-log-slope Top1 momentum with 0.10% one-way transaction cost only.
- Candidate grid: `off / 0.000 / 0.010 / 0.025 / 0.050 / 0.075 / 0.100 / 0.125 / 0.150 / 0.175 / 0.200 / 0.225 / 0.250 / 0.275 / 0.300 / 0.325 / 0.350 / 0.375 / 0.400 / 0.450 / 0.500 / 0.600 / 0.700 / 0.800 / 0.900`.
- Decision target: find the lower and upper R2 crossover points versus R2-off, and determine whether deterioration outside 0.15-0.30 still remains better than no R2.
- Source-change rule: `research_only_no_source_change`
- Required windows: full, 10Y, 5Y, 3Y, 1Y
- Required metrics: annual return, annualized volatility, Sharpe, max drawdown, and strategy-specific exposure/cost metrics
- Promotion threshold: none; research-only boundary mapping. Require exact parity to the prior formal grid at overlapping thresholds.
- Rerun triggers: any parity failure, incomplete frozen input, missing required window, or change to cost/execution/base assumptions.

## Implementation Anchor

- Official entrypoint: `run_subd_six_etf_v1_1.py`.
- Function or command path: frozen formal qfq panel -> official `calc_scores` precomputation -> official `run_staged_entry(mode=full_entry)` with runtime-injected cached score lookup.
- Existing loaders reused: frozen output of the current formal qfq loader from the immediately preceding same-session scan.
- Existing metrics reused: official trading-day windows and return/wealth/max-drawdown conventions.
- Default values and source locations: R2 0.20 and Buffer 1.05 in `run_subd_six_etf_v1_1.py`; this isolation scan fixes Buffer at 1.00.

| parameter | default | source location |
| --- | ---: | --- |
| `LOOKBACK` | 25 | `research_subd_six_etf_weighted_slope.py` |
| `SCORE_MIN / SCORE_MAX` | 0.0 / 5.0 | `research_subd_six_etf_weighted_slope.py` |
| `R2_THRESHOLD` | 0.20 | `run_subd_six_etf_v1_1.py` |
| `SWITCH_BUFFER` | fixed 1.00 | research isolation |
| `ONE_WAY_COST` | 0.001 | `run_subd_six_etf_v1_1.py` |

## Data Snapshot

- Run timestamp: 2026-09-03 Asia/Shanghai; measured scan runtime 103.990 seconds.
- Raw data start: 2011-12-09.
- Raw data end: 2026-09-02.
- Metrics start after warmup: score first becomes eligible on 2012-01-16; formal full window retains prior cash warmup rows.
- Metrics end: 2026-09-02.
- Latest trading date or snapshot: 2026-09-02.
- Data sources: frozen qfq/front-adjusted six-ETF panel from the immediately preceding same-session formal scan.
- Local cache paths: source artifact `../20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/price_snapshot_qfq.csv.gz`.
- Cache write risk: none in this extension; no remote refresh or calendar-cache mutation was performed.
- Missing or stale data: inherited matched-date boundary; all assets restricted to 2026-09-02 because `159915.SZ` lagged the other five by one session in the source run.
- Alignment rules: exact reuse of the prior 3,578-row aligned panel and restored forward-fill flags.
- Adjustment mode: qfq/front-adjusted only.
- Trading calendar: already validated China session index from the source run.
- Timezone assumptions: Asia/Shanghai, close-confirmed research convention.

## Cost and Execution Assumptions

- Commission: represented inside the aggregate one-way cost.
- Slippage: represented inside the aggregate one-way cost.
- Open-impact: none separately.
- Financing: none; leverage disabled.
- Borrow or shorting cost: none; long/cash only.
- Rebalance timing: daily close-confirmed signal.
- Fill timing: close convention; new position earns return from the next row.
- Leverage or sizing rules: full-entry binary 0/1 exposure; all sizing overlays disabled.
- Hedge assumptions: no hedge.

## Runtime Override Plan

- Override mechanism: cache only the output of the official score function by date, then runtime-filter by threshold inside the official execution function.
- Values restored after each candidate: the original `subd.calc_scores` is restored in a `finally` block.
- Default candidate included in same run: yes, R2 0.20; R2-off baseline also included.
- Parity check against official/default output: compare all five metrics at seven overlapping thresholds and compare daily return/NAV at R2-off and R2 0.20 against the prior exact-function scan.
- If parity check failed, explanation: not applicable. Seven overlapping threshold/window metric sets plus R2-off and R2-0.20 daily curves matched the preceding exact-function scan with maximum absolute difference `7.1054e-15`.

## Commands

```powershell
python -X utf8 quant_param_scan_runs\20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_extended_at_buffer_1_00\run_scan.py
```

## Output Files

- `scan_summary.csv`: 125 rows = 25 thresholds x 5 required windows.
- `window_metrics.csv`: 25-row wide comparison with return and drawdown deltas versus R2-off.
- `scan_meta.json`: this run metadata
- `command_log.txt`: initialization, frozen-input, runtime-override, and scan command details.
- `parity_checks.csv`: overlapping-grid and daily-curve parity evidence.
- `daily_outputs/`: selected boundary and reference thresholds.

## Full-Sample Results

| R2 threshold | annual return | delta vs off | max drawdown | MDD delta vs off | holding ratio |
| ---: | ---: | ---: | ---: | ---: | ---: |
| off / 0.000 | 23.05% | 0.00pp | -36.47% | 0.00pp | 89.44% |
| 0.050 | 22.91% | -0.14pp | -34.80% | +1.66pp | 85.30% |
| 0.075 | 23.72% | +0.68pp | -33.39% | +3.08pp | 84.24% |
| 0.125 | 27.28% | +4.24pp | -25.27% | +11.19pp | 82.17% |
| 0.175 | 30.16% | +7.12pp | -21.97% | +14.49pp | 80.21% |
| 0.200 | 29.46% | +6.42pp | -24.40% | +12.07pp | 79.26% |
| 0.250 | 30.91% | +7.87pp | -25.44% | +11.03pp | 77.45% |
| 0.300 | 26.40% | +3.36pp | -25.72% | +10.75pp | 75.55% |
| 0.350 | 25.14% | +2.09pp | -24.16% | +12.31pp | 73.28% |
| 0.375 | 21.60% | -1.44pp | -25.51% | +10.96pp | 71.88% |
| 0.500 | 12.15% | -10.90pp | -27.01% | +9.46pp | 63.61% |
| 0.700 | 4.95% | -18.10pp | -40.84% | -4.38pp | 41.50% |
| 0.900 | -1.36% | -24.40pp | -18.48% | +17.98pp | 4.42% |

For full-sample annual return, the observed lower crossover lies between 0.050 and 0.075, while the upper crossover lies between 0.350 and 0.375. Values beyond those brackets were not interpolated or claimed as exact thresholds.

## Window Results

Annual-return delta versus R2-off, in percentage points:

| R2 | Full | 10Y | 5Y | 3Y | 1Y |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.050 | -0.14 | +0.04 | +0.49 | +0.67 | +2.12 |
| 0.075 | +0.68 | -0.78 | +0.26 | -0.41 | +0.64 |
| 0.100 | +1.32 | -0.12 | +1.74 | -0.37 | -1.16 |
| 0.125 | +4.24 | +1.24 | +3.76 | +2.77 | +3.74 |
| 0.150 | +4.50 | +1.21 | +3.47 | +3.04 | +5.13 |
| 0.300 | +3.36 | -2.70 | +1.23 | +0.16 | +25.82 |
| 0.325 | +2.80 | -4.10 | -1.72 | -5.69 | +19.36 |
| 0.350 | +2.09 | -5.75 | -2.08 | -7.36 | +19.44 |
| 0.375 | -1.44 | -10.23 | -10.14 | -19.77 | +3.95 |
| 0.400 | -3.56 | -12.01 | -13.99 | -23.27 | +3.09 |
| 0.500 | -10.90 | -17.67 | -20.58 | -32.18 | +6.15 |

All five annual-return windows beat R2-off from 0.125 through 0.275. At 0.300, four of five beat R2-off but 10Y is already worse. At 0.325 and 0.350 only Full and 1Y remain better; the Full advantage is therefore not broad multi-window evidence.

## Stability Classification

- Label: `wide_stable` for retaining an R2 filter, not for choosing the single best threshold.
- Evidence: thresholds 0.125-0.275 beat R2-off on annual return in every required window; 0.15, 0.175, 0.25, and 0.275 also improve max drawdown in every window.
- Nearby-candidate behavior: Full-sample improvement extends approximately from 0.075 through 0.350, but robust five-window improvement is narrower at 0.125-0.275.
- Recent-window behavior: thresholds 0.300-0.600 retain a positive 1Y delta while most longer windows deteriorate. This is a regime-concentration warning, not evidence that the high-threshold tail remains generally superior.
- Cost sensitivity: frozen 0.10% one-way cost; turnover generally declines as the threshold rises, but reduced cost does not prevent high thresholds from underperforming.
- Data sensitivity: exact frozen panel and forward-fill flags reused; parity to the preceding formal grid passed.
- Leverage or exposure caveat: higher R2 thresholds increasingly sit in cash; by 0.900 the holding ratio is only 4.42%, making its smaller drawdown economically incomparable to the active baseline.

## Decision

- Decision: `keep_default`. Retain the R2 feature and keep 0.20 as the conservative default inside the broad robust region; do not promote the in-sample peaks at 0.175 or 0.25 from this scan alone.
- Recommended next action: proceed with simplification using `R2 0.20 / Switch Buffer 1.00`, then evaluate the next suspected overlay. If R2 itself is revisited later, use non-overlapping/walk-forward tests centered on 0.125-0.275 rather than extending the tail further.

## User-Facing Summary

The answer depends on the definition of improvement. Full-sample return remains above R2-off up to 0.350 and starts below it at 0.375. However, broad improvement across Full/10Y/5Y/3Y/1Y exists only from 0.125 through 0.275. On the high side, 0.300-0.350 is increasingly a recent-1Y effect, so it should not be treated as generally better than no R2.

## Finalization

- Finalized at: 2026-09-03T21:42:59+08:00
- Decision: keep_default
- Stability label: wide_stable
- Complete checker: PASS
