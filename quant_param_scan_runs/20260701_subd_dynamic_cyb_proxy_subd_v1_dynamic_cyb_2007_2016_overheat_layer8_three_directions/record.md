# Sub-D Dynamic ChiNext Proxy Layer 8 Overheat Three-Direction Scan

## Run Metadata

- Run folder: `quant_param_scan_runs\20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_overheat_layer8_three_directions`
- Layer: `Layer 8`
- Strategy: dynamic ChiNext proxy pool, 2007-2016.
- Entrypoint: `run_subd_proxy_dynamic_cyb_layer8_overheat_three_directions_scan.py`

## Research Question

Test overheat controls in three directions on both carried lines.

## Three Directions

- `fixed_same_side`: MA60 bias and 20-day bias-momentum same-side overheat with fixed enter/exit thresholds.
- `adaptive_quantile`: same-side overheat with per-asset rolling 252-session bias quantile thresholds.
- `score_veto`: retest the hidden score-overheat veto by changing `SCORE_MAX` and rebuilding each line.

## Carried Lines

- `A_clean`: no target-vol, no momentum decay, no NAV defense.
- `G_decay_nav`: momentum decay plus NAV defense.

## Data Snapshot

- Start/end: `2007-01-04` to `2016-12-30`.
- Rows: `2432`.
- Pool: QQQ/EWG/EWJ/GLD from 2007 start; ChiNext joins when its own data exists.
- 10Y is N/A because 2432 sessions is less than 2520 trading days.

## Cost and Execution Assumptions

- One-way cost: `0.001`.
- Overheat scale is set at T close and effective next session.
- Overheat costs are included through full final-exposure recomputation.
- Calendar: A-share trading days; US adjusted closes are forward-filled onto that calendar for this proxy diagnostic.
- Trades involving a forward-filled trade leg are blocked by the base staged-entry path for that day.

## Selection By Direction

| Line | Direction | Selected/Best | Role | Full Ann. | Full MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Full Ann Delta pp | Full MDD Improve pp | Effect Days Full | Pass | Reason |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| A_clean | fixed_same_side | `A_clean_fixed_same_side_fixed_enter_0p15_exit_0p13_scale_0p00_same_side_or_exit` | best_diagnostic_no_pass | 9.79% | -20.66% | 11.20% | -19.53% | 7.04% | -19.53% | 1.83% | -19.53% | 0.65 | 2.44 | 19.16% | False | full_mdd=True;dd_windows=1;return_tol=True;material=True |
| A_clean | adaptive_quantile | `A_clean_adaptive_quantile_adaptive_w252_eq0p95_xq0p8_floor_0p1_0p05_scale_0p00_same_side_or_exit` | best_diagnostic_no_pass | 5.13% | -19.53% | 5.47% | -19.53% | 3.06% | -19.53% | -1.01% | -19.53% | -4.01 | 3.57 | 23.64% | False | full_mdd=True;dd_windows=1;return_tol=False;material=True |
| A_clean | score_veto | `A_clean_score_veto_scoremax_4` | best_diagnostic_no_pass | 5.24% | -22.80% | 5.56% | -22.34% | 0.48% | -22.34% | -5.75% | -22.34% | -3.90 | 0.31 | 7.07% | False | full_mdd=True;dd_windows=1;return_tol=False;material=True |
| G_decay_nav | fixed_same_side | `G_decay_nav_fixed_same_side_fixed_enter_0p15_exit_0p13_scale_0p00_same_side_or_exit` | best_diagnostic_no_pass | 9.27% | -17.51% | 10.80% | -16.94% | 6.43% | -16.94% | 3.33% | -16.94% | 1.08 | 2.54 | 4.61% | False | full_mdd=True;dd_windows=1;return_tol=True;material=True |
| G_decay_nav | adaptive_quantile | `G_decay_nav_adaptive_quantile_adaptive_w252_eq0p85_xq0p8_floor_0p1_0p05_scale_0p00_same_side_or_exit` | best_diagnostic_no_pass | 6.42% | -16.94% | 7.27% | -16.94% | 4.47% | -16.94% | 0.48% | -16.94% | -1.78 | 3.12 | 13.69% | False | full_mdd=True;dd_windows=1;return_tol=False;material=True |
| G_decay_nav | score_veto | `G_decay_nav_score_veto_scoremax_4` | best_diagnostic_no_pass | 4.04% | -19.96% | 4.15% | -19.96% | -1.14% | -19.96% | -4.51% | -19.96% | -4.15 | 0.09 | 18.17% | False | full_mdd=True;dd_windows=1;return_tol=False;material=True |

## Comparison List

| Candidate | Type | Line | Direction | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Notes |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `A_clean_scoremax_5_overheat_off` | two_line_baseline | A_clean | baseline | 9.14% | -23.10% | N/A | N/A | 9.57% | -19.53% | 7.43% | -19.53% | 1.84% | -19.53% | Carried line before Layer8 overheat tests |
| `G_decay_nav_scoremax_5_overheat_off` | two_line_baseline | G_decay_nav | baseline | 8.19% | -20.05% | N/A | N/A | 8.67% | -16.94% | 6.53% | -16.94% | 3.33% | -16.94% | Carried line before Layer8 overheat tests |
| `A_clean_fixed_same_side_fixed_enter_0p15_exit_0p13_scale_0p00_same_side_or_exit` | best_diagnostic_no_pass | A_clean | fixed_same_side | 9.79% | -20.66% | N/A | N/A | 11.20% | -19.53% | 7.04% | -19.53% | 1.83% | -19.53% | Best candidate within its line and overheat direction |
| `A_clean_adaptive_quantile_adaptive_w252_eq0p95_xq0p8_floor_0p1_0p05_scale_0p00_same_side_or_exit` | best_diagnostic_no_pass | A_clean | adaptive_quantile | 5.13% | -19.53% | N/A | N/A | 5.47% | -19.53% | 3.06% | -19.53% | -1.01% | -19.53% | Best candidate within its line and overheat direction |
| `A_clean_score_veto_scoremax_4` | best_diagnostic_no_pass | A_clean | score_veto | 5.24% | -22.80% | N/A | N/A | 5.56% | -22.34% | 0.48% | -22.34% | -5.75% | -22.34% | Best candidate within its line and overheat direction |
| `G_decay_nav_fixed_same_side_fixed_enter_0p15_exit_0p13_scale_0p00_same_side_or_exit` | best_diagnostic_no_pass | G_decay_nav | fixed_same_side | 9.27% | -17.51% | N/A | N/A | 10.80% | -16.94% | 6.43% | -16.94% | 3.33% | -16.94% | Best candidate within its line and overheat direction |
| `G_decay_nav_adaptive_quantile_adaptive_w252_eq0p85_xq0p8_floor_0p1_0p05_scale_0p00_same_side_or_exit` | best_diagnostic_no_pass | G_decay_nav | adaptive_quantile | 6.42% | -16.94% | N/A | N/A | 7.27% | -16.94% | 4.47% | -16.94% | 0.48% | -16.94% | Best candidate within its line and overheat direction |
| `G_decay_nav_score_veto_scoremax_4` | best_diagnostic_no_pass | G_decay_nav | score_veto | 4.04% | -19.96% | N/A | N/A | 4.15% | -19.96% | -1.14% | -19.96% | -4.51% | -19.96% | Best candidate within its line and overheat direction |
| `orig_full_v1_1_reference` | original_full_strategy_reference | original | original_full_chain | 11.84% | -36.96% | N/A | N/A | 12.61% | -36.96% | 3.41% | -36.96% | -26.98% | -36.96% | Full official V1.1 chain including target-vol and original overheat; context only, not Layer8 pass baseline |

## Stability Classification

- Decision: `do_not_add_layer8_overheat_keep_two_carried_lines`.
- Stability label: `no_direction_pass_diagnostic`.
- No overheat direction passed the same-line Layer 2+ drawdown-control rule.
- Fixed/adaptive overheat improved full-sample drawdown in some cases, but did not improve enough available windows.
- Score-veto changes had weak drawdown support and larger return drag.

## Decision

- This scan reports per-direction pass/fail only.
- Do not merge directions yet; stop here before any next layer.
- Candidates compare only against their own carried-line baseline.

## Source Audit

| code          | name                            | source                                  | adjustment                | first_available   | first_used   | last       |   rows | pool_rule                                                  | last_aligned   |   ffill_days_on_cn_calendar |
|:--------------|:--------------------------------|:----------------------------------------|:--------------------------|:------------------|:-------------|:-----------|-------:|:-----------------------------------------------------------|:---------------|----------------------------:|
| QQQ           | NASDAQ_QQQ_ADJ_CLOSE_PROXY      | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWG           | GERMANY_EWG_ADJ_CLOSE_PROXY     | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| EWJ           | JAPAN_EWJ_ADJ_CLOSE_PROXY       | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| GLD           | GOLD_GLD_ADJ_CLOSE_PROXY        | Yahoo Finance chart API                 | adjusted close            | 2006-11-02        | 2007-01-03   | 2016-12-30 |   2558 | core asset available from 2007 start                       | 2016-12-30     |                          80 |
| CN_CYB_399006 | CHINEXT_INDEX_PROXY_DYNAMIC_ADD | Eastmoney push2his kline secid=0.399006 | index close / price index | 2010-06-01        | 2010-06-01   | 2016-12-30 |   1601 | dynamic asset; no prices before 2010-06-01 and no backfill | 2016-12-30     |                           0 |

## Finalization

- Finalized at: 2026-07-01T22:19:17+08:00
- Decision: do_not_add_layer8_overheat_keep_two_carried_lines
- Stability label: no_direction_pass_diagnostic
- Complete checker: PASS
