# Sub-D Dynamic ChiNext Proxy 2007-2016 Two-Line Carry

Updated: 2026-07-01

## Decision

后续层按两条线并行推进：

- `A_clean`: 不带 target-vol、不带动量衰减、不带净值防守。
- `G_decay_nav`: 带动量衰减，也带净值防守。

独立净值防守扫描证明 NAV defense 单项有效，但不作为单独 carry 线。此前“净值防守叠在动量衰减后”的扫描保留为 `G_decay_nav` 依据；此前“净值防守 standalone”的扫描只作为单项证据。

## Carry Lines

| Line | Candidate | Lookback | R2 | Switch Buffer | Entry | Momentum Decay | NAV Defense |
|---|---|---:|---:|---:|---:|---|---|
| `A_clean` | `lb_28_r2_0p50_buf_1p00_entry_0p75_decay_off_nav_off` | 28 | 0.50 | 1.00 | 0.75 | off | off |
| `G_decay_nav` | `lb_28_r2_0p50_buf_1p00_entry_0p75_decay_0p55_rec_0p85_c3_scale_0p75_nav_enter_0p125_exit_0p03_scale_0p75` | 28 | 0.50 | 1.00 | 0.75 | trigger 0.55 / recover 0.85 / confirm 3 / scale 0.75 | enter DD 12.5% / exit DD 3% / scale 0.75 |

## Current Metrics

| Line | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `A_clean` | 9.14% | -23.10% | N/A | N/A | 9.57% | -19.53% | 7.43% | -19.53% | 1.84% | -19.53% |
| `G_decay_nav` | 8.19% | -20.05% | N/A | N/A | 8.67% | -16.94% | 6.54% | -16.94% | 3.33% | -16.94% |

10Y is N/A because the 2007-01-04 to 2016-12-30 sample has 2432 A-share sessions, less than 2520 trading days.

## Reference Only

| Reference | Full Ann. | Full MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Role |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Standalone NAV defense selected | 8.33% | -20.50% | 8.98% | -18.09% | 6.47% | -18.09% | 1.91% | -18.09% | 单项证据，不 carry |
| Original same-stage line | 8.03% | -28.16% | 8.27% | -28.16% | 3.26% | -28.16% | -17.99% | -27.04% | original parameter reference |
| Original full V1.1 reference | 11.84% | -36.96% | 12.61% | -36.96% | 3.41% | -36.96% | -26.98% | -36.96% | context only |

## Future Layer Rule

For every later layer:

- Test both `A_clean` and `G_decay_nav`.
- Compare each candidate only against its own same-line baseline.
- Do not promote a candidate from one line by comparing it to the other line.
- Display Full, 10Y, 5Y, 3Y, and 1Y annualized return plus max drawdown for both lines.
- Keep the proxy diagnostic label: A-share calendar, US adjusted closes forward-filled to the A-share calendar, and ChiNext joining only from its own 2010-06-01 data.

## Source Runs

- `A_clean`: `quant_param_scan_runs/20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_nav_defense_standalone_layer7_nav_drawdown_gate_no_decay/comparison_list.csv`
- `G_decay_nav`: `quant_param_scan_runs/20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_nav_defense_layer7_nav_drawdown_gate/comparison_list.csv`
- Standalone NAV defense evidence: `quant_param_scan_runs/20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_nav_defense_standalone_layer7_nav_drawdown_gate_no_decay/record.md`
