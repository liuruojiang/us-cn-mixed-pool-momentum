from __future__ import annotations

import argparse
import contextlib
import json
import time
from pathlib import Path
from typing import Iterator

import pandas as pd

import run_subd_proxy_dynamic_cyb_layer0 as layer0
import run_subd_proxy_dynamic_cyb_r2none_final_main_oos_2017_2026 as final_oos


DEFAULT_START = pd.Timestamp("2007-01-01")
DEFAULT_SPLIT_DATE = pd.Timestamp("2017-01-01")
DEFAULT_END = pd.Timestamp("2026-06-30")
DEFAULT_TAG = "subd_proxy_dynamic_cyb_r2none_final_main_qqq_gld_agg_cyb_2007_2026_20260702"

FOUR_CORE_ASSETS = {
    "QQQ": "NASDAQ_QQQ_ADJ_CLOSE_PROXY",
    "GLD": "GOLD_GLD_ADJ_CLOSE_PROXY",
    "AGG": "US_AGG_BOND_AGG_ADJ_CLOSE_PROXY",
}
FOUR_PROXY_ASSETS = {
    **FOUR_CORE_ASSETS,
    "CN_CYB_399006": "CHINEXT_INDEX_PROXY_DYNAMIC_ADD",
}


@contextlib.contextmanager
def patched_four_asset_pool() -> Iterator[None]:
    original_core = dict(layer0.CORE_ASSETS)
    original_proxy = dict(layer0.PROXY_ASSETS)
    try:
        layer0.CORE_ASSETS.clear()
        layer0.CORE_ASSETS.update(FOUR_CORE_ASSETS)
        layer0.PROXY_ASSETS.clear()
        layer0.PROXY_ASSETS.update(FOUR_PROXY_ASSETS)
        yield
    finally:
        layer0.CORE_ASSETS.clear()
        layer0.CORE_ASSETS.update(original_core)
        layer0.PROXY_ASSETS.clear()
        layer0.PROXY_ASSETS.update(original_proxy)


def build_slice(
    mode: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    prices, sources = layer0.build_proxy_panel(start_date, end_date)
    curve = final_oos.build_final_curve(prices)
    metric_index = pd.DatetimeIndex(prices.index)
    metrics = pd.DataFrame([final_oos.summarize_curve(curve, metric_index, mode)])
    yearly = final_oos.yearly_returns(curve, metric_index, mode)
    daily = final_oos.daily_output(curve, mode, metric_index)
    return metrics, yearly, daily, sources.assign(mode=mode)


def build_oos_continuous(
    start_date: pd.Timestamp,
    split_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    prices, sources = layer0.build_proxy_panel(start_date, end_date)
    curve = final_oos.build_final_curve(prices)
    metric_start = pd.Timestamp(prices.index[prices.index >= split_date][0])
    metric_index = pd.DatetimeIndex(prices.index[prices.index >= metric_start])
    mode = "oos_2017_2026_continuous_state_from_2007_four_asset_pool"
    metrics = pd.DataFrame([final_oos.summarize_curve(curve, metric_index, mode)])
    yearly = final_oos.yearly_returns(curve, metric_index, mode)
    daily = final_oos.daily_output(curve, mode, metric_index)
    return metrics, yearly, daily, sources.assign(mode=mode)


def source_summary(sources: pd.DataFrame) -> list[dict[str, object]]:
    keep_cols = [
        "mode",
        "code",
        "name",
        "source",
        "adjustment",
        "first_available",
        "first_used",
        "last",
        "rows",
        "last_aligned",
        "ffill_days_on_cn_calendar",
    ]
    cols = [col for col in keep_cols if col in sources.columns]
    return sources[cols].to_dict(orient="records")


def write_record(
    output_dir: Path,
    metrics: pd.DataFrame,
    yearly: pd.DataFrame,
    sources: pd.DataFrame,
    meta: dict[str, object],
) -> None:
    lines = [
        "# Sub-D R2-Removed Final Main Four-Asset Pool",
        "",
        "## Pool",
        "",
        "- Kept: `QQQ`, `GLD`, `AGG`, `CN_CYB_399006`.",
        "- Removed from this proxy run: `EWG`, `EWJ`, soymeal.",
        "- ChiNext still joins dynamically from its own first usable data; no CSI500 substitute and no backfill.",
        "",
        "## Frozen Parameter",
        "",
        f"- Candidate: `{final_oos.final_candidate_name()}`",
        "- R2 removed; target-vol off; momentum decay off.",
        "- Lookback `28`, switch buffer `1.15`, entry fraction `0.25`.",
        "- NAV defense enter `20%`, exit `5%`, scale `0.50`.",
        "- Fixed same-side overheat enter `15%`, exit `13%`, scale `0`, recovery `same_side_or_exit`.",
        "",
        "## Mandatory Windows",
        "",
        "| Mode | Full Ann. | Full MDD | 10Y Ann. | 10Y MDD | 5Y Ann. | 5Y MDD | 3Y Ann. | 3Y MDD | 1Y Ann. | 1Y MDD | 10Y Reason |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for _, row in metrics.iterrows():
        lines.append(
            "| "
            f"{row['mode']} | "
            f"{final_oos.pct(row['ann_return_full'])} | {final_oos.pct(row['max_dd_full'])} | "
            f"{final_oos.pct(row['ann_return_last_10y'])} | {final_oos.pct(row['max_dd_last_10y'])} | "
            f"{final_oos.pct(row['ann_return_last_5y'])} | {final_oos.pct(row['max_dd_last_5y'])} | "
            f"{final_oos.pct(row['ann_return_last_3y'])} | {final_oos.pct(row['max_dd_last_3y'])} | "
            f"{final_oos.pct(row['ann_return_last_1y'])} | {final_oos.pct(row['max_dd_last_1y'])} | "
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
            f"{row['mode']} | {int(row['year'])} | {final_oos.pct(row['return'])} | "
            f"{final_oos.pct(row['max_dd'])} | {int(row['days'])} |"
        )

    lines.extend(
        [
            "",
            "## Data And Execution Assumptions",
            "",
            f"- Requested start: `{meta['requested_start']}`.",
            f"- Split date: `{meta['split_date']}`.",
            f"- Requested end: `{meta['requested_end']}`.",
            "- This is proxy diagnostic research, not formal production ETF execution.",
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
            f"- Metrics: `{output_dir / 'metrics.csv'}`",
            f"- Yearly returns: `{output_dir / 'yearly_returns.csv'}`",
            f"- Daily curves: `{output_dir / 'daily_curves.csv'}`",
            f"- Sources: `{output_dir / 'sources.csv'}`",
            f"- Metadata: `{output_dir / 'metadata.json'}`",
            "",
        ]
    )
    (output_dir / "record.md").write_text("\n".join(lines), encoding="utf-8")


def run_four_asset_pool(start_date: pd.Timestamp, split_date: pd.Timestamp, end_date: pd.Timestamp, tag: str) -> None:
    started = time.time()
    output_dir = Path("outputs") / tag
    output_dir.mkdir(parents=True, exist_ok=True)

    with patched_four_asset_pool():
        train_end = split_date - pd.Timedelta(days=1)
        train = build_slice(
            "insample_2007_2016_four_asset_pool",
            start_date,
            train_end,
        )
        oos_reset = build_slice(
            "oos_2017_2026_standalone_reset_four_asset_pool",
            split_date,
            end_date,
        )
        oos_continuous = build_oos_continuous(start_date, split_date, end_date)

    metrics = pd.concat([train[0], oos_reset[0], oos_continuous[0]], ignore_index=True)
    yearly = pd.concat([train[1], oos_reset[1], oos_continuous[1]], ignore_index=True)
    daily = pd.concat([train[2], oos_reset[2], oos_continuous[2]], ignore_index=True)
    sources = pd.concat([train[3], oos_reset[3], oos_continuous[3]], ignore_index=True)
    meta = {
        "tag": tag,
        "candidate": final_oos.final_candidate_name(),
        "test_type": "final_main_reduced_proxy_pool_with_agg_bond_proxy",
        "requested_start": start_date.date().isoformat(),
        "split_date": split_date.date().isoformat(),
        "requested_end": end_date.date().isoformat(),
        "kept_assets": FOUR_PROXY_ASSETS,
        "removed_assets": {
            "EWG": "GERMANY_EWG_ADJ_CLOSE_PROXY",
            "EWJ": "JAPAN_EWJ_ADJ_CLOSE_PROXY",
            "159985/soymeal": "not included in proxy run",
        },
        "cost_model": {"one_way_cost": 0.001, "stale_trade_guard": True},
        "source_summary": source_summary(sources),
        "command": (
            "python run_subd_proxy_dynamic_cyb_r2none_final_main_qqq_gld_agg_cyb.py "
            f"--start-date {start_date.date()} --split-date {split_date.date()} "
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
    write_record(output_dir, metrics, yearly, sources, meta)

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
    parser.add_argument("--start-date", default=DEFAULT_START.date().isoformat())
    parser.add_argument("--split-date", default=DEFAULT_SPLIT_DATE.date().isoformat())
    parser.add_argument("--end-date", default=DEFAULT_END.date().isoformat())
    parser.add_argument("--tag", default=DEFAULT_TAG)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_four_asset_pool(
        pd.Timestamp(args.start_date),
        pd.Timestamp(args.split_date),
        pd.Timestamp(args.end_date),
        args.tag,
    )


if __name__ == "__main__":
    main()
