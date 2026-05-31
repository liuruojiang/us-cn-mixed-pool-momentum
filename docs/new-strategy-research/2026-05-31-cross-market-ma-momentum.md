# 2026-05-31 Cross-Market MA + Momentum Allocation

## Scope

This note records the current cross-market research candidate from the local workspace `D:\\动量策略\\新策略研究`.

The result combines:

- US ETF multi-asset strategy family.
- A-share three-asset total-return proxy family.

The goal is not to select the two highest-return legs mechanically. The preferred structure keeps at least one moving-average leg and one momentum leg inside each market sleeve.

## Data And Cost Scope

- US source artifact: `quant_param_scan_runs/20260531_etf_multi_asset_four_strategy_25pct_cost_5bp/curves.csv`.
- A-share source artifact: `quant_param_scan_runs/20260531_a_three_asset_total_return_frequency_scan_5bp/`.
- Component-level cost: one-way `5bp` inside both market sleeves.
- Cross-market calendar: union of US and A-share trading calendars; non-local trading days are forward-filled.
- Annualization: calendar-year annualization on the combined calendar.
- Not yet included: portfolio-level rebalance cost, taxes, FX conversion, cross-border funding friction, or tradable A-share ETF replacement mapping.

## Selected Two-Leg Structure

| Market | MA leg | Momentum leg |
|---|---|---|
| US ETF | `ma_best_vt08_bnd06_gld07` | `weekly_best_vt24_bnd52_gld09` |
| A-share proxy | `weekly_ma_asset_s12_b08_g05` | `monthly_abs_asset_s06_b03_g09` |

## Key Metrics

| Combination | Full ann / max DD | 10Y ann / max DD | 5Y ann / max DD | 3Y ann / max DD |
|---|---:|---:|---:|---:|
| MA+Momentum: US70/A30 | 8.20% / -10.75% | 8.36% / -8.14% | 8.42% / -8.14% | 14.48% / -8.14% |
| MA+Momentum: US50/A50 | 8.30% / -15.69% | 7.68% / -7.91% | 7.92% / -7.91% | 13.21% / -7.91% |
| Four-leg: US70/A30 | 8.22% / -10.90% | 8.33% / -8.38% | 8.42% / -8.38% | 14.65% / -8.38% |
| Four-leg: US50/A50 | 8.31% / -15.82% | 7.67% / -8.22% | 7.91% / -8.22% | 13.40% / -8.22% |

## Decision

Current preferred research candidate: `MA+Momentum: US70/A30`.

Reasoning:

- It preserves rule diversity inside each market sleeve.
- It avoids the failure mode where pure Calmar selection chooses two same-family legs.
- It keeps recent 10Y and 5Y drawdowns near `-8.14%` while maintaining similar return to the four-leg `US70/A30` structure.

## Not Production Approval

This is a research-area record only. Before promoting this to production, rerun with current data and add:

- explicit portfolio-level rebalance cost;
- FX and currency-accounting policy;
- tradable A-share ETF implementation path;
- execution timing and holiday/calendar handling;
- sensitivity around US/A-share allocation weights.
