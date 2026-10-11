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
import run_subd_proxy_dynamic_cyb_layer2_r2_scan as layer2
import run_subd_six_etf_v1_1 as v11


DEFAULT_START = pd.Timestamp("2007-01-01")
DEFAULT_END = pd.Timestamp("2016-12-30")
DEFAULT_RUN_FOLDER = Path(
    "quant_param_scan_runs"
    "/20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_switch_buffer_layer3_switch_buffer"
)
PRIMARY_LOOKBACK = 28
PRIMARY_R2 = 0.50
LINE_GRID: tuple[tuple[int, float, str], ...] = (
    (28, 0.50, "layer2_primary"),
    (28, 0.40, "r2_neighbor"),
    (32, 0.50, "return_peak_watch"),
    (25, 0.20, "original_layer3"),
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


def candidate_label(lookback: int, r2_threshold: float, switch_buffer: float) -> str:
    return f"lb_{lookback}_r2_{layer2.r2_label(r2_threshold)}_buf_{buffer_label(switch_buffer)}"


def target_from_scores(
    scores: dict[str, float],
    prev_holding: str,
    switch_buffer: float,
) -> tuple[str, str, float, float, bool]:
    if not scores:
        return "CASH", "CASH", math.nan, math.nan, False
    best = max(scores, key=scores.get)
    best_score = float(scores[best])
    current_score = float(scores[prev_holding]) if prev_holding in scores else math.nan
    blocked = False
    target = best
    if (
        prev_holding in scores
        and prev_holding != best
        and switch_buffer > 1.0
        and best_score <= current_score * switch_buffer
    ):
        target = prev_holding
        blocked = True
    return target, best, best_score, current_score, blocked


def run_signal_with_switch_buffer(
    prices: pd.DataFrame,
    lookback: int,
    r2_threshold: float,
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
    label = candidate_label(lookback, r2_threshold, switch_buffer)

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
        valid_scores: dict[str, float] = {}
        for code, score in score_row.dropna().items():
            r2_value = r2_row.get(code, np.nan)
            if pd.notna(r2_value) and float(r2_value) >= float(r2_threshold):
                valid_scores[code] = float(score)

        target, best_candidate, best_score, current_score, buffer_blocked = target_from_scores(
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
            "r2_threshold": float(r2_threshold),
            "r2_label": layer2.r2_label(r2_threshold),
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
        "r2_threshold": float(first["r2_threshold"]),
        "r2_label": str(first["r2_label"]),
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
        baseline_candidate = candidate_label(
            int(first["lookback"]),
            float(first["r2_threshold"]),
            1.00,
        )
        row: dict[str, object] = {
            "candidate": candidate,
            "baseline_candidate": baseline_candidate,
            "line_role": first["line_role"],
            "lookback": int(first["lookback"]),
            "r2_threshold": float(first["r2_threshold"]),
            "r2_label": first["r2_label"],
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
                row[f"ann_return_{segment}"] = sub["ann_return"].iloc[0]
                row[f"max_dd_{segment}"] = sub["max_dd"].iloc[0]
                row[f"reason_{segment}"] = sub["reason"].iloc[0]
                row[f"trades_{segment}"] = sub["trades"].iloc[0]
                row[f"buffer_blocked_days_{segment}"] = sub["buffer_blocked_days"].iloc[0]

        base_rows = scan_summary[scan_summary["candidate"].eq(baseline_candidate)]
        for segment in SEGMENTS:
            base_sub = base_rows[base_rows["segment"].eq(segment)]
            if base_sub.empty:
                row[f"ann_delta_{segment}_pp"] = np.nan
                row[f"mdd_improve_{segment}_pp"] = np.nan
                row[f"trade_delta_{segment}"] = np.nan
            else:
                base_ann = base_sub["ann_return"].iloc[0]
                base_dd = base_sub["max_dd"].iloc[0]
                base_trades = base_sub["trades"].iloc[0]
                ann = row[f"ann_return_{segment}"]
                dd = row[f"max_dd_{segment}"]
                trades = row.get(f"trades_{segment}", np.nan)
                row[f"ann_delta_{segment}_pp"] = (ann - base_ann) * 100.0 if pd.notna(ann) and pd.notna(base_ann) else np.nan
                row[f"mdd_improve_{segment}_pp"] = (dd - base_dd) * 100.0 if pd.notna(dd) and pd.notna(base_dd) else np.nan
                row[f"trade_delta_{segment}"] = trades - base_trades if pd.notna(trades) and pd.notna(base_trades) else np.nan
        rows.append(row)
    out = pd.DataFrame(rows).sort_values(["lookback", "r2_threshold", "switch_buffer"])
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
    primary_passed = passed[
        passed["lookback"].eq(PRIMARY_LOOKBACK) & passed["r2_threshold"].eq(PRIMARY_R2)
    ].copy()
    if not primary_passed.empty:
        selected = primary_passed.sort_values(
            ["ann_return_full", "mdd_improve_full_pp"],
            ascending=[False, False],
        ).iloc[0].to_dict()
        decision = "carry_forward_primary_switch_buffer_pass"
        stability = "primary_pass"
    elif not passed.empty:
        selected = passed.sort_values(["ann_return_full", "mdd_improve_full_pp"], ascending=[False, False]).iloc[0].to_dict()
        decision = "watch_nonprimary_switch_buffer_pass"
        stability = "nonprimary_pass"
    else:
        primary_baseline = window_metrics[
            window_metrics["lookback"].eq(PRIMARY_LOOKBACK)
            & window_metrics["r2_threshold"].eq(PRIMARY_R2)
            & window_metrics["switch_buffer"].eq(1.0)
        ]
        selected = primary_baseline.iloc[0].to_dict()
        decision = "do_not_add_switch_buffer_keep_layer2_primary"
        stability = "no_pass_keep_previous"
    return {"selected": selected, "decision": decision, "stability_label": stability}


def original_full_reference(prices: pd.DataFrame, end_date: pd.Timestamp) -> dict[str, object]:
    row = layer2.original_full_reference(prices, end_date)
    row["candidate_type"] = "original_full_strategy_reference"
    row["notes"] = "Full official V1.1 chain; reference only, not Layer3 pass baseline"
    return row


def row_from_window(source: dict[str, object], candidate: str, ctype: str, notes: str) -> dict[str, object]:
    row = {
        "candidate": candidate,
        "candidate_type": ctype,
        "lookback": source["lookback"],
        "r2_threshold": source["r2_threshold"],
        "switch_buffer": source["switch_buffer"],
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
            candidate_label(28, 0.50, 1.00),
            "layer2_carried_baseline",
            "Layer2 carried primary line before switch buffer",
            None,
        ),
        (
            candidate_label(28, 0.50, 1.05),
            "layer3_primary_original_buffer",
            "Layer2 primary with original switch buffer 1.05",
            None,
        ),
        (
            str(selected["candidate"]),
            "layer3_selected",
            "Selected Layer3 line under the documented pass rule",
            None,
        ),
        (
            candidate_label(28, 0.40, 1.05),
            "r2_neighbor_original_buffer",
            "R2 neighbor with original switch buffer 1.05",
            None,
        ),
        (
            candidate_label(32, 0.50, 1.05),
            "return_peak_watch_original_buffer",
            "Return peak watch line with original switch buffer 1.05",
            None,
        ),
        (
            candidate_label(25, 0.20, 1.05),
            "original_layer3_switch_buffer",
            "Original first-layer parameter plus original R2 0.20 and switch buffer 1.05",
            "orig_layer3_lb25_r2_0p20_buf_1p05",
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
        candidate = output_label or label
        rows.append(row_from_window(match.iloc[0].to_dict(), candidate, ctype, notes))
    rows.append(full_reference)
    return pd.DataFrame(rows)


def pct(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value) * 100:.2f}%"


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
    ].sort_values("switch_buffer")
    top_pass = window_metrics[window_metrics["layer3_pass"].astype(bool)].sort_values(
        ["ann_return_full", "mdd_improve_full_pp"],
        ascending=[False, False],
    ).head(10)
    if top_pass.empty:
        top_pass = window_metrics[window_metrics["switch_buffer"].ne(1.0)].sort_values(
            "mdd_improve_full_pp",
            ascending=False,
        ).head(10)

    lines = [
        "# Sub-D Dynamic ChiNext Proxy Layer 3 Switch-Buffer Scan",
        "",
        "## Run Metadata",
        "",
        f"- Run folder: `{run_folder}`",
        "- Layer: `Layer 3`",
        "- Strategy: dynamic ChiNext proxy pool, 2007-2016.",
        "- Entrypoint: `run_subd_proxy_dynamic_cyb_layer3_switch_buffer_scan.py`",
        "",
        "## Research Question",
        "",
        "Add a switch buffer after the Layer 2 R2 filter. A candidate only replaces the current holding when its score is greater than the current holding score times the buffer.",
        "",
        "## Implementation Anchor",
        "",
        "- Data loader reused from `run_subd_proxy_dynamic_cyb_layer0.py`.",
        "- Score/R2 precompute reused from Layer 2.",
        "- Switch-buffer rule matches `_target_from_scores` in `run_subd_six_etf_v1_1.py`.",
        "- No staged entry, target-vol, or overheat in this layer.",
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
        f"- Lines carried: `{[(lb, r2, role) for lb, r2, role in LINE_GRID]}`.",
        f"- Switch-buffer grid: `{[buffer_label(x) for x in SWITCH_BUFFER_GRID]}`.",
        "- Baseline: same `lookback + R2` with switch buffer `1.00`.",
        f"- Pass rule: Full maxDD improves by more than `{MDD_IMPROVE_EPS_PP:.2f}pp`; at least 3 of the 4 available windows improve maxDD by more than `{MDD_IMPROVE_EPS_PP:.2f}pp`; Full/5Y annualized return lag <=1pp and 3Y/1Y lag <=3pp versus same-line no-buffer baseline.",
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
        "- `daily_outputs/switch_buffer_daily_curves.csv`",
        "- `sources.csv`",
        "",
        "## Primary Line Results",
        "",
        "| Candidate | Full Ann. | Full MDD | Full Ann Delta pp | Full MDD Improve pp | 5Y Ann. | 3Y Ann. | 1Y Ann. | Trades Full | Blocked Days Full | Pass | Reason |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for _, row in primary.iterrows():
        lines.append(
            "| "
            f"{row['candidate']} | {pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{row['ann_delta_full_pp']:.2f} | {row['mdd_improve_full_pp']:.2f} | "
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
    for _, row in top_pass.iterrows():
        lines.append(
            "| "
            f"{row['candidate']} | {row['line_role']} | {pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{row['mdd_improve_full_pp']:.2f} | {int(row['dd_improve_window_count'])} | {bool(row['layer3_pass'])} |"
        )
    lines.extend(
        [
            "",
            "## Comparison List",
            "",
            "| Candidate | Type | Full Ann. | Full MDD | 5Y Ann. | 3Y Ann. | 1Y Ann. | Notes |",
            "|---|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for _, row in comparison_list.iterrows():
        lines.append(
            "| "
            f"{row['candidate']} | {row['candidate_type']} | "
            f"{pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{pct(row['ann_return_last_5y'])} | {pct(row['ann_return_last_3y'])} | {pct(row['ann_return_last_1y'])} | "
            f"{row['notes']} |"
        )
    lines.extend(
        [
            "",
            "## Stability Classification",
            "",
            f"- Selected candidate: `{selected['candidate']}`.",
            f"- Decision: `{selection['decision']}`.",
            f"- Stability label: `{selection['stability_label']}`.",
            "- 10Y remains N/A by sample length and is not fabricated for strict scanner compatibility.",
            "",
            "## Decision",
            "",
            f"- Decision: `{selection['decision']}`.",
            "- Stop here before any staged-entry, target-vol, or overheat layer.",
            "",
            "## User-Facing Summary",
            "",
            f"Layer 3 selected `{selected['candidate']}` under the documented pass rule. See `window_metrics.csv` for all switch-buffer lines.",
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
    lookbacks = sorted({lookback for lookback, _, _ in LINE_GRID})
    score_cache = {lookback: layer2.precompute_scores(prices, lookback) for lookback in lookbacks}

    curves = []
    summary_rows = []
    for lookback, r2_threshold, line_role in LINE_GRID:
        score_frame, r2_frame = score_cache[lookback]
        for switch_buffer in SWITCH_BUFFER_GRID:
            curve = run_signal_with_switch_buffer(
                prices,
                lookback,
                r2_threshold,
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
    full_reference = original_full_reference(prices, end_date)
    selection = select_candidate(window_metrics)
    comparison_list = build_comparison_list(window_metrics, full_reference, selection["selected"])
    daily = pd.concat(curves, axis=0).reset_index()

    scan_summary.to_csv(run_folder / "scan_summary.csv", index=False, encoding="utf-8-sig")
    window_metrics.to_csv(run_folder / "window_metrics.csv", index=False, encoding="utf-8-sig")
    comparison_list.to_csv(run_folder / "comparison_list.csv", index=False, encoding="utf-8-sig")
    daily.to_csv(daily_dir / "switch_buffer_daily_curves.csv", index=False, encoding="utf-8-sig")
    sources.to_csv(run_folder / "sources.csv", index=False, encoding="utf-8-sig")

    metadata_path = run_folder / "scan_meta.json"
    meta = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    command = (
        "python run_subd_proxy_dynamic_cyb_layer3_switch_buffer_scan.py "
        f"--start-date {start_date.date()} --end-date {end_date.date()} --run-folder {run_folder}"
    )
    meta.update(
        {
            "phase": "scan_complete_unfinalized",
            "scan_type": "layer3_grid_scan",
            "parameter_group": "layer3_switch_buffer",
            "baseline": {"rule": "same lookback + R2 with switch_buffer=1.00"},
            "candidate_grid": [
                {
                    "lookback": int(lookback),
                    "r2_threshold": float(r2_threshold),
                    "line_role": line_role,
                    "switch_buffer": float(switch_buffer),
                }
                for lookback, r2_threshold, line_role in LINE_GRID
                for switch_buffer in SWITCH_BUFFER_GRID
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
                "signal": "close-to-close weighted-slope ranking with fixed R2 threshold and switch buffer",
                "switch_buffer_rule": "replace current holding only when best_score > current_score * switch_buffer",
                "overlays": "none in Layer 3 beyond R2 filter and switch buffer",
                "mixed_market_calendar": "diagnostic A-share calendar with US proxy forward-filled; trades on stale trade legs blocked",
            },
            "pass_rule": {
                "mdd_improve_eps_pp": MDD_IMPROVE_EPS_PP,
                "available_windows": list(AVAILABLE_PASS_SEGMENTS),
                "return_lag_tolerance_pp": {"full": 1.0, "last_5y": 1.0, "last_3y": 3.0, "last_1y": 3.0},
            },
            "layer3_selection": selection,
            "comparison_reference": {
                "layer2_baseline_candidate": candidate_label(28, 0.50, 1.00),
                "original_layer3_candidate": "orig_layer3_lb25_r2_0p20_buf_1p05",
                "original_full_strategy_candidate": "orig_full_v1_1_reference",
            },
            "outputs": {
                "scan_summary": str(run_folder / "scan_summary.csv"),
                "window_metrics": str(run_folder / "window_metrics.csv"),
                "comparison_list": str(run_folder / "comparison_list.csv"),
                "daily_curves": str(daily_dir / "switch_buffer_daily_curves.csv"),
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
    print(f"WROTE {daily_dir / 'switch_buffer_daily_curves.csv'}")
    print(
        json.dumps(
            {
                "selected": selection["selected"],
                "decision": selection["decision"],
                "stability_label": selection["stability_label"],
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
    primary = window_metrics[
        window_metrics["lookback"].eq(PRIMARY_LOOKBACK)
        & window_metrics["r2_threshold"].eq(PRIMARY_R2)
    ].sort_values("switch_buffer")
    print(primary.to_string(index=False))


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
