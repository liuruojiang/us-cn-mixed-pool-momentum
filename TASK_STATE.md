# Task State

## Goal

Optimize Strategy D / SubD V1.1 target volatility and max leverage using the real mixed US/A-share six-ETF weighted-slope code path.

## Key Paths

- Entrypoint: `run_subd_six_etf_v1_1.py`
- Base research module: `research_subd_six_etf_weighted_slope.py`
- Prior target-vol scan: `quant_param_scan_runs/20260521_subd_v11_target_vol`
- Planned run folder: `quant_param_scan_runs/20260529_subd_v11_target_vol_max_lev`

## Assumptions

- Strategy D means the mixed-pool Sub-D / six-ETF weighted-slope V1.1 path.
- This is research-only; do not change production parameters unless explicitly requested.
- Use the same data slice, cost model, staged-entry rule, MA60 overheat overlay, and close-to-close execution timing as the official V1.1 runner.

## Next Steps

1. Inspect the official target-vol and max-leverage consumers.
2. Completed target-vol by max-leverage grid scan from the official V1.1 path.
3. Saved `scan_summary.csv`, `window_metrics.csv`, `scan_meta.json`, `record.md`, and `command_log.txt`.
4. Strict artifact check passed; recommendation is `TARGET_VOL = 0.30`, `MAX_LEV = 1.0` for risk-adjusted/default use, with `0.25/1.5` as leveraged balanced alternative.

## Verification Commands

```powershell
python .\quant_param_scan_runs\20260529_subd_v11_target_vol_max_lev\run_scan.py
python C:\Users\Administrator.DESKTOP-95I7VVU\.codex\skills\quant-param-scan\scripts\check_quant_param_scan_artifacts.py --phase complete --strict .\quant_param_scan_runs\20260529_subd_v11_target_vol_max_lev
```
