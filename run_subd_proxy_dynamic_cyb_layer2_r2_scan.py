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
import run_subd_six_etf_v1_1 as v11


DEFAULT_START = pd.Timestamp("2007-01-01")
DEFAULT_END = pd.Timestamp("2016-12-30")
DEFAULT_RUN_FOLDER = Path(
    "quant_param_scan_runs"
    "/20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_r2_signal_quality_layer2_r2_threshold"
)
CARRY_LOOKBACKS = (25, 26, 28, 30, 32)
PRIMARY_LOOKBACK = 28
R2_GRID: tuple[float | None, ...] = (None, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60)
SCORE_MIN = 0.0
SCORE_MAX = 5.0
ONE_WAY_COST = 0.001
TRADING_DAYS = 252
SEGMENTS = ("full", "last_10y", "last_5y", "last_3y", "last_1y")
AVAILABLE_PASS_SEGMENTS = ("full", "last_5y", "last_3y", "last_1y")


def git_value(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def r2_label(value: float | None) -> str:
    if value is None:
        return "none"
    return f"{value:.2f}".replace(".", "p")


def candidate_label(lookback: int, r2_threshold: float | None) -> str:
    return f"lb_{lookback}_r2_{r2_label(r2_threshold)}"


def precompute_scores(prices: pd.DataFrame, lookback: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    score_rows = []
    r2_rows = []
    for idx, date in enumerate(prices.index):
        scores: dict[str, float] = {}
        r2_values: dict[str, float] = {}
        if idx >= lookback - 1:
            for code in layer0.PROXY_ASSETS:
                score, r2 = layer1.weighted_slope_score(
                    prices[code].iloc[idx - lookback + 1 : idx + 1],
                    lookback,
                )
                if not math.isnan(r2):
                    r2_values[code] = r2
                if SCORE_MIN < score < SCORE_MAX:
                    scores[code] = score
        score_rows.append({"date": date, **scores})
        r2_rows.append({"date": date, **r2_values})
    score_frame = pd.DataFrame(score_rows).set_index("date").reindex(columns=list(layer0.PROXY_ASSETS))
    r2_frame = pd.DataFrame(r2_rows).set_index("date").reindex(columns=list(layer0.PROXY_ASSETS))
    return score_frame, r2_frame


def run_signal_with_r2(
    prices: pd.DataFrame,
    lookback: int,
    r2_threshold: float | None,
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
    rows = []
    label = candidate_label(lookback, r2_threshold)

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
            if r2_threshold is None or (pd.notna(r2_value) and float(r2_value) >= float(r2_threshold)):
                valid_scores[code] = float(score)
        target = max(valid_scores, key=valid_scores.get) if valid_scores else "CASH"
        best_score = float(valid_scores[target]) if target in valid_scores else math.nan

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
            "lookback": lookback,
            "r2_threshold": np.nan if r2_threshold is None else float(r2_threshold),
            "r2_label": r2_label(r2_threshold),
            "position_before": prev_holding,
            "position": holding,
            "best_candidate": max(valid_scores, key=valid_scores.get) if valid_scores else "CASH",
            "best_candidate_score": best_score,
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


def summarize_curve(curve: pd.DataFrame, segment: str, label: str, start: pd.Timestamp | None, reason: str) -> dict[str, object]:
    candidate = str(curve["candidate"].iloc[0])
    lookback = int(curve["lookback"].iloc[0])
    r2_value = curve["r2_threshold"].iloc[0]
    if start is None:
        return {
            "candidate": candidate,
            "lookback": lookback,
            "r2_threshold": r2_value,
            "r2_label": str(curve["r2_label"].iloc[0]),
            "segment": segment,
            "window": label,
            "start": "",
            "end": curve.index[-1].date().isoformat(),
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
            "reason": reason,
        }
    sub = curve.loc[curve.index >= start].copy()
    ret = sub["return"].astype(float).fillna(0.0)
    wealth = (1.0 + ret).cumprod()
    years = len(sub) / TRADING_DAYS
    ann_return = float(wealth.iloc[-1] ** (1.0 / years) - 1.0)
    ann_vol = float(ret.std(ddof=0) * math.sqrt(TRADING_DAYS))
    sharpe = float(ret.mean() / ret.std(ddof=0) * math.sqrt(TRADING_DAYS)) if ret.std(ddof=0) > 0 else math.nan
    return {
        "candidate": candidate,
        "lookback": lookback,
        "r2_threshold": r2_value,
        "r2_label": str(curve["r2_label"].iloc[0]),
        "segment": segment,
        "window": label,
        "start": sub.index[0].date().isoformat(),
        "end": sub.index[-1].date().isoformat(),
        "rows": int(len(sub)),
        "ann_return": ann_return,
        "ann_vol": ann_vol,
        "max_dd": max_drawdown(wealth),
        "sharpe_repo": sharpe,
        "cash_days": int((sub["position"] == "CASH").sum()),
        "trades": int((sub["turnover"].astype(float) > 1e-12).sum()),
        "cost_total": float(sub["cost"].sum()),
        "turnover_total": float(sub["turnover"].sum()),
        "holding_day_ratio": float((sub["position"] != "CASH").mean()),
        "reason": reason,
    }


def build_window_metrics(scan_summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    baseline_by_lb = {
        int(row["lookback"]): row
        for _, row in scan_summary[
            scan_summary["segment"].eq("full") & scan_summary["r2_label"].eq("none")
        ].iterrows()
    }
    for candidate, group in scan_summary.groupby("candidate", sort=False):
        lookback = int(group["lookback"].iloc[0])
        baseline_candidate = candidate_label(lookback, None)
        row: dict[str, object] = {
            "candidate": candidate,
            "baseline_candidate": baseline_candidate,
            "lookback": lookback,
            "r2_threshold": group["r2_threshold"].iloc[0],
            "r2_label": group["r2_label"].iloc[0],
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
        base_rows = scan_summary[
            scan_summary["candidate"].eq(baseline_candidate)
        ]
        for segment in SEGMENTS:
            base_sub = base_rows[base_rows["segment"].eq(segment)]
            if base_sub.empty:
                row[f"ann_delta_{segment}_pp"] = np.nan
                row[f"mdd_improve_{segment}_pp"] = np.nan
            else:
                base_ann = base_sub["ann_return"].iloc[0]
                base_dd = base_sub["max_dd"].iloc[0]
                ann = row[f"ann_return_{segment}"]
                dd = row[f"max_dd_{segment}"]
                row[f"ann_delta_{segment}_pp"] = (ann - base_ann) * 100.0 if pd.notna(ann) and pd.notna(base_ann) else np.nan
                row[f"mdd_improve_{segment}_pp"] = (dd - base_dd) * 100.0 if pd.notna(dd) and pd.notna(base_dd) else np.nan
        rows.append(row)
    out = pd.DataFrame(rows).sort_values(["lookback", "r2_threshold"], na_position="first")
    return apply_pass_flags(out)


def apply_pass_flags(window_metrics: pd.DataFrame) -> pd.DataFrame:
    out = window_metrics.copy()
    pass_rows = []
    for _, row in out.iterrows():
        if str(row["r2_label"]) == "none":
            pass_rows.append(
                {
                    "dd_improve_window_count": 0,
                    "return_tolerance_ok": False,
                    "full_mdd_improved": False,
                    "layer2_pass": False,
                    "pass_reason": "baseline/no R2",
                }
            )
            continue
        dd_count = 0
        tolerance_ok = True
        for segment in AVAILABLE_PASS_SEGMENTS:
            mdd_improve = row.get(f"mdd_improve_{segment}_pp", np.nan)
            ann_delta = row.get(f"ann_delta_{segment}_pp", np.nan)
            if pd.notna(mdd_improve) and float(mdd_improve) > 0:
                dd_count += 1
            tolerance = 1.0 if segment in {"full", "last_5y"} else 3.0
            if pd.isna(ann_delta) or float(ann_delta) < -tolerance:
                tolerance_ok = False
        full_mdd = row.get("mdd_improve_full_pp", np.nan)
        full_mdd_improved = bool(pd.notna(full_mdd) and float(full_mdd) > 0)
        layer2_pass = bool(full_mdd_improved and dd_count >= 3 and tolerance_ok)
        reason = "pass" if layer2_pass else f"full_mdd={full_mdd_improved};dd_windows={dd_count};return_tol={tolerance_ok}"
        pass_rows.append(
            {
                "dd_improve_window_count": dd_count,
                "return_tolerance_ok": tolerance_ok,
                "full_mdd_improved": full_mdd_improved,
                "layer2_pass": layer2_pass,
                "pass_reason": reason,
            }
        )
    return pd.concat([out.reset_index(drop=True), pd.DataFrame(pass_rows)], axis=1)


def select_candidate(window_metrics: pd.DataFrame) -> dict[str, object]:
    passed = window_metrics[window_metrics["layer2_pass"].astype(bool)].copy()
    primary_passed = passed[passed["lookback"].eq(PRIMARY_LOOKBACK)].copy()
    if not primary_passed.empty:
        selected = primary_passed.sort_values(
            ["ann_return_full", "mdd_improve_full_pp"],
            ascending=[False, False],
        ).iloc[0].to_dict()
        decision = "carry_forward_primary_r2_pass"
        stability = "primary_pass"
    elif not passed.empty:
        selected = passed.sort_values(["ann_return_full", "mdd_improve_full_pp"], ascending=[False, False]).iloc[0].to_dict()
        decision = "watch_nonprimary_r2_pass"
        stability = "nonprimary_pass"
    else:
        candidates = window_metrics[window_metrics["r2_label"].ne("none")].copy()
        selected = candidates.sort_values(["mdd_improve_full_pp", "ann_return_full"], ascending=[False, False]).iloc[0].to_dict()
        decision = "no_layer2_promotion"
        stability = "no_pass"
    return {"selected": selected, "decision": decision, "stability_label": stability}


def original_full_reference(prices: pd.DataFrame, end_date: pd.Timestamp) -> dict[str, object]:
    original_assets = dict(subd.ASSETS)
    try:
        subd.ASSETS.clear()
        subd.ASSETS.update(layer0.PROXY_ASSETS)
        config = subd.RunConfig(
            source="akshare_em_qfq",
            one_way_cost=v11.ONE_WAY_COST,
            start_date=pd.Timestamp(prices.index[0]),
            end_date=end_date,
            output_tag="layer2_original_full_reference",
            target_vols=(),
            vol_window=subd.DEFAULT_VOL_WINDOW,
            max_lev=subd.DEFAULT_MAX_LEV,
        )
        curve = next(
            item
            for item in v11.build_curves(prices, config)
            if item["scenario"].iloc[0] == "v1_1_staged_50_plus_ma60_overheat"
        )
        row: dict[str, object] = {
            "candidate": "orig_full_v1_1_reference",
            "candidate_type": "original_full_strategy_reference",
            "lookback": subd.LOOKBACK,
            "r2_threshold": v11.R2_THRESHOLD,
            "notes": "Full official V1.1 chain; reference only, not Layer2 pass baseline",
        }
        for segment, label, start, reason in layer1.window_specs(prices.index):
            if start is None:
                row[f"ann_return_{segment}"] = np.nan
                row[f"max_dd_{segment}"] = np.nan
                row[f"reason_{segment}"] = reason
            else:
                metrics = v11.summarize(curve, start, label)
                row[f"ann_return_{segment}"] = metrics["cagr"]
                row[f"max_dd_{segment}"] = metrics["maxdd"]
                row[f"reason_{segment}"] = ""
        return row
    finally:
        subd.ASSETS.clear()
        subd.ASSETS.update(original_assets)


def build_comparison_list(window_metrics: pd.DataFrame, full_reference: dict[str, object]) -> pd.DataFrame:
    rows = []
    for label, ctype, notes in [
        ("lb_28_r2_none", "layer1_carried_baseline", "Layer1 carried primary line before R2"),
        ("lb_28_r2_0p20", "layer2_primary_original_r2", "Layer1 primary with original R2 threshold 0.20"),
        ("lb_26_r2_0p20", "layer2_neighbor_original_r2", "Left confirmation line with R2 0.20"),
        ("lb_30_r2_0p20", "layer2_neighbor_original_r2", "Right confirmation line with R2 0.20"),
        ("lb_32_r2_0p20", "return_peak_watch_original_r2", "Return peak watch line with R2 0.20"),
        ("lb_25_r2_0p20", "original_layer2_r2", "Original first-layer parameter plus original R2 0.20"),
    ]:
        source = window_metrics[window_metrics["candidate"].eq(label)].iloc[0].to_dict()
        row = {
            "candidate": label if label != "lb_25_r2_0p20" else "orig_layer2_lb25_r2_0p20",
            "candidate_type": ctype,
            "lookback": source["lookback"],
            "r2_threshold": source["r2_threshold"],
            "notes": notes,
        }
        for segment in SEGMENTS:
            row[f"ann_return_{segment}"] = source[f"ann_return_{segment}"]
            row[f"max_dd_{segment}"] = source[f"max_dd_{segment}"]
            row[f"reason_{segment}"] = source.get(f"reason_{segment}", "")
        rows.append(row)
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
        window_metrics["lookback"].eq(PRIMARY_LOOKBACK) & window_metrics["r2_label"].ne("none")
    ].sort_values(["layer2_pass", "ann_return_full"], ascending=[False, False])
    top_pass = window_metrics[window_metrics["layer2_pass"].astype(bool)].sort_values("ann_return_full", ascending=False).head(8)
    if top_pass.empty:
        top_pass = window_metrics[window_metrics["r2_label"].ne("none")].sort_values("mdd_improve_full_pp", ascending=False).head(8)

    lines = [
        "# Sub-D Dynamic ChiNext Proxy Layer 2 R2 Signal-Quality Scan",
        "",
        "## Run Metadata",
        "",
        f"- Run folder: `{run_folder}`",
        "- Layer: `Layer 2`",
        "- Strategy: dynamic ChiNext proxy pool, 2007-2016.",
        "- Entrypoint: `run_subd_proxy_dynamic_cyb_layer2_r2_scan.py`",
        "",
        "## Research Question",
        "",
        "Add an R2 signal-quality threshold to Layer 1 carried raw momentum lines and compare each candidate to its same-lookback no-R2 baseline.",
        "",
        "## Implementation Anchor",
        "",
        "- Data loader reused from `run_subd_proxy_dynamic_cyb_layer0.py`.",
        "- Score formula and stale-price trade guard match Layer 1.",
        "- No switch buffer, staged entry, target-vol, or overheat in this layer.",
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
        f"- Lookbacks carried: `{list(CARRY_LOOKBACKS)}`.",
        f"- R2 grid: `{[r2_label(x) for x in R2_GRID]}`.",
        "- Pass rule: Full maxDD improves; at least 3 of the 4 available windows improve maxDD; Full/5Y annualized return lag <=1pp and 3Y/1Y lag <=3pp versus same-lookback no-R2 baseline.",
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
        "- `daily_outputs/r2_signal_daily_curves.csv`",
        "- `sources.csv`",
        "",
        "## Primary Lookback Results",
        "",
        "| Candidate | Full Ann. | Full MDD | Full Ann Delta pp | Full MDD Improve pp | 5Y Ann. | 3Y Ann. | 1Y Ann. | Pass | Reason |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for _, row in primary.iterrows():
        lines.append(
            "| "
            f"{row['candidate']} | {pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{row['ann_delta_full_pp']:.2f} | {row['mdd_improve_full_pp']:.2f} | "
            f"{pct(row['ann_return_last_5y'])} | {pct(row['ann_return_last_3y'])} | {pct(row['ann_return_last_1y'])} | "
            f"{bool(row['layer2_pass'])} | {row['pass_reason']} |"
        )
    lines.extend(
        [
            "",
            "## Passing Or Best Candidates",
            "",
            "| Candidate | Full Ann. | Full MDD | Full MDD Improve pp | DD Improve Windows | Pass |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for _, row in top_pass.iterrows():
        lines.append(
            "| "
            f"{row['candidate']} | {pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{row['mdd_improve_full_pp']:.2f} | {int(row['dd_improve_window_count'])} | {bool(row['layer2_pass'])} |"
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
            "- Stop here before any switch-buffer, staged-entry, target-vol, or overheat layer.",
            "",
            "## User-Facing Summary",
            "",
            f"Layer 2 selected `{selected['candidate']}` under the documented pass rule. See `window_metrics.csv` for all thresholds.",
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
    score_cache = {lookback: precompute_scores(prices, lookback) for lookback in CARRY_LOOKBACKS}

    curves = []
    summary_rows = []
    for lookback in CARRY_LOOKBACKS:
        score_frame, r2_frame = score_cache[lookback]
        for r2_threshold in R2_GRID:
            curve = run_signal_with_r2(prices, lookback, r2_threshold, score_frame, r2_frame)
            curves.append(curve)
            for segment, label, start, reason in layer1.window_specs(prices.index):
                summary_rows.append(summarize_curve(curve, segment, label, start, reason))

    scan_summary = pd.DataFrame(summary_rows)
    window_metrics = build_window_metrics(scan_summary)
    full_reference = original_full_reference(prices, end_date)
    comparison_list = build_comparison_list(window_metrics, full_reference)
    selection = select_candidate(window_metrics)
    daily = pd.concat(curves, axis=0).reset_index()

    scan_summary.to_csv(run_folder / "scan_summary.csv", index=False, encoding="utf-8-sig")
    window_metrics.to_csv(run_folder / "window_metrics.csv", index=False, encoding="utf-8-sig")
    comparison_list.to_csv(run_folder / "comparison_list.csv", index=False, encoding="utf-8-sig")
    daily.to_csv(daily_dir / "r2_signal_daily_curves.csv", index=False, encoding="utf-8-sig")
    sources.to_csv(run_folder / "sources.csv", index=False, encoding="utf-8-sig")

    metadata_path = run_folder / "scan_meta.json"
    meta = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    command = (
        "python run_subd_proxy_dynamic_cyb_layer2_r2_scan.py "
        f"--start-date {start_date.date()} --end-date {end_date.date()} --run-folder {run_folder}"
    )
    meta.update(
        {
            "phase": "scan_complete_unfinalized",
            "scan_type": "layer2_grid_scan",
            "parameter_group": "layer2_r2_threshold",
            "baseline": {"rule": "same-lookback r2_none"},
            "candidate_grid": [
                {"lookback": int(lookback), "r2_threshold": r2_threshold}
                for lookback in CARRY_LOOKBACKS
                for r2_threshold in R2_GRID
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
                "signal": "close-to-close weighted-slope ranking with R2 threshold",
                "overlays": "none in Layer 2 beyond R2 filter",
                "mixed_market_calendar": "diagnostic A-share calendar with US proxy forward-filled; trades on stale trade legs blocked",
            },
            "layer2_selection": selection,
            "comparison_reference": {
                "original_layer2_candidate": "orig_layer2_lb25_r2_0p20",
                "original_full_strategy_candidate": "orig_full_v1_1_reference",
                "note": "Original Layer2 comparator is lb25 with R2 0.20 before later overlays; full strategy reference is context only.",
            },
            "outputs": {
                "record": str(run_folder / "record.md"),
                "scan_summary": str(run_folder / "scan_summary.csv"),
                "window_metrics": str(run_folder / "window_metrics.csv"),
                "scan_meta": str(run_folder / "scan_meta.json"),
                "command_log": str(run_folder / "command_log.txt"),
                "comparison_list": str(run_folder / "comparison_list.csv"),
                "daily_curves": str(daily_dir / "r2_signal_daily_curves.csv"),
                "sources": str(run_folder / "sources.csv"),
            },
            "decision": selection["decision"],
            "stability_label": selection["stability_label"],
            "git_branch": git_value(["branch", "--show-current"]),
            "git_commit": git_value(["rev-parse", "HEAD"]),
            "git_status_after_scan": git_value(["status", "--short"]),
            "elapsed_sec": round(time.time() - started, 3),
            "command": command,
            "warnings": [
                "10Y mandatory window is N/A because sample has fewer than 2520 trading days.",
                "This is proxy research; US adjusted closes are aligned to an A-share calendar for this diagnostic.",
            ],
        }
    )
    metadata_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    with (run_folder / "command_log.txt").open("a", encoding="utf-8") as f:
        f.write("\n[scan]\n")
        f.write("cwd=D:\\动量策略\\美股A股混合池子动量策略\n")
        f.write(f"{command}\n")
        f.write(f"elapsed_sec={meta['elapsed_sec']}\n")
    write_record(run_folder, window_metrics, comparison_list, selection, sources, meta)

    print(f"WROTE {run_folder / 'scan_summary.csv'}")
    print(f"WROTE {run_folder / 'window_metrics.csv'}")
    print(f"WROTE {run_folder / 'comparison_list.csv'}")
    print(f"WROTE {daily_dir / 'r2_signal_daily_curves.csv'}")
    print(json.dumps(selection, ensure_ascii=False, indent=2, default=str))
    print(window_metrics[window_metrics["lookback"].eq(PRIMARY_LOOKBACK)].to_string(index=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Layer 2 R2 threshold scan for dynamic ChiNext proxy Sub-D.")
    parser.add_argument("--start-date", default=DEFAULT_START.date().isoformat())
    parser.add_argument("--end-date", default=DEFAULT_END.date().isoformat())
    parser.add_argument("--run-folder", default=str(DEFAULT_RUN_FOLDER))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_scan(
        pd.Timestamp(args.start_date).normalize(),
        pd.Timestamp(args.end_date).normalize(),
        Path(args.run_folder),
    )


if __name__ == "__main__":
    main()
