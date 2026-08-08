# poe: name=SubD-Mixed-Pool-V13
# poe: privacy_shield=half
import inspect
import math
import re
import sys
import time
import warnings
from contextvars import ContextVar
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Iterable, Literal, Optional

import numpy as np
import pandas as pd
import requests

try:
    from fastapi_poe.types import SettingsResponse
except Exception:
    @dataclass
    class SettingsResponse:
        allow_attachments: bool = True
        introduction_message: str = ""

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
        prefix = "\r\x1b[F\x1b[2K" if value == "" else "\r\x1b[2K"
        sys.stdout.buffer.write((prefix + str(value)).encode("utf-8", errors="replace"))
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
    "QQQ": "NASDAQ100_QQQ_PROXY",
    "GLD": "GOLD_GLD_PROXY",
    "CN_CYB_399006": "CHINEXT_INDEX_PROXY",
    "KMLM": "MANAGED_FUTURES_KMLM_PROXY",
    "159985.SZ": "SOYMEAL_ETF",
}
CORE_ASSETS = ("QQQ", "GLD")
DYNAMIC_YAHOO_ASSETS = {
    "KMLM": pd.Timestamp("2020-12-02"),
}
DYNAMIC_CN_ETF_ASSETS = {"159985.SZ": pd.Timestamp("2019-12-05")}
DYNAMIC_ASSETS = {
    "CN_CYB_399006": pd.Timestamp("2010-06-01"),
    **DYNAMIC_YAHOO_ASSETS,
    **DYNAMIC_CN_ETF_ASSETS,
}
YAHOO_LIVE_ASSETS = {
    "QQQ": "QQQ",
    "GLD": "GLD",
    "KMLM": "KMLM",
}
EASTMONEY_LIVE_PROXY_SECIDS = {
    "CN_CYB_399006": "0.399006",
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

# V1.3 uses proxy symbols directly; override the copied display names.
ASSET_NAMES = {
    "QQQ": "Nasdaq100(QQQ)",
    "GLD": "Gold(GLD)",
    "CN_CYB_399006": "ChiNext(399006)",
    "KMLM": "Managed Futures(KMLM)",
    "159985.SZ": "Soymeal ETF(159985.SZ)",
    "CASH": "Cash",
}

# --- V1.3 selected mixed proxy parameter set. ---
LOOKBACK = 28
TRADING_DAYS = 252
SCORE_MIN = 0.0
SCORE_MAX = 5.0
DEFAULT_VOL_WINDOW = 80
DEFAULT_MAX_LEV = 1.0
VERSION = "1.3"
START_DATE = pd.Timestamp("2007-01-01")
EVAL_START = pd.Timestamp("2017-01-01")
R2_THRESHOLD = None
TARGET_VOL = None
TARGET_VOL_SCALE_REBALANCE_THRESHOLD = 0.075
V10_BASELINE_SWITCH_BUFFER = 1.00
SWITCH_BUFFER = 1.15
INITIAL_ENTRY_FRACTION = 0.25
NAV_DEFENSE_ENTER = 0.20
NAV_DEFENSE_EXIT = 0.05
NAV_DEFENSE_SCALE = 0.50
OVERHEAT_ENTER = 0.15
OVERHEAT_EXIT = 0.13
OVERHEAT_DERISK_SCALE = 0.0
OVERHEAT_RECOVERY_MODE = "same_side_or_exit"
ONE_WAY_COST = 0.001
CN_BIAS_N = 60
CN_MOM_DAY = 20
CASH_ANNUAL_YIELD = 0.03
CASH_DAILY_RETURN = (1.0 + CASH_ANNUAL_YIELD) ** (1.0 / TRADING_DAYS) - 1.0
V11_SCENARIO = "v1_3_kmlm_soy_cash3_nav_overheat"
CN_TZ = timezone(timedelta(hours=8))
CONFIRMED_CLOSE_CUTOFF = dt_time(15, 30)
OFFICIAL_CLOSE_TIME = dt_time(15, 0)
LIVE_EXECUTION_START = dt_time(14, 50)
LIVE_EXECUTION_END = dt_time(15, 0)
LIVE_QUOTE_MAX_AGE = pd.Timedelta(minutes=2)
LIVE_QUOTE_MAX_SKEW = pd.Timedelta(seconds=30)
LIVE_QUOTE_FUTURE_TOLERANCE = pd.Timedelta(seconds=10)
LIVE_PRICE_HISTORY_TODAY_MAX_DIFF = 0.03
LIVE_PRICE_LIMIT_TOLERANCE = 1e-9
ETF_PRICE_TICK = Decimal("0.001")
LIVE_PRICE_LIMIT_DESCRIPTION = (
    "temporary proxy price band based on price-matrix reference previous close, "
    "ETF limit ratio, and 0.001 CNY tick; not official exchange reference price"
)
LIVE_PRICE_LIMIT_RATIO_BY_CODE = {code: 0.10 for code in ASSETS if str(code).endswith((".SZ", ".SH"))}
LIVE_PRICE_LIMIT_RATIO_BY_CODE["159915.SZ"] = 0.20
POST_CLOSE_FIXED_PRICE_EFFECTIVE_DATE = pd.Timestamp("2026-07-06")
POST_CLOSE_FIXED_PRICE_EXECUTION_ENABLED = False
DAILY_CACHE_TTL = timedelta(minutes=5)
TRADING_CALENDAR_CACHE_PATH = Path(
    f"outputs/cn_trading_days_cache_{START_DATE.strftime('%Y%m%d')}.csv"
)
ADJUSTMENT_QFQ = "qfq/front-adjusted"
ADJUSTMENT_TOTAL_RETURN = "total-return/adjusted-close"
ADJUSTMENT_CROSS_VALIDATED_RAW = "raw/unadjusted cross-validated"
QFQ_ADJUSTMENT_ALLOWLIST = {ADJUSTMENT_QFQ}
SOURCE_DETAIL_AKSHARE_QFQ = "adjust=qfq"
SOURCE_DETAIL_EASTMONEY_FQT1 = "fqt=1"
SOURCE_DETAIL_TENCENT_QFQ = "qfqday"
SOURCE_SINA_CNFIN_CROSS_VALIDATED = "Sina direct + CNFin quote kline"
SOURCE_DETAIL_SINA_CNFIN_CROSS_VALIDATED = (
    "159985.SZ exact-date intersection; listing coverage from 2019-12-05; "
    "min_rows=500; min_shorter_overlap=99%; max_abs_close_diff=0.001"
)
SOURCE_DETAIL_TENCENT_VERIFIED_DAY_QFQ = (
    "qfq request; day verified vs Eastmoney fqt=1 "
    "(513030.SH:2895, 513520.SH:1729, 159985.SZ:1618 rows; "
    "through 2026-08-07; max close diff 0.001)"
)
TENCENT_VERIFIED_DAY_QFQ_CODES = {"513030.SH", "513520.SH", "159985.SZ"}
TENCENT_FQKLINE_PAGE_SIZE = 640
CROSS_VALIDATED_RAW_CODES = {"159985.SZ": pd.Timestamp("2019-12-05")}
SINA_DAILY_KLINE_MAX_ROWS = 1970
SINA_DAILY_KLINE_WARN_ROWS = 1900
CROSS_VALIDATED_RAW_MIN_ROWS = 500
CROSS_VALIDATED_RAW_MIN_SHORTER_OVERLAP = 0.99
CROSS_VALIDATED_RAW_MAX_ABS_CLOSE_DIFF = 0.001
CNFIN_KLINE_PAGE_SIZE = 2001
MAX_ADJUSTED_DAILY_ABS_RETURN = 0.35


class DeterministicProviderSchemaError(RuntimeError):
    pass
APPROVED_QFQ_HISTORICAL_SOURCES = {
    ("akshare.fund_etf_hist_em daily close", SOURCE_DETAIL_AKSHARE_QFQ),
    ("Eastmoney push2his kline", SOURCE_DETAIL_EASTMONEY_FQT1),
    ("Tencent fqkline", SOURCE_DETAIL_TENCENT_QFQ),
    ("Tencent fqkline", SOURCE_DETAIL_TENCENT_VERIFIED_DAY_QFQ),
}


# ════════════════════════════════════════════════════════════════
#  Data Classes
# ════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RunConfig:
    source: Literal["akshare_em_qfq", "proxy_mixed_v1_3"]
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

def _eastmoney_market_id(code: str) -> str:
    ticker, suffix = code.split(".")
    return f"{'0' if suffix == 'SZ' else '1'}.{ticker}"


def _is_cn_exchange_symbol(code: str | None) -> bool:
    text = str(code or "").upper().strip()
    return text.endswith(".SZ") or text.endswith(".SH")


def _yahoo_live_ticker(code: str) -> str | None:
    return YAHOO_LIVE_ASSETS.get(str(code).strip())


def _eastmoney_live_secid(code: str) -> str | None:
    text = str(code).strip()
    if _is_cn_exchange_symbol(text):
        return _eastmoney_market_id(text)
    return EASTMONEY_LIVE_PROXY_SECIDS.get(text)


def _eastmoney_live_ticker(code: str) -> str | None:
    secid = _eastmoney_live_secid(code)
    if not secid:
        return None
    return secid.split(".", 1)[1]


def _live_quote_supported_codes(codes: Iterable[str]) -> list[str]:
    return [
        str(code)
        for code in codes
        if _eastmoney_live_secid(str(code)) is not None or _yahoo_live_ticker(str(code)) is not None
    ]


def _live_quote_unsupported_codes(codes: Iterable[str]) -> list[str]:
    return [
        str(code)
        for code in codes
        if _eastmoney_live_secid(str(code)) is None and _yahoo_live_ticker(str(code)) is None
    ]


def _eastmoney_symbol(code: str) -> str:
    return code.split(".", 1)[0]


def _tencent_fq_symbol(code: str) -> str:
    ticker, suffix = code.split(".")
    return f"{'sz' if suffix == 'SZ' else 'sh'}{ticker}"


def _sina_symbol(code: str) -> str:
    ticker, suffix = code.split(".")
    if suffix == "SZ":
        return f"sz{ticker}"
    if suffix == "SH":
        return f"sh{ticker}"
    raise ValueError(f"Unsupported suffix: {code}")


HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://gu.qq.com/",
}
_HTTP_SESSION = requests.Session()


def _http_get(url: str, **kwargs):
    return _HTTP_SESSION.get(url, **kwargs)


def _source_record(
    code: str,
    source: str,
    adjustment: str,
    close: pd.Series,
    source_detail: str = "",
) -> dict:
    non_na = close.dropna()
    if non_na.empty:
        raise RuntimeError(f"{source} returned empty close series for {code}")
    return {
        "code": code,
        "name": ASSETS[code],
        "source": source,
        "adjustment": adjustment,
        "source_detail": source_detail,
        "first": non_na.index.min().date().isoformat(),
        "last": non_na.index.max().date().isoformat(),
        "rows": int(non_na.shape[0]),
    }


def _is_approved_cross_validated_raw_source(row: object) -> bool:
    return (
        str(getattr(row, "code", "") or "").strip() == "159985.SZ"
        and str(getattr(row, "source", "") or "").strip()
        == SOURCE_SINA_CNFIN_CROSS_VALIDATED
        and str(getattr(row, "adjustment", "") or "").strip().lower()
        == ADJUSTMENT_CROSS_VALIDATED_RAW
        and str(getattr(row, "source_detail", "") or "").strip()
        == SOURCE_DETAIL_SINA_CNFIN_CROSS_VALIDATED
    )


def _validate_qfq_sources(sources: pd.DataFrame) -> None:
    if sources.empty or "adjustment" not in sources.columns:
        raise RuntimeError("No qfq source metadata was returned")
    non_qfq: list[str] = []
    unapproved: list[str] = []
    for row in sources.itertuples(index=False):
        if _is_approved_cross_validated_raw_source(row):
            continue
        code = str(getattr(row, "code", "") or "").strip()
        source = str(getattr(row, "source", "") or "").strip()
        adjustment = str(getattr(row, "adjustment", "") or "").strip().lower()
        detail = str(getattr(row, "source_detail", "") or "").strip()
        if adjustment not in QFQ_ADJUSTMENT_ALLOWLIST:
            non_qfq.append(f"{code}:{source}[{adjustment}]")
        elif (source, detail) not in APPROVED_QFQ_HISTORICAL_SOURCES:
            unapproved.append(f"{code}:{source}[{detail}]")
    if non_qfq:
        raise RuntimeError("Non-qfq data source rejected: " + ", ".join(non_qfq[:6]))
    if unapproved:
        raise RuntimeError(
            "Unapproved qfq historical source rejected: " + ", ".join(unapproved[:6])
        )


def _load_akshare_eastmoney_qfq_one_close(code: str, end_date: pd.Timestamp) -> pd.Series:
    if not _HAS_AKSHARE:
        raise RuntimeError("akshare is not installed")
    symbol = _eastmoney_symbol(code)
    last_error = None
    for attempt in range(1, 4):
        try:
            df = ak.fund_etf_hist_em(
                symbol=symbol,
                period="daily",
                start_date=START_DATE.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                adjust="qfq",
            )
            if not df.empty:
                break
        except Exception as exc:
            last_error = exc
        time.sleep(1.5 * attempt)
    else:
        raise RuntimeError(f"AkShare Eastmoney qfq returned no rows for {code} / {symbol}; last_error={last_error}")
    close = df[["日期", "收盘"]].copy()
    close["日期"] = pd.to_datetime(close["日期"])
    close = close.set_index("日期")["收盘"].astype(float).sort_index()
    close = close.loc[:end_date]
    close.name = code
    return close


def _load_eastmoney_one_close(code: str, end_date: pd.Timestamp) -> pd.Series:
    """Fallback: fetch historical kline from Eastmoney HTTP API (fqt=1 = qfq)."""
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "klt": "101",
        "fqt": "1",
        "beg": START_DATE.strftime("%Y%m%d"),
        "end": end_date.strftime("%Y%m%d"),
        "secid": _eastmoney_market_id(code),
    }
    data = None
    last_error = None
    for attempt in range(1, 4):
        try:
            resp = _http_get(url, params=params, timeout=20, headers=HTTP_HEADERS)
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


def _validate_adjusted_close_continuity(code: str, close: pd.Series, source: str) -> None:
    returns = close.dropna().pct_change().abs().dropna()
    if returns.empty:
        return
    bad = returns[returns > MAX_ADJUSTED_DAILY_ABS_RETURN]
    if bad.empty:
        return
    first_date = pd.Timestamp(bad.index[0]).date().isoformat()
    raise RuntimeError(
        f"{source} adjusted close continuity check failed for {code}: "
        f"{first_date} abs_return={float(bad.iloc[0]):.2%}"
    )


def _load_tencent_qfq_one_close(code: str, end_date: pd.Timestamp) -> pd.Series:
    """Fetch Tencent qfq close, with independently verified day-key exceptions."""
    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    symbol = _tencent_fq_symbol(code)
    rows: list[list[str]] = []
    current_end = pd.Timestamp(end_date).normalize()
    last_error = None
    page_size = int(TENCENT_FQKLINE_PAGE_SIZE)
    payload_key: str | None = None
    for _page in range(16):
        page_rows: list[list[str]] | None = None
        page_error: Exception | None = None
        missing_qfqday_error: RuntimeError | None = None
        params = {
            "param": f"{symbol},day,{START_DATE.date().isoformat()},{current_end.date().isoformat()},{page_size},qfq",
        }
        for attempt in range(1, 4):
            try:
                resp = _http_get(url, params=params, timeout=20, headers=HTTP_HEADERS)
                resp.raise_for_status()
                payload = resp.json()
                data = payload.get("data") or {}
                if not isinstance(data, dict):
                    raise RuntimeError(f"Tencent returned non-object data for {code}: {payload.get('msg', '')}")
                node = data.get(symbol) or {}
                if "qfqday" in node:
                    page_payload_key = "qfqday"
                elif code in TENCENT_VERIFIED_DAY_QFQ_CODES and "day" in node:
                    page_payload_key = "day"
                else:
                    missing_qfqday_error = DeterministicProviderSchemaError(
                        f"Tencent fqkline adjusted response missing qfqday for {code}"
                    )
                    raise missing_qfqday_error
                if payload_key is not None and page_payload_key != payload_key:
                    missing_qfqday_error = DeterministicProviderSchemaError(
                        f"Tencent fqkline qfqday/day payload changed; refusing partial history for {code}"
                    )
                    raise missing_qfqday_error
                payload_key = page_payload_key
                page_error = None
                missing_qfqday_error = None
                page_rows = node.get(payload_key) or []
                if page_rows:
                    break
            except DeterministicProviderSchemaError as exc:
                if rows:
                    raise RuntimeError(
                        f"Tencent fqkline qfqday missing; refusing partial history for {code}"
                    ) from exc
                raise
            except Exception as exc:
                page_error = exc
                last_error = exc
            time.sleep(0.5 * attempt)
        if missing_qfqday_error is not None:
            if rows:
                raise RuntimeError(
                    f"Tencent fqkline qfqday missing; refusing partial history for {code}"
                ) from missing_qfqday_error
            raise missing_qfqday_error
        if page_rows is None:
            if rows:
                raise RuntimeError(
                    f"Tencent fqkline refusing partial history for {code} after provider failure: "
                    f"{page_error}"
                ) from page_error
            raise RuntimeError(
                f"Tencent fqkline qfq provider failure for {code}: {page_error}"
            ) from page_error
        if not page_rows:
            if not rows:
                raise RuntimeError(f"Tencent fqkline qfq returned no data for {code}; last_error={last_error}")
            break
        rows = page_rows + rows
        first_date = pd.Timestamp(page_rows[0][0]).normalize()
        if len(page_rows) < page_size or first_date <= START_DATE:
            break
        next_end = first_date - pd.Timedelta(days=1)
        if next_end >= current_end or next_end < START_DATE:
            break
        current_end = next_end
        time.sleep(0.2)

    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError(f"Tencent fqkline qfq normalized to empty for {code}")
    col_names = ["date", "open", "close", "high", "low", "volume"]
    df = df.iloc[:, :len(col_names)]
    df.columns = col_names
    close = df[["date", "close"]].copy()
    close["date"] = pd.to_datetime(close["date"])
    close = (
        close.drop_duplicates(subset=["date"], keep="last")
        .set_index("date")["close"]
        .astype(float)
        .sort_index()
    )
    close = close.loc[START_DATE:end_date]
    if close.dropna().empty:
        raise RuntimeError(f"Tencent fqkline qfq returned empty close series for {code}")
    _validate_adjusted_close_continuity(code, close, "Tencent fqkline")
    close.name = code
    close.attrs["source_detail"] = (
        SOURCE_DETAIL_TENCENT_VERIFIED_DAY_QFQ
        if payload_key == "day"
        else SOURCE_DETAIL_TENCENT_QFQ
    )
    return close


def _load_akshare_sina_raw_one_close(code: str, end_date: pd.Timestamp) -> pd.Series:
    """Diagnostic fallback for CN ETF history when approved qfq sources are unavailable."""
    if not _HAS_AKSHARE:
        raise RuntimeError("akshare is not installed")
    symbol = _sina_symbol(code)
    last_error = None
    for attempt in range(1, 4):
        try:
            df = ak.fund_etf_hist_sina(symbol=symbol)
            if df is not None and not df.empty:
                break
        except Exception as exc:
            last_error = exc
        time.sleep(1.5 * attempt)
    else:
        raise RuntimeError(f"AkShare Sina returned no rows for {code} / {symbol}; last_error={last_error}")
    if "date" not in df.columns or "close" not in df.columns:
        raise RuntimeError(f"AkShare Sina missing date/close columns for {code} / {symbol}")
    close = df[["date", "close"]].copy()
    close["date"] = pd.to_datetime(close["date"])
    close = close.set_index("date")["close"].astype(float).sort_index()
    close = close.loc[:end_date]
    close.name = code
    if close.dropna().empty:
        raise RuntimeError(f"AkShare Sina returned no usable close rows for {code} / {symbol}")
    return close


def _eastmoney_quote_time(value: object) -> str:
    ts = int(float(value))
    return datetime.fromtimestamp(ts, CN_TZ).strftime("%Y-%m-%d %H:%M:%S%z")


LIVE_QUOTE_COLUMNS = [
    "code",
    "price",
    "quote_time",
    "source",
    "source_execution_eligible",
    "prev_close",
    "limit_down",
    "limit_up",
    "volume",
    "amount",
]
LIVE_EXECUTION_ELIGIBLE_SOURCES = {"Eastmoney push2"}
EASTMONEY_LIVE_ENDPOINTS = (
    ("https://push2.eastmoney.com/api/qt/ulist.np/get", "Eastmoney push2", True),
    ("https://push2delay.eastmoney.com/api/qt/ulist.np/get", "Eastmoney push2delay", False),
)


class IncompleteLiveSnapshot(RuntimeError):
    pass


def _format_code_list(codes: list[str] | set[str]) -> str:
    return ",".join(sorted(str(code) for code in codes)) or "-"


class UnsupportedLiveQuoteSymbols(IncompleteLiveSnapshot):
    def __init__(self, codes: list[str] | set[str]):
        self.codes = tuple(sorted(str(code) for code in codes))
        super().__init__(
            "live quotes unsupported for proxy/non-CN symbols: "
            + _format_code_list(set(self.codes))
        )


def _is_proxy_live_quote_unsupported_error(exc: Exception) -> bool:
    return isinstance(exc, UnsupportedLiveQuoteSymbols)


def _live_snapshot_error(
    *,
    missing: set[str] | list[str] | None = None,
    duplicates: set[str] | list[str] | None = None,
    invalid: list[str] | None = None,
) -> str:
    parts = ["Incomplete live quote snapshot"]
    if missing:
        parts.append(f"missing={_format_code_list(set(missing))}")
    if duplicates:
        parts.append(f"duplicate={_format_code_list(set(duplicates))}")
    if invalid:
        parts.append("invalid=" + ",".join(str(item) for item in invalid))
    return "; ".join(parts)


def _explicit_bool_value(value: object, default: bool = False) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "y"}:
            return True
        if text in {"0", "false", "no", "n", ""}:
            return False
        return default
    if isinstance(value, (int, np.integer)):
        return int(value) == 1
    return default


def _source_execution_eligible(source: object, explicit_flag: object = False) -> bool:
    source_name = str(source or "").strip()
    return bool(
        source_name in LIVE_EXECUTION_ELIGIBLE_SOURCES
        and _explicit_bool_value(explicit_flag, False)
    )


def _optional_positive_float(value: object) -> float:
    number = _float(value, default=math.nan)
    return number if math.isfinite(number) and number > 0 else math.nan


def _optional_nonnegative_float(value: object) -> float:
    number = _float(value, default=math.nan)
    return number if math.isfinite(number) and number >= 0 else math.nan


def _decimal_from_number(value: object) -> Decimal | None:
    number = _optional_positive_float(value)
    if not math.isfinite(number):
        return None
    try:
        return Decimal(str(number))
    except (InvalidOperation, ValueError):
        return None


def _is_etf_tick_price(value: object) -> bool:
    dec = _decimal_from_number(value)
    if dec is None:
        return False
    return dec == dec.quantize(ETF_PRICE_TICK, rounding=ROUND_HALF_UP)


def _live_price_limit_ratio(code: str) -> float:
    text = str(code).strip()
    if not _is_cn_exchange_symbol(text):
        return math.nan
    return float(LIVE_PRICE_LIMIT_RATIO_BY_CODE.get(text, 0.10))


def _price_limit_bounds_from_prev_close(code: str, prev_close: object) -> tuple[float, float]:
    previous = _decimal_from_number(prev_close)
    if previous is None:
        return math.nan, math.nan
    ratio_value = _live_price_limit_ratio(code)
    if not math.isfinite(ratio_value):
        return math.nan, math.nan
    ratio = Decimal(str(ratio_value))
    lower = (previous * (Decimal("1") - ratio)).quantize(ETF_PRICE_TICK, rounding=ROUND_HALF_UP)
    upper = (previous * (Decimal("1") + ratio)).quantize(ETF_PRICE_TICK, rounding=ROUND_HALF_UP)
    if abs(previous - lower) < ETF_PRICE_TICK:
        lower = max(previous - ETF_PRICE_TICK, ETF_PRICE_TICK)
    if abs(upper - previous) < ETF_PRICE_TICK:
        upper = previous + ETF_PRICE_TICK
    return float(lower), float(upper)


def _prev_close_matches_reference(vendor_prev_close: float, independent_prev_close: float) -> bool:
    vendor = _decimal_from_number(vendor_prev_close)
    reference = _decimal_from_number(independent_prev_close)
    if vendor is None or reference is None:
        return False
    return abs(vendor - reference) <= ETF_PRICE_TICK


def _prev_close_matches_reference_for_code(
    code: str,
    vendor_prev_close: float,
    independent_prev_close: float,
) -> bool:
    if code in EASTMONEY_LIVE_PROXY_SECIDS:
        if not (math.isfinite(vendor_prev_close) and math.isfinite(independent_prev_close)):
            return False
        return abs(vendor_prev_close / independent_prev_close - 1.0) <= 1e-4
    return _prev_close_matches_reference(vendor_prev_close, independent_prev_close)


def _normalize_price_limit_fields(
    code: str,
    prev_close: object = math.nan,
    limit_down: object = math.nan,
    limit_up: object = math.nan,
) -> tuple[float, float, float]:
    previous = _optional_positive_float(prev_close)
    if not _is_cn_exchange_symbol(code):
        return previous, math.nan, math.nan
    lower = _optional_positive_float(limit_down)
    upper = _optional_positive_float(limit_up)
    if math.isfinite(previous) and not (math.isfinite(lower) and math.isfinite(upper)):
        derived_lower, derived_upper = _price_limit_bounds_from_prev_close(code, previous)
        if not math.isfinite(lower):
            lower = derived_lower
        if not math.isfinite(upper):
            upper = derived_upper
    return previous, lower, upper


def _all_quotes_execution_eligible(quotes: pd.DataFrame) -> bool:
    if quotes is None or quotes.empty:
        return False
    return all(
        _explicit_bool_value(getattr(row, "source_execution_eligible", False), False)
        for row in quotes.itertuples(index=False)
    )


def _normalize_live_quote_rows(
    rows: list[dict],
    requested_codes: list[str],
    *,
    source: str,
    source_execution_eligible: bool,
    now: datetime | None = None,
    require_today: bool = False,
    expected_quote_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    requested_codes = list(dict.fromkeys(requested_codes))
    requested_set = set(requested_codes)
    suffix_by_ticker = {
        (_eastmoney_live_ticker(code) or code.split(".", 1)[0]): code
        for code in requested_codes
    }
    now_ts = pd.Timestamp(_as_bj_datetime(now)) if now is not None else None
    if expected_quote_date is None and now_ts is not None:
        expected_quote_date = pd.Timestamp(now_ts.date()).normalize()
    elif expected_quote_date is not None:
        expected_quote_date = pd.Timestamp(expected_quote_date).normalize()
    seen_counts: dict[str, int] = {}
    parsed_by_code: dict[str, dict[str, object]] = {}
    invalid: list[str] = []

    for item in rows:
        ticker = str(item.get("f12", "")).strip()
        code = suffix_by_ticker.get(ticker)
        if not code:
            continue
        seen_counts[code] = seen_counts.get(code, 0) + 1
        price = _float(item.get("f2"), default=math.nan)
        if not math.isfinite(price) or price <= 0:
            invalid.append(f"{code}:price")
            continue
        try:
            quote_time = _eastmoney_quote_time(item.get("f124"))
        except Exception:
            invalid.append(f"{code}:quote_time")
            continue
        quote_ts = _parse_quote_time(quote_time)
        if quote_ts is None or quote_ts.year < 2000:
            invalid.append(f"{code}:quote_time")
            continue
        if now_ts is not None and quote_ts > now_ts + LIVE_QUOTE_FUTURE_TOLERANCE:
            invalid.append(f"{code}:future_quote_time")
            continue
        if (
            require_today
            and expected_quote_date is not None
            and pd.Timestamp(quote_ts.date()).normalize() != expected_quote_date
        ):
            invalid.append(f"{code}:quote_date")
            continue
        prev_close, limit_down, limit_up = _normalize_price_limit_fields(code, item.get("f18", math.nan))
        volume = _optional_nonnegative_float(item.get("f5", math.nan))
        amount = _optional_nonnegative_float(item.get("f6", math.nan))
        parsed_by_code[code] = {
            "code": code,
            "price": price,
            "quote_time": _format_quote_time(quote_ts),
            "source": source,
            "source_execution_eligible": _source_execution_eligible(
                source,
                bool(source_execution_eligible and _is_cn_exchange_symbol(code)),
            ),
            "prev_close": prev_close,
            "limit_down": limit_down,
            "limit_up": limit_up,
            "volume": volume,
            "amount": amount,
        }

    duplicates = {code for code, count in seen_counts.items() if count > 1}
    returned_codes = set(parsed_by_code)
    missing = requested_set - returned_codes
    if missing or duplicates or invalid or returned_codes != requested_set or len(parsed_by_code) != len(requested_codes):
        raise IncompleteLiveSnapshot(
            _live_snapshot_error(missing=missing, duplicates=duplicates, invalid=invalid)
        )
    return pd.DataFrame(
        [parsed_by_code[code] for code in requested_codes],
        columns=LIVE_QUOTE_COLUMNS,
    )


def _normalize_live_quote_frame(
    quotes: pd.DataFrame,
    requested_codes: list[str],
    *,
    now: datetime | None = None,
    require_today: bool = False,
    expected_quote_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    requested_codes = list(dict.fromkeys(requested_codes))
    requested_set = set(requested_codes)
    if quotes is None or quotes.empty:
        raise IncompleteLiveSnapshot(_live_snapshot_error(missing=requested_set))
    now_ts = pd.Timestamp(_as_bj_datetime(now)) if now is not None else None
    if expected_quote_date is None and now_ts is not None:
        expected_quote_date = pd.Timestamp(now_ts.date()).normalize()
    elif expected_quote_date is not None:
        expected_quote_date = pd.Timestamp(expected_quote_date).normalize()
    seen_counts: dict[str, int] = {}
    parsed_by_code: dict[str, dict[str, object]] = {}
    invalid: list[str] = []

    for row in quotes.itertuples(index=False):
        code = str(getattr(row, "code", "")).strip()
        if code not in requested_set:
            continue
        seen_counts[code] = seen_counts.get(code, 0) + 1
        try:
            price = float(getattr(row, "price"))
        except Exception:
            invalid.append(f"{code}:price")
            continue
        if not math.isfinite(price) or price <= 0:
            invalid.append(f"{code}:price")
            continue
        quote_ts = _parse_quote_time(getattr(row, "quote_time", None))
        if quote_ts is None or quote_ts.year < 2000:
            invalid.append(f"{code}:quote_time")
            continue
        if now_ts is not None and quote_ts > now_ts + LIVE_QUOTE_FUTURE_TOLERANCE:
            invalid.append(f"{code}:future_quote_time")
            continue
        if (
            require_today
            and expected_quote_date is not None
            and pd.Timestamp(quote_ts.date()).normalize() != expected_quote_date
        ):
            invalid.append(f"{code}:quote_date")
            continue
        source = str(getattr(row, "source", "") or "").strip()
        explicit_flag = getattr(row, "source_execution_eligible", False)
        prev_close, limit_down, limit_up = _normalize_price_limit_fields(
            code,
            getattr(row, "prev_close", math.nan),
            getattr(row, "limit_down", math.nan),
            getattr(row, "limit_up", math.nan),
        )
        volume = _optional_nonnegative_float(getattr(row, "volume", math.nan))
        amount = _optional_nonnegative_float(getattr(row, "amount", math.nan))
        parsed_by_code[code] = {
            "code": code,
            "price": price,
            "quote_time": _format_quote_time(quote_ts),
            "source": source or "live quote",
            "source_execution_eligible": _source_execution_eligible(
                source,
                bool(_explicit_bool_value(explicit_flag, False) and _is_cn_exchange_symbol(code)),
            ),
            "prev_close": prev_close,
            "limit_down": limit_down,
            "limit_up": limit_up,
            "volume": volume,
            "amount": amount,
        }

    duplicates = {code for code, count in seen_counts.items() if count > 1}
    returned_codes = set(parsed_by_code)
    missing = requested_set - returned_codes
    if missing or duplicates or invalid or returned_codes != requested_set or len(parsed_by_code) != len(requested_codes):
        raise IncompleteLiveSnapshot(
            _live_snapshot_error(missing=missing, duplicates=duplicates, invalid=invalid)
        )
    return pd.DataFrame(
        [parsed_by_code[code] for code in requested_codes],
        columns=LIVE_QUOTE_COLUMNS,
    )


def _live_quote_temporal_quality(quotes: pd.DataFrame, received_at: datetime) -> tuple[bool, str]:
    received_ts = pd.Timestamp(_as_bj_datetime(received_at))
    quote_times: list[pd.Timestamp] = []
    stale_codes: list[str] = []
    invalid: list[str] = []
    for row in quotes.itertuples(index=False):
        code = str(getattr(row, "code", "")).strip()
        quote_ts = _parse_quote_time(getattr(row, "quote_time", None))
        if quote_ts is None:
            invalid.append(f"{code}:quote_time")
            continue
        quote_times.append(quote_ts)
        quote_age = received_ts - quote_ts
        if quote_ts.date() != received_ts.date() or quote_ts > received_ts + LIVE_QUOTE_FUTURE_TOLERANCE:
            invalid.append(f"{code}:quote_time")
        elif quote_age > LIVE_QUOTE_MAX_AGE:
            stale_codes.append(code)
    if invalid:
        return False, "invalid=" + ",".join(invalid)
    if stale_codes:
        return False, "stale=" + _format_code_list(set(stale_codes))
    if quote_times:
        max_skew = max(quote_times) - min(quote_times)
        if max_skew > LIVE_QUOTE_MAX_SKEW:
            return False, f"skew_seconds={max_skew.total_seconds():.0f}"
    return True, ""


def _live_quote_candidate_latest_time(quotes: pd.DataFrame) -> pd.Timestamp | None:
    quote_times = [
        quote_ts
        for quote_ts in (_parse_quote_time(getattr(row, "quote_time", None)) for row in quotes.itertuples(index=False))
        if quote_ts is not None
    ]
    return max(quote_times) if quote_times else None


def _live_quote_candidate_quality_key(
    quotes: pd.DataFrame,
    received_at: datetime,
) -> tuple[float, float, float, float, float, float]:
    if quotes is None or quotes.empty:
        return (math.inf, math.inf, math.inf, math.inf, math.inf, math.inf)
    received_ts = pd.Timestamp(_as_bj_datetime(received_at))
    quote_times: list[pd.Timestamp] = []
    invalid_count = 0
    stale_count = 0
    for row in quotes.itertuples(index=False):
        quote_ts = _parse_quote_time(getattr(row, "quote_time", None))
        if quote_ts is None:
            invalid_count += 1
            continue
        quote_times.append(quote_ts)
        quote_age = received_ts - quote_ts
        if (
            quote_ts.date() != received_ts.date()
            or quote_ts > received_ts + LIVE_QUOTE_FUTURE_TOLERANCE
            or quote_age > LIVE_QUOTE_MAX_AGE
        ):
            stale_count += 1
    if not quote_times:
        return (invalid_count or math.inf, math.inf, math.inf, math.inf, math.inf, math.inf)
    max_quote_time = max(quote_times)
    min_quote_time = min(quote_times)
    max_age = max(max((received_ts - quote_ts).total_seconds(), 0.0) for quote_ts in quote_times)
    max_skew = max((max_quote_time - min_quote_time).total_seconds(), 0.0)
    max_age_limit = float(LIVE_QUOTE_MAX_AGE.total_seconds())
    max_skew_limit = float(LIVE_QUOTE_MAX_SKEW.total_seconds())
    age_ratio = max_age / max_age_limit if max_age_limit > 0 else math.inf
    skew_ratio = max_skew / max_skew_limit if max_skew_limit > 0 else math.inf
    worst_violation = max(age_ratio, skew_ratio)
    source_penalty = 0.0 if _all_quotes_execution_eligible(quotes) else 1.0
    return (
        float(invalid_count),
        float(worst_violation),
        float(stale_count),
        float(age_ratio + skew_ratio),
        source_penalty,
        -float(max_quote_time.timestamp()),
    )


def _better_live_quote_candidate(
    current: pd.DataFrame | None,
    candidate: pd.DataFrame,
    received_at: datetime,
) -> pd.DataFrame:
    if current is None:
        return candidate
    current_key = _live_quote_candidate_quality_key(current, received_at)
    candidate_key = _live_quote_candidate_quality_key(candidate, received_at)
    return candidate if candidate_key < current_key else current


def _missing_vendor_prev_close_codes(quotes: pd.DataFrame) -> list[str]:
    missing: list[str] = []
    for row in quotes.itertuples(index=False):
        code = str(getattr(row, "code", "")).strip()
        vendor_previous = _optional_positive_float(getattr(row, "prev_close", math.nan))
        if not math.isfinite(vendor_previous):
            missing.append(code)
    return missing


def _demote_live_quote_execution(quotes: pd.DataFrame) -> pd.DataFrame:
    out = quotes.copy()
    out["source_execution_eligible"] = False
    return out


def _validate_live_quote_prices_against_history(
    prices: pd.DataFrame,
    quotes: pd.DataFrame,
    today: pd.Timestamp,
) -> None:
    if prices is None or prices.empty or quotes is None or quotes.empty:
        return
    price_lookup = prices.copy()
    price_lookup.index = pd.DatetimeIndex(price_lookup.index).normalize()
    today = pd.Timestamp(today).normalize()
    invalid: list[str] = []
    for row in quotes.itertuples(index=False):
        code = str(getattr(row, "code", "")).strip()
        if code not in price_lookup.columns:
            continue
        quote_price = _optional_positive_float(getattr(row, "price", math.nan))
        if not math.isfinite(quote_price):
            invalid.append(f"{code}:price")
            continue
        is_cn_exchange = _is_cn_exchange_symbol(code)
        if is_cn_exchange and not _is_etf_tick_price(quote_price):
            invalid.append(f"{code}:price_tick={quote_price:.6f}")
            continue
        series = pd.to_numeric(price_lookup[code], errors="coerce")
        prev_history = series.loc[series.index < today].dropna()
        independent_previous = _optional_positive_float(prev_history.iloc[-1]) if not prev_history.empty else math.nan
        if not math.isfinite(independent_previous):
            invalid.append(f"{code}:prev_close_reference_missing")
            continue
        vendor_previous = _optional_positive_float(getattr(row, "prev_close", math.nan))
        check_vendor_previous = is_cn_exchange or code in EASTMONEY_LIVE_PROXY_SECIDS
        if check_vendor_previous and math.isfinite(vendor_previous):
            if is_cn_exchange and not _is_etf_tick_price(vendor_previous):
                invalid.append(f"{code}:prev_close_tick={vendor_previous:.6f}")
                continue
            if not _prev_close_matches_reference_for_code(code, vendor_previous, independent_previous):
                diff = abs(vendor_previous / independent_previous - 1.0)
                invalid.append(f"{code}:prev_close_reference_diff={diff:.2%}")
                continue
        previous = independent_previous
        limit_down, limit_up = (
            _price_limit_bounds_from_prev_close(code, previous)
            if is_cn_exchange
            else (math.nan, math.nan)
        )
        if is_cn_exchange and math.isfinite(limit_down) and math.isfinite(limit_up):
            if quote_price < limit_down - LIVE_PRICE_LIMIT_TOLERANCE or quote_price > limit_up + LIVE_PRICE_LIMIT_TOLERANCE:
                detail = f"{code}:price_limit={quote_price:.4f} not_in [{limit_down:.4f},{limit_up:.4f}]"
                if math.isfinite(previous):
                    detail += f":prev_close_return={quote_price / previous - 1.0:.2%}"
                invalid.append(detail)
        history_today = series.loc[series.index == today].dropna()
        if not history_today.empty:
            today_close = _optional_positive_float(history_today.iloc[-1])
            if math.isfinite(today_close):
                diff = abs(quote_price / today_close - 1.0)
                if diff > LIVE_PRICE_HISTORY_TODAY_MAX_DIFF:
                    invalid.append(f"{code}:history_today_diff={diff:.2%}:requires_backup_review")
                    continue
    if invalid:
        raise IncompleteLiveSnapshot(_live_snapshot_error(invalid=invalid))


def _last_valid_index(values: list[object]) -> int | None:
    for idx in range(len(values) - 1, -1, -1):
        try:
            value = float(values[idx])
        except Exception:
            continue
        if math.isfinite(value) and value > 0:
            return idx
    return None


def _load_yahoo_live_quotes(
    codes: list[str],
    *,
    now: datetime | None = None,
    expected_quote_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    now_ts = pd.Timestamp(_as_bj_datetime(now)) if now is not None else None
    expected = None if expected_quote_date is None else pd.Timestamp(expected_quote_date).normalize()
    for code in codes:
        ticker = _yahoo_live_ticker(code)
        if ticker is None:
            continue
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        params = {
            "range": "1d",
            "interval": "1m",
            "includePrePost": "true",
            "events": "history",
        }
        last_error = None
        for attempt in range(1, 3):
            try:
                resp = _http_get(url, params=params, timeout=20, headers=HTTP_HEADERS)
                resp.raise_for_status()
                result = (((resp.json().get("chart") or {}).get("result") or [None])[0])
                if not result:
                    raise IncompleteLiveSnapshot(f"{code}:yahoo_no_result")
                timestamps = result.get("timestamp") or []
                quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
                closes = quote.get("close") or []
                volumes = quote.get("volume") or []
                idx = _last_valid_index(list(closes))
                if idx is None or idx >= len(timestamps):
                    raise IncompleteLiveSnapshot(f"{code}:yahoo_no_price")
                price = float(closes[idx])
                quote_ts = pd.to_datetime(int(timestamps[idx]), unit="s", utc=True).tz_convert(CN_TZ)
                if now_ts is not None and quote_ts > now_ts + LIVE_QUOTE_FUTURE_TOLERANCE:
                    raise IncompleteLiveSnapshot(f"{code}:future_quote_time")
                if expected is not None and pd.Timestamp(quote_ts.date()).normalize() != expected:
                    raise IncompleteLiveSnapshot(f"{code}:quote_date")
                volume = (
                    _optional_nonnegative_float(volumes[idx])
                    if idx < len(volumes)
                    else math.nan
                )
                amount = price * volume if math.isfinite(volume) else math.nan
                meta = result.get("meta") or {}
                prev_close = _optional_positive_float(
                    meta.get("previousClose", meta.get("chartPreviousClose", math.nan))
                )
                rows.append(
                    {
                        "code": code,
                        "price": price,
                        "quote_time": _format_quote_time(quote_ts),
                        "source": "Yahoo Finance chart 1m",
                        "source_execution_eligible": False,
                        "prev_close": prev_close,
                        "limit_down": math.nan,
                        "limit_up": math.nan,
                        "volume": volume,
                        "amount": amount,
                    }
                )
                break
            except Exception as exc:
                last_error = exc
                if attempt >= 2:
                    raise RuntimeError(f"Yahoo live quote unavailable for {code}: {last_error}") from exc
                time.sleep(0.5 * attempt)
    return pd.DataFrame(rows, columns=LIVE_QUOTE_COLUMNS)


def _eastmoney_live_codes(codes: list[str]) -> list[str]:
    return [code for code in codes if _eastmoney_live_secid(code) is not None]


def _yahoo_live_codes(codes: list[str]) -> list[str]:
    return [code for code in codes if _yahoo_live_ticker(code) is not None]


def _fetch_eastmoney_live_quotes_from_endpoint(
    codes: list[str],
    *,
    url: str,
    source: str,
    source_execution_eligible: bool,
    response_received_at: datetime,
    expected_quote_date: pd.Timestamp,
) -> pd.DataFrame:
    if not codes:
        return pd.DataFrame(columns=LIVE_QUOTE_COLUMNS)
    params = {
        "fltt": "2",
        "invt": "2",
        "fields": "f12,f14,f2,f5,f6,f18,f124",
        "secids": ",".join(str(_eastmoney_live_secid(code)) for code in codes),
    }
    resp = _http_get(url, params=params, timeout=10, headers=HTTP_HEADERS)
    resp.raise_for_status()
    payload = resp.json()
    rows = ((payload.get("data") or {}).get("diff") or [])
    return _normalize_live_quote_rows(
        rows,
        codes,
        source=source,
        source_execution_eligible=source_execution_eligible,
        now=response_received_at,
        require_today=True,
        expected_quote_date=expected_quote_date,
    )


def load_live_quotes(
    codes: list[str],
    now: datetime | None = None,
    reference_prices: pd.DataFrame | None = None,
    expected_quote_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Fetch paired live price and vendor quote time for the ETF pool."""
    codes = list(dict.fromkeys(codes))
    if not codes:
        return pd.DataFrame(columns=LIVE_QUOTE_COLUMNS)
    unsupported = _live_quote_unsupported_codes(codes)
    if unsupported:
        raise UnsupportedLiveQuoteSymbols(unsupported)
    request_ts = _as_bj_datetime(now)
    if expected_quote_date is None:
        expected_quote_date = pd.Timestamp(request_ts.date()).normalize()
    else:
        expected_quote_date = pd.Timestamp(expected_quote_date).normalize()
    errors: list[str] = []
    best_monitor_candidate: pd.DataFrame | None = None
    eastmoney_codes = _eastmoney_live_codes(codes)
    yahoo_codes = _yahoo_live_codes(codes)
    yahoo_frame = pd.DataFrame(columns=LIVE_QUOTE_COLUMNS)
    if yahoo_codes:
        yahoo_frame = _load_yahoo_live_quotes(
            yahoo_codes,
            now=_now_bj(),
            expected_quote_date=expected_quote_date,
        )
    endpoints = EASTMONEY_LIVE_ENDPOINTS if eastmoney_codes else ((None, "", False),)
    for url, source, source_execution_eligible in endpoints:
        for attempt in range(1, 3):
            try:
                response_received_at = _now_bj()
                frames: list[pd.DataFrame] = []
                if yahoo_codes:
                    frames.append(yahoo_frame.copy())
                if eastmoney_codes and url is not None:
                    frames.append(
                        _fetch_eastmoney_live_quotes_from_endpoint(
                            eastmoney_codes,
                            url=url,
                            source=source,
                            source_execution_eligible=source_execution_eligible,
                            response_received_at=response_received_at,
                            expected_quote_date=expected_quote_date,
                        )
                    )
                candidate = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=LIVE_QUOTE_COLUMNS)
                candidate = _normalize_live_quote_frame(
                    candidate,
                    codes,
                    now=response_received_at,
                    require_today=True,
                    expected_quote_date=expected_quote_date,
                )
                if reference_prices is not None:
                    try:
                        _validate_live_quote_prices_against_history(reference_prices, candidate, expected_quote_date)
                    except IncompleteLiveSnapshot as exc:
                        errors.append(f"{source} attempt {attempt}: price quality rejected: {exc}")
                        if attempt < 2:
                            time.sleep(0.5 * attempt)
                        continue
                    cn_candidate = candidate[candidate["code"].map(_is_cn_exchange_symbol)]
                    missing_prev_close = _missing_vendor_prev_close_codes(cn_candidate)
                    if missing_prev_close:
                        candidate = _demote_live_quote_execution(candidate)
                        errors.append(
                            f"{source} attempt {attempt}: vendor prev_close missing; monitor only="
                            + _format_code_list(set(missing_prev_close))
                        )
                fresh_enough, quality_reason = _live_quote_temporal_quality(candidate, response_received_at)
                if not fresh_enough:
                    best_monitor_candidate = _better_live_quote_candidate(
                        best_monitor_candidate,
                        candidate,
                        response_received_at,
                    )
                    errors.append(f"{source} attempt {attempt}: quote quality rejected: {quality_reason}")
                    if attempt < 2:
                        time.sleep(0.5 * attempt)
                    continue
                if _all_quotes_execution_eligible(candidate):
                    return candidate
                best_monitor_candidate = _better_live_quote_candidate(
                    best_monitor_candidate,
                    candidate,
                    response_received_at,
                )
                errors.append(f"{source} attempt {attempt}: source permission rejected")
                if attempt < 2:
                    time.sleep(0.5 * attempt)
                continue
            except IncompleteLiveSnapshot as exc:
                errors.append(f"{source} attempt {attempt}: {exc}")
            except Exception as exc:
                errors.append(f"{source} attempt {attempt}: {str(exc)[:120]}")
            if attempt < 2:
                time.sleep(0.5 * attempt)
    if best_monitor_candidate is not None:
        return best_monitor_candidate
    raise RuntimeError("Eastmoney live quote unavailable. " + " | ".join(errors[-6:]))


def _load_sina_raw_one_close(code: str, end_date: pd.Timestamp) -> pd.Series:
    url = "https://quotes.sina.cn/cn/api/openapi.php/CN_MarketDataService.getKLineData"
    params = {
        "symbol": _sina_symbol(code),
        "scale": "240",
        "ma": "no",
        "datalen": str(SINA_DAILY_KLINE_MAX_ROWS),
    }
    last_error = None
    rows = None
    for attempt in range(1, 4):
        try:
            resp = _http_get(url, params=params, timeout=30, headers=HTTP_HEADERS)
            resp.raise_for_status()
            payload = resp.json()
            rows = ((payload.get("result") or {}).get("data") or [])
            if rows:
                break
        except Exception as exc:
            last_error = exc
        time.sleep(0.5 * attempt)
    if not rows:
        raise RuntimeError(f"Sina direct kline returned no data for {code}; last_error={last_error}")
    frame = pd.DataFrame(rows)
    if "day" not in frame.columns or "close" not in frame.columns:
        raise RuntimeError(f"Sina direct kline missing day/close for {code}")
    close = pd.Series(
        pd.to_numeric(frame["close"], errors="coerce").to_numpy(),
        index=pd.to_datetime(frame["day"], errors="coerce"),
        name=code,
        dtype="float64",
    ).dropna().sort_index()
    close = close[~close.index.duplicated(keep="last")].loc[:pd.Timestamp(end_date).normalize()]
    if close.empty or not np.isfinite(close.to_numpy()).all() or not (close > 0).all():
        raise RuntimeError(f"Sina direct kline normalized to invalid close series for {code}")
    close.attrs["adjustment"] = ADJUSTMENT_CROSS_VALIDATED_RAW
    return close


def _load_cnfin_raw_one_close(code: str, end_date: pd.Timestamp) -> pd.Series:
    if code not in CROSS_VALIDATED_RAW_CODES:
        raise RuntimeError(f"CNFin raw fallback unsupported for {code}")
    url = "https://quotedata.cnfin.com/quote/v1/kline"
    required_start = CROSS_VALIDATED_RAW_CODES[code]
    current_end = pd.Timestamp(end_date).normalize()
    rows: list[list[object]] = []
    fields: list[str] = []
    last_error = None
    for _page in range(10):
        page_rows = None
        params = {
            "prod_code": code,
            "candle_period": "6",
            "get_type": "range",
            "start_date": required_start.strftime("%Y%m%d"),
            "end_date": current_end.strftime("%Y%m%d"),
            "fields": "open_px,high_px,low_px,close_px,business_amount,business_balance",
        }
        for attempt in range(1, 4):
            try:
                resp = _http_get(url, params=params, timeout=30, headers=HTTP_HEADERS)
                resp.raise_for_status()
                candle = ((resp.json().get("data") or {}).get("candle") or {})
                fields = list(candle.get("fields") or [])
                page_rows = candle.get(code) or []
                if page_rows:
                    break
            except Exception as exc:
                last_error = exc
            time.sleep(0.5 * attempt)
        if not page_rows:
            if not rows:
                raise RuntimeError(f"CNFin raw kline returned no data for {code}; last_error={last_error}")
            break
        rows = page_rows + rows
        first_date = pd.Timestamp(str(page_rows[0][0])).normalize()
        if len(page_rows) < CNFIN_KLINE_PAGE_SIZE or first_date <= required_start:
            break
        next_end = first_date - pd.Timedelta(days=1)
        if next_end >= current_end or next_end < required_start:
            raise RuntimeError(f"CNFin raw kline pagination stalled for {code}")
        current_end = next_end
    if "min_time" not in fields or "close_px" not in fields:
        raise RuntimeError(f"CNFin raw kline missing min_time/close_px for {code}")
    frame = pd.DataFrame(rows, columns=fields)
    close = pd.Series(
        pd.to_numeric(frame["close_px"], errors="coerce").to_numpy(),
        index=pd.to_datetime(frame["min_time"].astype(str), errors="coerce"),
        name=code,
        dtype="float64",
    ).dropna().sort_index()
    close = close[~close.index.duplicated(keep="last")]
    close = close.loc[required_start:pd.Timestamp(end_date).normalize()]
    if close.empty or not np.isfinite(close.to_numpy()).all() or not (close > 0).all():
        raise RuntimeError(f"CNFin raw kline normalized to invalid close series for {code}")
    close.attrs["adjustment"] = ADJUSTMENT_CROSS_VALIDATED_RAW
    return close


def _load_cross_validated_raw_one_close(code: str, end_date: pd.Timestamp) -> pd.Series:
    listing_date = CROSS_VALIDATED_RAW_CODES.get(code)
    if listing_date is None:
        raise RuntimeError(f"cross-validated raw fallback unsupported for {code}")
    sina = _load_sina_raw_one_close(code, end_date)
    cnfin = _load_cnfin_raw_one_close(code, end_date)
    if sina.index.min() != listing_date or cnfin.index.min() != listing_date:
        raise RuntimeError(f"cross-validated raw listing coverage missing for {code}")
    common_index = sina.index.intersection(cnfin.index).sort_values()
    shorter_rows = min(len(sina), len(cnfin))
    if len(common_index) < CROSS_VALIDATED_RAW_MIN_ROWS:
        raise RuntimeError(f"cross-validated raw overlap rows insufficient for {code}")
    if len(common_index) / shorter_rows < CROSS_VALIDATED_RAW_MIN_SHORTER_OVERLAP:
        raise RuntimeError(f"cross-validated raw overlap ratio insufficient for {code}")
    sina_common = sina.reindex(common_index)
    cnfin_common = cnfin.reindex(common_index)
    max_diff = float((sina_common - cnfin_common).abs().max())
    if max_diff > CROSS_VALIDATED_RAW_MAX_ABS_CLOSE_DIFF + 1e-12:
        raise RuntimeError(
            f"cross-validated raw close difference too large for {code}: {max_diff:.6f}"
        )
    close = sina_common.copy()
    _validate_adjusted_close_continuity(code, close, SOURCE_SINA_CNFIN_CROSS_VALIDATED)
    close.attrs["adjustment"] = ADJUSTMENT_CROSS_VALIDATED_RAW
    source_detail = SOURCE_DETAIL_SINA_CNFIN_CROSS_VALIDATED
    if len(sina) >= SINA_DAILY_KLINE_WARN_ROWS:
        source_detail += (
            f"; Sina history cap warning: {len(sina)}/{SINA_DAILY_KLINE_MAX_ROWS} rows"
        )
    close.attrs["source_detail"] = source_detail
    return close


def _load_public_close_with_per_code_fallback(codes: list[str], end_date: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    series: list[pd.Series] = []
    sources: list[dict] = []
    errors: list[str] = []
    for code in codes:
        providers = [
            (
                "akshare.fund_etf_hist_em daily close",
                ADJUSTMENT_QFQ,
                SOURCE_DETAIL_AKSHARE_QFQ,
                _load_akshare_eastmoney_qfq_one_close,
            ),
            (
                "Tencent fqkline",
                ADJUSTMENT_QFQ,
                SOURCE_DETAIL_TENCENT_QFQ,
                _load_tencent_qfq_one_close,
            ),
            (
                "Eastmoney push2his kline",
                ADJUSTMENT_QFQ,
                SOURCE_DETAIL_EASTMONEY_FQT1,
                _load_eastmoney_one_close,
            ),
        ]
        if code in CROSS_VALIDATED_RAW_CODES:
            providers.append(
                (
                    SOURCE_SINA_CNFIN_CROSS_VALIDATED,
                    ADJUSTMENT_CROSS_VALIDATED_RAW,
                    SOURCE_DETAIL_SINA_CNFIN_CROSS_VALIDATED,
                    _load_cross_validated_raw_one_close,
                )
            )
        for source_name, adjustment, source_detail, loader in providers:
            try:
                close = loader(code, end_date)
                source_detail = str(close.attrs.get("source_detail") or source_detail)
                series.append(close)
                sources.append(_source_record(code, source_name, adjustment, close, source_detail))
                break
            except Exception as exc:
                errors.append(f"{code} {source_name}: {str(exc)[:160]}")
        else:
            raise RuntimeError("All historical data sources failed. " + " | ".join(errors[-8:]))
    source_frame = pd.DataFrame(sources)
    _validate_qfq_sources(source_frame)
    return pd.concat(series, axis=1).sort_index(), source_frame


def _source_summary_text(sources: pd.DataFrame) -> str:
    parts: list[str] = []
    for row in sources.itertuples(index=False):
        detail = str(getattr(row, "source_detail", "") or "").strip()
        adjustment = str(getattr(row, "adjustment", "") or "").strip()
        suffix = f"{adjustment}; {detail}" if detail else adjustment
        parts.append(f"{row.source} [{suffix}]")
    return ", ".join(dict.fromkeys(parts))


def _live_price_limit_summary() -> str:
    limited = [code for code in ASSETS if _is_cn_exchange_symbol(code)]
    execution_unsupported = [code for code in ASSETS if not _is_cn_exchange_symbol(code)]
    parts = [f"{code}={_live_price_limit_ratio(code):.0%}" for code in limited]
    if execution_unsupported:
        parts.append("proxy/non-CN live execution unsupported=" + ", ".join(sorted(execution_unsupported)))
    return ", ".join(parts)


def _fetch_yahoo_adj_close(ticker: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    period1 = int(pd.Timestamp(start).tz_localize("UTC").timestamp())
    period2 = int((pd.Timestamp(end) + pd.Timedelta(days=1)).tz_localize("UTC").timestamp())
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
            resp = _http_get(url, params=params, timeout=20, headers=HTTP_HEADERS)
            resp.raise_for_status()
            payload = resp.json()["chart"]["result"][0]
            timestamps = payload.get("timestamp") or []
            adj_list = payload["indicators"].get("adjclose") or []
            values = adj_list[0].get("adjclose") if adj_list else None
            if not values:
                raise RuntimeError(f"Yahoo adjusted close missing or empty for {ticker}")
            index = pd.to_datetime(timestamps, unit="s", utc=True).tz_convert(None).normalize()
            series = pd.Series(values, index=index, name=ticker, dtype="float64").dropna().sort_index()
            series = series[~series.index.duplicated(keep="last")]
            if not series.empty:
                return series
        except Exception as exc:
            last_error = exc
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"Yahoo chart fetch failed for {ticker}: {last_error}")


def _fetch_akshare_index_close_fallback(
    secid: str,
    beg: str,
    end: str,
    name: str,
) -> pd.Series:
    if not _HAS_AKSHARE:
        raise RuntimeError("akshare is not installed")
    symbol_by_secid = {"0.399006": "sz399006"}
    symbol = symbol_by_secid.get(secid)
    if symbol is None:
        raise RuntimeError(f"no akshare fallback symbol for {secid}")
    df = ak.stock_zh_index_daily(symbol=symbol)
    if df is None or df.empty:
        raise RuntimeError(f"akshare stock_zh_index_daily returned empty data for {symbol}")
    if "date" not in df.columns or "close" not in df.columns:
        raise RuntimeError(f"akshare stock_zh_index_daily missing date/close columns for {symbol}")
    out = pd.Series(
        pd.to_numeric(df["close"], errors="coerce").to_numpy(),
        index=pd.to_datetime(df["date"]),
        name=name,
    ).dropna().sort_index()
    out = out[(out.index >= pd.Timestamp(beg)) & (out.index <= pd.Timestamp(end))]
    out = out[~out.index.duplicated(keep="last")]
    if out.empty:
        raise RuntimeError(f"akshare stock_zh_index_daily returned no rows in {beg}~{end} for {symbol}")
    out.attrs["source_name"] = "akshare.stock_zh_index_daily"
    out.attrs["source_detail"] = f"symbol={symbol}; no pre-2010 backfill"
    return out


def _fetch_cnfin_index_close_fallback(
    secid: str,
    beg: str,
    end: str,
    name: str,
) -> pd.Series:
    prod_code_by_secid = {"0.399006": "399006.SZ"}
    prod_code = prod_code_by_secid.get(secid)
    if prod_code is None:
        raise RuntimeError(f"no CNFin fallback symbol for {secid}")
    url = "https://quotedata.cnfin.com/quote/v1/kline"
    required_start = pd.Timestamp(beg).normalize()
    current_end = pd.Timestamp(end).normalize()
    rows: list[list[object]] = []
    last_error = None
    for _page in range(10):
        page_rows = None
        params = {
            "prod_code": prod_code,
            "candle_period": "6",
            "get_type": "range",
            "start_date": required_start.strftime("%Y%m%d"),
            "end_date": current_end.strftime("%Y%m%d"),
            "fields": "open_px,high_px,low_px,close_px,business_amount,business_balance",
        }
        for attempt in range(1, 4):
            try:
                resp = _http_get(url, params=params, timeout=30, headers=HTTP_HEADERS)
                resp.raise_for_status()
                candle = (resp.json().get("data") or {}).get("candle") or {}
                page_rows = candle.get(prod_code) or []
                if page_rows:
                    break
            except Exception as exc:
                last_error = exc
            time.sleep(0.5 * attempt)
        if not page_rows:
            if not rows:
                raise RuntimeError(f"CNFin index kline returned no data for {prod_code}; last_error={last_error}")
            break
        rows = page_rows + rows
        first_date = pd.Timestamp(str(page_rows[0][0])).normalize()
        if len(page_rows) < 2001 or first_date <= required_start:
            break
        current_end = first_date - pd.Timedelta(days=1)
        if current_end < required_start:
            break
        time.sleep(0.2)
    frame = pd.DataFrame(rows)
    if frame.shape[1] < 5:
        raise RuntimeError(f"CNFin index kline missing close field for {prod_code}")
    out = pd.Series(
        pd.to_numeric(frame.iloc[:, 4], errors="coerce").to_numpy(),
        index=pd.to_datetime(frame.iloc[:, 0].astype(str), errors="coerce"),
        name=name,
    ).dropna().sort_index()
    out = out[(out.index >= required_start) & (out.index <= pd.Timestamp(end).normalize())]
    out = out[~out.index.duplicated(keep="last")]
    if out.empty:
        raise RuntimeError(f"CNFin index kline normalized to empty for {prod_code} in {beg}~{end}")
    out.attrs["source_name"] = "CNFin quote kline"
    out.attrs["source_detail"] = f"prod_code={prod_code}; no pre-2010 backfill"
    return out


def _fetch_eastmoney_index_close(secid: str, beg: str, end: str, name: str) -> pd.Series:
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
            resp = _http_get(url, params=params, timeout=20, headers=HTTP_HEADERS)
            resp.raise_for_status()
            data = (resp.json().get("data") or {}).get("klines") or []
            if data:
                frame = pd.DataFrame([item.split(",") for item in data])
                out = pd.Series(
                    frame.iloc[:, 2].astype(float).to_numpy(),
                    index=pd.to_datetime(frame.iloc[:, 0]),
                    name=name,
                ).sort_index()
                out.attrs["source_name"] = "Eastmoney push2his kline"
                out.attrs["source_detail"] = f"secid={secid}; no pre-2010 backfill"
                return out
        except Exception as exc:
            last_error = exc
            time.sleep(1.5 * attempt)
    fallback_errors: list[str] = []
    try:
        return _fetch_akshare_index_close_fallback(secid, beg, end, name)
    except Exception as fallback_exc:
        fallback_errors.append(f"akshare fallback failed: {fallback_exc}")
    try:
        return _fetch_cnfin_index_close_fallback(secid, beg, end, name)
    except Exception as fallback_exc:
        fallback_errors.append(f"CNFin fallback failed: {fallback_exc}")
        raise RuntimeError(
            f"Eastmoney index fetch failed for {secid}: {last_error}; "
            + "; ".join(fallback_errors)
        )


def _align_dynamic_proxy_prices(
    raw_prices: pd.DataFrame,
    calendar: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, pd.Timestamp, dict[str, pd.Timestamp]]:
    raw = raw_prices.copy()
    raw.index = pd.DatetimeIndex(raw.index).normalize()
    raw = raw.reindex(calendar)
    aligned = pd.DataFrame(index=calendar)
    last_by_asset: dict[str, pd.Timestamp] = {}
    for code in ASSETS:
        series = pd.to_numeric(raw[code], errors="coerce") if code in raw else pd.Series(index=calendar, dtype=float)
        finite = series.notna() & np.isfinite(series.to_numpy(dtype=float)) & (series > 0)
        if series.notna().any() and not finite[series.notna()].all():
            first_bad = series.index[series.notna() & ~finite][0]
            raise ValueError(f"{code} has non-finite or non-positive close at {pd.Timestamp(first_bad).date()}")
        valid = series.dropna()
        if valid.empty:
            aligned[code] = np.nan
            last_by_asset[code] = pd.NaT
            continue
        filled = series.ffill()
        filled.loc[filled.index < valid.index.min()] = np.nan
        aligned[code] = filled
        last_by_asset[code] = pd.Timestamp(valid.index.max())

    core_valid = aligned[list(CORE_ASSETS)].notna().all(axis=1)
    if not core_valid.any():
        raise RuntimeError("No date has all core proxy assets available")
    start = pd.Timestamp(aligned.index[core_valid][0])
    common_last = min(pd.Timestamp(last_by_asset[code]) for code in CORE_ASSETS)
    aligned = aligned.loc[start:common_last].copy()
    return aligned, common_last, last_by_asset


def _proxy_source_record(
    code: str,
    source: str,
    adjustment: str,
    series: pd.Series,
    source_detail: str,
    first_used: pd.Timestamp,
) -> dict[str, object]:
    clean = series.dropna()
    return {
        "code": code,
        "name": ASSETS[code],
        "source": source,
        "adjustment": adjustment,
        "source_detail": source_detail,
        "first_date": clean.index.min().date().isoformat(),
        "last_date": clean.index.max().date().isoformat(),
        "first_used": pd.Timestamp(first_used).date().isoformat(),
        "rows": int(clean.shape[0]),
    }


def load_close(config: RunConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    lookback_start = config.start_date - pd.Timedelta(days=60)
    calendar = _expected_cn_trading_days(config.start_date, config.end_date)
    if calendar is None or calendar.empty:
        raise RuntimeError("A-share trading calendar / 交易日历不可用，禁止加载正式行情")
    raw_series: dict[str, pd.Series] = {}
    sources: list[dict[str, object]] = []

    for ticker in CORE_ASSETS:
        raw = _fetch_yahoo_adj_close(ticker, lookback_start, config.end_date)
        raw_series[ticker] = raw
        used = raw.loc[raw.index >= config.start_date].dropna()
        sources.append(
            _proxy_source_record(
                ticker,
                "Yahoo Finance chart API",
                ADJUSTMENT_TOTAL_RETURN,
                raw,
                "adjusted close",
                used.index.min(),
            )
        )

    cyb_start = DYNAMIC_ASSETS["CN_CYB_399006"]
    cyb = _fetch_eastmoney_index_close(
        "0.399006",
        cyb_start.strftime("%Y%m%d"),
        config.end_date.strftime("%Y%m%d"),
        "CN_CYB_399006",
    )
    cyb = cyb.loc[cyb.index >= cyb_start]
    raw_series["CN_CYB_399006"] = cyb
    sources.append(
        _proxy_source_record(
            "CN_CYB_399006",
            str(cyb.attrs.get("source_name") or "Eastmoney push2his kline"),
            "index close / price index",
            cyb,
            str(cyb.attrs.get("source_detail") or "secid=0.399006; no pre-2010 backfill"),
            cyb.index.min(),
        )
    )

    for ticker, first_used in DYNAMIC_YAHOO_ASSETS.items():
        raw = _fetch_yahoo_adj_close(ticker, lookback_start, config.end_date)
        raw = raw.loc[raw.index >= first_used]
        raw_series[ticker] = raw
        used = raw.loc[raw.index >= first_used].dropna()
        sources.append(
            _proxy_source_record(
                ticker,
                "Yahoo Finance chart API",
                ADJUSTMENT_TOTAL_RETURN,
                raw,
                "adjusted close; dynamic asset joins from own first usable date",
                used.index.min(),
            )
        )

    for code, first_used in DYNAMIC_CN_ETF_ASSETS.items():
        try:
            cn_prices, cn_sources = _load_public_close_with_per_code_fallback([code], config.end_date)
            close = cn_prices[code].loc[cn_prices[code].index >= first_used]
            raw_series[code] = close
            for row in cn_sources.to_dict(orient="records"):
                row = dict(row)
                row["source_detail"] = (
                    str(row.get("source_detail") or "")
                    + "; dynamic asset joins from own first usable date"
                ).strip("; ")
                sources.append(row)
        except Exception as exc:
            raise RuntimeError(
                f"{code} qfq history unavailable; raw/unadjusted fallback is diagnostic-only: {exc}"
            ) from exc

    raw_prices = pd.concat(raw_series.values(), axis=1).sort_index()
    raw_unfilled_prices = raw_prices.reindex(calendar)
    aligned, _common_last, last_by_asset = _align_dynamic_proxy_prices(raw_prices, calendar)
    aligned.attrs["raw_unfilled_prices"] = raw_unfilled_prices.reindex(aligned.index).copy()
    source_frame = pd.DataFrame(sources)
    source_frame["last_aligned"] = source_frame["code"].map(
        lambda code: last_by_asset[code].date().isoformat() if pd.notna(last_by_asset[code]) else ""
    )
    return aligned, source_frame


def _apply_live_quotes_to_prices(
    prices: pd.DataFrame,
    quotes: pd.DataFrame,
    now: datetime | None = None,
) -> tuple[pd.DataFrame, dict[str, dict[str, object]]]:
    out = prices.copy()
    metadata: dict[str, dict[str, object]] = {}
    if quotes is None or quotes.empty:
        return out, metadata
    ts = _as_bj_datetime(now)
    today = pd.Timestamp(ts.date()).normalize()
    normalized = _normalize_live_quote_frame(
        quotes,
        list(ASSETS),
        require_today=True,
        expected_quote_date=today,
    )
    _validate_live_quote_prices_against_history(prices, normalized, today)
    new_row = {str(row.code): float(row.price) for row in normalized.itertuples(index=False)}
    for row in normalized.itertuples(index=False):
        code = str(row.code)
        quote_ts = _parse_quote_time(getattr(row, "quote_time", None))
        source = str(getattr(row, "source", "") or "live quote")
        metadata[code] = {
            "quote_price": float(row.price),
            "quote_time": _format_quote_time(quote_ts),
            "quote_date": pd.Timestamp(quote_ts.date()).normalize(),
            "quote_source": source,
            "source_execution_eligible": bool(getattr(row, "source_execution_eligible", False)),
            "quote_prev_close": _optional_positive_float(getattr(row, "prev_close", math.nan)),
            "quote_limit_down": _optional_positive_float(getattr(row, "limit_down", math.nan)),
            "quote_limit_up": _optional_positive_float(getattr(row, "limit_up", math.nan)),
            "quote_volume": _optional_nonnegative_float(getattr(row, "volume", math.nan)),
            "quote_amount": _optional_nonnegative_float(getattr(row, "amount", math.nan)),
        }
    if today not in out.index:
        out.loc[today, list(ASSETS)] = np.nan
    out.loc[today, list(ASSETS)] = [new_row[code] for code in ASSETS]
    return out.sort_index(), metadata


def _attach_signal_prices(daily: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    out = daily.copy()
    price_lookup = prices.copy()
    price_lookup.index = pd.DatetimeIndex(price_lookup.index).normalize()
    dates = pd.to_datetime(out["date"]).dt.normalize()
    for code in ASSETS:
        if code in price_lookup.columns:
            mapper = price_lookup[code].to_dict()
            out[f"signal_price_{code}"] = dates.map(mapper)
    return out


def _price_forward_fill_flags(
    raw_prices: pd.DataFrame,
    aligned_prices: pd.DataFrame,
    asset_cols: list[str] | tuple[str, ...],
) -> pd.DataFrame:
    asset_cols = list(asset_cols)
    raw = raw_prices.copy()
    raw.index = pd.DatetimeIndex(raw.index).normalize()
    aligned = aligned_prices.copy()
    aligned.index = pd.DatetimeIndex(aligned.index).normalize()
    raw = raw.reindex(aligned.index)
    flags = pd.DataFrame(False, index=aligned.index, columns=asset_cols)
    for code in asset_cols:
        flags[code] = aligned[code].notna() & raw[code].isna()
    return flags


def _validate_price_ffill_flags(
    prices: pd.DataFrame,
    price_ffill_flags: pd.DataFrame | None,
) -> pd.DataFrame:
    price_index = pd.DatetimeIndex(prices.index).normalize()
    if not price_index.is_unique:
        raise ValueError("price ffill mask requires a normalized unique prices index")
    if price_ffill_flags is None:
        return pd.DataFrame(False, index=price_index, columns=list(ASSETS), dtype=bool)
    if not isinstance(price_ffill_flags, pd.DataFrame):
        raise ValueError("price ffill mask must be a DataFrame")
    flags = price_ffill_flags.copy()
    try:
        raw_flag_index = pd.DatetimeIndex(flags.index)
    except Exception as exc:
        raise ValueError("price ffill mask index must contain valid dates") from exc
    if not raw_flag_index.equals(raw_flag_index.normalize()):
        raise ValueError("price ffill mask index must contain normalized midnight dates")
    flags.index = raw_flag_index
    if not flags.index.is_unique:
        raise ValueError("price ffill mask index must be normalized and unique")
    if flags.columns.has_duplicates:
        raise ValueError("price ffill mask asset columns must be unique")
    missing_assets = [code for code in ASSETS if code not in flags.columns]
    if missing_assets:
        raise ValueError(f"price ffill mask is missing asset columns: {missing_assets}")
    if set(flags.index) != set(price_index) or len(flags.index) != len(price_index):
        raise ValueError("price ffill mask must exactly cover the prices index")
    selected = flags.loc[:, list(ASSETS)]
    if selected.isna().any().any():
        raise ValueError("price ffill mask must not contain NA values")
    bad_dtypes = [code for code in ASSETS if not pd.api.types.is_bool_dtype(selected[code].dtype)]
    if bad_dtypes:
        raise ValueError(f"price ffill mask columns must have boolean dtype: {bad_dtypes}")
    return selected.reindex(price_index).astype(bool)


def _sync_live_quote_raw_availability(
    raw_prices: pd.DataFrame,
    updated_prices: pd.DataFrame,
    live_quote_metadata: dict[str, dict[str, object]],
) -> pd.DataFrame:
    raw = raw_prices.copy()
    raw.index = pd.DatetimeIndex(raw.index).normalize()
    updated = updated_prices.copy()
    updated.index = pd.DatetimeIndex(updated.index).normalize()
    for code, metadata in live_quote_metadata.items():
        if code not in ASSETS or code not in updated.columns:
            continue
        quote_date = metadata.get("quote_date")
        quote_price = metadata.get("quote_price")
        if quote_date is None or quote_price is None:
            continue
        date = pd.Timestamp(quote_date).normalize()
        if date not in updated.index or pd.isna(updated.at[date, code]):
            continue
        if date not in raw.index:
            raw.loc[date, list(ASSETS)] = np.nan
        raw.at[date, code] = float(updated.at[date, code])
    return raw.sort_index()


def _attach_price_fill_metadata(daily: pd.DataFrame, price_ffill_flags: pd.DataFrame) -> pd.DataFrame:
    out = daily.copy()
    if out.empty or "date" not in out.columns:
        return out
    flags = price_ffill_flags.copy()
    flags.index = pd.DatetimeIndex(flags.index).normalize()
    dates = pd.to_datetime(out["date"]).dt.normalize()
    for code in ASSETS:
        values = [
            bool(flags.at[date, code]) if date in flags.index and code in flags.columns else False
            for date in dates
        ]
        out[f"price_ffill_{code}"] = pd.Series(values, index=out.index, dtype=object)
    return out


def _attach_live_quote_metadata(
    daily: pd.DataFrame,
    live_quote_metadata: dict[str, dict[str, object]],
) -> pd.DataFrame:
    out = daily.copy()
    if not live_quote_metadata or out.empty:
        return out
    dates = pd.to_datetime(out["date"]).dt.normalize()
    for code, metadata in live_quote_metadata.items():
        quote_date = metadata.get("quote_date")
        if quote_date is None:
            continue
        mask = dates == pd.Timestamp(quote_date).normalize()
        if not mask.any():
            continue
        out.loc[mask, f"quote_price_{code}"] = metadata.get("quote_price")
        out.loc[mask, f"quote_time_{code}"] = metadata.get("quote_time")
        out.loc[mask, f"quote_source_{code}"] = metadata.get("quote_source")
        out.loc[mask, f"source_execution_eligible_{code}"] = metadata.get("source_execution_eligible")
        out.loc[mask, f"quote_prev_close_{code}"] = metadata.get("quote_prev_close")
        out.loc[mask, f"quote_limit_down_{code}"] = metadata.get("quote_limit_down")
        out.loc[mask, f"quote_limit_up_{code}"] = metadata.get("quote_limit_up")
        out.loc[mask, f"quote_volume_{code}"] = metadata.get("quote_volume")
        out.loc[mask, f"quote_amount_{code}"] = metadata.get("quote_amount")
    return out


def _official_close_timestamp_for_date(date_value: object) -> pd.Timestamp:
    day = pd.Timestamp(date_value).normalize()
    return pd.Timestamp(
        datetime(
            day.year,
            day.month,
            day.day,
            OFFICIAL_CLOSE_TIME.hour,
            OFFICIAL_CLOSE_TIME.minute,
            OFFICIAL_CLOSE_TIME.second,
            tzinfo=CN_TZ,
        )
    )


def _attach_confirmed_final_close_metadata(
    daily: pd.DataFrame,
    last_by_asset: dict[str, pd.Timestamp] | None = None,
    now: datetime | None = None,
) -> pd.DataFrame:
    out = daily.copy()
    if out.empty or "date" not in out.columns:
        return out
    ts = _as_bj_datetime(now)
    if ts.time() < CONFIRMED_CLOSE_CUTOFF:
        return out
    today = pd.Timestamp(ts.date()).normalize()
    dates = pd.to_datetime(out["date"]).dt.normalize()
    mask = dates == today
    if not mask.any():
        return out
    final_ts = _official_close_timestamp_for_date(today)
    final_time = _format_quote_time(final_ts)
    for code in ASSETS:
        last_date = None if last_by_asset is None else last_by_asset.get(code)
        if last_date is None or pd.isna(last_date) or pd.Timestamp(last_date).normalize() != today:
            continue
        signal_col = f"signal_price_{code}"
        if signal_col not in out.columns:
            return out
        signal_prices = pd.to_numeric(out.loc[mask, signal_col], errors="coerce")
        if signal_prices.isna().any():
            return out
    for code in ASSETS:
        last_date = None if last_by_asset is None else last_by_asset.get(code)
        if last_date is None or pd.isna(last_date) or pd.Timestamp(last_date).normalize() != today:
            out.loc[mask, f"bar_final_{code}"] = False
            continue
        signal_col = f"signal_price_{code}"
        out.loc[mask, f"final_price_{code}"] = pd.to_numeric(out.loc[mask, signal_col], errors="coerce")
        out.loc[mask, f"final_time_{code}"] = final_time
        out.loc[mask, f"bar_final_{code}"] = True
        out.loc[mask, f"final_close_source_{code}"] = "historical_daily_bar"
        out.loc[mask, f"final_close_execution_verified_{code}"] = False
    all_final = True
    for code in ASSETS:
        all_final = all_final and _explicit_bool_value(out.loc[mask, f"bar_final_{code}"].iloc[0], False)
    out.loc[mask, "source_bar_is_final"] = all_final
    out.loc[mask, "source_final_close_execution_verified"] = False
    if all_final:
        out.loc[mask, "source_quote_time"] = final_time
    return out


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
    annual_log_return = float(slope) * TRADING_DAYS
    if not math.isfinite(annual_log_return) or annual_log_return > math.log(sys.float_info.max):
        return math.nan, r2
    score = math.exp(annual_log_return) - 1.0
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
    values = nav.astype(float)
    peak = values.cummax()
    return float((values / peak - 1.0).min())


# ════════════════════════════════════════════════════════════════
#  V1.3 Strategy Engine — staged entry
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


def _require_valid_close(value: object, code: str, date: object, role: str) -> float:
    try:
        result = float(value)
    except Exception as exc:
        raise RuntimeError(f"missing close for held asset {code} on {pd.Timestamp(date).date()} ({role})") from exc
    if not math.isfinite(result) or result <= 0:
        raise RuntimeError(f"missing close for held asset {code} on {pd.Timestamp(date).date()} ({role})")
    return result


def _backtest_stale_price_trade_assets(
    flags: pd.DataFrame,
    date: pd.Timestamp,
    old_holding: str,
    old_fraction: float,
    trade_target: str,
    trade_fraction: float,
) -> list[str]:
    assets: list[str] = []
    eps = 1e-12
    if old_holding == trade_target:
        if abs(float(trade_fraction) - float(old_fraction)) > eps and old_holding in ASSETS:
            assets.append(old_holding)
    else:
        if old_holding in ASSETS and old_fraction > eps:
            assets.append(old_holding)
        if trade_target in ASSETS and trade_fraction > eps:
            assets.append(trade_target)
    normalized = pd.Timestamp(date).normalize()
    return [
        code
        for code in assets
        if code in flags.columns and normalized in flags.index and bool(flags.at[normalized, code])
    ]


def run_staged_entry(
    prices: pd.DataFrame,
    config: RunConfig,
    case: EntryCase,
    r2_threshold: float,
    switch_buffer: float,
    price_ffill_flags: pd.DataFrame | None = None,
) -> pd.DataFrame:
    prices = prices.loc[:config.end_date].copy()
    price_ffill_flags = _validate_price_ffill_flags(prices, price_ffill_flags)
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
        old_pending_entry_target = pending_entry_target
        old_pending_entry_since = pending_entry_since
        old_pending_entry_days = pending_entry_days
        old_staged_initial_count = staged_initial_count
        old_staged_fill_count = staged_fill_count

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

        stale_trade_assets: list[str] = []
        trade_blocked_by_stale_price = False
        blocked_trade_target = None  # type: Optional[str]
        if trade_target is not None:
            stale_trade_assets = _backtest_stale_price_trade_assets(
                price_ffill_flags,
                date,
                old_holding,
                old_fraction,
                trade_target,
                trade_fraction,
            )
            if stale_trade_assets:
                trade_blocked_by_stale_price = True
                blocked_trade_target = trade_target
                trade_target = None
                trade_fraction = old_fraction
                pending_entry_target = old_pending_entry_target
                pending_entry_since = old_pending_entry_since
                pending_entry_days = old_pending_entry_days
                staged_initial_count = old_staged_initial_count
                staged_fill_count = old_staged_fill_count
                staged_initial = False
                fill_on_down_day = False

        # --- daily return ---
        if old_holding == "CASH" or old_fraction <= 1e-12 or idx == 0:
            asset_return = 0.0
            asset_component = 0.0
        else:
            prev_px = prices.iloc[idx - 1].get(old_holding, np.nan)
            cur_px = prices.iloc[idx].get(old_holding, np.nan)
            prev_px = _require_valid_close(prev_px, old_holding, prices.index[idx - 1], "previous")
            cur_px = _require_valid_close(cur_px, old_holding, date, "current")
            asset_return = float(cur_px / prev_px - 1.0)
            asset_component = old_fraction * asset_return
        cash_exposure = max(0.0, 1.0 - float(old_fraction if old_holding != "CASH" else 0.0))
        cash_return_component = cash_exposure * CASH_DAILY_RETURN
        gross_return = asset_component + cash_return_component

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
        asset_return_row: dict[str, float] = {}
        for code in ASSETS:
            if idx == 0:
                code_return = 0.0
            else:
                previous = pd.to_numeric(prices.iloc[idx - 1].get(code, np.nan), errors="coerce")
                current = pd.to_numeric(prices.iloc[idx].get(code, np.nan), errors="coerce")
                code_return = (
                    float(current / previous - 1.0)
                    if pd.notna(previous) and pd.notna(current) and float(previous) > 0 and float(current) > 0
                    else math.nan
                )
            asset_return_row[f"asset_return_{code}"] = code_return
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
            "trade_blocked_by_stale_price": trade_blocked_by_stale_price,
            "blocked_trade_target": blocked_trade_target,
            "stale_price_trade_assets": ",".join(stale_trade_assets),
            "best_candidate": best_candidate,
            "best_candidate_score": best_score,
            "current_score": current_score,
            "buffer_blocked": buffer_blocked,
            "asset_return": asset_return,
            **asset_return_row,
            "gross_return": gross_return,
            "asset_component": asset_component,
            "cash_return_component": cash_return_component,
            "cash_exposure_effective": cash_exposure,
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


_CN_TRADING_DAY_CACHE: pd.DatetimeIndex | None = None
_CN_TRADING_DAY_CACHE_COVERAGE_END: pd.Timestamp | None = None
_CN_TRADING_DAY_CACHE_QUERIED_START: pd.Timestamp | None = None
_CN_TRADING_DAY_CACHE_QUERIED_END: pd.Timestamp | None = None
CNFIN_CALENDAR_SOURCE = "CNFin 000001.SS kline"
# SSE notice [2025] No. 45, published 2025-12-22; SZSE uses the same mainland closures.
# https://www.sse.com.cn/disclosure/announcement/general/c/c_20251222_10802507.shtml
OFFICIAL_CN_CALENDAR_2026_START = pd.Timestamp("2026-01-01")
OFFICIAL_CN_CALENDAR_2026_END = pd.Timestamp("2026-12-31")
OFFICIAL_CN_CALENDAR_2026_CLOSED_DATES = pd.DatetimeIndex(
    pd.to_datetime(
        [
            "2026-01-01",
            "2026-01-02",
            "2026-02-16",
            "2026-02-17",
            "2026-02-18",
            "2026-02-19",
            "2026-02-20",
            "2026-02-23",
            "2026-04-06",
            "2026-05-01",
            "2026-05-04",
            "2026-05-05",
            "2026-06-19",
            "2026-09-25",
            "2026-10-01",
            "2026-10-02",
            "2026-10-05",
            "2026-10-06",
            "2026-10-07",
        ]
    )
)
_CN_TRADING_DAY_FAILURE_REASON_VAR: ContextVar[str] = ContextVar(
    "_CN_TRADING_DAY_FAILURE_REASON",
    default="",
)


def _normalize_trading_calendar(raw: pd.DataFrame) -> pd.DatetimeIndex:
    if raw.empty:
        return pd.DatetimeIndex([])
    date_col = "trade_date" if "trade_date" in raw.columns else raw.columns[0]
    dates = pd.to_datetime(raw[date_col], errors="coerce")
    dates = pd.DatetimeIndex(pd.Series(dates).dropna()).normalize().unique().sort_values()
    return pd.DatetimeIndex(dates)


def _single_calendar_metadata_value(raw: pd.DataFrame, column: str) -> object | None:
    if column not in raw.columns:
        return None
    values = raw[column].dropna()
    values = values[values.astype(str).str.strip() != ""]
    if values.empty:
        return None
    if column in {
        "coverage_end",
        "generated_at",
        "first_trade_date",
        "last_trade_date",
        "queried_start",
        "queried_end",
    }:
        parsed = pd.to_datetime(values, errors="coerce")
        parsed = pd.Series(parsed).dropna()
        if parsed.empty:
            return None
        normalized = pd.DatetimeIndex(parsed).normalize().unique().sort_values()
        if len(normalized) > 1:
            raise RuntimeError(f"交易日历缓存元数据不一致: {column}")
        return pd.Timestamp(normalized[0]).normalize()
    unique = pd.Index(values.astype(str).str.strip().unique())
    if len(unique) > 1:
        raise RuntimeError(f"交易日历缓存元数据不一致: {column}")
    return str(unique[0])


def _calendar_cache_coverage_end(raw: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.Timestamp | None:
    if len(calendar) == 0:
        return None
    calendar_last = pd.Timestamp(calendar.max()).normalize()
    coverage_end = _single_calendar_metadata_value(raw, "coverage_end")
    if coverage_end is not None:
        coverage_end = pd.Timestamp(coverage_end).normalize()
        if coverage_end != calendar_last:
            raise RuntimeError(
                "交易日历缓存元数据不一致: "
                f"coverage_end={coverage_end.date().isoformat()}，"
                f"calendar.max={calendar_last.date().isoformat()}"
            )
        return coverage_end
    return calendar_last


def _calendar_is_usable(
    calendar: pd.DatetimeIndex | None,
    required_start: pd.Timestamp,
    required_end: pd.Timestamp,
    coverage_end: pd.Timestamp | None = None,
    queried_start: pd.Timestamp | None = None,
    queried_end: pd.Timestamp | None = None,
) -> bool:
    if calendar is None or len(calendar) == 0:
        return False
    calendar = pd.DatetimeIndex(calendar).normalize().unique().sort_values()
    required_start = pd.Timestamp(required_start).normalize()
    required_end = pd.Timestamp(required_end).normalize()
    first_session = pd.Timestamp(calendar.min()).normalize()
    calendar_last = pd.Timestamp(calendar.max()).normalize()
    if coverage_end is not None and pd.Timestamp(coverage_end).normalize() != calendar_last:
        return False
    normalized_queried_start = (
        pd.Timestamp(queried_start).normalize() if queried_start is not None else None
    )
    normalized_queried_end = pd.Timestamp(queried_end).normalize() if queried_end is not None else None
    if normalized_queried_start is not None and normalized_queried_start > first_session:
        return False
    if normalized_queried_end is not None and normalized_queried_end < calendar_last:
        return False
    if (
        normalized_queried_start is not None
        and normalized_queried_end is not None
        and normalized_queried_start > normalized_queried_end
    ):
        return False
    if first_session > required_start and (
        normalized_queried_start is None or normalized_queried_start > required_start
    ):
        return False
    if calendar_last < required_end and (
        normalized_queried_end is None or normalized_queried_end < required_end
    ):
        return False
    return True


def _load_cached_cn_trading_days() -> tuple[
    pd.DatetimeIndex,
    pd.Timestamp | None,
    pd.Timestamp | None,
    pd.Timestamp | None,
] | None:
    path = Path(TRADING_CALENDAR_CACHE_PATH)
    if not path.exists():
        return None
    raw = pd.read_csv(path)
    for column in (
        "coverage_end",
        "generated_at",
        "first_trade_date",
        "last_trade_date",
        "queried_start",
        "queried_end",
        "source",
    ):
        _single_calendar_metadata_value(raw, column)
    calendar = _normalize_trading_calendar(raw)
    if len(calendar) == 0:
        raise RuntimeError("本地交易日历缓存为空")
    first_meta = _single_calendar_metadata_value(raw, "first_trade_date")
    if first_meta is not None and pd.Timestamp(first_meta).normalize() != pd.Timestamp(calendar.min()).normalize():
        raise RuntimeError("交易日历缓存元数据不一致: first_trade_date")
    last_meta = _single_calendar_metadata_value(raw, "last_trade_date")
    if last_meta is not None and pd.Timestamp(last_meta).normalize() != pd.Timestamp(calendar.max()).normalize():
        raise RuntimeError("交易日历缓存元数据不一致: last_trade_date")
    source = _single_calendar_metadata_value(raw, "source")
    is_cnfin_cache = source == CNFIN_CALENDAR_SOURCE
    return (
        calendar,
        _calendar_cache_coverage_end(raw, calendar),
        _single_calendar_metadata_value(raw, "queried_start") if is_cnfin_cache else None,
        _single_calendar_metadata_value(raw, "queried_end") if is_cnfin_cache else None,
    )


def _load_cnfin_trading_calendar(
    required_start: pd.Timestamp,
    required_end: pd.Timestamp,
) -> tuple[pd.DatetimeIndex, pd.Timestamp | None, pd.Timestamp, pd.Timestamp]:
    url = "https://quotedata.cnfin.com/quote/v1/kline"
    code = "000001.SS"
    required_start = pd.Timestamp(required_start).normalize()
    required_end = pd.Timestamp(required_end).normalize()
    current_end = required_end
    rows: list[list[object]] = []
    last_error = None
    for _page in range(10):
        page_rows = None
        page_request_completed = False
        params = {
            "prod_code": code,
            "candle_period": "6",
            "get_type": "range",
            "start_date": required_start.strftime("%Y%m%d"),
            "end_date": current_end.strftime("%Y%m%d"),
            "fields": "open_px,high_px,low_px,close_px,business_amount,business_balance",
        }
        for attempt in range(1, 4):
            try:
                resp = _http_get(url, params=params, timeout=30, headers=HTTP_HEADERS)
                resp.raise_for_status()
                candle = (resp.json().get("data") or {}).get("candle") or {}
                page_rows = candle.get(code) or []
                page_request_completed = True
                break
            except Exception as exc:
                last_error = exc
            time.sleep(0.5 * attempt)
        if not page_request_completed:
            if rows:
                raise RuntimeError(
                    "CNFin trading calendar provider failure left partial calendar coverage; "
                    f"last_error={last_error}"
                ) from last_error
            raise RuntimeError(f"CNFin trading calendar returned no data; last_error={last_error}")
        if not page_rows:
            if not rows:
                raise RuntimeError(f"CNFin trading calendar returned no data; last_error={last_error}")
            break
        rows = page_rows + rows
        first_date = pd.Timestamp(str(page_rows[0][0])).normalize()
        if len(page_rows) < 2001 or first_date <= required_start:
            break
        current_end = first_date - pd.Timedelta(days=1)
        if current_end < required_start:
            break
        time.sleep(0.2)
    calendar = pd.DatetimeIndex(
        pd.to_datetime([str(row[0]) for row in rows], errors="coerce")
    ).dropna().normalize().unique().sort_values()
    if len(calendar) == 0:
        raise RuntimeError("CNFin trading calendar normalized to empty")
    return (
        pd.DatetimeIndex(calendar),
        pd.Timestamp(calendar.max()).normalize(),
        required_start,
        required_end,
    )


def _write_cached_cn_trading_days(
    calendar: pd.DatetimeIndex,
    source: str = "akshare.tool_trade_date_hist_sina",
    queried_start: pd.Timestamp | None = None,
    queried_end: pd.Timestamp | None = None,
) -> None:
    calendar = pd.DatetimeIndex(calendar).normalize().unique().sort_values()
    if len(calendar) == 0:
        return
    try:
        path = Path(TRADING_CALENDAR_CACHE_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        generated_at = _now_bj().isoformat()
        coverage_end = pd.Timestamp(calendar.max()).normalize()
        cache_data: dict[str, object] = {
                "trade_date": [pd.Timestamp(day).date().isoformat() for day in calendar],
                "generated_at": generated_at,
                "first_trade_date": pd.Timestamp(calendar.min()).date().isoformat(),
                "last_trade_date": pd.Timestamp(calendar.max()).date().isoformat(),
                "coverage_end": coverage_end.date().isoformat(),
                "source": source,
        }
        if queried_start is not None:
            cache_data["queried_start"] = pd.Timestamp(queried_start).date().isoformat()
        if queried_end is not None:
            cache_data["queried_end"] = pd.Timestamp(queried_end).date().isoformat()
        pd.DataFrame(cache_data).to_csv(
            path,
            index=False,
            encoding="utf-8",
        )
    except Exception:
        return


def _set_calendar_failure(reason: str) -> None:
    _CN_TRADING_DAY_FAILURE_REASON_VAR.set(reason)


def _calendar_failure_reason() -> str:
    return _CN_TRADING_DAY_FAILURE_REASON_VAR.get()


def _load_official_cn_trading_calendar_2026(
    required_start: pd.Timestamp,
    required_end: pd.Timestamp,
) -> tuple[pd.DatetimeIndex, pd.Timestamp, pd.Timestamp, pd.Timestamp] | None:
    required_start = pd.Timestamp(required_start).normalize()
    required_end = pd.Timestamp(required_end).normalize()
    if (
        required_start < OFFICIAL_CN_CALENDAR_2026_START
        or required_end > OFFICIAL_CN_CALENDAR_2026_END
    ):
        return None
    calendar = pd.bdate_range(
        OFFICIAL_CN_CALENDAR_2026_START,
        OFFICIAL_CN_CALENDAR_2026_END,
    ).difference(OFFICIAL_CN_CALENDAR_2026_CLOSED_DATES)
    return (
        pd.DatetimeIndex(calendar),
        pd.Timestamp(calendar.max()).normalize(),
        OFFICIAL_CN_CALENDAR_2026_START,
        OFFICIAL_CN_CALENDAR_2026_END,
    )


_CN_TRADING_DAY_CACHE_LOCK = RLock()


def _load_cn_trading_calendar_unlocked(
    required_start: pd.Timestamp,
    required_end: pd.Timestamp,
) -> tuple[
    pd.DatetimeIndex,
    pd.Timestamp | None,
    pd.Timestamp | None,
    pd.Timestamp | None,
] | None:
    global _CN_TRADING_DAY_CACHE, _CN_TRADING_DAY_CACHE_COVERAGE_END
    global _CN_TRADING_DAY_CACHE_QUERIED_START, _CN_TRADING_DAY_CACHE_QUERIED_END
    required_start = pd.Timestamp(required_start).normalize()
    required_end = pd.Timestamp(required_end).normalize()
    _set_calendar_failure("")
    if (
        _CN_TRADING_DAY_CACHE is not None
        and _calendar_is_usable(
            _CN_TRADING_DAY_CACHE,
            required_start,
            required_end,
            _CN_TRADING_DAY_CACHE_COVERAGE_END,
            _CN_TRADING_DAY_CACHE_QUERIED_START,
            _CN_TRADING_DAY_CACHE_QUERIED_END,
        )
    ):
        return (
            _CN_TRADING_DAY_CACHE,
            _CN_TRADING_DAY_CACHE_COVERAGE_END,
            _CN_TRADING_DAY_CACHE_QUERIED_START,
            _CN_TRADING_DAY_CACHE_QUERIED_END,
        )

    _CN_TRADING_DAY_CACHE = None
    _CN_TRADING_DAY_CACHE_COVERAGE_END = None
    _CN_TRADING_DAY_CACHE_QUERIED_START = None
    _CN_TRADING_DAY_CACHE_QUERIED_END = None
    source_errors: list[str] = []
    candidates: list[
        tuple[str, pd.DatetimeIndex, pd.Timestamp | None, pd.Timestamp | None, pd.Timestamp | None]
    ] = []
    if _HAS_AKSHARE:
        try:
            fresh_calendar = _normalize_trading_calendar(ak.tool_trade_date_hist_sina())
            if len(fresh_calendar) == 0:
                raise RuntimeError("AkShare交易日历为空")
            fresh_coverage_end = pd.Timestamp(fresh_calendar.max()).normalize()
            candidates.append(("AkShare", fresh_calendar, fresh_coverage_end, None, None))
        except Exception as exc:
            source_errors.append(str(exc))

    try:
        cached = _load_cached_cn_trading_days()
        if cached is not None:
            cached_calendar, cached_coverage_end, cached_queried_start, cached_queried_end = cached
            candidates.append(
                ("本地缓存", cached_calendar, cached_coverage_end, cached_queried_start, cached_queried_end)
            )
    except Exception as exc:
        source_errors.append(str(exc))

    valid_candidates: list[
        tuple[str, pd.DatetimeIndex, pd.Timestamp | None, pd.Timestamp | None, pd.Timestamp | None]
    ] = []
    for source_name, calendar, coverage_end, queried_start, queried_end in candidates:
        if _calendar_is_usable(
            calendar, required_start, required_end, coverage_end, queried_start, queried_end
        ):
            valid_candidates.append((source_name, calendar, coverage_end, queried_start, queried_end))
        else:
            source_errors.append(
                f"{source_name}交易日历覆盖不足：需要 {required_start.date()} 至 {required_end.date()}，"
                f"实际 {calendar.min().date()} 至 "
                f"{(coverage_end or pd.Timestamp(calendar.max())).date()}"
            )

    if not valid_candidates:
        try:
            cnfin_calendar, cnfin_coverage_end, queried_start, queried_end = (
                _load_cnfin_trading_calendar(required_start, required_end)
            )
            if _calendar_is_usable(
                cnfin_calendar,
                required_start,
                required_end,
                cnfin_coverage_end,
                queried_start,
                queried_end,
            ):
                valid_candidates.append(
                    ("CNFin", cnfin_calendar, cnfin_coverage_end, queried_start, queried_end)
                )
            else:
                source_errors.append(
                    f"CNFin交易日历覆盖不足：需要 {required_start.date()} 至 {required_end.date()}，"
                    f"实际 {cnfin_calendar.min().date()} 至 "
                    f"{(cnfin_coverage_end or pd.Timestamp(cnfin_calendar.max())).date()}"
                )
        except Exception as exc:
            source_errors.append(str(exc))

    if valid_candidates:
        source_name, chosen_calendar, chosen_coverage_end, chosen_queried_start, chosen_queried_end = max(
            valid_candidates,
            key=lambda item: (
                pd.Timestamp(item[1].max()).normalize(),
                pd.Timestamp(item[2] or item[1].max()).normalize(),
            ),
        )
        if source_name in {"AkShare", "CNFin"}:
            _write_cached_cn_trading_days(
                chosen_calendar,
                source=(
                    "akshare.tool_trade_date_hist_sina"
                    if source_name == "AkShare"
                    else CNFIN_CALENDAR_SOURCE
                ),
                queried_start=chosen_queried_start,
                queried_end=chosen_queried_end,
            )
        _CN_TRADING_DAY_CACHE = chosen_calendar
        _CN_TRADING_DAY_CACHE_COVERAGE_END = chosen_coverage_end
        _CN_TRADING_DAY_CACHE_QUERIED_START = chosen_queried_start
        _CN_TRADING_DAY_CACHE_QUERIED_END = chosen_queried_end
        return chosen_calendar, chosen_coverage_end, chosen_queried_start, chosen_queried_end

    if source_errors:
        _set_calendar_failure(
            "交易日历落后于行情数据或当前日期，禁止生成可执行信号；" + " | ".join(source_errors[-3:])
        )
    else:
        _set_calendar_failure("交易日历不可用，禁止生成实盘动作")
    return None


def _load_cn_trading_calendar(
    required_start: pd.Timestamp,
    required_end: pd.Timestamp,
) -> tuple[
    pd.DatetimeIndex,
    pd.Timestamp | None,
    pd.Timestamp | None,
    pd.Timestamp | None,
] | None:
    with _CN_TRADING_DAY_CACHE_LOCK:
        return _load_cn_trading_calendar_unlocked(required_start, required_end)


def _expected_cn_trading_days(start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex | None:
    start = pd.Timestamp(start).normalize()
    end = pd.Timestamp(end).normalize()
    if end < start:
        return pd.DatetimeIndex([])
    loaded = _load_cn_trading_calendar(start, end)
    if loaded is None:
        return None
    calendar, _, _, _ = loaded
    return pd.DatetimeIndex(calendar[(calendar >= start) & (calendar <= end)])


def align_prices_to_common_valid_date(
    prices: pd.DataFrame,
    asset_cols: list[str] | tuple[str, ...],
    calendar_validation_mode: Literal["required", "warning"] = "required",
) -> tuple[pd.DataFrame, pd.Timestamp, dict[str, pd.Timestamp]]:
    if calendar_validation_mode not in {"required", "warning"}:
        raise ValueError(f"Unknown calendar validation mode: {calendar_validation_mode}")
    asset_cols = list(asset_cols)
    missing = [col for col in asset_cols if col not in prices.columns]
    if missing:
        raise ValueError(f"Missing asset columns: {missing}")
    if not prices.index.is_unique:
        duplicates = pd.Index(prices.index[prices.index.duplicated()]).unique()
        first = pd.Timestamp(duplicates[0]).date().isoformat() if len(duplicates) else "unknown"
        raise ValueError(f"Price index must be unique; first duplicate={first}")
    if not prices.index.is_monotonic_increasing:
        raise ValueError("Price index must be strictly increasing")
    aligned_prices = prices.copy()
    rows_with_any_asset_price = prices[asset_cols].notna().any(axis=1)
    last_by_asset: dict[str, pd.Timestamp] = {}
    for col in asset_cols:
        series = pd.to_numeric(aligned_prices[col], errors="coerce")
        finite = np.isfinite(series.to_numpy(dtype=float))
        invalid = series.notna() & (~finite | (series <= 0))
        if invalid.any():
            first_bad = pd.Timestamp(series.index[invalid][0]).date().isoformat()
            raise ValueError(f"{col} has non-finite or non-positive close at {first_bad}")
        valid_dates = aligned_prices.index[series.notna()]
        if len(valid_dates):
            filled = series.ffill()
            aligned_prices.loc[rows_with_any_asset_price, col] = filled.loc[rows_with_any_asset_price]
        last_by_asset[col] = pd.Timestamp(valid_dates.max()) if len(valid_dates) else pd.NaT
    valid_all = aligned_prices[asset_cols].notna().all(axis=1)
    if not valid_all.any():
        raise ValueError("No date has valid close prices for all assets")
    common_last = pd.Timestamp(aligned_prices.index[valid_all].max())
    common_valid_dates = pd.DatetimeIndex(aligned_prices.index[valid_all]).normalize().unique().sort_values()
    first_common = pd.Timestamp(common_valid_dates.min())
    expected_sessions = _expected_cn_trading_days(first_common, common_last)
    if expected_sessions is None:
        reason = _calendar_failure_reason()
        if "交易日历落后于行情数据" in reason or "覆盖不足" in reason:
            raise RuntimeError(reason)
        if calendar_validation_mode == "required":
            raise RuntimeError(reason or "交易日历不可用，无法校验历史行情完整性")
        warnings.warn(
            reason or "交易日历不可用，未校验历史行情完整性",
            RuntimeWarning,
            stacklevel=2,
        )
    elif len(expected_sessions):
        expected_sessions = pd.DatetimeIndex(expected_sessions).normalize().unique().sort_values()
        missing_common = pd.DatetimeIndex(expected_sessions).difference(common_valid_dates)
        if len(missing_common):
            sample = ", ".join(pd.Timestamp(day).date().isoformat() for day in missing_common[:5])
            more = "..." if len(missing_common) > 5 else ""
            raise ValueError(f"Prices are missing common trading dates: {sample}{more}")
        unexpected_common = common_valid_dates.difference(expected_sessions)
        if len(unexpected_common):
            sample = ", ".join(pd.Timestamp(day).date().isoformat() for day in unexpected_common[:5])
            more = "..." if len(unexpected_common) > 5 else ""
            raise ValueError(f"Prices contain unexpected non-trading dates: {sample}{more}")
    return aligned_prices.loc[:common_last].copy(), common_last, last_by_asset


def _float_series(curve: pd.DataFrame, column: str, default: float) -> pd.Series:
    if column in curve.columns:
        return curve[column].astype(float).fillna(default)
    return pd.Series(default, index=curve.index, dtype=float)


def apply_target_vol_scale_rebalance_threshold(
    raw_next_scale: pd.Series,
    threshold: float = TARGET_VOL_SCALE_REBALANCE_THRESHOLD,
    initial_scale: float = 1.0,
) -> pd.Series:
    raw = raw_next_scale.astype(float)
    confirmed: list[float] = []
    last_confirmed = float(initial_scale)
    for value in raw:
        value = float(value)
        if threshold <= 0 or abs(value - last_confirmed) >= threshold:
            last_confirmed = value
        confirmed.append(last_confirmed)
    return pd.Series(confirmed, index=raw.index, dtype=float)


def _compute_target_vol_scales(
    curve: pd.DataFrame,
    target_vol: float,
    vol_window: int,
    max_lev: float,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    if isinstance(target_vol, (bool, np.bool_)):
        raise ValueError("target_vol must be a finite positive number")
    if isinstance(vol_window, (bool, np.bool_)) or not isinstance(
        vol_window, (int, np.integer)
    ):
        raise ValueError("vol_window must be an integer greater than 1")
    if isinstance(max_lev, (bool, np.bool_)):
        raise ValueError("max_lev must be a finite nonnegative number")

    target_vol = float(target_vol)
    max_lev = float(max_lev)
    vol_window = int(vol_window)
    if not math.isfinite(target_vol) or target_vol <= 0.0:
        raise ValueError("target_vol must be a finite positive number")
    if vol_window <= 1:
        raise ValueError("vol_window must be an integer greater than 1")
    if not math.isfinite(max_lev) or max_lev < 0.0:
        raise ValueError("max_lev must be a finite nonnegative number")

    try:
        base_ret = curve["return"].astype(float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("return values must be finite") from exc
    if not np.isfinite(base_ret.to_numpy()).all():
        raise ValueError("return values must be finite")

    initial_scale = min(1.0, max_lev)
    with np.errstate(over="ignore", invalid="ignore"):
        realized_vol = (
            base_ret.rolling(vol_window, min_periods=vol_window).std(ddof=0)
            * math.sqrt(TRADING_DAYS)
        )
    post_warmup_vol = realized_vol.iloc[vol_window - 1 :]
    if not np.isfinite(post_warmup_vol.to_numpy()).all():
        raise ValueError("realized volatility must be finite after warmup")

    complete_window = realized_vol.notna()
    next_scale = pd.Series(initial_scale, index=curve.index, dtype=float)
    positive_vol = complete_window & realized_vol.gt(0.0)
    zero_vol = complete_window & realized_vol.eq(0.0)
    next_scale.loc[positive_vol] = target_vol / realized_vol.loc[positive_vol]
    next_scale.loc[zero_vol] = max_lev
    next_scale = next_scale.clip(lower=0.0, upper=max_lev)
    next_scale = apply_target_vol_scale_rebalance_threshold(
        next_scale,
        initial_scale=initial_scale,
    )
    effective_scale = next_scale.shift(1, fill_value=initial_scale)
    return realized_vol, effective_scale.astype(float), next_scale.astype(float)


def _recompute_final_exposure_nav(
    curve: pd.DataFrame,
    target_vol_effective: pd.Series,
    target_vol_next: pd.Series,
    overheat_effective: pd.Series,
    overheat_next: pd.Series,
    one_way_cost: float,
    price_ffill_flags: pd.DataFrame | None = None,
) -> pd.DataFrame:
    out = curve.copy()
    ffill_flags = _validate_price_ffill_flags(out, price_ffill_flags)
    if "base_return" not in out.columns:
        out["base_return"] = out["return"].astype(float).fillna(0.0)
    if "base_nav" not in out.columns:
        out["base_nav"] = out["nav"].astype(float)
    if "base_gross_return" not in out.columns:
        out["base_gross_return"] = out["gross_return"].astype(float).fillna(0.0)
    if "base_turnover" not in out.columns:
        out["base_turnover"] = _float_series(out, "turnover", 0.0)
    if "base_cost" not in out.columns:
        out["base_cost"] = _float_series(out, "cost", 0.0)

    position_before = out["position_before"].astype(str)
    position_next = out["position"].astype(str)
    fraction_before = _float_series(out, "fraction_before", 0.0)
    holding_fraction = _float_series(out, "holding_fraction", 0.0)

    target_vol_effective = target_vol_effective.reindex(out.index).astype(float).fillna(1.0)
    target_vol_next = target_vol_next.reindex(out.index).astype(float).fillna(1.0)
    overheat_effective = overheat_effective.reindex(out.index).astype(float).fillna(1.0)
    overheat_next = overheat_next.reindex(out.index).astype(float).fillna(1.0)

    if "asset_return" not in out.columns:
        base_fraction_col = "base_fraction_before" if "base_fraction_before" in out.columns else "fraction_before"
        base_fraction = _float_series(out, base_fraction_col, 0.0)
        base_gross = out["base_gross_return"].astype(float).fillna(0.0)
        out["asset_return"] = pd.Series(
            np.divide(
                base_gross.to_numpy(dtype=float),
                base_fraction.to_numpy(dtype=float),
                out=np.zeros(len(out), dtype=float),
                where=np.abs(base_fraction.to_numpy(dtype=float)) > 1e-12,
            ),
            index=out.index,
            dtype=float,
        )
    asset_return = pd.to_numeric(out["asset_return"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)

    eps = 1e-12
    exposure_effective_vals: list[float] = []
    final_exposure_vals: list[float] = []
    final_exposure_after_overheat_vals: list[float] = []
    drifted_exposure_vals: list[float] = []
    rebalance_delta_vals: list[float] = []
    buy_delta_vals: list[float] = []
    sell_delta_vals: list[float] = []
    turnover_vals: list[float] = []
    cost_vals: list[float] = []
    gross_return_vals: list[float] = []
    net_return_vals: list[float] = []
    actual_position_before_vals: list[str] = []
    actual_position_next_vals: list[str] = []
    stale_blocked_vals: list[bool] = []
    stale_assets_vals: list[str] = []
    carried_position = "CASH"
    carried_exposure = 0.0
    pending_rebalance = False

    for row_number, idx in enumerate(out.index):
        prev_position = str(position_before.loc[idx])
        next_position = str(position_next.loc[idx])
        frac_before = float(fraction_before.loc[idx])
        hold_frac = float(holding_fraction.loc[idx])
        tv_effective = float(target_vol_effective.loc[idx])
        tv_next = float(target_vol_next.loc[idx])
        oh_effective = float(overheat_effective.loc[idx])
        oh_next = float(overheat_next.loc[idx])
        scheduled_exposure = frac_before * tv_effective * oh_effective if prev_position != "CASH" else 0.0
        if row_number == 0:
            actual_prev_position = prev_position if scheduled_exposure > eps else "CASH"
            exposure_before = scheduled_exposure
        else:
            actual_prev_position = carried_position
            exposure_before = carried_exposure if carried_position != "CASH" else 0.0

        if actual_prev_position == "CASH":
            asset_ret = 0.0
        else:
            actual_return_col = f"asset_return_{actual_prev_position}"
            if actual_return_col in out.columns:
                actual_return = pd.to_numeric(pd.Series([out.at[idx, actual_return_col]]), errors="coerce").iloc[0]
                if pd.isna(actual_return) or not math.isfinite(float(actual_return)):
                    raise RuntimeError(
                        f"Missing finite asset return for actual carried position {actual_prev_position} at {idx}"
                    )
                asset_ret = float(actual_return)
            elif actual_prev_position == prev_position:
                asset_ret = float(asset_return.loc[idx])
            else:
                raise RuntimeError(
                    f"Missing asset return for actual carried position {actual_prev_position} at {idx}"
                )

        cash_exposure = max(0.0, 1.0 - exposure_before)
        cash_component = cash_exposure * CASH_DAILY_RETURN
        gross = asset_ret * exposure_before + cash_component
        denominator = 1.0 + gross
        if abs(denominator) <= eps or actual_prev_position == "CASH":
            drifted = 0.0
        else:
            drifted = exposure_before * (1.0 + asset_ret) / denominator
            if not math.isfinite(drifted):
                drifted = 0.0

        desired_final = hold_frac * tv_next if next_position != "CASH" else 0.0
        desired_after_overheat = desired_final * oh_next
        raw_trade_target = out.at[idx, "trade_target"] if "trade_target" in out.columns else None
        has_base_trade = not (
            raw_trade_target is None
            or pd.isna(raw_trade_target)
            or str(raw_trade_target).strip().lower() in {"", "none", "nan", "<na>"}
        )
        position_changed = prev_position != next_position
        fraction_changed = abs(hold_frac - frac_before) > eps
        scale_changed = abs(tv_next - tv_effective) > eps
        overheat_changed = abs(oh_next - oh_effective) > eps
        should_rebalance = (
            has_base_trade
            or position_changed
            or fraction_changed
            or scale_changed
            or overheat_changed
            or pending_rebalance
        )

        if should_rebalance:
            final_after_overheat = desired_after_overheat
            final_before_overheat = desired_final
            rebalance = final_after_overheat - drifted
            same_asset = actual_prev_position == next_position and actual_prev_position != "CASH"
            if same_asset:
                buy = max(rebalance, 0.0)
                sell = max(-rebalance, 0.0)
                day_turnover = abs(rebalance)
            else:
                sell = drifted if actual_prev_position != "CASH" else 0.0
                buy = final_after_overheat if next_position != "CASH" else 0.0
                day_turnover = abs(sell) + abs(buy)
        else:
            final_after_overheat = drifted
            final_before_overheat = final_after_overheat / oh_next if next_position != "CASH" and abs(oh_next) > eps else 0.0
            rebalance = 0.0
            buy = 0.0
            sell = 0.0
            day_turnover = 0.0

        stale_assets: list[str] = []
        if should_rebalance and day_turnover > eps:
            if actual_prev_position == next_position and actual_prev_position in ASSETS:
                stale_assets.append(actual_prev_position)
            else:
                if sell > eps and actual_prev_position in ASSETS:
                    stale_assets.append(actual_prev_position)
                if buy > eps and next_position in ASSETS:
                    stale_assets.append(next_position)
            stale_assets = [
                code for code in dict.fromkeys(stale_assets)
                if bool(ffill_flags.at[pd.Timestamp(idx).normalize(), code])
            ]
        overlay_trade_blocked = bool(stale_assets)
        if overlay_trade_blocked:
            final_after_overheat = drifted
            final_before_overheat = (
                drifted / oh_next if actual_prev_position != "CASH" and abs(oh_next) > eps else 0.0
            )
            rebalance = buy = sell = day_turnover = 0.0
            next_position = actual_prev_position
            pending_rebalance = True
        elif should_rebalance:
            pending_rebalance = False

        day_cost = day_turnover * float(one_way_cost)
        net = (1.0 + gross) * (1.0 - day_cost) - 1.0
        actual_before = actual_prev_position if exposure_before > eps else "CASH"
        actual_next = next_position if final_after_overheat > eps else "CASH"

        exposure_effective_vals.append(exposure_before)
        final_exposure_vals.append(final_before_overheat)
        final_exposure_after_overheat_vals.append(final_after_overheat)
        drifted_exposure_vals.append(drifted)
        rebalance_delta_vals.append(rebalance)
        buy_delta_vals.append(buy)
        sell_delta_vals.append(sell)
        turnover_vals.append(day_turnover)
        cost_vals.append(day_cost)
        gross_return_vals.append(gross)
        net_return_vals.append(net)
        actual_position_before_vals.append(actual_before)
        actual_position_next_vals.append(actual_next)
        stale_blocked_vals.append(overlay_trade_blocked)
        stale_assets_vals.append(",".join(stale_assets))
        carried_position = actual_next
        carried_exposure = final_after_overheat if actual_next != "CASH" else 0.0

    exposure_effective = pd.Series(exposure_effective_vals, index=out.index, dtype=float)
    final_exposure = pd.Series(final_exposure_vals, index=out.index, dtype=float)
    final_exposure_after_overheat = pd.Series(final_exposure_after_overheat_vals, index=out.index, dtype=float)
    drifted_exposure = pd.Series(drifted_exposure_vals, index=out.index, dtype=float)
    rebalance_delta = pd.Series(rebalance_delta_vals, index=out.index, dtype=float)
    buy_delta = pd.Series(buy_delta_vals, index=out.index, dtype=float)
    sell_delta = pd.Series(sell_delta_vals, index=out.index, dtype=float)
    turnover = pd.Series(turnover_vals, index=out.index, dtype=float)
    cost = pd.Series(cost_vals, index=out.index, dtype=float)
    gross_return = pd.Series(gross_return_vals, index=out.index, dtype=float)
    net_return = pd.Series(net_return_vals, index=out.index, dtype=float)

    out["base_position_before"] = position_before
    out["base_position_next"] = position_next
    out["actual_position_before"] = pd.Series(actual_position_before_vals, index=out.index)
    out["actual_position_next"] = pd.Series(actual_position_next_vals, index=out.index)
    prior_blocked = out.get("trade_blocked_by_stale_price", pd.Series(False, index=out.index)).fillna(False).astype(bool)
    out["trade_blocked_by_stale_price"] = prior_blocked | pd.Series(stale_blocked_vals, index=out.index, dtype=bool)
    prior_assets = out.get("stale_price_trade_assets", pd.Series("", index=out.index)).fillna("").astype(str)
    out["stale_price_trade_assets"] = [
        ",".join(dict.fromkeys(filter(None, f"{old},{new}".split(","))))
        for old, new in zip(prior_assets, stale_assets_vals)
    ]
    out["target_vol_scale_effective"] = target_vol_effective
    out["target_vol_scale_next"] = target_vol_next
    out["weight"] = target_vol_next
    out["overheat_scale_effective"] = overheat_effective
    out["overheat_scale_next"] = overheat_next
    out["overheat_scale"] = overheat_next
    out["exposure_effective"] = exposure_effective
    out["final_exposure"] = final_exposure
    out["final_exposure_after_overheat"] = final_exposure_after_overheat
    out["drifted_exposure_before_trade"] = drifted_exposure
    out["rebalance_delta"] = rebalance_delta
    out["buy_delta"] = buy_delta
    out["sell_delta"] = sell_delta
    out["turnover"] = turnover
    out["cost"] = cost
    out["gross_return"] = gross_return
    out["cash_return_component"] = (1.0 - exposure_effective.clip(lower=0.0, upper=1.0)) * CASH_DAILY_RETURN
    out["cash_exposure_effective"] = 1.0 - exposure_effective.clip(lower=0.0, upper=1.0)
    out["return"] = net_return
    out["nav"] = (1.0 + net_return).cumprod()
    out["effective_trade_count"] = (turnover > 1e-12).cumsum()
    return out


# ════════════════════════════════════════════════════════════════
#  Target-vol overlay
# ════════════════════════════════════════════════════════════════

def apply_target_vol_overlay(
    curve: pd.DataFrame,
    target_vol: float,
    vol_window: int,
    max_lev: float,
    one_way_cost: float = ONE_WAY_COST,
    price_ffill_flags: pd.DataFrame | None = None,
) -> pd.DataFrame:
    result = curve.copy()
    realized_vol, effective_scale, next_scale = _compute_target_vol_scales(
        result, target_vol, vol_window, max_lev
    )
    result["base_return"] = result["return"].astype(float).fillna(0.0)
    result["base_nav"] = result["nav"]
    result["base_gross_return"] = result["gross_return"].astype(float).fillna(0.0)
    result["base_turnover"] = _float_series(result, "turnover", 0.0)
    result["base_cost"] = _float_series(result, "cost", 0.0)
    result["virtual_base_realized_vol"] = realized_vol
    result["realized_vol"] = realized_vol
    ones = pd.Series(1.0, index=result.index, dtype=float)
    result = _recompute_final_exposure_nav(
        result, effective_scale, next_scale, ones, ones, one_way_cost, price_ffill_flags
    )
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
    first_valid_idx = total_lookback - 1
    x = np.arange(CN_MOM_DAY, dtype=float)
    for i in range(first_valid_idx, n):
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


def _text_or_none(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text if text else None


def _float_or_default(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except Exception:
        return default
    return result if math.isfinite(result) else default


def _truthy(value: object) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _set_if_present(frame: pd.DataFrame, idx: object, column: str, value: object) -> None:
    if column in frame.columns:
        frame.at[idx, column] = value


def _apply_zero_overheat_execution_guard(
    out: pd.DataFrame,
    price_ffill_flags: pd.DataFrame | None = None,
) -> pd.DataFrame:
    required = {"position_before", "position", "fraction_before", "holding_fraction"}
    if not required.issubset(out.columns) or "overheat_scale_next" not in out.columns:
        return out

    guarded = out.copy()
    ffill_flags = _validate_price_ffill_flags(guarded, price_ffill_flags)
    for col in (
        "position_before",
        "position",
        "fraction_before",
        "holding_fraction",
        "trade_target",
        "trade_fraction",
        "pending_entry_target",
        "pending_entry_since",
        "pending_entry_days",
        "staged_initial",
        "fill_on_down_day",
    ):
        if col in guarded.columns and f"base_{col}" not in guarded.columns:
            guarded[f"base_{col}"] = guarded[col]

    guarded["actual_entry_state"] = "CASH"
    guarded["actual_pending_target"] = pd.NA
    guarded["actual_pending_since"] = pd.NaT
    guarded["actual_pending_days"] = 0
    guarded["actual_staged_initial"] = False
    guarded["actual_fill_on_down_day"] = False
    guarded["actual_staged_initial_count"] = 0
    guarded["actual_staged_fill_count"] = 0
    guarded["staged_entry_event_count"] = 0
    if "trade_blocked_by_stale_price" not in guarded.columns:
        guarded["trade_blocked_by_stale_price"] = False
    if "blocked_trade_target" not in guarded.columns:
        guarded["blocked_trade_target"] = None
    if "stale_price_trade_assets" not in guarded.columns:
        guarded["stale_price_trade_assets"] = ""
    if "overlay_blocked_trade_target" not in guarded.columns:
        guarded["overlay_blocked_trade_target"] = None

    actual_position = "CASH"
    actual_fraction = 0.0
    actual_pending_target: str | None = None
    actual_pending_since: pd.Timestamp | None = None
    actual_pending_days = 0
    actual_staged_initial_count = 0
    actual_staged_fill_count = 0
    staged_entry_event_count = 0
    eps = 1e-12

    for idx, row in guarded.iterrows():
        base_prev = str(row.get("position_before", "CASH"))
        base_target = str(row.get("position", "CASH"))
        base_fraction = float(np.clip(_float_or_default(row.get("holding_fraction"), 0.0), 0.0, 1.0))
        asset_return = _float_or_default(row.get("asset_return"), 0.0)
        next_scale = _float_or_default(row.get("overheat_scale_next"), 1.0)
        target_eligible = base_target in ASSETS
        blocked_next = bool(target_eligible and next_scale <= eps)

        prior_fraction = actual_fraction if actual_position == base_prev and base_prev in ASSETS else 0.0
        guarded.at[idx, "fraction_before"] = prior_fraction
        _set_if_present(guarded, idx, "staged_initial", False)
        _set_if_present(guarded, idx, "fill_on_down_day", False)

        state = "CASH"
        new_fraction = 0.0
        staged_initial = False
        fill_on_down_day = False

        stale_zero_exit = bool(
            blocked_next
            and actual_position in ASSETS
            and actual_fraction > eps
            and bool(ffill_flags.at[pd.Timestamp(idx).normalize(), actual_position])
        )
        if stale_zero_exit:
            new_fraction = actual_fraction
            if actual_pending_target == actual_position:
                state = "HALF_POSITION_WAIT_DOWN"
            elif new_fraction >= 1.0 - eps:
                state = "FULL_POSITION"
            else:
                state = "PARTIAL_POSITION"
            _set_if_present(guarded, idx, "trade_fraction", new_fraction)
            _set_if_present(guarded, idx, "pending_entry_target", actual_pending_target)
            _set_if_present(guarded, idx, "pending_entry_since", actual_pending_since)
            _set_if_present(guarded, idx, "pending_entry_days", actual_pending_days)
        elif blocked_next:
            new_fraction = 0.0
            state = "BLOCKED_BY_OVERHEAT"
            _set_if_present(guarded, idx, "trade_fraction", 0.0)
            _set_if_present(guarded, idx, "pending_entry_target", None)
            _set_if_present(guarded, idx, "pending_entry_since", None)
            _set_if_present(guarded, idx, "pending_entry_days", 0)
            actual_pending_target = None
            actual_pending_since = None
            actual_pending_days = 0
            actual_position = "CASH"
            actual_fraction = 0.0
        elif base_target == "CASH" or not target_eligible:
            new_fraction = 0.0
            state = "CASH"
            _set_if_present(guarded, idx, "pending_entry_target", None)
            _set_if_present(guarded, idx, "pending_entry_since", None)
            _set_if_present(guarded, idx, "pending_entry_days", 0)
            actual_position = "CASH"
            actual_fraction = 0.0
            actual_pending_target = None
            actual_pending_since = None
            actual_pending_days = 0
        else:
            row_pending = _text_or_none(row.get("pending_entry_target"))
            stale_initial_entry = bool(
                actual_position == "CASH"
                and actual_fraction <= eps
                and bool(ffill_flags.at[pd.Timestamp(idx).normalize(), base_target])
            )
            if stale_initial_entry:
                new_fraction = 0.0
                state = "CASH"
                guarded.at[idx, "trade_blocked_by_stale_price"] = True
                existing_target = _text_or_none(guarded.at[idx, "blocked_trade_target"])
                if existing_target is None:
                    guarded.at[idx, "blocked_trade_target"] = base_target
                guarded.at[idx, "overlay_blocked_trade_target"] = base_target
                existing_assets = _text_or_none(guarded.at[idx, "stale_price_trade_assets"]) or ""
                guarded.at[idx, "stale_price_trade_assets"] = ",".join(
                    dict.fromkeys(filter(None, f"{existing_assets},{base_target}".split(",")))
                )
                _set_if_present(guarded, idx, "trade_target", None)
                _set_if_present(guarded, idx, "trade_fraction", 0.0)
                _set_if_present(guarded, idx, "pending_entry_target", None)
                _set_if_present(guarded, idx, "pending_entry_since", None)
                _set_if_present(guarded, idx, "pending_entry_days", 0)
                actual_pending_target = None
                actual_pending_since = None
                actual_pending_days = 0
            elif actual_position != base_target or actual_fraction <= eps:
                new_fraction = min(base_fraction, INITIAL_ENTRY_FRACTION) if base_fraction > eps else 0.0
                if new_fraction > eps:
                    _set_if_present(guarded, idx, "trade_target", base_target)
                    _set_if_present(guarded, idx, "trade_fraction", new_fraction)
                if row_pending == base_target or base_fraction > new_fraction + eps:
                    actual_pending_target = base_target
                    actual_pending_since = pd.Timestamp(idx)
                    actual_pending_days = 0
                    staged_initial = new_fraction > eps
                    if staged_initial:
                        actual_staged_initial_count += 1
                    _set_if_present(guarded, idx, "pending_entry_target", base_target)
                    _set_if_present(guarded, idx, "pending_entry_since", actual_pending_since)
                    _set_if_present(guarded, idx, "pending_entry_days", actual_pending_days)
                    _set_if_present(guarded, idx, "staged_initial", staged_initial)
                else:
                    actual_pending_target = None
                    actual_pending_since = None
                    actual_pending_days = 0
                    _set_if_present(guarded, idx, "pending_entry_target", None)
                    _set_if_present(guarded, idx, "pending_entry_since", None)
                    _set_if_present(guarded, idx, "pending_entry_days", 0)
            elif actual_pending_target == base_target:
                actual_down_day = bool(asset_return < -eps)
                if actual_down_day:
                    new_fraction = base_fraction
                    fill_on_down_day = True
                    actual_staged_fill_count += 1
                    actual_pending_target = None if new_fraction >= 1.0 - eps else base_target
                    if actual_pending_target is None:
                        actual_pending_since = None
                        actual_pending_days = 0
                    _set_if_present(guarded, idx, "trade_target", base_target)
                    _set_if_present(guarded, idx, "trade_fraction", new_fraction)
                    _set_if_present(guarded, idx, "fill_on_down_day", True)
                    _set_if_present(guarded, idx, "pending_entry_target", actual_pending_target)
                    _set_if_present(guarded, idx, "pending_entry_since", actual_pending_since)
                    _set_if_present(guarded, idx, "pending_entry_days", actual_pending_days)
                else:
                    new_fraction = min(actual_fraction, base_fraction)
                    actual_pending_days += 1
                    _set_if_present(guarded, idx, "pending_entry_target", base_target)
                    _set_if_present(guarded, idx, "pending_entry_since", actual_pending_since)
                    _set_if_present(guarded, idx, "pending_entry_days", actual_pending_days)
            else:
                new_fraction = base_fraction
                actual_pending_target = None
                actual_pending_since = None
                actual_pending_days = 0
                _set_if_present(guarded, idx, "pending_entry_target", None)
                _set_if_present(guarded, idx, "pending_entry_since", None)
                _set_if_present(guarded, idx, "pending_entry_days", 0)

            if actual_pending_target == base_target:
                state = "HALF_POSITION_WAIT_DOWN"
            elif new_fraction >= 1.0 - eps:
                state = "FULL_POSITION"
            elif new_fraction > eps:
                state = "PARTIAL_POSITION"
            else:
                state = "CASH"

        if new_fraction < base_fraction - eps and _truthy(row.get("fill_on_down_day")):
            _set_if_present(guarded, idx, "fill_on_down_day", False)

        guarded.at[idx, "holding_fraction"] = new_fraction
        if abs(new_fraction - prior_fraction) > eps or (prior_fraction > eps and base_prev != base_target):
            staged_entry_event_count += 1
        guarded.at[idx, "actual_entry_state"] = state
        guarded.at[idx, "actual_pending_target"] = actual_pending_target if state == "HALF_POSITION_WAIT_DOWN" else pd.NA
        guarded.at[idx, "actual_pending_since"] = actual_pending_since if state == "HALF_POSITION_WAIT_DOWN" else pd.NaT
        guarded.at[idx, "actual_pending_days"] = actual_pending_days if state == "HALF_POSITION_WAIT_DOWN" else 0
        guarded.at[idx, "actual_staged_initial"] = staged_initial
        guarded.at[idx, "actual_fill_on_down_day"] = fill_on_down_day
        guarded.at[idx, "actual_staged_initial_count"] = actual_staged_initial_count
        guarded.at[idx, "actual_staged_fill_count"] = actual_staged_fill_count
        guarded.at[idx, "staged_entry_event_count"] = staged_entry_event_count
        actual_position = base_target if new_fraction > eps else "CASH"
        actual_fraction = new_fraction if actual_position != "CASH" else 0.0

    return guarded


def apply_overheat_overlay(
    curve: pd.DataFrame,
    features: dict[str, pd.DataFrame],
    case: OverheatCase,
    one_way_cost: float,
    recovery_mode: Literal["same_side_or_exit", "exit_only"] = "same_side_or_exit",
    price_ffill_flags: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if (
        not math.isfinite(float(case.enter))
        or not math.isfinite(float(case.exit))
        or not 0 < case.exit < case.enter
    ):
        raise ValueError(f"Bad overheat thresholds: {case}")
    if not math.isfinite(float(case.derisk_scale)) or not 0 <= case.derisk_scale <= 1:
        raise ValueError(f"Bad derisk scale: {case}")
    if recovery_mode not in {"same_side_or_exit", "exit_only"}:
        raise ValueError(f"Bad overheat recovery mode: {recovery_mode}")

    out = curve.copy()
    defense_on = False
    state_asset: str | None = None
    effective_scales: list[float] = []
    next_scales: list[float] = []
    effective_on_vals: list[bool] = []
    next_on_vals: list[bool] = []
    trigger_vals: list[bool] = []
    recover_vals: list[bool] = []
    bias_vals: list[float] = []
    mom_vals: list[float] = []
    same_side_vals: list[bool] = []
    missing_feature_vals: list[bool] = []

    for dt, row in out.iterrows():
        effective_holding = str(row["position_before"])
        target_holding = str(row["position"])
        effective_eligible = effective_holding in ASSETS
        target_eligible = target_holding in ASSETS

        effective_state = bool(defense_on and state_asset == effective_holding and effective_eligible)
        effective_scale = float(case.derisk_scale) if effective_state else 1.0
        next_state = bool(defense_on and state_asset == target_holding and target_eligible)

        bias = math.nan
        mom = math.nan
        same_side = False
        if target_eligible and dt in features[target_holding].index:
            frow = features[target_holding].loc[dt]
            bias = float(frow["bias"]) if pd.notna(frow["bias"]) else math.nan
            mom = float(frow["bias_mom"]) if pd.notna(frow["bias_mom"]) else math.nan
            same_side = bool(frow["same_side"]) if pd.notna(frow["same_side"]) else False
        feature_missing = bool(target_eligible and (pd.isna(bias) or pd.isna(mom)))

        triggered = False
        recovered = False
        prior_next_state = next_state
        if target_eligible:
            if next_state:
                if feature_missing:
                    next_state = True
                elif bias <= case.exit:
                    next_state = False
                    recovered = True
                elif recovery_mode == "same_side_or_exit" and not same_side:
                    next_state = False
                    recovered = True
            elif not feature_missing and same_side and bias >= case.enter:
                next_state = True
                triggered = True
        else:
            next_state = False

        next_scale = float(case.derisk_scale) if next_state and target_eligible else 1.0
        effective_scales.append(effective_scale)
        next_scales.append(next_scale)
        effective_on_vals.append(bool(effective_scale < 0.999999 and effective_eligible))
        next_on_vals.append(bool(next_scale < 0.999999 and target_eligible))
        trigger_vals.append(triggered)
        recover_vals.append(bool(recovered and prior_next_state))
        bias_vals.append(bias)
        mom_vals.append(mom)
        same_side_vals.append(same_side)
        missing_feature_vals.append(feature_missing)
        defense_on = next_state
        state_asset = target_holding if target_eligible else None

    out.insert(0, "scenario", case.label)
    out["overheat_enter"] = case.enter
    out["overheat_exit"] = case.exit
    out["overheat_derisk_scale"] = case.derisk_scale
    out["overheat_recovery_mode"] = recovery_mode
    out["nav_before_overheat"] = out["nav"]
    out["return_before_overheat"] = out["return"]
    out["overheat_scale_effective"] = pd.Series(effective_scales, index=out.index, dtype=float)
    out["overheat_scale_next"] = pd.Series(next_scales, index=out.index, dtype=float)
    out["overheat_scale"] = out["overheat_scale_next"]
    out["overheat_on_effective"] = pd.Series(effective_on_vals, index=out.index, dtype=bool)
    out["overheat_on"] = pd.Series(next_on_vals, index=out.index, dtype=bool)
    out["overheat_triggered"] = pd.Series(trigger_vals, index=out.index, dtype=bool)
    out["overheat_recovered"] = pd.Series(recover_vals, index=out.index, dtype=bool)
    out["overheat_bias"] = pd.Series(bias_vals, index=out.index, dtype=float)
    out["overheat_bias_mom"] = pd.Series(mom_vals, index=out.index, dtype=float)
    out["overheat_same_side"] = pd.Series(same_side_vals, index=out.index, dtype=bool)
    out["overheat_feature_missing"] = pd.Series(missing_feature_vals, index=out.index, dtype=bool)
    out["overheat_tc"] = 0.0
    out = _apply_zero_overheat_execution_guard(out, price_ffill_flags)
    target_vol_effective = _float_series(out, "target_vol_scale_effective", 1.0)
    target_vol_next = _float_series(out, "target_vol_scale_next", 1.0)
    existing_overlay_effective = _float_series(out, "nav_defense_scale_effective", 1.0)
    existing_overlay_next = _float_series(out, "nav_defense_scale_next", 1.0)
    combined_overlay_effective = existing_overlay_effective * out["overheat_scale_effective"].astype(float)
    combined_overlay_next = existing_overlay_next * out["overheat_scale_next"].astype(float)
    out = _recompute_final_exposure_nav(
        out,
        target_vol_effective,
        target_vol_next,
        combined_overlay_effective,
        combined_overlay_next,
        one_way_cost,
        price_ffill_flags,
    )
    out["combined_overlay_scale_effective"] = combined_overlay_effective
    out["combined_overlay_scale_next"] = combined_overlay_next
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
    out["overheat_recovery_mode"] = ""
    out["overheat_scale_effective"] = 1.0
    out["overheat_scale_next"] = 1.0
    out["overheat_scale"] = 1.0
    out["overheat_on"] = False
    out["overheat_on_effective"] = False
    out["overheat_triggered"] = False
    out["overheat_recovered"] = False
    out["overheat_feature_missing"] = False
    out["overheat_tc"] = 0.0
    out["nav_before_overheat"] = out["nav"]
    return out


def nav_defense_state(
    base_curve: pd.DataFrame,
    enter_threshold: float,
    exit_threshold: float,
    defense_scale: float,
) -> pd.DataFrame:
    if not 0.0 < exit_threshold < enter_threshold < 1.0:
        raise ValueError("NAV defense thresholds must satisfy 0 < exit < enter < 1")
    if not 0.0 <= defense_scale <= 1.0:
        raise ValueError("NAV defense scale must be in [0, 1]")
    pre_nav = base_curve["nav"].astype(float)
    base_dd = pre_nav / pre_nav.cummax().clip(lower=1.0) - 1.0
    active = False
    effective_scales: list[float] = []
    next_scales: list[float] = []
    trigger_flags: list[bool] = []
    recovery_flags: list[bool] = []

    for dd in base_dd:
        effective_scales.append(float(defense_scale) if active else 1.0)
        triggered = False
        recovered = False
        if active:
            if float(dd) >= -float(exit_threshold):
                active = False
                recovered = True
        elif float(dd) <= -float(enter_threshold):
            active = True
            triggered = True
        next_scales.append(float(defense_scale) if active else 1.0)
        trigger_flags.append(triggered)
        recovery_flags.append(recovered)

    return pd.DataFrame(
        {
            "nav_defense_base_dd": base_dd,
            "nav_defense_scale_effective": pd.Series(effective_scales, index=base_curve.index, dtype=float),
            "nav_defense_scale_next": pd.Series(next_scales, index=base_curve.index, dtype=float),
            "nav_defense_on_effective": pd.Series(
                [scale < 0.999999 for scale in effective_scales],
                index=base_curve.index,
                dtype=bool,
            ),
            "nav_defense_on_next": pd.Series(
                [scale < 0.999999 for scale in next_scales],
                index=base_curve.index,
                dtype=bool,
            ),
            "nav_defense_triggered": pd.Series(trigger_flags, index=base_curve.index, dtype=bool),
            "nav_defense_recovered": pd.Series(recovery_flags, index=base_curve.index, dtype=bool),
        },
        index=base_curve.index,
    )


def apply_nav_defense_overlay(
    curve: pd.DataFrame,
    enter_threshold: float,
    exit_threshold: float,
    defense_scale: float,
    one_way_cost: float,
    price_ffill_flags: pd.DataFrame | None = None,
) -> pd.DataFrame:
    out = curve.copy()
    out["return_before_nav_defense"] = out["return"].astype(float).fillna(0.0)
    out["nav_before_nav_defense"] = out["nav"].astype(float)
    gate = nav_defense_state(out, enter_threshold, exit_threshold, defense_scale)
    for col in gate.columns:
        out[col] = gate[col]
    ones = pd.Series(1.0, index=out.index, dtype=float)
    out = _recompute_final_exposure_nav(
        out,
        ones,
        ones,
        gate["nav_defense_scale_effective"],
        gate["nav_defense_scale_next"],
        one_way_cost,
        price_ffill_flags,
    )
    for col in gate.columns:
        out[col] = gate[col]
    out["nav_defense_enabled"] = True
    out["nav_enter_threshold"] = float(enter_threshold)
    out["nav_exit_threshold"] = float(exit_threshold)
    out["nav_defense_scale"] = float(defense_scale)
    return out


def build_curves(
    prices: pd.DataFrame,
    config: RunConfig,
    price_ffill_flags: pd.DataFrame | None = None,
) -> list[pd.DataFrame]:
    price_ffill_flags = _validate_price_ffill_flags(prices, price_ffill_flags)
    staged = run_staged_entry(
        prices,
        config,
        EntryCase("entry_25_wait_down_no_timeout", "all_new_asset_50_wait_down", INITIAL_ENTRY_FRACTION),
        R2_THRESHOLD,
        SWITCH_BUFFER,
        price_ffill_flags=price_ffill_flags,
    )
    staged["target_vol"] = np.nan
    staged["realized_vol"] = np.nan
    staged["target_vol_scale_effective"] = 1.0
    staged["target_vol_scale_next"] = 1.0
    staged["weight"] = 1.0
    defended = apply_nav_defense_overlay(
        staged,
        NAV_DEFENSE_ENTER,
        NAV_DEFENSE_EXIT,
        NAV_DEFENSE_SCALE,
        config.one_way_cost,
        price_ffill_flags,
    )
    v11 = apply_overheat_overlay(
        defended,
        build_overheat_features(prices),
        OverheatCase(V11_SCENARIO, OVERHEAT_ENTER, OVERHEAT_EXIT, OVERHEAT_DERISK_SCALE),
        config.one_way_cost,
        recovery_mode=OVERHEAT_RECOVERY_MODE,
        price_ffill_flags=price_ffill_flags,
    )
    v11.insert(0, "version", VERSION)
    v11["scenario"] = V11_SCENARIO
    return [v11]


# ════════════════════════════════════════════════════════════════
#  Live computation helpers
# ════════════════════════════════════════════════════════════════

def _build_config(end_date=None) -> RunConfig:
    end_date = _bj_today_naive() if end_date is None else pd.Timestamp(end_date).normalize()
    return RunConfig(
        source="proxy_mixed_v1_3", one_way_cost=ONE_WAY_COST,
        start_date=START_DATE, end_date=end_date,
        output_tag="v1_3_live", target_vols=(),
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
        raise poe.BotError("未找到 SubD mixed-pool v1.3 日度输出。")
    return out


def _build_v11_daily(
    end_date=None,
    data_state: Literal["confirmed", "live"] = "confirmed",
    now: datetime | None = None,
):
    """Download prices, run full backtest, return (daily_df, source_description)."""
    config = _build_config(end_date=end_date)
    prices, sources = load_close(config)
    prices = prices.loc[prices.index >= config.start_date]
    raw_prices_for_fill_flags = prices.attrs.get("raw_unfilled_prices")
    if not isinstance(raw_prices_for_fill_flags, pd.DataFrame):
        raw_prices_for_fill_flags = prices.copy()
    else:
        raw_prices_for_fill_flags = raw_prices_for_fill_flags.reindex(prices.index).copy()
    live_quote_metadata: dict[str, dict[str, object]] = {}
    live_source_note = ""
    if data_state == "live":
        try:
            live_quotes = _load_live_quotes_for_prices(list(ASSETS), prices, now=now)
            prices, live_quote_metadata = _apply_live_quotes_to_prices(prices, live_quotes, now=now)
            raw_prices_for_fill_flags = _sync_live_quote_raw_availability(
                raw_prices_for_fill_flags, prices, live_quote_metadata
            )
            if not live_quotes.empty:
                live_source_note = "live quotes: " + ", ".join(
                    dict.fromkeys(str(item) for item in live_quotes["source"].dropna())
                )
        except Exception as exc:
            raise poe.BotError(f"live quotes unavailable: {str(exc)[:240]}") from exc
    prices = prices.sort_index()
    common_last = pd.Timestamp(prices.index[-1])
    last_by_asset = {
        code: pd.Timestamp(prices[code].dropna().index.max()) if prices[code].notna().any() else pd.NaT
        for code in ASSETS
    }
    price_ffill_flags = _price_forward_fill_flags(raw_prices_for_fill_flags, prices, list(ASSETS))
    curves = build_curves(prices, config, price_ffill_flags=price_ffill_flags)
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="The behavior of DataFrame concatenation with empty or all-NA entries is deprecated.*",
            category=FutureWarning,
        )
        daily = pd.concat(curves, sort=False).reset_index().rename(columns={"index": "date"})
    if sources.empty:
        source_name = "unknown"
    else:
        source_name = _source_summary_text(sources)
    if live_source_note:
        source_name = f"{source_name}; {live_source_note}"
    daily = _attach_signal_prices(daily, prices)
    daily = _attach_price_fill_metadata(daily, price_ffill_flags)
    if data_state == "confirmed":
        daily = _attach_confirmed_final_close_metadata(daily, last_by_asset=last_by_asset, now=now)
    daily = _attach_live_quote_metadata(daily, live_quote_metadata)
    daily["common_last_date"] = common_last.date().isoformat()
    for code, last_date in last_by_asset.items():
        daily[f"last_date_{code}"] = "" if pd.isna(last_date) else pd.Timestamp(last_date).date().isoformat()
    return _normalize_daily(daily), source_name


def _load_live_quotes_for_prices(
    codes: list[str],
    prices: pd.DataFrame,
    now: datetime | None = None,
) -> pd.DataFrame:
    unsupported = _live_quote_unsupported_codes(codes)
    if unsupported:
        raise UnsupportedLiveQuoteSymbols(unsupported)
    kwargs: dict[str, object] = {"now": now}
    params = inspect.signature(load_live_quotes).parameters
    if "reference_prices" in params:
        kwargs["reference_prices"] = prices
    if "expected_quote_date" in params:
        kwargs["expected_quote_date"] = pd.Timestamp(_as_bj_datetime(now).date()).normalize()
    return load_live_quotes(codes, **kwargs)


_DAILY_CACHE: dict[str, tuple[datetime, pd.DataFrame, str]] = {}
_DAILY_CACHE_LOCK = RLock()


def _daily_cache_key(date_key: str, data_state: str) -> str:
    return f"{date_key}:{data_state}"


def _clear_daily_cache() -> None:
    with _DAILY_CACHE_LOCK:
        _DAILY_CACHE.clear()


def _crossed_close_boundary(cached_at: datetime, now: datetime) -> bool:
    return (
        cached_at.date() == now.date()
        and cached_at.time() < CONFIRMED_CLOSE_CUTOFF
        and now.time() >= CONFIRMED_CLOSE_CUTOFF
    )


def _with_cache_metadata(daily: pd.DataFrame, cached_at: datetime) -> pd.DataFrame:
    out = daily.copy()
    latest_text = ""
    bar_state = "unknown"
    if "date" in out.columns and not out.empty:
        parsed_dates = pd.to_datetime(out["date"], errors="coerce")
        latest = parsed_dates.max()
        if pd.notna(latest):
            latest_idx = parsed_dates.idxmax()
            latest_row = out.loc[latest_idx]
            latest_ts = pd.Timestamp(latest).normalize()
            latest_text = latest_ts.date().isoformat()
            bar_state = "intraday" if _row_uses_unconfirmed_bar(latest_row, cached_at) else "confirmed"
    out["cached_as_of_bj"] = cached_at.strftime("%Y-%m-%d %H:%M:%S")
    out["cached_latest_bar_date"] = latest_text
    out["cached_bar_state"] = bar_state
    return out


def _cached_daily(date_key: str, data_state: str = "confirmed") -> tuple[pd.DataFrame, str]:
    with _DAILY_CACHE_LOCK:
        key = _daily_cache_key(date_key, data_state)
        now = _now_bj()
        cached = _DAILY_CACHE.get(key)
        if cached is not None:
            cached_at, daily, source_name = cached
            if now - cached_at <= DAILY_CACHE_TTL and not _crossed_close_boundary(cached_at, now):
                return daily, source_name
        daily, source_name = _call_build_v11_daily(pd.Timestamp(date_key), data_state, now)
        daily = _with_cache_metadata(daily, now)
        _DAILY_CACHE[key] = (now, daily, source_name)
        return daily, source_name


_cached_daily.cache_clear = _clear_daily_cache  # type: ignore[attr-defined]


def _refresh_failed_cache_note(source_name: str, cached_at: datetime, exc: Exception) -> str:
    return (
        f"{source_name}; refresh failed, reused cached daily as of "
        f"{cached_at.strftime('%Y-%m-%d %H:%M:%S')}: {str(exc)[:120]}"
    )


def _call_build_v11_daily(
    end_date: pd.Timestamp,
    data_state: str,
    now: datetime,
) -> tuple[pd.DataFrame, str]:
    params = inspect.signature(_build_v11_daily).parameters
    accepts_kwargs = any(param.kind == param.VAR_KEYWORD for param in params.values())
    kwargs: dict[str, object] = {"end_date": end_date}
    if accepts_kwargs or "data_state" in params:
        kwargs["data_state"] = data_state
    if accepts_kwargs or "now" in params:
        kwargs["now"] = now
    return _build_v11_daily(**kwargs)


_PERFORMANCE_RESPONSE_RENDERED_VAR: ContextVar[bool] = ContextVar(
    "_PERFORMANCE_RESPONSE_RENDERED",
    default=False,
)


def _set_performance_response_rendered(rendered: bool):
    return _PERFORMANCE_RESPONSE_RENDERED_VAR.set(rendered)


def _performance_response_rendered() -> bool:
    return _PERFORMANCE_RESPONSE_RENDERED_VAR.get()


def _now_bj() -> datetime:
    return datetime.now(CN_TZ)


def _normalize_query_date(value: object) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert(CN_TZ).tz_localize(None)
    return ts.normalize()


def _bj_today_naive() -> pd.Timestamp:
    return pd.Timestamp(_now_bj().date())


def _as_bj_datetime(now: datetime | None = None) -> datetime:
    if now is None:
        return _now_bj()
    if now.tzinfo is None:
        return now.replace(tzinfo=CN_TZ)
    return now.astimezone(CN_TZ)


def _asset_exchange(code: str | None) -> str:
    text = str(code or "").upper().strip()
    if text.endswith(".SH"):
        return "SSE"
    if text.endswith(".SZ"):
        return "SZSE"
    return ""


def _security_type_for_asset(code: str | None) -> str:
    text = str(code or "").strip()
    if text not in ASSETS:
        return "UNKNOWN"
    return "ETF" if _is_cn_exchange_symbol(text) else "PROXY"


def _supports_post_close_fixed_price(
    ts: datetime,
    asset_code: str | None = None,
    exchange: str | None = None,
    security_type: str = "ETF",
) -> bool:
    session_date = pd.Timestamp(ts.date()).normalize()
    if session_date < POST_CLOSE_FIXED_PRICE_EFFECTIVE_DATE:
        return False
    normalized_security_type = str(security_type or "").upper()
    if normalized_security_type != "ETF":
        return False
    normalized_exchange = str(exchange or _asset_exchange(asset_code) or "").upper()
    if normalized_exchange not in {"SSE", "SZSE"}:
        return False
    if asset_code is not None and _security_type_for_asset(asset_code) != "ETF":
        return False
    return True


def _execution_session_status(
    ts: datetime,
    is_trading_day: bool,
    asset_code: str | None = None,
    exchange: str | None = None,
    security_type: str = "ETF",
    rule_version_date: object | None = None,
) -> str:
    if not is_trading_day:
        return "CLOSED"
    session_ts = ts
    if rule_version_date is not None:
        rule_day = pd.Timestamp(rule_version_date)
        session_ts = ts.replace(
            year=rule_day.year,
            month=rule_day.month,
            day=rule_day.day,
        )
    session_date = pd.Timestamp(session_ts.date()).normalize()
    normalized_exchange = str(exchange or _asset_exchange(asset_code) or "").upper()
    normalized_security_type = str(security_type or "").upper()
    if normalized_security_type != "ETF" or normalized_exchange not in {"SSE", "SZSE"}:
        return "CLOSED"
    sse_legacy_etf = (
        normalized_exchange == "SSE"
        and normalized_security_type == "ETF"
        and session_date < POST_CLOSE_FIXED_PRICE_EFFECTIVE_DATE
    )
    clock = ts.time()
    if clock < dt_time(9, 15):
        return "PRE_OPEN"
    if dt_time(9, 15) <= clock < dt_time(9, 25):
        return "OPEN_CALL_ACCEPT"
    if dt_time(9, 25) <= clock < dt_time(9, 30):
        return "OPEN_GAP"
    if dt_time(9, 30) <= clock < dt_time(11, 30):
        return "OPEN_AM"
    if dt_time(11, 30) <= clock < dt_time(13, 0):
        return "LUNCH_BREAK"
    if sse_legacy_etf:
        if dt_time(13, 0) <= clock < dt_time(15, 0):
            return "OPEN_PM"
    else:
        if dt_time(13, 0) <= clock < dt_time(14, 57):
            return "OPEN_PM"
        if dt_time(14, 57) <= clock < dt_time(15, 0):
            return "CLOSE_CALL_ACCEPT"
    if dt_time(15, 5) <= clock <= dt_time(15, 30) and _supports_post_close_fixed_price(
        session_ts,
        asset_code,
        exchange=exchange,
        security_type=security_type,
    ):
        return "POST_CLOSE"
    return "CLOSED"


def _row_text_value(row: pd.Series, key: str, default: str = "") -> str:
    value = row.get(key, default)
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return text if text else default


def _row_float_value(row: pd.Series, key: str, default: float = 0.0) -> float:
    try:
        value = float(row.get(key, default))
    except Exception:
        return default
    return value if math.isfinite(value) else default


def _row_bool_value(row: pd.Series, key: str, default: bool = False) -> bool:
    return _explicit_bool_value(row.get(key, default), default)


def _parse_quote_time(value: object) -> pd.Timestamp | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        ts = pd.Timestamp(value)
    except Exception:
        return None
    try:
        if pd.isna(ts):
            return None
    except (TypeError, ValueError):
        pass
    if ts.tzinfo is None:
        ts = ts.tz_localize(CN_TZ)
    else:
        ts = ts.tz_convert(CN_TZ)
    return ts


def _format_quote_time(ts: pd.Timestamp | None) -> str | None:
    if ts is None:
        return None
    return ts.strftime("%Y-%m-%d %H:%M:%S%z")


def _source_quote_time(row: pd.Series) -> str | None:
    return _format_quote_time(_parse_quote_time(row.get("source_quote_time", None)))


def _prices_close(left: float, right: float, *, rel_tol: float = 1e-8, abs_tol: float = 1e-8) -> bool:
    return math.isclose(float(left), float(right), rel_tol=rel_tol, abs_tol=abs_tol)


def _row_verified_final_close(row: pd.Series, now: datetime | None = None) -> bool:
    ts = _as_bj_datetime(now)
    row_date = pd.Timestamp(row.get("date")).normalize()
    if row_date != pd.Timestamp(ts.date()).normalize():
        return False
    now_ts = pd.Timestamp(ts)
    for code in ASSETS:
        final_ts = _parse_quote_time(row.get(f"final_time_{code}", None))
        final_price = _row_float_value(row, f"final_price_{code}", math.nan)
        signal_price = _row_float_value(row, f"signal_price_{code}", math.nan)
        if not _row_bool_value(row, f"bar_final_{code}", False):
            return False
        if final_ts is None or final_ts.date() != row_date.date():
            return False
        if final_ts > now_ts or final_ts.time() < OFFICIAL_CLOSE_TIME:
            return False
        if not (math.isfinite(final_price) and math.isfinite(signal_price)):
            return False
        if not _prices_close(final_price, signal_price):
            return False
    return True


def _row_final_close_execution_verified(row: pd.Series) -> bool:
    if not _row_bool_value(row, "source_final_close_execution_verified", False):
        return False
    return all(
        _row_bool_value(row, f"final_close_execution_verified_{code}", False)
        for code in ASSETS
    )


def _row_live_quote_trade_state_verified(row: pd.Series, code: str) -> bool:
    volume = _row_float_value(row, f"quote_volume_{code}", math.nan)
    amount = _row_float_value(row, f"quote_amount_{code}", math.nan)
    return bool(
        math.isfinite(volume)
        and volume > 0
        and math.isfinite(amount)
        and amount > 0
    )


def _leg_execution_block_reasons(row: pd.Series, side: str, asset: str) -> list[str]:
    reasons: list[str] = []
    side = str(side or "").upper()
    if side == "SELL" and not _row_bool_value(row, f"sell_available_{asset}", False):
        reasons.append("sell_available_not_verified")
    quote_price = _row_float_value(row, f"quote_price_{asset}", math.nan)
    limit_down = _row_float_value(row, f"quote_limit_down_{asset}", math.nan)
    limit_up = _row_float_value(row, f"quote_limit_up_{asset}", math.nan)
    if side == "BUY" and math.isfinite(quote_price) and math.isfinite(limit_up):
        if quote_price >= limit_up - LIVE_PRICE_LIMIT_TOLERANCE:
            reasons.append("buy_at_limit_up")
    if side == "SELL" and math.isfinite(quote_price) and math.isfinite(limit_down):
        if quote_price <= limit_down + LIVE_PRICE_LIMIT_TOLERANCE:
            reasons.append("sell_at_limit_down")
    return reasons


def _row_uses_unconfirmed_bar(row: pd.Series, now: datetime | None = None) -> bool:
    ts = _as_bj_datetime(now)
    row_date = pd.Timestamp(row.get("date")).normalize()
    today = pd.Timestamp(ts.date()).normalize()
    return bool(row_date >= today and not _row_verified_final_close(row, ts))


def _live_snapshot_freshness(row: pd.Series, now: datetime | None = None) -> dict[str, object]:
    ts = _as_bj_datetime(now)
    now_ts = pd.Timestamp(ts)
    quote_times: dict[str, pd.Timestamp] = {}
    quote_prices: dict[str, float] = {}
    missing_assets: list[str] = []
    stale_assets: list[str] = []
    price_mismatch_assets: list[str] = []
    source_ineligible_assets: list[str] = []
    non_executable_quote_assets: list[str] = []
    for code in ASSETS:
        quote_ts = _parse_quote_time(row.get(f"quote_time_{code}", None))
        quote_price = _row_float_value(row, f"quote_price_{code}", math.nan)
        signal_price = _row_float_value(row, f"signal_price_{code}", math.nan)
        if quote_ts is None:
            missing_assets.append(code)
            continue
        if not math.isfinite(quote_price) or quote_price <= 0:
            missing_assets.append(code)
            continue
        quote_times[code] = quote_ts
        quote_prices[code] = quote_price
        quote_age = now_ts - quote_ts
        if (
            quote_ts.date() != ts.date()
            or quote_ts > now_ts + LIVE_QUOTE_FUTURE_TOLERANCE
            or quote_age > LIVE_QUOTE_MAX_AGE
        ):
            stale_assets.append(code)
        if not math.isfinite(signal_price) or not _prices_close(signal_price, quote_price):
            price_mismatch_assets.append(code)
        if not _source_execution_eligible(
            _row_text_value(row, f"quote_source_{code}", ""),
            row.get(f"source_execution_eligible_{code}", False),
        ):
            source_ineligible_assets.append(code)
        if not _row_live_quote_trade_state_verified(row, code):
            non_executable_quote_assets.append(code)
    if len(quote_times) == len(ASSETS):
        min_quote_time = min(quote_times.values())
        max_quote_time = max(quote_times.values())
        max_quote_age = max(now_ts - quote_ts for quote_ts in quote_times.values())
        max_quote_skew = max_quote_time - min_quote_time
        if max_quote_skew > LIVE_QUOTE_MAX_SKEW:
            lag_threshold = max_quote_time - LIVE_QUOTE_MAX_SKEW
            for code, quote_ts in quote_times.items():
                if quote_ts < lag_threshold and code not in stale_assets:
                    stale_assets.append(code)
    else:
        min_quote_time = None
        max_quote_time = None
        max_quote_age = None
        max_quote_skew = None
    all_quote_price_time_pairs_valid = bool(
        len(quote_times) == len(ASSETS)
        and len(quote_prices) == len(ASSETS)
        and not missing_assets
    )
    price_matrix_uses_live_quotes = bool(
        all_quote_price_time_pairs_valid
        and not price_mismatch_assets
    )
    all_asset_quotes_fresh = bool(
        all_quote_price_time_pairs_valid
        and price_matrix_uses_live_quotes
        and not stale_assets
        and not source_ineligible_assets
        and not non_executable_quote_assets
        and max_quote_age is not None
        and max_quote_skew is not None
        and max_quote_age <= LIVE_QUOTE_MAX_AGE
        and max_quote_skew <= LIVE_QUOTE_MAX_SKEW
    )
    return {
        "all_asset_quotes_fresh": all_asset_quotes_fresh,
        "live_snapshot_fresh": all_asset_quotes_fresh,
        "all_quote_price_time_pairs_valid": all_quote_price_time_pairs_valid,
        "price_matrix_uses_live_quotes": price_matrix_uses_live_quotes,
        "max_quote_age_seconds": (
            None if max_quote_age is None else float(max_quote_age.total_seconds())
        ),
        "max_quote_time_skew_seconds": (
            None if max_quote_skew is None else float(max_quote_skew.total_seconds())
        ),
        "latest_quote_time": _format_quote_time(max_quote_time),
        "earliest_quote_time": _format_quote_time(min_quote_time),
        "missing_quote_assets": missing_assets,
        "stale_quote_assets": stale_assets,
        "price_mismatch_assets": price_mismatch_assets,
        "source_ineligible_assets": source_ineligible_assets,
        "non_executable_quote_assets": non_executable_quote_assets,
        "all_quote_sources_execution_eligible": bool(
            all_quote_price_time_pairs_valid
            and not source_ineligible_assets
            and not non_executable_quote_assets
        ),
    }


def _execution_leg_status(
    side: str,
    asset: str,
    ts: datetime,
    is_trading_day: bool,
    signal_price_is_available: bool,
    execution_enabled: bool,
    row: pd.Series | None = None,
) -> dict[str, object]:
    exchange = _asset_exchange(asset)
    security_type = _security_type_for_asset(asset)
    execution_session = _execution_session_status(
        ts,
        is_trading_day=is_trading_day,
        asset_code=asset,
        exchange=exchange,
        security_type=security_type,
    )
    exchange_can_match_immediately = bool(execution_session in {"OPEN_AM", "OPEN_PM"})
    can_submit_in_session = execution_session in {
        "OPEN_CALL_ACCEPT",
        "OPEN_AM",
        "OPEN_PM",
        "CLOSE_CALL_ACCEPT",
    }
    block_reasons = (
        _leg_execution_block_reasons(row, side, asset)
        if execution_enabled and row is not None
        else []
    )
    blocked = bool(block_reasons)
    can_use_post_close_fixed_price = bool(
        execution_enabled
        and POST_CLOSE_FIXED_PRICE_EXECUTION_ENABLED
        and execution_session == "POST_CLOSE"
        and signal_price_is_available
        and not blocked
    )
    exchange_can_submit_order_now = bool(can_submit_in_session or can_use_post_close_fixed_price)
    can_submit_order_now = bool(
        execution_enabled
        and exchange_can_submit_order_now
        and not blocked
    )
    can_match_immediately = bool(
        execution_enabled
        and exchange_can_match_immediately
        and not blocked
    )
    result = {
        "side": side,
        "asset": asset,
        "exchange": exchange,
        "security_type": security_type,
        "exchange_can_submit_order_now": exchange_can_submit_order_now,
        "exchange_can_match_immediately": exchange_can_match_immediately,
        "can_submit_order_now": can_submit_order_now,
        "can_match_immediately": can_match_immediately,
        "can_use_post_close_fixed_price": can_use_post_close_fixed_price,
        "signal_price_is_available": bool(signal_price_is_available),
        "execution_session": execution_session,
    }
    if block_reasons:
        result["execution_block_reasons"] = block_reasons
    return result


def _execution_legs_status(
    daily: pd.DataFrame,
    ts: datetime,
    is_trading_day: bool,
    signal_price_is_available: bool,
    execution_enabled: bool,
) -> list[dict[str, object]]:
    if daily.empty:
        return []
    row = daily.sort_values("date").iloc[-1]
    legs: list[dict[str, object]] = []
    sell_delta = _row_float_value(row, "sell_delta", 0.0)
    buy_delta = _row_float_value(row, "buy_delta", 0.0)
    actual_before = _row_text_value(
        row,
        "actual_position_before",
        _row_text_value(row, "position_before", "CASH"),
    )
    actual_next = _row_text_value(
        row,
        "actual_position_next",
        _row_text_value(row, "position", "CASH"),
    )
    if sell_delta > 1e-12 and actual_before != "CASH":
        legs.append(
            _execution_leg_status(
                "SELL",
                actual_before,
                ts,
                is_trading_day,
                signal_price_is_available,
                execution_enabled,
                row,
            )
        )
    if buy_delta > 1e-12 and actual_next != "CASH":
        legs.append(
            _execution_leg_status(
                "BUY",
                actual_next,
                ts,
                is_trading_day,
                signal_price_is_available,
                execution_enabled,
                row,
            )
        )
    return legs


def _row_asset_last_date(row: pd.Series, code: str) -> pd.Timestamp | None:
    value = row.get(f"last_date_{code}", None)
    if value is None:
        return None
    try:
        parsed = pd.Timestamp(value).normalize()
    except Exception:
        return None
    try:
        if pd.isna(parsed):
            return None
    except (TypeError, ValueError):
        pass
    return parsed


def _row_asset_price_is_ffilled(row: pd.Series, code: str) -> bool:
    return _row_bool_value(row, f"price_ffill_{code}", False)


def _row_trade_leg_assets(row: pd.Series) -> list[str]:
    assets: list[str] = []
    sell_delta = _row_float_value(row, "sell_delta", 0.0)
    buy_delta = _row_float_value(row, "buy_delta", 0.0)
    actual_before = _row_text_value(
        row,
        "actual_position_before",
        _row_text_value(row, "position_before", "CASH"),
    )
    actual_next = _row_text_value(
        row,
        "actual_position_next",
        _row_text_value(row, "position", "CASH"),
    )
    if sell_delta > 1e-12 and actual_before in ASSETS:
        assets.append(actual_before)
    if buy_delta > 1e-12 and actual_next in ASSETS and actual_next not in assets:
        assets.append(actual_next)
    return assets


def _stale_price_trade_assets(row: pd.Series) -> list[str]:
    row_date = pd.Timestamp(row.get("date")).normalize()
    stale: list[str] = []
    for code in _row_trade_leg_assets(row):
        last_date = _row_asset_last_date(row, code)
        if _row_asset_price_is_ffilled(row, code) or (
            last_date is not None and last_date < row_date
        ):
            stale.append(code)
    return stale


def _fallback_previous_business_day(day: pd.Timestamp) -> pd.Timestamp:
    prev = pd.Timestamp(day).normalize() - pd.Timedelta(days=1)
    while prev.weekday() >= 5:
        prev -= pd.Timedelta(days=1)
    return prev.normalize()


def _status_calendar_sessions(ts: datetime, latest_market_date: pd.Timestamp | None = None) -> dict[str, object]:
    today = pd.Timestamp(ts.date()).normalize()
    required_start = today - pd.Timedelta(days=30)
    latest_market = None
    if latest_market_date is not None:
        latest_market = pd.Timestamp(latest_market_date).normalize()
        required_start = min(required_start, latest_market)
    if today.weekday() >= 5 and (latest_market is None or latest_market <= today):
        required_end = latest_market if latest_market is not None else _fallback_previous_business_day(today)
    else:
        required_end = today
        if latest_market is not None:
            required_end = max(required_end, latest_market)
    calendar = _expected_cn_trading_days(required_start, required_end)
    if calendar is not None and len(calendar) and pd.Timestamp(calendar.max()).normalize() < required_end:
        official_calendar = _load_official_cn_trading_calendar_2026(required_start, required_end)
        if official_calendar is not None:
            _set_calendar_failure("")
            calendar = pd.DatetimeIndex(
                official_calendar[0][
                    (official_calendar[0] >= required_start)
                    & (official_calendar[0] <= required_end)
                ]
            )
    if calendar is not None and len(calendar):
        sessions = pd.DatetimeIndex(calendar).normalize().unique().sort_values()
        if latest_market is not None and latest_market not in set(sessions):
            _set_calendar_failure(
                "行情最新日期不在交易日历，禁止生成可执行信号："
                f"行情最新日期 {latest_market.date().isoformat()}"
            )
            return {
                "calendar_available": False,
                "expected_today_session": False,
                "expected_live_session": latest_market,
                "expected_confirmed_session": latest_market,
            }
        sessions = pd.DatetimeIndex(sessions[sessions <= today])
        if len(sessions):
            latest_session = pd.Timestamp(sessions.max()).normalize()
            if latest_market is not None and latest_market > latest_session:
                _set_calendar_failure(
                    "交易日历落后于行情数据，禁止生成可执行信号："
                    f"交易日历最后交易日 {latest_session.date().isoformat()}，"
                    f"行情最新日期 {latest_market.date().isoformat()}"
                )
                return {
                    "calendar_available": False,
                    "expected_today_session": False,
                    "expected_live_session": latest_session,
                    "expected_confirmed_session": latest_session,
                }
            today_is_session = latest_session == today
            prior_sessions = pd.DatetimeIndex(sessions[sessions < today])
            previous_session = (
                pd.Timestamp(prior_sessions.max()).normalize()
                if len(prior_sessions)
                else latest_session
            )
            expected_confirmed = today if today_is_session and ts.time() >= CONFIRMED_CLOSE_CUTOFF else previous_session
            if not today_is_session:
                expected_confirmed = latest_session
            return {
                "calendar_available": True,
                "expected_today_session": today_is_session,
                "expected_live_session": today if today_is_session else latest_session,
                "expected_confirmed_session": expected_confirmed,
            }
    previous_business_day = _fallback_previous_business_day(today)
    if ts.weekday() < 5:
        expected_confirmed = today if ts.time() >= CONFIRMED_CLOSE_CUTOFF else previous_business_day
        return {
            "calendar_available": False,
            "expected_today_session": True,
            "expected_live_session": today,
            "expected_confirmed_session": expected_confirmed,
        }
    return {
        "calendar_available": False,
        "expected_today_session": False,
        "expected_live_session": previous_business_day,
        "expected_confirmed_session": previous_business_day,
    }


def _cap_row_date_text(value: object, latest_confirmed: pd.Timestamp) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = pd.Timestamp(text).normalize()
    except Exception:
        return text
    if parsed > latest_confirmed:
        return latest_confirmed.date().isoformat()
    return parsed.date().isoformat()


def prepare_daily_for_signal(
    daily: pd.DataFrame,
    live: bool,
    now: datetime | None = None,
) -> pd.DataFrame:
    ordered = daily.copy()
    ordered["date"] = pd.to_datetime(ordered["date"])
    ordered = ordered.sort_values("date").reset_index(drop=True)
    if not live and len(ordered) >= 2 and _row_uses_unconfirmed_bar(ordered.iloc[-1], now):
        ordered = ordered.iloc[:-1].copy()
        latest_confirmed = pd.Timestamp(ordered["date"].iloc[-1]).normalize()
        if "common_last_date" in ordered.columns:
            ordered["common_last_date"] = latest_confirmed.date().isoformat()
        for code in ASSETS:
            col = f"last_date_{code}"
            if col in ordered.columns:
                ordered[col] = ordered[col].map(lambda value: _cap_row_date_text(value, latest_confirmed))
    if ordered.empty:
        raise poe.BotError("没有可用的已确认日线信号。")
    return ordered


def prepare_daily_for_performance(
    daily: pd.DataFrame,
    now: datetime | None = None,
) -> pd.DataFrame:
    return prepare_daily_for_signal(daily, live=False, now=now)


def signal_data_status(
    daily: pd.DataFrame,
    live: bool,
    now: datetime | None = None,
    purpose: Literal["execution", "performance"] = "execution",
) -> dict[str, object]:
    if purpose not in {"execution", "performance"}:
        raise ValueError(f"Unknown signal data status purpose: {purpose}")
    ts = _as_bj_datetime(now)
    latest = pd.Timestamp(daily["date"].max()).normalize()
    today = pd.Timestamp(ts.date()).normalize()
    sessions = _status_calendar_sessions(ts, latest)
    calendar_available = bool(sessions["calendar_available"])
    calendar_failure = _calendar_failure_reason() or "交易日历不可用，禁止生成实盘动作"
    if purpose == "execution" and not calendar_available and (
        "交易日历落后于行情数据" in calendar_failure or "行情最新日期不在交易日历" in calendar_failure
    ):
        raise RuntimeError(calendar_failure)
    if live and not calendar_available:
        raise RuntimeError(calendar_failure)
    expected_confirmed = pd.Timestamp(sessions["expected_confirmed_session"]).normalize()
    expected_live = pd.Timestamp(sessions["expected_live_session"]).normalize()
    expected_today_session = bool(sessions["expected_today_session"])
    live_data_available = bool(live and expected_today_session and latest >= expected_live)
    latest_row = daily.sort_values("date").iloc[-1]
    stale_price_trade_assets = _stale_price_trade_assets(latest_row)
    all_trade_legs_have_current_prices = not stale_price_trade_assets
    source_bar_is_final = _row_bool_value(latest_row, "source_bar_is_final", False)
    verified_final_close = _row_verified_final_close(latest_row, ts)
    final_close_execution_verified = bool(
        verified_final_close and _row_final_close_execution_verified(latest_row)
    )
    uses_unconfirmed = _row_uses_unconfirmed_bar(latest_row, ts)
    live_snapshot = _live_snapshot_freshness(latest_row, ts)
    quote_ts = _parse_quote_time(latest_row.get("source_quote_time", None))
    source_quote_time = _format_quote_time(quote_ts) or live_snapshot["latest_quote_time"]
    live_snapshot_fresh = bool(live_snapshot["live_snapshot_fresh"])
    official_close_ready = verified_final_close
    signal_uses_today_close = bool(latest == today and official_close_ready)
    post_close_signal_price_available = bool(
        signal_uses_today_close and final_close_execution_verified
    )
    non_live_execution_price_available = bool(
        POST_CLOSE_FIXED_PRICE_EXECUTION_ENABLED and post_close_signal_price_available
    )
    data_usable = True
    signal_valid = True
    if purpose == "execution" and not calendar_available:
        label = calendar_failure
        data_usable = False
        signal_valid = False
    elif latest < expected_confirmed:
        label = (
            f"数据滞后：最新应有确认日线 {expected_confirmed.date().isoformat()}，"
            f"实际仅到 {latest.date().isoformat()}"
        )
        data_usable = False
        signal_valid = False
    elif live and expected_today_session and latest < expected_live:
        label = "今日盘中快照尚不可用，最新为上一交易日收盘"
        live_data_available = False
        signal_valid = False
    elif uses_unconfirmed:
        if ts.time() >= CONFIRMED_CLOSE_CUTOFF:
            label = "已过收盘时间，但数据源最终bar尚未验证"
            if not live:
                data_usable = False
                signal_valid = False
        else:
            label = "盘中未确认"
    elif not expected_today_session:
        label = "市场今日休市；使用上一交易日确认收盘"
    else:
        label = "已确认收盘"
    signal_is_current_session = bool(latest == today)
    model_execution_price_available = bool(
        purpose == "execution"
        and signal_valid
        and data_usable
        and signal_is_current_session
        and all_trade_legs_have_current_prices
        and ((not live and non_live_execution_price_available) or (live and live_snapshot_fresh))
    )
    execution_enabled = bool(
        purpose == "execution"
        and signal_valid
        and data_usable
        and model_execution_price_available
        and all_trade_legs_have_current_prices
    )
    execution_legs = _execution_legs_status(
        daily,
        ts,
        expected_today_session,
        signal_price_is_available=post_close_signal_price_available,
        execution_enabled=execution_enabled,
    )
    fallback_execution_session = _execution_session_status(
        ts,
        expected_today_session,
        exchange="SSE",
        security_type="ETF",
    )
    raw_signal_has_trade = bool(execution_legs)
    if not raw_signal_has_trade:
        execution_session = "NO_TRADE"
    elif execution_legs:
        leg_sessions = [str(leg["execution_session"]) for leg in execution_legs]
        unique_leg_sessions = set(leg_sessions)
        execution_session = leg_sessions[0] if len(unique_leg_sessions) == 1 else "MIXED"
    else:
        execution_session = fallback_execution_session
    delayed_execution = bool(
        purpose == "execution"
        and signal_valid
        and data_usable
        and latest < today
        and raw_signal_has_trade
    )
    all_legs_can_submit = bool(
        raw_signal_has_trade and all(bool(leg["can_submit_order_now"]) for leg in execution_legs)
    )
    all_legs_can_match_immediately = bool(
        raw_signal_has_trade and all(bool(leg["can_match_immediately"]) for leg in execution_legs)
    )
    exchange_all_legs_can_submit = bool(
        raw_signal_has_trade and all(bool(leg["exchange_can_submit_order_now"]) for leg in execution_legs)
    )
    exchange_all_legs_can_match_immediately = bool(
        raw_signal_has_trade and all(bool(leg["exchange_can_match_immediately"]) for leg in execution_legs)
    )
    exchange_some_legs_can_match_immediately = bool(
        raw_signal_has_trade and any(bool(leg["exchange_can_match_immediately"]) for leg in execution_legs)
    )
    some_legs_can_match_immediately = bool(
        raw_signal_has_trade and any(bool(leg["can_match_immediately"]) for leg in execution_legs)
    )
    all_legs_can_use_post_close_fixed_price = bool(
        raw_signal_has_trade and all(bool(leg["can_use_post_close_fixed_price"]) for leg in execution_legs)
    )
    limit_blocked_trade_assets = sorted(
        {
            str(leg["asset"])
            for leg in execution_legs
            if any(
                reason in {"buy_at_limit_up", "sell_at_limit_down"}
                for reason in leg.get("execution_block_reasons", [])
            )
        }
    )
    sell_unavailable_trade_assets = sorted(
        {
            str(leg["asset"])
            for leg in execution_legs
            if "sell_available_not_verified" in leg.get("execution_block_reasons", [])
        }
    )
    partially_executable = bool(
        raw_signal_has_trade
        and exchange_some_legs_can_match_immediately
        and not exchange_all_legs_can_match_immediately
    )
    if raw_signal_has_trade:
        continuous_actionable_now = all_legs_can_match_immediately
        post_close_actionable_now = all_legs_can_use_post_close_fixed_price
        market_session_open = any(
            str(leg["execution_session"]) in {"OPEN_AM", "OPEN_PM"} for leg in execution_legs
        )
    else:
        continuous_actionable_now = False
        post_close_actionable_now = False
        market_session_open = bool(fallback_execution_session in {"OPEN_AM", "OPEN_PM"})
    can_submit_full_order_now = all_legs_can_submit
    can_complete_full_rebalance_now = bool(
        raw_signal_has_trade and (all_legs_can_match_immediately or post_close_actionable_now)
    )
    exchange_can_complete_full_rebalance_now = bool(
        raw_signal_has_trade and exchange_all_legs_can_match_immediately
    )
    actionable_now = bool(execution_enabled and can_complete_full_rebalance_now)
    exchange_can_execute_now = bool(raw_signal_has_trade and exchange_all_legs_can_submit)
    if ts.time() < LIVE_EXECUTION_START:
        strategy_execution_window_status = "BEFORE"
    elif ts.time() < LIVE_EXECUTION_END:
        strategy_execution_window_status = "OPEN"
    else:
        strategy_execution_window_status = "AFTER"
    strategy_execution_window_open = bool(live and strategy_execution_window_status == "OPEN")
    strategy_actionable_now = bool(
        execution_enabled
        and raw_signal_has_trade
        and not delayed_execution
        and ((not live) or (strategy_execution_window_open and live_snapshot_fresh))
        and (all_legs_can_submit or post_close_actionable_now)
    )
    action_required_now = bool(
        raw_signal_has_trade
        and signal_valid
        and data_usable
        and not delayed_execution
        and ((not live and model_execution_price_available) or (live and strategy_actionable_now))
    )
    bar_is_confirmed = bool(latest < today or verified_final_close)
    execution_note = ""
    if not signal_valid:
        execution_note = label
    elif purpose != "execution":
        actionable_now = False
        strategy_actionable_now = False
        execution_note = "绩效查询仅用于历史展示，不生成实盘动作。"
    elif not expected_today_session:
        actionable_now = False
        strategy_actionable_now = False
        execution_note = "市场今日休市；执行前应在下一交易日重新确认价格。"
    elif not raw_signal_has_trade:
        actionable_now = False
        strategy_actionable_now = False
        execution_note = "信号有效，无需下单。"
    elif delayed_execution:
        actionable_now = False
        strategy_actionable_now = False
        execution_note = "昨日调仓信号的模型成交时点已经过去；今日执行属于延迟执行，不包含在当前回测口径中。"
    elif stale_price_trade_assets:
        actionable_now = False
        strategy_actionable_now = False
        assets_text = ", ".join(stale_price_trade_assets)
        execution_note = f"调仓腿包含停牌/前值填充或滞后价格资产，当前不可执行: {assets_text}"
    elif live and strategy_execution_window_status == "BEFORE":
        actionable_now = False
        strategy_actionable_now = False
        execution_note = "实时估算信号，仅供监控；尚未进入策略执行窗口。"
    elif live and strategy_execution_window_status == "AFTER":
        actionable_now = False
        strategy_actionable_now = False
        execution_note = "实时估算信号，仅供监控；今日策略执行窗口已经结束。"
    elif live and live_snapshot["source_ineligible_assets"]:
        actionable_now = False
        strategy_actionable_now = False
        execution_note = "实时估算信号，仅供监控；实时行情来源尚未获得执行许可。"
    elif live and live_snapshot["non_executable_quote_assets"]:
        actionable_now = False
        strategy_actionable_now = False
        assets_text = ", ".join(live_snapshot["non_executable_quote_assets"])
        execution_note = f"实时估算信号，仅供监控；成交量/成交额未通过执行校验: {assets_text}"
    elif live and not live_snapshot_fresh:
        actionable_now = False
        strategy_actionable_now = False
        execution_note = "实时估算信号，仅供监控；全部ETF实时行情快照未通过新鲜度校验。"
    elif limit_blocked_trade_assets:
        actionable_now = False
        strategy_actionable_now = False
        assets_text = ", ".join(limit_blocked_trade_assets)
        execution_note = f"调仓腿触及方向性涨跌停限制，当前不按可立即执行处理: {assets_text}"
    elif sell_unavailable_trade_assets:
        actionable_now = False
        strategy_actionable_now = False
        assets_text = ", ".join(sell_unavailable_trade_assets)
        execution_note = f"卖出腿缺少券商可卖数量/T+1校验，当前不按可执行处理: {assets_text}"
    elif continuous_actionable_now:
        execution_note = "当前全部交易腿均处于连续竞价可即时撮合状态；仍需按实时价格、账户持仓和最小成交额复核。"
    elif post_close_actionable_now:
        execution_note = "当前全部交易腿均处于可用盘后固定价格交易状态；仅适用于支持盘后固定价格交易的ETF并需按收盘价委托。"
    elif all_legs_can_submit and not all_legs_can_match_immediately:
        execution_note = "当前可提交全部委托，但不能立即完成全部换仓；需等待集合竞价统一撮合。"
    elif execution_session == "POST_CLOSE" and not POST_CLOSE_FIXED_PRICE_EXECUTION_ENABLED:
        execution_note = "当前处于盘后固定价格交易时段，但盘后固定价格执行功能当前关闭，不输出可执行交易指令。"
    elif execution_session == "POST_CLOSE":
        execution_note = "当前处于盘后固定价格交易时段，但正式收盘价尚未通过验证，不输出可执行交易指令。"
    else:
        execution_note = "当前不能按模型收盘价成交并立即完成全部换仓；执行前需重新确认价格。"
    return {
        "label": label,
        "signal_date": latest.date().isoformat(),
        "latest_date": latest.date().isoformat(),
        "expected_latest_session": (expected_live if live else expected_confirmed).date().isoformat(),
        "expected_live_session": expected_live.date().isoformat(),
        "expected_confirmed_session": expected_confirmed.date().isoformat(),
        "actual_latest_session": latest.date().isoformat(),
        "calendar_available": calendar_available,
        "data_usable": data_usable,
        "signal_valid": signal_valid,
        "bar_is_confirmed": bar_is_confirmed,
        "official_close_ready": official_close_ready,
        "source_quote_time": source_quote_time,
        "source_bar_is_final": source_bar_is_final,
        "final_close_execution_verified": final_close_execution_verified,
        "all_asset_quotes_fresh": live_snapshot["all_asset_quotes_fresh"],
        "live_snapshot_fresh": live_snapshot_fresh,
        "all_quote_price_time_pairs_valid": live_snapshot["all_quote_price_time_pairs_valid"],
        "price_matrix_uses_live_quotes": live_snapshot["price_matrix_uses_live_quotes"],
        "max_quote_age_seconds": live_snapshot["max_quote_age_seconds"],
        "max_quote_time_skew_seconds": live_snapshot["max_quote_time_skew_seconds"],
        "latest_quote_time": live_snapshot["latest_quote_time"],
        "earliest_quote_time": live_snapshot["earliest_quote_time"],
        "missing_quote_assets": live_snapshot["missing_quote_assets"],
        "stale_quote_assets": live_snapshot["stale_quote_assets"],
        "price_mismatch_assets": live_snapshot["price_mismatch_assets"],
        "source_ineligible_assets": live_snapshot["source_ineligible_assets"],
        "non_executable_quote_assets": live_snapshot["non_executable_quote_assets"],
        "stale_price_trade_assets": stale_price_trade_assets,
        "limit_blocked_trade_assets": limit_blocked_trade_assets,
        "sell_unavailable_trade_assets": sell_unavailable_trade_assets,
        "all_trade_legs_have_current_prices": all_trade_legs_have_current_prices,
        "all_quote_sources_execution_eligible": live_snapshot["all_quote_sources_execution_eligible"],
        "signal_uses_today_close": signal_uses_today_close,
        "signal_is_current_session": signal_is_current_session,
        "model_execution_price_available": model_execution_price_available,
        "delayed_execution": delayed_execution,
        "raw_signal_has_trade": raw_signal_has_trade,
        "action_required_now": action_required_now,
        "action_required": raw_signal_has_trade,
        "all_legs_can_submit": all_legs_can_submit,
        "all_legs_can_match_immediately": all_legs_can_match_immediately,
        "some_legs_can_match_immediately": some_legs_can_match_immediately,
        "partially_executable": partially_executable,
        "exchange_can_execute_now": exchange_can_execute_now,
        "exchange_all_legs_can_submit": exchange_all_legs_can_submit,
        "exchange_all_legs_can_match_immediately": exchange_all_legs_can_match_immediately,
        "exchange_some_legs_can_match_immediately": exchange_some_legs_can_match_immediately,
        "exchange_can_complete_full_rebalance_now": exchange_can_complete_full_rebalance_now,
        "can_submit_full_order_now": can_submit_full_order_now,
        "can_complete_full_rebalance_now": can_complete_full_rebalance_now,
        "strategy_execution_window_status": strategy_execution_window_status,
        "strategy_execution_window_open": strategy_execution_window_open,
        "strategy_actionable_now": strategy_actionable_now,
        "actionable_now": actionable_now,
        "continuous_actionable_now": continuous_actionable_now,
        "post_close_actionable_now": post_close_actionable_now,
        "market_session_open": market_session_open,
        "execution_session": execution_session,
        "execution_legs": execution_legs,
        "market_open_now": market_session_open,
        "uses_unconfirmed_bar": uses_unconfirmed,
        "live_data_available": live_data_available,
        "tradable": strategy_actionable_now,
        "execution_note": execution_note,
        "now_bj": ts.strftime("%Y-%m-%d %H:%M"),
    }


def _get_daily_for_today(force_refresh: bool = False, data_state: str = "confirmed") -> tuple[pd.DataFrame, str]:
    date_key = _now_bj().date().isoformat()
    key = _daily_cache_key(date_key, data_state)
    if force_refresh:
        now = _now_bj()
        try:
            daily, source_name = _call_build_v11_daily(pd.Timestamp(date_key), data_state, now)
            daily = _with_cache_metadata(daily, now)
            with _DAILY_CACHE_LOCK:
                _DAILY_CACHE[key] = (now, daily, source_name)
        except Exception as exc:
            with _DAILY_CACHE_LOCK:
                cached = _DAILY_CACHE.get(key)
            if cached is None:
                raise
            cached_at, daily, source_name = cached
            source_name = _refresh_failed_cache_note(source_name, cached_at, exc)
    else:
        daily, source_name = _cached_daily(date_key, data_state=data_state)
    return daily.copy(), source_name


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
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if text.lower() in {"", "none", "nan", "nat", "<na>"}:
        return None
    return text


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
    overheat_scale_effective = _float(row.get("overheat_scale_effective"), default=1.0)
    overheat_scale_next = _float(row.get("overheat_scale_next"), default=_float(row.get("overheat_scale"), default=1.0))
    weight = _float(row.get("weight"), default=1.0)
    final_exposure = _float(row.get("final_exposure_after_overheat"), default=math.nan)
    exposure_effective = _float(row.get("exposure_effective"), default=math.nan)
    drifted_exposure = _float(row.get("drifted_exposure_before_trade"), default=exposure_effective)
    rebalance_delta = _float(row.get("rebalance_delta"), default=final_exposure - drifted_exposure)
    buy_delta = _float(row.get("buy_delta"), default=max(rebalance_delta, 0.0))
    sell_delta = _float(row.get("sell_delta"), default=max(-rebalance_delta, 0.0))
    base_position_before = str(row.get("base_position_before", row.get("position_before", "")))
    base_position_next = str(row.get("base_position_next", row.get("position", "")))
    actual_position_before = str(
        row.get(
            "actual_position_before",
            base_position_before if exposure_effective > 1e-12 else "CASH",
        )
    )
    actual_position_next = str(
        row.get(
            "actual_position_next",
            base_position_next if final_exposure > 1e-12 else "CASH",
        )
    )
    return {
        "version": str(row["version"]),
        "date": pd.Timestamp(row["date"]).date().isoformat(),
        "position_before": str(row.get("position_before", "")),
        "position": str(row.get("position", "")),
        "base_position_before": base_position_before,
        "base_position_next": base_position_next,
        "actual_position_before": actual_position_before,
        "actual_position_next": actual_position_next,
        "trade_target": _empty_to_none(row.get("trade_target")),
        "trade_fraction": _float(row.get("trade_fraction"), default=math.nan),
        "holding_fraction": _float(row.get("holding_fraction"), default=math.nan),
        "best_candidate": str(row.get("best_candidate", "")),
        "best_candidate_score": _float(row.get("best_candidate_score"), default=math.nan),
        "current_score": _float(row.get("current_score"), default=math.nan),
        "buffer_blocked": _bool(row.get("buffer_blocked")),
        "nav": _float(row.get("nav"), default=math.nan),
        "daily_return": _float(row.get("return"), default=math.nan),
        "target_vol_scale": weight,
        "target_vol_scale_effective": _float(row.get("target_vol_scale_effective"), default=weight),
        "target_vol_scale_next": _float(row.get("target_vol_scale_next"), default=weight),
        "overheat_scale": overheat_scale_next,
        "overheat_scale_effective": overheat_scale_effective,
        "overheat_scale_next": overheat_scale_next,
        "execution_scale": weight * overheat_scale_next,
        "final_exposure": final_exposure,
        "exposure_effective": _float(row.get("exposure_effective"), default=math.nan),
        "drifted_exposure_before_trade": drifted_exposure,
        "rebalance_delta": rebalance_delta,
        "buy_delta": buy_delta,
        "sell_delta": sell_delta,
        "turnover": _float(row.get("turnover"), default=0.0),
        "cost": _float(row.get("cost"), default=0.0),
        "overheat_on": _bool(row.get("overheat_on")),
        "overheat_on_effective": _bool(row.get("overheat_on_effective")),
        "overheat_triggered": _bool(row.get("overheat_triggered")),
        "overheat_recovered": _bool(row.get("overheat_recovered")),
        "overheat_feature_missing": _bool(row.get("overheat_feature_missing")),
        "common_last_date": str(row.get("common_last_date", "")),
    }


def _daily_returns_for_window(sub: pd.DataFrame) -> pd.Series:
    if "return" in sub.columns:
        ret = pd.to_numeric(sub["return"], errors="coerce")
        if len(ret) > 1 and ret.iloc[1:].isna().any():
            missing_dates = ", ".join(
                pd.Timestamp(value).date().isoformat()
                for value in sub.loc[ret.isna(), "date"].iloc[:6]
            )
            raise poe.BotError(f"missing return inside performance window: {missing_dates}")
        ret = ret.fillna(0.0)
        out = pd.Series(ret.to_numpy(dtype=float), index=sub.index, dtype=float)
        if not out.empty:
            out.iloc[0] = 0.0
        return out
    nav = pd.to_numeric(sub["nav"], errors="coerce").astype(float)
    if nav.isna().any():
        missing_dates = ", ".join(
            pd.Timestamp(value).date().isoformat()
            for value in sub.loc[nav.isna(), "date"].iloc[:6]
        )
        raise poe.BotError(f"missing nav inside performance window: {missing_dates}")
    return nav.pct_change(fill_method=None).fillna(0.0)


def _wealth_from_returns(ret: pd.Series) -> pd.Series:
    return (1.0 + ret.astype(float)).cumprod()


def _drawdown_from_wealth(wealth: pd.Series) -> pd.Series:
    wealth = wealth.astype(float)
    peak = wealth.cummax()
    return wealth / peak - 1.0


def calc_performance(daily: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, object]:
    start = pd.Timestamp(start).normalize()
    end = pd.Timestamp(end).normalize()
    sub = daily[(daily["date"] >= start) & (daily["date"] <= end)].copy()
    if sub.empty:
        raise poe.BotError(f"在 {start.date()} 到 {end.date()} 期间没有 v1.1 数据。")
    ret = _daily_returns_for_window(sub)
    wealth = _wealth_from_returns(ret)
    years = max(len(sub) / TRADING_DAYS, 1.0 / TRADING_DAYS)
    std = ret.std(ddof=0)
    drawdown = _drawdown_from_wealth(wealth)
    exposure_col = "exposure_effective" if "exposure_effective" in sub.columns else "final_exposure_after_overheat"
    final_exposure = sub[exposure_col].astype(float).fillna(0.0)
    overheat_col = "overheat_on_effective" if "overheat_on_effective" in sub.columns else "overheat_on"
    return {
        "start": pd.Timestamp(sub["date"].iloc[0]).date().isoformat(),
        "end": pd.Timestamp(sub["date"].iloc[-1]).date().isoformat(),
        "rows": int(len(sub)),
        "total": float(wealth.iloc[-1] - 1.0),
        "annual": float(wealth.iloc[-1] ** (1.0 / years) - 1.0),
        "maxdd": float(drawdown.min()),
        "vol": float(std * math.sqrt(TRADING_DAYS)),
        "sharpe": float(ret.mean() / std * math.sqrt(TRADING_DAYS)) if std > 0 else math.nan,
        "trades": int((sub["turnover"].astype(float) > 1e-12).sum()),
        "avg_scale": float(sub["weight"].astype(float).mean()),
        "avg_final_exposure": float(final_exposure.mean()),
        "cash_days": int((sub["position"].astype(str) == "CASH").sum()),
        "zero_exposure_days": int((final_exposure <= 1e-12).sum()),
        "overheat_days": int(sub[overheat_col].astype(str).str.lower().eq("true").sum()),
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
    sub["_report_return"] = _daily_returns_for_window(sub).to_numpy(dtype=float)
    rows: list[dict[str, object]] = []
    for year, part in sub.groupby(sub["date"].dt.year):
        if part.empty:
            continue
        ret = part["_report_return"].astype(float)
        wealth = _wealth_from_returns(ret)
        std = ret.std(ddof=0)
        dd = _drawdown_from_wealth(wealth)
        trades = int((part["turnover"].astype(float) > 1e-12).sum()) if "turnover" in part.columns else 0
        exposure_col = "exposure_effective" if "exposure_effective" in part.columns else "final_exposure_after_overheat"
        avg_exposure = float(part[exposure_col].astype(float).fillna(0.0).mean()) if exposure_col in part.columns else math.nan
        rows.append(
            {
                "year": int(year),
                "start": pd.Timestamp(part["date"].iloc[0]).date().isoformat(),
                "end": pd.Timestamp(part["date"].iloc[-1]).date().isoformat(),
                "rows": int(len(part)),
                "return": float(wealth.iloc[-1] - 1.0),
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


def _checked_timestamp(year: int, month: int, day: int, raw: str) -> pd.Timestamp:
    if month < 1 or month > 12:
        raise ValueError(f"非法日期: {raw}")
    try:
        return pd.Timestamp(year=int(year), month=int(month), day=int(day))
    except ValueError as exc:
        raise ValueError(f"非法日期: {raw}") from exc


def _month_start(year: int, month: int, raw: str) -> pd.Timestamp:
    return _checked_timestamp(year, month, 1, raw)


def _month_end(year: int, month: int, raw: str) -> pd.Timestamp:
    return _month_start(year, month, raw) + pd.offsets.MonthEnd(0)


def _reject_invalid_explicit_date(text: str) -> None:
    raw_text = str(text or "")
    for match in re.finditer(r"(?<!\d)(\d{4})[-年/.](\d{1,2})[-月/.](\d{1,2})\s*[日号]?", raw_text):
        _checked_timestamp(int(match.group(1)), int(match.group(2)), int(match.group(3)), match.group(0))
    for match in re.finditer(r"(?<!\d)(\d{4})[-年/.](\d{1,2})(?:\s*月?份?)?(?!\d)", raw_text):
        month = int(match.group(2))
        if month < 1 or month > 12:
            raise ValueError(f"非法日期: {match.group(0)}")


def parse_date_range(text, now=None):
    _reject_invalid_explicit_date(str(text or ""))
    now = _bj_today_naive() if now is None else _normalize_query_date(now)
    day_suffix = r"[日号]?"

    def _explicit_range(start: pd.Timestamp, end: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
        if end < start:
            raise ValueError("结束日期不能早于开始日期")
        return start, end

    def _build_explicit_year_date_range(m):
        start = _checked_timestamp(int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(0))
        end = _checked_timestamp(int(m.group(4)), int(m.group(5)), int(m.group(6)), m.group(0))
        return _explicit_range(start, end)

    def _build_year_to_month_day(m):
        year = int(m.group(1))
        start = _checked_timestamp(year, int(m.group(2)), int(m.group(3)), m.group(0))
        end = _checked_timestamp(year, int(m.group(4)), int(m.group(5)), m.group(0))
        if end < start:
            end = _checked_timestamp(year + 1, int(m.group(4)), int(m.group(5)), m.group(0))
        return start, end

    # YYYY-MM-DD ~ YYYY-MM-DD
    patterns = [
        (
            r"(\d{4})[-年/.](\d{1,2})[-月/.](\d{1,2})\s*"
            + day_suffix + r"\s*[到至—\-~]+\s*(\d{4})[-年/.](\d{1,2})[-月/.](\d{1,2})\s*" + day_suffix,
            _build_explicit_year_date_range,
        ),
        (
            r"(\d{4})[-年/.](\d{1,2})[-月/.](\d{1,2})\s*"
            + day_suffix + r"\s*[到至—\-~]+\s*(\d{1,2})[-月/.](\d{1,2})\s*" + day_suffix,
            _build_year_to_month_day,
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
        start = _checked_timestamp(year, int(match.group(1)), int(match.group(2)), match.group(0))
        end = _checked_timestamp(year, int(match.group(3)), int(match.group(4)), match.group(0))
        if start > end:
            start = _checked_timestamp(year - 1, int(match.group(1)), int(match.group(2)), match.group(0))
            end = _checked_timestamp(year, int(match.group(3)), int(match.group(4)), match.group(0))
        return start, end

    # YYYY-MM-DD至今
    match = re.search(r"(\d{4})[-年/.](\d{1,2})[-月/.](\d{1,2})\s*" + day_suffix + r"\s*至今", text)
    if match:
        return _checked_timestamp(int(match.group(1)), int(match.group(2)), int(match.group(3)), match.group(0)), now
    # Standalone YYYY-MM-DD
    match = re.search(
        r"(?<!\d)(\d{4})[-年/.](\d{1,2})[-月/.](\d{1,2})\s*" + day_suffix,
        text,
    )
    if match:
        day = _checked_timestamp(
            int(match.group(1)), int(match.group(2)), int(match.group(3)), match.group(0)
        )
        return day, day
    # MM-DD至今
    match = re.search(r"(\d{1,2})[-月/.](\d{1,2})\s*" + day_suffix + r"\s*至今", text)
    if match:
        start = _checked_timestamp(now.year, int(match.group(1)), int(match.group(2)), match.group(0))
        if start > now:
            start = _checked_timestamp(now.year - 1, int(match.group(1)), int(match.group(2)), match.group(0))
        return start, now
    # YYYY-MM至今
    match = re.search(r"(\d{4})[-年/.]?(\d{1,2})[-月]?\s*至今", text)
    if match:
        return _month_start(int(match.group(1)), int(match.group(2)), match.group(0)), now
    # YYYY至今
    match = re.search(r"(\d{4})\s*年?\s*至今", text)
    if match:
        return pd.Timestamp(f"{match.group(1)}-01-01"), now

    # YYYY-MM ~ YYYY-MM
    match = re.search(r"(\d{4})[-年/.](\d{1,2})[-月]?\s*[到至—\-~]+\s*(\d{4})[-年/.](\d{1,2})", text)
    if match:
        start = _month_start(int(match.group(1)), int(match.group(2)), match.group(0))
        end = _month_end(int(match.group(3)), int(match.group(4)), match.group(0))
        return _explicit_range(start, end)
    # YYYY-MM ~ MM (same year)
    match = re.search(r"(\d{4})[-年/.](\d{1,2})[-月]?\s*[到至—\-~]+\s*(\d{1,2})", text)
    if match:
        year = int(match.group(1))
        start_month = int(match.group(2))
        end_month = int(match.group(3))
        start = _month_start(year, start_month, match.group(0))
        end_year = year + 1 if end_month < start_month else year
        end = _month_end(end_year, end_month, match.group(0))
        return start, end
    # YYYYMM ~ YYYYMM
    match = re.search(r"(\d{4})(\d{2})\s*[-到至~]+\s*(\d{4})(\d{2})", text)
    if match:
        start = _month_start(int(match.group(1)), int(match.group(2)), match.group(0))
        end = _month_end(int(match.group(3)), int(match.group(4)), match.group(0))
        return _explicit_range(start, end)
    # YYYY ~ YYYY
    match = re.search(r"(\d{4})\s*年?\s*[到至—\-~]+\s*(\d{4})\s*年?", text)
    if match:
        start = pd.Timestamp(f"{match.group(1)}-01-01")
        end = pd.Timestamp(f"{match.group(2)}-12-31")
        return _explicit_range(start, end)

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
        start = _month_start(year, month, match.group(0))
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
    # Realtime signal/parameter requests intentionally take priority over chart words.
    if "实时信号" in compact or "信号实时" in compact:
        return "live_signal"
    if "实时参数" in compact or "参数实时" in compact:
        return "live_params"
    if re.search(r"交易记录|调仓记录|成交记录|换仓记录", query):
        return "performance"
    if re.search(r"净值曲线|收益曲线|走势", query):
        return "performance"
    if re.search(r"表现|收益(?!曲线)|回撤|年化|夏普|回报|绩效", query):
        return "performance"
    if "参数" in query:
        return "params"
    if "信号" in query:
        return "signal"
    return "signal"


MANDATORY_PERFORMANCE_LABELS = {"full_sample", "10Y", "5Y", "3Y", "1Y"}
MANDATORY_WINDOW_TRADING_DAYS = {
    "10Y": 10 * TRADING_DAYS,
    "5Y": 5 * TRADING_DAYS,
    "3Y": 3 * TRADING_DAYS,
    "1Y": TRADING_DAYS,
}


def _eval_start_label() -> str:
    return f"from_{EVAL_START.year}"


def _default_performance_ranges(
    latest: pd.Timestamp,
    earliest: pd.Timestamp | None = None,
) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    ranges: list[tuple[str, pd.Timestamp, pd.Timestamp]] = []
    if earliest is not None:
        ranges.append(("full_sample", earliest, latest))
    ranges.extend(
        [
            ("10Y", latest - pd.DateOffset(years=10), latest),
            ("5Y", latest - pd.DateOffset(years=5), latest),
            ("3Y", latest - pd.DateOffset(years=3), latest),
            ("1Y", latest - pd.DateOffset(years=1), latest),
            (_eval_start_label(), EVAL_START, latest),
        ]
    )
    return ranges


def trading_day_window_start(index: pd.Index, end: pd.Timestamp, trading_days: int) -> pd.Timestamp:
    ordered = pd.DatetimeIndex(index).normalize().sort_values()
    eligible = ordered[ordered <= pd.Timestamp(end).normalize()]
    if eligible.empty:
        raise ValueError(f"No trading dates on or before {pd.Timestamp(end).date()}")
    pos = len(eligible) - 1
    start_pos = max(0, pos - int(trading_days) + 1)
    return pd.Timestamp(eligible[start_pos])


def _default_performance_ranges_for_daily(
    daily: pd.DataFrame,
    latest: pd.Timestamp,
    earliest: pd.Timestamp | None = None,
) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    dates = pd.DatetimeIndex(pd.to_datetime(daily["date"])).normalize().sort_values()
    ranges: list[tuple[str, pd.Timestamp, pd.Timestamp]] = []
    if earliest is not None:
        ranges.append(("full_sample", earliest, latest))
    for label, years in (("10Y", 10), ("5Y", 5), ("3Y", 3), ("1Y", 1)):
        ranges.append((label, trading_day_window_start(dates, latest, years * TRADING_DAYS), latest))
    ranges.append((_eval_start_label(), EVAL_START, latest))
    return ranges


def resolve_performance_ranges(
    query: str,
    now=None,
    latest_date=None,
    earliest_date=None,
) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    now = _bj_today_naive() if now is None else _normalize_query_date(now)
    latest = now if latest_date is None else _normalize_query_date(latest_date)
    earliest = None if earliest_date is None else _normalize_query_date(earliest_date)
    parsed = parse_all_date_ranges(query, now=now)
    ranges: list[tuple[str, pd.Timestamp, pd.Timestamp]] = []
    if parsed:
        ranges.extend((f"{s.date()}~{e.date()}", s, e) for s, e in parsed)
    seen = {(label, pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()) for label, start, end in ranges}
    for item in _default_performance_ranges(latest, earliest):
        key = (item[0], pd.Timestamp(item[1]).normalize(), pd.Timestamp(item[2]).normalize())
        if key not in seen:
            ranges.append(item)
            seen.add(key)
    return ranges


def resolve_performance_ranges_for_daily(
    query: str,
    daily: pd.DataFrame,
    now=None,
    latest_date=None,
    earliest_date=None,
) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    now = _bj_today_naive() if now is None else _normalize_query_date(now)
    latest = now if latest_date is None else _normalize_query_date(latest_date)
    earliest = None if earliest_date is None else _normalize_query_date(earliest_date)
    parsed = parse_all_date_ranges(query, now=now)
    ranges: list[tuple[str, pd.Timestamp, pd.Timestamp]] = []
    if parsed:
        ranges.extend((f"{s.date()}~{e.date()}", s, e) for s, e in parsed)
    seen = {(label, pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()) for label, start, end in ranges}
    for item in _default_performance_ranges_for_daily(daily, latest, earliest):
        key = (item[0], pd.Timestamp(item[1]).normalize(), pd.Timestamp(item[2]).normalize())
        if key not in seen:
            ranges.append(item)
            seen.add(key)
    return ranges


def _exception_na_reason(exc: Exception) -> str:
    reason = str(exc).strip() or exc.__class__.__name__
    return reason.replace("|", "/")[:120]


def _mandatory_window_na_reason(
    label: str,
    start: pd.Timestamp,
    earliest: pd.Timestamp,
    available_rows: int | None = None,
) -> str | None:
    required_rows = MANDATORY_WINDOW_TRADING_DAYS.get(label)
    if (
        required_rows is not None
        and available_rows is not None
        and available_rows < required_rows
    ):
        return f"insufficient history: {available_rows} rows < {required_rows} trading days"
    if required_rows is not None and earliest > pd.Timestamp(start).normalize():
        return (
            f"insufficient history: first available {earliest.date().isoformat()} "
            f"after required {pd.Timestamp(start).date().isoformat()}"
        )
    return None


# ════════════════════════════════════════════════════════════════
#  Bot class
# ════════════════════════════════════════════════════════════════

def _fmt_bool_status(value: bool, on_text: str, off_text: str) -> str:
    return on_text if bool(value) else off_text


def _signal_action_text(
    sig: dict[str, object],
    *,
    target_exposure_label: str = "收盘后目标敞口",
) -> str:
    previous = _asset_name(str(sig.get("actual_position_before", sig.get("position_before", ""))))
    target = _asset_name(str(sig.get("actual_position_next", sig.get("position", ""))))
    base_previous = _asset_name(str(sig.get("base_position_before", sig.get("position_before", ""))))
    base_target = _asset_name(str(sig.get("base_position_next", sig.get("position", ""))))
    old_exp = _float(sig.get("exposure_effective"), default=math.nan)
    drifted_exp = _float(sig.get("drifted_exposure_before_trade"), default=old_exp)
    new_exp = _float(sig.get("final_exposure"), default=math.nan)
    buy_delta = _float(sig.get("buy_delta"), default=0.0)
    sell_delta = _float(sig.get("sell_delta"), default=0.0)
    turnover = _float(sig.get("turnover"), default=0.0)
    base_note = f"base virtual target: {base_previous} -> {base_target}"
    action_parts: list[str] = []
    if sell_delta > 1e-12:
        action_parts.append(f"卖出 {previous}，约占净值 {_fmt_pct(sell_delta)}")
    if buy_delta > 1e-12:
        action_parts.append(f"买入 {target}，约占净值 {_fmt_pct(buy_delta)}")
    if action_parts:
        action_parts.append(f"漂移后敞口 {_fmt_pct(drifted_exp)}")
        action_parts.append(f"{target_exposure_label} {_fmt_pct(new_exp)}")
        action_parts.append(base_note)
        return "；".join(action_parts)
    if turnover > 1e-12:
        return f"调仓金额低于显示阈值；漂移后敞口 {_fmt_pct(drifted_exp)}，{target_exposure_label} {_fmt_pct(new_exp)}；{base_note}"
    if new_exp <= 1e-12:
        return f"不买入，保持CASH/0敞口；{base_note}"
    return f"不调仓：持有 {target}，敞口 {_fmt_pct(new_exp)}"


def _trade_action_label(sig: dict[str, object]) -> str:
    buy_delta = _float(sig.get("buy_delta"), default=0.0)
    sell_delta = _float(sig.get("sell_delta"), default=0.0)
    parts: list[str] = []
    if sell_delta > 1e-12:
        parts.append(f"卖出 {_fmt_pct(sell_delta)} NAV")
    if buy_delta > 1e-12:
        parts.append(f"买入 {_fmt_pct(buy_delta)} NAV")
    if parts:
        return " / ".join(parts)
    old_exp = _float(sig.get("exposure_effective"), default=0.0)
    new_exp = _float(sig.get("final_exposure"), default=math.nan)
    if old_exp <= 1e-12 and new_exp <= 1e-12:
        return "\u4e0d\u4e70\u5165\uff0c\u4fdd\u63010\u655e\u53e3"
    return "不调仓" if _float(sig.get("turnover"), default=0.0) <= 1e-12 else "调仓金额低于显示阈值"


def _signal_rank_rows(daily: pd.DataFrame, limit: int = 6) -> list[dict[str, object]]:
    row = daily.sort_values("date").iloc[-1]
    rows: list[dict[str, object]] = []
    for code in ASSETS:
        raw_score = _float(row.get(f"raw_score_{code}"), default=math.nan)
        eligible_score = _float(row.get(f"score_{code}"), default=math.nan)
        r2 = _float(row.get(f"r2_{code}"), default=math.nan)
        eligible = not pd.isna(eligible_score)
        rows.append(
            {
                "code": code,
                "name": _asset_name(code),
                "score": raw_score if not pd.isna(raw_score) else eligible_score,
                "raw_score": raw_score,
                "eligible_score": eligible_score,
                "eligible": eligible,
                "r2": r2,
            }
        )
    rows.sort(
        key=lambda item: (
            bool(item["eligible"]),
            item["eligible_score"] if not pd.isna(item["eligible_score"]) else float("-inf"),
            item["raw_score"] if not pd.isna(item["raw_score"]) else float("-inf"),
        ),
        reverse=True,
    )
    return rows[:limit]


def _display_score(raw_score: float, eligible_score: float) -> float:
    return raw_score if not pd.isna(raw_score) else eligible_score


def _score_red_light_lines(daily: pd.DataFrame) -> list[str]:
    lines: list[str] = []
    for item in _signal_rank_rows(daily, limit=len(ASSETS)):
        raw_score = _float(item["raw_score"], default=math.nan)
        r2 = _float(item["r2"], default=math.nan)
        if pd.isna(raw_score) or pd.isna(r2) or raw_score < SCORE_MAX:
            continue
        code = str(item["code"])
        lines.append(
            f"- 红灯: **{_asset_name(code)}** Raw Score **{_fmt_num(raw_score, 4)}** ≥ {SCORE_MAX:.0f}，"
            "仅展示，不进入候选池。"
        )
    return lines


def _last_base_signal_date(daily: pd.DataFrame) -> str:
    ordered = daily.sort_values("date")
    if "trade_target" not in ordered.columns:
        return "no base signal"
    changed = ordered[ordered["trade_target"].apply(lambda value: _empty_to_none(value) is not None)]
    if changed.empty:
        return "no base signal"
    return pd.Timestamp(changed.iloc[-1]["date"]).date().isoformat()


def _last_actual_trade_date(daily: pd.DataFrame) -> str:
    ordered = daily.sort_values("date")
    if "turnover" not in ordered.columns:
        return "no actual trade"
    turnover = pd.to_numeric(ordered["turnover"], errors="coerce").fillna(0.0)
    changed = ordered[turnover > 1e-12]
    if changed.empty:
        return "no actual trade"
    return pd.Timestamp(changed.iloc[-1]["date"]).date().isoformat()


def _last_signal_date(daily: pd.DataFrame) -> str:
    return _last_actual_trade_date(daily)


def _trade_note(row: pd.Series) -> str:
    notes: list[str] = []
    if _bool(row.get("staged_initial")):
        notes.append(f"新资产先建{INITIAL_ENTRY_FRACTION:.0%}")
    if _bool(row.get("fill_on_down_day")):
        notes.append("下跌日补仓")
    if not notes and _empty_to_none(row.get("trade_target")) is None:
        old_exposure = _float(row.get("exposure_effective"), default=0.0)
        drifted_exposure = _float(row.get("drifted_exposure_before_trade"), default=old_exposure)
        new_exposure = _float(row.get("final_exposure_after_overheat"), default=0.0)
        buy_delta = _float(row.get("buy_delta"), default=max(new_exposure - drifted_exposure, 0.0))
        sell_delta = _float(row.get("sell_delta"), default=max(drifted_exposure - new_exposure, 0.0))
        if sell_delta > 1e-12 and buy_delta <= 1e-12 and abs(old_exposure - new_exposure) <= 1e-12:
            notes.append("漂移再平衡卖出")
        elif buy_delta > 1e-12 and sell_delta <= 1e-12 and abs(old_exposure - new_exposure) <= 1e-12:
            notes.append("漂移再平衡买入")
        elif old_exposure > 1e-12 and new_exposure <= 1e-12:
            notes.append("有效敞口清零")
        elif old_exposure <= 1e-12 and new_exposure > 1e-12:
            notes.append("恢复有效敞口")
        elif new_exposure < old_exposure - 1e-12:
            notes.append("降低有效敞口")
        elif new_exposure > old_exposure + 1e-12:
            notes.append("提高有效敞口")
        else:
            notes.append("scale调整")
    return " / ".join(notes) if notes else "-"


def _trade_operation_text(row: pd.Series) -> str:
    previous_code = str(row.get("actual_position_before", row.get("position_before", "")))
    target_code = str(row.get("actual_position_next", row.get("position", "")))
    previous = _asset_name(previous_code)
    target = _asset_name(target_code)
    old_exposure = _float(row.get("exposure_effective"), default=0.0)
    drifted_exposure = _float(row.get("drifted_exposure_before_trade"), default=old_exposure)
    new_exposure = _float(row.get("final_exposure_after_overheat"), default=0.0)
    buy_delta = _float(row.get("buy_delta"), default=max(new_exposure - drifted_exposure, 0.0))
    sell_delta = _float(row.get("sell_delta"), default=max(drifted_exposure - new_exposure, 0.0))

    if previous_code == target_code:
        if buy_delta > 1e-12:
            return f"补: {target} (buy {_fmt_pct(buy_delta)} NAV)"
        if sell_delta > 1e-12:
            return f"减: {target} (sell {_fmt_pct(sell_delta)} NAV)"
        return f"调: {target}"

    parts: list[str] = []
    if previous_code != "CASH" and sell_delta > 1e-12:
        parts.append(f"减: {previous} ({_fmt_pct(sell_delta)} NAV)")
    if target_code != "CASH" and buy_delta > 1e-12:
        parts.append(f"加: {target} ({_fmt_pct(buy_delta)} NAV)")
    return " / ".join(parts) if parts else "调: CASH"


def format_trade_records_table(
    daily: pd.DataFrame,
    limit: int = 20,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> str:
    records = trade_records_frame(daily, start=start, end=end)
    total = len(records)

    lines: list[str] = [f"### 调仓记录 ({total}条)", ""]
    if records.empty:
        lines.append("该时段无调仓记录")
        return "\n".join(lines) + "\n"

    lines.append("| 日期 | 策略 | 操作 | 基础仓位 | 日初敞口 | 漂移后敞口 | 收盘目标敞口 | 买入 | 卖出 | 换手 | 成本 | 说明 |")
    lines.append("|:-|:-|:-|--:|--:|--:|--:|--:|--:|--:|--:|:-|")
    for _, row in records.head(limit).iterrows():
        lines.append(
            f"| {row['date']} | {row['strategy']} | {row['operation']} | "
            f"{_fmt_pct(row['fraction_before'])} -> {_fmt_pct(row['holding_fraction'])} | "
            f"{_fmt_pct(row['exposure_effective'])} | "
            f"{_fmt_pct(row['drifted_exposure_before_trade'])} | "
            f"{_fmt_pct(row['final_exposure_after_overheat'])} | "
            f"{_fmt_pct(row['buy_delta'])} | "
            f"{_fmt_pct(row['sell_delta'])} | "
            f"{_fmt_pct(row['turnover'])} | "
            f"{_fmt_pct(row['cost'], 3)} | {row['note']} |"
        )
    if total > limit:
        lines.append("")
        lines.append(f"（仅显示最近{limit}条）")
    return "\n".join(lines) + "\n"


def trade_records_frame(
    daily: pd.DataFrame,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> pd.DataFrame:
    data = daily.copy()
    data["date"] = pd.to_datetime(data["date"])
    if start is not None:
        data = data[data["date"] >= pd.Timestamp(start).normalize()]
    if end is not None:
        data = data[data["date"] <= pd.Timestamp(end).normalize()]
    if "base_position_before" not in data.columns:
        data["base_position_before"] = data.get("position_before", "CASH")
    if "base_position_next" not in data.columns:
        data["base_position_next"] = data.get("position", "CASH")
    if "drifted_exposure_before_trade" not in data.columns:
        data["drifted_exposure_before_trade"] = pd.to_numeric(
            data.get("exposure_effective", 0.0), errors="coerce"
        ).fillna(0.0)
    if "rebalance_delta" not in data.columns:
        data["rebalance_delta"] = (
            pd.to_numeric(data.get("final_exposure_after_overheat", 0.0), errors="coerce").fillna(0.0)
            - pd.to_numeric(data["drifted_exposure_before_trade"], errors="coerce").fillna(0.0)
        )
    if "actual_position_before" not in data.columns:
        exposure_before = pd.to_numeric(data.get("exposure_effective", 0.0), errors="coerce").fillna(0.0)
        data["actual_position_before"] = np.where(
            exposure_before.to_numpy(dtype=float) > 1e-12,
            data.get("position_before", "CASH"),
            "CASH",
        )
    if "actual_position_next" not in data.columns:
        exposure_next = pd.to_numeric(data.get("final_exposure_after_overheat", 0.0), errors="coerce").fillna(0.0)
        data["actual_position_next"] = np.where(
            exposure_next.to_numpy(dtype=float) > 1e-12,
            data.get("position", "CASH"),
            "CASH",
        )
    same_asset = (
        data["actual_position_before"].astype(str).eq(data["actual_position_next"].astype(str))
        & data["actual_position_before"].astype(str).ne("CASH")
    )
    drifted = pd.to_numeric(data["drifted_exposure_before_trade"], errors="coerce").fillna(0.0)
    final_exposure = pd.to_numeric(data.get("final_exposure_after_overheat", 0.0), errors="coerce").fillna(0.0)
    rebalance = pd.to_numeric(data["rebalance_delta"], errors="coerce").fillna(0.0)
    if "buy_delta" not in data.columns:
        data["buy_delta"] = pd.Series(
            np.where(same_asset, rebalance.clip(lower=0.0), final_exposure),
            index=data.index,
            dtype=float,
        )
    if "sell_delta" not in data.columns:
        data["sell_delta"] = pd.Series(
            np.where(same_asset, (-rebalance).clip(lower=0.0), drifted),
            index=data.index,
            dtype=float,
        )
    turnover = pd.to_numeric(data.get("turnover", 0.0), errors="coerce").fillna(0.0)
    records = data[turnover > 1e-12].sort_values("date", ascending=False)
    if records.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "strategy",
                "operation",
                "base_position_before",
                "base_position_next",
                "actual_position_before",
                "actual_position_next",
                "position_before_name",
                "position_name",
                "fraction_before",
                "holding_fraction",
                "exposure_effective",
                "drifted_exposure_before_trade",
                "final_exposure_after_overheat",
                "rebalance_delta",
                "buy_delta",
                "sell_delta",
                "turnover",
                "cost",
                "note",
            ]
        )

    output = records.copy()
    output.insert(0, "note", [_trade_note(row) for _, row in records.iterrows()])
    output.insert(0, "operation", [_trade_operation_text(row) for _, row in records.iterrows()])
    output.insert(0, "strategy", [f"SubD V{row.get('version', VERSION)}" for _, row in records.iterrows()])
    output.insert(0, "position_name", [_asset_name(str(row.get("position", ""))) for _, row in records.iterrows()])
    output.insert(0, "position_before_name", [_asset_name(str(row.get("position_before", ""))) for _, row in records.iterrows()])
    output["date"] = output["date"].dt.date.astype(str)

    first_columns = [
        "date",
        "strategy",
        "operation",
        "base_position_before",
        "base_position_next",
        "actual_position_before",
        "actual_position_next",
        "position_before_name",
        "position_name",
        "fraction_before",
        "holding_fraction",
        "exposure_effective",
        "drifted_exposure_before_trade",
        "final_exposure_after_overheat",
        "rebalance_delta",
        "buy_delta",
        "sell_delta",
        "turnover",
        "cost",
        "note",
    ]
    remaining = [col for col in output.columns if col not in first_columns]
    return output[first_columns + remaining]


def trade_records_csv_bytes(
    daily: pd.DataFrame,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> bytes:
    records = trade_records_frame(daily, start=start, end=end)
    return records.to_csv(index=False).encode("utf-8-sig")


def _asset_last_dates_text(row: pd.Series) -> str:
    parts = []
    for code in ASSETS:
        value = str(row.get(f"last_date_{code}", "")).strip()
        if value:
            parts.append(f"{code}:{value}")
    return " | ".join(parts)


def _overheat_rule_text(row: pd.Series) -> str:
    mode = str(row.get("overheat_recovery_mode", "same_side_or_exit"))
    if mode.strip().lower() in {"", "none", "nan"}:
        return "无过热防守规则。"
    trigger = f"过热触发: bias >= {OVERHEAT_ENTER:.0%} 且 bias_mom 同向"
    if mode == "exit_only":
        recovery = f"过热恢复: bias <= {OVERHEAT_EXIT:.0%}"
    else:
        recovery = f"过热恢复: bias <= {OVERHEAT_EXIT:.0%}，或 same_side 消失"
    return f"{trigger}；{recovery}。"


def _entry_state_text(
    row: pd.Series,
    pending_target: str | None,
    pending_days: int,
    fill_on_down: bool,
    staged_initial: bool,
) -> str:
    actual_entry_state = str(row.get("actual_entry_state", "") or "")
    if actual_entry_state == "BLOCKED_BY_OVERHEAT":
        return "分阶段建仓: 过热防守阻断建仓，当前保持现金。"
    if actual_entry_state == "HALF_POSITION_WAIT_DOWN" and pending_target:
        return f"分阶段建仓: 等待补仓，待补目标 {_asset_name(pending_target)}，已等待 {pending_days} 个交易日。"
    if fill_on_down:
        return "分阶段建仓: 本日下跌补足仓位。"
    if staged_initial:
        return f"分阶段建仓: 本日首笔{INITIAL_ENTRY_FRACTION:.0%}建仓，后续等待下跌日补足。"
    return "分阶段建仓: 当前无待补仓。"


def _signal_exception_lines(
    data_status: dict[str, object],
    sig: dict[str, object],
) -> list[str]:
    lines: list[str] = []
    if not data_status["signal_valid"]:
        lines.append(f"- 数据不可交易: {data_status['label']}。")
        lines.append(
            f"- 预期最新交易日: {data_status['expected_latest_session']} | "
            f"实际最新交易日: {data_status['actual_latest_session']} | "
            f"信号计算日期: {data_status['signal_date']}。"
        )
        lines.append("- 本次只展示最近可用信号，不输出可执行交易指令。")
    elif data_status["delayed_execution"]:
        lines.append(f"- 延迟执行: {data_status['execution_note']}")
    elif data_status["raw_signal_has_trade"] and not data_status["strategy_actionable_now"]:
        lines.append(f"- 当前不可执行: {data_status['execution_note']}")
    elif data_status["raw_signal_has_trade"] and not (
        data_status["exchange_can_complete_full_rebalance_now"] or data_status["post_close_actionable_now"]
    ):
        if data_status["exchange_all_legs_can_submit"]:
            lines.append("- 当前可提交全部委托，但不能立即完成全部换仓；需等待集合竞价统一撮合。")
        else:
            lines.append(f"- 当前无法提交完整换仓指令: {data_status['execution_note']}")

    if data_status["execution_legs"] and data_status["raw_signal_has_trade"] and lines:
        leg_text = "；".join(
            f"{leg['side']} {leg['asset']}({leg['exchange']}/{leg['security_type']}): "
            f"{leg['execution_session']}，"
            f"可申报={'是' if leg['can_submit_order_now'] else '否'}，"
            f"可即时撮合={'是' if leg['can_match_immediately'] else '否'}"
            + (
                f"，阻断={','.join(leg['execution_block_reasons'])}"
                if leg.get("execution_block_reasons")
                else ""
            )
            for leg in data_status["execution_legs"]
        )
        lines.append(f"- 分腿状态: {leg_text}")

    if sig.get("overheat_feature_missing"):
        lines.append("- Overheat feature missing: keep prior defense state; do not trade on a recovery signal.")
    return lines


def _unconfirmed_bar_note(data_status: dict[str, object]) -> str:
    if data_status["strategy_execution_window_status"] == "AFTER":
        return "提示: 当前日线bar尚未最终确认；最终以收盘确认信号为准。"
    return "提示: 使用当天未确认bar，收盘前仍可能变化；最终以收盘确认信号为准。"


def _format_signal_report_compact(
    daily: pd.DataFrame,
    source_note: str,
    live: bool = False,
    now: datetime | None = None,
) -> str:
    ordered = prepare_daily_for_signal(daily, live=live, now=now)
    data_status = signal_data_status(ordered, live=live, now=now)
    row = ordered.iloc[-1]
    sig = latest_signal(ordered)

    prev_name = _asset_name(str(sig["actual_position_before"]))
    next_name = _asset_name(str(sig["actual_position_next"]))
    final_exposure = _float(sig["final_exposure"], default=math.nan)
    exposure_effective = _float(sig["exposure_effective"], default=math.nan)
    turnover = _float(sig["turnover"], default=0.0)
    cost = _float(sig["cost"], default=0.0)
    holding_fraction = _float(sig["holding_fraction"], default=math.nan)
    target_vol_scale_effective = _float(sig["target_vol_scale_effective"], default=math.nan)
    target_vol_scale_next = _float(sig["target_vol_scale_next"], default=math.nan)
    overheat_scale_effective = _float(sig["overheat_scale_effective"], default=1.0)
    overheat_scale_next = _float(sig["overheat_scale_next"], default=1.0)
    execution_scale = _float(sig.get("execution_scale"), default=math.nan)
    realized_vol = _float(row.get("virtual_base_realized_vol", row.get("realized_vol")), default=math.nan)
    base_nav = _float(row.get("base_nav"), default=math.nan)
    nav_before_overheat = _float(row.get("nav_before_overheat"), default=math.nan)
    overheat_bias = _float(row.get("overheat_bias"), default=math.nan)
    overheat_mom = _float(row.get("overheat_bias_mom"), default=math.nan)
    pending_target = _empty_to_none(row.get("actual_pending_target", row.get("pending_entry_target")))
    pending_days = int(_float(row.get("actual_pending_days", row.get("pending_entry_days")), default=0.0))
    fill_on_down = _bool(row.get("actual_fill_on_down_day", row.get("fill_on_down_day")))
    staged_initial = _bool(row.get("actual_staged_initial", row.get("staged_initial")))
    last_base_signal = _last_base_signal_date(ordered)
    last_actual_trade = _last_actual_trade_date(ordered)

    target_position_label = "若现在收盘目标持仓" if data_status["uses_unconfirmed_bar"] else "收盘后目标持仓"
    target_exposure_label = "若现在收盘目标敞口" if data_status["uses_unconfirmed_bar"] else "收盘后目标敞口"
    trade_action_label = "若现在收盘调仓动作" if data_status["uses_unconfirmed_bar"] else "本日调仓动作"
    target_scale_label = "若现在收盘目标" if data_status["uses_unconfirmed_bar"] else "收盘后目标"

    if not data_status["signal_valid"]:
        trade_label = "数据不可交易：不输出实盘动作"
        conclusion = f"数据不可交易：{data_status['label']}。最近可用信号日 {sig['date']}，不输出实盘动作。"
    elif not data_status["raw_signal_has_trade"]:
        trade_label = _trade_action_label(sig)
        conclusion = "信号有效，无需下单。"
    elif data_status["delayed_execution"]:
        trade_label = "延迟执行，不直接下单"
        conclusion = f"存在历史调仓信号，但模型成交时点已经过去。最近可用信号日 {sig['date']}，不直接下单。"
    elif live and not data_status["strategy_actionable_now"]:
        trade_label = "实时估算，暂不执行"
        note = str(data_status["execution_note"]).rstrip("。")
        conclusion = f"实时估算：{_signal_action_text(sig, target_exposure_label=target_exposure_label)}；{note}，不应下单。"
    elif data_status["strategy_actionable_now"] and (
        data_status["exchange_can_complete_full_rebalance_now"] or data_status["post_close_actionable_now"]
    ):
        trade_label = _trade_action_label(sig)
        conclusion = _signal_action_text(sig, target_exposure_label=target_exposure_label)
    elif data_status["strategy_actionable_now"] and data_status["exchange_all_legs_can_submit"]:
        trade_label = _trade_action_label(sig)
        conclusion = (
            f"{_signal_action_text(sig, target_exposure_label=target_exposure_label)}；"
            "当前可以提交全部委托，但需等待集合竞价统一撮合。"
        )
    else:
        trade_label = "当前无法提交完整换仓指令"
        conclusion = f"当前无法提交完整换仓指令：{data_status['execution_note']}。最近可用信号日 {sig['date']}。"

    red_light_lines = _score_red_light_lines(ordered)
    exception_lines = _signal_exception_lines(data_status, sig)
    mode_label = "实时" if live else "收盘确认"

    lines: list[str] = []
    lines.append(f"## SubD混合池子 V1.3 {mode_label}操作信号")
    lines.append("")
    lines.append(f"信号日: **{sig['date']}** | 数据: **{data_status['label']}** | 来源: **{source_note}**")
    lines.append("")
    lines.append("### 结论")
    lines.append("")
    lines.append(f"**{conclusion}**")
    lines.append("")
    lines.append("### 信号摘要")
    lines.append("")
    lines.append(f"- 当前持仓: **{prev_name}**")
    lines.append(f"- {target_position_label}: **{next_name}**")
    lines.append(f"- {trade_action_label}: **{trade_label}**")
    lines.append(f"- 当前敞口: **{_fmt_pct(exposure_effective)}**")
    lines.append(f"- {target_exposure_label}: **{_fmt_pct(final_exposure)}**")
    if turnover > 1e-12:
        lines.append(f"- 目标turnover: **{_fmt_pct(turnover)}**，成本: **{_fmt_pct(cost, 3)}**")
    lines.append(f"- 执行状态: **{data_status['execution_note']}**")
    lines.append(f"- 上次底层调仓信号: **{last_base_signal}**")
    lines.append(f"- 上次实际成交日: **{last_actual_trade}**")
    lines.append(f"- {_entry_state_text(row, pending_target, pending_days, fill_on_down, staged_initial)}")
    lines.append(
        f"- 参数: 基础仓位 **{_fmt_pct(holding_fraction)}** | "
        f"Target-vol **{_fmt_num(target_vol_scale_effective, 3)}x -> {_fmt_num(target_vol_scale_next, 3)}x** | "
        f"过热防守 **{_fmt_num(overheat_scale_effective, 3)}x -> {_fmt_num(overheat_scale_next, 3)}x**"
    )
    if data_status["uses_unconfirmed_bar"]:
        lines.append(f"- {_unconfirmed_bar_note(data_status)}")

    if exception_lines:
        lines.append("")
        lines.append("### 【异常提示】")
        lines.append("")
        lines.extend(exception_lines)

    if red_light_lines:
        lines.append("")
        lines.append("### 【风控提示】")
        lines.append("")
        lines.extend(red_light_lines)

    lines.append("")
    lines.append("### 仓位拆解")
    lines.append("")
    lines.append("| 层级 | 当前值 | 说明 |")
    lines.append("|:-|--:|:-|")
    lines.append(f"| 基础仓位 | **{_fmt_pct(holding_fraction)}** | V1.3新资产先建25%，等待下跌日补足 |")
    lines.append(f"| Target-vol scale(今日已生效) | **{_fmt_num(target_vol_scale_effective, 3)}x** | 用于本日收益 |")
    lines.append(f"| Target-vol scale({target_scale_label}) | **{_fmt_num(target_vol_scale_next, 3)}x** | V1.3已关闭target-vol |")
    lines.append(f"| Scale调整阈值 | **Δ≥{TARGET_VOL_SCALE_REBALANCE_THRESHOLD:.3f}** | 小于阈值沿用上次确认scale |")
    lines.append(f"| 过热防守scale(今日已生效) | **{_fmt_num(overheat_scale_effective, 3)}x** | 用于本日收益 |")
    lines.append(f"| 过热防守scale({target_scale_label}) | **{_fmt_num(overheat_scale_next, 3)}x** | 触发{OVERHEAT_ENTER:.0%} / 恢复{OVERHEAT_EXIT:.0%} |")
    lines.append(f"| 执行scale | **{_fmt_num(execution_scale, 3)}x** | Target-vol × 过热防守 |")
    lines.append(f"| 当前已生效敞口 | **{_fmt_pct(exposure_effective)}** | 本日收益使用的敞口 |")
    lines.append(f"| {target_exposure_label} | **{_fmt_pct(final_exposure)}** | 基础仓位 × {target_scale_label}执行scale |")
    if not pd.isna(realized_vol):
        lines.append(f"| 虚拟底层已实现波动率 | **{_fmt_pct(realized_vol)}** | 过热/guard前曲线，用于下一期target-vol计算 |")

    lines.append("")
    lines.append("### 动量排名")
    lines.append("")
    lines.append("| # | ETF | Raw Score | 显示Score | R² | 状态 | 角色 |")
    lines.append("|:-:|:-|--:|--:|--:|:-|:-|")
    for rank, item in enumerate(_signal_rank_rows(ordered), 1):
        code = str(item["code"])
        raw_score = _float(item["raw_score"], default=math.nan)
        eligible_score = _float(item["eligible_score"], default=math.nan)
        display_score = _display_score(raw_score, eligible_score)
        r2 = _float(item["r2"], default=math.nan)
        lines.append(
            f"| {rank} | {_asset_name(code)} | {_fmt_num(raw_score, 4)} | "
            f"{_fmt_num(display_score, 4)} | {_fmt_num(r2, 3)} | "
            f"{_momentum_status(raw_score, r2)} | {_momentum_role(code, sig)} |"
        )

    lines.append("")
    lines.append("### 规则状态")
    lines.append("")
    lines.append(f"- {_entry_state_text(row, pending_target, pending_days, fill_on_down, staged_initial)}")
    if sig["buffer_blocked"]:
        lines.append(
            f"- 切换buffer: **{SWITCH_BUFFER:.2f}x 已生效**，最强候选未领先当前持仓超过 {(SWITCH_BUFFER - 1.0):.0%}。"
        )
    else:
        lines.append(f"- 切换buffer: **{SWITCH_BUFFER:.2f}x**，换仓需要最强候选分数 > 当前持仓分数 × {SWITCH_BUFFER:.2f}。")
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
    lines.append(f"- {_overheat_rule_text(row)}")
    lines.append(f"- 成本口径: 单边交易成本 **{ONE_WAY_COST:.1%}**，日线收盘价口径。")

    lines.append("")
    lines.append("### 净值快照")
    lines.append("")
    lines.append("| 项目 | 值 |")
    lines.append("|:-|--:|")
    lines.append(f"| 当日收益 | **{_fmt_pct(sig['daily_return'], 3)}** |")
    lines.append(f"| V1.3净值 | **{_fmt_num(sig['nav'], 4)}** |")
    if not pd.isna(nav_before_overheat):
        lines.append(f"| 过热前净值 | **{_fmt_num(nav_before_overheat, 4)}** |")
    if not pd.isna(base_nav):
        lines.append(f"| 基础策略净值 | **{_fmt_num(base_nav, 4)}** |")

    lines.append("")
    lines.append(format_trade_records_table(ordered, limit=10).rstrip())

    return "\n".join(lines) + "\n"


def format_signal_report(
    daily: pd.DataFrame,
    source_note: str,
    live: bool = False,
    now: datetime | None = None,
) -> str:
    return _format_signal_report_compact(daily, source_note, live=live, now=now)


def _momentum_status(score: float, r2: float) -> str:
    if pd.isna(score) or pd.isna(r2):
        return "数据不足"
    if R2_THRESHOLD is not None and r2 < R2_THRESHOLD:
        return f"R²未过{R2_THRESHOLD:.2f}"
    if score <= SCORE_MIN:
        return f"Score≤{SCORE_MIN:.0f}"
    if score >= SCORE_MAX:
        return f"Score≥{SCORE_MAX:.0f}"
    return "入选"


def _score_rule_text() -> str:
    r2_rule = "R²过滤关闭" if R2_THRESHOLD is None else f"R²≥{R2_THRESHOLD:.2f}"
    return (
        f"Score 为{LOOKBACK}日加权对数斜率年化动量；只有 "
        f"{SCORE_MIN:g} < Score < {SCORE_MAX:g} 的 ETF 才进入候选池；{r2_rule}。"
    )


def _mixed_market_timing_notice(live: bool) -> str:
    notice = (
        "跨市场提示：美国日期T收盘晚于中国日期T收盘，US→CN切换不代表同日收盘可执行；"
        "中国长假会压缩累计美国收益到节后首个中国交易日。"
    )
    if live:
        notice += (
            " Yahoo 1分钟价在北京时间下午通常属于美股盘前/隔夜，"
            "仅作监控估算，不是美国正式收盘价。"
        )
    return notice


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


def format_live_params_snapshot(
    daily: pd.DataFrame,
    source_note: str,
    live: bool = False,
    now: datetime | None = None,
) -> str:
    ordered = daily.sort_values("date").reset_index(drop=True)
    row = ordered.iloc[-1]
    data_status = signal_data_status(ordered, live=live, now=now)
    sig = latest_signal(ordered)
    realized_vol = _float(row.get("virtual_base_realized_vol", row.get("realized_vol")), default=math.nan)
    overheat_bias = _float(row.get("overheat_bias"), default=math.nan)
    overheat_mom = _float(row.get("overheat_bias_mom"), default=math.nan)
    final_exposure = _float(sig["final_exposure"], default=math.nan)
    exposure_effective = _float(sig["exposure_effective"], default=math.nan)
    target_vol_scale_effective = _float(sig["target_vol_scale_effective"], default=math.nan)
    target_vol_scale_next = _float(sig["target_vol_scale_next"], default=math.nan)
    overheat_scale_effective = _float(sig["overheat_scale_effective"], default=1.0)
    overheat_scale_next = _float(sig["overheat_scale_next"], default=1.0)
    execution_scale = _float(sig["execution_scale"], default=math.nan)
    actual_previous = _asset_name(str(sig.get("actual_position_before", sig.get("position_before"))))
    actual_next = _asset_name(str(sig.get("actual_position_next", sig.get("position"))))
    base_previous = _asset_name(str(sig.get("base_position_before", sig.get("position_before"))))
    base_next = _asset_name(str(sig.get("base_position_next", sig.get("position"))))

    lines: list[str] = []
    lines.append("")
    lines.append("### 当前混合池动量快照")
    lines.append("")
    lines.append(f"数据源: **{source_note}** | 最新日线: **{sig['date']}**")
    lines.append(f"- 数据状态: **{data_status['label']}**")
    lines.append(
        f"- 预期最新交易日: **{data_status['expected_latest_session']}** | "
        f"实际最新交易日: **{data_status['actual_latest_session']}**"
    )
    lines.append(f"- 数据是否完整: **{'是' if data_status['data_usable'] else '否'}**")
    lines.append(f"- 信号是否有效: **{'是' if data_status['signal_valid'] else '否'}**")
    lines.append(f"- 信号计算日期: **{data_status['signal_date']}**")
    lines.append(f"- 日线bar是否确认: **{'是' if data_status['bar_is_confirmed'] else '否'}**")
    lines.append(f"- 正式收盘价是否就绪: **{'是' if data_status['official_close_ready'] else '否'}**")
    lines.append(f"- 行情时间戳: **{data_status['source_quote_time'] or '无'}**")
    lines.append(
        f"- 逐ETF报价时间范围: **{data_status['earliest_quote_time'] or '无'}"
        f" ~ {data_status['latest_quote_time'] or '无'}**，"
        f"最大时间差: **{_fmt_num(data_status['max_quote_time_skew_seconds'], 0)}秒**"
    )
    lines.append(f"- 全资产实时快照是否新鲜: **{'是' if data_status['live_snapshot_fresh'] else '否'}**")
    lines.append(f"- 报价价格-时间对是否完整: **{'是' if data_status['all_quote_price_time_pairs_valid'] else '否'}**")
    lines.append(f"- 策略价格是否来自实时快照: **{'是' if data_status['price_matrix_uses_live_quotes'] else '否'}**")
    lines.append(f"- 信号是否基于今日收盘价: **{'是' if data_status['signal_uses_today_close'] else '否'}**")
    lines.append(f"- 信号是否属于当前交易日: **{'是' if data_status['signal_is_current_session'] else '否'}**")
    lines.append(f"- 模型成交价格是否仍可用: **{'是' if data_status['model_execution_price_available'] else '否'}**")
    lines.append(f"- 是否延迟执行: **{'是' if data_status['delayed_execution'] else '否'}**")
    lines.append(f"- 当前交易时段: **{data_status['execution_session']}**")
    lines.append(f"- 原始信号是否包含调仓: **{'是' if data_status['raw_signal_has_trade'] else '否'}**")
    lines.append(f"- 当前是否需要执行: **{'是' if data_status['action_required_now'] else '否'}**")
    lines.append(f"- 策略实时执行窗口: **{LIVE_EXECUTION_START.strftime('%H:%M')}—{LIVE_EXECUTION_END.strftime('%H:%M')}**")
    lines.append("- 窗口外实时信号: **仅供监控，不执行**")
    lines.append(f"- 策略执行窗口状态: **{data_status['strategy_execution_window_status']}**")
    lines.append(f"- 交易所是否可以提交全部委托: **{'是' if data_status['exchange_all_legs_can_submit'] else '否'}**")
    lines.append(f"- 交易所是否可以立即完成全部换仓: **{'是' if data_status['exchange_can_complete_full_rebalance_now'] else '否'}**")
    lines.append(f"- 是否仅部分交易腿可即时撮合: **{'是' if data_status['partially_executable'] else '否'}**")
    lines.append(f"- 当前盘后固定价格能否完成全部换仓: **{'是' if data_status['post_close_actionable_now'] else '否'}**")
    lines.append(f"- 是否可作为实盘动作: **{'是' if data_status['tradable'] else '否'}**")
    lines.append(f"- 今日实时快照是否可用: **{'是' if data_status['live_data_available'] else '否'}**")
    lines.append(f"- 执行口径: **{data_status['execution_note']}**")
    lines.append(f"- {_mixed_market_timing_notice(live)}")
    if data_status["execution_legs"]:
        leg_text = "；".join(
            f"{leg['side']} {leg['asset']}({leg['exchange']}/{leg['security_type']}): "
            f"{leg['execution_session']}，"
            f"交易所可申报={'是' if leg['exchange_can_submit_order_now'] else '否'}，"
            f"交易所可即时撮合={'是' if leg['exchange_can_match_immediately'] else '否'}，"
            f"执行许可后可申报={'是' if leg['can_submit_order_now'] else '否'}，"
            f"盘后固定价={'是' if leg['can_use_post_close_fixed_price'] else '否'}"
            + (
                f"，阻断={','.join(leg['execution_block_reasons'])}"
                if leg.get("execution_block_reasons")
                else ""
            )
            for leg in data_status["execution_legs"]
        )
        lines.append(f"- 分腿执行状态: {leg_text}")
    if sig.get("common_last_date"):
        lines.append(f"最新共同有效日线: **{sig['common_last_date']}**")
    last_dates_text = _asset_last_dates_text(row)
    if last_dates_text:
        lines.append(f"各资产最后数据日: {last_dates_text}")
    lines.append("")
    lines.append(
        f"实际账户信号: **{actual_previous} -> {actual_next}** | "
        f"底层虚拟信号: **{base_previous} -> {base_next}** | "
        f"最强候选: **{_asset_name(str(sig['best_candidate']))}** | "
        f"目标敞口: **{_fmt_pct(final_exposure)}**"
    )
    lines.append("")
    lines.append("| # | ETF | Raw Score | 显示Score | R² | 入选状态 | 角色 |")
    lines.append("|:-:|:-|--:|--:|--:|:-|:-|")
    for rank, item in enumerate(_signal_rank_rows(ordered), 1):
        code = str(item["code"])
        raw_score = _float(item["raw_score"], default=math.nan)
        eligible_score = _float(item["eligible_score"], default=math.nan)
        display_score = _display_score(raw_score, eligible_score)
        r2 = _float(item["r2"], default=math.nan)
        lines.append(
            f"| {rank} | {_asset_name(code)} | {_fmt_num(raw_score, 4)} | "
            f"{_fmt_num(display_score, 4)} | {_fmt_num(r2, 3)} | "
            f"{_momentum_status(raw_score, r2)} | {_momentum_role(code, sig)} |"
        )
    lines.append("")
    lines.append("### 当前执行参数快照")
    lines.append("")
    lines.append("| 参数 | 当前值 | 说明 |")
    lines.append("|:-|--:|:-|")
    lines.append(f"| Target-vol scale(今日已生效) | **{_fmt_num(target_vol_scale_effective, 3)}x** | 用于本日收益 |")
    lines.append(f"| Target-vol scale(收盘后目标) | **{_fmt_num(target_vol_scale_next, 3)}x** | V1.3已关闭target-vol |")
    lines.append(f"| Scale调整阈值 | **Δ≥{TARGET_VOL_SCALE_REBALANCE_THRESHOLD:.3f}** | 小于阈值沿用上次确认scale |")
    lines.append(f"| 过热防守scale(今日已生效) | **{_fmt_num(overheat_scale_effective, 3)}x** | 用于本日收益 |")
    lines.append(f"| 过热防守scale(收盘后目标) | **{_fmt_num(overheat_scale_next, 3)}x** | 触发{OVERHEAT_ENTER:.0%} / 恢复{OVERHEAT_EXIT:.0%} |")
    lines.append(f"| 执行scale | **{_fmt_num(execution_scale, 3)}x** | Target-vol × 过热防守 |")
    lines.append(f"| 切换buffer | **{SWITCH_BUFFER:.2f}x** | 换仓需最强候选分数 > 当前持仓分数 × {SWITCH_BUFFER:.2f} |")
    lines.append(f"| 当前已生效敞口 | **{_fmt_pct(exposure_effective)}** | 本日收益使用的敞口 |")
    lines.append(f"| 收盘后目标敞口 | **{_fmt_pct(final_exposure)}** | 基础仓位 × 收盘后目标执行scale |")
    lines.append(f"| Live price check by code | **{_live_price_limit_summary()}** | {LIVE_PRICE_LIMIT_DESCRIPTION} |")
    lines.append(f"| Live history today cross-check | **>{LIVE_PRICE_HISTORY_TODAY_MAX_DIFF:.0%} => backup/review** | history today cross-check has no quote timestamp, so mismatch rejects only the candidate |")
    if not pd.isna(realized_vol):
        lines.append(f"| 虚拟底层已实现波动率 | **{_fmt_pct(realized_vol)}** | 过热/guard前曲线，当前target-vol计算输入 |")
    if not pd.isna(overheat_bias):
        lines.append(f"| 当前持仓乖离 | **{_fmt_pct(overheat_bias)}** | 过热防守观察值 |")
    if not pd.isna(overheat_mom):
        lines.append(f"| 乖离动量 | **{_fmt_num(overheat_mom, 2)}** | 同向过热判定输入 |")
    if sig.get("overheat_feature_missing"):
        lines.append("| Overheat feature missing | **YES** | Keep prior defense state; recovery signal is not tradable |")
    lines.append("")
    lines.append(f"说明: {_score_rule_text()}")
    lines.append(_overheat_rule_text(row))
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
    ret = _daily_returns_for_window(sub)
    sub["nav_norm"] = _wealth_from_returns(ret).to_numpy(dtype=float)
    sub["drawdown"] = _drawdown_from_wealth(sub["nav_norm"])
    return sub


def render_nav_curve_png(
    daily: pd.DataFrame,
    label: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> bytes:
    import io
    import logging
    import matplotlib

    logging.getLogger("matplotlib").setLevel(logging.CRITICAL)
    logging.getLogger("matplotlib.font_manager").setLevel(logging.CRITICAL)
    matplotlib.use("Agg")
    matplotlib.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "SimHei", "Arial Unicode MS"]
    matplotlib.rcParams["axes.unicode_minus"] = False
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
    ax_nav.plot(dates, nav.values, color="#2563EB", linewidth=2.0, label=f"SubD V1.3 NAV ({nav.iloc[-1]:.2f})")
    ax_nav.axhline(1.0, color="#9CA3AF", linestyle="--", linewidth=0.8)
    ax_nav.set_title(f"SubD Mixed Pool V1.3 NAV Curve | {label} | {period_start} to {period_end}", fontsize=13, fontweight="bold")
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
            name=f"subd_v13_nav_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
            contents=chart_bytes,
            content_type="image/png",
            is_inline=False,
        )
    except Exception as exc:
        msg.write(f"> 净值曲线图片生成失败: {str(exc)[:120]}\n")


def _query_wants_nav_curve(query: str) -> bool:
    return bool(re.search(r"净值曲线|收益曲线|走势|曲线|图", str(query or "")))


class SubDMixedPoolV13Bot:
    def run(self):
        query = poe.query.text.strip()
        kind = classify_query(query)
        try:
            if kind == "live_signal":
                self._handle_signal(live=True)
            elif kind == "signal":
                self._handle_signal(live=False)
            elif kind == "live_params":
                self._handle_params(live=True)
            elif kind == "params":
                self._handle_params(live=False)
            elif kind == "performance":
                performance_state_token = _set_performance_response_rendered(False)
                try:
                    try:
                        self._handle_performance(query)
                    except Exception:
                        if _performance_response_rendered():
                            return
                        raise
                finally:
                    _PERFORMANCE_RESPONSE_RENDERED_VAR.reset(performance_state_token)
            else:
                self._handle_signal(live=False)
        except poe.BotError:
            raise
        except Exception as exc:
            raise poe.BotError(f"查询失败: {str(exc)[:240]}")

    # ---- signal --------------------------------------------------------

    def _handle_signal(self, live: bool = False):
        with poe.start_message() as msg:
            if live:
                msg.write("正在实时刷新数据并计算盘中假设信号...\n")
            else:
                msg.write("正在刷新数据并计算收盘确认信号...\n")
            report_live = live
            try:
                daily, source_note = _get_daily_for_today(
                    force_refresh=live,
                    data_state="live" if live else "confirmed",
                )
            except Exception as exc:
                if not live or not _is_proxy_live_quote_unsupported_error(exc):
                    raise
                msg.overwrite("")
                msg.write(
                    "## SubD混合池子 V1.3 实时信号暂不可用\n\n"
                    f"live quotes unavailable: {str(exc)[:240]}\n\n"
                    "本次没有回退到收盘确认信号；请发送“信号”查看收盘确认版本。"
                )
                return
            msg.overwrite("")
            msg.write(format_signal_report(daily, source_note, live=report_live))

    # ---- params --------------------------------------------------------

    def _handle_params(self, live: bool = False):
        with poe.start_message() as msg:
            daily = None
            source_note = ""
            if live:
                msg.write("正在加载数据...\n")
                try:
                    daily, source_note = _get_daily_for_today(force_refresh=True, data_state="live")
                except Exception as exc:
                    source_note = f"加载失败: {str(exc)[:120]}"
                msg.overwrite("")

            title = "实时参数" if live else "参数"
            msg.write(f"## SubD混合池子 V1.3 {title}\n\n")
            if source_note:
                msg.write(f"数据: {source_note}\n\n")
            msg.write("| 参数 | 当前值 | 说明 |\n|:-|:-|:-|\n")
            msg.write(f"| 版本 | **{VERSION}** | {V11_SCENARIO} |\n")
            msg.write(f"| 起始日期 | **{START_DATE.date()}** | 回测起点 |\n")
            msg.write(f"| 评估起点 | **{EVAL_START.date()}** | 正式统计窗口起点 |\n")
            msg.write(f"| 加权斜率窗口 | **{LOOKBACK}日** | 对数价格加权线性拟合 |\n")
            msg.write(f"| Score入选范围 | **{SCORE_MIN:.0f} < Score < {SCORE_MAX:.0f}** | 超过上限或低于下限只显示，不进入候选池 |\n")
            msg.write("| R\u00b2门槛 | **关闭** | V1.3去掉R²过滤 |\n")
            msg.write("| 目标波动率 | **关闭** | V1.3不使用target-vol overlay |\n")
            msg.write(f"| 波动率窗口 | **{DEFAULT_VOL_WINDOW}日** | 用策略收益率估计 |\n")
            msg.write(f"| 最大杠杆 | **{DEFAULT_MAX_LEV:.1f}x** | scale上限 |\n")
            msg.write(f"| Scale调整阈值 | **Δ≥{TARGET_VOL_SCALE_REBALANCE_THRESHOLD:.3f}** | 小于阈值沿用上次确认scale |\n")
            msg.write(f"| 切换buffer | **{SWITCH_BUFFER:.2f}x** | 当前持仓保护 |\n")
            msg.write(f"| 新资产首笔 | **{INITIAL_ENTRY_FRACTION:.0%}** | 从现金或换新资产时先买入 |\n")
            msg.write("| 补仓规则 | **等下跌日补足** | 无固定超时 |\n")
            msg.write(f"| 过热触发/恢复 | **{OVERHEAT_ENTER:.0%} / {OVERHEAT_EXIT:.0%}** | price/MA{CN_BIAS_N}-1 且乖离动量同向 |\n")
            msg.write(f"| 过热后仓位 | **{OVERHEAT_DERISK_SCALE:.0%}** | 触发后切现金敞口 |\n")
            msg.write(f"| 单边成本 | **{ONE_WAY_COST:.1%}** | 调仓成本 |\n")
            msg.write("| SELL腿执行校验 | **需要已验证可卖数量** | 未接券商可卖数量时，含SELL腿的换仓保持monitor-only，不生成可执行动作 |\n")
            msg.write(f"| 资产池 | **{len(ASSETS)}个代理品种** | {', '.join(_asset_name(c) for c in ASSETS)} |\n")
            msg.write("| 数据源 | **QQQ/GLD/KMLM: Yahoo adjusted close；创业板: Eastmoney 399006指数代理；豆粕ETF: qfq正式源，raw仅诊断** | A股交易日历；动态资产从自身首个可用日期后加入，不做上市前回填 |\n")
            msg.write(f"| Live price check by code | **{_live_price_limit_summary()}** | {LIVE_PRICE_LIMIT_DESCRIPTION} |\n")
            msg.write(f"| Live history today cross-check | **>{LIVE_PRICE_HISTORY_TODAY_MAX_DIFF:.0%} => backup/review** | history today cross-check has no quote timestamp, so mismatch rejects only the candidate |\n")
            msg.write(f"\n{_mixed_market_timing_notice(live)}\n")
            if daily is not None:
                msg.write(format_live_params_snapshot(daily, source_note, live=live))

    # ---- performance ---------------------------------------------------

    def _handle_performance(self, query: str):
        daily, source_note = _get_daily_for_today(data_state="confirmed")
        daily = prepare_daily_for_performance(daily)
        earliest = pd.Timestamp(daily["date"].iloc[0])
        latest = pd.Timestamp(daily["date"].iloc[-1])
        ranges = resolve_performance_ranges_for_daily(
            query,
            daily,
            latest_date=latest,
            earliest_date=earliest,
        )
        available_rows = int(
            (pd.to_datetime(daily["date"]).dt.normalize() <= latest).sum()
        )
        chart_range = ranges[0] if ranges else None
        with poe.start_message() as msg:
            if chart_range is not None:
                label, start, end = chart_range
                _write_nav_curve(msg, daily, label, start, end)
                msg.write("\n")
            msg.write("## SubD混合池子 V1.3 表现\n\n")
            msg.write(f"数据: {source_note}\n")
            msg.write(f"最新日度数据: **{latest.date().isoformat()}**\n\n")
            msg.write("| 窗口 | 实际区间 | 天数 | 总收益 | 年化 | 最大回撤 | 波动率 | Sharpe | 交易数 | 平均敞口 | 零敞口天数 | 现金标签天数 |\n")
            msg.write("|:-|:-|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
            _set_performance_response_rendered(True)
            first_chart_range = None
            for label, start, end in ranges:
                try:
                    na_reason = _mandatory_window_na_reason(
                        label,
                        start,
                        earliest,
                        available_rows=available_rows,
                    )
                    if na_reason is not None:
                        raise poe.BotError(na_reason)
                    m = calc_performance(daily, start, end)
                    if first_chart_range is None:
                        first_chart_range = (label, start, end)
                    msg.write(
                        f"| {label} | {m['start']}~{m['end']} | {m['rows']} | "
                        f"{_fmt_pct(m['total'])} | {_fmt_pct(m['annual'])} | "
                        f"{_fmt_pct(m['maxdd'])} | {_fmt_pct(m['vol'])} | "
                        f"{_fmt_num(m['sharpe'], 2)} | {m['trades']} | "
                        f"{_fmt_pct(m['avg_final_exposure'])} | {m['zero_exposure_days']} | {m['cash_days']} |\n"
                    )
                except Exception as exc:
                    reason = _exception_na_reason(exc)
                    msg.write(
                        f"| {label} | N/A: {reason} | N/A | N/A | N/A | N/A | "
                        "N/A | N/A | N/A | N/A | N/A | N/A |\n"
                    )
            if first_chart_range is not None:
                try:
                    label, start, end = first_chart_range
                    msg.write("\n")
                    yearly = calc_yearly_performance(daily, EVAL_START, latest)
                    yearly_table = format_yearly_performance_table(yearly)
                    if yearly_table:
                        msg.write(yearly_table)
                        msg.write("\n")
                except Exception as exc:
                    msg.write("\n### 年度收益\n\n")
                    msg.write(f"N/A: {_exception_na_reason(exc)}\n\n")
                try:
                    label, start, end = first_chart_range
                    trade_table = format_trade_records_table(daily, limit=20, start=start, end=end)
                    msg.write(trade_table)
                except Exception as exc:
                    msg.write("\n### 调仓记录\n\n")
                    msg.write(f"N/A: {_exception_na_reason(exc)}\n\n")
                else:
                    csv_name = f"subd_v13_trade_records_{pd.Timestamp(start).date()}_{pd.Timestamp(end).date()}.csv"
                    try:
                        msg.attach_file(
                            name=csv_name,
                            contents=trade_records_csv_bytes(daily, start=start, end=end),
                            content_type="text/csv; charset=utf-8",
                        )
                        msg.write(f"📎 完整调仓记录CSV: **{csv_name}**\n")
                    except Exception as exc:
                        msg.write(f"📎 完整调仓记录CSV: N/A: {_exception_na_reason(exc)}\n")
                    msg.write("\n")


# ════════════════════════════════════════════════════════════════
#  Settings & entry point
# ════════════════════════════════════════════════════════════════


def _v13_introduction_message() -> str:
    return (
        "**SubD混合池子 V1.3 信号查询**\n\n"
        + "- 发送 **\"信号\"** -> 最新收盘确认信号（最多复用5分钟缓存；收盘确认前不使用当天盘中bar）\n"
        + "- 发送 **\"实时信号\"** -> 盘中/最新日线快照下的假设收盘信号\n"
        + "- 发送 **\"参数\"** -> V1.3参数总览\n"
        + "- 发送 **\"实时参数\"** -> 参数 + 实时数据快照\n"
        + '- 发送 **"表现"** / **"表现 过去两年"** / **"今年收益"** -> 绩效表\n'
        + '- 发送 **"交易记录 过去两个月"** -> 调仓记录表 + 完整CSV\n'
        + '- 发送 **"净值曲线 过去两年"** / **"收益曲线 今年"** -> 绩效表 + 净值曲线\n'
    )


poe.update_settings(SettingsResponse(
    allow_attachments=True,
    introduction_message=_v13_introduction_message(),
))

if __name__ == "__main__":
    SubDMixedPoolV13Bot().run()
