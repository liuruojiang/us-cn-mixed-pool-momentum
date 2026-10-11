# 六 ETF V1.3：正式条件下权重指数 p=0～5 扫描

## Run Metadata

- Run id: `20261003_formal_weight_power_0_5_step0p5_20260924`
- Research-only single-parameter scan.
- Git state: `scan_meta.json`.

## Research Question

- Grid: p=0, 0.5, ..., 5.0. Formal p=1.0 is included in the same run.
- Only time-weight exponent changes: `w_t=t^p` for t=1..25 from oldest to newest. Keep R²≥0.25 active, along with LOOKBACK=25 and strict Score bounds.
- Source-change rule: `research_only_no_source_change`; no formal strategy or provider file edited.

## Implementation Anchor

- Official `poe_subd_six_etf_v1_3_bot.py` account engine, with the existing L6 weighted-regression helper used only to supply candidate p Scores and R² values.
- The p=1 candidate invokes the original formal scoring function; p≠1 functions are swapped in memory and restored after each run.

## Data Snapshot

- L1 front-adjusted saved panel and forward-fill flags, 2011-12-09 to 2026-09-24, 3,594 China ETF sessions; hashes in `scan_meta.json`.
- All six ETFs can form a 25-day Score from 2020-01-09. Before then Full/10Y dynamically add listed assets.
- Two flagged filled asset-days cannot be traded. No provider refresh or cache write.

## Cost and Execution Assumptions

- Single ETF or cash, no leverage/financing, cash yield 0; each buy/sell leg costs an assumed 0.10% including slippage.
- Old holding receives T close-to-close return; T close signal hypothetically fills at same close. ETF premium, capacity and actual fill are unverified.
- Each trailing window uses first NAV as base and N−1 NAV changes for annualization.

## Runtime Override Plan

- p=1 must match L2 formal and p=0 must bridge to L8 before interpreting candidates.
- Independently recompute all 11×6 NAV metric pairs and 11×3,594 Score/R²/Top1 candidate-days.

## Commands

```powershell
python -X utf8 quant_param_scan_runs/20261003_formal_weight_power_0_5_step0p5_20260924/run_scan.py
python -X utf8 quant_param_scan_runs/20261003_formal_weight_power_0_5_step0p5_20260924/audit_results.py
python -X utf8 quant_param_scan_runs/20261003_formal_weight_power_0_5_step0p5_20260924/audit_signals.py
python -X utf8 quant_param_scan_runs/20261003_formal_weight_power_0_5_step0p5_20260924/build_report.py
```

## Output Files

- `scan_summary.csv`, `window_metrics.csv`, `daily_outputs/`, `parity_checks.json`, `signal_audit.json`, `result_tables.md`, `weight_power_scan.png`, `scan_meta.json`, `command_log.txt`.

## Full-Sample Results

- Formal p=1: 30.44% / -22.01%; common period 55.32% / -16.31%.
- Full return peak: p=1, 30.44% / -22.01%; common-period peak: p=1, 55.32% / -16.31%.

## Window Results

- All 11 paths across five required windows and common period: `result_tables.md`.
- Highest trailing 1Y return: p=1.5, 70.08% / -12.51%.

## Stability Classification

- `coarse_local_peak_with_recent_tradeoff`: p=1.0 leads annualized net return in Full, trailing 10Y/5Y/3Y, and the common six-ETF scoreable period; it also has the shallowest Full and 10Y drawdowns in this grid. The adjacent p=0.5/1.5 Full returns are 27.30%/23.30% versus 30.44% at p=1.0, with drawdowns -23.01%/-22.20% versus -22.01%. The coarse 0.5 step does not establish a robust plateau.
- p=1.5 leads recent 1Y at 70.08%/-12.51% versus formal p=1.0 at 63.26%/-13.54%, but its Full and 10Y returns fall by 7.14 and 9.54 percentage points; Full and 10Y drawdowns deepen slightly and materially, respectively. Higher p values also increase turnover: 573 at p=1, 661 at p=1.5, 1,327 at p=5.
- Formal p=1.0 matches L2 on all 3,594 holdings, turnover and cost rows with maximum NAV difference 7.11e-15; p=0 matches the earlier L8 path with 5.33e-15 maximum NAV difference. All 66 window metrics were independently recomputed from daily NAV and 39,534 candidate-days of Score/R²/Top1 decisions passed a separate weighted-moment audit. The active R² gate rejected 189–578 Score-passing asset-days across the 11 paths.
- Five trailing windows overlap, the history was used in earlier parameter selection, and no independent holdout, walk-forward or executable-price certification is present.

## Decision

- `keep_formal_p1`: retain the formal p=1.0 recency weighting and all other source settings. The recent p=1.5 improvement is research-only and does not justify promotion on the conflicting long-window evidence.
- No formal source, Poe-hosted bot or trading instruction was changed.

## User-Facing Summary

- With R²≥0.25 retained, p=1.0 leads most return windows and the common-history window. p=1.5 leads only the trailing 1Y return and has a lower 1Y drawdown, while materially weakening longer-window returns.

## Finalization

- Finalized at: 2026-10-03T19:35:51+08:00
- Decision: keep_formal_p1
- Stability label: coarse_local_peak_with_recent_tradeoff
- Complete checker: PASS
