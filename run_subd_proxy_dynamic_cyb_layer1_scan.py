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
import run_subd_six_etf_v1_1 as v11


DEFAULT_START = pd.Timestamp("2007-01-01")
DEFAULT_END = pd.Timestamp("2016-12-30")
DEFAULT_RUN_FOLDER = Path(
    "quant_param_scan_runs"
    "/20260701_subd_dynamic_cyb_proxy_subd_v1_dynamic_cyb_2007_2016_raw_weighted_slope_layer1_lookback_width"
)
LOOKBACK_GRID = (
    10,
    15,
    20,
    22,
    24,
    25,
    26,
    28,
    30,
    32,
    34,
    35,
    36,
    38,
    40,
    42,
    45,
    50,
    55,
    60,
    65,
    70,
    75,
    80,
    85,
    90,
)
BASELINE_LOOKBACK = 25
SCORE_MIN = 0.0
SCORE_MAX = 5.0
ONE_WAY_COST = 0.001
TRADING_DAYS = 252


def git_value(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def weighted_slope_score(window: pd.Series, lookback: int) -> tuple[float, float]:
    values = window.dropna().astype(float)
    if len(values) != lookback or (values <= 0).any():
        return math.nan, math.nan
    y = np.log(values.to_numpy())
    x = np.arange(len(y), dtype=float)
    weights = np.arange(1, len(y) + 1, dtype=float)
    slope, intercept = np.polyfit(x, y, 1, w=np.sqrt(weights))
    fitted = slope * x + intercept
    y_bar = float(np.average(y, weights=weights))
    ss_tot = float(np.sum(weights * (y - y_bar) ** 2))
    if ss_tot <= 0:
        return math.nan, math.nan
    ss_res = float(np.sum(weights * (y - fitted) ** 2))
    r2 = max(0.0, 1.0 - ss_res / ss_tot)
    annual_log_return = float(slope) * TRADING_DAYS
    if not math.isfinite(annual_log_return) or annual_log_return > math.log(np.finfo(float).max):
        return math.nan, r2
    return math.exp(annual_log_return) - 1.0, r2


def calc_scores(prices: pd.DataFrame, idx: int, lookback: int) -> tuple[dict[str, float], dict[str, float]]:
    scores: dict[str, float] = {}
    r2_values: dict[str, float] = {}
    for code in layer0.PROXY_ASSETS:
        score, r2 = weighted_slope_score(prices[code].iloc[idx - lookback + 1 : idx + 1], lookback)
        if not math.isnan(r2):
            r2_values[code] = r2
        if SCORE_MIN < score < SCORE_MAX:
            scores[code] = score
    return scores, r2_values


def price_is_ffill(flags: pd.DataFrame, date: pd.Timestamp, code: str) -> bool:
    normalized = pd.Timestamp(date).normalize()
    return bool(code in flags.columns and normalized in flags.index and flags.at[normalized, code])


def trade_leg_assets(old_holding: str, target: str) -> list[str]:
    assets: list[str] = []
    if old_holding != "CASH":
        assets.append(old_holding)
    if target != "CASH" and target not in assets:
        assets.append(target)
    return assets


def run_raw_signal(prices: pd.DataFrame, lookback: int) -> pd.DataFrame:
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

        scores: dict[str, float] = {}
        r2_values: dict[str, float] = {}
        if idx >= lookback - 1:
            scores, r2_values = calc_scores(prices, idx, lookback)
        target = max(scores, key=scores.get) if scores else "CASH"
        best_score = float(scores[target]) if target in scores else math.nan
        turnover = 0.0
        cost = 0.0
        stale_assets: list[str] = []
        trade_blocked = False
        blocked_target: str | None = None

        nav *= 1.0 + gross_return
        if target != prev_holding:
            stale_assets = [code for code in trade_leg_assets(prev_holding, target) if price_is_ffill(flags, date, code)]
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
            "candidate": f"lb_{lookback}",
            "lookback": lookback,
            "position_before": prev_holding,
            "position": holding,
            "best_candidate": max(scores, key=scores.get) if scores else "CASH",
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
            row[f"score_{code}"] = scores.get(code, math.nan)
            row[f"r2_{code}"] = r2_values.get(code, math.nan)
            row[f"price_ffill_{code}"] = price_is_ffill(flags, date, code)
        rows.append(row)
    return pd.DataFrame(rows).set_index("date")


def max_drawdown(nav: pd.Series) -> float:
    peak = nav.astype(float).cummax().clip(lower=1.0)
    return float((nav.astype(float) / peak - 1.0).min())


def mdd_period(ret: pd.Series) -> dict[str, object]:
    wealth = (1.0 + ret.astype(float).fillna(0.0)).cumprod()
    drawdown = wealth / wealth.cummax().clip(lower=1.0) - 1.0
    trough = drawdown.idxmin()
    peak = wealth.loc[:trough].idxmax()
    return {
        "peak": pd.Timestamp(peak).date().isoformat(),
        "trough": pd.Timestamp(trough).date().isoformat(),
        "max_dd": float(drawdown.loc[trough]),
    }


def window_specs(index: pd.Index) -> list[tuple[str, str, pd.Timestamp | None, str]]:
    ordered = pd.DatetimeIndex(index).sort_values()
    specs = [
        ("full", "Full", None),
        ("last_10y", "10Y", 10 * TRADING_DAYS),
        ("last_5y", "5Y", 5 * TRADING_DAYS),
        ("last_3y", "3Y", 3 * TRADING_DAYS),
        ("last_1y", "1Y", TRADING_DAYS),
    ]
    out: list[tuple[str, str, pd.Timestamp | None, str]] = []
    for segment, label, rows in specs:
        if rows is None:
            out.append((segment, label, pd.Timestamp(ordered[0]), ""))
        elif len(ordered) >= rows:
            out.append((segment, label, pd.Timestamp(ordered[-rows]), ""))
        else:
            out.append((segment, label, None, f"insufficient rows: {len(ordered)} < {rows} trading days"))
    return out


def summarize_curve(curve: pd.DataFrame, segment: str, label: str, start: pd.Timestamp | None, reason: str) -> dict[str, object]:
    candidate = str(curve["candidate"].iloc[0])
    lookback = int(curve["lookback"].iloc[0])
    if start is None:
        return {
            "candidate": candidate,
            "lookback": lookback,
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
    baseline = scan_summary[
        scan_summary["candidate"].eq(f"lb_{BASELINE_LOOKBACK}") & scan_summary["segment"].eq("full")
    ]
    baseline_ann = float(baseline["ann_return"].iloc[0]) if not baseline.empty else math.nan
    baseline_dd = float(baseline["max_dd"].iloc[0]) if not baseline.empty else math.nan
    for candidate, group in scan_summary.groupby("candidate", sort=False):
        row: dict[str, object] = {
            "candidate": candidate,
            "lookback": int(group["lookback"].iloc[0]),
        }
        for segment in ["full", "last_10y", "last_5y", "last_3y", "last_1y"]:
            sub = group[group["segment"].eq(segment)]
            if sub.empty:
                row[f"ann_return_{segment}"] = np.nan
                row[f"max_dd_{segment}"] = np.nan
                row[f"reason_{segment}"] = "missing segment"
            else:
                row[f"ann_return_{segment}"] = sub["ann_return"].iloc[0]
                row[f"max_dd_{segment}"] = sub["max_dd"].iloc[0]
                row[f"reason_{segment}"] = sub["reason"].iloc[0]
        row["full_ann_delta_vs_lb25_pp"] = (
            (float(row["ann_return_full"]) - baseline_ann) * 100.0 if pd.notna(row["ann_return_full"]) else np.nan
        )
        row["full_mdd_improvement_vs_lb25_pp"] = (
            (float(row["max_dd_full"]) - baseline_dd) * 100.0 if pd.notna(row["max_dd_full"]) else np.nan
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values("lookback")


def original_reference_metrics(prices: pd.DataFrame, end_date: pd.Timestamp) -> dict[str, object]:
    original_assets = dict(subd.ASSETS)
    try:
        subd.ASSETS.clear()
        subd.ASSETS.update(layer0.PROXY_ASSETS)
        config = subd.RunConfig(
            source="akshare_em_qfq",
            one_way_cost=v11.ONE_WAY_COST,
            start_date=pd.Timestamp(prices.index[0]),
            end_date=end_date,
            output_tag="layer1_original_reference",
            target_vols=(),
            vol_window=subd.DEFAULT_VOL_WINDOW,
            max_lev=subd.DEFAULT_MAX_LEV,
        )
        curves = v11.build_curves(prices, config)
        curve = next(
            item for item in curves if item["scenario"].iloc[0] == "v1_1_staged_50_plus_ma60_overheat"
        )
        row: dict[str, object] = {
            "candidate": "orig_full_v1_1_reference",
            "candidate_type": "original_full_strategy_reference",
            "lookback": subd.LOOKBACK,
            "notes": (
                "Full official V1.1 chain: lookback 25 + R2 0.20 + switch buffer 1.05 "
                "+ staged entry + target-vol + overheat"
            ),
        }
        for segment, label, start, reason in window_specs(prices.index):
            suffix = segment
            if start is None:
                row[f"ann_return_{suffix}"] = np.nan
                row[f"max_dd_{suffix}"] = np.nan
                row[f"reason_{suffix}"] = reason
            else:
                metrics = v11.summarize(curve, start, label)
                row[f"ann_return_{suffix}"] = metrics["cagr"]
                row[f"max_dd_{suffix}"] = metrics["maxdd"]
                row[f"reason_{suffix}"] = ""
        return row
    finally:
        subd.ASSETS.clear()
        subd.ASSETS.update(original_assets)


def build_comparison_list(window_metrics: pd.DataFrame, original_reference: dict[str, object]) -> pd.DataFrame:
    rows = []
    for lookback, candidate, candidate_type, notes in [
        (
            25,
            "orig_layer1_raw_lb25",
            "original_layer1_raw",
            "Original first-layer raw momentum: weighted-slope lookback 25, score range 0..5, no R2/overlay",
        ),
        (28, "lb_28", "layer1_primary", "Width-supported Layer1 raw-signal carry line"),
        (26, "lb_26", "layer1_neighbor", "Left confirmation neighbor for lb_28"),
        (30, "lb_30", "layer1_neighbor", "Right confirmation neighbor for lb_28"),
        (32, "lb_32", "return_peak_watch", "Full-sample return peak; fails 80% width rule"),
    ]:
        source = window_metrics[window_metrics["lookback"].eq(lookback)].iloc[0].to_dict()
        rows.append(
            {
                "candidate": candidate,
                "candidate_type": candidate_type,
                "lookback": lookback,
                "notes": notes,
                "ann_return_full": source["ann_return_full"],
                "max_dd_full": source["max_dd_full"],
                "ann_return_last_10y": source["ann_return_last_10y"],
                "max_dd_last_10y": source["max_dd_last_10y"],
                "reason_last_10y": source.get("reason_last_10y", ""),
                "ann_return_last_5y": source["ann_return_last_5y"],
                "max_dd_last_5y": source["max_dd_last_5y"],
                "ann_return_last_3y": source["ann_return_last_3y"],
                "max_dd_last_3y": source["max_dd_last_3y"],
                "ann_return_last_1y": source["ann_return_last_1y"],
                "max_dd_last_1y": source["max_dd_last_1y"],
            }
        )
    rows.append(original_reference)
    return pd.DataFrame(rows)


def build_width_table(window_metrics: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    metrics = window_metrics.set_index("lookback").sort_index()
    rows = []
    for lookback, row in metrics.iterrows():
        full_ann = float(row["ann_return_full"])
        lower = metrics.index[metrics.index < lookback]
        upper = metrics.index[metrics.index > lookback]
        left = int(lower.max()) if len(lower) else None
        right = int(upper.min()) if len(upper) else None
        left_ann = float(metrics.loc[left, "ann_return_full"]) if left is not None else math.nan
        right_ann = float(metrics.loc[right, "ann_return_full"]) if right is not None else math.nan
        left_ratio = left_ann / full_ann if left is not None and full_ann > 0 else math.nan
        right_ratio = right_ann / full_ann if right is not None and full_ann > 0 else math.nan
        width_supported = bool(
            left is not None
            and right is not None
            and math.isfinite(left_ratio)
            and math.isfinite(right_ratio)
            and left_ratio >= 0.8
            and right_ratio >= 0.8
        )
        rows.append(
            {
                "lookback": int(lookback),
                "candidate": row["candidate"],
                "width_metric": "ann_return_full",
                "ann_return_full": full_ann,
                "left_neighbor": left,
                "left_ann_return_full": left_ann,
                "left_retention_ratio": left_ratio,
                "right_neighbor": right,
                "right_ann_return_full": right_ann,
                "right_retention_ratio": right_ratio,
                "width_supported_80pct": width_supported,
                "edge_of_grid": left is None or right is None,
            }
        )
    width = pd.DataFrame(rows)
    peak_row = width.loc[width["ann_return_full"].idxmax()].to_dict()
    peak_ann = float(peak_row["ann_return_full"])
    supported = width[
        width["width_supported_80pct"] & (width["ann_return_full"] >= 0.8 * peak_ann)
    ].copy()
    broad_watch = width[width["width_supported_80pct"]].copy()
    if not supported.empty:
        recommended = supported.loc[supported["ann_return_full"].idxmax()].to_dict()
        decision = "carry_forward_width_supported"
        stability = "width_supported"
    else:
        recommended = peak_row
        decision = "watch_thin_peak_no_width_promotion"
        stability = "thin_or_edge"
    best_broad_watch = (
        broad_watch.loc[broad_watch["ann_return_full"].idxmax()].to_dict()
        if not broad_watch.empty
        else None
    )
    return width, {
        "peak": peak_row,
        "recommended": recommended,
        "best_broad_watch": best_broad_watch,
        "decision": decision,
        "stability_label": stability,
        "minimum_recommended_ann_return": 0.8 * peak_ann,
    }


def pct(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value) * 100:.2f}%"


def write_record(
    run_folder: Path,
    scan_summary: pd.DataFrame,
    window_metrics: pd.DataFrame,
    width_table: pd.DataFrame,
    comparison_list: pd.DataFrame,
    selection: dict[str, object],
    sources: pd.DataFrame,
    meta: dict[str, object],
) -> None:
    recommended = selection["recommended"]
    peak = selection["peak"]
    best_broad_watch = selection.get("best_broad_watch")
    rec_lb = int(recommended["lookback"])
    rec_metrics = window_metrics[window_metrics["lookback"].eq(rec_lb)].iloc[0]
    top = window_metrics.sort_values("ann_return_full", ascending=False).head(8)
    lines = [
        "# Sub-D Dynamic ChiNext Proxy Layer 1 Lookback Width Scan",
        "",
        "## Run Metadata",
        "",
        f"- Run folder: `{run_folder}`",
        f"- Layer: `Layer 1`",
        f"- Strategy: dynamic ChiNext proxy pool, 2007-2016.",
        f"- Entrypoint: `run_subd_proxy_dynamic_cyb_layer1_scan.py`",
        "",
        "## Research Question",
        "",
        "Test the raw weighted-slope lookback width before adding R2, staged entry, target-vol, or overheat overlays.",
        "",
        "## Implementation Anchor",
        "",
        "- Data loader reused from `run_subd_proxy_dynamic_cyb_layer0.py`.",
        "- Raw signal harness holds the highest positive weighted-slope score under `0 < score < 5`.",
        "- No R2 filter, no switch buffer, no staged entry, no target-vol, no overheat.",
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
        f"- Lookback grid: `{list(LOOKBACK_GRID)}`.",
        "- Width metric: `ann_return_full`.",
        "- Layer 1 pass rule: immediate left and right neighbors must each retain at least 80% of selected line's full-sample annualized return.",
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
        "- `ridge_width.csv`",
        "- `daily_outputs/raw_signal_daily_curves.csv`",
        "- `sources.csv`",
        "",
        "## Full-Sample Results",
        "",
        "| Lookback | Full Ann. | Full MaxDD | 5Y Ann. | 3Y Ann. | 1Y Ann. | Width Supported |",
        "|---:|---:|---:|---:|---:|---:|---|",
    ]
    supported_map = width_table.set_index("lookback")["width_supported_80pct"].to_dict()
    for _, row in top.iterrows():
        lb = int(row["lookback"])
        lines.append(
            "| "
            f"{lb} | {pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{pct(row['ann_return_last_5y'])} | {pct(row['ann_return_last_3y'])} | "
            f"{pct(row['ann_return_last_1y'])} | {supported_map.get(lb, False)} |"
        )
    lines.extend(
        [
            "",
            "## Comparison List",
            "",
            "| Candidate | Type | Full Ann. | Full MaxDD | 5Y Ann. | 3Y Ann. | 1Y Ann. | Notes |",
            "|---|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for _, row in comparison_list.iterrows():
        lines.append(
            "| "
            f"{row['candidate']} | {row['candidate_type']} | "
            f"{pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{pct(row['ann_return_last_5y'])} | {pct(row['ann_return_last_3y'])} | "
            f"{pct(row['ann_return_last_1y'])} | {row['notes']} |"
        )
    lines.extend(
        [
            "",
            "- `orig_layer1_raw_lb25` is the original first-layer raw momentum line and is the correct original comparator for Layer 1.",
            "- `orig_full_v1_1_reference` uses the full official overlay chain; it is shown only as a strategy reference and is not used for Layer 1 width scoring.",
            "- All rows have 10Y as `N/A` because this 2007-2016 sample has only 2432 A-share sessions, fewer than 2520.",
            "",
            "## Window Results",
            "",
            f"- Recommended candidate: `lb_{rec_lb}`.",
            f"- Mandatory windows for recommended: Full `{pct(rec_metrics['ann_return_full'])}` / MDD `{pct(rec_metrics['max_dd_full'])}`; "
            f"10Y `N/A`; 5Y `{pct(rec_metrics['ann_return_last_5y'])}` / MDD `{pct(rec_metrics['max_dd_last_5y'])}`; "
            f"3Y `{pct(rec_metrics['ann_return_last_3y'])}` / MDD `{pct(rec_metrics['max_dd_last_3y'])}`; "
            f"1Y `{pct(rec_metrics['ann_return_last_1y'])}` / MDD `{pct(rec_metrics['max_dd_last_1y'])}`.",
            "",
            "## Stability Classification",
            "",
            f"- Peak: `lb_{int(peak['lookback'])}` with full annualized `{pct(peak['ann_return_full'])}`.",
            f"- Recommended: `lb_{rec_lb}` with left retention `{recommended.get('left_retention_ratio'):.3f}` and right retention `{recommended.get('right_retention_ratio'):.3f}`.",
            f"- Minimum full annualized return for a promotable width-supported line: `{pct(selection['minimum_recommended_ann_return'])}`.",
            (
                f"- Best lower-return broad watch: `lb_{int(best_broad_watch['lookback'])}` with full annualized `{pct(best_broad_watch['ann_return_full'])}`."
                if best_broad_watch
                else "- Best lower-return broad watch: `N/A`."
            ),
            f"- Stability label: `{selection['stability_label']}`.",
            "",
            "## Decision",
            "",
            f"- Decision: `{selection['decision']}`.",
            (
                "- Carry this Layer 1 primary line plus its immediate neighbors into Layer 2 R2 filter tests."
                if selection["decision"] == "carry_forward_width_supported"
                else "- Do not promote Layer 1 as width-supported yet; carry the peak line, its immediate neighbors, and the best broad watch as diagnostics into Layer 2 R2 tests."
            ),
            "- Stop here before Layer 2 per standard process.",
            "",
            "## User-Facing Summary",
            "",
            f"Layer 1 recommends `lookback={rec_lb}` for the raw weighted-slope signal under the dynamic ChiNext proxy pool. "
            "The 10Y window remains N/A because 2007-2016 has fewer than 2520 A-share sessions.",
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
    curves = []
    summary_rows = []
    for lookback in LOOKBACK_GRID:
        curve = run_raw_signal(prices, lookback)
        curves.append(curve)
        for segment, label, start, reason in window_specs(prices.index):
            summary_rows.append(summarize_curve(curve, segment, label, start, reason))
    scan_summary = pd.DataFrame(summary_rows)
    window_metrics = build_window_metrics(scan_summary)
    width_table, selection = build_width_table(window_metrics)
    original_reference = original_reference_metrics(prices, end_date)
    comparison_list = build_comparison_list(window_metrics, original_reference)
    daily = pd.concat(curves, axis=0).reset_index()

    scan_summary.to_csv(run_folder / "scan_summary.csv", index=False, encoding="utf-8-sig")
    window_metrics.to_csv(run_folder / "window_metrics.csv", index=False, encoding="utf-8-sig")
    comparison_list.to_csv(run_folder / "comparison_list.csv", index=False, encoding="utf-8-sig")
    width_table.to_csv(run_folder / "ridge_width.csv", index=False, encoding="utf-8-sig")
    daily.to_csv(daily_dir / "raw_signal_daily_curves.csv", index=False, encoding="utf-8-sig")
    sources.to_csv(run_folder / "sources.csv", index=False, encoding="utf-8-sig")

    metadata_path = run_folder / "scan_meta.json"
    if metadata_path.exists():
        meta = json.loads(metadata_path.read_text(encoding="utf-8"))
    else:
        meta = {}
    command = (
        "python run_subd_proxy_dynamic_cyb_layer1_scan.py "
        f"--start-date {start_date.date()} --end-date {end_date.date()} --run-folder {run_folder}"
    )
    meta.update(
        {
            "phase": "scan_complete_unfinalized",
            "scan_type": "layer1_grid_scan",
            "parameter_group": "layer1_lookback_width",
            "baseline": {"candidate": f"lb_{BASELINE_LOOKBACK}", "lookback": BASELINE_LOOKBACK},
            "candidate_grid": [{"lookback": int(value), "score_min": SCORE_MIN, "score_max": SCORE_MAX} for value in LOOKBACK_GRID],
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
                "signal": "close-to-close raw weighted-slope ranking",
                "overlays": "none in Layer 1",
                "mixed_market_calendar": "diagnostic A-share calendar with US proxy forward-filled; trades on stale trade legs blocked",
            },
            "layer1_selection": selection,
            "outputs": {
                "record": str(run_folder / "record.md"),
                "scan_summary": str(run_folder / "scan_summary.csv"),
                "window_metrics": str(run_folder / "window_metrics.csv"),
                "scan_meta": str(run_folder / "scan_meta.json"),
                "command_log": str(run_folder / "command_log.txt"),
                "comparison_list": str(run_folder / "comparison_list.csv"),
                "ridge_width": str(run_folder / "ridge_width.csv"),
                "daily_curves": str(daily_dir / "raw_signal_daily_curves.csv"),
                "sources": str(run_folder / "sources.csv"),
            },
            "comparison_reference": {
                "original_layer1_candidate": "orig_layer1_raw_lb25",
                "original_full_strategy_candidate": "orig_full_v1_1_reference",
                "note": "Original first-layer raw line is the Layer1 comparator; full strategy reference is shown only for context.",
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
        f.write(f"cwd=D:\\动量策略\\美股A股混合池子动量策略\n")
        f.write(f"{command}\n")
        f.write(f"elapsed_sec={meta['elapsed_sec']}\n")
    write_record(run_folder, scan_summary, window_metrics, width_table, comparison_list, selection, sources, meta)

    print(f"WROTE {run_folder / 'scan_summary.csv'}")
    print(f"WROTE {run_folder / 'window_metrics.csv'}")
    print(f"WROTE {run_folder / 'ridge_width.csv'}")
    print(f"WROTE {daily_dir / 'raw_signal_daily_curves.csv'}")
    print(json.dumps(selection, ensure_ascii=False, indent=2))
    print(window_metrics.sort_values("ann_return_full", ascending=False).head(8).to_string(index=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Layer 1 lookback-width scan for dynamic ChiNext proxy Sub-D.")
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
