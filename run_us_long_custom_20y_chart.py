from __future__ import annotations

import importlib.util
import json
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import yfinance as yf


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "outputs" / "us_long_custom_20y_20260701"
BOT_PATH = ROOT / "mnt_bot V 7.6 plus.py"

START_DATE = pd.Timestamp("2006-07-01")
END_EXCLUSIVE = "2026-07-02"
RUN_DATE = "2026-07-01"

TARGET_WEIGHTS = {
    "SPY": 0.20,
    "QQQ": 0.20,
    "VT": 0.20,
    "GLD": 0.15,
    "AGG": 0.15,
    "DBC": 0.05,
    "BTC": 0.05,
}

YF_SYMBOLS = [
    "SPY",
    "QQQ",
    "VT",
    "GLD",
    "AGG",
    "DBC",
    "BTC-USD",
    "EFA",
    "EEM",
    "BIL",
]

VT_PROXY_WEIGHTS = {"SPY": 0.60, "EFA": 0.30, "EEM": 0.10}
NASDAQ_CHECK_SYMBOLS = ["SPY", "QQQ", "GLD", "AGG"]


def load_bot_module():
    spec = importlib.util.spec_from_file_location("mnt_bot_v76_plus", BOT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {BOT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_close_from_yfinance() -> pd.DataFrame:
    raw = yf.download(
        YF_SYMBOLS,
        start=START_DATE.strftime("%Y-%m-%d"),
        end=END_EXCLUSIVE,
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if raw.empty:
        raise RuntimeError("yfinance returned no data")
    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"].copy()
    else:
        close = raw.copy()
    close.index = pd.to_datetime(close.index).tz_localize(None)
    return close.sort_index()


def build_vt_proxy(close: pd.DataFrame, master_index: pd.DatetimeIndex) -> tuple[pd.Series, dict]:
    direct_vt = close["VT"].reindex(master_index)
    first_vt_date = direct_vt.first_valid_index()
    if first_vt_date is None:
        raise RuntimeError("VT has no valid data")

    proxy_prices = close[list(VT_PROXY_WEIGHTS)].reindex(master_index).ffill()
    proxy_returns = proxy_prices.pct_change().fillna(0.0)
    weighted_proxy_ret = sum(proxy_returns[sym] * w for sym, w in VT_PROXY_WEIGHTS.items())
    synthetic_nav = (1.0 + weighted_proxy_ret).cumprod()
    scale = float(direct_vt.loc[first_vt_date] / synthetic_nav.loc[first_vt_date])
    synthetic_price = synthetic_nav * scale

    vt_proxy = direct_vt.copy()
    vt_proxy.loc[vt_proxy.index < first_vt_date] = synthetic_price.loc[synthetic_price.index < first_vt_date]
    vt_proxy = vt_proxy.ffill()
    info = {
        "first_vt_date": first_vt_date.strftime("%Y-%m-%d"),
        "proxy_weights": VT_PROXY_WEIGHTS,
        "scale_to_vt_on_first_date": scale,
    }
    return vt_proxy.rename("VT_PROXY"), info


def build_price_frame(close: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    core = ["SPY", "QQQ", "GLD", "AGG", "DBC", "EFA", "EEM"]
    master_index = close[core].dropna(how="any").index
    master_index = master_index[master_index >= START_DATE]
    master_index = master_index[master_index <= close[["SPY", "QQQ", "GLD", "AGG", "DBC"]].dropna().index[-1]]
    if master_index.empty:
        raise RuntimeError("No master US ETF session index")

    vt_proxy, vt_info = build_vt_proxy(close, master_index)
    out = pd.DataFrame(index=master_index)
    for sym in ["SPY", "QQQ", "GLD", "AGG", "DBC", "BIL"]:
        out[sym] = close[sym].reindex(master_index)
    out["VT_PROXY"] = vt_proxy
    out["BTC-USD"] = close["BTC-USD"].reindex(master_index).ffill()
    out = out.sort_index()

    btc_first = out["BTC-USD"].first_valid_index()
    if btc_first is None:
        raise RuntimeError("BTC-USD has no valid data")
    info = {
        "master_start": out.index[0].strftime("%Y-%m-%d"),
        "master_end": out.index[-1].strftime("%Y-%m-%d"),
        "master_rows": int(len(out)),
        "btc_first_us_session": btc_first.strftime("%Y-%m-%d"),
        "vt_proxy": vt_info,
    }
    return out, info


def available_weights(date: pd.Timestamp, btc_first_date: pd.Timestamp) -> dict[str, float]:
    weights = TARGET_WEIGHTS.copy()
    if date < btc_first_date:
        weights.pop("BTC")
        total = sum(weights.values())
        weights = {asset: weight / total for asset, weight in weights.items()}
    return weights


def target_proxy(asset: str) -> str:
    if asset == "VT":
        return "VT_PROXY"
    if asset == "BTC":
        return "BTC-USD"
    return asset


def is_month_end(index: pd.DatetimeIndex, pos: int) -> bool:
    if pos == len(index) - 1:
        return True
    return index[pos].to_period("M") != index[pos + 1].to_period("M")


def simulate_annual_rebalanced_daily(
    prices: pd.DataFrame,
    commission: float,
    rebalance_month: int,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.DataFrame]:
    returns = prices.pct_change().fillna(0.0)
    btc_first = prices["BTC-USD"].first_valid_index()
    if btc_first is None:
        raise RuntimeError("BTC-USD missing")

    holdings: dict[str, float] = {}
    nav_values = []
    ret_values = []
    cost_values = []
    weight_rows = []
    prev_nav = 1.0

    for i, date in enumerate(prices.index):
        if i == 0:
            weights = available_weights(date, btc_first)
            holdings = {asset: weights[asset] for asset in weights}
            nav = sum(holdings.values())
            nav_values.append(nav)
            ret_values.append(0.0)
            cost_values.append(0.0)
            weight_rows.append({asset: holdings.get(asset, 0.0) / nav for asset in TARGET_WEIGHTS})
            prev_nav = nav
            continue

        for asset in list(holdings):
            proxy = target_proxy(asset)
            r = returns.loc[date, proxy] if proxy in returns.columns else 0.0
            if pd.isna(r):
                r = 0.0
            holdings[asset] *= 1.0 + float(r)

        nav = sum(holdings.values())
        daily_cost = 0.0
        must_rebalance = False
        if prices.index[i - 1] < btc_first <= date and "BTC" not in holdings:
            must_rebalance = True
        if date.month == rebalance_month and is_month_end(prices.index, i):
            must_rebalance = True

        if must_rebalance and nav > 0:
            weights = available_weights(date, btc_first)
            current = {asset: holdings.get(asset, 0.0) for asset in weights}
            turnover = sum(abs(nav * weights[asset] - current.get(asset, 0.0)) for asset in weights) / nav
            daily_cost = turnover * commission * nav
            nav -= daily_cost
            holdings = {asset: nav * weights[asset] for asset in weights}

        nav_values.append(nav)
        ret_values.append(nav / prev_nav - 1.0 if prev_nav else 0.0)
        cost_values.append(daily_cost / prev_nav if prev_nav else 0.0)
        weight_rows.append({asset: holdings.get(asset, 0.0) / nav if nav else 0.0 for asset in TARGET_WEIGHTS})
        prev_nav = nav

    nav = pd.Series(nav_values, index=prices.index, name="buy_hold_nav")
    ret = pd.Series(ret_values, index=prices.index, name="buy_hold_return")
    costs = pd.Series(cost_values, index=prices.index, name="rebalance_cost")
    weights = pd.DataFrame(weight_rows, index=prices.index)
    return ret, nav, costs, weights


def metric_row(label: str, returns: pd.Series) -> dict:
    returns = returns.dropna()
    if len(returns) < 20:
        return {
            "window": label,
            "start": "N/A",
            "end": "N/A",
            "years": np.nan,
            "annual_return": np.nan,
            "max_drawdown": np.nan,
        }
    nav = (1.0 + returns).cumprod()
    years = (returns.index[-1] - returns.index[0]).days / 365.25
    annual = nav.iloc[-1] ** (1.0 / years) - 1.0 if years > 0 else np.nan
    drawdown = nav / nav.cummax() - 1.0
    return {
        "window": label,
        "start": returns.index[0].strftime("%Y-%m-%d"),
        "end": returns.index[-1].strftime("%Y-%m-%d"),
        "years": years,
        "annual_return": annual,
        "max_drawdown": drawdown.min(),
    }


def build_metrics(returns: pd.DataFrame) -> pd.DataFrame:
    last_date = returns.index[-1]
    windows = [("Full", None), ("10Y", 10), ("5Y", 5), ("3Y", 3), ("1Y", 1)]
    rows = []
    for curve_name in returns.columns:
        for label, years in windows:
            if years is None:
                part = returns[curve_name]
            else:
                part = returns.loc[returns.index >= last_date - pd.DateOffset(years=years), curve_name]
            row = metric_row(label, part)
            row["curve"] = curve_name
            rows.append(row)
    return pd.DataFrame(rows)


def fetch_nasdaq_crosscheck(close: pd.DataFrame) -> pd.DataFrame:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.nasdaq.com",
        "Referer": "https://www.nasdaq.com/",
    }
    rows = []
    for symbol in NASDAQ_CHECK_SYMBOLS:
        url = (
            f"https://api.nasdaq.com/api/quote/{symbol}/historical"
            "?assetclass=etf&fromdate=2026-06-01&todate=2026-06-30&limit=9999"
        )
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            resp.raise_for_status()
            payload = resp.json()
            items = payload.get("data", {}).get("tradesTable", {}).get("rows", [])
            latest = items[0] if items else {}
            yf_june = close[symbol].loc["2026-06-01":"2026-06-30"].dropna()
            nasdaq_close = float(str(latest.get("close", "")).replace("$", "").replace(",", ""))
            yf_latest = float(yf_june.iloc[-1]) if len(yf_june) else np.nan
            rows.append(
                {
                    "symbol": symbol,
                    "source": "Nasdaq historical API",
                    "nasdaq_rows_2026_06": len(items),
                    "yfinance_rows_2026_06": int(len(yf_june)),
                    "nasdaq_latest_date": latest.get("date"),
                    "nasdaq_latest_close": nasdaq_close,
                    "yfinance_latest_date": yf_june.index[-1].strftime("%Y-%m-%d") if len(yf_june) else "N/A",
                    "yfinance_latest_close": yf_latest,
                    "latest_close_abs_diff": abs(nasdaq_close - yf_latest) if not pd.isna(yf_latest) else np.nan,
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "symbol": symbol,
                    "source": "Nasdaq historical API",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return pd.DataFrame(rows)


def write_chart(curves: pd.DataFrame, metrics: pd.DataFrame, out_path: Path) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(12.5, 7.2))
    ax.plot(curves.index, curves["strategy_nav"], label="US Long Strategy (Sub-C vol scaled)", linewidth=2.2)
    ax.plot(curves.index, curves["buy_hold_nav"], label="Buy & Hold (annual rebalance)", linewidth=2.0)
    ax.set_title("20Y Custom Allocation NAV: Strategy vs Annual Rebalanced Buy & Hold")
    ax.set_ylabel("NAV, start = 1.0")
    ax.set_xlabel("")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.28)
    ax.text(
        0.01,
        0.01,
        "Weights: SPY 20%, QQQ 20%, VT 20%, GLD 15%, AGG 15%, DBC 5%, BTC 5%. "
        "VT pre-inception proxy: 60% SPY/30% EFA/10% EEM. BTC pre-history excluded and remaining weights normalized.",
        transform=ax.transAxes,
        fontsize=8,
        alpha=0.75,
    )
    fig.autofmt_xdate(rotation=25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def fmt_pct(value: float) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{value:.2%}"


def write_record(
    out_dir: Path,
    run_info: dict,
    metrics: pd.DataFrame,
    source_manifest: pd.DataFrame,
    crosscheck: pd.DataFrame,
) -> None:
    lines = [
        "# Custom US Long 20Y NAV Chart",
        "",
        f"- Run date: {RUN_DATE}",
        f"- Code path: `run_us_long_custom_20y_chart.py`",
        f"- Production source inspected/imported: `mnt_bot V 7.6 plus.py`",
        "- Strategy identity: Sub-C US long production parameters; current source has timing disabled and target-vol scaling enabled.",
        f"- Window: {run_info['master_start']} to {run_info['master_end']} ({run_info['master_rows']} US sessions).",
        "- Market/session: US ETF trading sessions; BTC is aligned to US sessions with forward-filled crypto closes on ETF session dates.",
        "- Price mode: Yahoo/yfinance adjusted close (`auto_adjust=True`).",
        "- Frictions: annual rebalance one-way commission 0.10%; strategy additionally applies Sub-C target-vol financing/rebalance costs from source parameters.",
        "",
        "## Proxy Rules",
        "",
        "- SP500 leg: SPY.",
        "- Bond leg: AGG.",
        "- VT before VT data exists: synthetic 60% SPY / 30% EFA / 10% EEM daily-return proxy, scaled to VT on VT first valid date.",
        f"- VT first valid date: {run_info['vt_proxy']['first_vt_date']}.",
        f"- BTC first valid US session: {run_info['btc_first_us_session']}; before that, BTC is excluded and the remaining target weights are normalized.",
        "",
        "## Metrics",
        "",
        "| Curve | Window | Start | End | Years | Annualized Return | Max Drawdown |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in metrics.iterrows():
        years = "N/A" if pd.isna(row["years"]) else f"{row['years']:.2f}"
        lines.append(
            f"| {row['curve']} | {row['window']} | {row['start']} | {row['end']} | "
            f"{years} | {fmt_pct(row['annual_return'])} | {fmt_pct(row['max_drawdown'])} |"
        )
    lines.extend(
        [
            "",
            "## Data Manifest",
            "",
            "| Symbol | First Date | Last Date | Rows | First Close | Last Close | Source | Note |",
            "|---|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for _, row in source_manifest.iterrows():
        lines.append(
            f"| {row['symbol']} | {row['first_date']} | {row['last_date']} | {row['rows']} | "
            f"{row['first_close']} | {row['last_close']} | {row['source']} | {row['note']} |"
        )
    lines.extend(
        [
            "",
            "## Cross-Check",
            "",
            "- Nasdaq historical API was used for June 2026 close/row-count checks on SPY, QQQ, GLD, and AGG.",
            "- Stooq was attempted as a broader independent source, but returned an anti-automation verification page followed by `Access denied` in this environment.",
            "",
            "| Symbol | Nasdaq Rows | Yahoo Rows | Nasdaq Latest | Yahoo Latest | Close Diff | Error |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for _, row in crosscheck.iterrows():
        lines.append(
            f"| {row.get('symbol', '')} | {row.get('nasdaq_rows_2026_06', '')} | "
            f"{row.get('yfinance_rows_2026_06', '')} | {row.get('nasdaq_latest_close', '')} | "
            f"{row.get('yfinance_latest_close', '')} | {row.get('latest_close_abs_diff', '')} | "
            f"{row.get('error', '') if pd.notna(row.get('error', np.nan)) else ''} |"
        )
    lines.extend(
        [
            "",
            "## Output Files",
            "",
            "- `nav_chart.png`",
            "- `daily_curves.csv`",
            "- `window_metrics.csv`",
            "- `source_manifest.csv`",
            "- `nasdaq_crosscheck.csv`",
            "- `run_info.json`",
            "",
            "## Caveats",
            "",
            "- This is a research/proxy chart, not a pure seven-ticker live-tradable 20-year history.",
            "- The 2006-2008 VT segment is synthetic, and the 2006-2014 BTC segment is phase-excluded.",
            "- Nasdaq cross-check validates recent raw closes and row counts only; the backtest return path uses Yahoo adjusted close.",
        ]
    )
    (out_dir / "record.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bot = load_bot_module()
    close = get_close_from_yfinance()
    prices, run_info = build_price_frame(close)

    raw_ret, buy_hold_nav, rebal_cost, weights = simulate_annual_rebalanced_daily(
        prices,
        commission=float(bot.PROD_COMMISSION),
        rebalance_month=int(bot.PROD_REBAL_MONTH),
    )
    if bool(bot.PROD_VS_ENABLED):
        strategy_ret, strategy_scale, strategy_vs_cost = bot._apply_subc_vol_scaling(raw_ret, prices)
    else:
        strategy_ret = raw_ret.copy()
        strategy_scale = pd.Series(1.0, index=raw_ret.index)
        strategy_vs_cost = pd.Series(0.0, index=raw_ret.index)

    strategy_nav = (1.0 + strategy_ret.fillna(0.0)).cumprod()
    buy_hold_nav = (1.0 + raw_ret.fillna(0.0)).cumprod()
    curves = pd.DataFrame(
        {
            "strategy_return": strategy_ret,
            "buy_hold_return": raw_ret,
            "strategy_nav": strategy_nav,
            "buy_hold_nav": buy_hold_nav,
            "strategy_scale": strategy_scale,
            "strategy_vs_cost": strategy_vs_cost,
            "annual_rebalance_cost": rebal_cost,
        }
    )
    curves.index.name = "date"
    curves.to_csv(OUT_DIR / "daily_curves.csv", float_format="%.10f")
    weights.to_csv(OUT_DIR / "effective_target_weights.csv", float_format="%.10f")

    metrics = build_metrics(curves[["strategy_return", "buy_hold_return"]])
    metrics.to_csv(OUT_DIR / "window_metrics.csv", index=False, float_format="%.10f")

    manifest_rows = []
    for symbol in YF_SYMBOLS:
        ser = close[symbol].dropna() if symbol in close.columns else pd.Series(dtype=float)
        manifest_rows.append(
            {
                "symbol": symbol,
                "first_date": ser.index[0].strftime("%Y-%m-%d") if len(ser) else "N/A",
                "last_date": ser.index[-1].strftime("%Y-%m-%d") if len(ser) else "N/A",
                "rows": int(len(ser)),
                "first_close": round(float(ser.iloc[0]), 6) if len(ser) else "N/A",
                "last_close": round(float(ser.iloc[-1]), 6) if len(ser) else "N/A",
                "source": "Yahoo Finance via yfinance auto_adjust=True",
                "note": "",
            }
        )
    manifest_rows.append(
        {
            "symbol": "VT_PROXY",
            "first_date": prices["VT_PROXY"].first_valid_index().strftime("%Y-%m-%d"),
            "last_date": prices["VT_PROXY"].dropna().index[-1].strftime("%Y-%m-%d"),
            "rows": int(prices["VT_PROXY"].dropna().shape[0]),
            "first_close": round(float(prices["VT_PROXY"].dropna().iloc[0]), 6),
            "last_close": round(float(prices["VT_PROXY"].dropna().iloc[-1]), 6),
            "source": "Synthetic before VT inception, Yahoo VT afterward",
            "note": "60% SPY / 30% EFA / 10% EEM before first VT date",
        }
    )
    source_manifest = pd.DataFrame(manifest_rows)
    source_manifest.to_csv(OUT_DIR / "source_manifest.csv", index=False)

    crosscheck = fetch_nasdaq_crosscheck(close)
    crosscheck.to_csv(OUT_DIR / "nasdaq_crosscheck.csv", index=False)

    write_chart(curves, metrics, OUT_DIR / "nav_chart.png")
    run_info.update(
        {
            "run_at": datetime.now().isoformat(timespec="seconds"),
            "target_weights": TARGET_WEIGHTS,
            "source_parameters": {
                "PROD_USE_TIMING": bool(bot.PROD_USE_TIMING),
                "PROD_VS_ENABLED": bool(bot.PROD_VS_ENABLED),
                "PROD_VS_TARGET_VOL": float(bot.PROD_VS_TARGET_VOL),
                "PROD_VS_VOL_WINDOW": int(bot.PROD_VS_VOL_WINDOW),
                "PROD_VS_MAX_LEV": float(bot.PROD_VS_MAX_LEV),
                "PROD_VS_MIN_LEV": float(bot.PROD_VS_MIN_LEV),
                "PROD_VS_THRESHOLD": float(bot.PROD_VS_THRESHOLD),
                "PROD_COMMISSION": float(bot.PROD_COMMISSION),
                "PROD_REBAL_MONTH": int(bot.PROD_REBAL_MONTH),
                "PROD_CASH": str(bot.PROD_CASH),
            },
        }
    )
    (OUT_DIR / "run_info.json").write_text(json.dumps(run_info, indent=2), encoding="utf-8")
    write_record(OUT_DIR, run_info, metrics, source_manifest, crosscheck)

    print(f"wrote {OUT_DIR}")
    print(curves.tail(1).T.to_string())
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
