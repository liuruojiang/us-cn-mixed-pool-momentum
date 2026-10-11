from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd

import run_subd_proxy_dynamic_cyb_layer0 as layer0
import run_subd_proxy_dynamic_cyb_layer1_scan as layer1
import run_subd_proxy_dynamic_cyb_layer2_r2_scan as layer2
import run_subd_proxy_dynamic_cyb_layer3_switch_buffer_scan as layer3
import run_subd_proxy_dynamic_cyb_layer4_staged_entry_scan as layer4
import run_subd_proxy_dynamic_cyb_layer6_momentum_decay_scan as layer6
import run_subd_proxy_dynamic_cyb_layer7_nav_defense_scan as nav7


DEFAULT_START = pd.Timestamp("2007-01-01")
DEFAULT_END = pd.Timestamp("2016-12-30")
DEFAULT_RUN_FOLDER = Path(
    "quant_param_scan_runs"
    "/20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_nav_defense_standalone_layer7_nav_drawdown_gate_no_decay"
)
PRIMARY_LOOKBACK = 28
PRIMARY_R2 = 0.50
PRIMARY_SWITCH_BUFFER = 1.00
PRIMARY_ENTRY_FRACTION = 0.75
LINE_GRID: tuple[tuple[int, float, float, float, str, bool], ...] = (
    (28, 0.50, 1.00, 0.75, "layer5_carried_primary_no_decay", True),
    (28, 0.50, 1.00, 0.67, "entry_neighbor_no_decay", True),
    (28, 0.40, 1.00, 0.75, "r2_neighbor_no_decay", True),
    (32, 0.50, 1.00, 0.75, "return_peak_watch_no_decay", True),
    (25, 0.20, 1.05, 0.50, "original_same_stage_no_decay", False),
)
NAV_ENTER_THRESHOLDS = (0.075, 0.10, 0.125, 0.15, 0.20)
NAV_EXIT_THRESHOLDS = (0.03, 0.05, 0.08, 0.10)
DEFENSE_SCALES = (0.0, 0.25, 0.50, 0.75)
ONE_WAY_COST = 0.001
SEGMENTS = ("full", "last_10y", "last_5y", "last_3y", "last_1y")


def git_value(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def candidate_label(
    lookback: int,
    r2_threshold: float,
    switch_buffer: float,
    entry_fraction: float,
    nav_enter: float | None,
    nav_exit: float | None,
    defense_scale: float | None,
) -> str:
    return nav7.candidate_label(
        lookback,
        r2_threshold,
        switch_buffer,
        entry_fraction,
        None,
        None,
        None,
        None,
        nav_enter,
        nav_exit,
        defense_scale,
    )


def nav_grid(scan_nav: bool) -> list[tuple[float | None, float | None, float | None]]:
    grid: list[tuple[float | None, float | None, float | None]] = [(None, None, None)]
    if not scan_nav:
        return grid
    for enter in NAV_ENTER_THRESHOLDS:
        for exit_value in NAV_EXIT_THRESHOLDS:
            if exit_value >= enter:
                continue
            for scale in DEFENSE_SCALES:
                grid.append((float(enter), float(exit_value), float(scale)))
    return grid


def pct(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value) * 100:.2f}%"


def fmt_num(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value):.2f}"


def select_candidate(window_metrics: pd.DataFrame) -> dict[str, object]:
    passed = window_metrics[window_metrics["layer7_pass"].astype(bool)].copy()
    primary_passed = passed[
        passed["lookback"].eq(PRIMARY_LOOKBACK)
        & passed["r2_threshold"].eq(PRIMARY_R2)
        & passed["switch_buffer"].eq(PRIMARY_SWITCH_BUFFER)
        & passed["entry_fraction"].eq(PRIMARY_ENTRY_FRACTION)
        & (~passed["momentum_decay_enabled"].astype(bool))
    ].copy()
    if not primary_passed.empty:
        selected = primary_passed.sort_values(
            ["ann_return_full", "mdd_improve_full_pp", "defense_day_ratio_full"],
            ascending=[False, False, True],
        ).iloc[0].to_dict()
        decision = "carry_forward_standalone_nav_defense_pass"
        stability = "primary_pass_no_decay"
    else:
        baseline = window_metrics[
            window_metrics["lookback"].eq(PRIMARY_LOOKBACK)
            & window_metrics["r2_threshold"].eq(PRIMARY_R2)
            & window_metrics["switch_buffer"].eq(PRIMARY_SWITCH_BUFFER)
            & window_metrics["entry_fraction"].eq(PRIMARY_ENTRY_FRACTION)
            & (~window_metrics["momentum_decay_enabled"].astype(bool))
            & (~window_metrics["nav_defense_enabled"].astype(bool))
        ]
        selected = baseline.iloc[0].to_dict()
        if passed.empty:
            decision = "do_not_add_standalone_nav_defense_keep_layer5_primary"
            stability = "no_pass_keep_previous"
        else:
            decision = "do_not_add_standalone_nav_defense_keep_layer5_primary_watch_nonprimary"
            stability = "nonprimary_watch_only"
    result = {"selected": selected, "decision": decision, "stability_label": stability}
    if not passed.empty:
        result["best_nonprimary_pass"] = passed.sort_values(
            ["ann_return_full", "mdd_improve_full_pp"],
            ascending=[False, False],
        ).iloc[0].to_dict()
    return result


def row_from_window(source: dict[str, object], candidate: str, ctype: str, notes: str) -> dict[str, object]:
    row = {
        "candidate": candidate,
        "candidate_type": ctype,
        "lookback": source.get("lookback", ""),
        "r2_threshold": source.get("r2_threshold", ""),
        "switch_buffer": source.get("switch_buffer", ""),
        "entry_fraction": source.get("entry_fraction", ""),
        "decay_label": source.get("decay_label", ""),
        "nav_label": source.get("nav_label", ""),
        "notes": notes,
    }
    for segment in SEGMENTS:
        row[f"ann_return_{segment}"] = source[f"ann_return_{segment}"]
        row[f"max_dd_{segment}"] = source[f"max_dd_{segment}"]
        row[f"reason_{segment}"] = source.get(f"reason_{segment}", "")
    return row


def build_comparison_list(window_metrics: pd.DataFrame, full_reference: dict[str, object], selected: dict[str, object]) -> pd.DataFrame:
    rows = []
    comparisons = [
        (
            candidate_label(28, 0.50, 1.00, 0.75, None, None, None),
            "layer5_carried_baseline_no_decay",
            "Layer5 carried primary line; target-vol rejected and momentum decay disabled for standalone NAV-defense test",
            None,
        ),
        (
            str(selected["candidate"]),
            "standalone_nav_defense_selected",
            "Selected standalone NAV-defense line under the documented pass rule",
            None,
        ),
        (
            candidate_label(28, 0.50, 1.00, 0.67, None, None, None),
            "entry_neighbor_no_decay_nav_off",
            "Entry-fraction neighbor before standalone NAV defense",
            None,
        ),
        (
            candidate_label(32, 0.50, 1.00, 0.75, None, None, None),
            "return_peak_watch_no_decay_nav_off",
            "Return-peak watch line before standalone NAV defense",
            None,
        ),
        (
            candidate_label(25, 0.20, 1.05, 0.50, None, None, None),
            "original_same_stage_no_decay_nav_off",
            "Original first-layer parameter plus original R2 0.20, switch buffer 1.05, initial entry fraction 0.50; no momentum decay and no NAV defense",
            "orig_layer7_standalone_lb25_r2_0p20_buf_1p05_entry_0p50_nav_off",
        ),
    ]
    seen = set()
    for label, ctype, notes, output_label in comparisons:
        if label in seen:
            continue
        seen.add(label)
        match = window_metrics[window_metrics["candidate"].eq(label)]
        if match.empty:
            continue
        rows.append(row_from_window(match.iloc[0].to_dict(), output_label or label, ctype, notes))
    rows.append(full_reference)
    return pd.DataFrame(rows)


def write_record(
    run_folder: Path,
    window_metrics: pd.DataFrame,
    comparison_list: pd.DataFrame,
    selection: dict[str, object],
    sources: pd.DataFrame,
    meta: dict[str, object],
) -> None:
    selected = selection["selected"]
    primary = window_metrics[
        window_metrics["lookback"].eq(PRIMARY_LOOKBACK)
        & window_metrics["r2_threshold"].eq(PRIMARY_R2)
        & window_metrics["switch_buffer"].eq(PRIMARY_SWITCH_BUFFER)
        & window_metrics["entry_fraction"].eq(PRIMARY_ENTRY_FRACTION)
        & (~window_metrics["momentum_decay_enabled"].astype(bool))
    ].copy()
    primary_display = pd.concat(
        [
            primary[~primary["nav_defense_enabled"].astype(bool)],
            primary[primary["nav_defense_enabled"].astype(bool)].sort_values(
                ["layer7_pass", "ann_return_full", "mdd_improve_full_pp"],
                ascending=[False, False, False],
            ).head(12),
        ],
        ignore_index=True,
    )
    top_pass = window_metrics[window_metrics["layer7_pass"].astype(bool)].sort_values(
        ["ann_return_full", "mdd_improve_full_pp"],
        ascending=[False, False],
    ).head(10)
    if top_pass.empty:
        top_pass = window_metrics[window_metrics["nav_defense_enabled"].astype(bool)].sort_values(
            "mdd_improve_full_pp",
            ascending=False,
        ).head(10)

    lines = [
        "# Sub-D Dynamic ChiNext Proxy Standalone NAV Defense Scan",
        "",
        "## Run Metadata",
        "",
        f"- Run folder: `{run_folder}`",
        "- Layer: `Layer 7 standalone correction`",
        "- Strategy: dynamic ChiNext proxy pool, 2007-2016.",
        "- Entrypoint: `run_subd_proxy_dynamic_cyb_layer7_nav_defense_standalone_scan.py`",
        "",
        "## Research Question",
        "",
        "Test NAV drawdown defense by itself, without carrying Layer 6 momentum decay.",
        "",
        "## Implementation Anchor",
        "",
        "- Data loader reused from `run_subd_proxy_dynamic_cyb_layer0.py`.",
        "- Base curves reuse Layer 4 staged entry only; target-vol remains rejected and momentum decay is disabled.",
        "- NAV defense uses the pre-NAV-defense base NAV drawdown as `nav_defense_base_dd`.",
        "- T close base DD determines the next-session defense scale; effective scale is shifted one session.",
        "- NAV/exposure/cost recomputation reuses `_recompute_final_exposure_nav` from `run_subd_six_etf_v1_1.py` via the Layer 7 helper.",
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
        f"- Lines carried: `{[(lb, r2, buf, entry, role, scan) for lb, r2, buf, entry, role, scan in LINE_GRID]}`.",
        f"- NAV enter thresholds: `{list(NAV_ENTER_THRESHOLDS)}`.",
        f"- NAV exit thresholds: `{list(NAV_EXIT_THRESHOLDS)}`.",
        f"- Defense scales: `{list(DEFENSE_SCALES)}`.",
        "- Baseline: same `lookback + R2 + switch buffer + entry fraction` with no target-vol, no momentum decay, and no NAV defense.",
        f"- Pass rule: Full maxDD improves by more than `{nav7.MDD_IMPROVE_EPS_PP:.2f}pp`; at least 3 of the 4 available windows improve maxDD by more than `{nav7.MDD_IMPROVE_EPS_PP:.2f}pp`; Full/5Y annualized return lag <=1pp and 3Y/1Y lag <=3pp versus same-line no-NAV-defense baseline.",
        "",
        "## Commands",
        "",
        f"- `{meta['command']}`",
        "",
        "## Primary Line Results",
        "",
        "| Candidate | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Full Ann Delta pp | Full MDD Improve pp | Trigger Full | Defense Days Full | Pass | Reason |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for _, row in primary_display.iterrows():
        lines.append(
            "| "
            f"{row['candidate']} | {pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{pct(row['ann_return_last_10y'])} | {pct(row['max_dd_last_10y'])} | "
            f"{pct(row['ann_return_last_5y'])} | {pct(row['max_dd_last_5y'])} | "
            f"{pct(row['ann_return_last_3y'])} | {pct(row['max_dd_last_3y'])} | "
            f"{pct(row['ann_return_last_1y'])} | {pct(row['max_dd_last_1y'])} | "
            f"{fmt_num(row['ann_delta_full_pp'])} | {fmt_num(row['mdd_improve_full_pp'])} | "
            f"{int(row['trigger_count_full']) if pd.notna(row['trigger_count_full']) else 'N/A'} | "
            f"{pct(row['defense_day_ratio_full'])} | {bool(row['layer7_pass'])} | {row['pass_reason']} |"
        )
    lines.extend(
        [
            "",
            "## Passing Or Best Candidates",
            "",
            "| Candidate | Role | Full Ann. | Full MDD | Full MDD Improve pp | DD Improve Windows | Trigger Full | Defense Days Full | Pass |",
            "|---|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for _, row in top_pass.iterrows():
        lines.append(
            "| "
            f"{row['candidate']} | {row['line_role']} | {pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{fmt_num(row['mdd_improve_full_pp'])} | {int(row['dd_improve_window_count'])} | "
            f"{int(row['trigger_count_full']) if pd.notna(row['trigger_count_full']) else 'N/A'} | "
            f"{pct(row['defense_day_ratio_full'])} | {bool(row['layer7_pass'])} |"
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
            f"{row['candidate']} | {row['candidate_type']} | "
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
            f"- Selected candidate: `{selected['candidate']}`.",
            f"- Decision: `{selection['decision']}`.",
            f"- Stability label: `{selection['stability_label']}`.",
            f"- Best non-primary pass: `{selection.get('best_nonprimary_pass', {}).get('candidate', 'N/A')}`.",
            "- 10Y remains N/A by sample length: 2432 sessions is less than 2520 trading days.",
            "",
            "## Decision",
            "",
            f"- Decision: `{selection['decision']}`.",
            "- The prior NAV-defense-after-momentum-decay run is diagnostic only and superseded for this standalone layer decision.",
            "",
            "## User-Facing Summary",
            "",
            f"Standalone NAV defense selected `{selected['candidate']}` under the documented pass rule. See `window_metrics.csv` for all lines.",
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
    base_curves = {}
    for lookback, r2_threshold, switch_buffer, entry_fraction, line_role, _scan_nav in LINE_GRID:
        staged = layer4.run_staged_line(
            prices,
            end_date,
            lookback,
            r2_threshold,
            switch_buffer,
            entry_fraction,
            line_role,
        )
        base_curves[(lookback, r2_threshold, switch_buffer, entry_fraction, line_role, _scan_nav)] = (
            layer6.apply_momentum_decay_layer(
                staged,
                lookback,
                r2_threshold,
                switch_buffer,
                entry_fraction,
                None,
                None,
                None,
                None,
                line_role,
            )
        )

    curves = []
    summary_rows = []
    for line, base_curve in base_curves.items():
        lookback, r2_threshold, switch_buffer, entry_fraction, line_role, scan_nav = line
        for nav_enter, nav_exit, defense_scale in nav_grid(scan_nav):
            curve = nav7.apply_nav_defense_layer(
                base_curve,
                lookback,
                r2_threshold,
                switch_buffer,
                entry_fraction,
                None,
                None,
                None,
                None,
                nav_enter,
                nav_exit,
                defense_scale,
                line_role,
            )
            curves.append(curve)
            for segment, label, start, reason in layer1.window_specs(prices.index):
                summary_rows.append(nav7.summarize_curve(curve, segment, label, start, reason))

    scan_summary = pd.DataFrame(summary_rows)
    window_metrics = nav7.build_window_metrics(scan_summary)
    full_reference = layer2.original_full_reference(prices, end_date)
    full_reference["candidate_type"] = "original_full_strategy_reference"
    full_reference["notes"] = "Full official V1.1 chain including target-vol and overheat; context only, not standalone NAV-defense pass baseline"
    selection = select_candidate(window_metrics)
    comparison_list = build_comparison_list(window_metrics, full_reference, selection["selected"])
    daily = nav7.daily_output_frame(curves)

    scan_summary.to_csv(run_folder / "scan_summary.csv", index=False, encoding="utf-8-sig")
    window_metrics.to_csv(run_folder / "window_metrics.csv", index=False, encoding="utf-8-sig")
    comparison_list.to_csv(run_folder / "comparison_list.csv", index=False, encoding="utf-8-sig")
    daily.to_csv(daily_dir / "nav_defense_standalone_daily_curves.csv", index=False, encoding="utf-8-sig")
    sources.to_csv(run_folder / "sources.csv", index=False, encoding="utf-8-sig")

    metadata_path = run_folder / "scan_meta.json"
    meta = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    command = (
        "python run_subd_proxy_dynamic_cyb_layer7_nav_defense_standalone_scan.py "
        f"--start-date {start_date.date()} --end-date {end_date.date()} --run-folder {run_folder}"
    )
    meta.update(
        {
            "phase": "scan_complete_unfinalized",
            "scan_type": "standalone_layer7_nav_defense_grid_scan",
            "parameter_group": "layer7_nav_drawdown_gate_no_decay",
            "baseline": {"rule": "same lookback + R2 + switch_buffer + entry_fraction with no target-vol, no momentum decay, and NAV defense disabled"},
            "candidate_grid": [
                {
                    "lookback": int(lookback),
                    "r2_threshold": float(r2_threshold),
                    "switch_buffer": float(switch_buffer),
                    "entry_fraction": float(entry_fraction),
                    "line_role": line_role,
                    "momentum_decay": "disabled",
                    "nav_enter": None if nav_enter is None else float(nav_enter),
                    "nav_exit": None if nav_exit is None else float(nav_exit),
                    "defense_scale": None if defense_scale is None else float(defense_scale),
                }
                for lookback, r2_threshold, switch_buffer, entry_fraction, line_role, scan_nav in LINE_GRID
                for nav_enter, nav_exit, defense_scale in nav_grid(scan_nav)
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
                "signal": "close-to-close weighted-slope ranking with fixed R2 threshold, switch buffer, and staged entry",
                "target_vol": "disabled because Layer 5 rejected target-vol for this branch",
                "momentum_decay": "disabled by user correction; NAV defense tested standalone",
                "nav_defense": "pre-NAV-defense base NAV DD at T close sets next-session defense scale",
                "nav_defense_dd_basis": "nav_before_nav_defense; not recursive final NAV",
                "overheat": "not tested",
                "mixed_market_calendar": "diagnostic A-share calendar with US proxy forward-filled; base trades on stale trade legs blocked",
            },
            "pass_rule": {
                "mdd_improve_eps_pp": nav7.MDD_IMPROVE_EPS_PP,
                "available_windows": list(nav7.AVAILABLE_PASS_SEGMENTS),
                "return_lag_tolerance_pp": {"full": 1.0, "last_5y": 1.0, "last_3y": 3.0, "last_1y": 3.0},
            },
            "selection": selection,
            "supersedes": {
                "run": "20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_nav_defense_layer7_nav_drawdown_gate",
                "reason": "that run tested NAV defense after momentum decay; user requested standalone NAV defense",
            },
            "outputs": {
                "scan_summary": str(run_folder / "scan_summary.csv"),
                "window_metrics": str(run_folder / "window_metrics.csv"),
                "comparison_list": str(run_folder / "comparison_list.csv"),
                "daily_curves": str(daily_dir / "nav_defense_standalone_daily_curves.csv"),
                "sources": str(run_folder / "sources.csv"),
                "record": str(run_folder / "record.md"),
            },
            "git_branch_after": git_value(["branch", "--show-current"]),
            "git_commit_after": git_value(["rev-parse", "HEAD"]),
            "git_status_after": git_value(["status", "--short"]),
            "command": command,
            "elapsed_sec": round(time.time() - started, 3),
        }
    )
    metadata_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    write_record(run_folder, window_metrics, comparison_list, selection, sources, meta)

    with (run_folder / "command_log.txt").open("a", encoding="utf-8") as fh:
        fh.write("\n[scan]\n")
        fh.write(f"cwd={Path.cwd()}\n")
        fh.write(command + "\n")
        fh.write(f"elapsed_sec={meta['elapsed_sec']}\n")

    print(f"WROTE {run_folder / 'scan_summary.csv'}")
    print(f"WROTE {run_folder / 'window_metrics.csv'}")
    print(f"WROTE {run_folder / 'comparison_list.csv'}")
    print(f"WROTE {daily_dir / 'nav_defense_standalone_daily_curves.csv'}")
    print(json.dumps({"selected": selection["selected"], "decision": selection["decision"], "stability_label": selection["stability_label"]}, ensure_ascii=False, indent=2, default=str))
    primary = window_metrics[
        window_metrics["lookback"].eq(PRIMARY_LOOKBACK)
        & window_metrics["r2_threshold"].eq(PRIMARY_R2)
        & window_metrics["switch_buffer"].eq(PRIMARY_SWITCH_BUFFER)
        & window_metrics["entry_fraction"].eq(PRIMARY_ENTRY_FRACTION)
        & (~window_metrics["momentum_decay_enabled"].astype(bool))
    ].copy()
    cols = [
        "candidate",
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
    print(primary.sort_values(["layer7_pass", "ann_return_full", "mdd_improve_full_pp"], ascending=[False, False, False]).head(20)[cols].to_string(index=False))


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
