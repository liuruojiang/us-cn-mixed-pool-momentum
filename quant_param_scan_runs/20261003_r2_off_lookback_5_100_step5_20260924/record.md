# 六 ETF V1.3：R² 关闭、回看窗口 5–100 日扫描

## Run Metadata

- Run id: `20261003_r2_off_lookback_5_100_step5_20260924`
- Research-only conditional single-parameter scan.
- Git state: `scan_meta.json`.

## Research Question

- Disable only the R² eligibility gate, then vary LOOKBACK = 5, 10, ..., 100; keep Score limits 0.5 and 5.5, p=1, Top1 and all other account rules fixed.
- Include the formal 25-day R²-on object as a same-batch reference outside the conditional grid, plus R²-off 25-day as the within-grid baseline.
- Source-change rule: `research_only_no_source_change`; no strategy or provider code edited.

## Implementation Anchor

- `poe_subd_six_etf_v1_3_bot.py` weighted slope and `run_staged_entry`; direct call with `r2_threshold=None` and runtime LOOKBACK override, restored after each run.
- L6 helper supplies unchanged metric and account parity checks; independent signals are checked with a separate closed-form weighted slope.

## Data Snapshot

- L1 front-adjusted saved panel and forward-fill flags, 2011-12-09 to 2026-09-24, 3,594 China ETF sessions; hashes in `scan_meta.json`.
- All six ETFs can form a 100-day Score from 2020-05-07; before then Full/10Y dynamically add listed assets.
- Two flagged filled asset-days cannot be traded. No provider refresh or cache write.

## Cost and Execution Assumptions

- Single ETF or cash; no leverage or financing; cash yield 0; each buy/sell leg costs an assumed 0.10% including slippage.
- Old holding receives T close-to-close return; T close signal hypothetically fills at same close. ETF premium, capacity, actual fill and impact remain unverified.
- Each trailing window takes its first NAV as base and uses N−1 NAV changes for annualization.

## Runtime Override Plan

- Formal 25 must match L2, and R²-off 25 must match L4, before interpreting the grid.
- Audit every 21 × 6 metric pair from exported NAV and 20 × 3,594 Top1 signal days independently.

## Commands

```powershell
python -X utf8 quant_param_scan_runs/20261003_r2_off_lookback_5_100_step5_20260924/run_scan.py
python -X utf8 quant_param_scan_runs/20261003_r2_off_lookback_5_100_step5_20260924/audit_results.py
python -X utf8 quant_param_scan_runs/20261003_r2_off_lookback_5_100_step5_20260924/audit_signals.py
python -X utf8 quant_param_scan_runs/20261003_r2_off_lookback_5_100_step5_20260924/build_report.py
```

## Output Files

- `scan_summary.csv`, `window_metrics.csv`, `daily_outputs/`, `parity_checks.json`, `signal_audit.json`, `result_tables.md`, `lookback_scan.png`, `scan_meta.json`, `command_log.txt`.

## Full-Sample Results

- Formal 25 R² on: 30.44% / -22.01%; R²-off 25: 26.72% / -27.40%.
- R²-off Full return peak: 25 days, 26.72% / -27.40%; common-period peak: 25 days, 50.92% / -20.36%.

## Window Results

- All 21 paths across five required windows and the common period: `result_tables.md`.
- Highest trailing 1Y return: 20 days, 53.66% / -17.22%.

## Stability Classification

- `conditional_peak_not_robust`: within the R²-off grid, 25 days leads Full, 10Y, 5Y, 3Y and the common scoreable period on annualized return, but 20 days leads 1Y. Full R²-off 20/25/30 returns are 14.47%/26.72%/24.53%; their drawdowns are -33.35%/-27.40%/-23.45%. The 25-day Full return peak is narrow and the 30-day Full drawdown is shallower.
- The R²-off 25-day path underperforms the same-batch formal R²-on 25-day reference on annual return and drawdown in all five required windows and the common period. Full return is lower by 3.71 percentage points and drawdown deeper by 5.40 points; 1Y return is 39.41% versus formal 63.26%.
- Formal 25 and R²-off 25 exactly match earlier L2/L4 holdings, turnover and costs over 3,594 days, with NAV error at most 7.11e-15. All 126 window pairs were independently recalculated from exported NAV, and 71,880 candidate-days of Top1 selection passed an independent weighted-slope audit. With R² removed, the 25-day winner had 101 selected days whose R² was below 0.25, so the gate change was effective.
- Historical windows overlap and were previously used in research. No fresh holdout, walk-forward test or executable-price certification is present.

## Decision

- `keep_formal_r2_on_25`: retain the formal R²≥0.25 gate and 25-day lookback. None of the R²-off grid results warrants promotion on this frozen paper comparison.
- No formal source, Poe-hosted bot or trading instruction was changed.

## User-Facing Summary

- R²-off 25 is the conditional Full/common-period return peak, but both return and drawdown deteriorate versus formal R²-on 25; 20 days leads only the recent 1Y return inside the R²-off grid.

## Finalization

- Finalized at: 2026-10-03T19:24:28+08:00
- Decision: keep_formal_r2_on_25
- Stability label: conditional_peak_not_robust
- Complete checker: PASS
