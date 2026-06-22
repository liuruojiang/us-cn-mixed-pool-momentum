import importlib.util
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BOT_PATH = ROOT / "poe_subd_six_etf_v1_1_bot.py"


def load_bot_module():
    spec = importlib.util.spec_from_file_location("poe_subd_v11_bot_under_test", BOT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def minimal_daily(module):
    rows = []
    for date, nav in [("2026-06-08", 1.0), ("2026-06-09", 1.01)]:
        row = {
            "date": pd.Timestamp(date),
            "version": module.VERSION,
            "scenario": module.V11_SCENARIO,
            "position_before": "513520.SH",
            "position": "513520.SH",
            "trade_target": "",
            "trade_fraction": 0.0,
            "holding_fraction": 1.0,
            "fraction_before": 1.0,
            "best_candidate": "513520.SH",
            "best_candidate_score": 3.0,
            "current_score": 3.0,
            "buffer_blocked": False,
            "nav": nav,
            "return": 0.01,
            "weight": 1.0,
            "target_vol_scale_effective": 1.0,
            "target_vol_scale_next": 1.0,
            "overheat_scale_effective": 1.0,
            "overheat_scale_next": 1.0,
            "final_exposure_after_overheat": 1.0,
            "exposure_effective": 1.0,
            "turnover": 0.0,
            "cost": 0.0,
            "overheat_on": False,
            "overheat_on_effective": False,
            "overheat_triggered": False,
            "overheat_recovered": False,
            "common_last_date": date,
            "realized_vol": 0.2,
            "base_nav": nav,
            "nav_before_overheat": nav,
            "overheat_bias": 0.1,
            "overheat_bias_mom": 1.0,
            "pending_entry_target": "",
            "pending_entry_days": 0,
            "fill_on_down_day": False,
            "staged_initial": False,
        }
        for code in module.ASSETS:
            row[f"raw_score_{code}"] = 1.0 if code == "513520.SH" else -1.0
            row[f"score_{code}"] = row[f"raw_score_{code}"]
            row[f"r2_{code}"] = 0.5
            row[f"eligible_{code}"] = code == "513520.SH"
            row[f"last_date_{code}"] = date
        rows.append(row)
    return pd.DataFrame(rows)


def test_realtime_query_routes_to_live_signal_mode(monkeypatch):
    module = load_bot_module()
    captured = []

    def fake_handle_signal(self, live=False):
        captured.append(live)

    module.poe = SimpleNamespace(query=SimpleNamespace(text="实时信号"), BotError=Exception)
    monkeypatch.setattr(module.SubDSixEtfV11Bot, "_handle_signal", fake_handle_signal)

    module.SubDSixEtfV11Bot().run()

    assert captured == [True]


def test_get_daily_for_today_force_refresh_bypasses_same_day_cache(monkeypatch):
    module = load_bot_module()
    calls = []

    def fake_build(end_date=None):
        calls.append(pd.Timestamp(end_date).date().isoformat())
        return pd.DataFrame({"marker": [len(calls)]}), f"source-{len(calls)}"

    monkeypatch.setattr(module, "_build_v11_daily", fake_build)
    module._cached_daily.cache_clear()

    first, first_source = module._get_daily_for_today(force_refresh=True)
    second, second_source = module._get_daily_for_today(force_refresh=True)

    assert len(calls) == 2
    assert int(first["marker"].iloc[0]) == 1
    assert int(second["marker"].iloc[0]) == 2
    assert (first_source, second_source) == ("source-1", "source-2")


def test_confirmed_signal_drops_intraday_today_bar():
    module = load_bot_module()
    daily = minimal_daily(module)

    confirmed = module.prepare_daily_for_signal(
        daily,
        live=False,
        now=datetime(2026, 6, 9, 13, 0),
    )

    assert confirmed["date"].max().date().isoformat() == "2026-06-08"


def test_live_signal_report_marks_intraday_as_hypothetical(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module)

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-08", "2026-06-09"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    report = module.format_signal_report(
        daily,
        "unit-test source",
        live=True,
        now=datetime(2026, 6, 9, 13, 0),
    )

    assert "数据: **盘中未确认**" in report
    assert "若现在收盘目标持仓" in report
    assert "收盘前仍可能变化" in report


def test_live_params_snapshot_uses_actual_positions_and_status(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module)
    daily.loc[daily.index[-1], "position_before"] = "159915.SZ"
    daily.loc[daily.index[-1], "position"] = "159915.SZ"
    daily.loc[daily.index[-1], "actual_position_before"] = "CASH"
    daily.loc[daily.index[-1], "actual_position_next"] = "CASH"
    daily.loc[daily.index[-1], "final_exposure_after_overheat"] = 0.0

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-08", "2026-06-09"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    report = module.format_live_params_snapshot(
        daily,
        "unit-test source",
        live=True,
        now=datetime(2026, 6, 9, 13, 0),
    )

    assert "是否可作为实盘动作" in report
    assert "预期最新交易日" in report
    assert "实际账户信号" in report
    assert "现金 -> 现金" in report
    assert "创业板100ETF(159915.SZ) -> 创业板100ETF(159915.SZ)" in report


def test_intraday_cache_is_invalid_after_confirmed_close_boundary(monkeypatch):
    module = load_bot_module()
    calls = []
    current_time = [datetime(2026, 6, 18, 15, 29, tzinfo=module.CN_TZ)]

    def fake_now_bj():
        return current_time[0]

    def fake_build(end_date=None):
        calls.append(len(calls) + 1)
        return pd.DataFrame({"marker": [calls[-1]]}), f"source-{calls[-1]}"

    monkeypatch.setattr(module, "_now_bj", fake_now_bj)
    monkeypatch.setattr(module, "_build_v11_daily", fake_build)
    module._cached_daily.cache_clear()

    live, _ = module._get_daily_for_today(force_refresh=False, data_state="live")
    current_time[0] = datetime(2026, 6, 18, 15, 31, tzinfo=module.CN_TZ)
    confirmed, _ = module._get_daily_for_today(force_refresh=False, data_state="confirmed")

    assert int(live["marker"].iloc[0]) == 1
    assert int(confirmed["marker"].iloc[0]) == 2
    assert calls == [1, 2]
