# Sub-D V1.1 Per-Asset Score Gate Exemption Scan

## Decision

- Decision: research only; no source change made by this scan.
- Question: test whether exempting one or more of the six assets from the `score < 5` upper gate improves history.
- Lower gate preserved: all assets still require `score > 0` and `R2 >= 0.20`; exempt assets only skip the `score < 5` upper gate.

## Data

- Common last date: 2026-05-15
- Source: `akshare.fund_etf_hist_sina` raw close through the existing loader pattern from `analyze_score_cap_alternatives_20260511.py`.
- Adjustment: raw/unadjusted as served by Sina.

## Cost And Execution

- One-way cost: 0.1000%
- R2 threshold: 0.20
- Switch buffer: 1.05
- Entry: 50% initial entry, fill remainder on first down close.
- Target volatility: 25%, vol window 80, max leverage 1.5.
- Overheat: MA60 bias enter 20%, exit 18%, derisk scale 0.

## Top From-2020 Rows

| candidate                            |   ann_return |    max_dd |   sharpe_repo |   trades |   cost_sum | exempt_assets                 |
|:-------------------------------------|-------------:|----------:|--------------:|---------:|-----------:|:------------------------------|
| exempt_159915_SZ+513030_SH           |     0.607544 | -0.180541 |       2.01786 |     1245 |   0.347284 | 159915.SZ,513030.SH           |
| exempt_159915_SZ                     |     0.608727 | -0.180541 |       2.01346 |     1237 |   0.367596 | 159915.SZ                     |
| exempt_159915_SZ+513030_SH+159985_SZ |     0.583273 | -0.165506 |       1.95384 |     1252 |   0.338539 | 159915.SZ,513030.SH,159985.SZ |
| exempt_159915_SZ+159985_SZ           |     0.584438 | -0.165506 |       1.94972 |     1244 |   0.358851 | 159915.SZ,159985.SZ           |
| exempt_513030_SH                     |     0.5996   | -0.180541 |       1.93391 |     1282 |   0.388296 | 513030.SH                     |
| baseline_no_exempt                   |     0.59322  | -0.180541 |       1.90956 |     1274 |   0.409527 |                               |
| exempt_159915_SZ+513030_SH+518880_SH |     0.562598 | -0.180541 |       1.90307 |     1243 |   0.33412  | 159915.SZ,513030.SH,518880.SH |
| exempt_159915_SZ+159941_SZ+513030_SH |     0.556173 | -0.185391 |       1.89994 |     1242 |   0.332441 | 159915.SZ,159941.SZ,513030.SH |
| exempt_513030_SH+159985_SZ           |     0.58646  | -0.165506 |       1.89916 |     1289 |   0.368045 | 513030.SH,159985.SZ           |
| exempt_159915_SZ+159941_SZ           |     0.556965 | -0.185391 |       1.89557 |     1234 |   0.352658 | 159915.SZ,159941.SZ           |

## Output Files

- `scan_summary.csv`
- `window_metrics.csv`
- `daily_curves.csv`
- `selection.csv`
- `sources.csv`

## Stability

- Label: computed_pending_interpretation.
- Evidence: see `window_metrics.csv` for full, last_10y, last_5y, last_3y, and last_1y comparisons.
