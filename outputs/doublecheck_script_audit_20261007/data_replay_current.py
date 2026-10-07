"""Independent replay through repaired source parsers and formal builder.

Only external price responses are replaced with the preserved genuine qfq
snapshot. The real archived calendar is preloaded into the existing cache.
No fresh remote download or execution acceptance is asserted by this replay.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CODE = ROOT / "poe_subd_six_etf_v1_3_bot.py"
CURRENT = ROOT / "outputs/script_audit_20261007/current_network"
CALENDAR = ROOT / "outputs/recert_l1_20260926/calendar_cache_for_audit.csv"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    code_hash = digest(CODE)
    capture = json.loads((CURRENT / "manifest.json").read_text(encoding="utf-8"))
    for filename in ("raw_prices_qfq.csv.gz", "confirmed_daily.csv.gz"):
        assert digest(CURRENT / filename) == capture["files"][filename]
    prices = pd.read_csv(CURRENT / "raw_prices_qfq.csv.gz", parse_dates=["date"]).set_index("date")
    saved = pd.read_csv(CURRENT / "confirmed_daily.csv.gz", parse_dates=["date"])
    calendar = pd.DatetimeIndex(pd.to_datetime(pd.read_csv(CALENDAR).trade_date))
    covered = calendar[(calendar >= prices.index.min()) & (calendar <= prices.index.max())]
    assert covered.equals(prices.index)
    spec = importlib.util.spec_from_file_location("v13_doublecheck_data_current_replay", CODE)
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)
    bot._CN_TRADING_DAY_CACHE = calendar
    bot._CN_TRADING_DAY_CACHE_COVERAGE_END = calendar.max()
    bot._CN_TRADING_DAY_CACHE_QUERIED_START = None
    bot._CN_TRADING_DAY_CACHE_QUERIED_END = None
    date_calls = []
    actual_expected = bot._expected_cn_trading_days

    def expected(start, end):
        date_calls.append({"start": str(pd.Timestamp(start).date()), "end": str(pd.Timestamp(end).date())})
        return actual_expected(start, end)

    primary_calls = []

    def primary(**kwargs):
        code = next(code for code in bot.ASSETS if code.split(".")[0] == kwargs["symbol"])
        primary_calls.append(code)
        values = prices[code].dropna()
        return pd.DataFrame({"日期": values.index, "收盘": values.values})

    def unexpected_http(*args, **kwargs):
        raise AssertionError("Frozen replay must not make HTTP calls")

    bot._HAS_AKSHARE = True
    bot.ak = SimpleNamespace(fund_etf_hist_em=primary)
    bot._http_get = unexpected_http
    bot._expected_cn_trading_days = expected
    daily, source = bot._build_v13_daily(
        prices.index.max(), "confirmed", datetime(2026, 10, 7, 16, 0, tzinfo=bot.CN_TZ)
    )
    assert digest(CODE) == code_hash, "Code changed while replay was running"
    assert daily.date.equals(saved.date)
    differences = {}
    for column in ("nav", "return", "cost", "turnover", "buy_delta", "sell_delta", "fraction_before", "holding_fraction"):
        differences[column] = float(np.max(np.abs(daily[column] - saved[column])))
        np.testing.assert_allclose(daily[column], saved[column], rtol=0, atol=1e-10 if column == "nav" else 1e-12)
    for column in ("position", "position_before", "trade_blocked_by_stale_price"):
        assert daily[column].equals(saved[column])
    flag_columns = [f"price_ffill_{code}" for code in bot.ASSETS]
    np.testing.assert_array_equal(daily[flag_columns].to_numpy(bool), saved[flag_columns].to_numpy(bool))
    assert int(daily[flag_columns].to_numpy(bool).sum()) == 2
    assert date_calls == [
        {"start": "2011-12-09", "end": "2026-09-30"},
        {"start": "2011-12-09", "end": "2026-09-30"},
    ], "Provider checks should reuse one date set, followed by the required alignment check"
    windows = []
    for label, start, end in bot._default_performance_ranges_for_daily(daily, daily.date.max(), daily.date.min())[:5]:
        actual = bot.calc_performance(daily, start, end)
        expected_metrics = bot.calc_performance(saved, start, end)
        for key in ("annual", "maxdd"):
            assert abs(actual[key] - expected_metrics[key]) <= 1e-12
        windows.append({"window": label, **actual})
    result = {
        "status": "PASS",
        "basis": "same preserved genuine qfq snapshot; external price responses frozen; not a fresh network run",
        "code_sha256": code_hash,
        "capture_code_sha256": capture["code_sha256"],
        "real_input": {"path": str(CURRENT / "raw_prices_qfq.csv.gz"), "sha256": digest(CURRENT / "raw_prices_qfq.csv.gz")},
        "saved_daily": {"path": str(CURRENT / "confirmed_daily.csv.gz"), "sha256": digest(CURRENT / "confirmed_daily.csv.gz")},
        "calendar": {"path": str(CALENDAR), "sha256": digest(CALENDAR)},
        "official_chain": "_build_v13_daily -> load_close -> formal fallback -> actual AkShare parser(frozen response) -> central validator -> align -> flags -> build_curves -> metadata -> normalize -> official metrics",
        "rows": len(daily), "start": str(daily.date.min().date()), "end": str(daily.date.max().date()),
        "ffill_flags": 2, "source_description_in_replay": source,
        "primary_calls": primary_calls, "calendar_call_ranges": date_calls,
        "max_abs_ledger_differences_vs_preserved_daily": differences,
        "five_windows": windows,
        "assumptions": "China-listed ETF qfq; same-close paper execution; prior holding owns close-close return; one-way cost 0.001; cash 0; no order/fill/hosted-Poe acceptance",
    }
    (HERE / "data_current_replay_results.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "five_windows"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
