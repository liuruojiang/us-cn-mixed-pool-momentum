# poe: name=SubD-Six-ETF-V11
# poe: privacy_shield=half
import math
import re
import sys
import time
import warnings
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Literal, Optional, Tuple

import numpy as np
import pandas as pd
import requests
from fastapi_poe.types import SettingsResponse

try:
    import akshare as ak
    _HAS_AKSHARE = True
except ImportError:
    _HAS_AKSHARE = False


try:
    poe
except NameError:
    try:
        import fastapi_poe as poe
    except Exception:
        poe = None


class _LocalBotError(Exception):
    pass


class _LocalQuery:
    text = " ".join(sys.argv[1:]).strip() or "参数"


class _LocalMessage:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def write(self, value):
        sys.stdout.buffer.write(str(value).encode("utf-8", errors="replace"))
        sys.stdout.buffer.flush()

    def overwrite(self, value):
        sys.stdout.buffer.write(str(value).encode("utf-8", errors="replace"))
        sys.stdout.buffer.flush()

    def attach_file(self, *_args, **_kwargs):
        return None


class _PoeCompatProxy:
    def __init__(self, base):
        self._base = base

    def __getattr__(self, name):
        if self._base is not None and hasattr(self._base, name):
            return getattr(self._base, name)
        if name == "BotError":
            return _LocalBotError
        if name == "query":
            return _LocalQuery()
        if name == "start_message":
            return lambda: _LocalMessage()
        if name == "update_settings":
            return lambda _settings: None
        raise AttributeError(name)


poe = _PoeCompatProxy(poe)


# ════════════════════════════════════════════════════════════════
#  Constants
# ════════════════════════════════════════════════════════════════

ASSETS = {
    "159915.SZ": "CYB100_ETF",
    "159941.SZ": "NASDAQ_ETF",
    "513030.SH": "GERMANY_ETF",
    "513520.SH": "NIKKEI_ETF",
    "159985.SZ": "SOYMEAL_ETF",
    "518880.SH": "GOLD_ETF",
}

ASSET_NAMES = {
    "159915.SZ": "创业板100ETF",
    "159941.SZ": "纳指ETF",
    "513030.SH": "德国ETF",
    "513520.SH": "日经ETF",
    "159985.SZ": "豆粕ETF",
    "518880.SH": "黄金ETF",
    "CASH": "现金",
}

# --- Scoring ---
LOOKBACK = 25
TRADING_DAYS = 252
SCORE_MIN = 0.0
SCORE_MAX = 5.0
DEFAULT_VOL_WINDOW = 80
DEFAULT_MAX_LEV = 1.5

# --- V1.1 Strategy ---
VERSION = "1.1"
START_DATE = pd.Timestamp("2010-01-01")
EVAL_START = pd.Timestamp("2020-01-02")
R2_THRESHOLD = 0.20
TARGET_VOL = 0.25
SWITCH_BUFFER = 1.00
INITIAL_ENTRY_FRACTION = 0.50
OVERHEAT_ENTER = 0.20
OVERHEAT_EXIT = 0.18
OVERHEAT_DERISK_SCALE = 0.0
ONE_WAY_COST = 0.001
CN_BIAS_N = 60
CN_MOM_DAY = 20

V11_SCENARIO = "v1_1_staged_50_plus_ma60_overheat"


# ════════════════════════════════════════════════════════════════
#  Data Classes
# ════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RunConfig:
    source: Literal["sina", "eastmoney"]
    one_way_cost: float
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    output_tag: str
    target_vols: tuple[float, ...]
    vol_window: int
    max_lev: float


@dataclass(frozen=True)
class EntryCase:
    label: str
    mode: Literal["full_entry", "all_new_asset_50_wait_down"]
    initial_fraction: float = 1.0


@dataclass(frozen=True)
class OverheatCase:
    label: str
    enter: float
    exit: float
    derisk_scale: float


# ════════════════════════════════════════════════════════════════
#  Data Loading
# ════════════════════════════════════════════════════════════════

def _sina_symbol(code: str) -> str:
    ticker, suffix = code.split(".")
    return f"{'sz' if suffix == 'SZ' else 'sh'}{ticker}"


def _eastmoney_market_id(code: str) -> str:
    ticker, suffix = code.split(".")
    return f"{'0' if suffix == 'SZ' else '1'}.{ticker}"


def _tencent_symbol(code: str) -> str:
    ticker, suffix = code.split(".")
    return f"{'sz' if suffix == 'SZ' else 'sh'}{ticker}"


HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://gu.qq.com/",
}


def _source_record(code: str, source: str, adjustment: str, close: pd.Series) -> dict:
    non_na = close.dropna()
    if non_na.empty:
        raise RuntimeError(f"{source} returned empty close series for {code}")
    return {
        "code": code,
        "name": ASSETS[code],
        "source": source,
        "adjustment": adjustment,
        "first": non_na.index.min().date().isoformat(),
        "last": non_na.index.max().date().isoformat(),
        "rows": int(non_na.shape[0]),
    }


def _load_sina_close(codes: list[str], end_date: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    series: list[pd.Series] = []
    sources: list[dict] = []
    for code in codes:
        symbol = _sina_symbol(code)
        df = ak.fund_etf_hist_sina(symbol=symbol)
        if df.empty:
            raise RuntimeError(f"Sina returned no rows for {code} / {symbol}")
        close = df[["date", "close"]].copy()
        close["date"] = pd.to_datetime(close["date"])
        close = close.set_index("date")["close"].astype(float).sort_index()
        close = close.loc[:end_date]
        close.name = code
        series.append(close)
        sources.append(_source_record(code, "akshare.fund_etf_hist_sina raw close", "raw/unadjusted as served by Sina", close))
    return pd.concat(series, axis=1).sort_index(), pd.DataFrame(sources)


def _load_eastmoney_one_close(code: str, end_date: pd.Timestamp) -> pd.Series:
    """Fallback: fetch historical kline from Eastmoney HTTP API (fqt=0 = unadjusted)."""
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "klt": "101",
        "fqt": "0",
        "beg": "20100101",
        "end": end_date.strftime("%Y%m%d"),
        "secid": _eastmoney_market_id(code),
    }
    data = None
    last_error = None
    for attempt in range(1, 4):
        try:
            resp = requests.get(url, params=params, timeout=20, headers=HTTP_HEADERS)
            resp.raise_for_status()
            data = (resp.json().get("data") or {}).get("klines") or []
            if data:
                break
        except Exception as exc:
            last_error = exc
        time.sleep(1.5 * attempt)
    if not data:
        raise RuntimeError(f"Eastmoney returned no data for {code}; last_error={last_error}")
    rows = [item.split(",") for item in data]
    df = pd.DataFrame(rows)
    col_names = [
        "date", "open", "close", "high", "low", "volume",
        "amount", "amplitude", "pct_change", "px_change", "turnover_rate",
    ]
    df = df.iloc[:, :len(col_names)]
    df.columns = col_names
    close = df[["date", "close"]].copy()
    close["date"] = pd.to_datetime(close["date"])
    close = close.set_index("date")["close"].astype(float).sort_index()
    close = close.loc[:end_date]
    close.name = code
    return close


def _load_cnfin_one_close(code: str, end_date: pd.Timestamp) -> pd.Series:
    url = "https://quotedata.cnfin.com/quote/v1/kline"
    current = pd.Timestamp("2010-01-01")
    end = pd.Timestamp(end_date).normalize()
    rows: list[list] = []
    fields: list[str] = []
    errors: list[str] = []

    while current <= end:
        window_end = min(current + pd.DateOffset(years=8) - pd.Timedelta(days=1), end)
        params = {
            "prod_code": code,
            "candle_period": "6",
            "get_type": "range",
            "start_date": current.strftime("%Y%m%d"),
            "end_date": window_end.strftime("%Y%m%d"),
            "fields": "open_px,high_px,low_px,close_px,business_amount,business_balance",
        }
        data = None
        last_error = None
        for attempt in range(1, 4):
            try:
                resp = requests.get(url, params=params, timeout=20, headers=HTTP_HEADERS)
                resp.raise_for_status()
                payload = resp.json()
                candle = (payload.get("data") or {}).get("candle") or {}
                chunk_rows = candle.get(code) or []
                chunk_fields = candle.get("fields") or []
                if "min_time" in chunk_fields and "close_px" in chunk_fields:
                    data = (chunk_rows, chunk_fields)
                    break
            except Exception as exc:
                last_error = exc
            time.sleep(1.5 * attempt)
        if data is None:
            errors.append(f"{current.date()}~{window_end.date()}: {last_error}")
        else:
            chunk_rows, chunk_fields = data
            rows.extend(chunk_rows)
            fields = chunk_fields
        current = window_end + pd.Timedelta(days=1)

    if not rows or "min_time" not in fields or "close_px" not in fields:
        raise RuntimeError(f"CNFin returned no data for {code}; errors={' | '.join(errors[-3:])}")
    date_idx = fields.index("min_time")
    close_idx = fields.index("close_px")
    df = pd.DataFrame(
        {
            "date": [str(int(row[date_idx])) for row in rows],
            "close": [row[close_idx] for row in rows],
        }
    )
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
    close = df.drop_duplicates("date").set_index("date")["close"].astype(float).sort_index()
    close = close.loc[:end_date]
    close.name = code
    return close


def _load_tencent_one_close(code: str, end_date: pd.Timestamp) -> pd.Series:
    url = "https://web.ifzq.gtimg.cn/appstock/app/kline/kline"
    symbol = _tencent_symbol(code)
    start = pd.Timestamp("2010-01-01")
    end = pd.Timestamp(end_date).normalize()
    current = start
    rows: list[list] = []
    errors: list[str] = []

    while current <= end:
        window_end = min(current + pd.DateOffset(years=8) - pd.Timedelta(days=1), end)
        params = {
            "param": f"{symbol},day,{current.date().isoformat()},{window_end.date().isoformat()},2000",
        }
        data = None
        last_error = None
        for attempt in range(1, 4):
            try:
                resp = requests.get(url, params=params, timeout=20, headers=HTTP_HEADERS)
                resp.raise_for_status()
                payload = resp.json()
                root = (payload.get("data") or {}).get(symbol) if isinstance(payload.get("data"), dict) else {}
                data = (root or {}).get("day") or []
                break
            except Exception as exc:
                last_error = exc
            time.sleep(1.5 * attempt)
        if data is None:
            errors.append(f"{current.date()}~{window_end.date()}: {last_error}")
        else:
            rows.extend(data)
        current = window_end + pd.Timedelta(days=1)

    if not rows:
        raise RuntimeError(f"Tencent returned no data for {code}; errors={' | '.join(errors[-3:])}")
    df = pd.DataFrame(rows)
    df = df.iloc[:, :3]
    df.columns = ["date", "open", "close"]
    df["date"] = pd.to_datetime(df["date"])
    close = df.drop_duplicates("date").set_index("date")["close"].astype(float).sort_index()
    close = close.loc[:end]
    close.name = code
    return close


def _load_eastmoney_close(codes: list[str], end_date: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    series: list[pd.Series] = []
    sources: list[dict] = []
    for code in codes:
        close = _load_eastmoney_one_close(code, end_date)
        series.append(close)
        sources.append(_source_record(code, "Eastmoney push2his kline", "raw/unadjusted (fqt=0)", close))
    return pd.concat(series, axis=1).sort_index(), pd.DataFrame(sources)


def _load_cnfin_close(codes: list[str], end_date: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    series: list[pd.Series] = []
    sources: list[dict] = []
    for code in codes:
        close = _load_cnfin_one_close(code, end_date)
        series.append(close)
        sources.append(_source_record(code, "CNFin quotedata kline", "raw/unadjusted close_px", close))
    return pd.concat(series, axis=1).sort_index(), pd.DataFrame(sources)


def _load_tencent_close(codes: list[str], end_date: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    series: list[pd.Series] = []
    sources: list[dict] = []
    for code in codes:
        close = _load_tencent_one_close(code, end_date)
        series.append(close)
        sources.append(_source_record(code, "Tencent gu.qq kline", "raw/unadjusted day close", close))
    return pd.concat(series, axis=1).sort_index(), pd.DataFrame(sources)


def _load_public_close_with_per_code_fallback(codes: list[str], end_date: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    series: list[pd.Series] = []
    sources: list[dict] = []
    errors: list[str] = []
    for code in codes:
        for source_name, adjustment, loader in (
            ("CNFin quotedata kline", "raw/unadjusted close_px", _load_cnfin_one_close),
            ("Tencent gu.qq kline", "raw/unadjusted day close", _load_tencent_one_close),
            ("Eastmoney push2his kline", "raw/unadjusted (fqt=0)", _load_eastmoney_one_close),
        ):
            try:
                close = loader(code, end_date)
                series.append(close)
                sources.append(_source_record(code, source_name, adjustment, close))
                break
            except Exception as exc:
                errors.append(f"{code} {source_name}: {str(exc)[:160]}")
        else:
            raise RuntimeError("All public data sources failed. " + " | ".join(errors[-6:]))
    return pd.concat(series, axis=1).sort_index(), pd.DataFrame(sources)


def load_close(config: RunConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    codes = list(ASSETS)
    if _HAS_AKSHARE:
        try:
            return _load_sina_close(codes, config.end_date)
        except Exception:
            pass
    return _load_public_close_with_per_code_fallback(codes, config.end_date)


# ════════════════════════════════════════════════════════════════
#  Scoring (weighted log-slope + R²)
# ════════════════════════════════════════════════════════════════

def weighted_slope_score_and_r2(window: pd.Series) -> tuple[float, float]:
    values = window.dropna().astype(float)
    if len(values) != LOOKBACK or (values <= 0).any():
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
    score = math.exp(float(slope) * TRADING_DAYS) - 1.0
    return score, r2


def calc_scores(
    prices: pd.DataFrame,
    idx: int,
    r2_threshold: Optional[float] = None,
) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    scores: dict[str, float] = {}
    r2_values: dict[str, float] = {}
    raw_scores: dict[str, float] = {}
    for code in ASSETS:
        window = prices[code].iloc[idx - LOOKBACK + 1 : idx + 1]
        score, r2 = weighted_slope_score_and_r2(window)
        if not math.isnan(score):
            raw_scores[code] = score
        if not math.isnan(r2):
            r2_values[code] = r2
        passes_r2 = r2_threshold is None or (not math.isnan(r2) and r2 >= r2_threshold)
        if SCORE_MIN < score < SCORE_MAX and passes_r2:
            scores[code] = score
    return scores, r2_values, raw_scores


def max_drawdown(nav: pd.Series) -> float:
    return float((nav / nav.cummax() - 1.0).min())


# ════════════════════════════════════════════════════════════════
#  V1.1 Strategy Engine — staged entry
# ════════════════════════════════════════════════════════════════

def _target_from_scores(
    scores: dict[str, float],
    prev_holding: str,
    switch_buffer: float,
) -> tuple[str, str, float, float, bool]:
    if not scores:
        return "CASH", "CASH", math.nan, math.nan, False
    best = max(scores, key=scores.get)
    best_score = float(scores[best])
    current_score = float(scores[prev_holding]) if prev_holding in scores else math.nan
    blocked = False
    target = best
    if (
        prev_holding in scores
        and prev_holding != best
        and switch_buffer > 1.0
        and best_score <= current_score * switch_buffer
    ):
        target = prev_holding
        blocked = True
    return target, best, best_score, current_score, blocked


def run_staged_entry(
    prices: pd.DataFrame,
    config: RunConfig,
    case: EntryCase,
    r2_threshold: float,
    switch_buffer: float,
) -> pd.DataFrame:
    prices = prices.loc[:config.end_date].copy()
    holding = "CASH"
    holding_fraction = 0.0
    pending_entry_target = None  # type: Optional[str]
    pending_entry_since = None   # type: Optional[pd.Timestamp]
    pending_entry_days = 0
    nav = 1.0
    trade_count = 0
    staged_initial_count = 0
    staged_fill_count = 0
    buffer_blocked_count = 0
    rows: list[dict] = []

    for idx, date in enumerate(prices.index):
        old_holding = holding
        old_fraction = holding_fraction

        scores: dict[str, float] = {}
        r2_values: dict[str, float] = {}
        raw_scores: dict[str, float] = {}
        if idx >= LOOKBACK - 1:
            scores, r2_values, raw_scores = calc_scores(prices, idx, r2_threshold=r2_threshold)
        ideal, best_candidate, best_score, current_score, buffer_blocked = _target_from_scores(
            scores, old_holding, switch_buffer
        )
        if buffer_blocked:
            buffer_blocked_count += 1

        signal_target = ideal if ideal != old_holding else None
        trade_target = None  # type: Optional[str]
        trade_fraction = old_fraction
        fill_on_down_day = False
        staged_initial = False

        if case.mode == "full_entry":
            if signal_target is not None:
                trade_target = signal_target
                trade_fraction = 0.0 if signal_target == "CASH" else 1.0
                pending_entry_target = None
                pending_entry_since = None
                pending_entry_days = 0
        elif old_holding == "CASH":
            if ideal != "CASH":
                initial = float(np.clip(case.initial_fraction, 0.0, 1.0))
                trade_target = ideal
                trade_fraction = initial
                staged_initial = initial < 1.0 - 1e-12
                if staged_initial:
                    pending_entry_target = ideal
                    pending_entry_since = date
                    pending_entry_days = 0
                    staged_initial_count += 1
                else:
                    pending_entry_target = None
                    pending_entry_since = None
                    pending_entry_days = 0
        else:
            is_partial_pending = (
                pending_entry_target is not None
                and old_holding == pending_entry_target
                and old_fraction < 1.0 - 1e-12
            )
            if is_partial_pending:
                if signal_target is not None:
                    if signal_target != "CASH":
                        initial = float(np.clip(case.initial_fraction, 0.0, 1.0))
                        trade_target = signal_target
                        trade_fraction = initial
                        pending_entry_target = signal_target if initial < 1.0 - 1e-12 else None
                        pending_entry_since = date if pending_entry_target is not None else None
                        pending_entry_days = 0
                        staged_initial = pending_entry_target is not None
                        if staged_initial:
                            staged_initial_count += 1
                    else:
                        trade_target = signal_target
                        trade_fraction = 0.0
                        pending_entry_target = None
                        pending_entry_since = None
                        pending_entry_days = 0
                else:
                    prev_close = prices.iloc[idx - 1][pending_entry_target] if idx > 0 else np.nan
                    curr_close = prices.iloc[idx][pending_entry_target]
                    is_down_day = (
                        pd.notna(prev_close)
                        and pd.notna(curr_close)
                        and float(curr_close) < float(prev_close)
                    )
                    if is_down_day:
                        trade_target = pending_entry_target
                        trade_fraction = 1.0
                        pending_entry_target = None
                        pending_entry_since = None
                        pending_entry_days = 0
                        fill_on_down_day = True
                        staged_fill_count += 1
                    else:
                        pending_entry_days += 1
            elif signal_target is not None:
                if signal_target != "CASH":
                    initial = float(np.clip(case.initial_fraction, 0.0, 1.0))
                    trade_target = signal_target
                    trade_fraction = initial
                    staged_initial = initial < 1.0 - 1e-12
                    if staged_initial:
                        pending_entry_target = signal_target
                        pending_entry_since = date
                        pending_entry_days = 0
                        staged_initial_count += 1
                    else:
                        pending_entry_target = None
                        pending_entry_since = None
                        pending_entry_days = 0
                else:
                    trade_target = signal_target
                    trade_fraction = 0.0
                    pending_entry_target = None
                    pending_entry_since = None
                    pending_entry_days = 0

        # --- daily return ---
        if old_holding == "CASH" or old_fraction <= 1e-12 or idx == 0:
            gross_return = 0.0
            asset_component = 0.0
        else:
            prev_px = prices.iloc[idx - 1].get(old_holding, np.nan)
            cur_px = prices.iloc[idx].get(old_holding, np.nan)
            asset_ret = (
                float(cur_px / prev_px - 1.0)
                if pd.notna(prev_px) and pd.notna(cur_px) and prev_px > 0
                else 0.0
            )
            asset_component = old_fraction * asset_ret
            gross_return = asset_component

        # --- trading cost ---
        turnover = 0.0
        cost = 0.0
        if trade_target is not None:
            if old_holding == trade_target:
                turnover = abs(float(trade_fraction) - old_fraction)
            else:
                turnover = (old_fraction if old_holding != "CASH" else 0.0) + (
                    float(trade_fraction) if trade_target != "CASH" else 0.0
                )
            cost = turnover * config.one_way_cost
            holding = trade_target if float(trade_fraction) > 1e-12 else "CASH"
            holding_fraction = float(trade_fraction) if holding != "CASH" else 0.0
            if turnover > 1e-12:
                trade_count += 1
        else:
            holding_fraction = old_fraction

        nav *= (1.0 + gross_return) * (1.0 - cost)
        net_return = nav / rows[-1]["nav"] - 1.0 if rows else nav - 1.0
        score_row = {f"score_{code}": scores.get(code, math.nan) for code in ASSETS}
        raw_score_row = {f"raw_score_{code}": raw_scores.get(code, math.nan) for code in ASSETS}
        r2_row = {f"r2_{code}": r2_values.get(code, math.nan) for code in ASSETS}
        rows.append({
            "date": date,
            "entry_case": case.label,
            "position_before": old_holding,
            "fraction_before": old_fraction,
            "position": holding,
            "holding_fraction": holding_fraction,
            "pending_entry_target": pending_entry_target,
            "pending_entry_since": pending_entry_since,
            "pending_entry_days": pending_entry_days,
            "trade_target": trade_target,
            "trade_fraction": trade_fraction if trade_target is not None else math.nan,
            "staged_initial": staged_initial,
            "fill_on_down_day": fill_on_down_day,
            "best_candidate": best_candidate,
            "best_candidate_score": best_score,
            "current_score": current_score,
            "buffer_blocked": buffer_blocked,
            "gross_return": gross_return,
            "asset_component": asset_component,
            "turnover": turnover,
            "cost": cost,
            "return": net_return,
            "nav": nav,
            "trade_count": trade_count,
            "stop_count": 0,
            "stop_triggered": False,
            "staged_initial_count": staged_initial_count,
            "staged_fill_count": staged_fill_count,
            **score_row,
            **raw_score_row,
            **r2_row,
            "buffer_blocked_count": buffer_blocked_count,
        })

    return pd.DataFrame(rows).set_index("date")


# ════════════════════════════════════════════════════════════════
#  Target-vol overlay
# ════════════════════════════════════════════════════════════════

def apply_target_vol_overlay(
    curve: pd.DataFrame, target_vol: float, vol_window: int, max_lev: float,
) -> pd.DataFrame:
    result = curve.copy()
    base_ret = result["return"].astype(float).fillna(0.0)
    realized_vol = base_ret.rolling(vol_window, min_periods=vol_window).std(ddof=0) * math.sqrt(TRADING_DAYS)
    scale = (target_vol / realized_vol).replace([np.inf, -np.inf], np.nan)
    scale = scale.shift(1).clip(lower=0.0, upper=max_lev).fillna(1.0)
    result["base_return"] = base_ret
    result["base_nav"] = result["nav"]
    result["realized_vol"] = realized_vol
    result["weight"] = scale
    result["final_exposure"] = result["holding_fraction"].astype(float).fillna(0.0) * scale
    result["return"] = base_ret * scale
    result["gross_return"] = result["gross_return"].astype(float) * scale
    result["cost"] = result["cost"].astype(float) * scale
    result["nav"] = (1.0 + result["return"]).cumprod()
    result["target_vol"] = target_vol
    result["vol_window"] = vol_window
    result["max_lev"] = max_lev
    return result


# ════════════════════════════════════════════════════════════════
#  Overheat overlay (bias-momentum defence)
# ════════════════════════════════════════════════════════════════

def calc_bias_momentum(close_series: pd.Series) -> pd.Series:
    prices_arr = close_series.values.astype(float)
    n = len(prices_arr)
    result = np.full(n, np.nan)
    ma = close_series.rolling(CN_BIAS_N).mean().values
    total_lookback = CN_BIAS_N + CN_MOM_DAY - 1
    x = np.arange(CN_MOM_DAY, dtype=float)
    for i in range(total_lookback, n):
        bias_window = np.empty(CN_MOM_DAY)
        valid = True
        for j in range(CN_MOM_DAY):
            idx_j = i - CN_MOM_DAY + 1 + j
            if np.isnan(ma[idx_j]) or ma[idx_j] < 1e-10 or np.isnan(prices_arr[idx_j]):
                valid = False
                break
            bias_window[j] = prices_arr[idx_j] / ma[idx_j]
        if not valid or bias_window[0] < 1e-10:
            continue
        bias_norm = bias_window / bias_window[0]
        slope_val = np.polyfit(x, bias_norm, 1)[0]
        result[i] = slope_val * 10000
    return pd.Series(result, index=close_series.index)


def build_overheat_features(prices: pd.DataFrame) -> dict[str, pd.DataFrame]:
    features: dict[str, pd.DataFrame] = {}
    for code in ASSETS:
        price = prices[code].astype(float)
        ma = price.rolling(CN_BIAS_N).mean()
        bias = price / ma - 1.0
        bias_mom = calc_bias_momentum(price)
        same_side = (bias > 0) & (bias_mom > 0) & bias.notna() & bias_mom.notna()
        features[code] = pd.DataFrame(
            {"bias": bias, "bias_mom": bias_mom, "same_side": same_side},
            index=prices.index,
        )
    return features


def apply_overheat_overlay(
    curve: pd.DataFrame,
    features: dict[str, pd.DataFrame],
    case: OverheatCase,
    one_way_cost: float,
) -> pd.DataFrame:
    if not 0 < case.exit < case.enter:
        raise ValueError(f"Bad overheat thresholds: {case}")
    if not 0 <= case.derisk_scale <= 1:
        raise ValueError(f"Bad derisk scale: {case}")

    out = curve.copy()
    defense_on = False
    prev_scale = 1.0
    prev_holding = None
    returns: list[float] = []
    scales: list[float] = []
    on_vals: list[bool] = []
    trigger_vals: list[bool] = []
    recover_vals: list[bool] = []
    bias_vals: list[float] = []
    mom_vals: list[float] = []
    same_side_vals: list[bool] = []
    tc_vals: list[float] = []

    for dt, row in out.iterrows():
        holding = str(row["position_before"])
        if prev_holding is not None and holding != prev_holding:
            defense_on = False
            prev_scale = 1.0
        prev_holding = holding
        eligible = holding in ASSETS

        bias = math.nan
        mom = math.nan
        same_side = False
        if eligible and dt in features[holding].index:
            frow = features[holding].loc[dt]
            bias = float(frow["bias"]) if pd.notna(frow["bias"]) else math.nan
            mom = float(frow["bias_mom"]) if pd.notna(frow["bias_mom"]) else math.nan
            same_side = bool(frow["same_side"]) if pd.notna(frow["same_side"]) else False

        current_scale = float(case.derisk_scale) if defense_on and eligible else 1.0
        tc = abs(current_scale - prev_scale) * one_way_cost if eligible else 0.0
        ret_before = float(row["return"])
        realized = (1.0 + ret_before * current_scale) * (1.0 - tc) - 1.0
        returns.append(realized)
        scales.append(current_scale)
        on_vals.append(bool(current_scale < 0.999999 and eligible))
        tc_vals.append(float(tc))

        triggered = False
        recovered = False
        next_state = defense_on
        if eligible and pd.notna(bias) and same_side:
            if next_state:
                if bias <= case.exit:
                    next_state = False
                    recovered = True
            elif bias >= case.enter:
                next_state = True
                triggered = True
        elif next_state:
            next_state = False
            recovered = True

        trigger_vals.append(triggered)
        recover_vals.append(recovered)
        bias_vals.append(bias)
        mom_vals.append(mom)
        same_side_vals.append(same_side)
        defense_on = next_state
        prev_scale = current_scale

    out.insert(0, "scenario", case.label)
    out["overheat_enter"] = case.enter
    out["overheat_exit"] = case.exit
    out["overheat_derisk_scale"] = case.derisk_scale
    out["return_before_overheat"] = out["return"]
    out["overheat_scale"] = pd.Series(scales, index=out.index, dtype=float)
    out["overheat_on"] = pd.Series(on_vals, index=out.index, dtype=bool)
    out["overheat_triggered"] = pd.Series(trigger_vals, index=out.index, dtype=bool)
    out["overheat_recovered"] = pd.Series(recover_vals, index=out.index, dtype=bool)
    out["overheat_bias"] = pd.Series(bias_vals, index=out.index, dtype=float)
    out["overheat_bias_mom"] = pd.Series(mom_vals, index=out.index, dtype=float)
    out["overheat_same_side"] = pd.Series(same_side_vals, index=out.index, dtype=bool)
    out["overheat_tc"] = pd.Series(tc_vals, index=out.index, dtype=float)
    out["return"] = pd.Series(returns, index=out.index, dtype=float)
    out["nav"] = (1.0 + out["return"]).cumprod()
    return out


# ════════════════════════════════════════════════════════════════
#  Curve building
# ════════════════════════════════════════════════════════════════

def _tag_original(curve: pd.DataFrame) -> pd.DataFrame:
    out = curve.copy()
    out.insert(0, "scenario", "v1_0_original_full_entry")
    out.insert(0, "version", "1.0")
    out["overheat_enter"] = np.nan
    out["overheat_exit"] = np.nan
    out["overheat_derisk_scale"] = 1.0
    out["overheat_scale"] = 1.0
    out["overheat_on"] = False
    out["overheat_triggered"] = False
    out["overheat_recovered"] = False
    out["overheat_tc"] = 0.0
    out["final_exposure_after_overheat"] = out["final_exposure"]
    return out


def build_curves(prices: pd.DataFrame, config: RunConfig) -> list[pd.DataFrame]:
    original = apply_target_vol_overlay(
        run_staged_entry(
            prices, config,
            EntryCase("full_entry_baseline", "full_entry", 1.0),
            R2_THRESHOLD, SWITCH_BUFFER,
        ),
        TARGET_VOL, config.vol_window, config.max_lev,
    )
    staged = apply_target_vol_overlay(
        run_staged_entry(
            prices, config,
            EntryCase("all_new_asset_50_wait_down_no_timeout", "all_new_asset_50_wait_down", INITIAL_ENTRY_FRACTION),
            R2_THRESHOLD, SWITCH_BUFFER,
        ),
        TARGET_VOL, config.vol_window, config.max_lev,
    )
    v11 = apply_overheat_overlay(
        staged,
        build_overheat_features(prices),
        OverheatCase(V11_SCENARIO, OVERHEAT_ENTER, OVERHEAT_EXIT, OVERHEAT_DERISK_SCALE),
        config.one_way_cost,
    )
    v11.insert(0, "version", VERSION)
    v11["scenario"] = V11_SCENARIO
    v11["final_exposure_after_overheat"] = v11["final_exposure"] * v11["overheat_scale"]
    return [_tag_original(original), v11]


# ════════════════════════════════════════════════════════════════
#  Live computation helpers
# ════════════════════════════════════════════════════════════════

def _build_config(end_date=None) -> RunConfig:
    end_date = pd.Timestamp.today().normalize() if end_date is None else pd.Timestamp(end_date).normalize()
    return RunConfig(
        source="sina", one_way_cost=ONE_WAY_COST,
        start_date=START_DATE, end_date=end_date,
        output_tag="v1_1_live", target_vols=(),
        vol_window=DEFAULT_VOL_WINDOW, max_lev=DEFAULT_MAX_LEV,
    )


def _normalize_daily(daily: pd.DataFrame) -> pd.DataFrame:
    out = daily.copy()
    if "date" not in out.columns:
        out = out.reset_index().rename(columns={out.index.name or "index": "date"})
    out["date"] = pd.to_datetime(out["date"])
    out = out[out["version"].astype(str) == VERSION].copy()
    out = out[out["scenario"].astype(str) == V11_SCENARIO].copy()
    out = out.sort_values("date").reset_index(drop=True)
    if out.empty:
        raise poe.BotError("未找到 SubD six-ETF v1.1 日度输出。")
    return out


def _build_v11_daily(end_date=None):
    """Download prices, run full backtest, return (daily_df, source_description)."""
    config = _build_config(end_date=end_date)
    prices, sources = load_close(config)
    prices = prices.loc[prices.index >= config.start_date]
    curves = build_curves(prices, config)
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="The behavior of DataFrame concatenation with empty or all-NA entries is deprecated.*",
            category=FutureWarning,
        )
        daily = pd.concat(curves, sort=False).reset_index().rename(columns={"index": "date"})
    source_name = ", ".join(dict.fromkeys(sources["source"].astype(str).tolist())) if not sources.empty else "unknown"
    return _normalize_daily(daily), source_name


# ════════════════════════════════════════════════════════════════
#  Formatting utilities
# ════════════════════════════════════════════════════════════════

def _float(value, default: float = math.nan) -> float:
    try:
        if value is None or value == "":
            return default
        result = float(value)
        return result if math.isfinite(result) else default
    except Exception:
        return default


def _bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _empty_to_none(value):
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _fmt_pct(value: float, digits: int = 2) -> str:
    return "\u2014" if pd.isna(value) else f"{value * 100:.{digits}f}%"


def _fmt_num(value: float, digits: int = 2) -> str:
    return "\u2014" if pd.isna(value) else f"{value:.{digits}f}"


def _asset_name(code: str) -> str:
    code = str(code)
    label = ASSET_NAMES.get(code) or ASSETS.get(code)
    return f"{label}({code})" if label and code != "CASH" else label or code


# ════════════════════════════════════════════════════════════════
#  Signal / performance extraction
# ════════════════════════════════════════════════════════════════

def latest_signal(daily: pd.DataFrame) -> dict[str, object]:
    row = daily.sort_values("date").iloc[-1]
    overheat_scale = _float(row.get("overheat_scale"), default=1.0)
    weight = _float(row.get("weight"), default=1.0)
    final_exposure = _float(row.get("final_exposure_after_overheat"), default=math.nan)
    return {
        "version": str(row["version"]),
        "date": pd.Timestamp(row["date"]).date().isoformat(),
        "position_before": str(row.get("position_before", "")),
        "position": str(row.get("position", "")),
        "trade_target": _empty_to_none(row.get("trade_target")),
        "trade_fraction": _float(row.get("trade_fraction"), default=math.nan),
        "holding_fraction": _float(row.get("holding_fraction"), default=math.nan),
        "best_candidate": str(row.get("best_candidate", "")),
        "best_candidate_score": _float(row.get("best_candidate_score"), default=math.nan),
        "current_score": _float(row.get("current_score"), default=math.nan),
        "nav": _float(row.get("nav"), default=math.nan),
        "daily_return": _float(row.get("return"), default=math.nan),
        "target_vol_scale": weight,
        "overheat_scale": overheat_scale,
        "execution_scale": weight * overheat_scale,
        "final_exposure": final_exposure,
        "overheat_on": _bool(row.get("overheat_on")),
        "overheat_triggered": _bool(row.get("overheat_triggered")),
        "overheat_recovered": _bool(row.get("overheat_recovered")),
    }


def calc_performance(daily: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, object]:
    start = pd.Timestamp(start).normalize()
    end = pd.Timestamp(end).normalize()
    sub = daily[(daily["date"] >= start) & (daily["date"] <= end)].copy()
    if sub.empty:
        raise poe.BotError(f"在 {start.date()} 到 {end.date()} 期间没有 v1.1 数据。")
    nav = sub["nav"].astype(float)
    nav_norm = nav / float(nav.iloc[0])
    ret = sub["return"].astype(float).fillna(0.0)
    days = max((pd.Timestamp(sub["date"].iloc[-1]) - pd.Timestamp(sub["date"].iloc[0])).days, 1)
    std = ret.std(ddof=0)
    drawdown = nav_norm / nav_norm.cummax() - 1.0
    final_exposure = sub["final_exposure_after_overheat"].astype(float).fillna(0.0)
    return {
        "start": pd.Timestamp(sub["date"].iloc[0]).date().isoformat(),
        "end": pd.Timestamp(sub["date"].iloc[-1]).date().isoformat(),
        "rows": int(len(sub)),
        "total": float(nav_norm.iloc[-1] - 1.0),
        "annual": float(nav_norm.iloc[-1] ** (365.25 / days) - 1.0),
        "maxdd": float(drawdown.min()),
        "vol": float(std * math.sqrt(TRADING_DAYS)),
        "sharpe": float(ret.mean() / std * math.sqrt(TRADING_DAYS)) if std > 0 else math.nan,
        "trades": int(sub["trade_count"].astype(float).iloc[-1] - sub["trade_count"].astype(float).iloc[0]),
        "avg_scale": float(sub["weight"].astype(float).mean()),
        "avg_final_exposure": float(final_exposure.mean()),
        "cash_days": int((sub["position"].astype(str) == "CASH").sum()),
        "overheat_days": int(sub["overheat_on"].astype(str).str.lower().eq("true").sum()),
    }


def calc_yearly_performance(daily: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> list[dict[str, object]]:
    start = pd.Timestamp(start).normalize()
    end = pd.Timestamp(end).normalize()
    df = daily.copy()
    df["date"] = pd.to_datetime(df["date"])
    sub = df[(df["date"] >= start) & (df["date"] <= end)].copy()
    if sub.empty:
        return []
    sub = sub.sort_values("date")
    rows: list[dict[str, object]] = []
    for year, part in sub.groupby(sub["date"].dt.year):
        if part.empty:
            continue
        nav = part["nav"].astype(float)
        nav_norm = nav / float(nav.iloc[0])
        ret = part["return"].astype(float).fillna(0.0)
        std = ret.std(ddof=0)
        dd = nav_norm / nav_norm.cummax() - 1.0
        trades = 0
        if "trade_count" in part.columns:
            trades = int(part["trade_count"].astype(float).iloc[-1] - part["trade_count"].astype(float).iloc[0])
        exposure_col = "final_exposure_after_overheat" if "final_exposure_after_overheat" in part.columns else "holding_fraction"
        avg_exposure = float(part[exposure_col].astype(float).fillna(0.0).mean()) if exposure_col in part.columns else math.nan
        rows.append(
            {
                "year": int(year),
                "start": pd.Timestamp(part["date"].iloc[0]).date().isoformat(),
                "end": pd.Timestamp(part["date"].iloc[-1]).date().isoformat(),
                "rows": int(len(part)),
                "return": float(nav_norm.iloc[-1] - 1.0),
                "maxdd": float(dd.min()),
                "vol": float(std * math.sqrt(TRADING_DAYS)),
                "trades": trades,
                "avg_exposure": avg_exposure,
            }
        )
    return rows


def format_yearly_performance_table(rows: list[dict[str, object]]) -> str:
    if not rows:
        return ""
    lines = [
        "### 年度收益",
        "",
        "| 年份 | 实际区间 | 天数 | 收益 | 最大回撤 | 波动率 | 交易数 | 平均敞口 |",
        "|:-:|:-|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['year']} | {row['start']}~{row['end']} | {row['rows']} | "
            f"{_fmt_pct(row['return'])} | {_fmt_pct(row['maxdd'])} | "
            f"{_fmt_pct(row['vol'])} | {row['trades']} | {_fmt_pct(row['avg_exposure'])} |"
        )
    return "\n".join(lines) + "\n"


# ════════════════════════════════════════════════════════════════
#  Chinese date range parsing
# ════════════════════════════════════════════════════════════════

def _parse_cn_num(raw):
    text = str(raw).strip()
    if text in {"半", "0.5"}:
        return 0.5
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        val = float(text)
        return int(val) if val.is_integer() else val
    mapping = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    if text in mapping:
        return mapping[text]
    if "十" in text:
        left, right = text.split("十", 1)
        tens = mapping.get(left, 1) if left else 1
        ones = mapping.get(right, 0) if right else 0
        return tens * 10 + ones
    return None


def parse_date_range(text, now=None):
    now = pd.Timestamp.now().normalize() if now is None else pd.Timestamp(now).normalize()
    day_suffix = r"[日号]?"

    # YYYY-MM-DD ~ YYYY-MM-DD
    patterns = [
        (
            r"(\d{4})[-年/.](\d{1,2})[-月/.](\d{1,2})\s*"
            + day_suffix + r"\s*[到至—\-~]+\s*(\d{4})[-年/.](\d{1,2})[-月/.](\d{1,2})\s*" + day_suffix,
            lambda m: (
                pd.Timestamp(f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"),
                pd.Timestamp(f"{m.group(4)}-{int(m.group(5)):02d}-{int(m.group(6)):02d}"),
            ),
        ),
        (
            r"(\d{4})[-年/.](\d{1,2})[-月/.](\d{1,2})\s*"
            + day_suffix + r"\s*[到至—\-~]+\s*(\d{1,2})[-月/.](\d{1,2})\s*" + day_suffix,
            lambda m: (
                pd.Timestamp(f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"),
                pd.Timestamp(f"{m.group(1)}-{int(m.group(4)):02d}-{int(m.group(5)):02d}"),
            ),
        ),
    ]
    for pattern, build in patterns:
        match = re.search(pattern, text)
        if match:
            return build(match)

    # MM-DD ~ MM-DD
    match = re.search(
        r"(\d{1,2})[-月/.](\d{1,2})\s*" + day_suffix + r"\s*[到至—\-~]+\s*(\d{1,2})[-月/.](\d{1,2})\s*" + day_suffix,
        text,
    )
    if match:
        year = now.year
        start = pd.Timestamp(f"{year}-{int(match.group(1)):02d}-{int(match.group(2)):02d}")
        end = pd.Timestamp(f"{year}-{int(match.group(3)):02d}-{int(match.group(4)):02d}")
        if start > end:
            start = pd.Timestamp(f"{year - 1}-{int(match.group(1)):02d}-{int(match.group(2)):02d}")
            end = pd.Timestamp(f"{year - 1}-{int(match.group(3)):02d}-{int(match.group(4)):02d}")
        return start, end

    # YYYY-MM-DD至今
    match = re.search(r"(\d{4})[-年/.](\d{1,2})[-月/.](\d{1,2})\s*" + day_suffix + r"\s*至今", text)
    if match:
        return pd.Timestamp(f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"), now
    # MM-DD至今
    match = re.search(r"(\d{1,2})[-月/.](\d{1,2})\s*" + day_suffix + r"\s*至今", text)
    if match:
        start = pd.Timestamp(f"{now.year}-{int(match.group(1)):02d}-{int(match.group(2)):02d}")
        if start > now:
            start = pd.Timestamp(f"{now.year - 1}-{int(match.group(1)):02d}-{int(match.group(2)):02d}")
        return start, now
    # YYYY-MM至今
    match = re.search(r"(\d{4})[-年/.]?(\d{1,2})[-月]?\s*至今", text)
    if match:
        return pd.Timestamp(f"{match.group(1)}-{int(match.group(2)):02d}-01"), now
    # YYYY至今
    match = re.search(r"(\d{4})\s*年?\s*至今", text)
    if match:
        return pd.Timestamp(f"{match.group(1)}-01-01"), now

    # YYYY-MM ~ YYYY-MM
    match = re.search(r"(\d{4})[-年/.](\d{1,2})[-月]?\s*[到至—\-~]+\s*(\d{4})[-年/.](\d{1,2})", text)
    if match:
        start = pd.Timestamp(f"{match.group(1)}-{int(match.group(2)):02d}-01")
        end = pd.Timestamp(f"{match.group(3)}-{int(match.group(4)):02d}-01") + pd.offsets.MonthEnd(0)
        return start, end
    # YYYY-MM ~ MM (same year)
    match = re.search(r"(\d{4})[-年/.](\d{1,2})[-月]?\s*[到至—\-~]+\s*(\d{1,2})", text)
    if match:
        year = int(match.group(1))
        start = pd.Timestamp(f"{year}-{int(match.group(2)):02d}-01")
        end = pd.Timestamp(f"{year}-{int(match.group(3)):02d}-01") + pd.offsets.MonthEnd(0)
        return start, end
    # YYYYMM ~ YYYYMM
    match = re.search(r"(\d{4})(\d{2})\s*[-到至~]+\s*(\d{4})(\d{2})", text)
    if match:
        start = pd.Timestamp(f"{match.group(1)}-{match.group(2)}-01")
        end = pd.Timestamp(f"{match.group(3)}-{match.group(4)}-01") + pd.offsets.MonthEnd(0)
        return start, end
    # YYYY ~ YYYY
    match = re.search(r"(\d{4})\s*年?\s*[到至—\-~]+\s*(\d{4})\s*年?", text)
    if match:
        return pd.Timestamp(f"{match.group(1)}-01-01"), pd.Timestamp(f"{match.group(2)}-12-31")

    # 最近/过去/近 N 年/月
    match = re.search(r"(?:最近|过去|近)\s*([一二两三四五六七八九十\d半]+)\s*个?\s*年", text)
    if match:
        number = _parse_cn_num(match.group(1))
        if number is not None:
            return now - pd.DateOffset(months=int(number * 12)), now
    match = re.search(r"(?:最近|过去|近)\s*([一二两三四五六七八九十\d半]+)\s*个?\s*月", text)
    if match:
        number = _parse_cn_num(match.group(1))
        if number is not None:
            return now - pd.DateOffset(months=max(1, int(number))), now

    # 今年 / 去年 / 前年
    if "今年" in text:
        return pd.Timestamp(f"{now.year}-01-01"), now
    if "去年" in text:
        year = now.year - 1
        return pd.Timestamp(f"{year}-01-01"), pd.Timestamp(f"{year}-12-31")
    if "前年" in text:
        year = now.year - 2
        return pd.Timestamp(f"{year}-01-01"), pd.Timestamp(f"{year}-12-31")

    # YYYY-MM (specific month)
    match = re.search(r"(\d{4})[-年/.](\d{1,2})\s*月?份?", text)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        if 1 <= month <= 12:
            start = pd.Timestamp(f"{year}-{month:02d}-01")
            return start, start + pd.offsets.MonthEnd(0)
    # YYYY年
    match = re.search(r"(\d{4})\s*年?\s*全?年?", text)
    if match:
        year = int(match.group(1))
        if 2000 <= year <= 2099:
            return pd.Timestamp(f"{year}-01-01"), pd.Timestamp(f"{year}-12-31")

    return None, None


def parse_all_date_ranges(text, now=None):
    parts = re.split(r"以及|、|；|;\s*", text)
    if len(parts) == 1:
        parts = re.split(r"(?<=[年月日\d])\s*和\s*(?=[近最过今去前\d])", text)
    ranges: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    seen: set[tuple] = set()
    for part in parts:
        start, end = parse_date_range(part.strip(), now=now)
        if start is None or end is None:
            continue
        key = (start.date(), end.date())
        if key not in seen:
            ranges.append((start, end))
            seen.add(key)
    if not ranges:
        start, end = parse_date_range(text, now=now)
        if start is not None and end is not None:
            ranges.append((start, end))
    ranges.sort(key=lambda item: (item[1] - item[0]).days)
    return ranges


# ════════════════════════════════════════════════════════════════
#  Query classification & performance range resolution
# ════════════════════════════════════════════════════════════════

def classify_query(text: str) -> str:
    query = str(text or "").strip()
    compact = re.sub(r"\s+", "", query)
    if "实时信号" in compact or "信号实时" in compact:
        return "live_signal"
    if "实时参数" in compact or "参数实时" in compact:
        return "live_params"
    if re.search(r"净值曲线|收益曲线|走势", query):
        return "performance"
    if re.search(r"表现|收益(?!曲线)|回撤|年化|夏普|回报|绩效", query):
        return "performance"
    if "参数" in query:
        return "params"
    if "信号" in query:
        return "signal"
    return "signal"


def resolve_performance_ranges(
    query: str,
    now=None,
    latest_date=None,
) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    now = pd.Timestamp.now().normalize() if now is None else pd.Timestamp(now).normalize()
    latest = now if latest_date is None else pd.Timestamp(latest_date).normalize()
    parsed = parse_all_date_ranges(query, now=now)
    if parsed:
        return [(f"{s.date()}~{e.date()}", s, e) for s, e in parsed]
    return [
        ("from_2020", EVAL_START, latest),
        ("5Y", latest - pd.DateOffset(years=5), latest),
        ("3Y", latest - pd.DateOffset(years=3), latest),
        ("1Y", latest - pd.DateOffset(years=1), latest),
    ]


# ════════════════════════════════════════════════════════════════
#  Bot class
# ════════════════════════════════════════════════════════════════

def _fmt_bool_status(value: bool, on_text: str, off_text: str) -> str:
    return on_text if bool(value) else off_text


def _signal_action_text(sig: dict[str, object]) -> str:
    previous = _asset_name(str(sig.get("position_before", "")))
    target = _asset_name(str(sig.get("position", "")))
    trade_target = sig.get("trade_target")
    if trade_target:
        if str(sig.get("position_before")) == str(sig.get("position")):
            return f"仓位调整: 维持 {target}，目标基础仓位 {_fmt_pct(sig.get('holding_fraction'))}"
        return f"换仓信号: {previous} -> {target}，新资产首笔 {_fmt_pct(sig.get('holding_fraction'))}"
    return f"无换仓: 继续持有 {target}"


def _signal_rank_rows(daily: pd.DataFrame, limit: int = 6) -> list[dict[str, object]]:
    row = daily.sort_values("date").iloc[-1]
    rows: list[dict[str, object]] = []
    for code in ASSETS:
        raw_score = _float(row.get(f"raw_score_{code}"), default=math.nan)
        eligible_score = _float(row.get(f"score_{code}"), default=math.nan)
        score = raw_score if not pd.isna(raw_score) else eligible_score
        r2 = _float(row.get(f"r2_{code}"), default=math.nan)
        rows.append(
            {
                "code": code,
                "name": _asset_name(code),
                "score": score,
                "eligible_score": eligible_score,
                "r2": r2,
            }
        )
    rows.sort(
        key=lambda item: (
            not pd.isna(item["score"]),
            item["score"] if not pd.isna(item["score"]) else float("-inf"),
        ),
        reverse=True,
    )
    return rows[:limit]


def _last_signal_date(daily: pd.DataFrame) -> str:
    ordered = daily.sort_values("date")
    if "trade_target" not in ordered.columns:
        return "暂无换仓记录"
    changed = ordered[ordered["trade_target"].apply(lambda value: _empty_to_none(value) is not None)]
    if changed.empty:
        return "暂无换仓记录"
    return pd.Timestamp(changed.iloc[-1]["date"]).date().isoformat()


def format_signal_report(daily: pd.DataFrame, source_note: str) -> str:
    ordered = daily.sort_values("date").reset_index(drop=True)
    row = ordered.iloc[-1]
    sig = latest_signal(ordered)
    trade_label = _asset_name(str(sig["trade_target"])) if sig["trade_target"] else "不调仓"
    prev_name = _asset_name(str(sig["position_before"]))
    next_name = _asset_name(str(sig["position"]))
    final_exposure = _float(sig["final_exposure"], default=math.nan)
    holding_fraction = _float(sig["holding_fraction"], default=math.nan)
    target_vol_scale = _float(sig["target_vol_scale"], default=math.nan)
    overheat_scale = _float(sig["overheat_scale"], default=1.0)
    execution_scale = _float(sig["execution_scale"], default=math.nan)
    realized_vol = _float(row.get("realized_vol"), default=math.nan)
    base_nav = _float(row.get("base_nav"), default=math.nan)
    overheat_bias = _float(row.get("overheat_bias"), default=math.nan)
    overheat_mom = _float(row.get("overheat_bias_mom"), default=math.nan)
    pending_target = _empty_to_none(row.get("pending_entry_target"))
    pending_days = int(_float(row.get("pending_entry_days"), default=0.0))
    fill_on_down = _bool(row.get("fill_on_down_day"))
    staged_initial = _bool(row.get("staged_initial"))
    last_signal = _last_signal_date(ordered)

    lines: list[str] = []
    lines.append("## SubD六ETF V1.1 操作信号")
    lines.append("")
    lines.append(f"数据源: **{source_note}** | 信号日: **{sig['date']}** | 版本: **V{sig['version']}**")
    lines.append("")
    lines.append("### 结论")
    lines.append("")
    lines.append(f"**{_signal_action_text(sig)}**")
    lines.append("")
    lines.append(f"- 当前已生效持仓: **{prev_name}**")
    lines.append(f"- 今日目标持仓: **{next_name}**")
    lines.append(f"- 本日调仓动作: **{trade_label}**")
    lines.append(f"- 最终执行敞口: **{_fmt_pct(final_exposure)}**")
    lines.append(f"- 上次出现调仓信号: **{last_signal}**")
    lines.append("")
    lines.append("### 仓位拆解")
    lines.append("")
    lines.append("| 层级 | 当前值 | 说明 |")
    lines.append("|:-|--:|:-|")
    lines.append(f"| 基础仓位 | **{_fmt_pct(holding_fraction)}** | V1.1新资产先建50%，等待下跌日补足 |")
    lines.append(f"| Target-vol scale | **{_fmt_num(target_vol_scale, 3)}x** | 目标波动率{TARGET_VOL:.0%}，{DEFAULT_VOL_WINDOW}日收益率估计 |")
    lines.append(f"| 过热防守scale | **{_fmt_num(overheat_scale, 3)}x** | 触发{OVERHEAT_ENTER:.0%} / 恢复{OVERHEAT_EXIT:.0%} |")
    lines.append(f"| 执行scale | **{_fmt_num(execution_scale, 3)}x** | Target-vol × 过热防守 |")
    lines.append(f"| 最终敞口 | **{_fmt_pct(final_exposure)}** | 基础仓位 × 执行scale |")
    if not pd.isna(realized_vol):
        lines.append(f"| 已实现波动率 | **{_fmt_pct(realized_vol)}** | 用于下一期target-vol计算 |")
    lines.append("")
    lines.append("### 动量排名")
    lines.append("")
    lines.append("| # | ETF | Score | R² | 状态 |")
    lines.append("|:-:|:-|--:|--:|:-|")
    for rank, item in enumerate(_signal_rank_rows(ordered), 1):
        code = str(item["code"])
        score = _float(item["score"], default=math.nan)
        r2 = _float(item["r2"], default=math.nan)
        marker = " <- 最强候选" if code == str(sig["best_candidate"]) else ""
        hold_marker = " / 当前持仓" if code == str(sig["position_before"]) else ""
        status = "通过" if not pd.isna(score) else "未入选"
        if pd.isna(score) or pd.isna(r2):
            status = "数据不足"
        elif r2 < R2_THRESHOLD:
            status = f"R²未过{R2_THRESHOLD:.2f}"
        elif score <= SCORE_MIN:
            status = f"Score≤{SCORE_MIN:.0f}"
        elif score >= SCORE_MAX:
            status = f"Score≥{SCORE_MAX:.0f}"
        lines.append(
            f"| {rank} | {_asset_name(code)}{marker}{hold_marker} | "
            f"{_fmt_num(score, 4)} | {_fmt_num(r2, 3)} | {status} |"
        )
    lines.append("")
    lines.append("### 规则状态")
    lines.append("")
    if pending_target:
        lines.append(f"- 分阶段建仓: **等待补仓**，待补目标 **{_asset_name(pending_target)}**，已等待 **{pending_days}** 个交易日。")
    elif fill_on_down:
        lines.append("- 分阶段建仓: **本日下跌补足仓位**。")
    elif staged_initial:
        lines.append("- 分阶段建仓: **本日首笔50%建仓**，后续等待下跌日补足。")
    else:
        lines.append("- 分阶段建仓: 当前无待补仓。")
    overheat_status = _fmt_bool_status(sig["overheat_on"], "**防守中**", "**未触发**")
    if sig["overheat_triggered"]:
        overheat_status = "**本日触发**"
    elif sig["overheat_recovered"]:
        overheat_status = "**本日恢复**"
    bias_text = ""
    if not pd.isna(overheat_bias):
        bias_text = f" | 当前乖离 {_fmt_pct(overheat_bias)}"
    if not pd.isna(overheat_mom):
        bias_text += f" | 乖离动量 {_fmt_num(overheat_mom, 2)}"
    lines.append(f"- 过热防守: {overheat_status}{bias_text}。")
    lines.append(f"- 成本口径: 单边交易成本 **{ONE_WAY_COST:.1%}**，日线收盘价口径。")
    lines.append("")
    lines.append("### 净值快照")
    lines.append("")
    lines.append("| 项目 | 值 |")
    lines.append("|:-|--:|")
    lines.append(f"| 当日收益 | **{_fmt_pct(sig['daily_return'], 3)}** |")
    lines.append(f"| V1.1净值 | **{_fmt_num(sig['nav'], 4)}** |")
    if not pd.isna(base_nav):
        lines.append(f"| 过热前基础净值 | **{_fmt_num(base_nav, 4)}** |")
    lines.append("")
    lines.append("> 执行提醒: 这是日线收盘确认信号；实盘执行时按你的交易流程在下一可交易时点处理。")
    return "\n".join(lines) + "\n"


def _momentum_status(score: float, r2: float) -> str:
    if pd.isna(score) or pd.isna(r2):
        return "数据不足"
    if r2 < R2_THRESHOLD:
        return f"R²未过{R2_THRESHOLD:.2f}"
    if score <= SCORE_MIN:
        return f"Score≤{SCORE_MIN:.0f}"
    if score >= SCORE_MAX:
        return f"Score≥{SCORE_MAX:.0f}"
    return "入选"


def _momentum_role(code: str, sig: dict[str, object]) -> str:
    roles: list[str] = []
    if code == str(sig.get("best_candidate")):
        roles.append("最强候选")
    if code == str(sig.get("position_before")):
        roles.append("当前持仓")
    if code == str(sig.get("position")):
        roles.append("目标持仓")
    if sig.get("trade_target") and code == str(sig.get("trade_target")):
        roles.append("本日调仓")
    return " / ".join(roles) if roles else "-"


def format_live_params_snapshot(daily: pd.DataFrame, source_note: str) -> str:
    ordered = daily.sort_values("date").reset_index(drop=True)
    row = ordered.iloc[-1]
    sig = latest_signal(ordered)
    realized_vol = _float(row.get("realized_vol"), default=math.nan)
    overheat_bias = _float(row.get("overheat_bias"), default=math.nan)
    overheat_mom = _float(row.get("overheat_bias_mom"), default=math.nan)
    final_exposure = _float(sig["final_exposure"], default=math.nan)
    target_vol_scale = _float(sig["target_vol_scale"], default=math.nan)
    overheat_scale = _float(sig["overheat_scale"], default=1.0)
    execution_scale = _float(sig["execution_scale"], default=math.nan)

    lines: list[str] = []
    lines.append("")
    lines.append("### 当前六ETF动量快照")
    lines.append("")
    lines.append(f"数据源: **{source_note}** | 最新日线: **{sig['date']}**")
    lines.append("")
    lines.append(
        f"当前信号: **{_asset_name(str(sig['position_before']))} -> {_asset_name(str(sig['position']))}** | "
        f"最强候选: **{_asset_name(str(sig['best_candidate']))}** | "
        f"最终敞口: **{_fmt_pct(final_exposure)}**"
    )
    lines.append("")
    lines.append("| # | ETF | Score | R² | 入选状态 | 角色 |")
    lines.append("|:-:|:-|--:|--:|:-|:-|")
    for rank, item in enumerate(_signal_rank_rows(ordered), 1):
        code = str(item["code"])
        score = _float(item["score"], default=math.nan)
        r2 = _float(item["r2"], default=math.nan)
        lines.append(
            f"| {rank} | {_asset_name(code)} | {_fmt_num(score, 4)} | {_fmt_num(r2, 3)} | "
            f"{_momentum_status(score, r2)} | {_momentum_role(code, sig)} |"
        )
    lines.append("")
    lines.append("### 当前执行参数快照")
    lines.append("")
    lines.append("| 参数 | 当前值 | 说明 |")
    lines.append("|:-|--:|:-|")
    lines.append(f"| Target-vol scale | **{_fmt_num(target_vol_scale, 3)}x** | 目标波动率{TARGET_VOL:.0%}，波动窗口{DEFAULT_VOL_WINDOW}日 |")
    lines.append(f"| 过热防守scale | **{_fmt_num(overheat_scale, 3)}x** | 触发{OVERHEAT_ENTER:.0%} / 恢复{OVERHEAT_EXIT:.0%} |")
    lines.append(f"| 执行scale | **{_fmt_num(execution_scale, 3)}x** | Target-vol × 过热防守 |")
    lines.append(f"| 最终敞口 | **{_fmt_pct(final_exposure)}** | 基础仓位 × 执行scale |")
    if not pd.isna(realized_vol):
        lines.append(f"| 已实现波动率 | **{_fmt_pct(realized_vol)}** | 当前target-vol计算输入 |")
    if not pd.isna(overheat_bias):
        lines.append(f"| 当前持仓乖离 | **{_fmt_pct(overheat_bias)}** | 过热防守观察值 |")
    if not pd.isna(overheat_mom):
        lines.append(f"| 乖离动量 | **{_fmt_num(overheat_mom, 2)}** | 同向过热判定输入 |")
    lines.append("")
    lines.append("说明: Score 为25日加权对数斜率年化动量；只有 `0 < Score < 5` 且 R² 达标的 ETF 才进入候选池。")
    return "\n".join(lines) + "\n"


def _nav_window(daily: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    start = pd.Timestamp(start).normalize()
    end = pd.Timestamp(end).normalize()
    daily = daily.copy()
    daily["date"] = pd.to_datetime(daily["date"])
    sub = daily[(daily["date"] >= start) & (daily["date"] <= end)].copy()
    if sub.empty:
        raise poe.BotError(f"在 {start.date()} 到 {end.date()} 期间没有净值数据。")
    sub = sub.sort_values("date")
    nav = sub["nav"].astype(float)
    sub["nav_norm"] = nav / float(nav.iloc[0])
    sub["drawdown"] = sub["nav_norm"] / sub["nav_norm"].cummax() - 1.0
    return sub


def _sparkline(values: list[float], width: int = 48) -> str:
    clean = [float(v) for v in values if pd.notna(v)]
    if not clean:
        return ""
    if len(clean) > width:
        idx = np.linspace(0, len(clean) - 1, width).round().astype(int)
        clean = [clean[i] for i in idx]
    bars = "▁▂▃▄▅▆▇█"
    lo, hi = min(clean), max(clean)
    if abs(hi - lo) < 1e-12:
        return bars[0] * len(clean)
    return "".join(bars[int(round((v - lo) / (hi - lo) * (len(bars) - 1)))] for v in clean)


def format_nav_curve_text(
    daily: pd.DataFrame,
    label: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> str:
    sub = _nav_window(daily, start, end)
    nav = sub["nav_norm"].astype(float)
    dd = sub["drawdown"].astype(float)
    period_start = pd.Timestamp(sub["date"].iloc[0]).date().isoformat()
    period_end = pd.Timestamp(sub["date"].iloc[-1]).date().isoformat()
    total = float(nav.iloc[-1] - 1.0)
    maxdd = float(dd.min())
    lines = [
        "### 净值曲线",
        "",
        f"窗口: **{label}** | 实际区间: **{period_start}~{period_end}** | 样本: **{len(sub)}** 个交易日",
        "",
        "```text",
        f"NAV {nav.iloc[0]:.2f} {_sparkline(nav.tolist())} {nav.iloc[-1]:.2f}",
        f"DD  0.00 {_sparkline((1.0 + dd).tolist())} {maxdd:.2%}",
        "```",
        "",
        f"- 期末净值: **{nav.iloc[-1]:.4f}**",
        f"- 区间收益: **{_fmt_pct(total)}**",
        f"- 最大回撤: **{_fmt_pct(maxdd)}**",
    ]
    return "\n".join(lines) + "\n"


def render_nav_curve_png(
    daily: pd.DataFrame,
    label: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> bytes:
    import io
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    sub = _nav_window(daily, start, end)
    dates = pd.to_datetime(sub["date"])
    nav = sub["nav_norm"].astype(float)
    dd = sub["drawdown"].astype(float)
    period_start = pd.Timestamp(sub["date"].iloc[0]).date().isoformat()
    period_end = pd.Timestamp(sub["date"].iloc[-1]).date().isoformat()

    fig, (ax_nav, ax_dd) = plt.subplots(
        2,
        1,
        figsize=(11, 6.5),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )
    ax_nav.plot(dates, nav.values, color="#2563EB", linewidth=2.0, label=f"SubD V1.1 NAV ({nav.iloc[-1]:.2f})")
    ax_nav.axhline(1.0, color="#9CA3AF", linestyle="--", linewidth=0.8)
    ax_nav.set_title(f"SubD Six ETF V1.1 NAV Curve | {label} | {period_start} to {period_end}", fontsize=13, fontweight="bold")
    ax_nav.set_ylabel("NAV")
    ax_nav.grid(True, alpha=0.25)
    ax_nav.legend(loc="best")

    ax_dd.fill_between(dates, dd.values * 100.0, 0, color="#DC2626", alpha=0.25)
    ax_dd.plot(dates, dd.values * 100.0, color="#DC2626", linewidth=1.0)
    ax_dd.set_ylabel("DD %")
    ax_dd.grid(True, alpha=0.25)
    ax_dd.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _write_nav_curve(msg, daily: pd.DataFrame, label: str, start: pd.Timestamp, end: pd.Timestamp):
    try:
        chart_bytes = render_nav_curve_png(daily, label, start, end)
        msg.attach_file(
            name=f"subd_v11_nav_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
            contents=chart_bytes,
            content_type="image/png",
            is_inline=True,
        )
    except Exception as exc:
        msg.write(f"> 净值曲线图片生成失败: {str(exc)[:120]}\n")


class SubDSixEtfV11Bot:
    def run(self):
        query = poe.query.text.strip()
        kind = classify_query(query)
        try:
            if kind in ("signal", "live_signal"):
                self._handle_signal()
            elif kind == "live_params":
                self._handle_params(live=True)
            elif kind == "params":
                self._handle_params(live=False)
            elif kind == "performance":
                self._handle_performance(query)
            else:
                self._handle_signal()
        except poe.BotError:
            raise
        except Exception as exc:
            raise poe.BotError(f"查询失败: {str(exc)[:240]}")

    # ---- signal --------------------------------------------------------

    def _handle_signal(self):
        with poe.start_message() as msg:
            msg.write("正在加载数据并计算回测...\n")
            daily, source_note = _build_v11_daily()
            msg.overwrite("")
            msg.write(format_signal_report(daily, source_note))

    # ---- params --------------------------------------------------------

    def _handle_params(self, live: bool = False):
        with poe.start_message() as msg:
            daily = None
            source_note = ""
            if live:
                msg.write("正在加载数据...\n")
                try:
                    daily, source_note = _build_v11_daily()
                except Exception as exc:
                    source_note = f"加载失败: {str(exc)[:120]}"
                msg.overwrite("")

            title = "实时参数" if live else "参数"
            msg.write(f"## SubD六ETF V1.1 {title}\n\n")
            if source_note:
                msg.write(f"数据: {source_note}\n\n")
            msg.write("| 参数 | 当前值 | 说明 |\n|:-|:-|:-|\n")
            msg.write(f"| 版本 | **{VERSION}** | {V11_SCENARIO} |\n")
            msg.write(f"| 起始日期 | **{START_DATE.date()}** | 回测起点 |\n")
            msg.write(f"| 评估起点 | **{EVAL_START.date()}** | 正式统计窗口起点 |\n")
            msg.write(f"| 加权斜率窗口 | **{LOOKBACK}日** | 对数价格加权线性拟合 |\n")
            msg.write(f"| Score入选范围 | **{SCORE_MIN:.0f} < Score < {SCORE_MAX:.0f}** | 超过上限或低于下限只显示，不进入候选池 |\n")
            msg.write(f"| R\u00b2门槛 | **{R2_THRESHOLD:.2f}** | score入选过滤 |\n")
            msg.write(f"| 目标波动率 | **{TARGET_VOL:.0%}** | target-vol overlay |\n")
            msg.write(f"| 波动率窗口 | **{DEFAULT_VOL_WINDOW}日** | 用策略收益率估计 |\n")
            msg.write(f"| 最大杠杆 | **{DEFAULT_MAX_LEV:.1f}x** | scale上限 |\n")
            msg.write(f"| 切换buffer | **{SWITCH_BUFFER:.2f}x** | 当前持仓保护 |\n")
            msg.write(f"| 新资产首笔 | **{INITIAL_ENTRY_FRACTION:.0%}** | 从现金或换新资产时先买入 |\n")
            msg.write("| 补仓规则 | **等下跌日补足** | 无固定超时 |\n")
            msg.write(f"| 过热触发/恢复 | **{OVERHEAT_ENTER:.0%} / {OVERHEAT_EXIT:.0%}** | price/MA{CN_BIAS_N}-1 且乖离动量同向 |\n")
            msg.write(f"| 过热后仓位 | **{OVERHEAT_DERISK_SCALE:.0%}** | 触发后切现金敞口 |\n")
            msg.write(f"| 单边成本 | **{ONE_WAY_COST:.1%}** | 调仓成本 |\n")
            msg.write(f"| 资产池 | **{len(ASSETS)}只ETF** | {', '.join(_asset_name(c) for c in ASSETS)} |\n")
            msg.write("| 数据源 | **AkShare/Sina -> CNFin -> Tencent -> Eastmoney** | 均使用raw/unadjusted日收盘价；CNFin/Tencent按8年分段拉取 |\n")
            if daily is not None:
                msg.write(format_live_params_snapshot(daily, source_note))

    # ---- performance ---------------------------------------------------

    def _handle_performance(self, query: str):
        with poe.start_message() as msg:
            msg.write("正在加载数据并计算回测...\n")
            daily, source_note = _build_v11_daily()
            latest = pd.Timestamp(daily["date"].iloc[-1])
            ranges = resolve_performance_ranges(query, latest_date=latest)
            msg.overwrite("")
            msg.write("## SubD六ETF V1.1 表现\n\n")
            msg.write(f"数据: {source_note}\n")
            msg.write(f"最新日度数据: **{latest.date().isoformat()}**\n\n")
            msg.write("| 窗口 | 实际区间 | 天数 | 总收益 | 年化 | 最大回撤 | 波动率 | Sharpe | 交易数 | 平均敞口 |\n")
            msg.write("|:-|:-|---:|---:|---:|---:|---:|---:|---:|---:|\n")
            first_chart_range = None
            for label, start, end in ranges:
                try:
                    m = calc_performance(daily, start, end)
                    if first_chart_range is None:
                        first_chart_range = (label, start, end)
                    msg.write(
                        f"| {label} | {m['start']}~{m['end']} | {m['rows']} | "
                        f"{_fmt_pct(m['total'])} | {_fmt_pct(m['annual'])} | "
                        f"{_fmt_pct(m['maxdd'])} | {_fmt_pct(m['vol'])} | "
                        f"{_fmt_num(m['sharpe'], 2)} | {m['trades']} | "
                        f"{_fmt_pct(m['avg_final_exposure'])} |\n"
                    )
                except poe.BotError:
                    msg.write(f"| {label} | \u2014 | \u2014 | \u2014 | \u2014 | \u2014 | \u2014 | \u2014 | \u2014 | \u2014 |\n")
            if first_chart_range is not None:
                label, start, end = first_chart_range
                msg.write("\n")
                yearly = calc_yearly_performance(daily, start, end)
                yearly_table = format_yearly_performance_table(yearly)
                if yearly_table:
                    msg.write(yearly_table)
                    msg.write("\n")
                _write_nav_curve(msg, daily, label, start, end)


# ════════════════════════════════════════════════════════════════
#  Settings & entry point
# ════════════════════════════════════════════════════════════════

poe.update_settings(SettingsResponse(
    allow_attachments=True,
    introduction_message=(
        "**SubD六ETF V1.1 信号查询**\n\n"
        "- 发送 **\"信号\"** -> 最新信号（实时计算）\n"
        "- 发送 **\"参数\"** -> V1.1参数总览\n"
        "- 发送 **\"实时参数\"** -> 参数 + 实时数据快照\n"
        '- 发送 **"表现"** / **"表现 过去两年"** / **"今年收益"** -> 绩效表\n'
        '- 发送 **"净值曲线 过去两年"** / **"收益曲线 今年"** -> 绩效表 + 净值曲线\n'
    ),
))

if __name__ == "__main__":
    SubDSixEtfV11Bot().run()
