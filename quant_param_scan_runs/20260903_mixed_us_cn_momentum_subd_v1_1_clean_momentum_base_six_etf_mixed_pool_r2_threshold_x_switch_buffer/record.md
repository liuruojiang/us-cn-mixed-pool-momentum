# Quant Parameter Scan Record

## Run Metadata

- Run id: `20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer`
- Created at: 2026-09-03T20:58:20+08:00
- Project: mixed-us-cn-momentum
- Strategy or version: SubD V1.1 clean momentum base
- Sleeve or subsystem: six-etf mixed pool
- Parameter group: `R2_THRESHOLD x SWITCH_BUFFER`
- Scan type: `two_parameter_grid`
- Repo or workspace path: `D:\动量策略\美股A股混合池子动量策略`
- Target entrypoint: `run_subd_six_etf_v1_1.py`
- Git branch: `codex/previous-research-sync-20260821`
- Git commit: `6bf19204abca54f5ff7d15ec1708cf03a0412669`
- Working tree status before:

```text

```

## Research Question

- Baseline: `R2 off / Switch Buffer 1.00`, namely the 25-day weighted-log-slope Top1 momentum base with transaction costs only.
- Candidate grid: `R2 = off / 0.10 / 0.15 / 0.20 / 0.25 / 0.30 / 0.40 / 0.50`; `Switch Buffer = 1.00 / 1.02 / 1.03 / 1.05 / 1.08 / 1.10 / 1.15 / 1.20`.
- Decision target: isolate the marginal value and overfitting risk of R2 and Switch Buffer before any V1.1 simplification decision.
- Source-change rule: `research_only_no_source_change`
- Required windows: full, 10Y, 5Y, 3Y, 1Y
- Required metrics: annual return, annualized volatility, Sharpe, max drawdown, and strategy-specific exposure/cost metrics
- Promotion threshold: no automatic promotion; require multi-window consistency and a broad neighboring plateau after costs. A single-point return peak is insufficient.
- Rerun triggers: source/alignment failure, official-engine parity failure, missing required window, or any change to the frozen base/cost/execution assumptions.

## Implementation Anchor

- Official entrypoint: `run_subd_six_etf_v1_1.py`
- Function or command path: `poe_subd_six_etf_v1_1_bot.load_close` -> `run_subd_six_etf_v1_1.align_prices_to_common_valid_date` -> `run_subd_six_etf_v1_1.run_staged_entry(mode=full_entry)`; no overlays applied.
- Existing loaders reused: formal qfq loader with per-asset validated fallback from the current Poe V1.1 surface.
- Existing metrics reused: repo trading-day/window and wealth/max-drawdown conventions.
- Default values and source locations: `research_subd_six_etf_weighted_slope.py` and `run_subd_six_etf_v1_1.py`.

| parameter | default | source location |
| --- | ---: | --- |
| `LOOKBACK` | 25 | `research_subd_six_etf_weighted_slope.py` |
| `SCORE_MIN / SCORE_MAX` | 0.0 / 5.0 | `research_subd_six_etf_weighted_slope.py` |
| `R2_THRESHOLD` | 0.20 | `run_subd_six_etf_v1_1.py` |
| `SWITCH_BUFFER` | 1.05 | `run_subd_six_etf_v1_1.py` |
| `ONE_WAY_COST` | 0.001 | `run_subd_six_etf_v1_1.py` |

## Data Snapshot

- Run timestamp: 2026-09-03 20:58-21:21 Asia/Shanghai; measured scan runtime 1,030.196 seconds.
- Raw data start: 2011-12-09.
- Raw data end: 2026-09-02 after matched-date clipping.
- Metrics start after warmup: score first becomes eligible on 2012-01-16; the formal full window starts 2011-12-09 and retains the preceding cash warmup rows.
- Metrics end: 2026-09-02.
- Latest trading date or snapshot: 2026-09-02.
- Data sources: Tencent qfq for all six ETFs; the current loader reports three series as cross-validated against Eastmoney qfq through 2026-08-07.
- Local cache paths: `outputs/cn_trading_days_cache.csv`; frozen scan input copied to `price_snapshot_qfq.csv.gz` with SHA256 `0cc4af45158d6aaab4594b869b79309a96e8e3cc2f21a0205c38128913bec2aa`.
- Cache write risk: the official trading-calendar loader may refresh the repo-local calendar cache; the price snapshot and result artifacts are isolated in this run folder.
- Missing or stale data: before matching, `159915.SZ` ended on 2026-09-02 while the other five ended on 2026-09-03. The complete panel was clipped to 2026-09-02; no 2026-09-03 forward-filled price was traded.
- Alignment rules: required China-session validation and same matched end date for all assets; historical pre-inception values remain missing, so the investable cross-section expands as ETFs launch.
- Adjustment mode: qfq/front-adjusted only; raw prices are not allowed.
- Trading calendar: China trading-day calendar required.
- Timezone assumptions: Asia/Shanghai; daily close-confirmed research path.

## Cost and Execution Assumptions

- Commission: represented by the frozen aggregate one-way cost below.
- Slippage: represented by the frozen aggregate one-way cost below.
- Open-impact: none separately; no open execution is modeled.
- Financing: none; leverage disabled.
- Borrow or shorting cost: none; long/cash strategy only.
- Rebalance timing: daily, after the close-confirmed score.
- Fill timing: close execution convention; new position earns return from the next row.
- Leverage or sizing rules: full-entry 0/1 exposure only; target-vol and leverage overlays disabled.
- Hedge assumptions: no hedge.

## Runtime Override Plan

- Override mechanism: function arguments only; no production constant or source edit.
- Values restored after each candidate: not applicable because candidates are immutable function arguments.
- Default candidate included in same run: yes, current pair `R2 0.20 / Buffer 1.05`, but on the stripped momentum base.
- Parity check against official/default output: compare the runner and Poe implementations for the stripped current pair.
- If parity check failed, explanation: not applicable; runner/Poe maximum absolute daily-return difference and NAV difference were both exactly 0.

## Commands

```powershell
python -X utf8 quant_param_scan_runs\20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer\run_scan.py
```

## Output Files

- `scan_summary.csv`: 320 rows = 64 candidates x 5 required windows.
- `window_metrics.csv`: 64-row wide comparison with baseline/current-pair deltas.
- `scan_meta.json`: this run metadata
- `command_log.txt`: initialization, failure boundary, matched-date action, and scan command.
- `daily_outputs/`: four core combinations with daily NAV/return/position/turnover.
- `parity_checks.csv`: runner/Poe daily parity for `R2 0.20 / Buffer 1.05` on the stripped base.
- `price_snapshot_qfq.csv.gz`: frozen matched qfq input.
- `source_snapshot.csv`: per-asset source provenance and original last dates.

## Full-Sample Results

| candidate | annual return | max drawdown | Sharpe | turnover total | holding ratio |
| --- | ---: | ---: | ---: | ---: | ---: |
| R2 off / Buffer 1.00 | 23.05% | -36.47% | 0.972 | 691 | 89.44% |
| R2 0.20 / Buffer 1.00 | 29.46% | -24.40% | 1.263 | 653 | 79.26% |
| R2 off / Buffer 1.05 | 23.32% | -36.83% | 0.982 | 677 | 89.44% |
| R2 0.20 / Buffer 1.05 | 29.68% | -24.97% | 1.271 | 641 | 79.26% |
| R2 0.25 / Buffer 1.05 | 31.21% | -26.69% | 1.341 | 641 | 77.45% |

The full grid is in `scan_summary.csv`. At Buffer 1.00, R2 thresholds 0.15/0.20/0.25/0.30 produced 27.55%/29.46%/30.91%/26.40% annual returns, versus 23.05% with R2 off. Thresholds 0.40 and 0.50 degraded to 19.49% and 12.15%.

## Window Results

Annual return / max drawdown:

| candidate | Full | 10Y | 5Y | 3Y | 1Y |
| --- | ---: | ---: | ---: | ---: | ---: |
| R2 off / Buffer 1.00 | 23.05% / -36.47% | 34.17% / -21.48% | 48.40% / -21.48% | 61.05% / -17.18% | 33.36% / -17.18% |
| R2 0.20 / Buffer 1.00 | 29.46% / -24.40% | 34.28% / -21.83% | 53.36% / -21.83% | 68.20% / -15.87% | 52.73% / -15.87% |
| R2 off / Buffer 1.05 | 23.32% / -36.83% | 34.52% / -22.97% | 49.12% / -22.97% | 62.58% / -16.92% | 34.05% / -16.92% |
| R2 0.20 / Buffer 1.05 | 29.68% / -24.97% | 34.55% / -23.32% | 53.44% / -23.32% | 68.58% / -15.87% | 53.51% / -15.87% |
| R2 0.25 / Buffer 1.05 | 31.21% / -26.69% | 36.44% / -19.47% | 58.27% / -19.47% | 72.35% / -15.20% | 73.82% / -13.77% |

`R2 0.25 / Buffer 1.05` was the return and Sharpe winner in all five nested windows. Because the recent windows overlap, this is supporting evidence rather than independent five-fold confirmation.

## Stability Classification

- Label: `narrow_stable` overall. The R2 feature has a broad useful region, while the exact 0.25 threshold and the small Buffer edge still require out-of-sample confirmation.
- Evidence: R2 0.15-0.30 beats R2-off full-sample return at Buffer 1.00; 0.20 and 0.25 also materially improve drawdown. The best point is not isolated, but performance falls sharply by R2 0.40/0.50.
- Nearby-candidate behavior: Buffer 1.02/1.03/1.05 forms a shallow return plateau. At R2 0.25, their full returns are 31.02%/31.13%/31.21%; Buffer 1.08 and above starts to degrade.
- Recent-window behavior: R2 0.25 / Buffer 1.05 wins all required windows, but its 1Y advantage over R2 0.20 is unusually large (+20.31 percentage points), so the exact threshold may be benefiting from the current regime.
- Cost sensitivity: only the frozen 0.10% one-way cost was tested. At R2 0.20, Buffer 1.05 saves 12 turnover units versus Buffer 1.00 but adds only 0.22 percentage points of full-sample annual return and worsens full max drawdown by 0.58 percentage points.
- Data sensitivity: qfq provider provenance is recorded. ETF inception dates are staggered, and the latest matched date was clipped to 2026-09-02 because one series lagged one session.
- Leverage or exposure caveat: no leverage, target-vol sizing, staged entry, stop/cooldown, or overheat layer is present; results must not be compared directly with the complete V1.1 headline curve.

## Decision

- Decision: `watchlist`. R2 should not be removed in the first simplification pass; its feature-level benefit is material and supported across a 0.15-0.30 neighborhood. Switch Buffer has much weaker marginal value and is the cleaner removal candidate.
- Recommended next action: use `R2 0.20 / Buffer 1.00` as the conservative simplification candidate, then test it against the complete V1.1 stack under matched ablations. Keep `R2 0.25` as a research challenger, not a new default, until non-overlapping or walk-forward evidence is added.

## User-Facing Summary

With every other layer disabled, R2 is doing real defensive work; Switch Buffer is mostly a small turnover tweak. The exact best pair (`0.25 / 1.05`) is promising but not sufficient to promote because the recent-period contribution is large and all required windows share the same endpoint. No production source was changed.

## Finalization

- Finalized at: 2026-09-03T21:24:47+08:00
- Decision: watchlist
- Stability label: narrow_stable
- Complete checker: PASS
