# Large Artifact Cleanup Record - 2026-05-22

## Scope

This cleanup removed oversized reproducible scan-level `daily_curves.csv` files before syncing the workspace to GitHub. Two of these files exceeded GitHub's single-file upload limit, and the rest were row-level curve exports that would materially bloat the repository. It did not change strategy code, parameter defaults, scan summaries, source manifests, or user-facing research conclusions.

## Backup

Before deletion, the files were backed up to:

```text
.codex_backups/20260522_010334
.codex_backups/20260522_010517
```

## Removed Files

```text
quant_param_scan_runs/20260516_subd_v11_per_asset_score_gate_exemptions/daily_curves.csv
docs/gn_20260516/artifacts/scans/us_switch_frictionless_raw/daily_curves.csv
docs/gn_20260516/artifacts/scans/cn_switch_coarse/daily_curves.csv
docs/gn_20260516/artifacts/scans/us_r2_02_tv_grid/daily_curves.csv
docs/gn_20260516/artifacts/scans/us_r2_03_tv_grid/daily_curves.csv
docs/gn_20260516/artifacts/scans/us_r2_raw/daily_curves.csv
docs/gn_20260516/artifacts/scans/us_r2_tv/daily_curves.csv
docs/gn_20260516/artifacts/scans/us_switch_cost_raw/daily_curves.csv
docs/gn_20260516/artifacts/scans/us_switch_cost_score0to5/daily_curves.csv
quant_param_scan_runs/20260516_subd_v11_per_asset_score_cap_values/daily_curves.csv
quant_param_scan_runs/20260516_subd_v11_score_min_positive_values/daily_curves.csv
quant_param_scan_runs/20260516_subd_v11_score_min_values/daily_curves.csv
quant_param_scan_runs/20260521_subd_v11_target_vol/daily_curves.csv
```

## Preserved Evidence

For both scan folders, the durable evidence remains:

- `command_log.txt`
- `record.md`
- `scan_meta.json`
- `scan_summary.csv`
- `selection.csv` where present
- `sources.csv`
- `window_metrics.csv`

The removed files were row-level curve exports. They were not required for the documented conclusions and were too large or too noisy to sync to GitHub without Git LFS.
