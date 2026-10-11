# Quant Parameter Scan Record

## Run Metadata

- Run id: `20260903_mixed_us_cn_momentum_subd_pure_momentum_base_plus_target_vol_six_etf_mixed_pool_target_vol`
- Created at: 2026-09-03T22:40:16+08:00
- Project: mixed-us-cn-momentum
- Strategy or version: SubD pure momentum base plus target vol
- Sleeve or subsystem: six-etf mixed pool
- Parameter group: `TARGET_VOL with W80 max1.5 DB7.5pp`
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
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_plus_staged_entry_six_etf_mixed_pool_initial_entry_fraction/
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_extended_at_buffer_1_00/
?? quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/
```

## Research Question

- Baseline: pure momentum with target volatility disabled; R2 off, Buffer 1.00, full entry, overheat off, one-way cost 0.10%.
- Candidate grid: target volatility `off / 5% / 7.5% / 10% / 12.5% / 15% / 17.5% / 20% / 22.5% / 25% / 27.5% / 30% / 35% / 40% / 45% / 50% / 60% / 75% / 100%`.
- Decision target: determine whether the current 25% target-volatility level adds a broad, multi-window improvement over the pure base before testing any companion parameter.
- Source-change rule: `research_only_no_source_change`
- Required windows: full, 10Y, 5Y, 3Y, 1Y
- Required metrics: annual return, annualized volatility, Sharpe, max drawdown, and strategy-specific exposure/cost metrics
- Promotion threshold: require a neighboring target-volatility band, multi-window risk-adjusted support, and transparent leverage/cost dependence; an isolated CAGR or drawdown optimum is insufficient.
- Rerun triggers: off-baseline mismatch, runner/Poe current-25% parity failure, frozen-input mismatch, missing required window, or accidental activation of R2/Buffer/staging/overheat.

## Implementation Anchor

- Official entrypoint: `run_subd_six_etf_v1_1.py`.
- Function or command path: accepted pure-base curve -> official `apply_target_vol_overlay` -> drift-aware final execution ledger.
- Existing loaders reused: frozen qfq panel and the accepted pure-base daily curve; no remote refresh.
- Existing metrics reused: official trading-day windows and return/wealth/max-drawdown conventions.
- Default values and source locations: target 25% and scale deadband 7.5 percentage points in `run_subd_six_etf_v1_1.py`; window 80 and maximum leverage 1.5 in `research_subd_six_etf_weighted_slope.py`.

| parameter | default | source location |
| --- | ---: | --- |
| `TARGET_VOL` | 0.25 | `run_subd_six_etf_v1_1.py` |
| `TARGET_VOL_SCALE_REBALANCE_THRESHOLD` | 0.075 | `run_subd_six_etf_v1_1.py` |
| `DEFAULT_VOL_WINDOW` | 80 | `research_subd_six_etf_weighted_slope.py` |
| `DEFAULT_MAX_LEV` | 1.5 | `research_subd_six_etf_weighted_slope.py` |

## Data Snapshot

- Run timestamp: 2026-09-03 Asia/Shanghai; measured scan runtime 19.421 seconds.
- Raw data start: 2011-12-09.
- Raw data end: 2026-09-02 after matched-date clipping.
- Metrics start after warmup: formal full window retains warmup cash rows; 80-day target-vol estimator acts with its documented warmup behavior.
- Metrics end: 2026-09-02.
- Latest trading date or snapshot: 2026-09-02.
- Data sources: frozen Tencent qfq six-ETF price panel from the accepted stripped-base scan.
- Local cache paths: source `price_snapshot_qfq.csv.gz`; pure-base `daily_outputs/full_entry_1.00.csv.gz`.
- Cache write risk: none; frozen inputs are read-only and outputs stay inside this run folder.
- Missing or stale data: the frozen panel is clipped to 2026-09-02 because `159915.SZ` ended one session before the other five raw series; no proxy extension or forward-filled 2026-09-03 trade was introduced.
- Alignment rules: same six assets, China-session validation, matched end date, and the same pre-inception missing-value treatment as the pure base.
- Adjustment mode: qfq/front-adjusted only.
- Trading calendar: China trading-day calendar, 252 sessions per annualization year.
- Timezone assumptions: Asia/Shanghai; daily close-confirmed research path.

## Cost and Execution Assumptions

- Commission: represented inside aggregate one-way cost.
- Slippage: represented inside aggregate one-way cost.
- Aggregate one-way cost: 0.10% on traded notional for every candidate.
- Open-impact: none separately; no open execution is modeled.
- Financing: excluded, matching the current V1.1 research engine; leverage results must be read with this caveat.
- Borrow or shorting cost: none; long/cash strategy only.
- Rebalance timing: realized volatility uses prior daily strategy returns; computed target scale is shifted one row before becoming effective.
- Fill timing: close execution convention through the official drift-aware execution ledger.
- Leverage or sizing rules: target volatility divided by trailing 80-day realized volatility, clipped to `[0, 1.5]`; scale changes smaller than 0.075 retain the last confirmed scale.
- Hedge assumptions: no hedge.

## Runtime Override Plan

- Override mechanism: immutable function arguments only; no production constant or source edit.
- Values restored after each candidate: not applicable; module globals remain unchanged.
- Default candidate included in same run: yes, current target 25%, plus explicit disabled baseline.
- Parity check against official/default output: disabled candidate must exactly match the accepted pure base; current 25% daily return/NAV/turnover/exposure/scale must match the Poe implementation.
- If parity check failed, explanation: not applicable. Disabled-versus-pure-base and current-25%-runner-versus-Poe return, NAV, turnover, exposure, and scale differences were all exactly zero.

## Commands

```powershell
python -X utf8 quant_param_scan_runs\20260903_mixed_us_cn_momentum_subd_pure_momentum_base_plus_target_vol_six_etf_mixed_pool_target_vol\run_scan.py
```

## Output Files

- `scan_summary.csv`: 19 candidates x 5 required windows, including return, volatility, Sharpe, drawdown, exposure, leverage, scale, turnover, and cost metrics.
- `window_metrics.csv`: one row per target-volatility level with Full/10Y/5Y/3Y/1Y metrics and deltas versus disabled.
- `parity_checks.csv`: disabled-baseline and current-25% runner/Poe daily parity checks.
- `daily_outputs/*.csv.gz`: daily paths for the disabled baseline and every target-volatility candidate.
- `scan_meta.json`: this run metadata
- `command_log.txt`: initialization, run, and finalization commands.

## Full-Sample Results

| target vol | annual return | delta vs off | annual vol | max drawdown | drawdown delta | Sharpe | average exposure |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| off | 23.05% | 0.00pp | 24.37% | -36.47% | 0.00pp | 0.972 | 0.894 |
| 10.0% | 10.67% | -12.37pp | 11.40% | -19.33% | +17.14pp | 0.952 | 0.438 |
| 15.0% | 14.65% | -8.39pp | 16.65% | -29.52% | +6.95pp | 0.905 | 0.646 |
| 17.5% | 17.23% | -5.82pp | 19.30% | -33.54% | +2.93pp | 0.915 | 0.754 |
| 20.0% | 19.19% | -3.85pp | 21.76% | -37.08% | -0.61pp | 0.917 | 0.848 |
| 22.5% | 21.03% | -2.01pp | 23.99% | -40.02% | -3.55pp | 0.922 | 0.943 |
| **25.0% current** | **23.15%** | **+0.11pp** | **26.12%** | **-43.22%** | **-6.75pp** | **0.928** | **1.012** |
| 27.5% | 24.96% | +1.92pp | 27.95% | -45.66% | -9.19pp | 0.937 | 1.079 |
| 30.0% | 26.79% | +3.75pp | 29.49% | -47.47% | -11.00pp | 0.948 | 1.134 |
| 50.0% | 31.95% | +8.91pp | 35.24% | -53.88% | -17.41pp | 0.963 | 1.304 |
| 75.0% / 100.0% | 32.65% | +9.60pp | 35.85% | -51.63% | -15.16pp | 0.970 | 1.322 |

No enabled candidate delivers a full-sample Pareto improvement in both annual return and max drawdown. Lower targets buy drawdown reduction with a large return sacrifice and lower Sharpe; higher targets increase return by applying leverage and materially worsen drawdown. The disabled baseline has the highest full-sample Sharpe in the grid.

## Window Results

Current 25% target versus the same pure momentum base:

| window | off annual return | current annual return | return delta | off max drawdown | current max drawdown | drawdown delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | 23.05% | 23.15% | +0.11pp | -36.47% | -43.22% | -6.75pp |
| 10Y | 34.17% | 35.22% | +1.05pp | -21.48% | -24.95% | -3.47pp |
| 5Y | 48.40% | 52.60% | +4.20pp | -21.48% | -24.46% | -2.98pp |
| 3Y | 61.05% | 63.61% | +2.56pp | -17.18% | -18.16% | -0.97pp |
| 1Y | 33.36% | 36.68% | +3.32pp | -17.18% | -16.79% | +0.40pp |

The current 25% level improves annual return in all five windows, but worsens drawdown in Full/10Y/5Y/3Y and improves 1Y drawdown by only 0.40pp. Full-sample Sharpe falls from 0.972 to 0.928.

## Stability Classification

- Label: `no_pareto_improvement`.
- Evidence: no target-volatility level matches or beats both disabled annual return and disabled max drawdown in the full sample; disabled also has the highest full-sample Sharpe.
- Nearby-candidate behavior: 20%-30% forms a smooth risk/leverage ladder rather than a favorable plateau. Moving from 20% to 30% raises annual return from 19.19% to 26.79% while max drawdown deteriorates from -37.08% to -47.47%.
- Recent-window behavior: current 25% has stronger recent annual returns, but the benefit is not accompanied by consistent drawdown improvement; four of five drawdown windows are worse.
- Cost sensitivity: all candidates include the same 0.10% one-way trading cost. Current 25% total modeled cost is 0.751 versus 0.691 for off, so the comparison includes extra scale/switch turnover.
- Data sensitivity: frozen data through 2026-09-02; no proxy extension or refreshed prices.
- Leverage or exposure caveat: current 25% uses exposure above 1.0 on 58.2% of full-sample rows, hits the 1.5 scale cap on 15.5%, and performs 149 scale changes. Financing cost is excluded; therefore its already-small +0.11pp full-sample return edge is optimistic relative to a financed implementation.

## Decision

- Decision: `confirmed_off`; the user confirmed on 2026-09-03 that target volatility is disabled in the V1.1 naive-mainline decision set.
- Recommended next action: keep the target-volatility layer disabled. Its 80-day window, 1.5 leverage cap, and 7.5pp scale deadband are retired companion parameters and will not be scanned. This records a research/mainline decision and does not by itself edit the production runner or Poe bot.

## Finalization

- Finalized at: 2026-09-03T22:45:23+08:00
- Decision: confirmed_off (user-confirmed after the scan; supersedes the provisional recommendation)
- Stability label: no_pareto_improvement
- Complete checker: PASS
