# Sub-D V1.1 Test-File Cleanup Record - 2026-05-16

## Scope

This cleanup removed temporary root-level research/test runner scripts created or left as loose workspace files during Sub-D V1.1 parameter testing. It did not change production strategy logic.

Preserved:

- Formal strategy/runtime files, including `research_subd_six_etf_weighted_slope.py`, `run_subd_six_etf_v1_1.py`, and `poe_subd_six_etf_v1_1_bot.py`.
- Existing docs under `docs/`.
- Research outputs under `outputs/`.
- Structured scan artifacts under `quant_param_scan_runs/`.
- Backups under `.codex_backups/`.

## Backup

Before deletion, all cleanup targets were backed up to:

```text
.codex_backups/20260516_230855
```

The backup contains the removed scripts, the removed `__pycache__` directory, and a `manifest.json`.

## Removed Files

Removed root-level temporary scripts:

```text
analyze_lookback_half_life_grid_20260511.py
analyze_r2_threshold_scan_20260511.py
analyze_score_cap_alternatives_20260511.py
analyze_score_gate_cap_values_20260516.py
analyze_score_gate_exemptions_20260516.py
analyze_score_gate_min_positive_values_20260516.py
analyze_score_gate_min_values_20260516.py
analyze_score_max_veto_robustness_20260511.py
analyze_score_transform_variants_20260511.py
analyze_soymeal_etf_futures_correlation_20260510.py
analyze_subd_v11_1_2_switch_entry_20260511.py
analyze_subd_v11_1_3_overheat_20260511.py
analyze_subd_v11_1_4_target_vol_20260511.py
analyze_subd_v11_30y_bond_expansion_20260510.py
analyze_subd_v11_csi2000_expansion_20260510.py
analyze_subd_v11_pool_expansion_20260510.py
analyze_subd_v11_remove_soymeal_20260510.py
analyze_subd_v11_signal_jitter_20260510.py
analyze_subd_v11_switch_buffer_fine_scan_20260510.py
analyze_subd_v11_us_etf_pool_20260515.py
analyze_weighted_log_slope_diagnostics_20260511.py
analyze_weighting_half_life_platform_20260511.py
analyze_weighting_half_life_scan_20260511.py
```

Removed generated cache:

```text
__pycache__/
```

## Preserved Evidence

The cleanup intentionally kept the reproducible scan records and result artifacts:

```text
quant_param_scan_runs/20260516_subd_v11_per_asset_score_gate_exemptions/
quant_param_scan_runs/20260516_subd_v11_per_asset_score_cap_values/
quant_param_scan_runs/20260516_subd_v11_score_min_values/
quant_param_scan_runs/20260516_subd_v11_score_min_positive_values/
```

Key recent scan conclusions preserved in those folders:

- Per-asset score upper-bound exemption test.
- Per-asset score upper-bound value scan.
- Negative score lower-bound scan.
- Positive score lower-bound scan over `0..5`.

## Verification

Commands run:

```powershell
git status --short
python C:\Users\Administrator.DESKTOP-95I7VVU\.codex\skills\quant-research\scripts\backup_paths.py --root . <cleanup-targets>
Remove-Item -LiteralPath <verified-workspace-targets> -Recurse -Force
```

Post-cleanup observation:

- No `tests/` directory existed before cleanup.
- Root-level loose `analyze_*.py` temporary scripts listed above were removed.
- Result directories and output CSV/JSON/PNG artifacts were preserved.
