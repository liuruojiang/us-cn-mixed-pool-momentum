# 六 ETF 正式 V1.3：LOOKBACK 5–100 日扫描

## Run Metadata

- Run id: `20261003_formal_lookback_5_100_step5_20260924`
- Scan type: `single_parameter`
- Decision scope: research only
- Git state: see `scan_meta.json`

## Research Question

- Grid: 5, 10, ..., 100; formal baseline 25 included.
- Only LOOKBACK changes; it sets both Score and R² regression length. Weight p=1, all formal gates and account rules fixed.
- Source-change rule: `research_only_no_source_change`.
- Required windows: Full, trailing 10Y/5Y/3Y/1Y and common 100-day scoreable period.

## Implementation Anchor

- Official `poe_subd_six_etf_v1_3_bot.py` weighted slope and `run_staged_entry`; reused verified L6 runner/metrics and prior formal scan harness.
- Runtime override changes `LOOKBACK` in memory and restores it after each candidate; no formal source edit.

## Data Snapshot

- L1 front-adjusted saved panel and forward-fill flags, 2011-12-09 to 2026-09-24, 3,594 China ETF sessions; hashes in `scan_meta.json`.
- All six ETFs can form a 100-day Score from 2020-05-07. Before then, Full/10Y dynamically add listed assets.
- Two flagged filled asset-days cannot be traded. No data refresh or cache write in this run.

## Cost and Execution Assumptions

- Single ETF or cash, no leverage or financing, cash yield 0; each buy/sell leg costs 0.10% combined assumed fee/slippage.
- Old holding receives T close-to-close return; T close signal hypothetically fills at same close. Executable price, ETF premium, capacity and impact are not certified.
- Each trailing window uses first NAV as base and N−1 NAV changes for annualization.

## Runtime Override Plan

- Formal 25-day path must match L2 daily ledger and saved L6 path; see `parity_checks.json`.
- Independent NAV recalculation audits all 20 × 6 candidate-window pairs.

## Commands

```powershell
python -X utf8 quant_param_scan_runs/20261003_formal_lookback_5_100_step5_20260924/run_scan.py
python -X utf8 quant_param_scan_runs/20261003_formal_lookback_5_100_step5_20260924/audit_results.py
python -X utf8 quant_param_scan_runs/20261003_formal_lookback_5_100_step5_20260924/build_report.py
```

## Output Files

- `scan_summary.csv`, `window_metrics.csv`, `daily_outputs/`, `parity_checks.json`, `result_tables.md`, `lookback_scan.png`, `scan_meta.json`, `command_log.txt`.

## Full-Sample Results

- Formal 25: 30.44% / -22.01%; common period 53.20% / -16.31%.
- Full return peak: 25 days, 30.44% / -22.01%; common-period peak: 25 days, 53.20% / -16.31%.

## Window Results

- Complete 20-row five-window table: `result_tables.md`.
- Highest trailing 1Y return: 25 days, 63.26% / -13.54%.

## Stability Classification

- `isolated_peak_in_grid_unvalidated`: 25 days leads annualized net return in all five required windows and the common 100-day scoreable period. Its 20/30-day Full annual returns are 12.69%/22.97% versus 30.44% at 25. The 30-day Full drawdown is slightly shallower (-21.28% versus -22.01%), while its trailing 10Y/5Y/3Y/1Y drawdowns are deeper.
- This is a coarse 5-day grid on an already researched, overlapping historical sample. The earlier 2-day grid also showed a sharp local peak near 25; there is no independent holdout or walk-forward evidence to call the peak robust.
- The 25-day baseline matches L2 on all 3,594 positions, turnover and cost rows, with maximum NAV difference 7.11e-15. All 120 candidate-window annual returns and drawdowns were independently recomputed from exported NAV; 10 overlapping paths match the prior formal scan. See `parity_checks.json`, `overlap_checks.json` and `command_log.txt`.

## Decision

- `keep_default`: retain formal LOOKBACK=25 and all other settings. The grid is research evidence, not a promotion, Poe deployment, or order authorization.
- Reassess only after a genuinely independent period or executable-price validation on the same frozen rule set; the same-close paper fill remains unverified.

## User-Facing Summary

- The formal 25-day setting is the highest-return candidate across all six reported windows in this grid, but is a narrow historical peak. Keep it unchanged.

## Finalization

- Finalized at: 2026-10-03T19:10:19+08:00
- Decision: keep_default
- Stability label: isolated_peak_in_grid_unvalidated
- Complete checker: PASS
