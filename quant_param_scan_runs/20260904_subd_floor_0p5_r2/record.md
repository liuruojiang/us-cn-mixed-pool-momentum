# Score > 0.5条件分支的R2扫描

## Run Metadata

- Run id:20260904_subd_floor_0p5_r2;2026-09-04 Asia/Shanghai.
- User explicitly requested the R2 display under Score>0.5. This is a conditional research branch, not reversal of the accepted no-floor mainline.
- Single parameter R2 threshold; source-change rule research_only_no_source_change. Existing untracked research/docs preserved; full before/after git status in scan_meta.json.
- No production edits or mainline decision-doc edits.

## Research Question

- Strict 0.5<Score<5, LOOKBACK25, linear weights, Top1, full entry, Buffer1, overheat/target-vol OFF, cash yield0.
- Baseline: same Score>0.5 branch with R2 OFF, not no-floor baseline.
- R2 grid: off,0,.01,.025,.05,.075,.10,.125,.15,.175,.20,.225,.25,.275,.30,.325,.35,.375,.40,.45,.50,.60,.70,.80,.90.
- Predeclared filter criterion: Full/10Y/5Y annual return loss<=1pp;3Y/1Y<=3pp; Full MDD improved and at least3 windows improved; seek adjacent passing points. No post-result tolerance widening.
- R2 window remains25. Neither Score floor nor upper bound optimized this turn.

## Implementation Anchor

- research_subd_six_etf_weighted_slope.py: official weighted_slope_score_and_r2 and calc_scores; strict SCORE_MIN<score<SCORE_MAX.
- run_subd_six_etf_v1_1.py: official run_staged_entry, full_entry1, Buffer1.
- poe_subd_six_etf_v1_1_bot.py: independent baseline validation atR2=.20.
- Research harness caches official scores under floor0.5, filters by R2 and calls official execution. Globals restored in finally. All125 metric sets reconciled with official summarize().
- Actual production SCORE_MIN remains0 and SCORE_MAX5.

## Data Snapshot

- Frozen Tencent fqkline qfq/front-adjusted panel,2011-12-09 through2026-09-02,3578 rows.
- Source: ../20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/price_snapshot_qfq.csv.gz.
- Saved conditional baseline: ../20260904_mixed_us_cn_momentum_subd_pure_momentum_core_six_etf_mixed_pool_score_min_absolute_momentum_floor/daily_outputs/score_min_0p5.csv.gz.
- Snapshot SHA256:0cc4af45158d6aaab4594b869b79309a96e8e3cc2f21a0205c38128913bec2aa.
- China exchange ETF calendar,Asia/Shanghai;252-session annualization/trailing windows. No US direct-market series mixed into Chinese sessions.
- Preserve original warmup/pre-inception NaNs, available-asset rules and stale-price flags; no new fill, cache refresh or proxy extension. Latest matched date remainsSep2 due to159915 lag in source snapshot.
- First observations:159915=2011-12-09;518880=2013-07-29;513030=2014-09-05;159941=2015-07-13;513520=2019-06-25;159985=2019-12-05.
- Full/10Y are historical expanding-availability pool evidence, not fixed-six common-history formal evidence. All six first observed2019-12-05; inception history inherited, not freshly independently audited.

## Cost and Execution Assumptions

- One-way0.10% aggregate fees/slippage; asset switch turnover2, cash leg1. No leverage, financing, borrowing, hedge or cash yield.
- Old holding earns current close-close return; research close signal/close fill, cost on trade row, new position earns next-row return.
- Existing stale-price trade guard retained. No detailed liquidity/capacity, limit-price/T+1, opening-impact or QDII-premium execution model; live executability not established.

## Runtime Override Plan and Integrity Checks

- SCORE_MIN=0.5 set only in research runtime; all globals restored. Verify every finite best-candidate score strictly>0.5 and<5.
- R2-off versus historical score_min_0p5 daily curve: NAV max difference3.5527e-15, return9.9530e-17; position/turnover/fraction exact.
- Off=0 exact. Cached versus uncached.20 and runner versus Poe.20 all checked daily fields exact.
- All official summary metrics agree within1.0298e-14; finite metrics, binary exposures, cost equality, previous-position timing and disabled-layer checks pass.
- Negative-candidate count is0 at every threshold, as required by positive floor. Source hashes match prior run; production diff empty.
- New research files only; no risky existing-file edit, backup or production rollback required.

## Commands

Working directory:D:\动量策略\美股A股混合池子动量策略

```powershell
python -X utf8 D:/Codex/home/skills/quant-param-scan/scripts/init_quant_param_scan_run.py --root quant_param_scan_runs --project mixed-us-cn-momentum --strategy 'SubD score floor 0.5' --subsystem six-etf --parameter-group R2_THRESHOLD --repo . --entrypoint run_subd_six_etf_v1_1.py --date 2026-09-04 --slug subd_floor_0p5_r2
python -X utf8 quant_param_scan_runs/20260904_subd_floor_0p5_r2/run_scan.py
python -X utf8 quant_param_scan_runs/20260904_subd_floor_0p5_r2/verify_results.py
python -X utf8 -m py_compile quant_param_scan_runs/20260904_subd_floor_0p5_r2/run_scan.py quant_param_scan_runs/20260904_subd_floor_0p5_r2/verify_results.py
git diff --check
git diff --exit-code -- research_subd_six_etf_weighted_slope.py run_subd_six_etf_v1_1.py poe_subd_six_etf_v1_1_bot.py
```

- Scan runtime133.11sec;25 candidates/125 metric rows.

## Output Files

- scan_summary.csv and window_metrics.csv: full metrics and same-branch deltas.
- daily_outputs/:25 daily curves.
- parity_checks.csv, metric_parity_checks.csv, integrity_checks.json: verification and hashes.
- width_checks.csv: predeclared criterion results.
- negative_momentum_diagnostics.csv: all negative selections absent.
- result_tables.md: full tables; scan_meta.json and command_log.txt: provenance.

## Full-Sample Results and Window Results

### Complete grid results

Each cell: annual return / max drawdown. All results are retrospective research.

| R2 | Full | 10Y | 5Y | 3Y | 1Y |
| --- | ---: | ---: | ---: | ---: | ---: |
| off | 26.43% / -27.40% | 33.27% / -21.42% | 48.15% / -19.72% | 60.82% / -16.18% | 38.45% / -15.87% |
| 0.0 | 26.43% / -27.40% | 33.27% / -21.42% | 48.15% / -19.72% | 60.82% / -16.18% | 38.45% / -15.87% |
| 0.01 | 26.43% / -27.40% | 33.27% / -21.42% | 48.15% / -19.72% | 60.82% / -16.18% | 38.45% / -15.87% |
| 0.025 | 26.43% / -27.40% | 33.27% / -21.42% | 48.15% / -19.72% | 60.82% / -16.18% | 38.45% / -15.87% |
| 0.05 | 26.06% / -26.94% | 33.27% / -21.42% | 48.15% / -19.72% | 60.82% / -16.18% | 38.45% / -15.87% |
| 0.075 | 26.69% / -22.77% | 33.18% / -21.42% | 47.95% / -19.72% | 60.47% / -16.74% | 38.45% / -15.87% |
| 0.1 | 26.56% / -22.77% | 33.16% / -21.42% | 48.58% / -19.72% | 61.61% / -15.87% | 38.45% / -15.87% |
| 0.125 | 27.54% / -22.83% | 33.36% / -21.42% | 49.09% / -19.72% | 62.52% / -15.87% | 38.45% / -15.87% |
| 0.15 | 27.71% / -22.83% | 33.61% / -21.86% | 49.65% / -20.17% | 63.86% / -15.87% | 39.62% / -15.87% |
| 0.175 | 29.03% / -22.03% | 34.25% / -21.86% | 51.89% / -20.17% | 69.23% / -15.87% | 55.06% / -15.87% |
| 0.2 | 28.92% / -22.51% | 33.13% / -21.86% | 51.67% / -20.17% | 68.82% / -15.87% | 55.06% / -15.87% |
| 0.225 | 28.46% / -22.51% | 32.68% / -21.86% | 52.29% / -20.17% | 68.20% / -15.87% | 55.97% / -15.87% |
| 0.25 | 30.03% / -22.01% | 33.97% / -17.42% | 52.98% / -17.07% | 67.50% / -15.04% | 59.86% / -13.77% |
| 0.275 | 29.27% / -19.32% | 33.25% / -17.66% | 50.84% / -17.07% | 64.96% / -15.04% | 50.51% / -13.77% |
| 0.3 | 26.39% / -21.15% | 30.60% / -16.60% | 46.97% / -16.48% | 59.11% / -15.33% | 51.86% / -13.00% |
| 0.325 | 26.18% / -21.15% | 30.11% / -15.99% | 45.63% / -15.06% | 55.58% / -14.86% | 52.50% / -11.89% |
| 0.35 | 26.12% / -21.76% | 29.44% / -16.60% | 46.55% / -15.06% | 54.52% / -15.05% | 54.59% / -13.06% |
| 0.375 | 23.02% / -22.55% | 25.49% / -22.53% | 39.11% / -22.53% | 42.79% / -22.53% | 41.78% / -18.82% |
| 0.4 | 20.81% / -24.26% | 23.86% / -24.26% | 35.39% / -24.26% | 37.47% / -24.26% | 37.37% / -17.47% |
| 0.45 | 17.65% / -28.34% | 20.87% / -28.34% | 31.42% / -28.34% | 32.17% / -28.34% | 38.78% / -16.82% |
| 0.5 | 12.84% / -26.79% | 17.76% / -26.79% | 29.20% / -26.79% | 31.02% / -26.79% | 44.79% / -14.77% |
| 0.6 | 12.56% / -28.98% | 17.57% / -23.04% | 31.52% / -16.34% | 31.79% / -13.34% | 40.34% / -13.15% |
| 0.7 | 5.10% / -42.18% | 7.65% / -31.18% | 21.89% / -14.66% | 16.77% / -14.66% | 19.45% / -14.66% |
| 0.8 | -0.48% / -37.81% | -0.35% / -28.60% | 5.26% / -21.69% | -3.22% / -21.69% | -5.28% / -14.05% |
| 0.9 | -1.45% / -19.60% | -1.48% / -16.64% | -2.74% / -16.54% | -3.09% / -12.23% | -2.67% / -4.80% |

### Deltas versus R2 off, Score floor 0.5

Each cell: annual-return delta / max-drawdown improvement, percentage points.

| R2 | Full | 10Y | 5Y | 3Y | 1Y |
| --- | ---: | ---: | ---: | ---: | ---: |
| off | +0.00 / +0.00 | +0.00 / +0.00 | +0.00 / +0.00 | +0.00 / +0.00 | +0.00 / +0.00 |
| 0.0 | +0.00 / +0.00 | +0.00 / +0.00 | +0.00 / +0.00 | +0.00 / +0.00 | +0.00 / +0.00 |
| 0.01 | +0.00 / +0.00 | +0.00 / +0.00 | +0.00 / +0.00 | +0.00 / +0.00 | +0.00 / +0.00 |
| 0.025 | +0.00 / +0.00 | +0.00 / +0.00 | +0.00 / +0.00 | +0.00 / +0.00 | +0.00 / +0.00 |
| 0.05 | -0.37 / +0.46 | -0.00 / -0.00 | +0.00 / -0.00 | -0.00 / +0.00 | -0.00 / -0.00 |
| 0.075 | +0.26 / +4.63 | -0.09 / +0.00 | -0.20 / -0.00 | -0.36 / -0.56 | -0.00 / -0.00 |
| 0.1 | +0.13 / +4.63 | -0.12 / +0.00 | +0.43 / -0.00 | +0.79 / +0.31 | -0.00 / -0.00 |
| 0.125 | +1.11 / +4.57 | +0.09 / -0.00 | +0.94 / -0.00 | +1.70 / +0.31 | -0.00 / +0.00 |
| 0.15 | +1.28 / +4.57 | +0.34 / -0.44 | +1.50 / -0.45 | +3.04 / +0.31 | +1.17 / -0.00 |
| 0.175 | +2.59 / +5.37 | +0.98 / -0.44 | +3.74 / -0.45 | +8.41 / +0.31 | +16.62 / -0.00 |
| 0.2 | +2.48 / +4.89 | -0.14 / -0.44 | +3.52 / -0.45 | +8.00 / +0.31 | +16.62 / -0.00 |
| 0.225 | +2.03 / +4.89 | -0.59 / -0.44 | +4.14 / -0.45 | +7.38 / +0.31 | +17.52 / +0.00 |
| 0.25 | +3.60 / +5.40 | +0.70 / +4.00 | +4.83 / +2.65 | +6.68 / +1.14 | +21.41 / +2.09 |
| 0.275 | +2.84 / +8.09 | -0.02 / +3.76 | +2.69 / +2.65 | +4.13 / +1.14 | +12.06 / +2.09 |
| 0.3 | -0.04 / +6.25 | -2.67 / +4.82 | -1.17 / +3.24 | -1.71 / +0.85 | +13.41 / +2.87 |
| 0.325 | -0.25 / +6.25 | -3.16 / +5.43 | -2.51 / +4.66 | -5.24 / +1.32 | +14.05 / +3.98 |
| 0.35 | -0.31 / +5.65 | -3.84 / +4.82 | -1.60 / +4.66 | -6.31 / +1.13 | +16.14 / +2.81 |
| 0.375 | -3.41 / +4.85 | -7.78 / -1.12 | -9.04 / -2.81 | -18.04 / -6.35 | +3.33 / -2.96 |
| 0.4 | -5.62 / +3.14 | -9.41 / -2.84 | -12.76 / -4.54 | -23.35 / -8.08 | -1.07 / -1.60 |
| 0.45 | -8.78 / -0.94 | -12.40 / -6.93 | -16.73 / -8.62 | -28.65 / -12.16 | +0.33 / -0.95 |
| 0.5 | -13.59 / +0.62 | -15.51 / -5.37 | -18.95 / -7.07 | -29.81 / -10.61 | +6.34 / +1.10 |
| 0.6 | -13.88 / -1.58 | -15.71 / -1.63 | -16.63 / +3.38 | -29.03 / +2.84 | +1.89 / +2.71 |
| 0.7 | -21.33 / -14.78 | -25.62 / -9.76 | -26.26 / +5.06 | -44.05 / +1.52 | -19.00 / +1.21 |
| 0.8 | -26.91 / -10.41 | -33.62 / -7.19 | -42.88 / -1.97 | -64.04 / -5.51 | -43.73 / +1.82 |
| 0.9 | -27.88 / +7.80 | -34.76 / +4.78 | -50.89 / +3.18 | -63.91 / +3.95 | -41.12 / +11.07 |

## Stability Classification

- narrow_stable under the strict predeclared criterion: only.250 and.275 pass. Do not call the entire visually favorable range fully validated.
- Low thresholds0,.01,.025 are identical to off in displayed metrics and daily return/NAV/position/turnover. .05 affects Full slightly, with trailing windows essentially unchanged.
- The broader.125-.275 region has useful return/DD tradeoffs conditional on floor0.5, but.150-.225 slightly worsens10Y/5Y DD and does not satisfy the >=3-window DD-improvement rule.
- .250 beats branch baseline on all5 annual returns and all5 drawdowns. .275 improves all5 drawdowns and4 annual returns;10Y CAGR is lower by only.02pp.
- Neighbor support remains bounded: .225 and.300 do not pass strict criterion. .300-.350 retains lower DD but sacrifices longer-window return; .375+ mostly degrades.
- This is interaction evidence, not a reason to infer score-floor0.5 is free of overfit. The same data has been repeatedly scanned; windows overlap; no independent OOS.
- No R2 window, recency weight, lookback, pool or cost sensitivity scan performed.

## Decision

- watchlist only for the requested conditional branch; .250 and.275 merit observation, not automatic adoption.
- Original no-floor/R2-off research mainline unchanged. Production and shared decision docs unchanged.
- Stop after displaying this result; no further parameter scan without confirmation.

## User-Facing Summary

在0.5<Score<5条件下，R2低阈值几乎重复已有过滤；0.25及0.275在本次预设多窗口规则下通过，其中0.25五窗口收益和回撤均改善。仅为条件分支展示，不代表重新接受0.5门槛或证明该组合没有过拟合。

## Finalization

- Finalized at: 2026-09-04T11:33:08+08:00
- Decision: watchlist
- Stability label: narrow_stable
- Complete checker: PASS
