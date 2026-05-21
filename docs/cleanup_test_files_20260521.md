# Sub-D V1.1 Test-File Cleanup Record - 2026-05-21

## Scope

This cleanup removed generated Python cache files left after the target-volatility scan and verification run. It did not change strategy code, scan outputs, docs, or production runtime files.

Preserved:

- Formal strategy/runtime files: `research_subd_six_etf_weighted_slope.py`, `run_subd_six_etf_v1_1.py`, `poe_subd_six_etf_v1_1_bot.py`.
- Current target-vol scan artifacts under `quant_param_scan_runs/20260521_subd_v11_target_vol/`, including `run_scan.py`, CSV outputs, `record.md`, and `scan_meta.json`.
- Existing `docs/`, `outputs/`, and `.codex_backups/` evidence.

## Backup

Before deletion, cleanup targets were backed up to:

```text
.codex_backups/20260521_182417
```

## Removed Paths

```text
__pycache__/
quant_param_scan_runs/20260521_subd_v11_target_vol/__pycache__/
```

## Verification

Commands run:

```powershell
python C:\Users\Administrator.DESKTOP-95I7VVU\.codex\skills\quant-research\scripts\backup_paths.py --root . '__pycache__' 'quant_param_scan_runs\20260521_subd_v11_target_vol\__pycache__'
Remove-Item -LiteralPath <verified-workspace-cache-paths> -Recurse -Force
git status --short
```

Post-cleanup observation:

- No root `__pycache__/` directory remains.
- No `__pycache__/` remains inside `quant_param_scan_runs/20260521_subd_v11_target_vol/`.
- Durable scan records and CSV outputs remain in place.
