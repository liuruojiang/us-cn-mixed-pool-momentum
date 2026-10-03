# 六 ETF V1.3：R²门槛 0～2 扫描

## Run Metadata

- Run id: `20261003_r2_threshold_0_2_step0p05_20260924`
- Research-only single-parameter scan.
- Git state: `scan_meta.json`.

## Research Question

- Grid: R² threshold 0, 0.05, ..., 2.00. Formal 0.25 is included in the same run.
- Only R² eligibility lower bound changes; LOOKBACK=25, weight p=1, strict Score bounds, Top1 and account rules fixed.
- Score and R² come from the same weighted regression. Mathematically R²≤1, so >1 is an intentionally included cash-only boundary region.
- Source-change rule: `research_only_no_source_change`; no formal strategy or provider file edited.

## Implementation Anchor

- Official `poe_subd_six_etf_v1_3_bot.py` scoring/account engine receives each R² threshold as a runtime argument; no global parameter or source edit.
- The zero-threshold path bridges to the prior R²-off audit because valid weighted R² values are clamped at zero.

## Data Snapshot

- L1 front-adjusted saved panel and forward-fill flags, 2011-12-09 to 2026-09-24, 3,594 China ETF sessions; hashes in `scan_meta.json`.
- Six-ETF common 25-day scoreable start: 2020-01-09; earlier Full/10Y dynamically add listed assets.
- Two flagged filled asset-days cannot be traded. No provider refresh or cache write.

## Cost and Execution Assumptions

- Single ETF or cash; no leverage/financing; cash yield 0; each buy/sell leg has assumed 0.10% fee/slippage.
- T close signal hypothetically fills at T close, after old holding receives that day's close-to-close return. ETF premium, capacity and actual fill are unverified.
- Trailing windows use first NAV as base and N−1 NAV changes for annualization.
- Cash-only paths have zero volatility and undefined Sharpe. Strict artifact format stores 0 only as a placeholder with `sharpe_defined=False`; this is not a measured Sharpe of zero.

## Runtime Override Plan

- Formal 0.25 path must match L2; 0 path must match L4 R²-off. Independent audits recompute all 41×6 NAV windows and all 41×3,594 Top1 candidate-days.

## Commands

```powershell
python -X utf8 quant_param_scan_runs/20261003_r2_threshold_0_2_step0p05_20260924/run_scan.py
python -X utf8 quant_param_scan_runs/20261003_r2_threshold_0_2_step0p05_20260924/audit_results.py
python -X utf8 quant_param_scan_runs/20261003_r2_threshold_0_2_step0p05_20260924/audit_signals.py
python -X utf8 quant_param_scan_runs/20261003_r2_threshold_0_2_step0p05_20260924/build_report.py
```

## Output Files

- `scan_summary.csv`, `window_metrics.csv`, `daily_outputs/`, `parity_checks.json`, `signal_audit.json`, `result_tables.md`, `r2_threshold_scan.png`, `scan_meta.json`, `command_log.txt`.

## Full-Sample Results

- Formal 0.25: 30.44% / -22.01%; zero threshold: 26.72% / -27.40%.
- Full return peak: threshold 0.25, 30.44% / -22.01%; common-period peak: 0.25, 55.32% / -16.31%.
- First all-cash threshold in this grid: 1.00; observed maximum weighted R²: 0.97370398.

## Window Results

- All 41 paths across five required windows and common period: `result_tables.md`.
- Highest trailing 1Y return: threshold 0.25, 63.26% / -13.54%.

## Stability Classification

- `local_peak_narrow_in_sample`: 0.25 leads Full, 10Y, 5Y, 1Y and the six-ETF common period on return. The 3Y return peak is 0.20 (66.69% versus formal 65.90%).
- Immediate neighbors: 0.20 has Full 29.24% / -22.51%, 0.25 has 30.44% / -22.01%, and 0.30 has 26.80% / -21.15%. Thus 0.25 beats both neighbors on return; 0.30 has 0.85 percentage point less severe Full drawdown, so return and risk do not share the same optimum.
- Changing only the threshold changes 50 position-days at 0.20 and 47 at 0.30 versus formal across 3,594 sessions. The local peak is meaningful in this sample but not a broad flat plateau. Windows overlap, all parameter values are in-sample, and there is no independent holdout.
- At 0.95 only 20 dates have an eligible ETF and eight trade days occur; 1.00–2.00 have no eligible ETF or trades. Those 21 grid points are cash-only boundaries, not comparable active strategies.

## Decision

- `keep_formal_r2_0p25`: retain the formal 0.25 setting. This is the top-return setting in Full, 10Y, 5Y, 1Y, and common-window comparisons; the nearby 0.30 setting improves Full drawdown modestly but sacrifices 3.64 percentage points of Full annualized return.
- Formal 0.25 daily path matches L2 (zero position mismatches; NAV maximum absolute difference 7.11e-15). Threshold zero matches the earlier L4 R²-off path. Independent audit reproduced all 246 NAV windows and 147,354 candidate-days with zero Top1 mismatches.
- No formal code, production parameter, source data, or provider cache changed. Same-T-close paper fills and lack of independent holdout limit any claim of executable or out-of-sample superiority.

## User-Facing Summary

- With all other formal settings fixed, the original 0.25 threshold leads the 0–2 step-0.05 grid on Full annualized net return (30.44%, max drawdown -22.01%) and also leads the common period (55.32%, -16.31%). Its immediate return neighbors are weaker, though 0.30 has a slightly smaller drawdown.
- R² cannot exceed 1; the observed maximum is 0.97370398. Thresholds 1.00–2.00 produce cash-only paths with 0 return / 0 drawdown under the assumed 0 cash yield; their Sharpe is undefined.
- Complete 41-point × five-window table and the six-ETF common-period comparison are in `result_tables.md`. Formal 0.25 remains unchanged; this run is research only.

## Finalization

- Finalized at: 2026-10-03T20:05:05+08:00
- Decision: keep_formal_r2_0p25
- Stability label: local_peak_narrow_in_sample
- Complete checker: PASS
