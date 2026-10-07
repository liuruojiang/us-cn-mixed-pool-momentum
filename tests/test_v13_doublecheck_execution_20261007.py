"""Independent double-check of V1.3 output boundaries and execution metadata.

The preserved public-price daily frame is the real-data basis. Deliberately
corrupt values and metadata below are diagnostic faults, never market data.
"""

import importlib.util
import io
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import Event, local
from types import SimpleNamespace

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
REAL_DAILY = ROOT / "outputs/script_audit_20261007/current_network/confirmed_daily.csv.gz"


@pytest.fixture
def bot():
    spec = importlib.util.spec_from_file_location(
        "v13_execution_doublecheck", ROOT / "poe_subd_six_etf_v1_3_bot.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def real_daily():
    return pd.read_csv(REAL_DAILY, parse_dates=["date"])


class CapturePoe:
    BotError = RuntimeError

    def __init__(self, query):
        self.query = SimpleNamespace(text=query)
        self.writes = []
        self.attachments = []

    def start_message(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def write(self, text):
        self.writes.append(text)

    def attach_file(self, **kwargs):
        self.attachments.append(kwargs)


@pytest.mark.parametrize(
    "query,start,end",
    [
        ("2026-09-24", "2026-09-24", "2026-09-24"),
        ("2026-09-30", "2026-09-30", "2026-09-30"),
        ("2026-10-07", "2026-10-07", "2026-10-07"),
        ("2026-09-17到2026-09-25", "2026-09-17", "2026-09-25"),
        ("2026年9月份", "2026-09-01", "2026-09-30"),
        ("2026/09至今", "2026-09-01", "2026-10-07"),
        ("过去0.5年", "2026-04-07", "2026-10-07"),
        ("2001.06至今", "2001-06-01", "2026-10-07"),
    ],
)
def test_actual_handler_trade_csv_uses_only_the_requested_range(
    bot, real_daily, monkeypatch, query, start, end
):
    capture = CapturePoe(f"交易记录 {query}")
    monkeypatch.setattr(bot, "poe", capture)
    monkeypatch.setattr(
        bot, "_now_bj", lambda: datetime(2026, 10, 7, 16, 0, tzinfo=bot.CN_TZ)
    )
    monkeypatch.setattr(
        bot, "_get_daily_for_today", lambda **kwargs: (real_daily.copy(), "preserved actual qfq daily")
    )
    # Only unrelated image generation is disabled; record selection and CSV
    # generation execute the real handler and real record functions.
    monkeypatch.setattr(bot, "_write_nav_curve", lambda *args, **kwargs: None)
    bot.SubDSixEtfV13Bot().run()
    exports = [
        item for item in capture.attachments
        if item["name"].startswith("subd_v13_trade_records_")
    ]
    assert len(exports) == 1
    actual = pd.read_csv(io.BytesIO(exports[0]["contents"]))
    expected = real_daily.loc[
        (real_daily.date >= pd.Timestamp(start))
        & (real_daily.date <= pd.Timestamp(end))
        & (real_daily.turnover > 1e-12),
        "date",
    ].sort_values(ascending=False).dt.strftime("%Y-%m-%d").tolist()
    assert actual["date"].tolist() == expected
    text = "".join(capture.writes)
    for label in ("full_sample", "10Y", "5Y", "3Y", "1Y"):
        assert f"| {label} |" in text
    if not expected:
        assert "该时段无调仓记录" in text


@pytest.mark.parametrize("api", ["yearly", "nav", "trade"])
@pytest.mark.parametrize("fault", ["NaT", "same_day_time", "bad_return", "zero_nav", "bad_wealth"])
def test_all_report_output_apis_fail_closed_on_corrupt_preserved_daily(
    bot, real_daily, api, fault
):
    daily = real_daily.tail(4).copy().reset_index(drop=True)
    if fault == "NaT":
        daily.loc[1, "date"] = pd.NaT
    elif fault == "same_day_time":
        duplicate = daily.iloc[[1]].copy()
        duplicate["date"] += pd.Timedelta(hours=15)
        daily = pd.concat([daily, duplicate], ignore_index=True)
    elif fault == "bad_return":
        daily.loc[1, "return"] = -1.0
    elif fault == "zero_nav":
        daily.loc[1, "nav"] = 0.0
    else:
        daily["wealth"] = 1.0
        daily.loc[1, "wealth"] = float("nan")
    start, end = pd.Timestamp("2026-09-01"), pd.Timestamp("2026-09-30")
    with pytest.raises(bot.poe.BotError):
        if api == "yearly":
            bot.calc_yearly_performance(daily, start, end)
        elif api == "nav":
            bot.nav_curve_csv_bytes(daily, start, end)
        else:
            bot.trade_records_csv_bytes(daily, start, end)


def with_diagnostic_final_metadata(bot, real_daily):
    out = real_daily.tail(4).copy().reset_index(drop=True)
    i = out.index[-1]
    for code in bot.ASSETS:
        out.loc[i, f"bar_final_{code}"] = True
        out.loc[i, f"final_time_{code}"] = "2026-09-30 15:00:00+08:00"
        out.loc[i, f"final_price_{code}"] = out.loc[i, f"signal_price_{code}"]
        out.loc[i, f"final_close_execution_verified_{code}"] = False
    out.loc[i, "source_bar_is_final"] = True
    out.loc[i, "source_final_close_execution_verified"] = False
    return out


@pytest.mark.parametrize(
    "fault", ["false_text", "pre_close_time", "future_time", "wrong_day", "price_mismatch", "missing_flag"]
)
def test_one_invalid_asset_final_bar_cannot_be_overridden_by_global_final_flag(
    bot, real_daily, fault
):
    daily = with_diagnostic_final_metadata(bot, real_daily)
    i, asset = daily.index[-1], next(iter(bot.ASSETS))
    if fault == "false_text":
        daily.loc[i, f"bar_final_{asset}"] = "false"
    elif fault == "pre_close_time":
        daily.loc[i, f"final_time_{asset}"] = "2026-09-30 14:59:59+08:00"
    elif fault == "future_time":
        daily.loc[i, f"final_time_{asset}"] = "2026-09-30 16:00:00+08:00"
    elif fault == "wrong_day":
        daily.loc[i, f"final_time_{asset}"] = "2026-09-29 15:00:00+08:00"
    elif fault == "price_mismatch":
        daily.loc[i, f"final_price_{asset}"] += 0.01
    else:
        daily = daily.drop(columns=[f"bar_final_{asset}"])
    now = datetime(2026, 9, 30, 15, 6, tzinfo=bot.CN_TZ)
    assert bot._row_verified_final_close(daily.iloc[-1], now) is False
    prepared = bot.prepare_daily_for_performance(daily, now=now)
    assert prepared.date.max() == pd.Timestamp("2026-09-29")


def test_final_looking_future_rows_never_enter_confirmed_output(bot, real_daily):
    daily = with_diagnostic_final_metadata(bot, real_daily)
    future = daily.tail(1).copy()
    future["date"] = pd.Timestamp("2026-10-08")
    for code in bot.ASSETS:
        future[f"final_time_{code}"] = "2026-10-08 15:00:00+08:00"
    combined = pd.concat([daily, future], ignore_index=True)
    prepared = bot.prepare_daily_for_performance(
        combined, now=datetime(2026, 9, 30, 15, 6, tzinfo=bot.CN_TZ)
    )
    assert prepared.date.max() == pd.Timestamp("2026-09-30")


def test_synthesized_final_bar_keeps_performance_but_never_enables_execution(
    bot, real_daily, monkeypatch
):
    daily = with_diagnostic_final_metadata(bot, real_daily)
    i, asset = daily.index[-1], next(iter(bot.ASSETS))
    # A diagnostic CASH -> ETF BUY gives the guard a real execution leg to
    # refuse; the preserved latest actual row itself did not trade.
    daily.loc[i, "actual_position_before"] = "CASH"
    daily.loc[i, "actual_position_next"] = asset
    daily.loc[i, "buy_delta"] = 1.0
    daily.loc[i, "sell_delta"] = 0.0
    now = datetime(2026, 9, 30, 15, 6, tzinfo=bot.CN_TZ)
    monkeypatch.setattr(bot, "POST_CLOSE_FIXED_PRICE_EXECUTION_ENABLED", True)
    monkeypatch.setattr(bot, "_expected_cn_trading_days", lambda *args: pd.to_datetime(["2026-09-29", "2026-09-30"]))
    prepared = bot.prepare_daily_for_performance(daily, now=now)
    status = bot.signal_data_status(prepared, live=False, now=now)
    assert prepared.date.max() == pd.Timestamp("2026-09-30")
    assert status["bar_is_confirmed"] is True
    assert status["raw_signal_has_trade"] is True
    assert status["final_close_execution_verified"] is False
    assert status["tradable"] is False
    # Positive control: the same diagnostic leg and verified prices, with all
    # explicit execution certifications enabled, are otherwise executable.
    prepared.loc[prepared.index[-1], "source_final_close_execution_verified"] = True
    for code in bot.ASSETS:
        prepared.loc[prepared.index[-1], f"final_close_execution_verified_{code}"] = True
    trusted = bot.signal_data_status(prepared, live=False, now=now)
    assert trusted["final_close_execution_verified"] is True
    assert trusted["tradable"] is True


def test_mixed_normal_and_force_refresh_preserve_newest_cache(bot, monkeypatch):
    state = local()
    old_started, old_can_finish = Event(), Event()
    old_now = datetime(2026, 9, 30, 14, 54, tzinfo=bot.CN_TZ)
    new_now = datetime(2026, 9, 30, 14, 55, tzinfo=bot.CN_TZ)
    monkeypatch.setattr(bot, "_now_bj", lambda: state.now)

    def build(end_date=None, data_state="live", now=None):
        if now == old_now:
            old_started.set()
            assert old_can_finish.wait(timeout=5)
            return pd.DataFrame({"marker": [1]}), "old force"
        return pd.DataFrame({"marker": [2]}), "new normal"

    def request(now, force):
        state.now = now
        return bot._get_daily_for_today(force_refresh=force, data_state="live")

    monkeypatch.setattr(bot, "_build_v13_daily", build)
    bot._clear_daily_cache()
    with ThreadPoolExecutor(max_workers=2) as pool:
        older = pool.submit(request, old_now, True)
        assert old_started.wait(timeout=5)
        try:
            newer = pool.submit(request, new_now, False).result(timeout=5)
        finally:
            old_can_finish.set()
        older_result = older.result(timeout=5)
    assert older_result[0].marker.iloc[0] == 1
    assert newer[0].marker.iloc[0] == 2
    cached_at, cached, source = bot._DAILY_CACHE[bot._daily_cache_key("2026-09-30", "live")]
    assert cached_at == new_now
    assert cached.marker.iloc[0] == 2
    assert source == "new normal"


def test_handler_daily_copies_do_not_mutate_the_cache(bot, real_daily, monkeypatch):
    now = datetime(2026, 10, 7, 16, 0, tzinfo=bot.CN_TZ)
    monkeypatch.setattr(bot, "_now_bj", lambda: now)
    monkeypatch.setattr(bot, "_build_v13_daily", lambda **kwargs: (real_daily.copy(), "real preserved frame"))
    bot._clear_daily_cache()
    one, _ = bot._get_daily_for_today(data_state="confirmed")
    one.loc[one.index[-1], "nav"] = float("inf")
    two, _ = bot._get_daily_for_today(data_state="confirmed")
    assert two.nav.iloc[-1] == real_daily.nav.iloc[-1]
    assert two is not one


@pytest.mark.parametrize(
    "query,start,end",
    [
        ("2026-06 到 2026-08", "2026-06-01", "2026-08-31"),
        ("2025年12月到1月", "2025-12-01", "2026-01-31"),
        ("2025/12/15到1/15", "2025-12-15", "2026-01-15"),
        ("近1.5年", "2025-04-07", "2026-10-07"),
    ],
)
def test_supported_date_grammars_keep_existing_semantics(bot, query, start, end):
    actual = bot.parse_date_range(query, now=datetime(2026, 10, 7))
    assert actual == (pd.Timestamp(start), pd.Timestamp(end))


def test_beijing_date_controls_relative_ranges_at_utc_midnight_boundary(bot):
    start, end = bot.parse_date_range(
        "过去0.5年", now=pd.Timestamp("2026-09-30 17:00:00+00:00")
    )
    assert start == pd.Timestamp("2026-04-01")
    assert end == pd.Timestamp("2026-10-01")
