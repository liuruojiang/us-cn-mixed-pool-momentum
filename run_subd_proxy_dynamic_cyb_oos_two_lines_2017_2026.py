from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

import run_subd_proxy_dynamic_cyb_layer0 as layer0
import run_subd_proxy_dynamic_cyb_layer1_scan as layer1
import run_subd_proxy_dynamic_cyb_layer8_overheat_three_directions_scan as layer8


DEFAULT_START = pd.Timestamp("2017-01-01")
DEFAULT_END = pd.Timestamp("2026-06-30")
DEFAULT_TAG = "subd_proxy_dynamic_cyb_2017_2026ytd_oos_two_lines_20260701"
TRADING_DAYS = 252


def pct(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value) * 100:.2f}%"


def fmt(value: object, digits: int = 2) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value):.{digits}f}"


def line_parameter_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in layer8.CARRY_LINES:
        rows.append(
            {
                "line_id": line.line_id,
                "lookback": int(line.lookback),
                "r2_threshold": float(line.r2_threshold),
                "switch_buffer": float(line.switch_buffer),
                "entry_fraction": float(line.entry_fraction),
                "score_max": float(layer8.DEFAULT_SCORE_MAX),
                "target_vol": "off",
                "momentum_decay_enabled": bool(line.decay_ratio is not None),
                "decay_ratio_threshold": np.nan if line.decay_ratio is None else float(line.decay_ratio),
                "recovery_ratio_threshold": np.nan if line.recovery_ratio is None else float(line.recovery_ratio),
                "confirm_days": np.nan if line.confirm_days is None else int(line.confirm_days),
                "decay_scale": np.nan if line.decay_scale is None else float(line.decay_scale),
                "nav_defense_enabled": bool(line.nav_enter is not None),
                "nav_enter_threshold": np.nan if line.nav_enter is None else float(line.nav_enter),
                "nav_exit_threshold": np.nan if line.nav_exit is None else float(line.nav_exit),
                "nav_defense_scale": np.nan if line.nav_scale is None else float(line.nav_scale),
                "overheat": "off",
            }
        )
    return rows


def build_oos_curves(prices: pd.DataFrame) -> list[pd.DataFrame]:
    end_date = pd.Timestamp(prices.index[-1])
    curves: list[pd.DataFrame] = []
    for line in layer8.CARRY_LINES:
        base_curve = layer8.build_line_curve(prices, end_date, line, layer8.DEFAULT_SCORE_MAX)
        curves.append(layer8.apply_no_new_overheat(base_curve, line))
    layer8.mark_effect_vs_baseline(curves)
    return curves


def build_window_tables(prices: pd.DataFrame, curves: list[pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    for curve in curves:
        for segment, label, start, reason in layer1.window_specs(prices.index):
            rows.append(layer8.summarize_curve(curve, segment, label, start, reason))
    scan_summary = pd.DataFrame(rows)
    window_metrics = layer8.build_window_metrics(scan_summary)
    return scan_summary, window_metrics


def build_yearly_returns(curves: list[pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for curve in curves:
        candidate = str(curve["candidate"].iloc[0])
        line_id = str(curve["line_id"].iloc[0])
        for year, group in curve.groupby(curve.index.year):
            ret = group["return"].astype(float).fillna(0.0)
            rows.append(
                {
                    "line_id": line_id,
                    "candidate": candidate,
                    "year": int(year),
                    "days": int(len(group)),
                    "return": float((1.0 + ret).prod() - 1.0),
                    "max_dd": layer8.max_drawdown((1.0 + ret).cumprod()),
                }
            )
    return pd.DataFrame(rows)


def daily_output(curves: list[pd.DataFrame]) -> pd.DataFrame:
    return layer8.daily_output_frame(curves)


def write_record(
    output_dir: Path,
    params: pd.DataFrame,
    window_metrics: pd.DataFrame,
    yearly: pd.DataFrame,
    sources: pd.DataFrame,
    metadata: dict[str, object],
) -> None:
    lines = [
        "# Sub-D Dynamic ChiNext Proxy OOS Two-Line Test",
        "",
        "## Scope",
        "",
        "- Freeze the two carried lines selected from the 2007-2016 layered test.",
        "- Apply them unchanged to the next available window: 2017 start through the latest confirmed end date used in this run.",
        "- This is proxy OOS research, not a production ETF formal result.",
        "",
        "## Frozen Parameters",
        "",
        "| Line | Lookback | R2 | Switch Buffer | Entry | Score Max | Target Vol | Decay | NAV Defense | Overheat |",
        "|---|---:|---:|---:|---:|---:|---|---|---|---|",
    ]
    for _, row in params.iterrows():
        decay = "off"
        if bool(row["momentum_decay_enabled"]):
            decay = (
                f"ratio {fmt(row['decay_ratio_threshold'])}, "
                f"recover {fmt(row['recovery_ratio_threshold'])}, "
                f"confirm {int(row['confirm_days'])}, "
                f"scale {fmt(row['decay_scale'])}"
            )
        nav = "off"
        if bool(row["nav_defense_enabled"]):
            nav = (
                f"enter {pct(row['nav_enter_threshold'])}, "
                f"exit {pct(row['nav_exit_threshold'])}, "
                f"scale {fmt(row['nav_defense_scale'])}"
            )
        lines.append(
            "| "
            f"`{row['line_id']}` | {int(row['lookback'])} | {fmt(row['r2_threshold'])} | "
            f"{fmt(row['switch_buffer'])} | {pct(row['entry_fraction'])} | {fmt(row['score_max'])} | "
            f"{row['target_vol']} | {decay} | {nav} | {row['overheat']} |"
        )

    lines.extend(
        [
            "",
            "## OOS Mandatory Windows",
            "",
            "| Line | Candidate | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | 10Y Reason |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for _, row in window_metrics.iterrows():
        lines.append(
            "| "
            f"`{row['line_id']}` | `{row['candidate']}` | "
            f"{pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{pct(row['ann_return_last_10y'])} | {pct(row['max_dd_last_10y'])} | "
            f"{pct(row['ann_return_last_5y'])} | {pct(row['max_dd_last_5y'])} | "
            f"{pct(row['ann_return_last_3y'])} | {pct(row['max_dd_last_3y'])} | "
            f"{pct(row['ann_return_last_1y'])} | {pct(row['max_dd_last_1y'])} | "
            f"{row.get('reason_last_10y', '') or ''} |"
        )

    lines.extend(
        [
            "",
            "## Yearly Returns",
            "",
            "| Line | Year | Return | Max DD | Days |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for _, row in yearly.iterrows():
        lines.append(
            "| "
            f"`{row['line_id']}` | {int(row['year'])} | "
            f"{pct(row['return'])} | {pct(row['max_dd'])} | {int(row['days'])} |"
        )

    lines.extend(
        [
            "",
            "## Data And Execution Assumptions",
            "",
            f"- Requested start: `{metadata['requested_start']}`.",
            f"- Effective start: `{metadata['effective_start']}`.",
            f"- Effective end: `{metadata['effective_end']}`.",
            f"- Rows: `{metadata['rows']}` A-share sessions.",
            "- Pool rule: `QQQ`, `EWG`, `EWJ`, and `GLD`; `CN_CYB_399006` is available throughout this OOS window.",
            "- Calendar: repo-local A-share trading-day cache.",
            "- US proxies: Yahoo Finance adjusted close, reindexed to the A-share calendar and forward-filled by rule.",
            "- ChiNext proxy: Eastmoney `0.399006` index close / price index.",
            "- Cost model: one-way cost `0.001`; stale trade legs on forward-filled prices are blocked by the base staged-entry path.",
            "- Execution: close-to-close diagnostic helper path, same as the 2007-2016 proxy layered tests.",
            "",
            "## Source Audit",
            "",
            sources.to_markdown(index=False),
            "",
            "## Artifacts",
            "",
            f"- Parameters: `{output_dir / 'line_params.csv'}`",
            f"- Window metrics: `{output_dir / 'window_metrics.csv'}`",
            f"- Scan-style summary: `{output_dir / 'scan_summary.csv'}`",
            f"- Daily curves: `{output_dir / 'daily_curves.csv'}`",
            f"- Yearly returns: `{output_dir / 'yearly_returns.csv'}`",
            f"- Sources: `{output_dir / 'sources.csv'}`",
            f"- Metadata: `{output_dir / 'metadata.json'}`",
            "",
        ]
    )
    (output_dir / "record.md").write_text("\n".join(lines), encoding="utf-8")


def run_oos(start_date: pd.Timestamp, end_date: pd.Timestamp, tag: str) -> None:
    started = time.time()
    output_dir = Path("outputs") / tag
    output_dir.mkdir(parents=True, exist_ok=True)

    prices, sources = layer0.build_proxy_panel(start_date, end_date)
    curves = build_oos_curves(prices)
    scan_summary, window_metrics = build_window_tables(prices, curves)
    params = pd.DataFrame(line_parameter_rows())
    yearly = build_yearly_returns(curves)
    daily = daily_output(curves)

    metadata = {
        "tag": tag,
        "test_type": "oos_two_carried_lines",
        "requested_start": start_date.date().isoformat(),
        "requested_end": end_date.date().isoformat(),
        "effective_start": pd.Timestamp(prices.index[0]).date().isoformat(),
        "effective_end": pd.Timestamp(prices.index[-1]).date().isoformat(),
        "rows": int(len(prices)),
        "proxy_assets": layer0.PROXY_ASSETS,
        "score_max": layer8.DEFAULT_SCORE_MAX,
        "cost_model": {"one_way_cost": layer8.ONE_WAY_COST, "stale_trade_guard": True},
        "calendar": "repo-local A-share trading-day cache",
        "data_sources": {
            "us_proxies": "Yahoo Finance chart API adjusted close",
            "chinext": "Eastmoney push2his kline secid=0.399006 index close",
        },
        "command": (
            "python run_subd_proxy_dynamic_cyb_oos_two_lines_2017_2026.py "
            f"--start-date {start_date.date()} --end-date {end_date.date()} --tag {tag}"
        ),
        "elapsed_sec": None,
    }
    metadata["elapsed_sec"] = round(time.time() - started, 3)

    params.to_csv(output_dir / "line_params.csv", index=False, encoding="utf-8-sig")
    scan_summary.to_csv(output_dir / "scan_summary.csv", index=False, encoding="utf-8-sig")
    window_metrics.to_csv(output_dir / "window_metrics.csv", index=False, encoding="utf-8-sig")
    yearly.to_csv(output_dir / "yearly_returns.csv", index=False, encoding="utf-8-sig")
    daily.to_csv(output_dir / "daily_curves.csv", index=False, encoding="utf-8-sig")
    sources.to_csv(output_dir / "sources.csv", index=False, encoding="utf-8-sig")
    (output_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    write_record(output_dir, params, window_metrics, yearly, sources, metadata)

    display_cols = [
        "line_id",
        "candidate",
        "ann_return_full",
        "max_dd_full",
        "ann_return_last_10y",
        "max_dd_last_10y",
        "reason_last_10y",
        "ann_return_last_5y",
        "max_dd_last_5y",
        "ann_return_last_3y",
        "max_dd_last_3y",
        "ann_return_last_1y",
        "max_dd_last_1y",
    ]
    print(f"WROTE {output_dir / 'record.md'}")
    print(window_metrics[display_cols].to_string(index=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", default=DEFAULT_START.date().isoformat())
    parser.add_argument("--end-date", default=DEFAULT_END.date().isoformat())
    parser.add_argument("--tag", default=DEFAULT_TAG)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_oos(pd.Timestamp(args.start_date), pd.Timestamp(args.end_date), args.tag)


if __name__ == "__main__":
    main()
