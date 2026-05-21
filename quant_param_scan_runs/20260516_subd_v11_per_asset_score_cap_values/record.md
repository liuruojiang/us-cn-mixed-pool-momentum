# Sub-D V1.1 Per-Asset Score Cap Value Scan

## Decision

- Decision: research only; no source change made by this scan.
- Best single-asset result is evaluated by keeping five assets at cap 5 and changing one asset cap.
- Focus 2D scan is limited to `159915.SZ` and `513030.SH`, which were the useful exemptions in the previous scan.

## Data

- Common last date: 2026-05-15
- Source: `akshare.fund_etf_hist_sina` raw close.
- Adjustment: raw/unadjusted as served by Sina.
- Baseline parity NAV absolute difference versus official `run_staged_entry` path: 0.0

## Cost And Execution

- One-way cost: 0.1000%
- R2 threshold: 0.20
- Switch buffer: 1.05
- Target volatility: 25%, vol window 80, max leverage 1.5.
- Overheat: MA60 bias enter 20%, exit 18%, derisk scale 0.

## Top From-2020 Candidates

| candidate                          | scan_family            |   ann_return |    max_dd |   sharpe_repo |   trades |   cost_sum |
|:-----------------------------------|:-----------------------|-------------:|----------:|--------------:|---------:|-----------:|
| focus_159915_SZ_inf__513030_SH_15  | focus_159915_513030_2d |     0.617641 | -0.180541 |       2.04117 |     1248 |   0.35005  |
| focus_159915_SZ_inf__513030_SH_12  | focus_159915_513030_2d |     0.617156 | -0.180541 |       2.03979 |     1248 |   0.35009  |
| focus_159915_SZ_inf__513030_SH_6   | focus_159915_513030_2d |     0.616405 | -0.180541 |       2.03312 |     1241 |   0.354684 |
| focus_159915_SZ_7__513030_SH_15    | focus_159915_513030_2d |     0.639108 | -0.180541 |       2.02603 |     1284 |   0.382348 |
| focus_159915_SZ_7__513030_SH_12    | focus_159915_513030_2d |     0.63836  | -0.180541 |       2.0241  |     1284 |   0.382391 |
| focus_159915_SZ_inf__513030_SH_10  | focus_159915_513030_2d |     0.608415 | -0.180541 |       2.01924 |     1248 |   0.350582 |
| focus_159915_SZ_inf__513030_SH_inf | focus_159915_513030_2d |     0.607544 | -0.180541 |       2.01786 |     1245 |   0.347284 |
| single_159915_SZ_cap_inf           | single_159915.SZ       |     0.608727 | -0.180541 |       2.01346 |     1237 |   0.367596 |
| focus_159915_SZ_inf__513030_SH_5   | focus_159915_513030_2d |     0.608727 | -0.180541 |       2.01346 |     1237 |   0.367596 |
| focus_159915_SZ_inf__513030_SH_8   | focus_159915_513030_2d |     0.606041 | -0.180541 |       2.01336 |     1248 |   0.350625 |
| focus_159915_SZ_7__513030_SH_inf   | focus_159915_513030_2d |     0.629494 | -0.180541 |       2.00951 |     1281 |   0.379175 |
| focus_159915_SZ_7__513030_SH_6     | focus_159915_513030_2d |     0.631829 | -0.180541 |       2.00654 |     1277 |   0.387206 |
| focus_159915_SZ_inf__513030_SH_4   | focus_159915_513030_2d |     0.604078 | -0.180541 |       2.00335 |     1213 |   0.367856 |
| focus_159915_SZ_8__513030_SH_15    | focus_159915_513030_2d |     0.626959 | -0.180541 |       2.00237 |     1281 |   0.375543 |
| focus_159915_SZ_8__513030_SH_12    | focus_159915_513030_2d |     0.626217 | -0.180541 |       2.00043 |     1281 |   0.375586 |

## Stability

- Label: single_asset_clear_159915_focus_combo_mixed.
- Evidence: see `scan_summary.csv` and `window_metrics.csv`.

## Output Files

- `scan_summary.csv`
- `window_metrics.csv`
- `daily_curves.csv` for baseline and top candidates
- `sources.csv`

## Finalization

- Finalized at: 2026-05-16T10:41:11+08:00
- Decision: Research-only result: prefer 159915.SZ no upper cap; optional 513030.SH cap 12-15 with 159915.SZ no cap improves full/from-2020 Sharpe but weakens recent 3Y annual return versus baseline; keep other assets at cap 5 except 159985.SZ cap 6 is a small single-asset candidate needing combo confirmation.
- Stability label: single_asset_clear_159915_focus_combo_mixed
- Complete checker: PASS
