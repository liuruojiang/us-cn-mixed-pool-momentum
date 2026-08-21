from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd

import run_subd_proxy_dynamic_cyb_layer0 as layer0
import run_subd_proxy_dynamic_cyb_layer8_overheat_three_directions_scan as layer8
import run_subd_proxy_dynamic_cyb_r2none_layer8_overheat_three_directions_scan as r2none_layer8


DEFAULT_WARMUP_START = pd.Timestamp("2007-01-01")
DEFAULT_METRIC_START = pd.Timestamp("2017-01-01")
DEFAULT_END = pd.Timestamp("2026-06-30")
DEFAULT_TAG = "subd_proxy_dynamic_cyb_r2none_final_main_oos_2017_2026ytd_20260702"
TRADING_DAYS = 252

FINAL_MAIN_LINE = r2none_layer8.CARRY_LINES[0]
FINAL_OVERHEAT_CASE = layer8.FixedSameSideCase(0.15, 0.13, 0.0, "same_side_or_exit")


def pct(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value) * 100:.2f}%"


def fmt(value: object, digits: int = 2) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value):.{digits}f}"


def final_candidate_name() -> str:
    return r2none_layer8.candidate_label(
        FINAL_MAIN_LINE,
        "fixed_same_side",
        layer8.fixed_label(FINAL_OVERHEAT_CASE),
    )


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


def max_drawdown(nav: pd.Series) -> float:
    peak = nav.astype(float).cummax().clip(lower=1.0)
    return float((nav.astype(float) / peak - 1.0).min())


def build_final_curve(prices: pd.DataFrame) -> pd.DataFrame:
    r2none_layer8.patch_layer8_helpers()
    end_date = pd.Timestamp(prices.index[-1])
    base_curve = r2none_layer8.build_line_curve(prices, end_date, FINAL_MAIN_LINE, r2none_layer8.DEFAULT_SCORE_MAX)
    features = layer8.fixed_features(layer8.build_bias_features(prices), FINAL_OVERHEAT_CASE)
    curve = layer8.apply_overheat_overlay_to_line(
        base_curve,
        FINAL_MAIN_LINE,
        "fixed_same_side",
        layer8.fixed_label(FINAL_OVERHEAT_CASE),
        features,
        FINAL_OVERHEAT_CASE.derisk_scale,
        FINAL_OVERHEAT_CASE.recovery_mode,
    )
    curve["candidate"] = final_candidate_name()
    curve["line_id"] = "final_main"
    return curve


def position_series(curve: pd.DataFrame) -> pd.Series:
    if "actual_position_next" in curve.columns:
        return curve["actual_position_next"].astype(str)
    return curve["position"].astype(str)


def exposure_series(curve: pd.DataFrame) -> pd.Series:
    if "exposure_effective" in curve.columns:
        return pd.to_numeric(curve["exposure_effective"], errors="coerce").fillna(0.0)
    if "final_exposure_after_overheat" in curve.columns:
        return pd.to_numeric(curve["final_exposure_after_overheat"], errors="coerce").fillna(0.0)
    return pd.to_numeric(curve.get("holding_fraction", pd.Series(0.0, index=curve.index)), errors="coerce").fillna(0.0)


def summarize_curve(curve: pd.DataFrame, metric_index: pd.DatetimeIndex, mode: str) -> dict[str, object]:
    sub_curve = curve.loc[curve.index.isin(metric_index)].copy()
    if sub_curve.empty:
        raise RuntimeError(f"No rows available for metric mode {mode}")
    out: dict[str, object] = {
        "mode": mode,
        "line_id": "final_main",
        "candidate": final_candidate_name(),
        "lookback": int(FINAL_MAIN_LINE.lookback),
        "r2_threshold": np.nan,
        "switch_buffer": float(FINAL_MAIN_LINE.switch_buffer),
        "entry_fraction": float(FINAL_MAIN_LINE.entry_fraction),
        "target_vol": "off",
        "momentum_decay": "off",
        "nav_enter": float(FINAL_MAIN_LINE.nav_enter),
        "nav_exit": float(FINAL_MAIN_LINE.nav_exit),
        "nav_scale": float(FINAL_MAIN_LINE.nav_scale),
        "overheat_enter": float(FINAL_OVERHEAT_CASE.enter),
        "overheat_exit": float(FINAL_OVERHEAT_CASE.exit),
        "overheat_scale": float(FINAL_OVERHEAT_CASE.derisk_scale),
        "overheat_recovery_mode": FINAL_OVERHEAT_CASE.recovery_mode,
        "rows_full": int(len(sub_curve)),
        "cash_ratio_full": float((position_series(sub_curve) == "CASH").mean()),
        "avg_exposure_full": float(exposure_series(sub_curve).mean()),
        "trades_full": int((pd.to_numeric(sub_curve["turnover"], errors="coerce").fillna(0.0) > 1e-12).sum()),
        "cost_total_full": float(pd.to_numeric(sub_curve["cost"], errors="coerce").fillna(0.0).sum()),
        "turnover_total_full": float(pd.to_numeric(sub_curve["turnover"], errors="coerce").fillna(0.0).sum()),
        "nav_defense_day_ratio_full": float(sub_curve["nav_defense_on_effective"].astype(bool).mean())
        if "nav_defense_on_effective" in sub_curve.columns
        else np.nan,
        "overheat_day_ratio_full": float(sub_curve["overheat_rule_on_effective"].astype(bool).mean())
        if "overheat_rule_on_effective" in sub_curve.columns
        else np.nan,
    }
    for segment, _, start, reason in window_specs(metric_index):
        if start is None:
            out[f"ann_return_{segment}"] = np.nan
            out[f"max_dd_{segment}"] = np.nan
            out[f"reason_{segment}"] = reason
            continue
        seg_curve = sub_curve.loc[sub_curve.index >= start].copy()
        ret = pd.to_numeric(seg_curve["return"], errors="coerce").fillna(0.0)
        wealth = (1.0 + ret).cumprod()
        years = len(seg_curve) / TRADING_DAYS
        out[f"ann_return_{segment}"] = float(wealth.iloc[-1] ** (1.0 / years) - 1.0)
        out[f"max_dd_{segment}"] = max_drawdown(wealth)
        out[f"reason_{segment}"] = ""
    return out


def yearly_returns(curve: pd.DataFrame, metric_index: pd.DatetimeIndex, mode: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    sub_curve = curve.loc[curve.index.isin(metric_index)].copy()
    for year, group in sub_curve.groupby(sub_curve.index.year):
        ret = pd.to_numeric(group["return"], errors="coerce").fillna(0.0)
        rows.append(
            {
                "mode": mode,
                "year": int(year),
                "days": int(len(group)),
                "return": float((1.0 + ret).prod() - 1.0),
                "max_dd": max_drawdown((1.0 + ret).cumprod()),
            }
        )
    return pd.DataFrame(rows)


def daily_output(curve: pd.DataFrame, mode: str, metric_index: pd.DatetimeIndex) -> pd.DataFrame:
    keep = [
        "candidate",
        "line_id",
        "position_before",
        "fraction_before",
        "position",
        "holding_fraction",
        "actual_position_before",
        "actual_position_next",
        "nav_defense_scale_effective",
        "nav_defense_scale_next",
        "nav_defense_on_effective",
        "nav_defense_on_next",
        "overheat_rule_scale_effective",
        "overheat_rule_scale_next",
        "overheat_rule_on_effective",
        "overheat_rule_on_next",
        "overheat_bias",
        "overheat_bias_mom",
        "overheat_same_side",
        "combined_overlay_scale_effective",
        "combined_overlay_scale_next",
        "asset_return",
        "gross_return",
        "turnover",
        "cost",
        "return",
        "nav",
        "exposure_effective",
        "final_exposure_after_overheat",
    ]
    out = curve.loc[curve.index.isin(metric_index), [col for col in keep if col in curve.columns]].copy()
    out.insert(0, "mode", mode)
    return out.reset_index()


def write_record(
    output_dir: Path,
    metrics: pd.DataFrame,
    yearly: pd.DataFrame,
    sources_by_mode: dict[str, pd.DataFrame],
    meta: dict[str, object],
) -> None:
    lines = [
        "# Sub-D R2-Removed Final Main OOS Test",
        "",
        "## Frozen Parameter",
        "",
        f"- Candidate: `{final_candidate_name()}`",
        "- Observation line is dropped.",
        "- R2 removed; target-vol off; momentum decay off.",
        "- Main line: lookback `28`, switch buffer `1.15`, entry fraction `0.25`.",
        "- NAV defense: enter `20%`, exit `5%`, scale `0.50`.",
        "- Fixed same-side overheat: enter `15%`, exit `13%`, scale `0`, recovery `same_side_or_exit`.",
        "",
        "## OOS Results",
        "",
        "| Mode | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Cash | Avg Exposure | NAV Defense Days | Overheat Days | 10Y Reason |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for _, row in metrics.iterrows():
        lines.append(
            "| "
            f"{row['mode']} | {pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{pct(row['ann_return_last_10y'])} | {pct(row['max_dd_last_10y'])} | "
            f"{pct(row['ann_return_last_5y'])} | {pct(row['max_dd_last_5y'])} | "
            f"{pct(row['ann_return_last_3y'])} | {pct(row['max_dd_last_3y'])} | "
            f"{pct(row['ann_return_last_1y'])} | {pct(row['max_dd_last_1y'])} | "
            f"{pct(row['cash_ratio_full'])} | {pct(row['avg_exposure_full'])} | "
            f"{pct(row['nav_defense_day_ratio_full'])} | {pct(row['overheat_day_ratio_full'])} | "
            f"{row.get('reason_last_10y', '') or ''} |"
        )

    lines.extend(
        [
            "",
            "## Yearly Returns",
            "",
            "| Mode | Year | Return | Max DD | Days |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for _, row in yearly.iterrows():
        lines.append(
            "| "
            f"{row['mode']} | {int(row['year'])} | {pct(row['return'])} | {pct(row['max_dd'])} | {int(row['days'])} |"
        )

    lines.extend(
        [
            "",
            "## Data And Execution Assumptions",
            "",
            f"- Metric start: `{meta['metric_start']}`.",
            f"- Requested end: `{meta['requested_end']}`.",
            f"- Standalone effective start/end: `{meta['standalone_effective_start']}` to `{meta['standalone_effective_end']}`.",
            f"- Continuous warmup/effective metric window: `{meta['continuous_warmup_start']}` warmup, metrics from `{meta['continuous_effective_metric_start']}` to `{meta['continuous_effective_end']}`.",
            "- This is proxy diagnostic research, not formal production ETF execution.",
            "- Calendar: repo-local A-share trading-day cache.",
            "- US proxies: Yahoo Finance adjusted close, reindexed to the A-share calendar and forward-filled by rule.",
            "- ChiNext proxy: Eastmoney `0.399006` index close / price index.",
            "- Cost model: one-way cost `0.001`; stale trade legs on forward-filled prices are blocked by the base staged-entry path.",
            "- Execution: close-to-close diagnostic helper path, same as the 2007-2016 proxy layered tests.",
            "",
            "## Source Audit",
            "",
        ]
    )
    for mode, sources in sources_by_mode.items():
        lines.extend([f"### {mode}", "", sources.to_markdown(index=False), ""])

    lines.extend(
        [
            "## Artifacts",
            "",
            f"- Metrics: `{output_dir / 'metrics.csv'}`",
            f"- Yearly returns: `{output_dir / 'yearly_returns.csv'}`",
            f"- Daily curves: `{output_dir / 'daily_curves.csv'}`",
            f"- Sources: `{output_dir / 'sources.csv'}`",
            f"- Metadata: `{output_dir / 'metadata.json'}`",
            "",
        ]
    )
    (output_dir / "record.md").write_text("\n".join(lines), encoding="utf-8")


def run_oos(warmup_start: pd.Timestamp, metric_start: pd.Timestamp, end_date: pd.Timestamp, tag: str) -> None:
    started = time.time()
    output_dir = Path("outputs") / tag
    output_dir.mkdir(parents=True, exist_ok=True)

    standalone_prices, standalone_sources = layer0.build_proxy_panel(metric_start, end_date)
    standalone_curve = build_final_curve(standalone_prices)
    standalone_index = pd.DatetimeIndex(standalone_prices.index)

    continuous_prices, continuous_sources = layer0.build_proxy_panel(warmup_start, end_date)
    continuous_curve = build_final_curve(continuous_prices)
    continuous_effective_start = pd.Timestamp(continuous_prices.index[continuous_prices.index >= metric_start][0])
    continuous_index = pd.DatetimeIndex(continuous_prices.index[continuous_prices.index >= continuous_effective_start])

    metrics = pd.DataFrame(
        [
            summarize_curve(standalone_curve, standalone_index, "standalone_reset_2017"),
            summarize_curve(continuous_curve, continuous_index, "continuous_state_from_2007"),
        ]
    )
    yearly = pd.concat(
        [
            yearly_returns(standalone_curve, standalone_index, "standalone_reset_2017"),
            yearly_returns(continuous_curve, continuous_index, "continuous_state_from_2007"),
        ],
        ignore_index=True,
    )
    daily = pd.concat(
        [
            daily_output(standalone_curve, "standalone_reset_2017", standalone_index),
            daily_output(continuous_curve, "continuous_state_from_2007", continuous_index),
        ],
        ignore_index=True,
    )
    sources = pd.concat(
        [
            standalone_sources.assign(mode="standalone_reset_2017"),
            continuous_sources.assign(mode="continuous_state_from_2007"),
        ],
        ignore_index=True,
    )
    meta = {
        "tag": tag,
        "candidate": final_candidate_name(),
        "test_type": "final_main_oos_after_2007_2016_selection",
        "warmup_start": warmup_start.date().isoformat(),
        "metric_start": metric_start.date().isoformat(),
        "requested_end": end_date.date().isoformat(),
        "standalone_effective_start": pd.Timestamp(standalone_prices.index[0]).date().isoformat(),
        "standalone_effective_end": pd.Timestamp(standalone_prices.index[-1]).date().isoformat(),
        "standalone_rows": int(len(standalone_prices)),
        "continuous_warmup_start": pd.Timestamp(continuous_prices.index[0]).date().isoformat(),
        "continuous_effective_metric_start": continuous_effective_start.date().isoformat(),
        "continuous_effective_end": pd.Timestamp(continuous_prices.index[-1]).date().isoformat(),
        "continuous_metric_rows": int(len(continuous_index)),
        "proxy_assets": layer0.PROXY_ASSETS,
        "cost_model": {"one_way_cost": 0.001, "stale_trade_guard": True},
        "command": (
            "python run_subd_proxy_dynamic_cyb_r2none_final_main_oos_2017_2026.py "
            f"--warmup-start {warmup_start.date()} --metric-start {metric_start.date()} "
            f"--end-date {end_date.date()} --tag {tag}"
        ),
        "elapsed_sec": None,
    }
    meta["elapsed_sec"] = round(time.time() - started, 3)

    metrics.to_csv(output_dir / "metrics.csv", index=False, encoding="utf-8-sig")
    yearly.to_csv(output_dir / "yearly_returns.csv", index=False, encoding="utf-8-sig")
    daily.to_csv(output_dir / "daily_curves.csv", index=False, encoding="utf-8-sig")
    sources.to_csv(output_dir / "sources.csv", index=False, encoding="utf-8-sig")
    (output_dir / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    write_record(
        output_dir,
        metrics,
        yearly,
        {
            "standalone_reset_2017": standalone_sources,
            "continuous_state_from_2007": continuous_sources,
        },
        meta,
    )

    display_cols = [
        "mode",
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
        "cash_ratio_full",
        "avg_exposure_full",
        "nav_defense_day_ratio_full",
        "overheat_day_ratio_full",
    ]
    print(f"WROTE {output_dir / 'record.md'}")
    print(metrics[display_cols].to_string(index=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--warmup-start", default=DEFAULT_WARMUP_START.date().isoformat())
    parser.add_argument("--metric-start", default=DEFAULT_METRIC_START.date().isoformat())
    parser.add_argument("--end-date", default=DEFAULT_END.date().isoformat())
    parser.add_argument("--tag", default=DEFAULT_TAG)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_oos(pd.Timestamp(args.warmup_start), pd.Timestamp(args.metric_start), pd.Timestamp(args.end_date), args.tag)


if __name__ == "__main__":
    main()
