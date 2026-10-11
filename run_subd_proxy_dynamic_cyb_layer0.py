from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

import research_subd_six_etf_weighted_slope as subd
import run_subd_six_etf_v1_1 as v11


DEFAULT_START = pd.Timestamp("2007-01-01")
DEFAULT_END = pd.Timestamp("2016-12-30")
CHINEXT_FIRST_USED = pd.Timestamp("2010-06-01")
TRADING_CALENDAR_PATH = Path("outputs/cn_trading_days_cache.csv")

CORE_ASSETS = {
    "QQQ": "NASDAQ_QQQ_ADJ_CLOSE_PROXY",
    "EWG": "GERMANY_EWG_ADJ_CLOSE_PROXY",
    "EWJ": "JAPAN_EWJ_ADJ_CLOSE_PROXY",
    "GLD": "GOLD_GLD_ADJ_CLOSE_PROXY",
}

PROXY_ASSETS = {
    **CORE_ASSETS,
    "CN_CYB_399006": "CHINEXT_INDEX_PROXY_DYNAMIC_ADD",
}


def fetch_eastmoney_index_close(secid: str, beg: str, end: str, name: str) -> pd.Series:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json,text/plain,*/*",
        }
    )
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "klt": "101",
        "fqt": "1",
        "beg": beg,
        "end": end,
        "secid": secid,
    }
    last_error = None
    for attempt in range(1, 5):
        try:
            response = session.get(url, params=params, timeout=20)
            response.raise_for_status()
            data = (response.json().get("data") or {}).get("klines") or []
            if data:
                frame = pd.DataFrame([item.split(",") for item in data])
                return pd.Series(
                    frame.iloc[:, 2].astype(float).to_numpy(),
                    index=pd.to_datetime(frame.iloc[:, 0]),
                    name=name,
                ).sort_index()
        except Exception as exc:  # noqa: BLE001 - public market data can fail transiently.
            last_error = exc
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"Eastmoney index fetch failed for {secid}: {last_error}")


def fetch_yahoo_adj_close(ticker: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    period1 = int(start.tz_localize("UTC").timestamp())
    period2 = int((end + pd.Timedelta(days=1)).tz_localize("UTC").timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {
        "period1": period1,
        "period2": period2,
        "interval": "1d",
        "events": "history|div|split",
        "includeAdjustedClose": "true",
    }
    last_error = None
    for attempt in range(1, 5):
        try:
            response = session.get(url, params=params, timeout=20)
            response.raise_for_status()
            payload = response.json()["chart"]["result"][0]
            timestamps = payload.get("timestamp") or []
            adj_list = payload["indicators"].get("adjclose") or []
            values = (
                adj_list[0]["adjclose"]
                if adj_list and "adjclose" in adj_list[0]
                else payload["indicators"]["quote"][0]["close"]
            )
            index = pd.to_datetime(timestamps, unit="s", utc=True).tz_convert(None).normalize()
            series = pd.Series(values, index=index, name=ticker, dtype="float64").dropna().sort_index()
            series = series[~series.index.duplicated(keep="last")]
            if not series.empty:
                return series
        except Exception as exc:  # noqa: BLE001 - public market data can fail transiently.
            last_error = exc
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"Yahoo chart fetch failed for {ticker}: {last_error}")


def load_cn_calendar(start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.DatetimeIndex:
    if not TRADING_CALENDAR_PATH.exists():
        raise FileNotFoundError(f"Missing CN trading calendar cache: {TRADING_CALENDAR_PATH}")
    calendar = pd.read_csv(TRADING_CALENDAR_PATH, parse_dates=["trade_date"])["trade_date"]
    calendar = pd.DatetimeIndex(calendar).normalize().unique().sort_values()
    calendar = calendar[(calendar >= start_date.normalize()) & (calendar <= end_date.normalize())]
    if calendar.empty:
        raise RuntimeError(f"No CN trading days between {start_date.date()} and {end_date.date()}")
    return pd.DatetimeIndex(calendar)


def dynamic_align_to_calendar(
    raw_prices: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    core_cols: list[str],
    all_cols: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.Timestamp]]:
    raw = raw_prices.copy()
    raw.index = pd.DatetimeIndex(raw.index).normalize()
    raw = raw.reindex(calendar)
    aligned = pd.DataFrame(index=calendar)
    last_by_asset: dict[str, pd.Timestamp] = {}
    for col in all_cols:
        series = pd.to_numeric(raw[col], errors="coerce") if col in raw else pd.Series(index=calendar, dtype=float)
        finite = series.notna() & np.isfinite(series.to_numpy(dtype=float)) & (series > 0)
        if series.notna().any() and not finite[series.notna()].all():
            first_bad = series.index[series.notna() & ~finite][0]
            raise ValueError(f"{col} has non-finite or non-positive close at {pd.Timestamp(first_bad).date()}")
        valid = series.dropna()
        if valid.empty:
            aligned[col] = np.nan
            last_by_asset[col] = pd.NaT
            continue
        filled = series.ffill()
        filled.loc[filled.index < valid.index.min()] = np.nan
        aligned[col] = filled
        last_by_asset[col] = pd.Timestamp(valid.index.max())

    core_valid = aligned[core_cols].notna().all(axis=1)
    if not core_valid.any():
        raise RuntimeError("No date has all four core proxy assets available")
    start = pd.Timestamp(aligned.index[core_valid][0])
    aligned = aligned.loc[start:].copy()
    raw = raw.loc[aligned.index].copy()
    flags = pd.DataFrame(False, index=aligned.index, columns=all_cols)
    for col in all_cols:
        flags[col] = aligned[col].notna() & raw[col].isna()
    aligned.attrs["price_ffill_flags"] = flags.astype(bool)
    return aligned, flags.astype(bool), last_by_asset


def build_proxy_panel(start_date: pd.Timestamp, end_date: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    calendar = load_cn_calendar(start_date, end_date)
    lookback_start = start_date - pd.Timedelta(days=60)
    raw_series: dict[str, pd.Series] = {}
    source_rows = []

    for ticker, label in CORE_ASSETS.items():
        raw = fetch_yahoo_adj_close(ticker, lookback_start, end_date)
        raw_series[ticker] = raw
        source_rows.append(
            {
                "code": ticker,
                "name": label,
                "source": "Yahoo Finance chart API",
                "adjustment": "adjusted close",
                "first_available": raw.dropna().index.min().date().isoformat(),
                "first_used": raw.loc[raw.index >= start_date].dropna().index.min().date().isoformat(),
                "last": raw.dropna().index.max().date().isoformat(),
                "rows": int(raw.dropna().shape[0]),
                "pool_rule": "core asset available from 2007 start",
            }
        )

    cyb_raw = fetch_eastmoney_index_close(
        "0.399006",
        CHINEXT_FIRST_USED.strftime("%Y%m%d"),
        end_date.strftime("%Y%m%d"),
        "CN_CYB_399006",
    )
    cyb = cyb_raw.loc[cyb_raw.index >= CHINEXT_FIRST_USED]
    raw_series["CN_CYB_399006"] = cyb
    source_rows.append(
        {
            "code": "CN_CYB_399006",
            "name": PROXY_ASSETS["CN_CYB_399006"],
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
    aligned, flags, last_by_asset = dynamic_align_to_calendar(
        raw_prices,
        calendar,
        list(CORE_ASSETS),
        list(PROXY_ASSETS),
    )
    sources = pd.DataFrame(source_rows)
    sources["last_aligned"] = sources["code"].map(
        lambda code: last_by_asset[code].date().isoformat() if pd.notna(last_by_asset[code]) else None
    )
    sources["ffill_days_on_cn_calendar"] = sources["code"].map(lambda code: int(flags[code].sum()))
    return aligned, sources


def mandatory_window_specs(index: pd.Index) -> list[tuple[str, pd.Timestamp | None, str | None]]:
    ordered = pd.DatetimeIndex(index).sort_values()
    specs = [
        ("Full", None),
        ("10Y", 10 * subd.TRADING_DAYS),
        ("5Y", 5 * subd.TRADING_DAYS),
        ("3Y", 3 * subd.TRADING_DAYS),
        ("1Y", subd.TRADING_DAYS),
    ]
    out: list[tuple[str, pd.Timestamp | None, str | None]] = []
    for label, trading_days in specs:
        if trading_days is None:
            out.append((label, pd.Timestamp(ordered[0]), None))
        elif len(ordered) >= trading_days:
            out.append((label, pd.Timestamp(ordered[-trading_days]), None))
        else:
            out.append((label, None, f"insufficient rows: {len(ordered)} < {trading_days} trading days"))
    return out


def curve_return(curve: pd.DataFrame) -> pd.Series:
    return curve["return"].astype(float).fillna(0.0)


def summarize_window(curve: pd.DataFrame, start: pd.Timestamp, label: str) -> dict[str, object]:
    row = v11.summarize(curve, start, label)
    row["reason"] = ""
    return row


def mdd_period_from_returns(ret: pd.Series) -> dict[str, object]:
    wealth = (1.0 + ret).cumprod()
    peak = wealth.cummax().clip(lower=1.0)
    drawdown = wealth / peak - 1.0
    trough = drawdown.idxmin()
    peak_date = wealth.loc[:trough].idxmax()
    return {
        "peak": pd.Timestamp(peak_date).date().isoformat(),
        "trough": pd.Timestamp(trough).date().isoformat(),
        "maxdd": float(drawdown.loc[trough]),
    }


def asset_metric(series: pd.Series, label: str) -> dict[str, object]:
    clean = series.dropna().astype(float)
    ret = clean.pct_change().fillna(0.0)
    wealth = (1.0 + ret).cumprod()
    years = len(clean) / subd.TRADING_DAYS
    return {
        "asset": label,
        "start": clean.index[0].date().isoformat(),
        "end": clean.index[-1].date().isoformat(),
        "days": int(len(clean)),
        "total": float(wealth.iloc[-1] - 1.0),
        "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0),
        "maxdd": subd.max_drawdown(wealth),
        "vol": float(ret.std(ddof=0) * math.sqrt(subd.TRADING_DAYS)),
    }


def format_pct(value: object) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value) * 100:.2f}%"


def write_record(
    docs_dir: Path,
    output_dir: Path,
    summary: pd.DataFrame,
    extra_windows: pd.DataFrame,
    sources: pd.DataFrame,
    metadata: dict[str, object],
) -> None:
    v11_summary = summary[summary["scenario"].eq("v1_1_staged_50_plus_ma60_overheat")]
    v11_extra = extra_windows[extra_windows["scenario"].eq("v1_1_staged_50_plus_ma60_overheat")]
    lines = [
        "# Sub-D Dynamic ChiNext Proxy 2007-2016 Layer 0",
        "",
        "## Scope",
        "",
        "- Layer: 0 / data availability, dynamic-pool definition, and unchanged V1.0/V1.1 baseline reproduction.",
        "- Pool rule: `QQQ`, `EWG`, `EWJ`, and `GLD` participate from the 2007 start; `CN_CYB_399006` joins only after its own data exists.",
        "- ChiNext is not backfilled and CSI500 is not used as an asset.",
        "- This is proxy research, not a production ETF formal result.",
        "",
        "## Data And Execution Assumptions",
        "",
        f"- Effective sample start: `{metadata['effective_start']}`.",
        f"- End date: `{metadata['end_date']}`.",
        "- Calendar: repo-local A-share trading-day cache. US proxy adjusted closes are reindexed to this calendar and forward-filled by rule.",
        "- ChiNext rule: no prices before `2010-06-01`; it can only be ranked once a full 25-trading-day slope window exists.",
        "- Costs and overlays: unchanged V1.1 function chain, one-way cost `0.001`, R2 threshold `0.20`, target vol `0.25`, max leverage `1.5`, 50% staged entry, MA60 same-side overheat.",
        "",
        "## Mandatory Window Baseline",
        "",
        "| Window | Start | End | Ann. Return | Max Drawdown | Reason |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for _, row in v11_summary.iterrows():
        lines.append(
            "| "
            f"{row['window']} | "
            f"{row.get('start') or 'N/A'} | "
            f"{row.get('end') or 'N/A'} | "
            f"{format_pct(row.get('cagr'))} | "
            f"{format_pct(row.get('maxdd'))} | "
            f"{row.get('reason') or ''} |"
        )
    lines.extend(
        [
            "",
            "## Requested Extra Windows",
            "",
            "| Window | Start | End | Ann. Return | Max Drawdown |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for _, row in v11_extra.iterrows():
        lines.append(
            "| "
            f"{row['window']} | "
            f"{row.get('start') or 'N/A'} | "
            f"{row.get('end') or 'N/A'} | "
            f"{format_pct(row.get('cagr'))} | "
            f"{format_pct(row.get('maxdd'))} |"
        )
    lines.extend(
        [
            "",
            "## Source Audit",
            "",
            sources.to_markdown(index=False),
            "",
            "## Artifacts",
            "",
            f"- Summary: `{output_dir / 'summary.csv'}`",
            f"- Extra windows: `{output_dir / 'extra_windows.csv'}`",
            f"- Daily curves: `{output_dir / 'daily_curves.csv'}`",
            f"- Sources: `{output_dir / 'sources.csv'}`",
            f"- Asset metrics: `{output_dir / 'asset_metrics.csv'}`",
            f"- Metadata: `{output_dir / 'metadata.json'}`",
            "",
            "## Stop Point",
            "",
            "Layer 0 is complete. Next layer is Layer 1 raw weighted-slope parameter width test; do not continue without explicit approval.",
            "",
        ]
    )
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "record.md").write_text("\n".join(lines), encoding="utf-8")


def run_layer0(start_date: pd.Timestamp, end_date: pd.Timestamp, tag: str) -> None:
    output_dir = Path("outputs") / tag
    docs_dir = Path("docs") / tag
    output_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    prices, sources = build_proxy_panel(start_date, end_date)
    original_assets = dict(subd.ASSETS)
    try:
        subd.ASSETS.clear()
        subd.ASSETS.update(PROXY_ASSETS)
        config = subd.RunConfig(
            source="akshare_em_qfq",
            one_way_cost=v11.ONE_WAY_COST,
            start_date=pd.Timestamp(prices.index[0]),
            end_date=end_date,
            output_tag=tag,
            target_vols=(),
            vol_window=subd.DEFAULT_VOL_WINDOW,
            max_lev=subd.DEFAULT_MAX_LEV,
        )
        curves = v11.build_curves(prices, config)

        summary_rows = []
        for curve in curves:
            for window, start, reason in mandatory_window_specs(prices.index):
                if reason:
                    summary_rows.append(
                        {
                            "version": curve["version"].iloc[0],
                            "scenario": curve["scenario"].iloc[0],
                            "window": window,
                            "start": None,
                            "end": end_date.date().isoformat(),
                            "days": int(len(prices)),
                            "total": np.nan,
                            "cagr": np.nan,
                            "maxdd": np.nan,
                            "reason": reason,
                        }
                    )
                else:
                    summary_rows.append(summarize_window(curve, start, window))
        summary = pd.DataFrame(summary_rows)

        extra_starts = {
            "from_2010_06_01_cyb_available": CHINEXT_FIRST_USED,
            "from_2011_01_01": pd.Timestamp("2011-01-01"),
        }
        extra_rows = []
        for curve in curves:
            for label, start in extra_starts.items():
                actual = pd.DatetimeIndex(curve.index)[pd.DatetimeIndex(curve.index) >= start]
                if len(actual):
                    extra_rows.append(summarize_window(curve, pd.Timestamp(actual[0]), label))
        extra_windows = pd.DataFrame(extra_rows)

        daily = pd.concat(curves, axis=0).reset_index()
        asset_metrics = pd.DataFrame(asset_metric(prices[col], col) for col in prices.columns)
        flags = prices.attrs.get("price_ffill_flags")
        ffill_counts = {
            col: int(flags[col].sum()) for col in prices.columns
        } if isinstance(flags, pd.DataFrame) else {}
        curve_mdd_periods = {
            curve["scenario"].iloc[0]: mdd_period_from_returns(curve_return(curve)) for curve in curves
        }
        v11_curve = next(curve for curve in curves if curve["scenario"].iloc[0] == "v1_1_staged_50_plus_ma60_overheat")
        yearly = pd.DataFrame(
            {
                "year": int(year),
                "return": float((1.0 + curve_return(group)).prod() - 1.0),
                "days": int(len(group)),
            }
            for year, group in v11_curve.groupby(v11_curve.index.year)
        )
        score_cols = [f"score_{code}" for code in PROXY_ASSETS]
        first_score_dates = {}
        for code in PROXY_ASSETS:
            col = f"score_{code}"
            first_valid = v11_curve.index[v11_curve[col].notna()] if col in v11_curve else []
            first_score_dates[code] = pd.Timestamp(first_valid[0]).date().isoformat() if len(first_valid) else None

        metadata = {
            "tag": tag,
            "layer": "Layer 0",
            "requested_start": start_date.date().isoformat(),
            "effective_start": pd.Timestamp(prices.index[0]).date().isoformat(),
            "end_date": end_date.date().isoformat(),
            "rows": int(len(prices)),
            "proxy_assets": PROXY_ASSETS,
            "core_assets": CORE_ASSETS,
            "dynamic_asset": "CN_CYB_399006",
            "dynamic_asset_first_price": CHINEXT_FIRST_USED.date().isoformat(),
            "first_score_dates": first_score_dates,
            "ffill_counts_on_cn_calendar": ffill_counts,
            "curve_mdd_periods": curve_mdd_periods,
            "config": {
                "lookback": subd.LOOKBACK,
                "r2_threshold": v11.R2_THRESHOLD,
                "target_vol": v11.TARGET_VOL,
                "target_vol_rebalance_threshold": v11.TARGET_VOL_SCALE_REBALANCE_THRESHOLD,
                "switch_buffer": v11.SWITCH_BUFFER,
                "v10_switch_buffer": v11.V10_BASELINE_SWITCH_BUFFER,
                "initial_entry_fraction": v11.INITIAL_ENTRY_FRACTION,
                "overheat_enter": v11.OVERHEAT_ENTER,
                "overheat_exit": v11.OVERHEAT_EXIT,
                "overheat_derisk_scale": v11.OVERHEAT_DERISK_SCALE,
                "one_way_cost": v11.ONE_WAY_COST,
                "vol_window": subd.DEFAULT_VOL_WINDOW,
                "max_lev": subd.DEFAULT_MAX_LEV,
            },
            "command": f"python run_subd_proxy_dynamic_cyb_layer0.py --start-date {start_date.date()} --end-date {end_date.date()} --tag {tag}",
        }

        summary.to_csv(output_dir / "summary.csv", index=False, encoding="utf-8-sig")
        extra_windows.to_csv(output_dir / "extra_windows.csv", index=False, encoding="utf-8-sig")
        daily.to_csv(output_dir / "daily_curves.csv", index=False, encoding="utf-8-sig")
        sources.to_csv(output_dir / "sources.csv", index=False, encoding="utf-8-sig")
        asset_metrics.to_csv(output_dir / "asset_metrics.csv", index=False, encoding="utf-8-sig")
        yearly.to_csv(output_dir / "v11_yearly.csv", index=False, encoding="utf-8-sig")
        subd.data_quality(prices).to_csv(output_dir / "data_quality.csv", index=False, encoding="utf-8-sig")
        (output_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        write_record(docs_dir, output_dir, summary, extra_windows, sources, metadata)

        print(f"WROTE {output_dir / 'summary.csv'}")
        print(f"WROTE {output_dir / 'extra_windows.csv'}")
        print(f"WROTE {output_dir / 'daily_curves.csv'}")
        print(f"WROTE {docs_dir / 'record.md'}")
        print(summary.to_string(index=False))
        print("\nEXTRA WINDOWS")
        print(extra_windows.to_string(index=False))
        print("\nFIRST SCORE DATES")
        print(json.dumps(first_score_dates, ensure_ascii=False, indent=2))
    finally:
        subd.ASSETS.clear()
        subd.ASSETS.update(original_assets)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Sub-D dynamic ChiNext proxy standard-process Layer 0.")
    parser.add_argument("--start-date", default=DEFAULT_START.date().isoformat())
    parser.add_argument("--end-date", default=DEFAULT_END.date().isoformat())
    parser.add_argument("--tag", default="subd_proxy_dynamic_cyb_2007_2016_layer0")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_layer0(pd.Timestamp(args.start_date).normalize(), pd.Timestamp(args.end_date).normalize(), args.tag)


if __name__ == "__main__":
    main()
