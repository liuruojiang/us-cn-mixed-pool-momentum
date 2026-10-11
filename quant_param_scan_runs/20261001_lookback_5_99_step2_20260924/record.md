# 六 ETF V1.3：LOOKBACK 5–99 日、步长 2 的纸面扫描

## Run Metadata

- Run id: `20261001_lookback_5_99_step2_20260924`
- Scan type: `single_parameter`
- Strategy: six ETF V1.3 Sub-D
- Decision scope: research only; formal parameters unchanged
- Git branch/commit and pre-run dirty status: see `scan_meta.json`

## Research Question

- Formal baseline: LOOKBACK 25 days.
- Grid: 5, 7, ..., 99 trading days (48 values); 100 is off-grid at step 2.
- Change only LOOKBACK, which jointly sets the weighted-log-slope Score and R² regression length. Keep all other formal filters and account rules fixed.
- Compare Full, last 10Y/5Y/3Y/1Y and the six-ETF common scoreable period. No production promotion from this retrospective sweep.
- Source-change rule: `research_only_no_source_change`; any strategy, data or cost rule change requires a new run.

## Implementation Anchor

- Official module: `poe_subd_six_etf_v1_3_bot.py`; `run_staged_entry` with `EntryCase(full_entry)` and `_build_config`.
- The runner imports reusable L6 `run_one`, `metrics` and exact-path parity helpers. It changes `bot.LOOKBACK` only in memory and restores it for each candidate.
- Frozen formal parameters: LOOKBACK=25, p=1, strict 0.5<Score<5.5, R²≥0.25, Buffer=1, one-way cost 0.001.

## Data Snapshot

- L1 formal loader's Tencent-labelled qfq adjusted-close panel plus forward-fill flags, 2011-12-09 to 2026-09-24, 3,594 China ETF sessions; SHA-256 paths in `scan_meta.json`.
- Six ETF common scoreable period: 2020-01-09 to 2026-09-24. Earlier Full/10Y results add assets as they become available; they are not a fixed six-ETF pool.
- Two flagged forward-filled asset-days remain flagged and cannot be traded. No data refresh or cache write occurred in this run.
- Historical frozen data are used for comparability; no claim of a latest 2026-10-01 market close or executable signal.

## Cost and Execution Assumptions

- One-way combined fee/slippage 0.10% per buy/sell leg; full single ETF or cash; cash return 0; max ETF exposure 1; no financing, borrowing or hedge.
- Old holding earns T close-to-close return; T close signal hypothetically fills at that same close. True fill price, ETF premium, capacity and market impact remain unverified. These are paper NAVs.
- Dates follow the saved China ETF session index in Asia/Shanghai. Each trailing window uses its first NAV as base and N−1 NAV changes for annualization.

## Runtime Override Plan

- Only `LOOKBACK` is overridden; all other formal code is imported unchanged.
- The formal 25-day path matches L2's 3,594 daily positions/turnover/cost exactly, with NAV error ≤7.11e−15; 23/25/27/29 also match L6 saved daily paths (see `parity_checks.json`).
- Formal source hash differs from the older L6 hash because of later report changes; daily economic parity above verifies this scan's unchanged baseline.

## Commands

```powershell
python -X utf8 quant_param_scan_runs/20261001_lookback_5_99_step2_20260924/run_scan.py
python -X utf8 quant_param_scan_runs/20261001_lookback_5_99_step2_20260924/audit_results.py
python -X utf8 quant_param_scan_runs/20261001_lookback_5_99_step2_20260924/build_report.py
```

## Output Files

- `scan_summary.csv`: 48 candidates × six windows with costs, holdings and differences against formal.
- `window_metrics.csv`: 48 candidate rows, required five windows and common scoreable period.
- `daily_outputs/`: 48 full daily account paths.
- `result_tables.md`: complete five-window and common-period display.
- `lookback_scan.png`: return and drawdown curves.
- `parity_checks.json`: baseline and overlap path parity; `audit_results.py` independently recomputed all 288 candidate-window annual returns and drawdowns from saved NAV with tolerance 1e−10.
- `scan_meta.json`, `command_log.txt`: machine-readable scope and commands.

## Full-Sample Results

- Formal 25 days: 30.44% / -22.01% (annualized net return / max drawdown); common scoreable period 55.32% / -16.31%.
- Highest Full annualized return: 25 days, 30.44% / -22.01%; highest common-period annualized return: 25 days, 55.32% / -16.31%.

## Window Results

| 回看日数 | 全样本 | 近10年 | 近5年 | 近3年 | 近1年 |
|---:|---:|---:|---:|---:|---:|
| 21 | 14.48% / -35.94% | 18.95% / -29.16% | 44.07% / -20.77% | 48.72% / -16.81% | 65.90% / -11.82% |
| 23 | 24.87% / -24.10% | 28.67% / -24.10% | 46.30% / -24.10% | 51.23% / -15.41% | 63.56% / -11.66% |
| 25 | 30.44% / -22.01% | 35.72% / -16.31% | 54.26% / -15.96% | 65.90% / -14.34% | 63.26% / -13.54% |
| 27 | 28.07% / -18.26% | 33.97% / -17.24% | 42.03% / -16.50% | 52.00% / -16.50% | 25.04% / -16.50% |
| 29 | 23.63% / -23.44% | 29.78% / -23.44% | 37.47% / -22.97% | 51.44% / -21.24% | 37.25% / -21.24% |

- Highest last-1Y annualized return is 21 days: 65.90% / -11.82%; this differs from the Full/common-period winner.
- All 48 values and five mandatory windows are in `result_tables.md`; exact metrics and costs are in the CSV files.

## Stability Classification

- Label: `local_peak_unvalidated`.
- 25 days is the peak Full and common scoreable annualized return in this specified grid; the immediate 23/27-day neighbors remain positive but have lower annualized return. The 27-day Full drawdown is shallower, and 21/23 days lead the most recent year.
- Returns deteriorate for very short and long windows. The five windows overlap, and the historical sample has been used in earlier parameter selection; this is not fresh out-of-sample evidence.
- Only the existing one-way 0.10% model cost is included. No independent fill or premium sensitivity was added.

## Decision

- `keep_default`: preserve formal LOOKBACK=25 and all source settings. The scan is a research comparison, not authorization to update a Poe-hosted bot or place orders.
- If a new candidate is considered later, require a new independent sample or executable-price validation under the same fixed rules.

## Finalization

- Finalized at: 2026-10-01T17:21:03+08:00
- Decision: keep_default
- Stability label: local_peak_unvalidated
- Complete checker: PASS
