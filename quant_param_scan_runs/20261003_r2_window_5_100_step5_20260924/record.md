# 六 ETF V1.3：独立 R²窗口 5～100 日扫描

## Run Metadata

- Run id: `20261003_r2_window_5_100_step5_20260924`
- Research-only single-parameter scan.
- Git state before scan: clean at commit `47e5ffca3b66502642b604a0daaf9b6b5706452d`.

## Research Question

- Grid: R² calculation window 5, 10, ..., 100 trading-price observations; formal 25 is included in the same run.
- Score always uses its formal 25-day window. Both regressions retain linear time weights p=1. R² gate stays >=0.25; strict Score bounds, Top1 and account rules fixed.
- Source-change rule: `research_only_no_source_change`; no formal strategy, provider file or parameter changed.

## Implementation Anchor

- Official `poe_subd_six_etf_v1_3_bot.py` account engine is reused. Only `calc_scores` is temporarily replaced to look up a formal 25-day Score and separate N-day weighted R²; original function is restored after each candidate.
- R² calculation copies the official weighted-log-price least-squares formula, with N as the only free input.

## Data Snapshot

- L1 front-adjusted saved panel and forward-fill flags, 2011-12-09 to 2026-09-24, 3,594 China ETF sessions; hashes in `scan_meta.json`.
- Common six-ETF 25-day Score start: 2020-01-09; common 100-day R² coverage starts 2020-05-07. Earlier Full/10Y dynamically add listed assets.
- Two flagged filled asset-days cannot be traded. No provider refresh or cache write.

## Cost and Execution Assumptions

- Single ETF or cash; no leverage/financing; cash yield 0; each buy/sell leg has assumed 0.10% fee/slippage.
- T close signal hypothetically fills at T close, after old holding receives that day's close-to-close return. ETF premium, capacity and actual fill are unverified.
- Trailing windows use first NAV as base and N−1 NAV changes for annualization.

## Runtime Override Plan

- Unpatched formal path must match saved L2; separated R²-window 25 path must match unpatched formal. The original `calc_scores` is restored after each run.
- Independent audits recompute all 20×6 NAV windows and all 20×3,594 Top1 candidate-days from weighted moments.

## Commands

```powershell
python -X utf8 quant_param_scan_runs/20261003_r2_window_5_100_step5_20260924/run_scan.py
python -X utf8 quant_param_scan_runs/20261003_r2_window_5_100_step5_20260924/audit_results.py
python -X utf8 quant_param_scan_runs/20261003_r2_window_5_100_step5_20260924/audit_signals.py
python -X utf8 quant_param_scan_runs/20261003_r2_window_5_100_step5_20260924/build_report.py
```

## Output Files

- `scan_summary.csv`, `window_metrics.csv`, `daily_outputs/`, `parity_checks.json`, `signal_audit.json`, `result_tables.md`, `r2_window_scan.png`, `scan_meta.json`, `command_log.txt`.

## Full-Sample Results

- Formal 25 days: 30.44% / -22.01%.
- Full return peak: 25 days, 30.44% / -22.01%.
- Common 100-day coverage return peak: 25 days, 53.20% / -16.31%.

## Window Results

- All 20 paths across five required windows and common 100-day-coverage period: `result_tables.md`.
- Return winners by Full/10Y/5Y/3Y/1Y: full=25, last_10y=25, last_5y=25, last_3y=100, last_1y=75.

## Stability Classification

- `isolated_full_peak_recent_window_divergence`: the formal 25-day R² window leads annualized return in Full, 10Y, 5Y and the common 100-day-coverage period, but neither immediate neighbor supports a broad plateau. Full 20/25/30-day results are 21.46% / -23.46%, 30.44% / -22.01%, and 26.32% / -20.33%.
- Full return and drawdown have different optima: 30 and 35 days have smaller Full drawdowns than 25 but lower returns; 100 days gives 27.81% / -19.07%, also lower return and smaller drawdown.
- The trailing 3Y return leader is 100 days at 69.69% / -12.05% versus formal 65.90% / -14.34%; trailing 1Y leader is 75 days at 68.96% / -10.59% versus formal 63.26% / -13.54%. These windows overlap and are in-sample, not independent holdouts.
- Moving to 20/30 days changes 206/150 position-days versus formal across 3,594 sessions. Longer R² windows change initial eligibility when asset history is short; the 2020-05-07 common period removes the six-ETF 100-day initial-coverage mismatch.

## Decision

- `keep_formal_r2_window_25`: retain the existing common Score/R² 25-day setting. It leads the matched Full/10Y/5Y and all-six 100-day-coverage return comparisons, while recent 3Y/1Y and drawdown advantages of longer windows remain research candidates.
- The unpatched formal 25-day path matches L2 (zero position mismatches, maximum NAV difference 7.11e-15); separated Score25/R²25 matches the unpatched formal path exactly. Independent audits recomputed 120 NAV windows and 71,880 candidate-days, with zero Top1 mismatches and maximum R² difference 3.11e-13.
- No formal code, production parameter, source data, or provider cache changed. Same-T-close paper fills and lack of independent holdout limit any executable or out-of-sample claim.

## User-Facing Summary

- Score remains 25 days throughout; only R²'s separate regression window varies from 5 to 100 in steps of 5. The formal 25-day window is the highest Full-return point at 30.44% / -22.01% and common-coverage-return point at 53.20% / -16.31%.
- Longer R² windows can reduce Full drawdown and lead shorter recent windows, so 25 days is a narrow in-sample peak rather than a universally best setting. Full 20-point and common-period tables are in `result_tables.md`; formal 25 days remains unchanged.

## Finalization

- Finalized at: 2026-10-03T22:02:48+08:00
- Decision: keep_formal_r2_window_25
- Stability label: isolated_full_peak_recent_window_divergence
- Complete checker: PASS
