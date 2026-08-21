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
DEFAULT_TAG = "subd_proxy_dynamic_cyb_r2none_final_main_qqq_gld_emxc_cyb_2007_2026_20260702"
EMXC_SWITCH_DATE = pd.Timestamp("2017-08-01")

CORE_ASSETS_WITH_EMXC_PROXY = {
    "QQQ": "NASDAQ_QQQ_ADJ_CLOSE_PROXY",
    "GLD": "GOLD_GLD_ADJ_CLOSE_PROXY",
    "EMXC": "EM_EX_CHINA_EMXC_SPLICED_EEM_PROXY",
}
PROXY_ASSETS_WITH_EMXC_PROXY = {
    **CORE_ASSETS_WITH_EMXC_PROXY,
    "CN_CYB_399006": "CHINEXT_INDEX_PROXY_DYNAMIC_ADD",
}


@contextlib.contextmanager
def patched_emxc_pool() -> Iterator[None]:
    original_core = dict(layer0.CORE_ASSETS)
    original_proxy = dict(layer0.PROXY_ASSETS)
    try:
        layer0.CORE_ASSETS.clear()
        layer0.CORE_ASSETS.update(CORE_ASSETS_WITH_EMXC_PROXY)
        layer0.PROXY_ASSETS.clear()
        layer0.PROXY_ASSETS.update(PROXY_ASSETS_WITH_EMXC_PROXY)
        yield
    finally:
        layer0.CORE_ASSETS.clear()
        layer0.CORE_ASSETS.update(original_core)
        layer0.PROXY_ASSETS.clear()
        layer0.PROXY_ASSETS.update(original_proxy)


def build_emxc_spliced_series(
    lookback_start: pd.Timestamp,
    end_date: pd.Timestamp,
) -> tuple[pd.Series, dict[str, object]]:
    eem = layer0.fetch_yahoo_adj_close("EEM", lookback_start, end_date)
    hybrid = eem.rename("EMXC").copy()
    if end_date < EMXC_SWITCH_DATE:
        return hybrid, {
            "eem_first": eem.index.min().date().isoformat(),
            "eem_last": eem.index.max().date().isoformat(),
            "eem_rows": int(len(eem)),
            "emxc_first": None,
            "emxc_last": None,
            "emxc_rows": 0,
            "switch_date": EMXC_SWITCH_DATE.date().isoformat(),
            "first_emxc_date_used": None,
            "scale_factor": None,
        }

    emxc = layer0.fetch_yahoo_adj_close("EMXC", lookback_start, end_date)
    emxc_aligned = emxc.reindex(hybrid.index)
    switch_idx = hybrid.index >= EMXC_SWITCH_DATE
    first_emxc_date = emxc_aligned.loc[switch_idx].first_valid_index()
    if first_emxc_date is None:
        raise RuntimeError("EMXC has no valid prices after switch date")
    scale_factor = float(hybrid.loc[first_emxc_date] / emxc_aligned.loc[first_emxc_date])
    hybrid.loc[switch_idx] = emxc_aligned.loc[switch_idx] * scale_factor
    hybrid = hybrid.dropna().rename("EMXC")
    meta = {
        "eem_first": eem.index.min().date().isoformat(),
        "eem_last": eem.index.max().date().isoformat(),
        "eem_rows": int(len(eem)),
        "emxc_first": emxc.index.min().date().isoformat(),
        "emxc_last": emxc.index.max().date().isoformat(),
        "emxc_rows": int(len(emxc)),
        "switch_date": EMXC_SWITCH_DATE.date().isoformat(),
        "first_emxc_date_used": pd.Timestamp(first_emxc_date).date().isoformat(),
        "scale_factor": scale_factor,
    }
    return hybrid, meta


def build_proxy_panel_with_emxc_proxy(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    calendar = layer0.load_cn_calendar(start_date, end_date)
    lookback_start = start_date - pd.Timedelta(days=60)
    raw_series: dict[str, pd.Series] = {}
    source_rows: list[dict[str, object]] = []

    for ticker, label in {
        "QQQ": CORE_ASSETS_WITH_EMXC_PROXY["QQQ"],
        "GLD": CORE_ASSETS_WITH_EMXC_PROXY["GLD"],
    }.items():
        raw = layer0.fetch_yahoo_adj_close(ticker, lookback_start, end_date)
        raw_series[ticker] = raw
        used = raw.loc[raw.index >= start_date].dropna()
        source_rows.append(
            {
                "code": ticker,
                "name": label,
                "source": "Yahoo Finance chart API",
                "adjustment": "adjusted close",
                "first_available": raw.dropna().index.min().date().isoformat(),
                "first_used": used.index.min().date().isoformat(),
                "last": raw.dropna().index.max().date().isoformat(),
                "rows": int(raw.dropna().shape[0]),
                "pool_rule": "core asset available from 2007 start",
            }
        )

    emxc_hybrid, emxc_meta = build_emxc_spliced_series(lookback_start, end_date)
    raw_series["EMXC"] = emxc_hybrid
    emxc_used = emxc_hybrid.loc[emxc_hybrid.index >= start_date].dropna()
    source_rows.append(
        {
            "code": "EMXC",
            "name": CORE_ASSETS_WITH_EMXC_PROXY["EMXC"],
            "source": "Yahoo Finance chart API; EEM spliced to scaled EMXC",
            "adjustment": "adjusted close; EMXC scaled to EEM at switch",
            "first_available": emxc_hybrid.dropna().index.min().date().isoformat(),
            "first_used": emxc_used.index.min().date().isoformat(),
            "last": emxc_hybrid.dropna().index.max().date().isoformat(),
            "rows": int(emxc_hybrid.dropna().shape[0]),
            "pool_rule": "EEM proxy before 2017-08-01; scaled EMXC after switch",
            "proxy_switch_date": emxc_meta["switch_date"],
            "proxy_input_eem_first": emxc_meta["eem_first"],
            "proxy_input_eem_last": emxc_meta["eem_last"],
            "proxy_input_emxc_first": emxc_meta["emxc_first"],
            "proxy_input_emxc_last": emxc_meta["emxc_last"],
            "proxy_scale_factor": emxc_meta["scale_factor"],
        }
    )

    cyb_raw = layer0.fetch_eastmoney_index_close(
        "0.399006",
        layer0.CHINEXT_FIRST_USED.strftime("%Y%m%d"),
        end_date.strftime("%Y%m%d"),
        "CN_CYB_399006",
    )
    cyb = cyb_raw.loc[cyb_raw.index >= layer0.CHINEXT_FIRST_USED]
    raw_series["CN_CYB_399006"] = cyb
    source_rows.append(
        {
            "code": "CN_CYB_399006",
            "name": PROXY_ASSETS_WITH_EMXC_PROXY["CN_CYB_399006"],
            "source": "Eastmoney push2his kline secid=0.399006",
            "adjustment": "index close / price index",
            "first_available": cyb.dropna().index.min().date().isoformat(),
            "first_used": cyb.dropna().index.min().date().isoformat(),
            "last": cyb.dropna().index.max().date().isoformat(),
            "rows": int(cyb.dropna().shape[0]),
            "pool_rule": "dynamic asset; no prices before 2010-06-01 and no backfill",
        }
    )

    raw_prices = pd.concat(raw_series.values(), axis=1).sort_index()
    aligned, flags, last_by_asset = layer0.dynamic_align_to_calendar(
        raw_prices,
        calendar,
        list(CORE_ASSETS_WITH_EMXC_PROXY),
        list(PROXY_ASSETS_WITH_EMXC_PROXY),
    )
    sources = pd.DataFrame(source_rows)
    sources["last_aligned"] = sources["code"].map(
        lambda code: last_by_asset[code].date().isoformat() if pd.notna(last_by_asset[code]) else None
    )
    sources["ffill_days_on_cn_calendar"] = sources["code"].map(lambda code: int(flags[code].sum()))
    return aligned, sources


def build_slice(
    mode: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    prices, sources = build_proxy_panel_with_emxc_proxy(start_date, end_date)
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
    prices, sources = build_proxy_panel_with_emxc_proxy(start_date, end_date)
    curve = final_oos.build_final_curve(prices)
    metric_start = pd.Timestamp(prices.index[prices.index >= split_date][0])
    metric_index = pd.DatetimeIndex(prices.index[prices.index >= metric_start])
    mode = "oos_2017_2026_continuous_state_from_2007_emxc_proxy_pool"
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
        "pool_rule",
        "proxy_switch_date",
        "proxy_scale_factor",
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
        "# Sub-D R2-Removed Final Main EMXC Proxy Pool",
        "",
        "## Pool",
        "",
        "- Kept: `QQQ`, `GLD`, `EMXC` spliced with `EEM`, `CN_CYB_399006`.",
        "- Removed from this proxy run: `AGG`, `EWG`, `EWJ`, soymeal.",
        "- EMXC rule: `EEM` before `2017-08-01`; scaled `EMXC` after switch.",
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


def run_emxc_proxy_pool(start_date: pd.Timestamp, split_date: pd.Timestamp, end_date: pd.Timestamp, tag: str) -> None:
    started = time.time()
    output_dir = Path("outputs") / tag
    output_dir.mkdir(parents=True, exist_ok=True)

    with patched_emxc_pool():
        train_end = split_date - pd.Timedelta(days=1)
        train = build_slice(
            "insample_2007_2016_emxc_proxy_pool",
            start_date,
            train_end,
        )
        oos_reset = build_slice(
            "oos_2017_2026_standalone_reset_emxc_proxy_pool",
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
        "test_type": "final_main_reduced_proxy_pool_with_emxc_eem_splice",
        "requested_start": start_date.date().isoformat(),
        "split_date": split_date.date().isoformat(),
        "requested_end": end_date.date().isoformat(),
        "kept_assets": PROXY_ASSETS_WITH_EMXC_PROXY,
        "removed_assets": {
            "AGG": "removed per user request",
            "EWG": "GERMANY_EWG_ADJ_CLOSE_PROXY",
            "EWJ": "JAPAN_EWJ_ADJ_CLOSE_PROXY",
            "159985/soymeal": "not included in proxy run",
        },
        "emxc_proxy_rule": {
            "ticker_requested_by_user": "EXMC or proxy",
            "ticker_used": "EMXC",
            "invalid_ticker_probe": "EXMC returned Yahoo chart 404",
            "proxy_before_switch": "EEM",
            "switch_date": EMXC_SWITCH_DATE.date().isoformat(),
            "splice_method": "scale EMXC to EEM on first valid EMXC date after switch",
        },
        "cost_model": {"one_way_cost": 0.001, "stale_trade_guard": True},
        "source_summary": source_summary(sources),
        "command": (
            "python run_subd_proxy_dynamic_cyb_r2none_final_main_qqq_gld_emxc_cyb.py "
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
    run_emxc_proxy_pool(
        pd.Timestamp(args.start_date),
        pd.Timestamp(args.split_date),
        pd.Timestamp(args.end_date),
        args.tag,
    )


if __name__ == "__main__":
    main()
