from __future__ import annotations

import argparse
import json
import math
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd

import run_subd_proxy_dynamic_cyb_layer0 as layer0
import run_subd_proxy_dynamic_cyb_layer1_scan as layer1
import run_subd_proxy_dynamic_cyb_layer2_r2_scan as layer2
import run_subd_proxy_dynamic_cyb_layer3_switch_buffer_scan as layer3


DEFAULT_START = pd.Timestamp("2007-01-01")
DEFAULT_END = pd.Timestamp("2016-12-30")
DEFAULT_RUN_FOLDER = Path(
    "quant_param_scan_runs"
    "/20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_r2_removed_branch_layer3_switch_buffer_after_r2_removed"
)

PRIMARY_LOOKBACK = 28
LINE_GRID: tuple[tuple[int, str], ...] = (
    (28, "layer1_primary_r2_removed"),
    (26, "layer1_left_neighbor_r2_removed"),
    (30, "layer1_right_neighbor_r2_removed"),
    (32, "layer1_return_peak_watch_r2_removed"),
    (25, "original_lookback_r2_removed"),
)
SWITCH_BUFFER_GRID = (1.00, 1.02, 1.03, 1.05, 1.08, 1.10, 1.15, 1.20)
ONE_WAY_COST = 0.001
TRADING_DAYS = 252
SEGMENTS = ("full", "last_10y", "last_5y", "last_3y", "last_1y")
AVAILABLE_PASS_SEGMENTS = ("full", "last_5y", "last_3y", "last_1y")
MDD_IMPROVE_EPS_PP = 0.01


def git_value(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def buffer_label(value: float) -> str:
    return f"{float(value):.2f}".replace(".", "p")


def candidate_label(lookback: int, switch_buffer: float) -> str:
    return f"lb_{lookback}_r2_none_buf_{buffer_label(switch_buffer)}"


def pct(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value) * 100:.2f}%"


def fmt(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value):.2f}"


def run_signal_with_switch_buffer(
    prices: pd.DataFrame,
    lookback: int,
    switch_buffer: float,
    line_role: str,
    score_frame: pd.DataFrame,
    r2_frame: pd.DataFrame,
) -> pd.DataFrame:
    flags = prices.attrs.get("price_ffill_flags")
    if isinstance(flags, pd.DataFrame):
        flags = flags.copy()
        flags.index = pd.DatetimeIndex(flags.index).normalize()
        flags = flags.reindex(pd.DatetimeIndex(prices.index).normalize()).fillna(False).astype(bool)
    else:
        flags = pd.DataFrame(False, index=pd.DatetimeIndex(prices.index).normalize(), columns=list(layer0.PROXY_ASSETS))

    nav = 1.0
    holding = "CASH"
    trade_count = 0
    buffer_blocked_count = 0
    rows = []
    label = candidate_label(lookback, switch_buffer)

    for idx, date in enumerate(prices.index):
        prev_nav = nav
        prev_holding = holding
        gross_return = 0.0
        if idx > 0 and prev_holding != "CASH":
            prev_px = prices.iloc[idx - 1].get(prev_holding, np.nan)
            curr_px = prices.iloc[idx].get(prev_holding, np.nan)
            if pd.isna(prev_px) or pd.isna(curr_px) or float(prev_px) <= 0 or float(curr_px) <= 0:
                raise RuntimeError(f"missing close for held asset {prev_holding} on {pd.Timestamp(date).date()}")
            gross_return = float(curr_px / prev_px - 1.0)

        score_row = score_frame.loc[date]
        r2_row = r2_frame.loc[date]
        valid_scores = {code: float(score) for code, score in score_row.dropna().items()}

        target, best_candidate, best_score, current_score, buffer_blocked = layer3.target_from_scores(
            valid_scores,
            prev_holding,
            switch_buffer,
        )
        if buffer_blocked:
            buffer_blocked_count += 1

        turnover = 0.0
        cost = 0.0
        stale_assets: list[str] = []
        trade_blocked = False
        blocked_target: str | None = None

        nav *= 1.0 + gross_return
        if target != prev_holding:
            stale_assets = [
                code
                for code in layer1.trade_leg_assets(prev_holding, target)
                if layer1.price_is_ffill(flags, date, code)
            ]
            if stale_assets:
                trade_blocked = True
                blocked_target = target
                target = prev_holding
            else:
                turnover = (1.0 if prev_holding != "CASH" else 0.0) + (1.0 if target != "CASH" else 0.0)
                cost = turnover * ONE_WAY_COST
                if cost:
                    nav *= 1.0 - cost
                if turnover > 1e-12:
                    trade_count += 1
                holding = target

        if target == prev_holding:
            holding = prev_holding

        row = {
            "date": date,
            "candidate": label,
            "line_role": line_role,
            "lookback": lookback,
            "r2_threshold": np.nan,
            "r2_label": "none",
            "switch_buffer": float(switch_buffer),
            "buffer_label": buffer_label(switch_buffer),
            "position_before": prev_holding,
            "position": holding,
            "best_candidate": best_candidate,
            "best_candidate_score": best_score,
            "current_score": current_score,
            "buffer_blocked": buffer_blocked,
            "buffer_blocked_count": buffer_blocked_count,
            "gross_return": gross_return,
            "turnover": turnover,
            "cost": cost,
            "return": nav / prev_nav - 1.0,
            "nav": nav,
            "trade_count": trade_count,
            "trade_blocked_by_stale_price": trade_blocked,
            "blocked_trade_target": blocked_target,
            "stale_price_trade_assets": ",".join(stale_assets),
        }
        for code in layer0.PROXY_ASSETS:
            row[f"score_{code}"] = valid_scores.get(code, math.nan)
            row[f"r2_{code}"] = r2_row.get(code, math.nan)
            row[f"price_ffill_{code}"] = layer1.price_is_ffill(flags, date, code)
        rows.append(row)

    return pd.DataFrame(rows).set_index("date")


def max_drawdown(nav: pd.Series) -> float:
    peak = nav.astype(float).cummax().clip(lower=1.0)
    return float((nav.astype(float) / peak - 1.0).min())


def summarize_curve(
    curve: pd.DataFrame,
    segment: str,
    label: str,
    start: pd.Timestamp | None,
    reason: str,
) -> dict[str, object]:
    first = curve.iloc[0]
    base = {
        "candidate": str(first["candidate"]),
        "line_role": str(first["line_role"]),
        "lookback": int(first["lookback"]),
        "r2_threshold": np.nan,
        "r2_label": "none",
        "switch_buffer": float(first["switch_buffer"]),
        "buffer_label": str(first["buffer_label"]),
        "segment": segment,
        "window": label,
        "end": curve.index[-1].date().isoformat(),
    }
    if start is None:
        return {
            **base,
            "start": "",
            "rows": np.nan,
            "ann_return": np.nan,
            "ann_vol": np.nan,
            "max_dd": np.nan,
            "sharpe_repo": np.nan,
            "cash_days": np.nan,
            "trades": np.nan,
            "cost_total": np.nan,
            "turnover_total": np.nan,
            "holding_day_ratio": np.nan,
            "buffer_blocked_days": np.nan,
            "reason": reason,
        }
    sub = curve.loc[curve.index >= start].copy()
    ret = sub["return"].astype(float).fillna(0.0)
    wealth = (1.0 + ret).cumprod()
    years = len(sub) / TRADING_DAYS
    ann_vol = float(ret.std(ddof=0) * math.sqrt(TRADING_DAYS))
    sharpe = float(ret.mean() / ret.std(ddof=0) * math.sqrt(TRADING_DAYS)) if ret.std(ddof=0) > 0 else math.nan
    return {
        **base,
        "start": sub.index[0].date().isoformat(),
        "rows": int(len(sub)),
        "ann_return": float(wealth.iloc[-1] ** (1.0 / years) - 1.0),
        "ann_vol": ann_vol,
        "max_dd": max_drawdown(wealth),
        "sharpe_repo": sharpe,
        "cash_days": int((sub["position"] == "CASH").sum()),
        "trades": int((sub["turnover"].astype(float) > 1e-12).sum()),
        "cost_total": float(sub["cost"].sum()),
        "turnover_total": float(sub["turnover"].sum()),
        "holding_day_ratio": float((sub["position"] != "CASH").mean()),
        "buffer_blocked_days": int(sub["buffer_blocked"].astype(bool).sum()),
        "reason": reason,
    }


def build_window_metrics(scan_summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for candidate, group in scan_summary.groupby("candidate", sort=False):
        first = group.iloc[0]
        baseline_candidate = candidate_label(int(first["lookback"]), 1.00)
        row: dict[str, object] = {
            "candidate": candidate,
            "baseline_candidate": baseline_candidate,
            "line_role": first["line_role"],
            "lookback": int(first["lookback"]),
            "r2_threshold": np.nan,
            "r2_label": "none",
            "switch_buffer": float(first["switch_buffer"]),
            "buffer_label": first["buffer_label"],
        }
        for segment in SEGMENTS:
            sub = group[group["segment"].eq(segment)]
            if sub.empty:
                row[f"ann_return_{segment}"] = np.nan
                row[f"max_dd_{segment}"] = np.nan
                row[f"reason_{segment}"] = "missing segment"
            else:
                source = sub.iloc[0]
                for col in (
                    "ann_return",
                    "ann_vol",
                    "max_dd",
                    "sharpe_repo",
                    "trades",
                    "cost_total",
                    "turnover_total",
                    "holding_day_ratio",
                    "buffer_blocked_days",
                ):
                    row[f"{col}_{segment}"] = source[col]
                row[f"reason_{segment}"] = source["reason"]

        base_rows = scan_summary[scan_summary["candidate"].eq(baseline_candidate)]
        for segment in SEGMENTS:
            base_sub = base_rows[base_rows["segment"].eq(segment)]
            if base_sub.empty:
                row[f"ann_delta_{segment}_pp"] = np.nan
                row[f"mdd_improve_{segment}_pp"] = np.nan
                row[f"trade_delta_{segment}"] = np.nan
            else:
                base = base_sub.iloc[0]
                ann = row.get(f"ann_return_{segment}", np.nan)
                dd = row.get(f"max_dd_{segment}", np.nan)
                trades = row.get(f"trades_{segment}", np.nan)
                row[f"ann_delta_{segment}_pp"] = (
                    (ann - base["ann_return"]) * 100.0 if pd.notna(ann) and pd.notna(base["ann_return"]) else np.nan
                )
                row[f"mdd_improve_{segment}_pp"] = (
                    (dd - base["max_dd"]) * 100.0 if pd.notna(dd) and pd.notna(base["max_dd"]) else np.nan
                )
                row[f"trade_delta_{segment}"] = trades - base["trades"] if pd.notna(trades) and pd.notna(base["trades"]) else np.nan
        rows.append(row)

    out = pd.DataFrame(rows).sort_values(["lookback", "switch_buffer"])
    return apply_pass_flags(out)


def apply_pass_flags(window_metrics: pd.DataFrame) -> pd.DataFrame:
    out = window_metrics.copy()
    pass_rows = []
    for _, row in out.iterrows():
        if abs(float(row["switch_buffer"]) - 1.0) < 1e-12:
            pass_rows.append(
                {
                    "dd_improve_window_count": 0,
                    "return_tolerance_ok": False,
                    "full_mdd_improved": False,
                    "layer3_pass": False,
                    "pass_reason": "baseline/no switch buffer",
                }
            )
            continue
        dd_count = 0
        tolerance_ok = True
        for segment in AVAILABLE_PASS_SEGMENTS:
            mdd_improve = row.get(f"mdd_improve_{segment}_pp", np.nan)
            ann_delta = row.get(f"ann_delta_{segment}_pp", np.nan)
            if pd.notna(mdd_improve) and float(mdd_improve) > MDD_IMPROVE_EPS_PP:
                dd_count += 1
            tolerance = 1.0 if segment in {"full", "last_5y"} else 3.0
            if pd.isna(ann_delta) or float(ann_delta) < -tolerance:
                tolerance_ok = False
        full_mdd = row.get("mdd_improve_full_pp", np.nan)
        full_mdd_improved = bool(pd.notna(full_mdd) and float(full_mdd) > MDD_IMPROVE_EPS_PP)
        layer3_pass = bool(full_mdd_improved and dd_count >= 3 and tolerance_ok)
        reason = "pass" if layer3_pass else f"full_mdd={full_mdd_improved};dd_windows={dd_count};return_tol={tolerance_ok}"
        pass_rows.append(
            {
                "dd_improve_window_count": dd_count,
                "return_tolerance_ok": tolerance_ok,
                "full_mdd_improved": full_mdd_improved,
                "layer3_pass": layer3_pass,
                "pass_reason": reason,
            }
        )
    return pd.concat([out.reset_index(drop=True), pd.DataFrame(pass_rows)], axis=1)


def select_candidate(window_metrics: pd.DataFrame) -> dict[str, object]:
    passed = window_metrics[window_metrics["layer3_pass"].astype(bool)].copy()
    primary_passed = passed[passed["lookback"].eq(PRIMARY_LOOKBACK)].copy()
    if not primary_passed.empty:
        selected = primary_passed.sort_values(
            ["mdd_improve_full_pp", "ann_return_full"],
            ascending=[False, False],
        ).iloc[0].to_dict()
        decision = "carry_forward_r2_removed_switch_buffer_pass"
        stability = "primary_drawdown_pass"
    elif not passed.empty:
        selected = passed.sort_values(["ann_return_full", "mdd_improve_full_pp"], ascending=[False, False]).iloc[0].to_dict()
        decision = "watch_nonprimary_switch_buffer_pass"
        stability = "nonprimary_pass"
    else:
        baseline = window_metrics[
            window_metrics["lookback"].eq(PRIMARY_LOOKBACK) & window_metrics["switch_buffer"].eq(1.0)
        ].iloc[0].to_dict()
        selected = baseline
        decision = "do_not_add_switch_buffer_keep_r2_removed_baseline"
        stability = "no_pass_keep_r2_removed"
    return {"selected": selected, "decision": decision, "stability_label": stability}


def original_full_reference(prices: pd.DataFrame, end_date: pd.Timestamp) -> dict[str, object]:
    row = layer2.original_full_reference(prices, end_date)
    row["candidate_type"] = "original_full_strategy_reference"
    row["lookback"] = 25
    row["r2_threshold"] = 0.20
    row["switch_buffer"] = 1.05
    row["notes"] = "Full official V1.1 chain; context only, not Layer3 pass baseline"
    return row


def row_from_window(source: dict[str, object], ctype: str, notes: str) -> dict[str, object]:
    row = {
        "candidate": source["candidate"],
        "candidate_type": ctype,
        "lookback": source.get("lookback", ""),
        "r2_threshold": source.get("r2_threshold", np.nan),
        "switch_buffer": source.get("switch_buffer", np.nan),
        "notes": notes,
    }
    for segment in SEGMENTS:
        row[f"ann_return_{segment}"] = source.get(f"ann_return_{segment}", np.nan)
        row[f"max_dd_{segment}"] = source.get(f"max_dd_{segment}", np.nan)
        row[f"reason_{segment}"] = source.get(f"reason_{segment}", "")
    return row


def build_comparison_list(
    window_metrics: pd.DataFrame,
    selected: dict[str, object],
    full_reference: dict[str, object],
) -> pd.DataFrame:
    labels = [
        (candidate_label(28, 1.00), "r2_removed_layer2_baseline", "R2 removed baseline carried from Layer2 reset"),
        (candidate_label(28, 1.05), "r2_removed_original_buffer", "R2 removed primary with original switch buffer 1.05"),
        (candidate_label(28, 1.08), "return_watch_buffer", "R2 removed primary with strongest full-sample annualized return among passing buffers"),
        (candidate_label(28, 1.15), "drawdown_watch_buffer", "R2 removed primary with strongest full-sample drawdown improvement among passing buffers"),
        (str(selected["candidate"]), "layer3_selected", "Selected candidate under Layer3 pass rule"),
        (candidate_label(26, 1.00), "left_neighbor_baseline", "Layer1 left neighbor with R2 removed"),
        (candidate_label(30, 1.00), "right_neighbor_baseline", "Layer1 right neighbor with R2 removed"),
        (candidate_label(32, 1.00), "return_peak_watch_baseline", "Layer1 return peak watch with R2 removed"),
        (candidate_label(25, 1.05), "original_lookback_r2_removed_buffer", "Original lookback with R2 removed and buffer 1.05"),
    ]
    rows = []
    seen: set[str] = set()
    for label, ctype, notes in labels:
        if label in seen:
            continue
        seen.add(label)
        sub = window_metrics[window_metrics["candidate"].eq(label)]
        if not sub.empty:
            rows.append(row_from_window(sub.iloc[0].to_dict(), ctype, notes))
    rows.append(full_reference)
    return pd.DataFrame(rows)


def daily_output_frame(curves: list[pd.DataFrame]) -> pd.DataFrame:
    keep = [
        "candidate",
        "line_role",
        "lookback",
        "r2_label",
        "switch_buffer",
        "position_before",
        "position",
        "best_candidate",
        "best_candidate_score",
        "current_score",
        "buffer_blocked",
        "buffer_blocked_count",
        "gross_return",
        "turnover",
        "cost",
        "return",
        "nav",
        "trade_count",
        "trade_blocked_by_stale_price",
        "blocked_trade_target",
        "stale_price_trade_assets",
    ]
    return pd.concat([curve[[col for col in keep if col in curve.columns]] for curve in curves], axis=0).reset_index()


def write_record(
    run_folder: Path,
    window_metrics: pd.DataFrame,
    comparison_list: pd.DataFrame,
    selection: dict[str, object],
    sources: pd.DataFrame,
    meta: dict[str, object],
) -> None:
    selected = selection["selected"]
    primary = window_metrics[window_metrics["lookback"].eq(PRIMARY_LOOKBACK)].sort_values("switch_buffer")
    passing = window_metrics[window_metrics["layer3_pass"].astype(bool)].sort_values(
        ["ann_return_full", "mdd_improve_full_pp"],
        ascending=[False, False],
    )
    top = passing if not passing.empty else window_metrics[window_metrics["switch_buffer"].ne(1.0)].sort_values(
        "mdd_improve_full_pp",
        ascending=False,
    ).head(10)
    lines = [
        "# Sub-D Dynamic ChiNext Proxy R2-Removed Branch Layer 3 Switch Buffer Scan",
        "",
        "## Run Metadata",
        "",
        f"- Run folder: `{run_folder}`",
        "- Layer: `Layer 3` after resetting Layer 2 to `R2 removed`.",
        "- Strategy: dynamic ChiNext proxy pool, 2007-2016.",
        "- Entrypoint: `run_subd_proxy_dynamic_cyb_r2none_layer3_switch_buffer_scan.py`",
        "",
        "## Research Question",
        "",
        "After removing the R2 signal-quality filter, test whether adding a switch buffer improves drawdown without giving back too much return.",
        "",
        "## Implementation Anchor",
        "",
        "- Data loader reused from `run_subd_proxy_dynamic_cyb_layer0.py`.",
        "- Score precompute reused from `run_subd_proxy_dynamic_cyb_layer2_r2_scan.py`.",
        "- Target switch rule reused from `run_subd_proxy_dynamic_cyb_layer3_switch_buffer_scan.py`.",
        "- R2 is not used to filter scores in this branch.",
        "- No staged entry, target-vol, momentum decay, NAV defense, or overheat in this layer.",
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
        "- Calendar: A-share trading days; US adjusted closes are forward-filled onto that calendar for this proxy diagnostic.",
        "- Trades involving a forward-filled trade leg are blocked for that day.",
        "",
        "## Runtime Override Plan",
        "",
        f"- Lines: `{[(lb, role) for lb, role in LINE_GRID]}`.",
        f"- Switch-buffer grid: `{[buffer_label(x) for x in SWITCH_BUFFER_GRID]}`.",
        "- Baseline: same lookback with `r2_none` and switch buffer `1.00`.",
        f"- Pass rule: Full maxDD improves by more than `{MDD_IMPROVE_EPS_PP:.2f}pp`; at least 3 of 4 available windows improve maxDD; Full/5Y annualized return lag <=1pp and 3Y/1Y lag <=3pp.",
        "",
        "## Commands",
        "",
        f"- `{meta['command']}`",
        "",
        "## Output Files",
        "",
        "- `scan_summary.csv`",
        "- `window_metrics.csv`",
        "- `comparison_list.csv`",
        "- `daily_outputs/r2none_switch_buffer_daily_curves.csv`",
        "- `sources.csv`",
        "",
        "## Full-Sample Results",
        "",
        "| Candidate | Full Ann. | Full MDD | Full Ann Delta pp | Full MDD Improve pp | 5Y Ann. | 3Y Ann. | 1Y Ann. | Trades Full | Blocked Days Full | Pass | Reason |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for _, row in primary.iterrows():
        lines.append(
            "| "
            f"`{row['candidate']}` | {pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{fmt(row['ann_delta_full_pp'])} | {fmt(row['mdd_improve_full_pp'])} | "
            f"{pct(row['ann_return_last_5y'])} | {pct(row['ann_return_last_3y'])} | {pct(row['ann_return_last_1y'])} | "
            f"{int(row['trades_full']) if pd.notna(row['trades_full']) else 'N/A'} | "
            f"{int(row['buffer_blocked_days_full']) if pd.notna(row['buffer_blocked_days_full']) else 'N/A'} | "
            f"{bool(row['layer3_pass'])} | {row['pass_reason']} |"
        )
    lines.extend(
        [
            "",
            "## Passing Or Best Candidates",
            "",
            "| Candidate | Role | Full Ann. | Full MDD | Full MDD Improve pp | DD Improve Windows | Pass |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
    )
    for _, row in top.iterrows():
        lines.append(
            "| "
            f"`{row['candidate']}` | {row['line_role']} | {pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{fmt(row['mdd_improve_full_pp'])} | {int(row['dd_improve_window_count'])} | {bool(row['layer3_pass'])} |"
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
            "## Window Results",
            "",
            f"- Selected candidate: `{selected['candidate']}`.",
            f"- Selected Full: `{pct(selected['ann_return_full'])}` / MDD `{pct(selected['max_dd_full'])}`.",
            f"- Selected 10Y: `N/A` because sample rows are below 2520.",
            f"- Selected 5Y: `{pct(selected['ann_return_last_5y'])}` / MDD `{pct(selected['max_dd_last_5y'])}`.",
            f"- Selected 3Y: `{pct(selected['ann_return_last_3y'])}` / MDD `{pct(selected['max_dd_last_3y'])}`.",
            f"- Selected 1Y: `{pct(selected['ann_return_last_1y'])}` / MDD `{pct(selected['max_dd_last_1y'])}`.",
            "",
            "## Stability Classification",
            "",
            f"- Decision: `{selection['decision']}`.",
            f"- Stability label: `{selection['stability_label']}`.",
            "- 10Y remains N/A by sample length and is not fabricated for strict scanner compatibility.",
            "",
            "## Decision",
            "",
            f"- Decision: `{selection['decision']}`.",
            "- Stop here before staged-entry, target-vol, momentum decay, NAV defense, or overheat layers.",
            "",
            "## User-Facing Summary",
            "",
            f"R2 is removed. Layer 3 selected `{selected['candidate']}` under the documented pass rule.",
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
    lookbacks = sorted({lookback for lookback, _ in LINE_GRID})
    score_cache = {lookback: layer2.precompute_scores(prices, lookback) for lookback in lookbacks}

    curves = []
    summary_rows = []
    for lookback, line_role in LINE_GRID:
        score_frame, r2_frame = score_cache[lookback]
        for switch_buffer in SWITCH_BUFFER_GRID:
            curve = run_signal_with_switch_buffer(
                prices,
                lookback,
                switch_buffer,
                line_role,
                score_frame,
                r2_frame,
            )
            curves.append(curve)
            for segment, label, start, reason in layer1.window_specs(prices.index):
                summary_rows.append(summarize_curve(curve, segment, label, start, reason))

    scan_summary = pd.DataFrame(summary_rows)
    window_metrics = build_window_metrics(scan_summary)
    selection = select_candidate(window_metrics)
    full_reference = original_full_reference(prices, end_date)
    comparison_list = build_comparison_list(window_metrics, selection["selected"], full_reference)
    daily = daily_output_frame(curves)

    scan_summary.to_csv(run_folder / "scan_summary.csv", index=False, encoding="utf-8-sig")
    window_metrics.to_csv(run_folder / "window_metrics.csv", index=False, encoding="utf-8-sig")
    comparison_list.to_csv(run_folder / "comparison_list.csv", index=False, encoding="utf-8-sig")
    daily.to_csv(daily_dir / "r2none_switch_buffer_daily_curves.csv", index=False, encoding="utf-8-sig")
    sources.to_csv(run_folder / "sources.csv", index=False, encoding="utf-8-sig")

    command = (
        "python run_subd_proxy_dynamic_cyb_r2none_layer3_switch_buffer_scan.py "
        f"--start-date {start_date.date()} --end-date {end_date.date()} --run-folder {run_folder}"
    )
    metadata_path = run_folder / "scan_meta.json"
    meta = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    meta.update(
        {
            "phase": "scan_complete_unfinalized",
            "scan_type": "layer3_grid_scan_after_r2_removed",
            "parameter_group": "layer3_switch_buffer_after_r2_removed",
            "baseline": {
                "rule": "Layer2 reset to R2 removed; compare each switch buffer to same-lookback buffer=1.00",
                "primary_candidate": candidate_label(PRIMARY_LOOKBACK, 1.00),
            },
            "candidate_grid": [
                {
                    "lookback": int(lookback),
                    "line_role": line_role,
                    "r2_threshold": None,
                    "switch_buffer": float(buffer),
                }
                for lookback, line_role in LINE_GRID
                for buffer in SWITCH_BUFFER_GRID
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
            "cost_model": {"one_way_cost": ONE_WAY_COST, "stale_trade_guard": True},
            "execution_assumptions": {
                "signal": "close-to-close weighted-slope ranking, score range 0..5, no R2 filter",
                "switch_buffer_rule": "replace current holding only when best_score > current_score * switch_buffer",
                "overlays": "none in this layer beyond switch buffer",
                "mixed_market_calendar": "diagnostic A-share calendar with US proxy forward-filled; trades on stale trade legs blocked",
            },
            "pass_rule": {
                "mdd_improve_eps_pp": MDD_IMPROVE_EPS_PP,
                "available_windows": list(AVAILABLE_PASS_SEGMENTS),
                "return_lag_tolerance_pp": {"full": 1.0, "last_5y": 1.0, "last_3y": 3.0, "last_1y": 3.0},
            },
            "layer3_selection": selection,
            "outputs": {
                "scan_summary": str(run_folder / "scan_summary.csv"),
                "window_metrics": str(run_folder / "window_metrics.csv"),
                "comparison_list": str(run_folder / "comparison_list.csv"),
                "daily_curves": str(daily_dir / "r2none_switch_buffer_daily_curves.csv"),
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
    write_record(run_folder, window_metrics, comparison_list, selection, sources, meta)

    with (run_folder / "command_log.txt").open("a", encoding="utf-8") as fh:
        fh.write("\n[scan]\n")
        fh.write(f"cwd={Path.cwd()}\n")
        fh.write(command + "\n")
        fh.write(f"elapsed_sec={meta['elapsed_sec']}\n")

    print(f"WROTE {run_folder / 'scan_summary.csv'}")
    print(f"WROTE {run_folder / 'window_metrics.csv'}")
    print(f"WROTE {run_folder / 'comparison_list.csv'}")
    print(f"WROTE {daily_dir / 'r2none_switch_buffer_daily_curves.csv'}")
    display_cols = [
        "candidate",
        "line_role",
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
        "trades_full",
        "buffer_blocked_days_full",
        "layer3_pass",
        "pass_reason",
    ]
    primary = window_metrics[window_metrics["lookback"].eq(PRIMARY_LOOKBACK)].sort_values("switch_buffer")
    print(primary[display_cols].to_string(index=False))


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
