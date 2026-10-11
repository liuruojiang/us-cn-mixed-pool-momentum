# 取消Score下限后的上限复测

## Run Metadata

- Run id: 20260904_subd_no_floor_score_max; date: 2026-09-04 Asia/Shanghai.
- Research-only single-parameter scan; official entrypoint: run_subd_six_etf_v1_1.py.
- Existing untracked research/docs preserved; full git status before/after is in scan_meta.json.
- Source-change rule: research_only_no_source_change. No production or accepted decision document modified.

## Research Question

- Baseline: SCORE_MIN=-inf, SCORE_MAX=5, LOOKBACK=25, linear recency weights, Top1, full entry, Buffer=1, R2/overheat/target-vol OFF, cash yield=0.
- Grid: 2, 3, 4, 4.5, 5, 5.5, 6, 6.5, 7, 8, 10, infinity.
- Test whether cap 5 remains useful after removing the floor; no R2 or other parameter scan in this run.
- Predeclared validation and width criteria: pre_scan_plan.md. No automatic promotion.

## Implementation Anchor

- research_subd_six_etf_weighted_slope.py: weighted_slope_score_and_r2 and calc_scores; original production SCORE_MIN=0, SCORE_MAX=5.
- run_subd_six_etf_v1_1.py: run_staged_entry with full_entry/1.0, r2=None, buffer=1.0.
- poe_subd_six_etf_v1_1_bot.py: independent no-floor/cap-5 baseline parity.
- Reused original cap-scan harness and prior lookback metrics helper; no new signal formula. All module overrides use finally restoration.
- verify_results.py reconciles all 60 candidate/window metric sets to official summarize(), including CAGR, MDD, volatility and Sharpe.

## Data Snapshot

- Actual frozen Tencent fqkline qfq/front-adjusted panel; 2011-12-09 through 2026-09-02, 3578 rows.
- Panel source: ../20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/price_snapshot_qfq.csv.gz.
- Accepted baseline: ../20260904_mixed_us_cn_momentum_subd_pure_momentum_core_six_etf_mixed_pool_score_min_absolute_momentum_floor/daily_outputs/score_min_-inf.csv.gz.
- Frozen panel SHA256: 0cc4af45158d6aaab4594b869b79309a96e8e3cc2f21a0205c38128913bec2aa.
- China exchange ETF calendar, Asia/Shanghai; annualization 252 sessions and trailing windows 252*N sessions, not calendar-year subtraction.
- Inherited pre-inception missing values and stale-price forward-fill flags preserved; zero duplicate dates and no nonpositive observed prices. No new forward-fill, remote refresh, cache mutation or proxy extension.
- First available prices: 159915 2011-12-09; 518880 2013-07-29; 513030 2014-09-05; 159941 2015-07-13; 513520 2019-06-25; 159985 2019-12-05.
- Historical Full/10Y pool expands with available assets. All six first have observations on 2019-12-05; this run preserves the historical comparison, NOT fixed-six common-history formal evidence. Inception/source availability is inherited, not newly independently audited.
- Endpoint remains Sep 2 because 159915 lagged the other assets in the frozen source. This is historical research, not refreshed live data.

## Cost and Execution Assumptions

- 0.10% one-way aggregate fee/slippage; asset switch turnover=2, cash leg=1.
- Close signal/close fill research convention; old holding earns today's close-to-close return, new holding starts next-row return; same-day cost applied. No same-day new-position return leakage.
- Full entry, max exposure 1, no leverage, financing, borrowing, hedge or cash interest.
- Existing stale-price trade blocking preserved. Separate opening impact, orderbook capacity, detailed price-limit/T+1 executability and QDII premium constraints not simulated. Close-fill assumption does not establish live executability.

## Runtime Override Plan and Integrity Checks

- SCORE_MIN=-inf held fixed while SCORE_MAX changes; original subd and Poe globals restored in finally.
- Baseline matches accepted no-floor curve: maximum NAV difference 7.1054e-15, return difference 9.9747e-17; positions, turnover and fractions exact.
- Runner/Poe no-floor baseline: all checked daily fields exact.
- Official metric parity maximum difference 1.0103e-14. Passed finite-value, exposure, cost=turnover*0.001, previous-position timing and disabled-layer checks for all 12 curves.
- Baseline includes 314 days with negative best score, confirming the floor is actually disabled.
- Production file hashes unchanged; git diff --exit-code for the three production scripts passed.
- No risky existing code was edited, so no backup was required. Rollback: none for production; research files are additive.

## Commands

Working directory: D:\动量策略\美股A股混合池子动量策略

```powershell
python -X utf8 D:/Codex/home/skills/quant-param-scan/scripts/init_quant_param_scan_run.py --root quant_param_scan_runs --project mixed-us-cn-momentum --strategy 'SubD no score floor' --subsystem six-etf --parameter-group SCORE_MAX --repo . --entrypoint run_subd_six_etf_v1_1.py --date 2026-09-04 --slug subd_no_floor_score_max
python -X utf8 quant_param_scan_runs/20260904_subd_no_floor_score_max/run_scan.py
python -X utf8 quant_param_scan_runs/20260904_subd_no_floor_score_max/verify_results.py
python -X utf8 -m py_compile quant_param_scan_runs/20260904_subd_no_floor_score_max/run_scan.py quant_param_scan_runs/20260904_subd_no_floor_score_max/verify_results.py
git diff --check
git diff --exit-code -- research_subd_six_etf_weighted_slope.py run_subd_six_etf_v1_1.py poe_subd_six_etf_v1_1_bot.py
```

- Scan runtime: 192.016 seconds; 12 candidates x 5 windows.

## Output Files

- scan_summary.csv: 60 actual metric rows.
- window_metrics.csv: 12 candidates, all windows and deltas versus no-floor/cap-5.
- daily_outputs/: all 12 daily curves.
- parity_checks.csv, metric_parity_checks.csv, integrity_checks.json: baseline and metric evidence, source hashes.
- width_checks.csv: predeclared quantitative checks.
- result_tables.md: complete metrics/deltas.
- scan_meta.json and command_log.txt: provenance and execution log.

## Full-Sample Results and Window Results

### Complete grid results

Each cell: annual return / max drawdown. All results are retrospective research.

| Cap | Full | 10Y | 5Y | 3Y | 1Y |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2.0 | 10.36% / -54.85% | 15.88% / -26.00% | 20.32% / -26.00% | 27.18% / -22.01% | 7.25% / -22.01% |
| 3.0 | 17.82% / -48.14% | 24.27% / -28.09% | 29.52% / -28.09% | 38.37% / -15.85% | 16.09% / -14.67% |
| 4.0 | 21.38% / -47.61% | 27.59% / -23.85% | 38.48% / -23.85% | 45.16% / -16.38% | 14.89% / -16.38% |
| 4.5 | 23.92% / -46.42% | 30.63% / -22.85% | 46.65% / -22.85% | 60.75% / -15.85% | 41.45% / -15.34% |
| 5.0 | 26.89% / -39.79% | 34.53% / -21.48% | 49.15% / -21.48% | 60.83% / -17.18% | 38.26% / -17.18% |
| 5.5 | 27.64% / -39.79% | 36.25% / -20.43% | 51.54% / -20.43% | 63.92% / -17.69% | 50.23% / -17.69% |
| 6.0 | 26.89% / -39.74% | 33.57% / -21.19% | 49.37% / -20.43% | 58.13% / -17.22% | 42.03% / -17.22% |
| 6.5 | 25.50% / -45.32% | 32.36% / -21.19% | 46.43% / -20.43% | 53.36% / -17.36% | 33.99% / -17.36% |
| 7.0 | 25.95% / -45.09% | 31.53% / -20.43% | 47.01% / -20.43% | 58.55% / -16.89% | 40.82% / -16.89% |
| 8.0 | 27.96% / -45.42% | 32.24% / -23.43% | 50.89% / -20.43% | 69.08% / -16.12% | 61.81% / -16.12% |
| 10.0 | 26.94% / -44.86% | 30.33% / -23.43% | 46.48% / -20.43% | 60.92% / -16.92% | 47.10% / -16.92% |
| inf | 25.65% / -40.35% | 23.79% / -30.05% | 32.63% / -30.05% | 36.49% / -30.05% | 23.67% / -20.46% |

### Deltas versus cap 5, no lower floor

Each cell: annual-return delta / max-drawdown improvement, percentage points.

| Cap | Full | 10Y | 5Y | 3Y | 1Y |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2.0 | -16.53 / -15.06 | -18.65 / -4.52 | -28.82 / -4.52 | -33.65 / -4.82 | -31.01 / -4.82 |
| 3.0 | -9.07 / -8.35 | -10.26 / -6.61 | -19.63 / -6.61 | -22.46 / +1.33 | -22.18 / +2.51 |
| 4.0 | -5.51 / -7.82 | -6.95 / -2.36 | -10.67 / -2.36 | -15.68 / +0.81 | -23.38 / +0.81 |
| 4.5 | -2.97 / -6.63 | -3.90 / -1.37 | -2.49 / -1.37 | -0.09 / +1.33 | +3.18 / +1.85 |
| 5.0 | +0.00 / +0.00 | +0.00 / +0.00 | +0.00 / +0.00 | +0.00 / +0.00 | +0.00 / +0.00 |
| 5.5 | +0.75 / +0.00 | +1.72 / +1.05 | +2.40 / +1.05 | +3.09 / -0.50 | +11.97 / -0.50 |
| 6.0 | +0.00 / +0.05 | -0.97 / +0.29 | +0.23 / +1.05 | -2.71 / -0.04 | +3.76 / -0.04 |
| 6.5 | -1.38 / -5.53 | -2.17 / +0.29 | -2.72 / +1.05 | -7.47 / -0.18 | -4.27 / -0.18 |
| 7.0 | -0.94 / -5.30 | -3.00 / +1.05 | -2.14 / +1.05 | -2.28 / +0.29 | +2.56 / +0.29 |
| 8.0 | +1.08 / -5.63 | -2.29 / -1.94 | +1.75 / +1.05 | +8.25 / +1.06 | +23.55 / +1.06 |
| 10.0 | +0.05 / -5.07 | -4.20 / -1.94 | -2.66 / +1.05 | +0.09 / +0.26 | +8.84 / +0.26 |
| inf | -1.24 / -0.56 | -10.75 / -8.57 | -16.52 / -8.57 | -24.34 / -12.86 | -14.59 / -3.27 |

## Stability Classification

- Label: narrow_stable for the cap-5-to-6 region, NOT wide_stable and NOT proof of no overfit.
- Removing cap loses annual return in all five windows and deepens every MDD. Full CAGR -1.24pp and MDD -0.56pp; losses become much larger in the 10Y/5Y/3Y windows.
- Cap 5.5 improves all five CAGR windows, leaves Full MDD unchanged, improves 10Y/5Y MDD, but worsens 3Y/1Y MDD by about 0.50pp. Full gain +0.75pp versus 1Y +11.97pp: recent gain is much larger.
- Cap 6 is the only alternative numerically passing the predeclared DD-control rule, but Full MDD improves only about 0.05pp and CAGR essentially unchanged; this is too small to claim a meaningful risk-control improvement.
- Core width check is NOT fully passed: 4.5 retains 88.97% of cap-5 Full CAGR, but next connected point 4 retains only 79.50%, below 80%; left-side MDD is much worse. Right neighbors 5.5 and 6 retain >=100%, but 6.5 worsens Full MDD by 5.53pp. We do not claim a wide symmetric platform.
- Cap 8 has higher Full/recent CAGR but weaker 10Y and deeper Full MDD; not a robust replacement supported by 7/10.
- Full trade days decline: cap 5=349, 5.5=336, 6=330, no cap=237. Full average exposure: 98.21%, 98.30%, 98.41%, 99.30%. Lower turnover/cost does not rescue no-cap performance.
- No-cap annual volatility 29.30% versus cap-5 25.46%; Sharpe 0.925 versus 1.062. Cost sums are arithmetic daily cost-rate sums, not terminal wealth loss.
- Windows overlap, are retrospective and were used repeatedly in prior research; no untouched OOS or universe-selection robustness established. Width does not rule out overfit.

## Decision

- keep_default for the research carried line: keep SCORE_MAX=5 with SCORE_MIN=-inf pending user confirmation.
- Cap 5.5 is a watchlist candidate, not adopted. Cap 6 is nearby confirmation only; do not overstate its tiny Full DD gain.
- Do not cancel the upper veto based on these results. Stop here and wait for the user's confirmation before R2 or another parameter.
- Production runner/Poe remain unchanged, including production SCORE_MIN=0.

## User-Facing Summary

取消下限以后，上限依然有作用：上限全部取消，五个窗口收益与回撤同时恶化。5.5是值得记录但尚未晋升的新候选；5左侧表现不稳，不能称为宽平台。倾向继续保留上限5，等用户确认后再进行下一项。

## Finalization

- Finalized at: 2026-09-04T11:15:08+08:00
- Decision: keep_default
- Stability label: narrow_stable
- Complete checker: PASS
