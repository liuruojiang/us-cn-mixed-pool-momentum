# Quant Parameter Scan Record

## Run Metadata

- Run id: `20260523_mixed_us_cn_momentum_subd_v1_1_six_etf_mixed_pool_target_vol_scale_rebalance_threshold`
- Project: mixed-us-cn-momentum
- Strategy or version: SubD V1.1
- Sleeve or subsystem: six-etf mixed pool
- Parameter group: `target_vol_scale_rebalance_threshold`
- Scan type: threshold_grid_on_official_v11_daily_artifact
- Repo or workspace path: `C:\Users\Administrator.DESKTOP-95I7VVU\Desktop\动量策略\美股A股混合池子动量策略`
- Target entrypoint: `run_subd_six_etf_v1_1.py`
- Git branch: `main`
- Git commit: `d255aeb7a118e9a735572f5dc03223277e9ba0a3`

## Research Question

- Baseline: current SubD V1.1 target-vol scale has no rebalance threshold.
- Candidate grid: `0.000, 0.005, 0.010, 0.020, 0.030, 0.050, 0.075, 0.100`.
- Decision target: check whether a target-vol scale rebalance threshold changes recent annualized returns and max drawdowns.
- Required focus windows: last_5y, last_3y, last_1y.

## Implementation Anchor

- Official daily artifact: `outputs/subd_six_etf_v1_1_20260509_daily.csv`.
- Official recompute function reused: `run_subd_six_etf_v1_1._recompute_final_exposure_nav(...)`.
- Threshold rule: update confirmed target-vol scale only when `abs(raw_next_scale - last_confirmed_scale) >= threshold`; threshold `0` is the current continuous baseline.
- Cost model: repo one-way turnover cost `0.001`; no extra open-impact or financing model.
- Execution timing: target-vol scale remains one day shifted before affecting return.

## Data Snapshot

- Daily artifact rows used: 3496
- Date range: 2011-12-09 to 2026-05-08
- Artifact SHA256: `de93712c8d46786527345e38ef0261c5bcd719c11766e7672b5e35d83c70f8c8`
- Adjustment/source mode: inherits official artifact; prior run recorded raw/unadjusted Sina daily close.

## Recent Window Results

| candidate    |   SCALE_THRESHOLD |   ann_return_last_5y |   max_dd_last_5y |   ann_return_last_3y |   max_dd_last_3y |   ann_return_last_1y |   max_dd_last_1y |   scale_rebalance_days_last_5y |   scale_rebalance_days_last_3y |   scale_rebalance_days_last_1y |
|:-------------|------------------:|---------------------:|-----------------:|---------------------:|-----------------:|---------------------:|-----------------:|-------------------------------:|-------------------------------:|-------------------------------:|
| th_0_current |          0.000000 |             0.614261 |        -0.180541 |             0.990112 |        -0.165506 |             0.927361 |        -0.127513 |                           1260 |                            756 |                            252 |
| th_0p005     |          0.005000 |             0.614667 |        -0.180547 |             0.991049 |        -0.165496 |             0.928081 |        -0.127557 |                            460 |                            257 |                            111 |
| th_0p01      |          0.010000 |             0.614878 |        -0.180359 |             0.990827 |        -0.165136 |             0.925182 |        -0.127546 |                            315 |                            184 |                             80 |
| th_0p02      |          0.020000 |             0.614382 |        -0.180035 |             0.992012 |        -0.165012 |             0.929064 |        -0.127597 |                            194 |                            115 |                             47 |
| th_0p03      |          0.030000 |             0.614793 |        -0.180826 |             0.994863 |        -0.165299 |             0.937782 |        -0.127429 |                            132 |                             78 |                             30 |
| th_0p05      |          0.050000 |             0.617425 |        -0.179995 |             0.991315 |        -0.164193 |             0.931316 |        -0.128573 |                             79 |                             49 |                             15 |
| th_0p075     |          0.075000 |             0.623896 |        -0.180994 |             1.008048 |        -0.162956 |             0.944062 |        -0.128573 |                             53 |                             32 |                             13 |
| th_0p1       |          0.100000 |             0.617373 |        -0.183451 |             0.987762 |        -0.162956 |             0.926822 |        -0.128573 |                             34 |                             21 |                              4 |

## Decision

- Decision: `threshold_0p02_or_0p03_reasonable_operational_filter`.
- Interpretation: recent return and drawdown barely move from adding a small threshold, while scale rebalance days fall materially.
- Suggested next action: use `0.02` as the first production candidate; `0.03` is also defensible if the priority is fewer resize trades.

## Stability

- Stability label: `recent_windows_low_metric_drift`.
- Evidence: `0.02` and `0.03` keep 5Y/3Y/1Y annualized return and max drawdown very close to the no-threshold baseline while reducing scale rebalance days sharply.
- Caveat: this scan reuses the official daily artifact ending 2026-05-08 and does not add open-impact or financing sensitivity.

## Commands

```powershell
python .\quant_param_scan_runs\20260523_mixed_us_cn_momentum_subd_v1_1_six_etf_mixed_pool_target_vol_scale_rebalance_threshold\run_scan.py
```

- Runtime seconds: 1.96

## Finalization

- Finalized at: 2026-05-23T02:07:47+08:00
- Decision: threshold_0p02_or_0p03_reasonable_operational_filter
- Stability label: recent_windows_low_metric_drift
- Complete checker: FAIL
- Checker errors:
  - record.md missing required marker: stability

## Finalization

- Finalized at: 2026-05-23T02:08:16+08:00
- Decision: threshold_0p02_or_0p03_reasonable_operational_filter
- Stability label: recent_windows_low_metric_drift
- Complete checker: PASS
