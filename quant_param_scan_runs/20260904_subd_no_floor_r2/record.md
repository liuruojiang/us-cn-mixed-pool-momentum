# 无Score下限底座的R2复测

## Run Metadata

- Run id: 20260904_subd_no_floor_r2; 2026-09-04 Asia/Shanghai.
- Single-parameter research only. Existing untracked research and decision docs preserved; git status recorded in scan_meta.json.
- Source-change rule: research_only_no_source_change. No production changes, no accepted decision-document edits.

## Research Question

- Baseline: SCORE_MIN=-inf, SCORE_MAX=5, LOOKBACK=25, linear recency weights, Top1, full entry, Buffer=1, cash yield=0, R2/overheat/target-vol OFF.
- Grid: off, 0, .01, .025, .05, .075, .10, .125, .15, .175, .20, .225, .25, .275, .30, .325, .35, .375, .40, .45, .50, .60, .70, .80, .90.
- R2 calculation window remains 25 days; not separately scanned this turn.
- Predeclared filter acceptance: Full/10Y/5Y annual-return loss <=1pp; 3Y/1Y <=3pp; positive Full MDD improvement and MDD improvement in at least 3 windows. Seek adjacent passing points. No ex-post tolerance widening.
- Compare to no-floor/R2-off, never silently to old floor-zero baseline. See pre_scan_plan.md.

## Implementation Anchor

- research_subd_six_etf_weighted_slope.py: weighted_slope_score_and_r2 and calc_scores. R2 is sign-agnostic. Official defaults remain SCORE_MIN=0, SCORE_MAX=5.
- run_subd_six_etf_v1_1.py: official run_staged_entry with full entry, Buffer=1 and scanned R2.
- poe_subd_six_etf_v1_1_bot.py: independent .20 parity.
- Reuse official score function, cache its outputs under SCORE_MIN=-inf then filter by R2. No new score formula. Globals restored in finally. Uncached .20 rerun validates cached path.
- verify_results.py compares all 125 candidate/window outputs with official summarize() for CAGR, MDD, volatility and Sharpe.

## Data Snapshot

- Frozen Tencent fqkline qfq/front-adjusted six-ETF panel, 2011-12-09 through 2026-09-02, 3578 rows.
- Source: ../20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/price_snapshot_qfq.csv.gz.
- Accepted no-floor baseline: ../20260904_subd_no_floor_score_max/daily_outputs/score_max_5.csv.gz.
- SHA256: 0cc4af45158d6aaab4594b869b79309a96e8e3cc2f21a0205c38128913bec2aa.
- China exchange ETF sessions, Asia/Shanghai; annualization252; trailing windows252*N sessions, not calendar-year subtraction.
- Inherited available-asset pool: first observations 159915=2011-12-09, 518880=2013-07-29, 513030=2014-09-05, 159941=2015-07-13, 513520=2019-06-25, 159985=2019-12-05.
- Full/10Y use expanding availability, not fixed-six common-history formal evidence. All six first observed on 2019-12-05. Inception/vendor availability history inherited, not independently refreshed.
- Preserve warmup/pre-inception NaNs and stale-price flags. No new forward-fill, cache refresh or proxy extension. Endpoint retained Sep2 due to lagged 159915 in original source; not a current live snapshot.

## Cost and Execution Assumptions

- One-way .10% aggregate fee/slippage; asset switch turnover2, cash leg1; cash interest0, no leverage, financing, borrowing or hedge.
- Close signal/close fill research convention; old holding receives current close-to-close return, new position earns next-row return; transaction cost applied on trade row.
- Existing stale-price trade blocking retained. No separate opening-impact, orderbook liquidity/capacity, detailed T+1/price-limit or QDII-premium execution model; live fills not validated.

## Runtime Override Plan and Integrity Checks

- SCORE_MIN=-inf only in research runtime. SCORE_MAX=5 unchanged. R2 window and recency weighting unchanged.
- R2-off versus accepted no-floor baseline: NAV maximum absolute difference7.1054e-15; return9.9747e-17; position/turnover/fraction exact.
- R2=0 equals off exactly.
- Cached versus uncached .20 and runner versus Poe .20: all checked daily fields exact.
- All official summary metric differences <=1.3545e-14. Finite returns/NAV, binary exposure, modeled cost equality, previous-position timing and disabled-layer checks passed.
- Source hashes match preceding run, production git diff --exit-code passed.
- Existing production/source logic not edited; research files additive. No backup or production rollback required.

## Commands

Working directory: D:\动量策略\美股A股混合池子动量策略

```powershell
python -X utf8 D:/Codex/home/skills/quant-param-scan/scripts/init_quant_param_scan_run.py --root quant_param_scan_runs --project mixed-us-cn-momentum --strategy 'SubD no score floor' --subsystem six-etf --parameter-group R2_THRESHOLD --repo . --entrypoint run_subd_six_etf_v1_1.py --date 2026-09-04 --slug subd_no_floor_r2
python -X utf8 quant_param_scan_runs/20260904_subd_no_floor_r2/run_scan.py
python -X utf8 quant_param_scan_runs/20260904_subd_no_floor_r2/verify_results.py
python -X utf8 -m py_compile quant_param_scan_runs/20260904_subd_no_floor_r2/run_scan.py quant_param_scan_runs/20260904_subd_no_floor_r2/verify_results.py
git diff --check
git diff --exit-code -- research_subd_six_etf_weighted_slope.py run_subd_six_etf_v1_1.py poe_subd_six_etf_v1_1_bot.py
```

- Scan elapsed132.833 seconds,25 candidates and125 window rows.

## Output Files

- scan_summary.csv / window_metrics.csv: all real metrics and deltas.
- daily_outputs/: all25 daily curves.
- parity_checks.csv / metric_parity_checks.csv / integrity_checks.json: provenance and parity.
- width_checks.csv: predeclared rule results.
- negative_momentum_diagnostics.csv: sign-agnostic selection diagnostics.
- result_tables.md: full grids. scan_meta.json / command_log.txt: audit trail.

## Full-Sample Results and Window Results

### Complete grid results

Each cell: annual return / max drawdown. All results are retrospective research.

| R2 | Full | 10Y | 5Y | 3Y | 1Y |
| --- | ---: | ---: | ---: | ---: | ---: |
| off | 26.89% / -39.79% | 34.53% / -21.48% | 49.15% / -21.48% | 60.83% / -17.18% | 38.26% / -17.18% |
| 0.0 | 26.89% / -39.79% | 34.53% / -21.48% | 49.15% / -21.48% | 60.83% / -17.18% | 38.26% / -17.18% |
| 0.01 | 24.31% / -40.87% | 34.27% / -20.89% | 46.94% / -20.89% | 58.41% / -17.18% | 35.73% / -17.18% |
| 0.025 | 24.06% / -43.06% | 35.51% / -20.21% | 48.86% / -20.21% | 60.89% / -17.18% | 38.91% / -17.18% |
| 0.05 | 24.09% / -35.07% | 33.12% / -23.19% | 47.26% / -18.66% | 59.49% / -17.57% | 44.09% / -17.18% |
| 0.075 | 25.00% / -30.71% | 31.92% / -22.45% | 47.01% / -20.53% | 58.66% / -20.53% | 47.15% / -17.18% |
| 0.1 | 25.99% / -30.40% | 34.46% / -19.00% | 50.19% / -19.00% | 61.64% / -18.14% | 49.90% / -17.18% |
| 0.125 | 28.49% / -29.21% | 34.92% / -19.79% | 50.21% / -19.79% | 61.89% / -18.80% | 49.65% / -17.18% |
| 0.15 | 26.50% / -24.60% | 32.05% / -22.87% | 49.51% / -22.87% | 62.57% / -22.07% | 49.64% / -15.84% |
| 0.175 | 29.52% / -25.62% | 33.11% / -25.62% | 51.33% / -25.62% | 68.30% / -22.58% | 72.44% / -15.84% |
| 0.2 | 28.67% / -27.13% | 30.49% / -27.13% | 49.67% / -27.13% | 62.42% / -27.13% | 71.50% / -15.84% |
| 0.225 | 29.82% / -28.18% | 32.00% / -27.96% | 53.87% / -27.96% | 65.65% / -27.96% | 86.11% / -12.38% |
| 0.25 | 30.42% / -30.85% | 30.97% / -27.66% | 51.11% / -27.66% | 63.32% / -27.66% | 90.57% / -12.38% |
| 0.275 | 29.74% / -29.12% | 30.87% / -29.12% | 49.01% / -29.12% | 64.09% / -29.12% | 93.44% / -12.38% |
| 0.3 | 27.25% / -28.63% | 29.38% / -28.63% | 45.97% / -28.63% | 56.49% / -28.63% | 87.36% / -12.38% |
| 0.325 | 27.59% / -28.23% | 28.49% / -28.23% | 43.74% / -28.23% | 50.01% / -28.23% | 78.76% / -12.38% |
| 0.35 | 27.12% / -28.87% | 27.35% / -28.87% | 42.48% / -28.87% | 47.74% / -28.87% | 74.57% / -12.86% |
| 0.375 | 24.07% / -34.40% | 24.95% / -34.40% | 36.27% / -34.40% | 37.50% / -34.40% | 57.60% / -19.64% |
| 0.4 | 21.21% / -36.79% | 22.45% / -36.79% | 32.54% / -36.79% | 34.79% / -36.79% | 61.86% / -16.92% |
| 0.45 | 19.14% / -38.00% | 21.66% / -38.00% | 30.05% / -38.00% | 33.21% / -38.00% | 65.20% / -16.82% |
| 0.5 | 13.74% / -37.49% | 17.31% / -37.49% | 26.55% / -37.49% | 25.38% / -37.49% | 63.49% / -14.47% |
| 0.6 | 16.51% / -31.03% | 17.10% / -31.03% | 29.23% / -31.03% | 29.74% / -31.03% | 58.38% / -13.16% |
| 0.7 | 9.29% / -33.92% | 8.44% / -33.92% | 19.54% / -21.99% | 19.23% / -20.26% | 30.51% / -12.36% |
| 0.8 | 1.53% / -45.33% | 2.86% / -38.71% | 15.49% / -20.32% | 6.82% / -20.32% | 10.91% / -13.86% |
| 0.9 | -0.73% / -24.80% | -0.34% / -21.16% | 0.29% / -7.91% | -0.13% / -7.91% | -2.67% / -4.80% |

### Deltas versus R2 off, no lower floor

Each cell: annual-return delta / max-drawdown improvement, percentage points.

| R2 | Full | 10Y | 5Y | 3Y | 1Y |
| --- | ---: | ---: | ---: | ---: | ---: |
| off | +0.00 / +0.00 | +0.00 / +0.00 | +0.00 / +0.00 | +0.00 / +0.00 | +0.00 / +0.00 |
| 0.0 | +0.00 / +0.00 | +0.00 / +0.00 | +0.00 / +0.00 | +0.00 / +0.00 | +0.00 / +0.00 |
| 0.01 | -2.58 / -1.08 | -0.27 / +0.59 | -2.21 / +0.59 | -2.42 / +0.00 | -2.53 / -0.00 |
| 0.025 | -2.83 / -3.27 | +0.98 / +1.28 | -0.28 / +1.28 | +0.06 / +0.00 | +0.65 / -0.00 |
| 0.05 | -2.79 / +4.72 | -1.41 / -1.71 | -1.89 / +2.82 | -1.34 / -0.38 | +5.83 / -0.00 |
| 0.075 | -1.89 / +9.09 | -2.62 / -0.96 | -2.14 / +0.95 | -2.17 / -3.35 | +8.89 / +0.00 |
| 0.1 | -0.90 / +9.39 | -0.07 / +2.48 | +1.04 / +2.48 | +0.81 / -0.96 | +11.64 / +0.00 |
| 0.125 | +1.60 / +10.58 | +0.39 / +1.70 | +1.06 / +1.70 | +1.06 / -1.62 | +11.39 / +0.00 |
| 0.15 | -0.39 / +15.19 | -2.48 / -1.39 | +0.37 / -1.39 | +1.74 / -4.88 | +11.38 / +1.35 |
| 0.175 | +2.63 / +14.17 | -1.42 / -4.14 | +2.18 / -4.14 | +7.47 / -5.39 | +34.17 / +1.35 |
| 0.2 | +1.78 / +12.66 | -4.05 / -5.65 | +0.52 / -5.65 | +1.59 / -9.94 | +33.24 / +1.35 |
| 0.225 | +2.94 / +11.62 | -2.53 / -6.48 | +4.73 / -6.48 | +4.82 / -10.78 | +47.85 / +4.81 |
| 0.25 | +3.53 / +8.94 | -3.57 / -6.18 | +1.96 / -6.18 | +2.49 / -10.48 | +52.30 / +4.81 |
| 0.275 | +2.85 / +10.67 | -3.66 / -7.64 | -0.13 / -7.64 | +3.26 / -11.94 | +55.18 / +4.81 |
| 0.3 | +0.37 / +11.16 | -5.15 / -7.15 | -3.18 / -7.15 | -4.34 / -11.45 | +49.10 / +4.81 |
| 0.325 | +0.70 / +11.56 | -6.05 / -6.75 | -5.41 / -6.75 | -10.83 / -11.05 | +40.50 / +4.81 |
| 0.35 | +0.23 / +10.92 | -7.18 / -7.39 | -6.67 / -7.39 | -13.09 / -11.69 | +36.30 / +4.32 |
| 0.375 | -2.82 / +5.39 | -9.58 / -12.92 | -12.87 / -12.92 | -23.33 / -17.21 | +19.34 / -2.46 |
| 0.4 | -5.68 / +3.01 | -12.08 / -15.30 | -16.61 / -15.30 | -26.04 / -19.60 | +23.59 / +0.26 |
| 0.45 | -7.75 / +1.80 | -12.87 / -16.51 | -19.10 / -16.51 | -27.63 / -20.81 | +26.93 / +0.37 |
| 0.5 | -13.15 / +2.30 | -17.23 / -16.01 | -22.60 / -16.01 | -35.45 / -20.31 | +25.23 / +2.72 |
| 0.6 | -10.37 / +8.76 | -17.44 / -9.55 | -19.92 / -9.55 | -31.09 / -13.84 | +20.12 / +4.02 |
| 0.7 | -17.60 / +5.87 | -26.09 / -12.44 | -29.60 / -0.51 | -41.60 / -3.08 | -7.75 / +4.82 |
| 0.8 | -25.36 / -5.54 | -31.67 / -17.23 | -33.65 / +1.16 | -54.01 / -3.14 | -27.36 / +3.33 |
| 0.9 | -27.61 / +15.00 | -34.88 / +0.32 | -48.86 / +13.57 | -60.96 / +9.27 | -40.93 / +12.39 |

## Stability Classification

- narrow_stable: only .100 and .125 pass the predeclared rule. These are two adjacent tested points, not a proven continuous interval or broad platform.
- .100 reduces Full CAGR by .90pp, reduces Full MDD by9.39pp, improves 10Y/5Y DD, but worsens3Y DD by.96pp. .125 increases CAGR in all5 windows, improves Full/10Y/5Y DD, worsens3Y DD1.62pp, leaves1Y DD unchanged.
- .075 fails Full/10Y/5Y return tolerances. .150 fails10Y return tolerance and worsens10Y/5Y/3Y DD. Passing neighborhood is bounded by nonpassing sampled points.
- Old .20 is not broadly robust on the new base: Full CAGR+1.78pp and DD+12.66pp, but10Y CAGR-4.05pp and10Y/5Y/3Y DD worsens5.65/5.65/9.94pp.
- .175-.350 have sizable recent gains but nonpassing longer-window tradeoffs. Full CAGR remains above off through sampled .350, then below at .375, but that is not cross-window superiority.
- High thresholds increasingly suppress exposure; .90 holds about6.12% of days. Smaller drawdown there is not useful standalone evidence.
- All windows overlap and prior scans used the same sample. No fresh OOS, survivorship validation, R2-window scan or sign-aware new feature test. Fewer parameters do not eliminate selection bias.

## Negative Momentum Diagnostic

- Negative best-candidate days: off314; .100410; .125426; .200463.
- On165 days at .125 and225 days at .20, the chosen best candidate has negative momentum while R2-off's best candidate is positive.
- This confirms changed ranking/filter semantics: a weakly fitted positive trend can be filtered out while a strongly fitted negative trend remains. It does NOT alone attribute the realized losses to these days.
- Do not silently reintroduce Score>0 or a sign gate; that would change the requested no-floor base.

## Decision

- watchlist, no automatic promotion. Keep carried research baseline R2-off pending user decision.
- .100 primary simple-threshold research candidate; .125 neighboring return-heavy candidate. Do not choose .125 purely because its Full CAGR is higher.
- Old .20 not recommended for direct reuse on this base. Stop after this one parameter; no next parameter without confirmation.
- All production defaults remain unchanged.

## User-Facing Summary

取消下限后R2仍有研究价值，但原先较宽的有效区间不能照搬。按预先收益/回撤要求，仅0.10和0.125两个相邻测试点通过；0.125五窗口收益均提高，但3年回撤略差。当前只记候选，不启用，等待用户确认。

## Finalization

- Finalized at: 2026-09-04T11:22:23+08:00
- Decision: watchlist
- Stability label: narrow_stable
- Complete checker: PASS
