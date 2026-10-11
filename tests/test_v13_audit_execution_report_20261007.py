"""Adversarial I/O cases for six-ETF V1.3; synthetic rows are diagnostic only."""
import importlib.util
import io
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from threading import Event, local
import inspect

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def bot():
    spec = importlib.util.spec_from_file_location(
        "v13_execution_report_audit", ROOT / "poe_subd_six_etf_v1_3_bot.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def diagnostic_daily(module, dates=("2026-06-15", "2026-06-16", "2026-06-17")):
    rows = []
    for i, date in enumerate(dates):
        row = {
            "date": pd.Timestamp(date),
            "version": module.VERSION,
            "scenario": module.V13_SCENARIO,
            "position_before": "CASH",
            "position": "159915.SZ",
            "fraction_before": 0.0,
            "holding_fraction": 1.0,
            "trade_target": "159915.SZ",
            "trade_fraction": 1.0,
            "actual_position_before": "CASH",
            "actual_position_next": "159915.SZ",
            "nav": (1 - module.ONE_WAY_COST) ** (i + 1),
            "return": -module.ONE_WAY_COST,
            "turnover": 1.0,
            "cost": module.ONE_WAY_COST,
            "weight": 1.0,
            "exposure_effective": 0.0,
            "drifted_exposure_before_trade": 0.0,
            "final_exposure_after_overheat": 1.0,
            "buy_delta": 1.0,
            "sell_delta": 0.0,
            "overheat_on": False,
            "overheat_on_effective": False,
        }
        for code in module.ASSETS:
            row[f"last_date_{code}"] = date
            row[f"price_ffill_{code}"] = False
            row[f"signal_price_{code}"] = 1.0
        rows.append(row)
    return pd.DataFrame(rows)


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

    def write(self, value):
        self.writes.append(value)

    def attach_file(self, **kwargs):
        self.attachments.append(kwargs)


def run_record_query(bot, monkeypatch, query, daily):
    capture = CapturePoe(query)
    monkeypatch.setattr(bot, "poe", capture)
    monkeypatch.setattr(bot, "_now_bj", lambda: datetime(2026, 6, 18, 16, tzinfo=bot.CN_TZ))
    monkeypatch.setattr(bot, "_get_daily_for_today", lambda **kw: (daily.copy(), "diagnostic rows"))
    # Chart rendering is unrelated to record selection, and would use the same range.
    monkeypatch.setattr(bot, "_write_nav_curve", lambda *args, **kw: None)
    bot.SubDSixEtfV13Bot().run()
    return capture


def record_exports(capture):
    return [item for item in capture.attachments if item["name"].startswith("subd_v13_trade_records_")]


def test_single_day_trade_query_keeps_requested_day_when_metrics_are_na(bot, monkeypatch):
    daily = diagnostic_daily(bot)
    capture = run_record_query(bot, monkeypatch, "交易记录 2026-06-16", daily)
    exports = record_exports(capture)
    assert len(exports) == 1
    records = pd.read_csv(io.BytesIO(exports[0]["contents"]))
    assert records["date"].tolist() == ["2026-06-16"]
    assert "2026-06-16_2026-06-16" in exports[0]["name"]


def test_no_session_trade_query_does_not_export_full_history(bot, monkeypatch):
    daily = diagnostic_daily(bot)
    capture = run_record_query(bot, monkeypatch, "交易记录 2026-06-14", daily)
    for item in record_exports(capture):
        records = pd.read_csv(io.BytesIO(item["contents"]))
        assert records.empty


def test_date_range_trade_query_uses_requested_bounds(bot, monkeypatch):
    daily = diagnostic_daily(bot)
    capture = run_record_query(bot, monkeypatch, "交易记录 2026-06-15到2026-06-16", daily)
    exports = record_exports(capture)
    assert len(exports) == 1
    records = pd.read_csv(io.BytesIO(exports[0]["contents"]))
    assert records["date"].tolist() == ["2026-06-16", "2026-06-15"]


def test_requested_no_trade_day_remains_empty_in_table_and_csv(bot, monkeypatch):
    daily = diagnostic_daily(bot)
    daily.loc[1, ["turnover", "cost", "buy_delta", "sell_delta"]] = 0.0
    capture = run_record_query(bot, monkeypatch, "交易记录 2026-06-16", daily)
    assert "该时段无调仓记录" in "".join(capture.writes)
    for item in record_exports(capture):
        assert pd.read_csv(io.BytesIO(item["contents"])).empty


@pytest.mark.parametrize("api", ["yearly", "nav", "trade"])
def test_reporting_apis_reject_duplicate_daily_sessions(bot, api):
    daily = diagnostic_daily(bot)
    duplicate = pd.concat([daily, daily.iloc[[1]]], ignore_index=True)
    with pytest.raises(bot.poe.BotError, match="duplicate normalized date"):
        if api == "yearly":
            bot.calc_yearly_performance(duplicate, daily.date.iloc[0], daily.date.iloc[-1])
        elif api == "nav":
            bot.nav_curve_csv_bytes(duplicate, daily.date.iloc[0], daily.date.iloc[-1])
        else:
            bot.trade_records_csv_bytes(duplicate, daily.date.iloc[0], daily.date.iloc[-1])


@pytest.mark.parametrize("api", ["yearly", "nav", "trade"])
def test_reporting_apis_reject_invalid_nav_even_with_finite_returns(bot, api):
    daily = diagnostic_daily(bot)
    daily.loc[1, "nav"] = float("inf")
    with pytest.raises(bot.poe.BotError, match="nav must be finite"):
        if api == "yearly":
            bot.calc_yearly_performance(daily, daily.date.iloc[0], daily.date.iloc[-1])
        elif api == "nav":
            bot.nav_curve_csv_bytes(daily, daily.date.iloc[0], daily.date.iloc[-1])
        else:
            bot.trade_records_csv_bytes(daily, daily.date.iloc[0], daily.date.iloc[-1])


def test_performance_preparation_rejects_single_unconfirmed_row(bot):
    daily = diagnostic_daily(bot, dates=("2026-06-18",))
    with pytest.raises(bot.poe.BotError, match="没有可用的已确认日线"):
        bot.prepare_daily_for_performance(daily, now=datetime(2026, 6, 18, 14, 0))


def test_performance_preparation_does_not_retain_future_bar(bot):
    daily = diagnostic_daily(bot, dates=("2026-06-17", "2026-06-18", "2026-06-19"))
    result = bot.prepare_daily_for_performance(daily, now=datetime(2026, 6, 18, 14, 0))
    assert result.date.tolist() == [pd.Timestamp("2026-06-17")]


@pytest.mark.parametrize("separator", ["-", "/", "."])
@pytest.mark.parametrize("year", [2001, 2010, 2026])
def test_year_month_to_now_is_not_shadowed_by_month_day_parser(bot, separator, year):
    start, end = bot.parse_date_range(f"{year}{separator}06至今", now=datetime(2026, 10, 7))
    assert start == pd.Timestamp(f"{year}-06-01")
    assert end == pd.Timestamp("2026-10-07")


def test_half_year_decimal_request_keeps_its_window(bot):
    start, end = bot.parse_date_range("过去0.5年", now=datetime(2026, 10, 7))
    assert start == pd.Timestamp("2026-04-07")
    assert end == pd.Timestamp("2026-10-07")


def test_older_force_refresh_finishing_late_does_not_replace_newer_cache(bot, monkeypatch):
    state = local()
    older_started, allow_older_finish = Event(), Event()
    older_time = datetime(2026, 6, 18, 14, 54, tzinfo=bot.CN_TZ)
    newer_time = datetime(2026, 6, 18, 14, 55, tzinfo=bot.CN_TZ)
    monkeypatch.setattr(bot, "_now_bj", lambda: state.now)

    def build(end_date=None, data_state="live", now=None):
        if now == older_time:
            older_started.set()
            assert allow_older_finish.wait(timeout=5)
            return pd.DataFrame({"marker": [1]}), "older refresh"
        return pd.DataFrame({"marker": [2]}), "newer refresh"

    def request(now):
        state.now = now
        return bot._get_daily_for_today(force_refresh=True, data_state="live")

    monkeypatch.setattr(bot, "_build_v13_daily", build)
    bot._clear_daily_cache()
    with ThreadPoolExecutor(max_workers=2) as executor:
        old = executor.submit(request, older_time)
        assert older_started.wait(timeout=5)
        try:
            newer = executor.submit(request, newer_time).result(timeout=5)
            assert newer[0].marker.iloc[0] == 2
        finally:
            allow_older_finish.set()
        old.result(timeout=5)
    cache_time, cached_daily, _ = bot._DAILY_CACHE[bot._daily_cache_key("2026-06-18", "live")]
    assert cache_time == newer_time
    assert cached_daily.marker.iloc[0] == 2


@pytest.mark.parametrize("check", [
    "test_live_fresh_quote_pairs_can_pass_snapshot_validation",
    "test_live_snapshot_zero_volume_is_monitor_only",
    "test_live_buy_leg_at_limit_up_is_not_tradable",
    "test_live_sell_leg_at_limit_down_is_not_tradable_even_when_sell_available",
    "test_live_sell_leg_requires_verified_sell_available_quantity",
    "test_live_fresh_quote_price_must_match_signal_price",
    "test_stale_same_day_quote_times_are_listed_as_stale_assets",
    "test_global_final_flag_alone_does_not_confirm_six_asset_close",
    "test_trade_leg_with_forward_filled_price_blocks_execution",
    "test_weekend_signal_is_valid_but_not_actionable_now",
    "test_execution_signal_fails_closed_without_calendar_even_when_not_live",
    "test_performance_rendered_state_is_isolated_between_contexts",
    "test_performance_run_uses_only_its_request_rendered_state",
    "test_performance_run_suppresses_second_response_after_own_render",
])
def test_critical_execution_and_response_guards_on_actual_v13(bot, monkeypatch, check):
    # Reuse independently designed counterexamples against V1.3, rather than V1.1.
    spec = importlib.util.spec_from_file_location(
        f"shared_v13_execution_audit_{check}",
        ROOT / "tests/test_poe_subd_external_review_regressions.py",
    )
    shared = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shared)
    monkeypatch.setattr(bot, "V11_SCENARIO", bot.V13_SCENARIO, raising=False)
    monkeypatch.setattr(bot, "SubDSixEtfV11Bot", bot.SubDSixEtfV13Bot, raising=False)
    monkeypatch.setattr(shared, "load_bot_module", lambda: bot)
    if check == "test_execution_signal_fails_closed_without_calendar_even_when_not_live":
        # Both the provider/cache route and the trusted 2026 fallback are unavailable.
        monkeypatch.setattr(bot, "_load_official_cn_trading_calendar_2026", lambda *args: None)
    function = getattr(shared, check)
    function(**({"monkeypatch": monkeypatch} if "monkeypatch" in inspect.signature(function).parameters else {}))
