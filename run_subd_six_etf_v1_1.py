import argparse
import math
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

import research_subd_six_etf_weighted_slope as subd


VERSION = "1.1"
START_DATE = pd.Timestamp("2010-01-01")
EVAL_START = pd.Timestamp("2020-01-02")
END_DATE = pd.Timestamp.today().normalize()
R2_THRESHOLD = 0.20
TARGET_VOL = 0.25
TARGET_VOL_SCALE_REBALANCE_THRESHOLD = 0.075
V10_BASELINE_SWITCH_BUFFER = 1.00
SWITCH_BUFFER = 1.05
INITIAL_ENTRY_FRACTION = 0.50
OVERHEAT_ENTER = 0.20
OVERHEAT_EXIT = 0.18
OVERHEAT_DERISK_SCALE = 0.0
ONE_WAY_COST = 0.001
CN_BIAS_N = 60
CN_MOM_DAY = 20
TRADING_CALENDAR_CACHE_PATH = Path("outputs/cn_trading_days_cache.csv")
_CN_TRADING_DAY_FAILURE_REASON = ""


def _sanity_check_subd_contract() -> None:
    required = {
        "ASSETS": dict,
        "LOOKBACK": int,
        "TRADING_DAYS": int,
        "DEFAULT_VOL_WINDOW": int,
        "DEFAULT_MAX_LEV": (int, float),
        "OUTPUT_DIR": object,
        "RunConfig": type,
        "calc_scores": object,
        "max_drawdown": object,
        "load_close": object,
        "data_quality": object,
    }
    for name, expected_type in required.items():
        if not hasattr(subd, name):
            raise RuntimeError(f"research_subd_six_etf_weighted_slope missing {name}")
        value = getattr(subd, name)
        if expected_type is not object and not isinstance(value, expected_type):
            raise RuntimeError(f"Unexpected type for subd.{name}: {type(value)!r}")
    if not subd.ASSETS:
        raise RuntimeError("subd.ASSETS is empty")
    if subd.LOOKBACK <= 0 or subd.TRADING_DAYS <= 0:
        raise RuntimeError("subd.LOOKBACK and subd.TRADING_DAYS must be positive")


_sanity_check_subd_contract()


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


def run_staged_entry(
    prices: pd.DataFrame,
    config: subd.RunConfig,
    case: EntryCase,
    r2_threshold: float,
    switch_buffer: float,
) -> pd.DataFrame:
    price_ffill_flags = _price_ffill_flags_for_prices(prices, list(subd.ASSETS))
    prices = prices.loc[: config.end_date].copy()
    price_ffill_flags = price_ffill_flags.reindex(pd.DatetimeIndex(prices.index).normalize()).fillna(False).astype(bool)
    holding = "CASH"
    holding_fraction = 0.0
    pending_entry_target: str | None = None
    pending_entry_since: pd.Timestamp | None = None
    pending_entry_days = 0
    nav = 1.0
    trade_count = 0
    staged_initial_count = 0
    staged_fill_count = 0
    buffer_blocked_count = 0
    rows = []

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
        if idx >= subd.LOOKBACK - 1:
            scores, r2_values = subd.calc_scores(prices, idx, r2_threshold=r2_threshold)
        ideal, best_candidate, best_score, current_score, buffer_blocked = _target_from_scores(
            scores, old_holding, switch_buffer
        )
        if buffer_blocked:
            buffer_blocked_count += 1

        signal_target = ideal if ideal != old_holding else None
        trade_target: str | None = None
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

        stale_price_trade_assets: list[str] = []
        trade_blocked_by_stale_price = False
        blocked_trade_target: str | None = None
        if trade_target is not None:
            stale_price_trade_assets = _stale_price_trade_assets(
                price_ffill_flags,
                date,
                old_holding,
                old_fraction,
                trade_target,
                trade_fraction,
            )
            if stale_price_trade_assets:
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

        if old_holding == "CASH" or old_fraction <= 1e-12 or idx == 0:
            asset_return = 0.0
            gross_return = 0.0
            asset_component = 0.0
        else:
            prev_px = prices.iloc[idx - 1].get(old_holding, np.nan)
            cur_px = prices.iloc[idx].get(old_holding, np.nan)
            prev_px = _require_valid_close(prev_px, old_holding, prices.index[idx - 1], "previous")
            cur_px = _require_valid_close(cur_px, old_holding, date, "current")
            asset_return = float(cur_px / prev_px - 1.0)
            asset_component = old_fraction * asset_return
            gross_return = asset_component

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
        score_row = {f"score_{code}": scores.get(code, math.nan) for code in subd.ASSETS}
        r2_row = {f"r2_{code}": r2_values.get(code, math.nan) for code in subd.ASSETS}
        asset_return_row: dict[str, float] = {}
        for code in subd.ASSETS:
            if idx == 0:
                code_return = 0.0
            else:
                previous = pd.to_numeric(prices.iloc[idx - 1].get(code, np.nan), errors="coerce")
                current = pd.to_numeric(prices.iloc[idx].get(code, np.nan), errors="coerce")
                code_return = (
                    float(current / previous - 1.0)
                    if pd.notna(previous)
                    and pd.notna(current)
                    and float(previous) > 0.0
                    and float(current) > 0.0
                    else math.nan
                )
            asset_return_row[f"asset_return_{code}"] = code_return
        ffill_row = {
            f"price_ffill_{code}": _price_is_forward_filled(price_ffill_flags, date, code)
            for code in subd.ASSETS
        }
        rows.append(
            {
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
                "trade_blocked_by_stale_price": trade_blocked_by_stale_price,
                "blocked_trade_target": blocked_trade_target,
                "stale_price_trade_assets": ",".join(stale_price_trade_assets),
                "asset_return": asset_return,
                **asset_return_row,
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
                **ffill_row,
                **score_row,
                **r2_row,
                "buffer_blocked_count": buffer_blocked_count,
            }
        )

    return pd.DataFrame(rows).set_index("date")


def _expected_cn_trading_days(start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex | None:
    helper = getattr(subd, "_expected_cn_trading_days", None)
    if callable(helper):
        try:
            result = helper(start, end)
            reason = _calendar_failure_reason()
            if result is None and ("交易日历落后于行情数据" in reason or "覆盖不足" in reason):
                raise RuntimeError(reason)
            if result is not None:
                return result
        except RuntimeError as exc:
            if "交易日历落后于行情数据" in str(exc) or "覆盖不足" in str(exc):
                raise
    start = pd.Timestamp(start).normalize()
    end = pd.Timestamp(end).normalize()
    if end < start:
        return pd.DatetimeIndex([])
    loaded = _load_cn_trading_calendar(start, end)
    if loaded is None:
        return None
    calendar, _coverage_end = loaded
    return pd.DatetimeIndex(calendar[(calendar >= start) & (calendar <= end)])


def _set_calendar_failure(reason: str) -> None:
    global _CN_TRADING_DAY_FAILURE_REASON
    _CN_TRADING_DAY_FAILURE_REASON = reason


def _calendar_failure_reason() -> str:
    return _CN_TRADING_DAY_FAILURE_REASON or str(getattr(subd, "_CN_TRADING_DAY_FAILURE_REASON", "") or "")


def _normalize_trading_calendar(frame: pd.DataFrame) -> pd.DatetimeIndex:
    if frame is None or frame.empty:
        return pd.DatetimeIndex([])
    candidate_columns = ("trade_date", "交易日", "calendarDate", "日期", "date")
    column = next((name for name in candidate_columns if name in frame.columns), frame.columns[0])
    calendar = pd.to_datetime(frame[column], errors="coerce").dropna().dt.normalize().unique()
    return pd.DatetimeIndex(calendar).sort_values()


def _load_cached_cn_trading_days() -> tuple[pd.DatetimeIndex, pd.Timestamp | None] | None:
    path = Path(TRADING_CALENDAR_CACHE_PATH)
    if not path.exists():
        return None
    cache = pd.read_csv(path)
    calendar = _normalize_trading_calendar(cache)
    if len(calendar) == 0:
        return None
    coverage_end = None
    if "coverage_end" in cache.columns:
        coverage = pd.to_datetime(cache["coverage_end"], errors="coerce").dropna()
        if not coverage.empty:
            coverage_end = pd.Timestamp(coverage.max()).normalize()
    return calendar, coverage_end


def _write_cached_cn_trading_days(calendar: pd.DatetimeIndex, source: str) -> None:
    calendar = pd.DatetimeIndex(calendar).normalize().unique().sort_values()
    if len(calendar) == 0:
        return
    try:
        path = Path(TRADING_CALENDAR_CACHE_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            {
                "trade_date": [pd.Timestamp(day).date().isoformat() for day in calendar],
                "coverage_end": pd.Timestamp(calendar.max()).date().isoformat(),
                "source": source,
            }
        ).to_csv(path, index=False, encoding="utf-8")
    except Exception:
        return


def _calendar_is_usable(
    calendar: pd.DatetimeIndex,
    required_start: pd.Timestamp,
    required_end: pd.Timestamp,
    coverage_end: pd.Timestamp | None,
) -> bool:
    if len(calendar) == 0:
        return False
    coverage = pd.Timestamp(coverage_end or calendar.max()).normalize()
    return (
        pd.Timestamp(calendar.min()).normalize() <= required_start
        and coverage >= required_end
        and pd.Timestamp(calendar.max()).normalize() >= required_end
    )


def _load_cn_trading_calendar(
    required_start: pd.Timestamp,
    required_end: pd.Timestamp,
) -> tuple[pd.DatetimeIndex, pd.Timestamp | None] | None:
    required_start = pd.Timestamp(required_start).normalize()
    required_end = pd.Timestamp(required_end).normalize()
    _set_calendar_failure("")
    source_errors: list[str] = []
    candidates: list[tuple[str, pd.DatetimeIndex, pd.Timestamp | None]] = []
    ak = getattr(subd, "ak", None)
    if ak is not None and hasattr(ak, "tool_trade_date_hist_sina"):
        try:
            calendar = _normalize_trading_calendar(ak.tool_trade_date_hist_sina())
            if len(calendar) == 0:
                raise RuntimeError("AkShare trading calendar returned no rows")
            candidates.append(("AkShare", calendar, pd.Timestamp(calendar.max()).normalize()))
        except Exception as exc:
            source_errors.append(f"AkShare: {exc}")
    try:
        cached = _load_cached_cn_trading_days()
        if cached is not None:
            calendar, coverage_end = cached
            candidates.append(("local cache", calendar, coverage_end))
    except Exception as exc:
        source_errors.append(f"local cache: {exc}")
    valid_candidates = [
        (source, calendar, coverage_end)
        for source, calendar, coverage_end in candidates
        if _calendar_is_usable(calendar, required_start, required_end, coverage_end)
    ]
    if valid_candidates:
        source, calendar, coverage_end = max(
            valid_candidates,
            key=lambda item: pd.Timestamp(item[2] or item[1].max()).normalize(),
        )
        if source == "AkShare":
            _write_cached_cn_trading_days(calendar, "akshare.tool_trade_date_hist_sina")
        return calendar, coverage_end
    for source, calendar, coverage_end in candidates:
        source_errors.append(
            f"{source} coverage insufficient: need {required_start.date()} to {required_end.date()}, "
            f"got {calendar.min().date()} to {pd.Timestamp(coverage_end or calendar.max()).date()}"
        )
    _set_calendar_failure("交易日历不可用，无法校验历史行情完整性" + ("；" + " | ".join(source_errors[-3:]) if source_errors else ""))
    return None


def _expected_latest_from_asset_dates(latest_valid_dates: list[pd.Timestamp], fallback: pd.Timestamp) -> pd.Timestamp:
    if not latest_valid_dates:
        return fallback
    normalized = pd.Series([pd.Timestamp(item).normalize() for item in latest_valid_dates])
    mode = normalized.mode()
    if not mode.empty:
        return pd.Timestamp(mode.max())
    return pd.Timestamp(normalized.median()).normalize()


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
    return flags.astype(bool)


def _price_ffill_flags_for_prices(
    prices: pd.DataFrame,
    asset_cols: list[str] | tuple[str, ...],
) -> pd.DataFrame:
    asset_cols = list(asset_cols)
    normalized_index = pd.DatetimeIndex(prices.index).normalize()
    flags = prices.attrs.get("price_ffill_flags")
    if isinstance(flags, pd.DataFrame):
        out = flags.copy()
        out.index = pd.DatetimeIndex(out.index).normalize()
        out = out.reindex(normalized_index).fillna(False)
        for code in asset_cols:
            if code not in out.columns:
                out[code] = False
        return out[asset_cols].astype(bool)
    return pd.DataFrame(False, index=normalized_index, columns=asset_cols)


def _price_is_forward_filled(flags: pd.DataFrame, date: pd.Timestamp, code: str) -> bool:
    normalized = pd.Timestamp(date).normalize()
    return bool(code in flags.columns and normalized in flags.index and flags.at[normalized, code])


def _trade_leg_assets(
    old_holding: str,
    old_fraction: float,
    trade_target: str,
    trade_fraction: float,
) -> list[str]:
    assets: list[str] = []
    eps = 1e-12
    trade_fraction = float(trade_fraction)
    if old_holding == trade_target:
        delta = trade_fraction - float(old_fraction)
        if delta < -eps and old_holding in subd.ASSETS:
            assets.append(old_holding)
        elif delta > eps and trade_target in subd.ASSETS:
            assets.append(trade_target)
    else:
        if old_holding in subd.ASSETS and old_fraction > eps:
            assets.append(old_holding)
        if trade_target in subd.ASSETS and trade_fraction > eps and trade_target not in assets:
            assets.append(trade_target)
    return assets


def _stale_price_trade_assets(
    flags: pd.DataFrame,
    date: pd.Timestamp,
    old_holding: str,
    old_fraction: float,
    trade_target: str,
    trade_fraction: float,
) -> list[str]:
    return [
        code
        for code in _trade_leg_assets(old_holding, old_fraction, trade_target, trade_fraction)
        if _price_is_forward_filled(flags, date, code)
    ]


def align_prices_to_common_valid_date(
    prices: pd.DataFrame,
    asset_cols: list[str] | tuple[str, ...],
    calendar_validation_mode: str = "required",
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
    latest_valid_dates = [pd.Timestamp(last).normalize() for last in last_by_asset.values() if pd.notna(last)]
    expected_latest = _expected_latest_from_asset_dates(latest_valid_dates, common_last)
    stale = [
        f"{code}:{last.date().isoformat() if pd.notna(last) else 'N/A'}"
        for code, last in last_by_asset.items()
        if pd.isna(last) or pd.Timestamp(last).normalize() != expected_latest.normalize()
    ]
    if stale:
        raise ValueError(
            f"Latest close dates are not aligned to expected {expected_latest.date().isoformat()}: "
            f"{', '.join(stale)}"
        )
    out = aligned_prices.loc[:common_last].copy()
    out.attrs["price_ffill_flags"] = _price_forward_fill_flags(prices, out, asset_cols)
    return out, common_last, last_by_asset


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
    if isinstance(vol_window, (bool, np.bool_)) or not isinstance(vol_window, (int, np.integer)):
        raise ValueError("vol_window must be an integer greater than 1")
    if isinstance(max_lev, (bool, np.bool_)):
        raise ValueError("max_lev must be a finite nonnegative number")

    try:
        target_vol = float(target_vol)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("target_vol must be a finite positive number") from exc
    try:
        max_lev = float(max_lev)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("max_lev must be a finite nonnegative number") from exc
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
            * math.sqrt(subd.TRADING_DAYS)
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


def _overlay_price_ffill_flags(
    curve: pd.DataFrame,
    price_ffill_flags: pd.DataFrame | None,
) -> pd.DataFrame:
    """Return a strict per-row stale-price mask for overlay trade legs."""
    if not curve.index.is_unique:
        raise ValueError("overlay ledger requires a unique curve index")
    if price_ffill_flags is None:
        attrs_mask = curve.attrs.get("price_ffill_flags")
        if isinstance(attrs_mask, pd.DataFrame):
            price_ffill_flags = attrs_mask
        else:
            embedded = pd.DataFrame(False, index=curve.index, columns=list(subd.ASSETS), dtype=bool)
            for code in subd.ASSETS:
                column = f"price_ffill_{code}"
                if column not in curve.columns:
                    continue
                values = curve[column]
                if values.isna().any() or not pd.api.types.is_bool_dtype(values.dtype):
                    raise ValueError(f"{column} must contain non-null boolean values")
                embedded[code] = values.to_numpy(dtype=bool)
            return embedded

    if not isinstance(price_ffill_flags, pd.DataFrame):
        raise ValueError("price ffill mask must be a DataFrame")
    flags = price_ffill_flags.copy()
    if not flags.index.is_unique:
        raise ValueError("price ffill mask index must be unique")
    if flags.columns.has_duplicates:
        raise ValueError("price ffill mask asset columns must be unique")
    missing_assets = [code for code in subd.ASSETS if code not in flags.columns]
    if missing_assets:
        raise ValueError(f"price ffill mask is missing asset columns: {missing_assets}")
    if isinstance(curve.index, pd.DatetimeIndex):
        try:
            curve_dates = pd.DatetimeIndex(curve.index).normalize()
            flag_dates = pd.DatetimeIndex(flags.index).normalize()
        except Exception as exc:
            raise ValueError("price ffill mask index must contain valid dates") from exc
        if not curve_dates.is_unique or not flag_dates.is_unique:
            raise ValueError("price ffill mask requires unique normalized dates")
        flags.index = flag_dates
        if not flag_dates.equals(curve_dates):
            raise ValueError("price ffill mask must exactly cover the curve index")
        flags.index = curve.index
    elif not flags.index.equals(curve.index):
        raise ValueError("price ffill mask must exactly cover the curve index")
    selected = flags.loc[:, list(subd.ASSETS)]
    if selected.isna().any().any():
        raise ValueError("price ffill mask must not contain NA values")
    bad_dtypes = [code for code in subd.ASSETS if not pd.api.types.is_bool_dtype(selected[code].dtype)]
    if bad_dtypes:
        raise ValueError(f"price ffill mask columns must have boolean dtype: {bad_dtypes}")
    return selected.astype(bool)


def _recompute_final_exposure_nav(
    curve: pd.DataFrame,
    target_vol_effective: pd.Series,
    target_vol_next: pd.Series,
    overheat_effective: pd.Series,
    overheat_next: pd.Series,
    one_way_cost: float,
    price_ffill_flags: pd.DataFrame | None = None,
    max_lev: float | None = None,
) -> pd.DataFrame:
    out = curve.copy()
    ffill_flags = _overlay_price_ffill_flags(out, price_ffill_flags)
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

    if max_lev is None and "max_lev" in out.columns and not out.empty:
        max_lev = out["max_lev"].iloc[0]
    if isinstance(max_lev, (bool, np.bool_)):
        raise ValueError("max_lev hard cap must be a finite nonnegative number")
    if max_lev is None:
        hard_cap = math.inf
    else:
        try:
            hard_cap = float(max_lev)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("max_lev hard cap must be a finite nonnegative number") from exc
        if not math.isfinite(hard_cap) or hard_cap < 0.0:
            raise ValueError("max_lev hard cap must be a finite nonnegative number")

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
    asset_return = (
        pd.to_numeric(out["asset_return"], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )

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
    cap_rebalance_vals: list[bool] = []
    cap_turnover_vals: list[float] = []
    cap_cost_vals: list[float] = []
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
        scheduled_exposure = (
            frac_before * tv_effective * oh_effective if prev_position != "CASH" else 0.0
        )
        scheduled_exposure = min(scheduled_exposure, hard_cap)
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
                actual_return = pd.to_numeric(
                    pd.Series([out.at[idx, actual_return_col]]), errors="coerce"
                ).iloc[0]
                if pd.isna(actual_return) or not math.isfinite(float(actual_return)):
                    raise RuntimeError(
                        f"Missing finite asset return for actual carried position "
                        f"{actual_prev_position} at {idx}"
                    )
                asset_ret = float(actual_return)
            elif actual_prev_position == prev_position:
                asset_ret = float(asset_return.loc[idx])
            else:
                raise RuntimeError(
                    f"Missing asset return for actual carried position {actual_prev_position} at {idx}"
                )

        gross = asset_ret * exposure_before
        denominator = 1.0 + gross
        if not math.isfinite(denominator) or denominator <= 0.0:
            raise RuntimeError(f"NAV factor must remain finite and positive at {idx}")
        if actual_prev_position == "CASH":
            drifted = 0.0
        else:
            drifted = exposure_before * (1.0 + asset_ret) / denominator
            if not math.isfinite(drifted):
                drifted = 0.0

        desired_final = hold_frac * tv_next if next_position != "CASH" else 0.0
        desired_after_overheat = min(desired_final * oh_next, hard_cap)
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
        policy_rebalance = (
            has_base_trade
            or position_changed
            or fraction_changed
            or scale_changed
            or overheat_changed
            or pending_rebalance
        )
        cap_rebalance = bool(drifted > hard_cap + eps)
        should_rebalance = policy_rebalance or cap_rebalance

        if policy_rebalance:
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
        elif cap_rebalance:
            final_after_overheat = hard_cap
            final_before_overheat = hard_cap / oh_next if abs(oh_next) > eps else 0.0
            rebalance = hard_cap - drifted
            buy = 0.0
            sell = drifted - hard_cap
            day_turnover = sell
        else:
            final_after_overheat = drifted
            final_before_overheat = (
                final_after_overheat / oh_next
                if next_position != "CASH" and abs(oh_next) > eps
                else 0.0
            )
            rebalance = 0.0
            buy = 0.0
            sell = 0.0
            day_turnover = 0.0

        stale_assets: list[str] = []
        if should_rebalance and day_turnover > eps:
            if actual_prev_position == next_position and actual_prev_position in subd.ASSETS:
                stale_assets.append(actual_prev_position)
            else:
                if sell > eps and actual_prev_position in subd.ASSETS:
                    stale_assets.append(actual_prev_position)
                if buy > eps and next_position in subd.ASSETS:
                    stale_assets.append(next_position)
            stale_assets = [
                code
                for code in dict.fromkeys(stale_assets)
                if bool(ffill_flags.at[idx, code])
            ]
        overlay_trade_blocked = bool(stale_assets)
        if overlay_trade_blocked:
            if cap_rebalance:
                raise RuntimeError(
                    f"Cannot enforce max_lev hard cap with stale execution price at {idx}: "
                    + ",".join(stale_assets)
                )
            final_after_overheat = drifted
            final_before_overheat = (
                drifted / oh_next
                if actual_prev_position != "CASH" and abs(oh_next) > eps
                else 0.0
            )
            rebalance = buy = sell = day_turnover = 0.0
            next_position = actual_prev_position
            pending_rebalance = True
        elif should_rebalance:
            pending_rebalance = False

        day_cost = day_turnover * float(one_way_cost)
        net = (1.0 + gross) * (1.0 - day_cost) - 1.0
        if not math.isfinite(net) or 1.0 + net <= 0.0:
            raise RuntimeError(f"NAV must remain finite and positive after costs at {idx}")
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
        # Attribute turnover to the hard cap only when the cap itself caused
        # the rebalance.  A coincident policy rebalance would have incurred
        # the same trade without the cap and must not be double-counted.
        cap_only_rebalance = bool(cap_rebalance and not policy_rebalance)
        cap_rebalance_vals.append(cap_only_rebalance)
        cap_turnover_vals.append(day_turnover if cap_only_rebalance else 0.0)
        cap_cost_vals.append(day_cost if cap_only_rebalance else 0.0)
        carried_position = actual_next
        carried_exposure = final_after_overheat if actual_next != "CASH" else 0.0

    exposure_effective = pd.Series(exposure_effective_vals, index=out.index, dtype=float)
    final_exposure = pd.Series(final_exposure_vals, index=out.index, dtype=float)
    final_exposure_after_overheat = pd.Series(
        final_exposure_after_overheat_vals, index=out.index, dtype=float
    )
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
    prior_blocked = out.get(
        "trade_blocked_by_stale_price", pd.Series(False, index=out.index)
    ).fillna(False).astype(bool)
    out["trade_blocked_by_stale_price"] = prior_blocked | pd.Series(
        stale_blocked_vals, index=out.index, dtype=bool
    )
    prior_assets = out.get(
        "stale_price_trade_assets", pd.Series("", index=out.index)
    ).fillna("").astype(str)
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
    out["exposure_cap_rebalance"] = pd.Series(cap_rebalance_vals, index=out.index, dtype=bool)
    out["exposure_cap_turnover"] = pd.Series(cap_turnover_vals, index=out.index, dtype=float)
    out["exposure_cap_cost"] = pd.Series(cap_cost_vals, index=out.index, dtype=float)
    out["gross_return"] = gross_return
    out["return"] = net_return
    out["nav"] = (1.0 + net_return).cumprod()
    if not np.isfinite(out["nav"].to_numpy(dtype=float)).all() or (out["nav"] <= 0.0).any():
        raise RuntimeError("NAV must remain finite and positive")
    out["effective_trade_count"] = (turnover > 1e-12).cumsum()
    return out


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
    result["target_vol_input_return"] = result["return"].astype(float).fillna(0.0)
    result["target_vol_input_nav"] = result["nav"].astype(float)
    result["base_gross_return"] = result["gross_return"].astype(float).fillna(0.0)
    result["base_return"] = result["return"].astype(float).fillna(0.0)
    result["base_nav"] = result["nav"].astype(float)
    result["base_turnover"] = _float_series(result, "turnover", 0.0)
    result["base_cost"] = _float_series(result, "cost", 0.0)
    result["virtual_base_realized_vol"] = realized_vol
    result["realized_vol"] = realized_vol
    ones = pd.Series(1.0, index=result.index, dtype=float)
    result = _recompute_final_exposure_nav(
        result,
        effective_scale,
        next_scale,
        ones,
        ones,
        one_way_cost,
        price_ffill_flags=price_ffill_flags,
        max_lev=max_lev,
    )
    result["target_vol"] = target_vol
    result["vol_window"] = vol_window
    result["max_lev"] = max_lev
    return result


def calc_bias_momentum(close_series: pd.Series) -> pd.Series:
    prices = close_series.values.astype(float)
    n = len(prices)
    result = np.full(n, np.nan)
    ma = close_series.rolling(CN_BIAS_N).mean().values
    total_lookback = CN_BIAS_N + CN_MOM_DAY - 1
    first_valid_idx = total_lookback - 1
    if n <= first_valid_idx:
        return pd.Series(result, index=close_series.index)

    with np.errstate(divide="ignore", invalid="ignore"):
        bias_ratio = np.where((ma >= 1e-10) & np.isfinite(prices), prices / ma, np.nan)

    windows = np.lib.stride_tricks.sliding_window_view(bias_ratio, CN_MOM_DAY)
    starts = windows[:, 0]
    valid = np.isfinite(windows).all(axis=1) & (starts >= 1e-10)
    end_indices = np.arange(CN_MOM_DAY - 1, n)
    valid &= end_indices >= first_valid_idx
    if valid.any():
        x = np.arange(CN_MOM_DAY, dtype=float)
        x_centered = x - x.mean()
        denom = float(np.sum(x_centered * x_centered))
        normalized = windows[valid] / starts[valid, None]
        y_centered = normalized - normalized.mean(axis=1, keepdims=True)
        slopes = (y_centered @ x_centered) / denom
        result[end_indices[valid]] = slopes * 10000
    return pd.Series(result, index=close_series.index)


def build_overheat_features(prices: pd.DataFrame) -> dict[str, pd.DataFrame]:
    features: dict[str, pd.DataFrame] = {}
    for code in subd.ASSETS:
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
    ffill_flags = _overlay_price_ffill_flags(guarded, price_ffill_flags)
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
        target_eligible = base_target in subd.ASSETS
        blocked_next = bool(target_eligible and next_scale <= eps)

        prior_fraction = actual_fraction if actual_position == base_prev and base_prev in subd.ASSETS else 0.0
        guarded.at[idx, "fraction_before"] = prior_fraction
        _set_if_present(guarded, idx, "staged_initial", False)
        _set_if_present(guarded, idx, "fill_on_down_day", False)

        state = "CASH"
        new_fraction = 0.0
        staged_initial = False
        fill_on_down_day = False

        stale_zero_exit = bool(
            blocked_next
            and actual_position in subd.ASSETS
            and actual_fraction > eps
            and bool(ffill_flags.at[idx, actual_position])
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
                and bool(ffill_flags.at[idx, base_target])
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
    effective_scales = []
    next_scales = []
    effective_on_vals = []
    next_on_vals = []
    trigger_vals = []
    recover_vals = []
    bias_vals = []
    mom_vals = []
    same_side_vals = []
    missing_feature_vals = []

    aligned_features: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for code, frame in features.items():
        aligned = frame.reindex(out.index)
        bias_arr = aligned["bias"].to_numpy(dtype=float)
        mom_arr = aligned["bias_mom"].to_numpy(dtype=float)
        same_side_arr = aligned["same_side"].fillna(False).astype(bool).to_numpy()
        aligned_features[code] = (bias_arr, mom_arr, same_side_arr)

    effective_holdings = out["position_before"].astype(str).to_numpy()
    target_holdings = out["position"].astype(str).to_numpy()

    for i in range(len(out)):
        effective_holding = effective_holdings[i]
        target_holding = target_holdings[i]
        effective_eligible = effective_holding in subd.ASSETS
        target_eligible = target_holding in subd.ASSETS

        effective_state = bool(defense_on and state_asset == effective_holding and effective_eligible)
        effective_scale = float(case.derisk_scale) if effective_state else 1.0
        next_state = bool(defense_on and state_asset == target_holding and target_eligible)

        bias = math.nan
        mom = math.nan
        same_side = False
        if target_eligible and target_holding in aligned_features:
            bias_arr, mom_arr, same_side_arr = aligned_features[target_holding]
            bias = float(bias_arr[i]) if pd.notna(bias_arr[i]) else math.nan
            mom = float(mom_arr[i]) if pd.notna(mom_arr[i]) else math.nan
            same_side = bool(same_side_arr[i])
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
    out = _recompute_final_exposure_nav(
        out,
        target_vol_effective,
        target_vol_next,
        out["overheat_scale_effective"],
        out["overheat_scale_next"],
        one_way_cost,
        price_ffill_flags=price_ffill_flags,
        max_lev=float(out["max_lev"].iloc[0]) if "max_lev" in out.columns and not out.empty else None,
    )
    return out


def _validated_trading_dates(index: pd.Index, context: str) -> pd.DatetimeIndex:
    try:
        dates = pd.DatetimeIndex(index)
    except Exception as exc:
        raise ValueError(f"{context} must contain valid trading dates") from exc
    if dates.hasnans:
        raise ValueError(f"{context} must not contain missing trading dates")
    dates = dates.normalize()
    if not dates.is_unique:
        duplicates = dates[dates.duplicated()].unique()
        first = pd.Timestamp(duplicates[0]).date().isoformat() if len(duplicates) else "unknown"
        raise ValueError(f"{context} must contain unique trading dates; first duplicate={first}")
    if not dates.is_monotonic_increasing:
        raise ValueError(f"{context} must contain strictly increasing trading dates")
    return dates


def _daily_returns_for_window(sub: pd.DataFrame) -> pd.Series:
    if "return" in sub.columns:
        ret = pd.to_numeric(sub["return"], errors="coerce")
        if ret.isna().any() or not np.isfinite(ret.to_numpy(dtype=float)).all():
            raise ValueError("return values must be finite inside performance window")
        if (ret <= -1.0).any():
            raise ValueError("return values must be greater than -1 inside performance window")
        out = pd.Series(ret.to_numpy(dtype=float), index=sub.index, dtype=float)
        if out.empty:
            return out
        out.iloc[0] = 0.0
        return out
    nav = pd.to_numeric(sub["nav"], errors="coerce").astype(float)
    if not np.isfinite(nav.to_numpy(dtype=float)).all() or (nav <= 0.0).any():
        raise ValueError("nav values must be finite and positive inside performance window")
    return nav.pct_change(fill_method=None).fillna(0.0)


def _wealth_from_returns(ret: pd.Series) -> pd.Series:
    values = ret.astype(float)
    if not np.isfinite(values.to_numpy(dtype=float)).all() or (values <= -1.0).any():
        raise ValueError("return values must be finite and greater than -1")
    wealth = (1.0 + values).cumprod()
    if not np.isfinite(wealth.to_numpy(dtype=float)).all() or (wealth <= 0.0).any():
        raise ValueError("wealth must remain finite and positive")
    return wealth


def summarize(curve: pd.DataFrame, start: pd.Timestamp, label: str) -> dict[str, object]:
    _validated_trading_dates(curve.index, "performance curve index")
    sub = curve.loc[curve.index >= start].copy()
    if sub.empty:
        raise ValueError(f"No performance rows on or after {pd.Timestamp(start).date()}")
    ret = _daily_returns_for_window(sub)
    wealth = _wealth_from_returns(ret)
    years = len(sub) / subd.TRADING_DAYS
    std = ret.std(ddof=0)
    exposure_col = "exposure_effective" if "exposure_effective" in sub.columns else "final_exposure_after_overheat"
    final_exposure = sub[exposure_col].astype(float).fillna(0.0)
    overheat_col = "overheat_on_effective" if "overheat_on_effective" in sub.columns else "overheat_on"
    return {
        "result_status": str(curve["result_status"].iloc[0]) if "result_status" in curve.columns else "unclassified",
        "result_note": str(curve["result_note"].iloc[0]) if "result_note" in curve.columns else "",
        "version": curve["version"].iloc[0],
        "scenario": curve["scenario"].iloc[0],
        "window": label,
        "start": sub.index[0].date().isoformat(),
        "end": sub.index[-1].date().isoformat(),
        "days": len(sub),
        "total": float(wealth.iloc[-1] - 1.0),
        "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0),
        "maxdd": subd.max_drawdown(wealth),
        "sharpe": float(ret.mean() / std * math.sqrt(subd.TRADING_DAYS)) if std > 0 else math.nan,
        "vol": float(std * math.sqrt(subd.TRADING_DAYS)),
        "cash_days": int((sub["position"] == "CASH").sum()),
        "half_position_days": int(((sub["holding_fraction"] > 1e-12) & (sub["holding_fraction"] < 1.0 - 1e-12)).sum()),
        "pending_days": int(sub["pending_entry_target"].notna().sum()),
        "staged_initials": int(sub["staged_initial"].astype(bool).sum()),
        "staged_fills": int(sub["fill_on_down_day"].astype(bool).sum()),
        "overheat_days": int(sub[overheat_col].astype(bool).sum()) if overheat_col in sub.columns else 0,
        "overheat_triggers": int(sub["overheat_triggered"].astype(bool).sum()) if "overheat_triggered" in sub.columns else 0,
        "overheat_recoveries": int(sub["overheat_recovered"].astype(bool).sum()) if "overheat_recovered" in sub.columns else 0,
        "trades": int((sub["turnover"].astype(float) > 1e-12).sum()),
        "cost_sum": float(sub["cost"].sum()),
        "turnover_sum": float(sub["turnover"].sum()),
        "avg_scale": float(sub["weight"].mean()),
        "avg_final_exposure": float(final_exposure.mean()),
        "max_final_exposure": float(final_exposure.max()),
    }


def tag_original(curve: pd.DataFrame) -> pd.DataFrame:
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


def trading_day_window_start(index: pd.Index, end: pd.Timestamp, trading_days: int) -> pd.Timestamp:
    if isinstance(trading_days, (bool, np.bool_)) or not isinstance(trading_days, (int, np.integer)):
        raise ValueError("trading_days must be a positive integer")
    trading_days = int(trading_days)
    if trading_days <= 0:
        raise ValueError("trading_days must be a positive integer")
    ordered = _validated_trading_dates(index, "performance window index")
    eligible = ordered[ordered <= pd.Timestamp(end).normalize()]
    if eligible.empty:
        raise ValueError(f"No trading dates on or before {end}")
    if len(eligible) < trading_days:
        raise ValueError(
            f"performance window requires {trading_days} unique trading dates; "
            f"only {len(eligible)} available"
        )
    return pd.Timestamp(eligible[-trading_days])


def build_performance_windows(
    index: pd.Index,
    common_last: pd.Timestamp,
    eval_start: pd.Timestamp,
) -> dict[str, pd.Timestamp]:
    ordered = _validated_trading_dates(index, "performance window index")
    eligible = ordered[ordered <= pd.Timestamp(common_last).normalize()]
    if eligible.empty:
        raise ValueError(f"No trading dates on or before {common_last}")
    windows: dict[str, pd.Timestamp] = {
        "full_sample": pd.Timestamp(eligible[0]),
        "10Y": trading_day_window_start(eligible, common_last, 10 * subd.TRADING_DAYS),
        "5Y": trading_day_window_start(eligible, common_last, 5 * subd.TRADING_DAYS),
        "3Y": trading_day_window_start(eligible, common_last, 3 * subd.TRADING_DAYS),
        "1Y": trading_day_window_start(eligible, common_last, subd.TRADING_DAYS),
    }
    if pd.Timestamp(eval_start) <= pd.Timestamp(common_last):
        windows["from_2020"] = pd.Timestamp(eval_start)
    return windows


def classify_source_evidence(source: str) -> tuple[str, str]:
    """Classify whether the selected adjustment mode can support formal results."""
    canonicalizer = getattr(subd, "_canonical_source", None)
    canonical = canonicalizer(source) if callable(canonicalizer) else str(source).strip().lower()
    if canonical == "akshare_sina_raw":
        return (
            "diagnostic_only",
            "DIAGNOSTIC ONLY: Sina raw/unadjusted closes are not eligible for formal strategy performance.",
        )
    if canonical == "akshare_em_qfq":
        return (
            "formal",
            "FORMAL: qfq/front-adjusted ETF closes with the configured adjusted-source fallbacks.",
        )
    raise ValueError(f"Unsupported source: {source}")


def attach_source_evidence(frame: pd.DataFrame, source: str) -> pd.DataFrame:
    status, note = classify_source_evidence(source)
    out = frame.copy()
    out["result_status"] = status
    out["result_note"] = note
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Sub-D six ETF V1.1 backtest.")
    parser.add_argument("--start-date", default=START_DATE.date().isoformat())
    parser.add_argument("--end-date", default=END_DATE.date().isoformat())
    parser.add_argument("--eval-start", default=EVAL_START.date().isoformat())
    parser.add_argument("--output-tag", default=None)
    parser.add_argument(
        "--source",
        choices=["akshare_sina_raw", "akshare_em_qfq", "sina", "eastmoney"],
        default="akshare_em_qfq",
        help="qfq/eastmoney is formal; raw/sina is explicitly diagnostic-only",
    )
    return parser.parse_args()


def build_curves(prices: pd.DataFrame, config: subd.RunConfig) -> list[pd.DataFrame]:
    price_ffill_flags = _price_ffill_flags_for_prices(prices, list(subd.ASSETS))
    original = apply_target_vol_overlay(
        run_staged_entry(
            prices,
            config,
            EntryCase("full_entry_baseline", "full_entry", 1.0),
            R2_THRESHOLD,
            V10_BASELINE_SWITCH_BUFFER,
        ),
        TARGET_VOL,
        config.vol_window,
        config.max_lev,
        config.one_way_cost,
        price_ffill_flags=price_ffill_flags,
    )
    staged = apply_target_vol_overlay(
        run_staged_entry(
            prices,
            config,
            EntryCase("all_new_asset_50_wait_down_no_timeout", "all_new_asset_50_wait_down", INITIAL_ENTRY_FRACTION),
            R2_THRESHOLD,
            SWITCH_BUFFER,
        ),
        TARGET_VOL,
        config.vol_window,
        config.max_lev,
        config.one_way_cost,
        price_ffill_flags=price_ffill_flags,
    )
    v11 = apply_overheat_overlay(
        staged,
        build_overheat_features(prices),
        OverheatCase("v1_1_staged_50_plus_ma60_overheat", OVERHEAT_ENTER, OVERHEAT_EXIT, OVERHEAT_DERISK_SCALE),
        config.one_way_cost,
        price_ffill_flags=price_ffill_flags,
    )
    v11.insert(0, "version", VERSION)
    v11["scenario"] = "v1_1_staged_50_plus_ma60_overheat"
    return [
        attach_source_evidence(curve, config.source)
        for curve in (tag_original(original), v11)
    ]


def main() -> None:
    args = parse_args()
    start_date = pd.Timestamp(args.start_date).normalize()
    end_date = pd.Timestamp(args.end_date).normalize()
    eval_start = pd.Timestamp(args.eval_start).normalize()
    output_tag = args.output_tag or f"v1_1_{end_date.strftime('%Y%m%d')}"
    result_status, result_note = classify_source_evidence(args.source)
    if result_status == "diagnostic_only" and "diagnostic" not in output_tag.lower():
        output_tag = f"{output_tag}_diagnostic"
    config = subd.RunConfig(
        source=args.source,
        one_way_cost=ONE_WAY_COST,
        start_date=start_date,
        end_date=end_date,
        output_tag=output_tag,
        target_vols=(),
        vol_window=subd.DEFAULT_VOL_WINDOW,
        max_lev=subd.DEFAULT_MAX_LEV,
    )
    prices, sources = subd.load_close(config)
    prices = prices.loc[prices.index >= config.start_date]
    prices, common_last, _last_by_asset = align_prices_to_common_valid_date(prices, list(subd.ASSETS))
    curves = build_curves(prices, config)
    windows = build_performance_windows(prices.index, common_last, eval_start)
    summary = pd.DataFrame([summarize(curve, start, label) for curve in curves for label, start in windows.items()])
    sources = attach_source_evidence(sources, config.source)
    quality = attach_source_evidence(subd.data_quality(prices), config.source)

    prefix = f"subd_six_etf_{config.output_tag}"
    subd.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.concat(curves).reset_index().to_csv(subd.OUTPUT_DIR / f"{prefix}_daily.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(subd.OUTPUT_DIR / f"{prefix}_summary.csv", index=False, encoding="utf-8-sig")
    sources.to_csv(subd.OUTPUT_DIR / f"{prefix}_sources.csv", index=False, encoding="utf-8-sig")
    quality.to_csv(subd.OUTPUT_DIR / f"{prefix}_data_quality.csv", index=False, encoding="utf-8-sig")

    print(f"SUBD SIX ETF V1.1 SUMMARY [{result_status.upper()}]")
    print(result_note)
    print(summary.to_string(index=False))
    print(f"\nWROTE {subd.OUTPUT_DIR / (prefix + '_summary.csv')}")
    print(f"WROTE {subd.OUTPUT_DIR / (prefix + '_daily.csv')}")


if __name__ == "__main__":
    main()
