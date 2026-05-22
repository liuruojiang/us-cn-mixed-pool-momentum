# Quant Parameter Scan Record

## Run Metadata

- Run id: `20260523_mixed_us_cn_momentum_subd_v1_1_six_etf_mixed_pool_target_vol_scale_rebalance_threshold_fine_0p05_0p10`
- Project: mixed-us-cn-momentum
- Strategy or version: SubD V1.1
- Sleeve or subsystem: six-etf mixed pool
- Parameter group: `target_vol_scale_rebalance_threshold_fine_0p05_0p10`
- Scan type: fine_threshold_grid_on_official_v11_daily_artifact
- Repo or workspace path: `C:\Users\Administrator.DESKTOP-95I7VVU\Desktop\动量策略\美股A股混合池子动量策略`
- Target entrypoint: `run_subd_six_etf_v1_1.py`
- Git branch: `main`
- Git commit: `d255aeb7a118e9a735572f5dc03223277e9ba0a3`

## Research Question

- Baseline: threshold `0` is current no-threshold behavior.
- Candidate grid: `0.000, 0.050, 0.055, 0.060, 0.065, 0.070, 0.075, 0.080, 0.085, 0.090, 0.095, 0.100`.
- Decision target: find a threshold above `0.05` that cuts five-year resize count below roughly 100 without damaging 5Y/3Y/1Y return and max drawdown.

## Implementation Anchor

- Official daily artifact: `outputs/subd_six_etf_v1_1_20260509_daily.csv`.
- Official recompute function reused through the coarse scan helper: `run_subd_six_etf_v1_1._recompute_final_exposure_nav(...)`.
- Threshold rule: update confirmed target-vol scale only when `abs(raw_next_scale - last_confirmed_scale) >= threshold`.
- Cost model: one-way turnover cost `0.001`; no extra open-impact or financing sensitivity.
- Execution timing: target-vol scale remains one day shifted before affecting return.

## Data Snapshot

- Daily artifact rows used: 3496
- Date range: 2011-12-09 to 2026-05-08
- Artifact SHA256: `de93712c8d46786527345e38ef0261c5bcd719c11766e7672b5e35d83c70f8c8`

## Recent Window Results

| candidate    |   SCALE_THRESHOLD |   ann_return_last_5y |   max_dd_last_5y |   ann_return_last_3y |   max_dd_last_3y |   ann_return_last_1y |   max_dd_last_1y |   scale_rebalance_days_last_5y |   scale_rebalance_days_last_3y |   scale_rebalance_days_last_1y |   cost_total_last_5y |
|:-------------|------------------:|---------------------:|-----------------:|---------------------:|-----------------:|---------------------:|-----------------:|-------------------------------:|-------------------------------:|-------------------------------:|---------------------:|
| th_0_current |          0.000000 |             0.614261 |        -0.180541 |             0.990112 |        -0.165506 |             0.927361 |        -0.127513 |                           1260 |                            756 |                            252 |             0.331259 |
| th_0p05      |          0.050000 |             0.617425 |        -0.179995 |             0.991315 |        -0.164193 |             0.931316 |        -0.128573 |                             79 |                             49 |                             15 |             0.328662 |
| th_0p055     |          0.055000 |             0.616499 |        -0.181016 |             0.993546 |        -0.164023 |             0.931285 |        -0.128573 |                             78 |                             49 |                             16 |             0.328142 |
| th_0p06      |          0.060000 |             0.615513 |        -0.180857 |             0.996375 |        -0.164023 |             0.943924 |        -0.128573 |                             68 |                             42 |                             11 |             0.327359 |
| th_0p065     |          0.065000 |             0.617143 |        -0.180877 |             0.996264 |        -0.164023 |             0.934930 |        -0.128573 |                             62 |                             40 |                             11 |             0.327506 |
| th_0p07      |          0.070000 |             0.621195 |        -0.180749 |             1.003713 |        -0.159978 |             0.932102 |        -0.128573 |                             58 |                             35 |                             11 |             0.327615 |
| th_0p075     |          0.075000 |             0.623896 |        -0.180994 |             1.008048 |        -0.162956 |             0.944062 |        -0.128573 |                             53 |                             32 |                             13 |             0.328154 |
| th_0p08      |          0.080000 |             0.622916 |        -0.181962 |             1.010011 |        -0.159879 |             0.944314 |        -0.128573 |                             47 |                             31 |                             12 |             0.325213 |
| th_0p085     |          0.085000 |             0.621230 |        -0.182973 |             1.006264 |        -0.162956 |             0.948937 |        -0.128573 |                             43 |                             27 |                              9 |             0.326474 |
| th_0p09      |          0.090000 |             0.619914 |        -0.184790 |             1.003522 |        -0.162956 |             0.965968 |        -0.128573 |                             38 |                             25 |                              8 |             0.327344 |
| th_0p095     |          0.095000 |             0.611921 |        -0.184790 |             0.988002 |        -0.162956 |             0.926822 |        -0.128573 |                             34 |                             21 |                              4 |             0.326756 |
| th_0p1       |          0.100000 |             0.617373 |        -0.183451 |             0.987762 |        -0.162956 |             0.926822 |        -0.128573 |                             34 |                             21 |                              4 |             0.326574 |

## Stability

- Stability label: `fine_recent_window_tradeoff`.
- Evidence: the `0.055` to `0.085` band keeps recent return/drawdown close to or better than the current baseline while reducing five-year scale rebalance days from 1260 to double digits.
- Caveat: this is an artifact-based scan ending 2026-05-08 and still lacks separate open-impact / financing sensitivity.

## Decision

- Decision: `prefer_0p075_if_resize_count_priority_else_0p055`.
- Interpretation: `0.055` already brings five-year scale rebalance days under 100; `0.075` gives a stronger reduction and still has the best recent-window profile in this grid.
- Suggested next action: if the execution objective is clearly to avoid 100+ five-year resize events, promote `0.075` as the next implementation candidate; use `0.055` only if you want the smallest change from the earlier `0.05` area.

## Commands

```powershell
python .\quant_param_scan_runs\20260523_mixed_us_cn_momentum_subd_v1_1_six_etf_mixed_pool_target_vol_scale_rebalance_threshold_fine_0p05_0p10\run_scan.py
```

- Runtime seconds: 4.73

## Finalization

- Finalized at: 2026-05-23T02:16:29+08:00
- Decision: prefer_0p075_if_resize_count_priority_else_0p055
- Stability label: fine_recent_window_tradeoff
- Complete checker: PASS
