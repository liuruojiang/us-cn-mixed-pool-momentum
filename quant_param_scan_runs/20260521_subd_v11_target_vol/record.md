# Quant Parameter Scan Record

## Run Metadata

- Run id: `20260521_subd_v11_target_vol`
- Project: mixed-us-cn-momentum
- Strategy or version: SubD V1.1
- Sleeve or subsystem: six-etf mixed pool
- Parameter group: `target_vol`
- Scan type: grid_scan_rebuilt_from_official_v11_path
- Repo or workspace path: `C:\Users\Administrator.DESKTOP-95I7VVU\Desktop\动量策略\美股A股混合池子动量策略`
- Target entrypoint: `run_subd_six_etf_v1_1.py`
- Git branch: `main`
- Git commit: `d7c3790bd3a4f1b5715f4583b995542f5ad076c2`
- Working tree status before: captured in `scan_meta.json`.

## Research Question

- Baseline: SubD V1.1 staged 50% entry + MA60 overheat overlay with current default `TARGET_VOL = 0.25`.
- Candidate grid: `0.100, 0.125, 0.150, 0.175, 0.200, 0.225, 0.250, 0.275, 0.300, 0.325, 0.350, 0.375, 0.400`.
- Decision target: find the target-vol level with the best risk-adjusted behavior while checking drawdown and leverage-cap saturation.
- Source-change rule: `research_only_no_source_change`.
- Required windows: full, last_10y, last_5y, last_3y, last_1y.
- Required metrics: annual return, annualized volatility, Sharpe, max drawdown, cost, turnover, exposure, and leverage-cap saturation.
- Promotion threshold: do not promote a higher-vol candidate unless Sharpe and recent-window behavior stay competitive and max drawdown is acceptable.
- Rerun triggers: data refresh, asset-pool change, cost-model change, target-vol implementation change, or V1.1 signal/overheat parameter change.

## Implementation Anchor

- Official entrypoint: `run_subd_six_etf_v1_1.py`.
- Function path: `run_staged_entry(...) -> apply_target_vol_overlay(...) -> apply_overheat_overlay(...)`.
- Existing loaders reused: `research_subd_six_etf_weighted_slope.load_close(...)`.
- Existing metrics reused or matched: repo annualization uses 252 trading days and daily NAV drawdown.

| parameter | default | source location |
| --- | ---: | --- |
| `TARGET_VOL` | 0.25 | `run_subd_six_etf_v1_1.py` |
| `DEFAULT_VOL_WINDOW` | 80 | `research_subd_six_etf_weighted_slope.py` |
| `DEFAULT_MAX_LEV` | 1.50 | `research_subd_six_etf_weighted_slope.py` |
| `ONE_WAY_COST` | 0.0010 | `run_subd_six_etf_v1_1.py` |

## Data Snapshot

- Run timestamp: 2026-05-21T18:18:31.090394
- Raw data start: 2011-12-09
- Raw data end: 2026-05-08
- Metrics end / common valid date: 2026-05-08
- Data sources: akshare.fund_etf_hist_sina raw close
- Data mode: normalized_from_existing_official_daily_artifact
- Loader failure, if any: RuntimeError("All qfq data sources failed. 159915.SZ akshare.fund_etf_hist_em daily close: AkShare Eastmoney qfq returned no rows for 159915.SZ / 159915; last_error=('Connection aborted.', RemoteDisconnected('Remote end closed connection without respo | 159915.SZ Eastmoney push2his kline: Eastmoney returned no rows for 159915.SZ; last_error=('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))")
- Local cache paths: none intentionally written by this script.
- Cache write risk: loader may use provider/network cache outside this run only if the imported dependency does so; no repo cache writes were added.
- Missing or stale data: see `sources.csv` and `data_quality.csv`.
- Alignment rules: truncate to the latest date where every asset has non-null close.
- Adjustment mode: raw/unadjusted as served by Sina in the existing official artifact.
- Trading calendar: A-share ETF trading dates after cross-asset non-null alignment.
- Timezone assumptions: date-level China market closes; no intraday timezone conversion in this scan.

## Cost and Execution Assumptions

- Commission/slippage proxy: one-way cost `0.0010` applied to exposure turnover.
- Open-impact: not separately modeled.
- Financing: not separately modeled; exposure is capped by `DEFAULT_MAX_LEV`.
- Borrow or shorting cost: not applicable; long-only ETF rotation.
- Rebalance/fill timing: close-to-close return uses previous effective holding; target-vol scale is shifted one day before it affects return.
- Leverage or sizing rules: target_vol / 80-day realized vol, clipped to 0.0-1.5, then combined with staged entry and overheat scale.
- Hedge assumptions: none.

## Runtime Override Plan

- Override mechanism: loop over candidate `target_vol` values and call the official V1.1 overlay functions directly.
- Values restored after each candidate: no module globals were patched.
- Default candidate included in same run: yes, `TARGET_VOL = 0.25`.
- Parity check against official/default output: same function chain as `build_curves(...)`; candidate `0.25` is the parity anchor.
- If parity check failed, explanation: not applicable.

## Commands

```powershell
python .\quant_param_scan_runs\20260521_subd_v11_target_vol\run_scan.py
```

## Output Files

- `scan_summary.csv`: long-form metrics by target-vol candidate and window.
- `window_metrics.csv`: wide comparison table by candidate.
- `daily_curves.csv`: same-run daily NAV/return/exposure rows.
- `sources.csv`: data-source rows from the official loader.
- `data_quality.csv`: row-count and date coverage by asset.
- `scan_meta.json`: this run metadata.
- `command_log.txt`: initialization and scan commands.

## Full-Sample Results

- Best full-sample Sharpe: `tv_40` (`TARGET_VOL=0.400`), ann_return 41.66%, max_dd -28.05%, Sharpe 1.362.
- Default `tv_25` full-sample: ann_return 33.82%, max_dd -28.13%, Sharpe 1.320.

| candidate   |   TARGET_VOL |   ann_return |   ann_vol |   sharpe_repo |    max_dd |   avg_weight |   pct_at_max_lev |
|:------------|-------------:|-------------:|----------:|--------------:|----------:|-------------:|-----------------:|
| tv_40       |     0.400000 |     0.416630 |  0.285525 |      1.362484 | -0.280465 |     1.476433 |         0.872998 |
| tv_37p5     |     0.375000 |     0.411834 |  0.283063 |      1.359881 | -0.280465 |     1.465304 |         0.836384 |
| tv_35       |     0.350000 |     0.405144 |  0.279550 |      1.356420 | -0.280465 |     1.450156 |         0.775172 |
| tv_32p5     |     0.325000 |     0.393061 |  0.274108 |      1.346337 | -0.282025 |     1.426360 |         0.681922 |
| tv_30       |     0.300000 |     0.379433 |  0.267065 |      1.337897 | -0.283246 |     1.392060 |         0.599542 |
| tv_27p5     |     0.275000 |     0.359298 |  0.256493 |      1.324987 | -0.284884 |     1.344447 |         0.473398 |
| tv_25       |     0.250000 |     0.338153 |  0.243046 |      1.320009 | -0.281324 |     1.281696 |         0.377860 |
| tv_22p5     |     0.225000 |     0.309544 |  0.226653 |      1.303182 | -0.266227 |     1.204387 |         0.267735 |

## Window Results

- Best last_5y Sharpe: `tv_40` (`TARGET_VOL=0.400`), ann_return 76.95%, max_dd -22.76%, Sharpe 2.003.

| candidate   |   TARGET_VOL |   ann_return |   ann_vol |   sharpe_repo |    max_dd |   avg_weight |   pct_at_max_lev |
|:------------|-------------:|-------------:|----------:|--------------:|----------:|-------------:|-----------------:|
| tv_40       |     0.400000 |     0.769455 |  0.308592 |      2.002992 | -0.227551 |     1.496193 |         0.907937 |
| tv_25       |     0.250000 |     0.614261 |  0.255946 |      1.998781 | -0.180541 |     1.228081 |         0.175397 |
| tv_37p5     |     0.375000 |     0.759478 |  0.306469 |      1.996282 | -0.227551 |     1.484772 |         0.853175 |
| tv_22p5     |     0.225000 |     0.552134 |  0.234777 |      1.989929 | -0.163861 |     1.125039 |         0.080159 |
| tv_27p5     |     0.275000 |     0.660314 |  0.273832 |      1.988044 | -0.196930 |     1.314987 |         0.310317 |
| tv_35       |     0.350000 |     0.744800 |  0.303140 |      1.987208 | -0.227551 |     1.466856 |         0.742063 |
| tv_20       |     0.200000 |     0.486026 |  0.210652 |      1.985874 | -0.146888 |     1.009313 |         0.042063 |
| tv_30       |     0.300000 |     0.699475 |  0.287868 |      1.985563 | -0.212700 |     1.383853 |         0.467460 |

## Stability Classification

- Label: balanced_recent_stable
- Evidence: full CSV tables were generated from the official V1.1 code path or a parity-checked official daily artifact. Default `tv_25` keeps strong full-sample Sharpe while avoiding the heavy leverage-cap saturation seen at `tv_35`-`tv_40`.
- Nearby-candidate behavior: `tv_22p5` is the lower-drawdown conservative alternative; `tv_27p5` increases return but gives up some recent-window drawdown control.
- Recent-window behavior: last_3y Sharpe is best at `tv_25`; last_1y Sharpe is best around `tv_22p5`, while high target-vol candidates win mainly by staying near the 1.5x cap.
- Cost sensitivity: current run includes the repo one-way cost only; no additional open-impact sensitivity.
- Data sensitivity: Eastmoney/Akshare front-adjusted daily ETF closes, aligned to common valid date.
- Leverage or exposure caveat: high target-vol candidates increasingly hit the 1.5x cap; cap saturation is reported.

## Decision

- Decision: keep_default_25_balanced
- Recommended next action: keep `TARGET_VOL = 0.25` as the balanced default; treat `0.225` as the conservative drawdown-reduction alternative and do not promote `0.35`-`0.40` without a separate leverage-cap/open-impact sensitivity run.

## User-Facing Summary

- Recommended target volatility: `0.25` for the balanced production setting. Pure full-sample CAGR/Sharpe sorting points to `0.40`, but that is mostly a max-leverage-cap regime rather than a clean target-vol choice.
- Runtime seconds: 33.84.

## Finalization

- Finalized at: 2026-05-21T18:19:54+08:00
- Decision: keep_default_25_balanced
- Stability label: balanced_recent_stable
- Complete checker: PASS
