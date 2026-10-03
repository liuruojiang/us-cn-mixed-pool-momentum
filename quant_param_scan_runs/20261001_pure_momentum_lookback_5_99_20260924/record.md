# 六 ETF 纯动量回看窗口扫描记录

## Run Metadata

- Run id: `20261001_pure_momentum_lookback_5_99_20260924`; scan type `single_parameter`; strategy six ETF V1.3 research-only branch.
- Git branch, commit and original dirty worktree state: `scan_meta.json`.
- Formal V1.3 source and Poe configuration were not changed.

## Research Question

- Sweep LOOKBACK = 5, 7, ..., 99 days (48 values); step 2 from 5 does not hit 100.
- Pure reference: 25 days, Score > 0, no upper cap, no R² gate, Buffer=1, Top1 full entry or cash.
- This is a new uncapped raw-momentum definition. The older capped research base `0<Score<5` and formal V1.3 `0.5<Score<5.5, R²>=0.25` remain separately labeled.
- Required windows: Full, trailing 10Y/5Y/3Y/1Y, plus six-ETF common scoreable period. Source-change rule: `research_only_no_source_change`.

## Implementation Anchor

- `poe_subd_six_etf_v1_3_bot.py` provides the actual weighted log-price slope, `run_staged_entry` single account and `_build_config`; only runtime globals and eligibility arguments change.
- Formal Score uses 252-day annualization and linear recency weights 1..N. `run_scan.py` restores LOOKBACK/SCORE_MIN/SCORE_MAX after every candidate.
- Unchanged formal 25-day path matches L2's 3,594 daily positions, turnover and costs exactly, with NAV max error 7.11e−15; pure 25 differs from formal on 1068 holding days. See `parity_checks.json`.

## Data Snapshot

- Frozen L1 qfq adjusted ETF closes and forward-fill flags, 2011-12-09 to 2026-09-24, 3,594 China ETF sessions; hashes in `scan_meta.json`.
- Full/10Y windows dynamically admit ETF members after listing. Six ETF common scoreable period: 2020-01-09 to 2026-09-24. Two previously flagged forward-filled asset-days stay flagged and cannot be traded.
- Read-only local snapshot; no provider query or cache mutation in this run. Results do not represent the latest 2026-10-01 market close.

## Cost and Execution Assumptions

- One ETF or cash; max exposure 1; cash yield 0; no borrow/financing/hedge. A buy and a sell each incur the assumed 0.10% combined one-way fee/slippage.
- Old holding earns T close-to-close move; T-close signal hypothetically fills at the same close. This is a paper model, without verified actual fills, ETF premium, capacity or impact.
- All variants share the L1 China ETF session index, Asia/Shanghai, identical 252-day windows, and N−1 NAV changes for annualization.

## Runtime Override Plan

- Set `LOOKBACK=N`, `SCORE_MIN=0`, `SCORE_MAX=+inf`, `r2_threshold=None`, `switch_buffer=1`, `full_entry=1` only during each candidate call; formal source unchanged.
- `audit_results.py` recomputes all 288 candidate-window annual returns and drawdowns from saved NAV to tolerance 1e−10.
- `audit_signals.py` separately computes weighted slopes and checks all 172,512 Top1 candidate-days. For pure 25, 464 selected days had R² below formal 0.25 and 345 selected days exceeded the formal Score cap, confirming that both filters were effectively off.

## Commands

```powershell
python -X utf8 quant_param_scan_runs/20261001_pure_momentum_lookback_5_99_20260924/run_scan.py
python -X utf8 quant_param_scan_runs/20261001_pure_momentum_lookback_5_99_20260924/audit_results.py
python -X utf8 quant_param_scan_runs/20261001_pure_momentum_lookback_5_99_20260924/audit_signals.py
python -X utf8 quant_param_scan_runs/20261001_pure_momentum_lookback_5_99_20260924/build_report.py
```

## Output Files

- `scan_summary.csv`: 48 candidates × six windows with trades, costs and deltas against pure 25 days.
- `window_metrics.csv`: 48 rows with mandatory five-window and common scoreable metrics.
- `daily_outputs/`: 48 daily account paths; `candidate_event_counts.csv`: position differences against pure 25 days.
- `result_tables.md`: complete readable results; `lookback_scan.png`: return and drawdown plot.
- `parity_checks.json`, `signal_audit.json`, `scan_meta.json`, `command_log.txt`: parity, independent signal checks and provenance.

## Full-Sample Results

- Pure 25 days: 21.34% / -38.55%; common scoreable period 30.41% / -30.05%.
- Highest Full annualized return: 29 days, 26.87% / -29.95%; highest common-period return: 29 days, 30.91% / -26.27%.

## Window Results

| 回看日数 | 全样本 | 近10年 | 近5年 | 近3年 | 近1年 |
|---:|---:|---:|---:|---:|---:|
| 5 | -5.98% / -71.98% | -7.84% / -63.37% | -9.28% / -50.42% | -8.04% / -47.88% | -21.49% / -37.31% |
| 15 | 16.13% / -38.18% | 12.93% / -38.18% | 25.15% / -33.87% | 25.60% / -33.87% | 36.19% / -16.77% |
| 21 | 17.54% / -46.83% | 18.88% / -37.32% | 33.16% / -25.50% | 34.41% / -25.50% | 9.48% / -17.23% |
| 23 | 20.25% / -33.94% | 21.20% / -30.17% | 25.23% / -30.17% | 23.64% / -30.17% | 6.00% / -18.53% |
| 25 | 21.34% / -38.55% | 23.38% / -30.05% | 30.75% / -30.05% | 33.35% / -30.05% | 0.53% / -19.96% |
| 27 | 23.23% / -34.40% | 23.73% / -26.43% | 27.39% / -26.43% | 25.33% / -26.43% | -13.06% / -26.43% |
| 29 | 26.87% / -29.95% | 26.12% / -26.27% | 28.59% / -26.27% | 25.30% / -26.27% | -13.94% / -26.27% |
| 99 | 5.72% / -55.90% | 2.68% / -42.31% | 5.89% / -30.26% | 6.68% / -30.26% | -1.70% / -26.25% |

- Highest last-1Y return: 15 days, 36.19% / -16.77%. All 48 rows are in `result_tables.md`.

## Stability Classification

- Label: `retrospective_grid_only`. Full, common and recent windows can disagree; five trailing windows overlap and this history has been repeatedly used for strategy research.
- The scan cannot certify an independent out-of-sample optimum or executable returns. Fee/slippage is a fixed paper assumption; no separate impact sensitivity was run.

## Decision

- `research_only_no_promotion`: show the pure-momentum shape while retaining the formal V1.3 parameters and any Poe deployment unchanged.
- Any later candidate promotion needs a separate decision and a fresh executable-price/data validation. Rerun this grid if the source, input data, costs or execution model changes.

## Finalization

- Finalized at: 2026-10-01T20:53:27+08:00
- Decision: research_only_no_promotion
- Stability label: retrospective_grid_only
- Complete checker: PASS
