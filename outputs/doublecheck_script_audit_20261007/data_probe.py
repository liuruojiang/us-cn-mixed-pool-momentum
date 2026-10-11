"""Fault-injected official-build counterexamples against immutable 7a baseline.

Real frozen prices and archived independent exchange-calendar dates are read
without edits. All injected/removed bars are diagnostic, never real行情.
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
CODE = ROOT / ".codex_backups/20261007_200248/poe_subd_six_etf_v1_3_bot.py"
RAW = ROOT / "outputs/recert_l1_20260926/prices_raw_qfq_through_20260924.csv.gz"
CALENDAR = ROOT / "outputs/recert_l1_20260926/calendar_cache_for_audit.csv"
SHA = "7a4cf15ff1603764dbf3469aab9b85f33756c98129116b4ce7dedb46eb48e1e3"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, CODE)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def main():
    assert digest(CODE) == SHA
    prices = pd.read_csv(RAW, parse_dates=["date"]).set_index("date")
    calendar = pd.DatetimeIndex(pd.to_datetime(pd.read_csv(CALENDAR).trade_date))
    covered = calendar[(calendar >= prices.index.min()) & (calendar <= prices.index.max())]
    assert covered.equals(prices.index), "Unchanged real baseline differs from archived calendar"
    result = {
        "basis": "diagnostic fault injection on real frozen qfq prices; no market fault is asserted",
        "baseline_code_sha256": digest(CODE),
        "real_input": {"path": str(RAW), "sha256": digest(RAW), "rows": len(prices)},
        "calendar": {"path": str(CALENDAR), "sha256": digest(CALENDAR), "real_price_index_equals_calendar_slice": True},
        "scenarios": [],
    }
    baseline = None
    for label, date, fault in [
        ("unchanged", None, None),
        ("pre_common_weekend", "2012-06-09", "insert_non_session"),
        ("pre_common_holiday", "2012-10-01", "insert_non_session"),
        ("pre_common_missing_market_date", "2012-06-11", "delete_date"),
        ("pre_common_missing_market_month", "2012-06-01", "delete_month"),
        ("post_common_weekend", "2026-09-19", "insert_non_session"),
        ("post_common_holiday", "2026-01-01", "insert_non_session"),
    ]:
        bot = load_module("v13_doublecheck_data_probe_" + label)
        backup_calls = []
        all_primary = {}
        for code in bot.ASSETS:
            close = prices[code].dropna().copy()
            if code == "159915.SZ":
                if fault == "insert_non_session":
                    close.loc[pd.Timestamp(date)] = close.loc[:pd.Timestamp(date)].iloc[-1]
                    close = close.sort_index()
                elif fault == "delete_date":
                    close = close.drop(index=pd.Timestamp(date))
                elif fault == "delete_month":
                    close = close.drop(index=close.loc["2012-06-01":"2012-06-30"].index)
            all_primary[code.split(".")[0]] = close

        def primary(**kwargs):
            close = all_primary[kwargs["symbol"]]
            return pd.DataFrame({"日期": close.index, "收盘": close.values})

        def backup(code, end):
            backup_calls.append(code)
            close = prices[code].dropna().rename(code)
            close.attrs["source_detail"] = bot.SOURCE_DETAIL_TENCENT_QFQ
            return close

        bot._HAS_AKSHARE = True
        bot.ak = SimpleNamespace(fund_etf_hist_em=primary)
        bot._load_tencent_qfq_one_close = backup
        bot._expected_cn_trading_days = lambda start, end: calendar[(calendar >= start) & (calendar <= end)]
        scenario = {"name": label, "injected_fault": fault, "date": date}
        try:
            daily, sources = bot._build_v13_daily(
                prices.index.max(), "confirmed", datetime(2026, 9, 26, 16, 0, tzinfo=bot.CN_TZ)
            )
            scenario.update(
                official_build="returned", rows=len(daily),
                start=str(daily.date.min().date()), end=str(daily.date.max().date()),
                source_description=sources,
                invalid_date_returned=bool(date and pd.Timestamp(date) in set(daily.date) and fault == "insert_non_session"),
                ffill_flags=int(daily[[f"price_ffill_{code}" for code in bot.ASSETS]].to_numpy(bool).sum()),
                diagnostic_end_nav=float(daily.nav.iloc[-1]),
            )
            # All five official metric windows are computed here only to show
            # the injected input's effect; these are not new strategy results.
            scenario["diagnostic_five_windows"] = []
            for window, start, end in bot._default_performance_ranges_for_daily(
                daily, daily.date.max(), daily.date.min()
            )[:5]:
                metrics = bot.calc_performance(daily, start, end)
                scenario["diagnostic_five_windows"].append({"window": window, **metrics})
            if label == "unchanged":
                baseline = daily
            else:
                merged = baseline[["date", "position", "nav"]].merge(
                    daily[["date", "position", "nav"]], on="date", suffixes=("_base", "_fault")
                )
                scenario.update(
                    compared_common_rows=len(merged),
                    position_disagreements=int(merged.position_base.ne(merged.position_fault).sum()),
                    diagnostic_max_abs_nav_difference=float(np.max(np.abs(merged.nav_base - merged.nav_fault))),
                    diagnostic_end_nav_difference=float(daily.nav.iloc[-1] - baseline.nav.iloc[-1]),
                )
        except Exception as exc:
            scenario.update(official_build="raised", error_type=type(exc).__name__, error=str(exc))
        scenario["backup_calls"] = backup_calls
        result["scenarios"].append(scenario)
    output = HERE / "data_probe_results.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
