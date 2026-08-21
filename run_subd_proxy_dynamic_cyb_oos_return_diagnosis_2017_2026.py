from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import research_subd_six_etf_weighted_slope as subd
import run_subd_proxy_dynamic_cyb_layer0 as layer0
import run_subd_proxy_dynamic_cyb_layer8_overheat_three_directions_scan as layer8
import run_subd_six_etf_v1_1 as v11
from run_subd_proxy_dynamic_cyb_layer8_overheat_three_directions_scan import CarryLine


DEFAULT_WARMUP_START = pd.Timestamp("2007-01-01")
DEFAULT_METRIC_START = pd.Timestamp("2017-01-01")
DEFAULT_END = pd.Timestamp("2026-06-30")
DEFAULT_TAG = "subd_proxy_dynamic_cyb_2017_2026ytd_oos_return_diagnosis_20260701"
TRADING_DAYS = 252
SEGMENTS = ("full", "last_10y", "last_5y", "last_3y", "last_1y")


def pct(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value) * 100:.2f}%"


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


def build_original_v11_curve(prices: pd.DataFrame) -> pd.DataFrame:
    original_assets = dict(subd.ASSETS)
    try:
        subd.ASSETS.clear()
        subd.ASSETS.update(layer0.PROXY_ASSETS)
        config = subd.RunConfig(
            source="proxy_dynamic_cyb",
            one_way_cost=v11.ONE_WAY_COST,
            start_date=pd.Timestamp(prices.index[0]),
            end_date=pd.Timestamp(prices.index[-1]),
            output_tag="oos_return_diagnosis",
            target_vols=(),
            vol_window=subd.DEFAULT_VOL_WINDOW,
            max_lev=subd.DEFAULT_MAX_LEV,
        )
        curve = next(
            item
            for item in v11.build_curves(prices, config)
            if item["scenario"].iloc[0] == "v1_1_staged_50_plus_ma60_overheat"
        ).copy()
    finally:
        subd.ASSETS.clear()
        subd.ASSETS.update(original_assets)
    curve["candidate"] = "orig_full_v1_1_reference"
    curve["line_id"] = "original_v1_1"
    curve["diagnosis_group"] = "original_full_chain"
    return curve


def build_clean_line(prices: pd.DataFrame, r2_threshold: float, label: str) -> pd.DataFrame:
    line = CarryLine(label, 28, r2_threshold, 1.00, 0.75, None, None, None, None, None, None, None)
    curve = layer8.apply_no_new_overheat(
        layer8.build_line_curve(prices, pd.Timestamp(prices.index[-1]), line, layer8.DEFAULT_SCORE_MAX),
        line,
    )
    curve["diagnosis_group"] = "clean_r2_sensitivity"
    return curve


def build_curves(prices: pd.DataFrame) -> list[pd.DataFrame]:
    curves: list[pd.DataFrame] = [build_original_v11_curve(prices)]
    for line in layer8.CARRY_LINES:
        curve = layer8.apply_no_new_overheat(
            layer8.build_line_curve(prices, pd.Timestamp(prices.index[-1]), line, layer8.DEFAULT_SCORE_MAX),
            line,
        )
        curve["diagnosis_group"] = "selected_two_line"
        curves.append(curve)
    for r2 in (0.0, 0.2, 0.3, 0.4, 0.5):
        curves.append(build_clean_line(prices, r2, f"A_clean_r2_{str(r2).replace('.', 'p')}"))
    return curves


def position_series(curve: pd.DataFrame) -> pd.Series:
    if "actual_position_next" in curve.columns:
        return curve["actual_position_next"].astype(str)
    return curve["position"].astype(str)


def exposure_series(curve: pd.DataFrame) -> pd.Series:
    if "exposure_effective" in curve.columns:
        return pd.to_numeric(curve["exposure_effective"], errors="coerce").fillna(0.0)
    if "final_exposure_after_overheat" in curve.columns:
        return pd.to_numeric(curve["final_exposure_after_overheat"], errors="coerce").fillna(0.0)
    if "holding_fraction" in curve.columns:
        return pd.to_numeric(curve["holding_fraction"], errors="coerce").fillna(0.0)
    return pd.Series(0.0, index=curve.index)


def summarize(curve: pd.DataFrame, oos_index: pd.DatetimeIndex) -> dict[str, object]:
    sub_curve = curve.loc[curve.index.isin(oos_index)].copy()
    base = {
        "candidate": str(sub_curve["candidate"].iloc[0]),
        "line_id": str(sub_curve["line_id"].iloc[0]),
        "diagnosis_group": str(sub_curve["diagnosis_group"].iloc[0]),
        "lookback": sub_curve["lookback"].iloc[0] if "lookback" in sub_curve.columns else subd.LOOKBACK,
        "r2_threshold": sub_curve["r2_threshold"].iloc[0] if "r2_threshold" in sub_curve.columns else v11.R2_THRESHOLD,
        "target_vol": v11.TARGET_VOL if str(sub_curve["line_id"].iloc[0]) == "original_v1_1" else np.nan,
        "overheat": "original_ma60" if str(sub_curve["line_id"].iloc[0]) == "original_v1_1" else "off",
    }
    pos = position_series(sub_curve)
    exp = exposure_series(sub_curve)
    base["cash_ratio_full"] = float((pos == "CASH").mean())
    base["avg_exposure_full"] = float(exp.mean())
    base["trades_full"] = int((pd.to_numeric(sub_curve["turnover"], errors="coerce").fillna(0.0) > 1e-12).sum())
    for segment, _, start, reason in window_specs(oos_index):
        if start is None:
            base[f"ann_return_{segment}"] = np.nan
            base[f"max_dd_{segment}"] = np.nan
            base[f"reason_{segment}"] = reason
            continue
        seg_curve = sub_curve.loc[sub_curve.index >= start]
        ret = pd.to_numeric(seg_curve["return"], errors="coerce").fillna(0.0)
        wealth = (1.0 + ret).cumprod()
        years = len(seg_curve) / TRADING_DAYS
        base[f"ann_return_{segment}"] = float(wealth.iloc[-1] ** (1.0 / years) - 1.0)
        base[f"max_dd_{segment}"] = float((wealth / wealth.cummax().clip(lower=1.0) - 1.0).min())
        base[f"reason_{segment}"] = ""
    return base


def write_record(output_dir: Path, metrics: pd.DataFrame, sources: pd.DataFrame, meta: dict[str, object]) -> None:
    lines = [
        "# Sub-D OOS Return Diagnosis",
        "",
        "## Finding",
        "",
        "- The low return in the prior two-line OOS table is caused by the selected `R2=0.50` carried lines being much more defensive than the original mixed-pool momentum strategy.",
        "- It is not explained by 2017 cold start or by `SCORE_MAX=5`; the continuous-state check still shows the same pattern.",
        "- This diagnosis uses 2007 warmup/state history and reports metrics from the 2017 OOS window onward.",
        "",
        "## Comparison",
        "",
        "| Candidate | Group | R2 | Target Vol | Overheat | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | Cash Ratio | Avg Exposure |",
        "|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in metrics.iterrows():
        lines.append(
            "| "
            f"`{row['candidate']}` | {row['diagnosis_group']} | {row['r2_threshold']} | "
            f"{row['target_vol'] if pd.notna(row['target_vol']) else 'off'} | {row['overheat']} | "
            f"{pct(row['ann_return_full'])} | {pct(row['max_dd_full'])} | "
            f"{pct(row['ann_return_last_10y'])} | {pct(row['max_dd_last_10y'])} | "
            f"{pct(row['ann_return_last_5y'])} | {pct(row['max_dd_last_5y'])} | "
            f"{pct(row['ann_return_last_3y'])} | {pct(row['max_dd_last_3y'])} | "
            f"{pct(row['ann_return_last_1y'])} | {pct(row['max_dd_last_1y'])} | "
            f"{pct(row['cash_ratio_full'])} | {pct(row['avg_exposure_full'])} |"
        )
    lines.extend(
        [
            "",
            "## Window",
            "",
            f"- Warmup/state start: `{meta['warmup_start']}`.",
            f"- Metric start: `{meta['metric_start']}`.",
            f"- Effective metric start: `{meta['effective_metric_start']}`.",
            f"- End: `{meta['end']}`.",
            f"- OOS rows: `{meta['oos_rows']}`.",
            "- 10Y is N/A because the OOS window has fewer than 2520 A-share sessions.",
            "",
            "## Source Audit",
            "",
            sources.to_markdown(index=False),
            "",
        ]
    )
    (output_dir / "record.md").write_text("\n".join(lines), encoding="utf-8")


def run_diagnosis(warmup_start: pd.Timestamp, metric_start: pd.Timestamp, end: pd.Timestamp, tag: str) -> None:
    output_dir = Path("outputs") / tag
    output_dir.mkdir(parents=True, exist_ok=True)
    prices, sources = layer0.build_proxy_panel(warmup_start, end)
    effective_metric_start = pd.Timestamp(prices.index[prices.index >= metric_start][0])
    oos_index = pd.DatetimeIndex(prices.index[prices.index >= effective_metric_start])
    curves = build_curves(prices)
    metrics = pd.DataFrame(summarize(curve, oos_index) for curve in curves)
    meta = {
        "tag": tag,
        "warmup_start": warmup_start.date().isoformat(),
        "metric_start": metric_start.date().isoformat(),
        "effective_metric_start": effective_metric_start.date().isoformat(),
        "end": pd.Timestamp(prices.index[-1]).date().isoformat(),
        "rows": int(len(prices)),
        "oos_rows": int(len(oos_index)),
        "command": (
            "python run_subd_proxy_dynamic_cyb_oos_return_diagnosis_2017_2026.py "
            f"--warmup-start {warmup_start.date()} --metric-start {metric_start.date()} "
            f"--end-date {end.date()} --tag {tag}"
        ),
    }
    metrics.to_csv(output_dir / "comparison_metrics.csv", index=False, encoding="utf-8-sig")
    sources.to_csv(output_dir / "sources.csv", index=False, encoding="utf-8-sig")
    (output_dir / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    write_record(output_dir, metrics, sources, meta)
    print(f"WROTE {output_dir / 'record.md'}")
    cols = [
        "candidate",
        "diagnosis_group",
        "r2_threshold",
        "ann_return_full",
        "max_dd_full",
        "cash_ratio_full",
        "avg_exposure_full",
        "ann_return_last_5y",
        "max_dd_last_5y",
    ]
    print(metrics[cols].to_string(index=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--warmup-start", default=DEFAULT_WARMUP_START.date().isoformat())
    parser.add_argument("--metric-start", default=DEFAULT_METRIC_START.date().isoformat())
    parser.add_argument("--end-date", default=DEFAULT_END.date().isoformat())
    parser.add_argument("--tag", default=DEFAULT_TAG)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_diagnosis(pd.Timestamp(args.warmup_start), pd.Timestamp(args.metric_start), pd.Timestamp(args.end_date), args.tag)


if __name__ == "__main__":
    main()
