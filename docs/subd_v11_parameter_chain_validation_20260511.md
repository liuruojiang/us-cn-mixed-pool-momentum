# Sub-D V1.1 Parameter Chain Validation - 2026-05-11

## Scope

This note records the independent validation of Sub-D six-ETF V1.1 parameter-chain review items 1.1-1.4.

Validation data:

- Source: QVeris `cn_financial_pro.history_quotation.v1`
- Adjustment: `cps=3`, continuous adjusted close
- Common last date: 2026-05-08
- Evaluation anchor: 2020-01-02
- Formal strategy code was not changed during these diagnostics.

## Meta Conclusion

The V1.1 chain contains several ad hoc-looking rules, but the independent checks show they are not arbitrary in the current data regime.

The pattern is consistent across modules:

- SCORE_MAX / score veto looks semantically dirty, but is empirically important.
- Staged-entry timeout is theoretically cleaner, but barely triggers.
- Overheat partial derisk is theoretically smoother, but degrades monotonically.
- Target-vol asset-return volatility is cleaner, but mainly lowers risk budget rather than improving risk-adjusted results.

The current V1.1 parameter set appears to be a local empirical optimum. Future cleanups should be treated as hypotheses and revalidated end to end before changing production behavior.

## 1.1 Score Veto

`SCORE_MAX=5` should be understood as an overheat veto, not as a normal score cap.

QVeris adjusted sensitivity:

| SCORE_MAX | CAGR | MaxDD | Sharpe |
| ---: | ---: | ---: | ---: |
| 3 | 47.18% | -28.80% | 1.64 |
| 4 | 52.40% | -19.37% | 1.75 |
| 5 | 61.35% | -18.05% | 1.98 |
| 6 | 57.98% | -18.54% | 1.90 |
| 8 | 50.98% | -20.32% | 1.73 |
| 10 | 47.09% | -20.32% | 1.64 |
| inf | 44.40% | -20.32% | 1.62 |

Interpretation:

- `5` is not an isolated spike; the 4-6 region is materially better than 3, 8, 10, and no cap.
- Subperiod best values are not perfectly stable. 2020 is an exception, while 2021 onward mostly favors 5 or 6.
- Keep the behavior for now, but rename the concept in future code cleanup.

Recommended no-behavior-change refactor:

```python
SCORE_MIN = 0.0
SCORE_OVERHEAT_VETO = 5.0

passes_entry = score > SCORE_MIN and passes_r2
passes_overheat_veto = score < SCORE_OVERHEAT_VETO
if passes_entry and passes_overheat_veto:
    scores[code] = score
```

## 1.2 Staged Entry And Switch Buffer

From-2020 validation:

| Scenario | CAGR | MaxDD | Sharpe |
| --- | ---: | ---: | ---: |
| Full entry, buffer 1.00, no overheat | 56.69% | -21.39% | 1.76 |
| Full entry, buffer 1.05, no overheat | 56.98% | -22.76% | 1.76 |
| Staged, no timeout, no overheat | 57.29% | -20.76% | 1.84 |
| Current V1.1 staged + overheat | 61.35% | -18.05% | 1.96 |
| Staged timeout 5D + overheat | 61.60% | -18.05% | 1.96 |

Decision:

- Keep current staged-entry behavior.
- Do not add timeout now.

Evidence:

- Longest consecutive half-position stretch was 14 trading days.
- 10-day and 15-day timeout did not trigger.
- 5-day timeout triggered only 4 times from 2020-01-02 to 2026-05-08.

Design constraint:

Staged-entry currently depends on the sensitivity of the existing switching rule. If future work makes switching slower, for example by increasing buffer or adding a score-margin condition, staged-entry timeout must be revalidated.

Potential future code comment:

```python
# Staged-entry depends on the current switching rule remaining sensitive enough.
# QVeris cps=3 validation through 2026-05-08 found max consecutive half-position
# of 14 trading days; 10D/15D timeouts did not trigger. Revalidate timeout if
# switch_buffer or score-margin logic changes.
```

## 1.3 Overheat Defense

Asset fairness issue is real. The fixed 20% bias threshold mostly targets ChiNext / CYB100.

| Asset | bias >= 20% days | same_side and bias >= 20% days |
| --- | ---: | ---: |
| CYB100_ETF | 65 | 52 |
| NASDAQ_ETF | 4 | 4 |
| GERMANY_ETF | 7 | 7 |
| NIKKEI_ETF | 4 | 4 |
| SOYMEAL_ETF | 8 | 8 |
| GOLD_ETF | 3 | 3 |

Derisk action scan:

| Overheat action | CAGR | MaxDD | Sharpe |
| --- | ---: | ---: | ---: |
| No overheat | 57.29% | -20.76% | 1.84 |
| scale = 0.0, same_side_or_exit | 61.35% | -18.05% | 1.96 |
| scale = 0.3, same_side_or_exit | 60.16% | -18.87% | 1.93 |
| scale = 0.5, same_side_or_exit | 59.36% | -19.41% | 1.90 |
| scale = 0.7, same_side_or_exit | 58.54% | -19.95% | 1.88 |
| scale = 0.0, exit_only | 61.18% | -18.05% | 1.96 |

Decision:

- Keep current full derisk action.
- Do not adopt partial derisk.

Future research:

- Study per-asset adaptive thresholds, such as rolling 252-day bias quantiles.
- If threshold logic changes, keep the action as full derisk first. Do not change threshold and action in the same experiment.

Interpretation:

The overheat signal behaves like a binary veto in this strategy chain, not like a continuous sizing signal.

## 1.4 Target-Volatility Overlay

The expert concern is mechanically valid: using strategy returns for realized vol can depress volatility estimates during half-position or cash periods, which raises future scale.

However, the validation shows this mostly changes risk budget rather than improving Sharpe.

From-2020 validation:

| Vol source / window | CAGR | MaxDD | Sharpe | Avg scale |
| --- | ---: | ---: | ---: | ---: |
| Strategy return, 80D | 61.35% | -18.05% | 1.96 | 1.18 |
| Strategy return, 40D | 61.86% | -18.12% | 1.99 | 1.20 |
| Strategy return, 25D | 61.50% | -18.88% | 1.96 | 1.22 |
| Asset full return, 80D | 47.25% | -15.73% | 1.88 | 1.00 |
| Asset full return, 40D | 53.94% | -15.73% | 2.01 | 1.04 |
| Asset full return, 25D | 53.66% | -15.01% | 1.95 | 1.07 |

Decision:

- Keep current strategy-return 80D target-vol method for V1.1.
- Do not switch to asset-full-return volatility in the current design.

Interpretation:

Target-vol source choice is primarily a risk-budget decision:

- Strategy-return volatility: more aggressive, higher average scale, higher CAGR, deeper drawdown.
- Asset-full-return volatility: more conservative, lower average scale, lower CAGR, shallower drawdown.
- Sharpe is broadly similar across the best variants, so the current method does not appear to inflate risk-adjusted performance materially.

Future research:

- Strategy-return 40D is a small candidate: CAGR and Sharpe are slightly higher, MaxDD is nearly unchanged, but max-leverage days rise materially.
- This is not urgent because 80D and 40D are economically close.

## Current Decisions

| Rule | Theoretical concern | Validation result | Decision |
| --- | --- | --- | --- |
| Score veto at 5 | Hidden overheat veto, possible overfit | 4-6 region robust, 5 best full-window | Keep behavior; rename semantics later |
| Staged-entry no timeout | Could stay half-position too long | Max half-position streak 14D; 10D/15D no trigger | Keep no-timeout |
| Overheat full derisk | All-or-nothing may be too violent | Partial derisk degrades monotonically | Keep full derisk |
| Fixed overheat threshold | Asset unfairness | Concern confirmed, mostly CYB100 | Future adaptive-threshold research |
| Target-vol strategy-return vol | Vol may be understated | Sharpe not impaired; mainly risk-budget choice | Keep current 80D method |

## Artifacts

Scripts:

- `analyze_score_max_veto_robustness_20260511.py`
- `analyze_subd_v11_1_2_switch_entry_20260511.py`
- `analyze_subd_v11_1_3_overheat_20260511.py`
- `analyze_subd_v11_1_4_target_vol_20260511.py`

Key outputs:

- `outputs/weighted_log_slope_qveris_cps3_score_max_veto_robustness_20260511_summary.csv`
- `outputs/weighted_log_slope_qveris_cps3_score_max_veto_robustness_20260511_best_by_period.csv`
- `outputs/subd_v11_1_2_switch_entry_qveris_cps3_20260511_summary.csv`
- `outputs/subd_v11_1_3_overheat_qveris_cps3_20260511_feature_distribution.csv`
- `outputs/subd_v11_1_3_overheat_qveris_cps3_20260511_summary.csv`
- `outputs/subd_v11_1_4_target_vol_qveris_cps3_20260511_summary.csv`
