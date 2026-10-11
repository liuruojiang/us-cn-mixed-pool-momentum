from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd

import research_subd_six_etf_weighted_slope as subd
import run_subd_proxy_dynamic_cyb_layer0 as layer0
import run_subd_proxy_dynamic_cyb_layer1_scan as layer1
import run_subd_proxy_dynamic_cyb_layer3_switch_buffer_scan as layer3
import run_subd_proxy_dynamic_cyb_layer4_staged_entry_scan as layer4
import run_subd_proxy_dynamic_cyb_layer7_nav_defense_scan as nav7
import run_subd_proxy_dynamic_cyb_r2none_layer4_staged_entry_scan as r2none_layer4
import run_subd_proxy_dynamic_cyb_r2none_layer5_target_vol_scan as r2none_layer5
import run_subd_proxy_dynamic_cyb_r2none_layer6_momentum_decay_scan as r2none_layer6
import run_subd_six_etf_v1_1 as v11


DEFAULT_START = pd.Timestamp("2007-01-01")
DEFAULT_END = pd.Timestamp("2016-12-30")
DEFAULT_RUN_FOLDER = Path(
    "quant_param_scan_runs"
    "/20260702_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_r2_removed_branch_layer7_nav_defense_after_r2_removed_no_decay"
)

LINE_GRID: tuple[tuple[int, float, float, str], ...] = (
    (28, 1.15, 0.25, "main_line_r2_removed"),
    (28, 1.15, 0.75, "return_watch_line_r2_removed"),
)
NAV_ENTER_THRESHOLDS = nav7.NAV_ENTER_THRESHOLDS
NAV_EXIT_THRESHOLDS = nav7.NAV_EXIT_THRESHOLDS
DEFENSE_SCALES = nav7.DEFENSE_SCALES
ONE_WAY_COST = 0.001
SEGMENTS = ("full", "last_10y", "last_5y", "last_3y", "last_1y")
R2_EXEC_THRESHOLD_FOR_REMOVED = 0.0


def git_value(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def pct(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value) * 100:.2f}%"


def fmt(value: object, digits: int = 2) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value):.{digits}f}"


def candidate_label(
    lookback: int,
    switch_buffer: float,
    entry_fraction: float,
    nav_enter: float | None,
    nav_exit: float | None,
    defense_scale: float | None,
) -> str:
    base = r2none_layer6.candidate_label(
        lookback,
        switch_buffer,
        entry_fraction,
        None,
        None,
        None,
        None,
    )
    return f"{base}_{nav7.nav_label(nav_enter, nav_exit, defense_scale)}"


def nav_grid() -> list[tuple[float | None, float | None, float | None]]:
    grid: list[tuple[float | None, float | None, float | None]] = [(None, None, None)]
    for enter in NAV_ENTER_THRESHOLDS:
        for exit_value in NAV_EXIT_THRESHOLDS:
            if exit_value >= enter:
                continue
            for scale in DEFENSE_SCALES:
                grid.append((float(enter), float(exit_value), float(scale)))
    return grid


def apply_nav_defense_layer(
    base_curve: pd.DataFrame,
    lookback: int,
    switch_buffer: float,
    entry_fraction: float,
    nav_enter: float | None,
    nav_exit: float | None,
    defense_scale: float | None,
    line_role: str,
    line_order: int,
) -> pd.DataFrame:
    enabled = nav_enter is not None
    curve = base_curve.copy()
    curve["return_before_nav_defense"] = curve["return"].astype(float).fillna(0.0)
    curve["nav_before_nav_defense"] = curve["nav"].astype(float)
    curve["nav_defense_base_dd"] = curve["nav_before_nav_defense"] / curve["nav_before_nav_defense"].cummax() - 1.0

    if enabled:
        gate = nav7.nav_defense_state(curve, float(nav_enter), float(nav_exit), float(defense_scale))
        score_effective = pd.to_numeric(
            curve.get("score_decay_multiplier_effective", pd.Series(1.0, index=curve.index)),
            errors="coerce",
        ).fillna(1.0)
        score_next = pd.to_numeric(
            curve.get("score_decay_multiplier_next", pd.Series(1.0, index=curve.index)),
            errors="coerce",
        ).fillna(1.0)
        combined_effective = score_effective * gate["nav_defense_scale_effective"]
        combined_next = score_next * gate["nav_defense_scale_next"]
        ones = pd.Series(1.0, index=curve.index, dtype=float)
        out = v11._recompute_final_exposure_nav(
            curve,
            ones,
            ones,
            combined_effective,
            combined_next,
            ONE_WAY_COST,
        )
        for col in gate.columns:
            out[col] = gate[col]
        out["score_decay_multiplier_effective"] = score_effective
        out["score_decay_multiplier_next"] = score_next
        out["combined_overlay_scale_effective"] = combined_effective
        out["combined_overlay_scale_next"] = combined_next
    else:
        out = curve.copy()
        out["nav_defense_scale_next"] = 1.0
        out["nav_defense_scale_effective"] = 1.0
        out["nav_defense_on_next"] = False
        out["nav_defense_on_effective"] = False
        out["nav_defense_triggered"] = False
        out["nav_defense_recovered"] = False
        out["combined_overlay_scale_effective"] = pd.to_numeric(
            out.get("score_decay_multiplier_effective", pd.Series(1.0, index=out.index)),
            errors="coerce",
        ).fillna(1.0)
        out["combined_overlay_scale_next"] = pd.to_numeric(
            out.get("score_decay_multiplier_next", pd.Series(1.0, index=out.index)),
            errors="coerce",
        ).fillna(1.0)

    out["candidate"] = candidate_label(lookback, switch_buffer, entry_fraction, nav_enter, nav_exit, defense_scale)
    out["baseline_candidate"] = candidate_label(lookback, switch_buffer, entry_fraction, None, None, None)
    out["line_role"] = line_role
    out["line_order"] = int(line_order)
    out["lookback"] = int(lookback)
    out["r2_threshold"] = np.nan
    out["r2_label"] = "none"
    out["r2_execution_threshold"] = R2_EXEC_THRESHOLD_FOR_REMOVED
    out["switch_buffer"] = float(switch_buffer)
    out["buffer_label"] = layer3.buffer_label(switch_buffer)
    out["entry_fraction"] = float(entry_fraction)
    out["entry_label"] = layer4.fraction_label(entry_fraction)
    out["momentum_decay_enabled"] = False
    out["decay_ratio_threshold"] = np.nan
    out["recovery_ratio_threshold"] = np.nan
    out["confirm_days"] = np.nan
    out["derisk_scale"] = 1.0
    out["decay_label"] = r2none_layer6.layer6.decay_label(None, None, None, None)
    out["nav_defense_enabled"] = bool(enabled)
    out["nav_enter_threshold"] = np.nan if nav_enter is None else float(nav_enter)
    out["nav_exit_threshold"] = np.nan if nav_exit is None else float(nav_exit)
    out["nav_defense_scale"] = 1.0 if defense_scale is None else float(defense_scale)
    out["nav_label"] = nav7.nav_label(nav_enter, nav_exit, defense_scale)
    return out


def select_by_line(window_metrics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for line_role, group in window_metrics.groupby("line_role", sort=False):
        passed = group[group["layer7_pass"].astype(bool)].copy()
        baseline = group[~group["nav_defense_enabled"].astype(bool)].iloc[0].to_dict()
        if passed.empty:
            selected = baseline
            selected["selection_role"] = "baseline_no_nav_defense_pass"
        elif line_role.startswith("return_watch"):
            selected = passed.sort_values(
                ["ann_return_full", "mdd_improve_full_pp", "defense_day_ratio_full"],
                ascending=[False, False, True],
            ).iloc[0].to_dict()
            selected["selection_role"] = "return_watch_nav_defense_pass"
        else:
            selected = passed.sort_values(
                ["mdd_improve_full_pp", "ann_return_full", "defense_day_ratio_full"],
                ascending=[False, False, True],
            ).iloc[0].to_dict()
            selected["selection_role"] = "selected_drawdown_nav_defense_pass"
        rows.append(selected)
    return pd.DataFrame(rows)


def original_full_reference(prices: pd.DataFrame, end_date: pd.Timestamp) -> dict[str, object]:
    row = r2none_layer5.original_full_reference(prices, end_date)
    row["candidate_type"] = "original_full_v1_1_reference"
    row["notes"] = (
        "Full official V1.1 chain on this proxy panel; includes original lookback 25, "
        "R2 0.20, switch buffer 1.05, staged entry 0.50, target-vol 25%, and later overlays."
    )
    return row


def row_from_window(source: dict[str, object], ctype: str, notes: str) -> dict[str, object]:
    row = {
        "candidate": source["candidate"],
        "candidate_type": ctype,
        "line_role": source.get("line_role", ""),
        "lookback": source.get("lookback", ""),
        "r2_threshold": source.get("r2_threshold", np.nan),
        "switch_buffer": source.get("switch_buffer", np.nan),
        "entry_fraction": source.get("entry_fraction", np.nan),
        "decay_label": source.get("decay_label", ""),
        "nav_label": source.get("nav_label", ""),
        "notes": notes,
    }
    for segment in SEGMENTS:
        row[f"ann_return_{segment}"] = source.get(f"ann_return_{segment}", np.nan)
        row[f"max_dd_{segment}"] = source.get(f"max_dd_{segment}", np.nan)
        row[f"reason_{segment}"] = source.get(f"reason_{segment}", "")
    return row


def build_comparison_list(
    window_metrics: pd.DataFrame,
    line_selection: pd.DataFrame,
    full_reference: dict[str, object],
) -> pd.DataFrame:
    rows = []
    for _, row in window_metrics[~window_metrics["nav_defense_enabled"].astype(bool)].iterrows():
        rows.append(row_from_window(row.to_dict(), "line_baseline_no_nav_defense", "Same carried line before NAV-defense layer"))
    for _, row in line_selection.iterrows():
        rows.append(row_from_window(row.to_dict(), str(row["selection_role"]), "Line-level selected NAV-defense result"))
    rows.append(full_reference)
    return pd.DataFrame(rows)


def write_record(
    run_folder: Path,
    window_metrics: pd.DataFrame,
    line_selection: pd.DataFrame,
    comparison_list: pd.DataFrame,
    sources: pd.DataFrame,
    meta: dict[str, object],
) -> None:
    top = window_metrics[window_metrics["nav_defense_enabled"].astype(bool)].sort_values(
        ["layer7_pass", "mdd_improve_full_pp", "ann_return_full"],
        ascending=[False, False, False],
    ).head(14)
    lines = [
        "# Sub-D Dynamic ChiNext Proxy R2-Removed Branch Layer 7 NAV Defense Scan",
        "",
        "## Run Metadata",
        "",
        f"- Run folder: `{run_folder}`",
        "- Layer: `Layer 7` after R2 removal, rejected target-vol, and rejected momentum decay.",
        "- Entrypoint: `run_subd_proxy_dynamic_cyb_r2none_layer7_nav_defense_scan.py`",
        "",
        "## Research Question",
        "",
        "Test standalone NAV drawdown defense on the two user-confirmed carried lines.",
        "",
        "## Implementation Anchor",
        "",
        "- Data loader reused from `run_subd_proxy_dynamic_cyb_layer0.py`.",
        "- Base curves reuse `run_subd_proxy_dynamic_cyb_r2none_layer4_staged_entry_scan.py` plus no-decay scaffolding from the R2-removed Layer 6 script.",
        "- NAV defense uses the pre-NAV-defense base NAV drawdown as `nav_defense_base_dd`.",
        "- T close base DD determines next-session defense scale; effective scale is shifted one session.",
        "- NAV/exposure/cost recomputation reuses `_recompute_final_exposure_nav` from `run_subd_six_etf_v1_1.py`.",
        "",
        "## Data Snapshot",
        "",
        f"- Start/end: `{meta['data_snapshot']['start']}` to `{meta['data_snapshot']['end']}`.",
        f"- Rows: `{meta['data_snapshot']['rows']}`.",
        "- Pool: QQQ/EWG/EWJ/GLD from 2007 start; ChiNext joins when its own data exists.",
        "",
        "## Cost and Execution Assumptions",
        "",
        f"- One-way cost: `{ONE_WAY_COST}`.",
        "- NAV defense cost is charged when the defense scale changes final exposure.",
        "- Calendar: A-share trading days; US adjusted closes are forward-filled onto that calendar for this proxy diagnostic.",
        "- Trades involving a forward-filled trade leg are blocked by the base staged-entry path for that day.",
        "",
        "## Runtime Override Plan",
        "",
        f"- Lines: `{[(lb, buf, entry, role) for lb, buf, entry, role in LINE_GRID]}`.",
        f"- NAV enter thresholds: `{list(NAV_ENTER_THRESHOLDS)}`.",
        f"- NAV exit thresholds: `{list(NAV_EXIT_THRESHOLDS)}`.",
        f"- Defense scales: `{list(DEFENSE_SCALES)}`.",
        "- Baseline: same `lookback + switch buffer + entry fraction` with R2 removed, no target-vol, no momentum decay, and no NAV defense.",
        f"- Pass rule: Full maxDD improves by more than `{nav7.MDD_IMPROVE_EPS_PP:.2f}pp`; at least 3 of 4 available windows improve maxDD; Full/5Y annualized return lag <=1pp and 3Y/1Y lag <=3pp.",
        "",
        "## Commands",
        "",
        f"- `{meta['command']}`",
        "",
        "## Output Files",
        "",
        "- `scan_summary.csv`",
        "- `window_metrics.csv`",
        "- `line_selection.csv`",
        "- `comparison_list.csv`",
        "- `daily_outputs/r2none_nav_defense_daily_curves.csv`",
        "- `sources.csv`",
        "",
        "## Line-Level Selection",
        "",
        "| Line Role | Candidate | Selection | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | MDD Improve pp | Trigger Full | Defense Days Full | Pass Reason |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for _, row in line_selection.iterrows():
        lines.append(
            "| "
            f"{row['line_role']} | `{row['candidate']}` | {row['selection_role']} | "
            f"{pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{pct(row['ann_return_last_10y'])} | {pct(row['max_dd_last_10y'])} | "
            f"{pct(row['ann_return_last_5y'])} | {pct(row['max_dd_last_5y'])} | "
            f"{pct(row['ann_return_last_3y'])} | {pct(row['max_dd_last_3y'])} | "
            f"{pct(row['ann_return_last_1y'])} | {pct(row['max_dd_last_1y'])} | "
            f"{fmt(row['mdd_improve_full_pp'])} | "
            f"{int(row['trigger_count_full']) if pd.notna(row['trigger_count_full']) else 'N/A'} | "
            f"{pct(row['defense_day_ratio_full'])} | {row['pass_reason']} |"
        )
    lines.extend(
        [
            "",
            "## Best NAV Defense Candidates",
            "",
            "| Candidate | Role | Full Ann. | Full MDD | Full Ann Delta pp | Full MDD Improve pp | DD Improve Windows | Trigger Full | Defense Days Full | Pass | Reason |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for _, row in top.iterrows():
        lines.append(
            "| "
            f"`{row['candidate']}` | {row['line_role']} | {pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{fmt(row['ann_delta_full_pp'])} | {fmt(row['mdd_improve_full_pp'])} | {int(row['dd_improve_window_count'])} | "
            f"{int(row['trigger_count_full']) if pd.notna(row['trigger_count_full']) else 'N/A'} | "
            f"{pct(row['defense_day_ratio_full'])} | {bool(row['layer7_pass'])} | {row['pass_reason']} |"
        )
    lines.extend(
        [
            "",
            "## Comparison List",
            "",
            "| Candidate | Type | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Notes |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for _, row in comparison_list.iterrows():
        lines.append(
            "| "
            f"`{row['candidate']}` | {row['candidate_type']} | "
            f"{pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{pct(row['ann_return_last_10y'])} | {pct(row['max_dd_last_10y'])} | "
            f"{pct(row['ann_return_last_5y'])} | {pct(row['max_dd_last_5y'])} | "
            f"{pct(row['ann_return_last_3y'])} | {pct(row['max_dd_last_3y'])} | "
            f"{pct(row['ann_return_last_1y'])} | {pct(row['max_dd_last_1y'])} | {row['notes']} |"
        )
    lines.extend(
        [
            "",
            "## Stability Classification",
            "",
            "- Decision: `line_level_selection_after_nav_defense_on_r2_removed_branch`.",
            "- Stability label: `nav_defense_pass_if_line_selection_uses_overlay_else_keep_previous`.",
            "- 10Y remains N/A by sample length: 2432 sessions is less than 2520 trading days.",
            "",
            "## Decision",
            "",
            "- Keep each line's selected row from `line_selection.csv`.",
            "- Stop here before overheat tests.",
            "",
            "## Source Audit",
            "",
            sources.to_markdown(index=False),
            "",
        ]
    )
    (run_folder / "record.md").write_text("\n".join(lines), encoding="utf-8")


def run_scan(start_date: pd.Timestamp, end_date: pd.Timestamp, run_folder: Path) -> None:
    started = time.time()
    run_folder.mkdir(parents=True, exist_ok=True)
    daily_dir = run_folder / "daily_outputs"
    daily_dir.mkdir(parents=True, exist_ok=True)

    prices, sources = layer0.build_proxy_panel(start_date, end_date)
    grid = nav_grid()
    curves = []
    summary_rows = []
    for line_order, (lookback, switch_buffer, entry_fraction, line_role) in enumerate(LINE_GRID):
        staged = r2none_layer4.run_staged_line(
            prices,
            end_date,
            lookback,
            switch_buffer,
            entry_fraction,
            line_role,
        )
        base_curve = r2none_layer6.apply_momentum_decay_layer(
            staged,
            lookback,
            switch_buffer,
            entry_fraction,
            None,
            None,
            None,
            None,
            line_role,
            line_order,
        )
        for nav_enter, nav_exit, defense_scale in grid:
            curve = apply_nav_defense_layer(
                base_curve,
                lookback,
                switch_buffer,
                entry_fraction,
                nav_enter,
                nav_exit,
                defense_scale,
                line_role,
                line_order,
            )
            curves.append(curve)
            for segment, label, start, reason in layer1.window_specs(prices.index):
                summary_rows.append(nav7.summarize_curve(curve, segment, label, start, reason))

    scan_summary = pd.DataFrame(summary_rows)
    window_metrics = nav7.build_window_metrics(scan_summary)
    line_selection = select_by_line(window_metrics)
    full_reference = original_full_reference(prices, end_date)
    comparison_list = build_comparison_list(window_metrics, line_selection, full_reference)
    daily = nav7.daily_output_frame(curves)

    scan_summary.to_csv(run_folder / "scan_summary.csv", index=False, encoding="utf-8-sig")
    window_metrics.to_csv(run_folder / "window_metrics.csv", index=False, encoding="utf-8-sig")
    line_selection.to_csv(run_folder / "line_selection.csv", index=False, encoding="utf-8-sig")
    comparison_list.to_csv(run_folder / "comparison_list.csv", index=False, encoding="utf-8-sig")
    daily.to_csv(daily_dir / "r2none_nav_defense_daily_curves.csv", index=False, encoding="utf-8-sig")
    sources.to_csv(run_folder / "sources.csv", index=False, encoding="utf-8-sig")

    command = (
        "python run_subd_proxy_dynamic_cyb_r2none_layer7_nav_defense_scan.py "
        f"--start-date {start_date.date()} --end-date {end_date.date()} --run-folder {run_folder}"
    )
    metadata_path = run_folder / "scan_meta.json"
    meta = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    meta.update(
        {
            "phase": "scan_complete_unfinalized",
            "scan_type": "layer7_nav_defense_scan_after_r2_removed_no_decay",
            "parameter_group": "layer7_nav_defense_after_r2_removed_no_decay",
            "baseline": {
                "rule": "same lookback + switch_buffer + entry_fraction with R2 removed, target-vol disabled, momentum decay disabled, and NAV defense disabled",
                "line_baselines": [candidate_label(lb, buf, entry, None, None, None) for lb, buf, entry, _ in LINE_GRID],
            },
            "candidate_grid": [
                {
                    "lookback": int(lookback),
                    "switch_buffer": float(switch_buffer),
                    "entry_fraction": float(entry_fraction),
                    "line_role": line_role,
                    "r2_threshold": None,
                    "r2_execution_threshold": R2_EXEC_THRESHOLD_FOR_REMOVED,
                    "momentum_decay": None,
                    "nav_enter": None if nav_enter is None else float(nav_enter),
                    "nav_exit": None if nav_exit is None else float(nav_exit),
                    "defense_scale": None if defense_scale is None else float(defense_scale),
                }
                for lookback, switch_buffer, entry_fraction, line_role in LINE_GRID
                for nav_enter, nav_exit, defense_scale in grid
            ],
            "data_snapshot": {
                "start": pd.Timestamp(prices.index[0]).date().isoformat(),
                "end": pd.Timestamp(prices.index[-1]).date().isoformat(),
                "rows": int(len(prices)),
                "calendar": "A-share trading-day cache",
                "pool_rule": "QQQ/EWG/EWJ/GLD from 2007 start; CN_CYB_399006 joins from own data with no backfill",
                "ffill_counts_on_cn_calendar": {
                    code: int(prices.attrs["price_ffill_flags"][code].sum()) for code in prices.columns
                },
            },
            "cost_model": {
                "one_way_cost": ONE_WAY_COST,
                "stale_trade_guard": True,
                "nav_defense_rebalance_cost_included": True,
            },
            "execution_assumptions": {
                "signal": "close-to-close weighted-slope ranking, score range 0..5, switch buffer, R2 removed",
                "staged_entry": "enter new asset with selected initial fraction; fill to 100% on later down day if signal remains unchanged",
                "target_vol": "disabled because Layer 5 rejected target-vol for both carried lines",
                "momentum_decay": "disabled because Layer 6 rejected momentum decay for both carried lines",
                "nav_defense": "pre-NAV-defense base NAV DD at T close sets next-session defense scale",
                "nav_defense_dd_basis": "nav_before_nav_defense; not recursive final NAV",
                "mixed_market_calendar": "diagnostic A-share calendar with US proxy forward-filled; base trades on stale trade legs blocked",
            },
            "pass_rule": {
                "mdd_improve_eps_pp": nav7.MDD_IMPROVE_EPS_PP,
                "available_windows": list(nav7.AVAILABLE_PASS_SEGMENTS),
                "return_lag_tolerance_pp": {"full": 1.0, "last_5y": 1.0, "last_3y": 3.0, "last_1y": 3.0},
            },
            "line_selection": json.loads(line_selection.to_json(orient="records")),
            "comparison_reference": {
                "original_full_strategy_candidate": "orig_full_v1_1_reference",
                "original_default_params": {
                    "lookback": subd.LOOKBACK,
                    "r2_threshold": v11.R2_THRESHOLD,
                    "switch_buffer": v11.SWITCH_BUFFER,
                    "entry_fraction": v11.INITIAL_ENTRY_FRACTION,
                    "target_vol": v11.TARGET_VOL,
                },
            },
            "outputs": {
                "scan_summary": str(run_folder / "scan_summary.csv"),
                "window_metrics": str(run_folder / "window_metrics.csv"),
                "line_selection": str(run_folder / "line_selection.csv"),
                "comparison_list": str(run_folder / "comparison_list.csv"),
                "daily_curves": str(daily_dir / "r2none_nav_defense_daily_curves.csv"),
                "sources": str(run_folder / "sources.csv"),
                "record": str(run_folder / "record.md"),
                "scan_meta": str(run_folder / "scan_meta.json"),
                "command_log": str(run_folder / "command_log.txt"),
            },
            "git_branch_after": git_value(["branch", "--show-current"]),
            "git_commit_after": git_value(["rev-parse", "HEAD"]),
            "git_status_after": git_value(["status", "--short"]),
            "command": command,
            "elapsed_sec": round(time.time() - started, 3),
        }
    )
    metadata_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    write_record(run_folder, window_metrics, line_selection, comparison_list, sources, meta)

    with (run_folder / "command_log.txt").open("a", encoding="utf-8") as fh:
        fh.write("\n[scan]\n")
        fh.write(f"cwd={Path.cwd()}\n")
        fh.write(command + "\n")
        fh.write(f"elapsed_sec={meta['elapsed_sec']}\n")

    print(f"WROTE {run_folder / 'scan_summary.csv'}")
    print(f"WROTE {run_folder / 'window_metrics.csv'}")
    print(f"WROTE {run_folder / 'line_selection.csv'}")
    print(f"WROTE {run_folder / 'comparison_list.csv'}")
    print(f"WROTE {daily_dir / 'r2none_nav_defense_daily_curves.csv'}")
    display_cols = [
        "line_role",
        "candidate",
        "selection_role",
        "ann_return_full",
        "max_dd_full",
        "ann_delta_full_pp",
        "mdd_improve_full_pp",
        "ann_return_last_5y",
        "max_dd_last_5y",
        "ann_return_last_3y",
        "max_dd_last_3y",
        "ann_return_last_1y",
        "max_dd_last_1y",
        "trigger_count_full",
        "defense_day_ratio_full",
        "layer7_pass",
        "pass_reason",
    ]
    print(line_selection[display_cols].to_string(index=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", default=str(DEFAULT_START.date()))
    parser.add_argument("--end-date", default=str(DEFAULT_END.date()))
    parser.add_argument("--run-folder", default=str(DEFAULT_RUN_FOLDER))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_scan(pd.Timestamp(args.start_date), pd.Timestamp(args.end_date), Path(args.run_folder))


if __name__ == "__main__":
    main()
