"""Data-chain fault injections, built from the existing real qfq snapshot.

This does not download or overwrite provider prices/calendar caches. Faults are
explicitly injected; the output is a code diagnostic, not a new backtest result.
"""
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BOT_PATH = ROOT / "poe_subd_six_etf_v1_3_bot.py"
RAW_PATH = ROOT / "outputs/recert_l1_20260926/prices_raw_qfq_through_20260924.csv.gz"


def load_bot():
    spec = importlib.util.spec_from_file_location("v13_data_fault_probe", BOT_PATH)
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)
    return bot


def run():
    bot = load_bot()
    real = pd.read_csv(RAW_PATH, parse_dates=["date"]).set_index("date")
    target = "159915.SZ"
    backup_calls = []

    def injected_akshare(**kwargs):
        code = next(code for code in bot.ASSETS if code.split(".")[0] == kwargs["symbol"])
        s = real[code].dropna()
        if code == target:
            s = s.iloc[-20:]
        return pd.DataFrame({"日期": s.index, "收盘": s.values})

    def full_backup(code, end):
        backup_calls.append(code)
        return real[code].dropna().rename(code)

    # Keep all dates/calendar evidence local. This reads the current cache and
    # does not refresh or write it; remote loader faults use the actual parser.
    cached = bot._load_cached_cn_trading_days()
    calendar = cached[0]
    def local_calendar(start, end):
        return calendar[(calendar >= start) & (calendar <= end)]

    with patch.object(bot, "_HAS_AKSHARE", True), patch.object(bot, "ak", SimpleNamespace(fund_etf_hist_em=injected_akshare), create=True), patch.object(bot, "_load_tencent_qfq_one_close", full_backup), patch.object(bot, "_expected_cn_trading_days", local_calendar):
        loaded, sources = bot.load_close(bot._build_config(real.index[-1]))
        daily, source_note = bot._build_v13_daily(end_date=real.index[-1], now=datetime(2026, 9, 26, 10, 0, tzinfo=bot.CN_TZ))
    selected = sources.loc[sources.code == target].iloc[0]
    latest = daily.iloc[-1]
    clean_score, clean_r2 = bot.weighted_slope_score_and_r2(real[target].ffill().iloc[-bot.LOOKBACK:])
    result = {
        "classification": "fault injection using an existing real frozen qfq panel; diagnostic only",
        "real_input_path": str(RAW_PATH.relative_to(ROOT)),
        "real_panel_rows": len(real),
        "real_input_first": str(real.index.min().date()),
        "real_input_last": str(real.index.max().date()),
        "primary_short_history": {
            "injected_asset": target,
            "injected_rows": 20,
            "accepted_source": str(selected.source),
            "accepted_first": str(selected["first"]),
            "accepted_last": str(selected["last"]),
            "accepted_rows": int(selected["rows"]),
            "backup_calls": backup_calls,
            "loaded_panel_first": str(loaded.index.min().date()),
            "actual_formal_daily_first": str(daily.date.min().date()),
            "latest_raw_score_is_nan": bool(pd.isna(latest[f"raw_score_{target}"])),
            "clean_latest_score": float(clean_score),
            "clean_latest_r2": float(clean_r2),
            "source_note": source_note,
        },
    }

    # Premature empty and repeated pages from the real existing Tencent parser.
    page = real[target].dropna().iloc[-640:]
    rows = [[str(day.date()), str(value), str(value), str(value), str(value), "100"] for day, value in page.items()]
    class Response:
        def __init__(self, page_rows): self.page_rows = page_rows
        def raise_for_status(self): return None
        def json(self): return {"code": 0, "data": {"sz159915": {"qfqday": self.page_rows}}}

    for failure, page_responses in [("premature_empty", [rows, [], [], []]), ("repeated_page", [rows, rows])]:
        calls = []
        def fake_http(_url, **kwargs):
            calls.append(kwargs["params"]["param"])
            return Response(page_responses[min(len(calls)-1, len(page_responses)-1)])
        with patch.object(bot, "_http_get", fake_http), patch.object(bot.time, "sleep", lambda _: None):
            try:
                returned = bot._load_tencent_qfq_one_close(target, real.index[-1])
                result[failure] = {"rejected": False, "rows_returned": len(returned), "first": str(returned.index.min().date()), "last": str(returned.index.max().date()), "requests": calls}
            except Exception as exc:
                result[failure] = {"rejected": True, "exception": type(exc).__name__, "message": str(exc), "requests": calls}

    # Malformed text is a helper-contract issue: public source .astype(float)
    # parsers reject such text before this helper in the actual formal chain.
    small = real.tail(3).copy()
    small[target] = small[target].astype(object)
    small.loc[small.index[1], target] = "not-a-price"
    with patch.object(bot, "_expected_cn_trading_days", local_calendar):
        aligned, _, _ = bot.align_prices_to_common_valid_date(small, list(bot.ASSETS))
    flags = bot._price_forward_fill_flags(small, aligned, list(bot.ASSETS))
    result["malformed_text_helper_only"] = {"accepted": True, "filled_value": float(aligned.loc[small.index[1], target]), "ffill_flag": bool(flags.loc[small.index[1], target])}

    with patch.object(bot, "_expected_cn_trading_days", lambda *_: None):
        session_status = bot._status_calendar_sessions(datetime(2026, 10, 7, 16, 0, tzinfo=bot.CN_TZ), pd.Timestamp("2026-09-30"))
    result["official_calendar_not_used_when_provider_unavailable"] = {key: str(value) if isinstance(value, pd.Timestamp) else value for key, value in session_status.items()}

    # Negative-age cache: normal path currently accepts a future cache timestamp.
    now = datetime(2026, 10, 7, 16, 0, tzinfo=bot.CN_TZ)
    bot._clear_daily_cache()
    key = bot._daily_cache_key("2026-10-07", "live")
    bot._DAILY_CACHE[key] = (now + timedelta(minutes=3), pd.DataFrame({"marker": ["future-cache"]}), "fault-injected")
    with patch.object(bot, "_now_bj", lambda: now), patch.object(bot, "_call_build_v13_daily", lambda *_: (pd.DataFrame({"marker": ["fresh-build"]}), "new")):
        cached, _ = bot._cached_daily("2026-10-07", data_state="live")
    result["negative_age_live_cache"] = {"returned_marker": str(cached.marker.iloc[0])}

    output = Path(__file__).with_name("data_probe_results.json")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    run()
