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


FORMAL_START = pd.Timestamp("2007-01-15")
DEFAULT_END = pd.Timestamp("2016-12-30")
LOOKBACK_START = pd.Timestamp("2006-12-01")
CSI500_PUBLICATION_DATE = pd.Timestamp("2007-01-15")
CSI500_FACTSHEET_URL = (
    "https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/"
    "000905factsheet.pdf"
)

PROXY_ASSETS = {
    "CN_ZZ500_000905": "CSI500_INDEX_PROXY_FOR_A_SHARE_LEG",
    "QQQ": "NASDAQ_QQQ_ADJ_CLOSE_PROXY",
    "EWG": "GERMANY_EWG_ADJ_CLOSE_PROXY",
    "EWJ": "JAPAN_EWJ_ADJ_CLOSE_PROXY",
    "GLD": "GOLD_GLD_ADJ_CLOSE_PROXY",
}


def fetch_eastmoney_index_close(secid: str, beg: str, end: str) -> pd.Series:
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
                rows = [item.split(",") for item in data]
                frame = pd.DataFrame(rows)
                series = pd.Series(
                    frame.iloc[:, 2].astype(float).to_numpy(),
                    index=pd.to_datetime(frame.iloc[:, 0]),
                    name="CN_ZZ500_000905",
                ).sort_index()
                return series
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
            if adj_list and "adjclose" in adj_list[0]:
                values = adj_list[0]["adjclose"]
            else:
                values = payload["indicators"]["quote"][0]["close"]
            index = pd.to_datetime(timestamps, unit="s", utc=True).tz_convert(None).normalize()
            series = pd.Series(values, index=index, name=ticker, dtype="float64").dropna().sort_index()
            series = series[~series.index.duplicated(keep="last")]
            if not series.empty:
                return series
        except Exception as exc:  # noqa: BLE001 - public market data can fail transiently.
            last_error = exc
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"Yahoo chart fetch failed for {ticker}: {last_error}")


def build_proxy_panel(end_date: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    csi_raw = fetch_eastmoney_index_close("1.000905", "20070101", end_date.strftime("%Y%m%d"))
    csi = csi_raw.loc[csi_raw.index >= FORMAL_START].loc[:end_date].copy()
    if csi.empty:
        raise RuntimeError("CSI500 proxy is empty after formal publication date")

    prices = pd.DataFrame(index=csi.index)
    prices["CN_ZZ500_000905"] = csi
    source_rows = [
        {
            "code": "CN_ZZ500_000905",
            "name": PROXY_ASSETS["CN_ZZ500_000905"],
            "source": "Eastmoney push2his kline secid=1.000905",
            "adjustment": "index close / price index",
            "publication_or_inception": CSI500_PUBLICATION_DATE.date().isoformat(),
            "raw_first": csi_raw.dropna().index.min().date().isoformat(),
            "first_used": csi.dropna().index.min().date().isoformat(),
            "last": csi.dropna().index.max().date().isoformat(),
            "rows": int(csi.dropna().shape[0]),
            "note": "Raw vendor rows before CSI publication are clipped.",
        }
    ]

    for ticker in ("QQQ", "EWG", "EWJ", "GLD"):
        raw = fetch_yahoo_adj_close(ticker, LOOKBACK_START, end_date)
        clipped = raw.loc[:end_date]
        prices[ticker] = clipped.reindex(prices.index)
        source_rows.append(
            {
                "code": ticker,
                "name": PROXY_ASSETS[ticker],
                "source": "Yahoo Finance chart API",
                "adjustment": "adjusted close",
                "publication_or_inception": clipped.dropna().index.min().date().isoformat(),
                "raw_first": raw.dropna().index.min().date().isoformat(),
                "first_used": clipped.dropna().index.min().date().isoformat(),
                "last": clipped.dropna().index.max().date().isoformat(),
                "rows": int(clipped.dropna().shape[0]),
                "note": "Reindexed to CSI500 trading calendar for this proxy diagnostic.",
            }
        )
    return prices, pd.DataFrame(source_rows)


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
            out.append(
                (
                    label,
                    None,
                    f"insufficient rows: {len(ordered)} < {trading_days} trading days after {FORMAL_START.date()}",
                )
            )
    return out


def curve_return(curve: pd.DataFrame) -> pd.Series:
    return curve["return"].astype(float).fillna(0.0)


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
    sources: pd.DataFrame,
    metadata: dict[str, object],
) -> None:
    v11_summary = summary[summary["scenario"].eq("v1_1_staged_50_plus_ma60_overheat")].copy()
    lines = [
        "# Sub-D Proxy ZZ500 2007-2016 Layer 0",
        "",
        "## Scope",
        "",
        "- Layer: 0 / data availability, proxy definition, and unchanged V1.0/V1.1 baseline reproduction.",
        "- A-share leg replacement: CSI500 price index proxy `CN_ZZ500_000905` replaces ChiNext proxy.",
        "- Soymeal leg is removed. Remaining overseas proxies: `QQQ`, `EWG`, `EWJ`, `GLD`.",
        "- This is proxy research, not a production ETF formal result.",
        "",
        "## Data And Execution Assumptions",
        "",
        f"- Formal proxy start: `{metadata['formal_start']}`.",
        f"- End date: `{metadata['end_date']}`.",
        f"- CSI500 publication evidence: {CSI500_FACTSHEET_URL}.",
        "- CSI500 data source: Eastmoney `push2his` daily close for `1.000905`; vendor rows before publication are clipped.",
        "- US proxy data source: Yahoo Finance chart API adjusted close.",
        "- Calendar: CSI500 trading dates. US proxy prices are reindexed to this calendar and forward-filled by the official aligner.",
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
            "## Source Audit",
            "",
            sources.to_markdown(index=False),
            "",
            "## Artifacts",
            "",
            f"- Summary: `{output_dir / 'summary.csv'}`",
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


def run_layer0(end_date: pd.Timestamp, tag: str) -> None:
    output_dir = Path("outputs") / tag
    docs_dir = Path("docs") / tag
    output_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    prices, sources = build_proxy_panel(end_date)
    original_assets = dict(subd.ASSETS)
    try:
        subd.ASSETS.clear()
        subd.ASSETS.update(PROXY_ASSETS)
        config = subd.RunConfig(
            source="akshare_em_qfq",
            one_way_cost=v11.ONE_WAY_COST,
            start_date=FORMAL_START,
            end_date=end_date,
            output_tag=tag,
            target_vols=(),
            vol_window=subd.DEFAULT_VOL_WINDOW,
            max_lev=subd.DEFAULT_MAX_LEV,
        )
        aligned, common_last, last_by_asset = v11.align_prices_to_common_valid_date(
            prices, list(subd.ASSETS), calendar_validation_mode="required"
        )
        aligned = aligned.loc[aligned.index >= FORMAL_START].copy()
        curves = v11.build_curves(aligned, config)

        summary_rows = []
        for curve in curves:
            for window, start, reason in mandatory_window_specs(aligned.index):
                if reason:
                    summary_rows.append(
                        {
                            "version": curve["version"].iloc[0],
                            "scenario": curve["scenario"].iloc[0],
                            "window": window,
                            "start": None,
                            "end": common_last.date().isoformat(),
                            "days": int(len(aligned)),
                            "total": np.nan,
                            "cagr": np.nan,
                            "maxdd": np.nan,
                            "reason": reason,
                        }
                    )
                else:
                    row = v11.summarize(curve, start, window)
                    row["reason"] = ""
                    summary_rows.append(row)
        summary = pd.DataFrame(summary_rows)

        daily = pd.concat(curves, axis=0).reset_index()
        asset_metrics = pd.DataFrame(asset_metric(aligned[col], col) for col in aligned.columns)
        flags = aligned.attrs.get("price_ffill_flags")
        ffill_counts = {
            col: int(flags[col].sum()) for col in aligned.columns
        } if isinstance(flags, pd.DataFrame) else {}
        curve_mdd_periods = {
            curve["scenario"].iloc[0]: mdd_period_from_returns(curve_return(curve)) for curve in curves
        }
        yearly = []
        v11_curve = next(curve for curve in curves if curve["scenario"].iloc[0] == "v1_1_staged_50_plus_ma60_overheat")
        for year, group in v11_curve.groupby(v11_curve.index.year):
            yearly.append(
                {
                    "year": int(year),
                    "return": float((1.0 + curve_return(group)).prod() - 1.0),
                    "days": int(len(group)),
                }
            )
        yearly_df = pd.DataFrame(yearly)

        metadata = {
            "tag": tag,
            "layer": "Layer 0",
            "formal_start": FORMAL_START.date().isoformat(),
            "end_date": end_date.date().isoformat(),
            "common_last": common_last.date().isoformat(),
            "rows_after_start": int(len(aligned)),
            "proxy_assets": PROXY_ASSETS,
            "csi500_publication_date": CSI500_PUBLICATION_DATE.date().isoformat(),
            "csi500_factsheet_url": CSI500_FACTSHEET_URL,
            "last_by_asset": {
                key: pd.Timestamp(value).date().isoformat() if pd.notna(value) else None
                for key, value in last_by_asset.items()
            },
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
            "command": f"python run_subd_proxy_zz500_layer0.py --end-date {end_date.date()} --tag {tag}",
        }

        summary.to_csv(output_dir / "summary.csv", index=False, encoding="utf-8-sig")
        daily.to_csv(output_dir / "daily_curves.csv", index=False, encoding="utf-8-sig")
        sources.to_csv(output_dir / "sources.csv", index=False, encoding="utf-8-sig")
        asset_metrics.to_csv(output_dir / "asset_metrics.csv", index=False, encoding="utf-8-sig")
        yearly_df.to_csv(output_dir / "v11_yearly.csv", index=False, encoding="utf-8-sig")
        subd.data_quality(aligned).to_csv(output_dir / "data_quality.csv", index=False, encoding="utf-8-sig")
        (output_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        write_record(docs_dir, output_dir, summary, sources, metadata)

        print(f"WROTE {output_dir / 'summary.csv'}")
        print(f"WROTE {output_dir / 'daily_curves.csv'}")
        print(f"WROTE {docs_dir / 'record.md'}")
        print(summary.to_string(index=False))
    finally:
        subd.ASSETS.clear()
        subd.ASSETS.update(original_assets)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Sub-D proxy ZZ500 standard-process Layer 0.")
    parser.add_argument("--end-date", default=DEFAULT_END.date().isoformat())
    parser.add_argument("--tag", default="subd_proxy_zz500_2007_2016_layer0")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_layer0(pd.Timestamp(args.end_date).normalize(), args.tag)


if __name__ == "__main__":
    main()
