from __future__ import annotations

import argparse
import json
import math
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd

import research_subd_six_etf_weighted_slope as subd
import run_subd_proxy_dynamic_cyb_layer0 as layer0
import run_subd_proxy_dynamic_cyb_layer1_scan as layer1
import run_subd_proxy_dynamic_cyb_layer8_overheat_three_directions_scan as layer8
import run_subd_proxy_dynamic_cyb_r2none_layer4_staged_entry_scan as r2none_layer4
import run_subd_proxy_dynamic_cyb_r2none_layer7_nav_defense_scan as r2none_layer7
import run_subd_six_etf_v1_1 as v11


DEFAULT_START = pd.Timestamp("2007-01-01")
DEFAULT_END = pd.Timestamp("2016-12-30")
DEFAULT_RUN_FOLDER = Path(
    "quant_param_scan_runs"
    "/20260702_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_r2_removed_branch_layer8_overheat_three_directions_after_nav_defense_no_decay"
)
ONE_WAY_COST = 0.001
DEFAULT_SCORE_MAX = 5.0
SEGMENTS = ("full", "last_10y", "last_5y", "last_3y", "last_1y")


CARRY_LINES = (
    layer8.CarryLine(
        "main_nav_r2_removed",
        28,
        math.nan,
        1.15,
        0.25,
        None,
        None,
        None,
        None,
        0.20,
        0.05,
        0.50,
    ),
    layer8.CarryLine(
        "return_watch_nav_r2_removed",
        28,
        math.nan,
        1.15,
        0.75,
        None,
        None,
        None,
        None,
        0.15,
        0.10,
        0.75,
    ),
)


def git_value(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def pct(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value) * 100:.2f}%"


def fmt_num(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value):.2f}"


def line_index(line: layer8.CarryLine) -> int:
    for idx, candidate in enumerate(CARRY_LINES):
        if candidate.line_id == line.line_id:
            return idx
    return 0


def selected_nav_label(line: layer8.CarryLine) -> str:
    return r2none_layer7.candidate_label(
        line.lookback,
        line.switch_buffer,
        line.entry_fraction,
        line.nav_enter,
        line.nav_exit,
        line.nav_scale,
    )


def line_base_candidate(line: layer8.CarryLine) -> str:
    return f"{selected_nav_label(line)}_scoremax_{layer8.score_max_label(DEFAULT_SCORE_MAX)}_overheat_off"


def candidate_label(line: layer8.CarryLine, direction: str, parameter_label: str) -> str:
    if direction == "baseline":
        return line_base_candidate(line)
    return f"{selected_nav_label(line)}_{direction}_{parameter_label}"


def run_staged_line_with_score_max(
    prices: pd.DataFrame,
    end_date: pd.Timestamp,
    line: layer8.CarryLine,
    score_max: float,
) -> pd.DataFrame:
    original_score_max = subd.SCORE_MAX
    try:
        subd.SCORE_MAX = float(score_max)
        return r2none_layer4.run_staged_line(
            prices,
            end_date,
            line.lookback,
            line.switch_buffer,
            line.entry_fraction,
            line.line_id,
        )
    finally:
        subd.SCORE_MAX = original_score_max


def build_line_curve(
    prices: pd.DataFrame,
    end_date: pd.Timestamp,
    line: layer8.CarryLine,
    score_max: float,
) -> pd.DataFrame:
    staged = run_staged_line_with_score_max(prices, end_date, line, score_max)
    no_decay = r2none_layer7.r2none_layer6.apply_momentum_decay_layer(
        staged,
        line.lookback,
        line.switch_buffer,
        line.entry_fraction,
        None,
        None,
        None,
        None,
        line.line_id,
        line_index(line),
    )
    curve = r2none_layer7.apply_nav_defense_layer(
        no_decay,
        line.lookback,
        line.switch_buffer,
        line.entry_fraction,
        line.nav_enter,
        line.nav_exit,
        line.nav_scale,
        line.line_id,
        line_index(line),
    )
    curve["candidate"] = selected_nav_label(line)
    curve["line_id"] = line.line_id
    curve["score_max"] = float(score_max)
    curve["score_max_label"] = layer8.score_max_label(score_max)
    return curve


def patch_layer8_helpers() -> None:
    layer8.line_base_candidate = line_base_candidate
    layer8.candidate_label = candidate_label
    layer8.build_line_curve = build_line_curve


def original_full_reference(prices: pd.DataFrame, end_date: pd.Timestamp) -> dict[str, object]:
    row = r2none_layer7.original_full_reference(prices, end_date)
    row["candidate_type"] = "original_full_v1_1_reference"
    row["line_id"] = "original"
    row["overheat_direction"] = "original_full_chain"
    row["overheat_parameter_label"] = "original_v1_1"
    row["notes"] = (
        "Full official V1.1 proxy-chain reference: original lookback 25, R2 0.20, "
        "switch buffer 1.05, staged entry 0.50, target-vol 25%, and original overheat."
    )
    return row


def write_record(
    run_folder: Path,
    direction_selection: pd.DataFrame,
    comparison_list: pd.DataFrame,
    sources: pd.DataFrame,
    meta: dict[str, object],
) -> None:
    pass_count = int(direction_selection["layer8_pass"].astype(bool).sum())
    decision = (
        "carry_forward_overheat_pass_candidates"
        if pass_count > 0
        else "do_not_add_layer8_overheat_keep_layer7_nav_lines"
    )
    stability = "overheat_direction_pass" if pass_count > 0 else "no_direction_pass_diagnostic"
    lines = [
        "# Sub-D Dynamic ChiNext Proxy R2-Removed Branch Layer 8 Overheat Three-Direction Scan",
        "",
        "## Run Metadata",
        "",
        f"- Run folder: `{run_folder}`",
        "- Layer: `Layer 8` after R2 removal, rejected target-vol, rejected momentum decay, and selected NAV defense.",
        "- Entrypoint: `run_subd_proxy_dynamic_cyb_r2none_layer8_overheat_three_directions_scan.py`",
        "",
        "## Research Question",
        "",
        "Test three overheat-control directions on the two Layer 7 selected NAV-defense lines.",
        "",
        "## Three Directions",
        "",
        "- `fixed_same_side`: MA60 bias and 20-day bias-momentum same-side overheat with fixed enter/exit thresholds.",
        "- `adaptive_quantile`: same-side overheat with per-asset rolling 252-session bias quantile thresholds.",
        "- `score_veto`: rebuild the signal with different `SCORE_MAX` values.",
        "",
        "## Carried Lines",
        "",
        f"- `main_nav_r2_removed`: `{selected_nav_label(CARRY_LINES[0])}`.",
        f"- `return_watch_nav_r2_removed`: `{selected_nav_label(CARRY_LINES[1])}`.",
        "",
        "## Data Snapshot",
        "",
        f"- Start/end: `{meta['data_snapshot']['start']}` to `{meta['data_snapshot']['end']}`.",
        f"- Rows: `{meta['data_snapshot']['rows']}`.",
        "- Pool: QQQ/EWG/EWJ/GLD from 2007 start; ChiNext joins when its own data exists.",
        "- 10Y is N/A because 2432 sessions is less than 2520 trading days.",
        "",
        "## Cost and Execution Assumptions",
        "",
        f"- One-way cost: `{ONE_WAY_COST}`.",
        "- Overheat scale is set at T close and effective next session.",
        "- Overheat costs are included through final-exposure recomputation.",
        "- Calendar: A-share trading days; US adjusted closes are forward-filled onto that calendar for this proxy diagnostic.",
        "- Trades involving a forward-filled trade leg are blocked by the base staged-entry path for that day.",
        "",
        "## Selection By Direction",
        "",
        "| Line | Direction | Selected/Best | Role | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Full Ann Delta pp | Full MDD Improve pp | Effect Days Full | Pass | Reason |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for _, row in direction_selection.iterrows():
        lines.append(
            "| "
            f"{row['line_id']} | {row['overheat_direction']} | `{row['candidate']}` | {row['selection_role']} | "
            f"{pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{pct(row['ann_return_last_10y'])} | {pct(row['max_dd_last_10y'])} | "
            f"{pct(row['ann_return_last_5y'])} | {pct(row['max_dd_last_5y'])} | "
            f"{pct(row['ann_return_last_3y'])} | {pct(row['max_dd_last_3y'])} | "
            f"{pct(row['ann_return_last_1y'])} | {pct(row['max_dd_last_1y'])} | "
            f"{fmt_num(row['ann_delta_full_pp'])} | {fmt_num(row['mdd_improve_full_pp'])} | "
            f"{pct(row['effect_day_ratio_full'])} | {bool(row['layer8_pass'])} | {row['pass_reason']} |"
        )
    lines.extend(
        [
            "",
            "## Comparison List",
            "",
            "| Candidate | Type | Line | Direction | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Notes |",
            "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for _, row in comparison_list.iterrows():
        lines.append(
            "| "
            f"`{row['candidate']}` | {row['candidate_type']} | {row['line_id']} | {row['overheat_direction']} | "
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
            f"- Decision: `{decision}`.",
            f"- Stability label: `{stability}`.",
            f"- Passing direction count: `{pass_count}`.",
            "",
            "## Decision",
            "",
            "- This scan reports per-direction pass/fail only.",
            "- Candidates compare only against their own Layer 7 NAV-defense baseline.",
            "- Stop here before combining overheat directions or moving to a later layer.",
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
    patch_layer8_helpers()
    run_folder.mkdir(parents=True, exist_ok=True)
    daily_dir = run_folder / "daily_outputs"
    daily_dir.mkdir(parents=True, exist_ok=True)

    prices, sources = layer0.build_proxy_panel(start_date, end_date)
    base_features = layer8.build_bias_features(prices)
    base_curves = {
        line.line_id: build_line_curve(prices, end_date, line, DEFAULT_SCORE_MAX)
        for line in CARRY_LINES
    }

    curves: list[pd.DataFrame] = []
    for line in CARRY_LINES:
        base_curve = base_curves[line.line_id]
        curves.append(layer8.apply_no_new_overheat(base_curve, line))

        for case in layer8.FIXED_SAME_SIDE_CASES:
            curves.append(
                layer8.apply_overheat_overlay_to_line(
                    base_curve,
                    line,
                    "fixed_same_side",
                    layer8.fixed_label(case),
                    layer8.fixed_features(base_features, case),
                    case.derisk_scale,
                    case.recovery_mode,
                )
            )

        for case in layer8.ADAPTIVE_QUANTILE_CASES:
            curves.append(
                layer8.apply_overheat_overlay_to_line(
                    base_curve,
                    line,
                    "adaptive_quantile",
                    layer8.adaptive_label(case),
                    layer8.build_adaptive_features(base_features, case),
                    case.derisk_scale,
                    case.recovery_mode,
                )
            )

        for score_max in layer8.SCORE_MAX_CASES:
            if abs(float(score_max) - DEFAULT_SCORE_MAX) < 1e-12:
                continue
            score_curve = build_line_curve(prices, end_date, line, score_max)
            curves.append(layer8.apply_score_max_candidate(score_curve, line, score_max))

    layer8.mark_effect_vs_baseline(curves)

    summary_rows = []
    for curve in curves:
        for segment, label, start, reason in layer1.window_specs(prices.index):
            summary_rows.append(layer8.summarize_curve(curve, segment, label, start, reason))
    scan_summary = pd.DataFrame(summary_rows)
    window_metrics = layer8.build_window_metrics(scan_summary)
    direction_selection = layer8.select_by_direction(window_metrics)
    original_reference = original_full_reference(prices, end_date)
    comparison_list = layer8.build_comparison_list(window_metrics, direction_selection, original_reference)
    daily = layer8.daily_output_frame(curves)

    scan_summary.to_csv(run_folder / "scan_summary.csv", index=False, encoding="utf-8-sig")
    window_metrics.to_csv(run_folder / "window_metrics.csv", index=False, encoding="utf-8-sig")
    direction_selection.to_csv(run_folder / "direction_selection.csv", index=False, encoding="utf-8-sig")
    comparison_list.to_csv(run_folder / "comparison_list.csv", index=False, encoding="utf-8-sig")
    daily.to_csv(daily_dir / "r2none_overheat_three_directions_daily_curves.csv", index=False, encoding="utf-8-sig")
    sources.to_csv(run_folder / "sources.csv", index=False, encoding="utf-8-sig")

    pass_count = int(direction_selection["layer8_pass"].astype(bool).sum())
    command = (
        "python run_subd_proxy_dynamic_cyb_r2none_layer8_overheat_three_directions_scan.py "
        f"--start-date {start_date.date()} --end-date {end_date.date()} --run-folder {run_folder}"
    )
    metadata_path = run_folder / "scan_meta.json"
    meta = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    meta.update(
        {
            "phase": "scan_complete_unfinalized",
            "scan_type": "layer8_overheat_three_direction_scan_after_r2_removed_nav_defense",
            "parameter_group": "layer8_overheat_three_directions_after_r2_removed_nav_defense",
            "baseline": {
                "rule": "two Layer 7 selected NAV-defense lines before adding overheat; SCORE_MAX=5.0 for score-veto baseline",
                "candidates": [line_base_candidate(line) for line in CARRY_LINES],
            },
            "three_directions": {
                "fixed_same_side": "fixed MA60 bias and 20-day bias momentum same-side thresholds",
                "adaptive_quantile": "per-asset rolling 252-session bias quantile thresholds, same-side trigger",
                "score_veto": "rebuild the signal with different SCORE_MAX values",
            },
            "fixed_same_side_grid": [case.__dict__ for case in layer8.FIXED_SAME_SIDE_CASES],
            "adaptive_quantile_grid": [case.__dict__ for case in layer8.ADAPTIVE_QUANTILE_CASES],
            "score_max_grid": [layer8.score_max_label(v) for v in layer8.SCORE_MAX_CASES],
            "carry_lines": [
                {
                    "line_id": line.line_id,
                    "selected_layer7_candidate": selected_nav_label(line),
                    "lookback": int(line.lookback),
                    "r2_threshold": None,
                    "switch_buffer": float(line.switch_buffer),
                    "entry_fraction": float(line.entry_fraction),
                    "momentum_decay": None,
                    "nav_enter": None if line.nav_enter is None else float(line.nav_enter),
                    "nav_exit": None if line.nav_exit is None else float(line.nav_exit),
                    "nav_scale": None if line.nav_scale is None else float(line.nav_scale),
                }
                for line in CARRY_LINES
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
                "overheat_rebalance_cost_included": True,
            },
            "execution_assumptions": {
                "signal": "close-to-close weighted-slope ranking with R2 removed, switch buffer, and staged entry",
                "target_vol": "disabled because Layer 5 rejected target-vol for both carried lines",
                "momentum_decay": "disabled because Layer 6 rejected momentum decay for both carried lines",
                "nav_defense": "Layer 7 selected NAV-defense line is included before testing overheat",
                "overheat": "T close overheat state sets next-session scale; effective scale is shifted one session",
                "adaptive_quantile_threshold": "rolling bias quantiles use prior sessions only via shift(1)",
                "mixed_market_calendar": "diagnostic A-share calendar with US proxy forward-filled; base trades on stale trade legs blocked",
            },
            "pass_rule": {
                "mdd_improve_eps_pp": layer8.MDD_IMPROVE_EPS_PP,
                "available_windows": list(layer8.AVAILABLE_PASS_SEGMENTS),
                "return_lag_tolerance_pp": {"full": 1.0, "last_5y": 1.0, "last_3y": 3.0, "last_1y": 3.0},
                "material_effect": "effect_day_ratio_full must be positive",
            },
            "direction_selection": json.loads(direction_selection.to_json(orient="records")),
            "comparison_reference": {
                "original_full_strategy_candidate": "orig_full_v1_1_reference",
                "original_default_params": {
                    "lookback": subd.LOOKBACK,
                    "r2_threshold": v11.R2_THRESHOLD,
                    "switch_buffer": v11.SWITCH_BUFFER,
                    "entry_fraction": v11.INITIAL_ENTRY_FRACTION,
                    "target_vol": v11.TARGET_VOL,
                    "overheat_enter": v11.OVERHEAT_ENTER,
                    "overheat_exit": v11.OVERHEAT_EXIT,
                    "overheat_derisk_scale": v11.OVERHEAT_DERISK_SCALE,
                },
            },
            "outputs": {
                "scan_summary": str(run_folder / "scan_summary.csv"),
                "window_metrics": str(run_folder / "window_metrics.csv"),
                "direction_selection": str(run_folder / "direction_selection.csv"),
                "comparison_list": str(run_folder / "comparison_list.csv"),
                "daily_curves": str(daily_dir / "r2none_overheat_three_directions_daily_curves.csv"),
                "sources": str(run_folder / "sources.csv"),
                "record": str(run_folder / "record.md"),
                "scan_meta": str(run_folder / "scan_meta.json"),
                "command_log": str(run_folder / "command_log.txt"),
            },
            "decision": (
                "carry_forward_overheat_pass_candidates"
                if pass_count > 0
                else "do_not_add_layer8_overheat_keep_layer7_nav_lines"
            ),
            "stability_label": "overheat_direction_pass" if pass_count > 0 else "no_direction_pass_diagnostic",
            "git_branch_after": git_value(["branch", "--show-current"]),
            "git_commit_after": git_value(["rev-parse", "HEAD"]),
            "git_status_after": git_value(["status", "--short"]),
            "command": command,
            "elapsed_sec": round(time.time() - started, 3),
        }
    )
    metadata_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    write_record(run_folder, direction_selection, comparison_list, sources, meta)

    with (run_folder / "command_log.txt").open("a", encoding="utf-8") as fh:
        fh.write("\n[scan]\n")
        fh.write(f"cwd={Path.cwd()}\n")
        fh.write(command + "\n")
        fh.write(f"elapsed_sec={meta['elapsed_sec']}\n")

    print(f"WROTE {run_folder / 'scan_summary.csv'}")
    print(f"WROTE {run_folder / 'window_metrics.csv'}")
    print(f"WROTE {run_folder / 'direction_selection.csv'}")
    print(f"WROTE {run_folder / 'comparison_list.csv'}")
    print(f"WROTE {daily_dir / 'r2none_overheat_three_directions_daily_curves.csv'}")
    display_cols = [
        "line_id",
        "overheat_direction",
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
        "effect_day_ratio_full",
        "layer8_pass",
        "pass_reason",
    ]
    print(direction_selection[display_cols].to_string(index=False))


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
