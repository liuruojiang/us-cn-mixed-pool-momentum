# Sub-D Power-WMA Cost-Only Signal Screen

Date: 2026-05-17

## Scope

This note records the direct Power-WMA replacement test for the real Sub-D V1.1 six-ETF workflow.

Implementation anchor:

- `research_subd_six_etf_weighted_slope.py`
- `run_subd_six_etf_v1_1.py`
- Research runner: `analyze_subd_power_wma_cost_only.py`

Run folder:

`quant_param_scan_runs/20260517_subd_six_etf_v1_1_cost_only_signal_power_wma_lookback_power`

## Test Definition

Cost-only rule:

- Six-ETF Sub-D pool: `159915.SZ`, `159941.SZ`, `513030.SH`, `513520.SH`, `159985.SZ`, `518880.SH`.
- Original signal: weighted log-slope score with `LOOKBACK=25`; R2 and score bounds removed except positive sign.
- Power signal: Power-WMA on each ETF daily return.
- Positioning: top positive score holds 100%; all non-positive scores hold cash.
- Timing: close-confirmed signal, next close-to-close return.
- Cost: one-way transaction cost `0.001`; cash daily return `0.0`.
- Removed: R2 gate, score min/max gates except positive sign, stop/cooldown, switch buffer, staged entry, target-vol, and overheat overlay.

Data:

- Source: `akshare.fund_etf_hist_sina`.
- Adjustment: raw/unadjusted as served by Sina.
- Common joined range: 2020-01-10 to 2026-05-15.

Grid:

- `lookback = [5, 10, 15, 20, 25, 30, 40, 60]`
- `power = [0, 0.25, 0.5, 0.75, 1, 1.25, 1.5, 2]`

## Result

| Candidate | Full Ann / DD | 10Y Ann / DD | 5Y Ann / DD | 3Y Ann / DD | 1Y Ann / DD |
|---|---:|---:|---:|---:|---:|
| Original weighted log-slope | 29.74% / -30.05% | 30.19% / -30.05% | 31.38% / -30.05% | 43.87% / -30.05% | 39.17% / -19.96% |
| Best 5Y Power p0.5/lb25 | 27.25% / -34.54% | 26.04% / -34.54% | 31.45% / -34.54% | 44.29% / -34.54% | 81.09% / -18.42% |
| Power p0.75/lb25 | 26.32% / -28.98% | 25.24% / -28.98% | 31.28% / -28.98% | 37.91% / -28.98% | 42.83% / -22.56% |
| Power p0/lb25 | 21.96% / -37.91% | 21.90% / -37.91% | 27.98% / -25.50% | 37.44% / -25.50% | 67.92% / -20.38% |

Counts:

- Power candidates scanned: 64.
- Candidates beating original on 5Y/3Y/1Y return only: 1.
- Candidates beating original on 5Y/3Y/1Y by both return and max drawdown: 0.
- Candidates beating original on all reported windows by both return and max drawdown: 0.

## Decision

Do not promote Power-WMA as a direct Sub-D replacement.

The best candidate, `p0.5/lb25`, is a watchlist item because it improves 5Y/3Y/1Y annual return, especially 1Y, but it has lower full-sample annual return and wider 5Y/3Y drawdown than the original weighted log-slope signal. The next useful test, if revisited, should be a short-window Power overlay or blend inside the full V1.1 stack, not a raw signal replacement.

## Cleanup Note

Key results from the formal scan folder were copied into this note. The one-off script, single-point output folder, and Power-WMA scan folder created for this exploration were removed after this record was written.
