import importlib.util
import math
import sys
from contextvars import copy_context
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
BOT_PATH = ROOT / "poe_subd_six_etf_v1_1_bot.py"
RESEARCH_PATH = ROOT / "research_subd_six_etf_weighted_slope.py"


OBSOLETE_POE_HELPERS = (
    "_sina_symbol",
    "_tencent_symbol",
    "_load_sina_close",
    "_load_cnfin_one_close",
    "_load_tencent_one_close",
    "_load_cnfin_close",
    "_load_tencent_close",
    "_load_eastmoney_close",
    "_validate_no_partial_raw_history",
    "_round_to_etf_tick",
    "_expected_latest_from_asset_dates",
    "should_drop_unconfirmed_bar",
    "format_nav_curve_text",
    "_sparkline",
)


def load_bot_module():
    spec = importlib.util.spec_from_file_location("poe_subd_review_regressions", BOT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_research_module():
    spec = importlib.util.spec_from_file_location("research_subd_review_regressions", RESEARCH_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_performance_rendered_state_is_isolated_between_contexts():
    module = load_bot_module()
    left = copy_context()
    right = copy_context()

    assert left.run(module._performance_response_rendered) is False
    assert right.run(module._performance_response_rendered) is False

    left.run(module._set_performance_response_rendered, True)

    assert left.run(module._performance_response_rendered) is True
    assert right.run(module._performance_response_rendered) is False


def test_performance_run_uses_only_its_request_rendered_state(monkeypatch):
    module = load_bot_module()
    bot = module.SubDSixEtfV11Bot()
    other_request = copy_context()
    monkeypatch.setattr(module.poe, "query", SimpleNamespace(text="表现"), raising=False)

    def fail_after_other_request_rendered(_query):
        other_request.run(module._set_performance_response_rendered, True)
        raise RuntimeError("request A failed")

    monkeypatch.setattr(bot, "_handle_performance", fail_after_other_request_rendered)

    with pytest.raises(module.poe.BotError, match="request A failed"):
        bot.run()


def test_performance_run_suppresses_second_response_after_own_render(monkeypatch):
    module = load_bot_module()
    bot = module.SubDSixEtfV11Bot()
    monkeypatch.setattr(module.poe, "query", SimpleNamespace(text="表现"), raising=False)

    def fail_after_own_response_rendered(_query):
        module._set_performance_response_rendered(True)
        raise RuntimeError("already rendered")

    monkeypatch.setattr(bot, "_handle_performance", fail_after_own_response_rendered)

    assert bot.run() is None
    assert module._performance_response_rendered() is False


def minimal_daily(module, dates=("2026-06-08", "2026-06-09")):
    rows = []
    for i, date in enumerate(dates, 1):
        row = {
            "date": pd.Timestamp(date),
            "version": module.VERSION,
            "scenario": module.V11_SCENARIO,
            "position_before": "513520.SH",
            "position": "513520.SH",
            "trade_target": "",
            "trade_fraction": math.nan,
            "holding_fraction": 1.0,
            "fraction_before": 1.0,
            "best_candidate": "513520.SH",
            "best_candidate_score": 3.0,
            "current_score": 3.0,
            "buffer_blocked": False,
            "nav": float(i),
            "return": 0.0,
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
            "base_nav": float(i),
            "nav_before_overheat": float(i),
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


def fill_live_quote_pairs(module, daily, row_idx=0, quote_time="2026-06-18 14:54:30"):
    for offset, code in enumerate(module.ASSETS):
        price = 1.0 + offset / 100.0
        daily.loc[row_idx, f"quote_price_{code}"] = price
        daily.loc[row_idx, f"quote_time_{code}"] = quote_time
        daily.loc[row_idx, f"quote_source_{code}"] = "Eastmoney push2"
        daily.loc[row_idx, f"source_execution_eligible_{code}"] = True
        daily.loc[row_idx, f"quote_volume_{code}"] = 1000 + offset
        daily.loc[row_idx, f"quote_amount_{code}"] = price * (1000 + offset)
        daily.loc[row_idx, f"quote_limit_down_{code}"] = round(price * 0.9, 3)
        daily.loc[row_idx, f"quote_limit_up_{code}"] = round(price * 1.1, 3)
        daily.loc[row_idx, f"signal_price_{code}"] = price
    return daily


def fill_final_quote_pairs(module, daily, row_idx=0, quote_time="2026-06-18 15:01:00"):
    for offset, code in enumerate(module.ASSETS):
        price = 1.0 + offset / 100.0
        daily.loc[row_idx, f"final_price_{code}"] = price
        daily.loc[row_idx, f"final_time_{code}"] = quote_time
        daily.loc[row_idx, f"bar_final_{code}"] = True
        daily.loc[row_idx, f"signal_price_{code}"] = price
    return daily


def test_public_loader_rejects_raw_fallback_when_qfq_sources_fail(monkeypatch):
    module = load_bot_module()

    def fail_qfq(code, end_date):
        raise RuntimeError(f"qfq unavailable for {code}")

    monkeypatch.setattr(module, "_load_akshare_eastmoney_qfq_one_close", fail_qfq)
    monkeypatch.setattr(module, "_load_eastmoney_one_close", fail_qfq)
    monkeypatch.setattr(module, "_load_tencent_qfq_one_close", fail_qfq, raising=False)

    with pytest.raises(RuntimeError, match="qfq"):
        module._load_public_close_with_per_code_fallback(["159915.SZ"], pd.Timestamp("2026-01-02"))

    assert not hasattr(module, "_load_cnfin_one_close")
    assert not hasattr(module, "_load_tencent_one_close")


def test_eastmoney_qfq_fallback_uses_canonical_adjustment_detail(monkeypatch):
    module = load_bot_module()

    def fail_akshare(code, end_date):
        raise RuntimeError(f"akshare qfq unavailable for {code}")

    def eastmoney_qfq(code, end_date):
        idx = pd.to_datetime(["2026-01-01", "2026-01-02"])
        return pd.Series([1.0, 1.1], index=idx, name=code)

    monkeypatch.setattr(module, "_load_akshare_eastmoney_qfq_one_close", fail_akshare)
    monkeypatch.setattr(module, "_load_tencent_qfq_one_close", fail_akshare)
    monkeypatch.setattr(module, "_load_eastmoney_one_close", eastmoney_qfq)

    prices, sources = module._load_public_close_with_per_code_fallback(
        ["159915.SZ"], pd.Timestamp("2026-01-02")
    )

    assert prices.columns.tolist() == ["159915.SZ"]
    assert sources.loc[0, "adjustment"] == module.ADJUSTMENT_QFQ
    assert sources.loc[0, "source_detail"] == "fqt=1"


def test_tencent_qfq_fallback_uses_canonical_adjustment_detail(monkeypatch):
    module = load_bot_module()

    def fail_qfq(code, end_date):
        raise RuntimeError(f"provider unavailable for {code}")

    def tencent_qfq(code, end_date):
        idx = pd.to_datetime(["2026-01-01", "2026-01-02"])
        return pd.Series([1.0, 1.1], index=idx, name=code)

    monkeypatch.setattr(module, "_load_akshare_eastmoney_qfq_one_close", fail_qfq)
    monkeypatch.setattr(module, "_load_eastmoney_one_close", fail_qfq)
    monkeypatch.setattr(module, "_load_tencent_qfq_one_close", tencent_qfq, raising=False)

    prices, sources = module._load_public_close_with_per_code_fallback(
        ["159915.SZ"], pd.Timestamp("2026-01-02")
    )

    assert prices.columns.tolist() == ["159915.SZ"]
    assert sources.loc[0, "source"] == "Tencent fqkline"
    assert sources.loc[0, "adjustment"] == module.ADJUSTMENT_QFQ
    assert sources.loc[0, "source_detail"] == module.SOURCE_DETAIL_TENCENT_QFQ


def test_tencent_qfq_loader_pages_until_full_history(monkeypatch):
    module = load_bot_module()
    calls = []

    class FakeResponse:
        def __init__(self, rows):
            self._rows = rows

        def raise_for_status(self):
            return None

        def json(self):
            return {"code": 0, "msg": "", "data": {"sz159915": {"qfqday": self._rows}}}

    first_page = [
        ["2024-01-02", "1.0", "1.1", "1.2", "0.9", "1000"],
        ["2026-01-02", "1.15", "1.2", "1.25", "1.1", "2000"],
    ]
    second_page = [
        ["2023-12-29", "0.9", "1.0", "1.1", "0.8", "900"],
    ]

    def fake_http_get(url, params=None, **kwargs):
        calls.append(params["param"])
        return FakeResponse(first_page if len(calls) == 1 else second_page)

    monkeypatch.setattr(module, "_http_get", fake_http_get)
    monkeypatch.setattr(module, "TENCENT_FQKLINE_PAGE_SIZE", 2, raising=False)

    close = module._load_tencent_qfq_one_close("159915.SZ", pd.Timestamp("2026-01-02"))

    assert len(calls) == 2
    assert "sz159915,day,2010-01-01,2026-01-02,2,qfq" in calls[0]
    assert "sz159915,day,2010-01-01,2024-01-01,2,qfq" in calls[1]
    assert close.index.min() == pd.Timestamp("2023-12-29")
    assert close.index.max() == pd.Timestamp("2026-01-02")
    assert close.loc[pd.Timestamp("2026-01-02")] == pytest.approx(1.2)


@pytest.mark.parametrize(
    ("code", "symbol"),
    [
        ("513030.SH", "sh513030"),
        ("513520.SH", "sh513520"),
        ("159985.SZ", "sz159985"),
    ],
)
def test_tencent_qfq_loader_accepts_verified_day_key(monkeypatch, code, symbol):
    module = load_bot_module()

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "code": 0,
                "msg": "",
                "data": {
                    symbol: {
                        "day": [["2026-01-02", "1.0", "1.1", "1.2", "0.9", "1000"]]
                    }
                },
            }

    monkeypatch.setattr(module, "_http_get", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    close = module._load_tencent_qfq_one_close(code, pd.Timestamp("2026-01-02"))

    assert close.loc[pd.Timestamp("2026-01-02")] == pytest.approx(1.1)
    assert close.attrs["source_detail"] == module.SOURCE_DETAIL_TENCENT_VERIFIED_DAY_QFQ


def test_tencent_qfq_loader_rejects_day_key_for_non_allowlisted_code(monkeypatch):
    module = load_bot_module()

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "code": 0,
                "msg": "",
                "data": {
                    "sz159915": {
                        "day": [["2026-01-02", "1.0", "1.1", "1.2", "0.9", "1000"]]
                    }
                },
            }

    monkeypatch.setattr(module, "_http_get", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="qfqday"):
        module._load_tencent_qfq_one_close("159915.SZ", pd.Timestamp("2026-01-02"))


def test_tencent_verified_day_detail_reaches_source_metadata(monkeypatch):
    module = load_bot_module()

    def fail_provider(code, end_date):
        raise RuntimeError(f"provider unavailable for {code}")

    def verified_tencent_day(code, end_date):
        close = pd.Series(
            [1.0, 1.1],
            index=pd.to_datetime(["2026-01-01", "2026-01-02"]),
            name=code,
        )
        close.attrs["source_detail"] = module.SOURCE_DETAIL_TENCENT_VERIFIED_DAY_QFQ
        return close

    monkeypatch.setattr(module, "_load_akshare_eastmoney_qfq_one_close", fail_provider)
    monkeypatch.setattr(module, "_load_tencent_qfq_one_close", verified_tencent_day)
    monkeypatch.setattr(module, "_load_eastmoney_one_close", fail_provider)

    _prices, sources = module._load_public_close_with_per_code_fallback(
        ["513030.SH"], pd.Timestamp("2026-01-02")
    )

    assert sources.loc[0, "source_detail"] == module.SOURCE_DETAIL_TENCENT_VERIFIED_DAY_QFQ


def test_tencent_qfq_loader_rejects_day_only_page_after_qfq_history(monkeypatch):
    module = load_bot_module()
    calls = []

    class FakeResponse:
        def __init__(self, node):
            self._node = node

        def raise_for_status(self):
            return None

        def json(self):
            return {"code": 0, "msg": "", "data": {"sh513030": self._node}}

    qfq_rows = [
        ["2024-01-02", "1.0", "1.1", "1.2", "0.9", "1000"],
        ["2026-01-02", "1.1", "1.2", "1.3", "1.0", "2000"],
    ]
    day_rows = [["2023-12-29", "0.9", "1.0", "1.1", "0.8", "900"]]

    def fake_http_get(*args, **kwargs):
        calls.append(kwargs["params"]["param"])
        node = {"qfqday": qfq_rows} if len(calls) == 1 else {"day": day_rows}
        return FakeResponse(node)

    monkeypatch.setattr(module, "_http_get", fake_http_get)
    monkeypatch.setattr(module, "TENCENT_FQKLINE_PAGE_SIZE", 2, raising=False)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="qfqday.*partial history"):
        module._load_tencent_qfq_one_close("513030.SH", pd.Timestamp("2026-01-02"))


def test_tencent_qfq_loader_rejects_provider_failure_after_qfq_history(monkeypatch):
    module = load_bot_module()
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "code": 0,
                "msg": "",
                "data": {
                    "sh513030": {
                        "qfqday": [
                            ["2024-01-02", "1.0", "1.1", "1.2", "0.9", "1000"],
                            ["2026-01-02", "1.1", "1.2", "1.3", "1.0", "2000"],
                        ]
                    }
                },
            }

    def fake_http_get(*args, **kwargs):
        calls.append(kwargs["params"]["param"])
        if len(calls) == 1:
            return FakeResponse()
        raise RuntimeError("unit provider failure")

    monkeypatch.setattr(module, "_http_get", fake_http_get)
    monkeypatch.setattr(module, "TENCENT_FQKLINE_PAGE_SIZE", 2, raising=False)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="partial history.*provider failure"):
        module._load_tencent_qfq_one_close("513030.SH", pd.Timestamp("2026-01-02"))


def test_poe_bot_obsolete_dead_helpers_are_not_reintroduced():
    source = BOT_PATH.read_text(encoding="utf-8")
    for helper in OBSOLETE_POE_HELPERS:
        assert f"def {helper}" not in source
    assert "chart_args" not in source
    assert "f297" not in source
    assert "StringIO" not in source
    assert "sys.stderr =" not in source


def test_live_config_source_names_actual_qfq_loader():
    module = load_bot_module()
    config = module._build_config(end_date=pd.Timestamp("2026-01-02"))
    assert config.source == "akshare_em_qfq"


def test_signal_handler_uses_daily_cache_instead_of_force_refreshing_every_query():
    source = BOT_PATH.read_text(encoding="utf-8")
    start = source.index("    def _handle_signal")
    end = source.index("    # ---- params", start)
    handle_signal_source = source[start:end]
    assert "force_refresh=True" not in handle_signal_source
    assert "force_refresh=live" in handle_signal_source


def test_target_vol_keeps_strategy_return_window_pending_research_adoption():
    module = load_bot_module()
    dates = pd.bdate_range("2026-01-01", periods=160)
    active_returns = np.array([0.01, -0.01] * 40, dtype=float)
    cash_returns = np.zeros(80, dtype=float)
    curve = pd.DataFrame(
        {
            "return": np.concatenate([active_returns, cash_returns]),
            "asset_return": np.concatenate([active_returns, cash_returns]),
            "position_before": ["159915.SZ"] * 80 + ["CASH"] * 80,
            "fraction_before": [1.0] * 80 + [0.0] * 80,
        },
        index=dates,
    )

    realized_vol, _effective_scale, next_scale = module._compute_target_vol_scales(
        curve,
        target_vol=0.20,
        vol_window=80,
        max_lev=1.5,
    )

    assert realized_vol.iloc[-1] == pytest.approx(0.0)
    assert next_scale.iloc[-1] == pytest.approx(1.5)


@pytest.mark.parametrize("max_lev", [1.2, 0.6, 0.0])
def test_target_vol_warmup_uses_capped_initial_scale_and_preserves_shift_timing(max_lev):
    module = load_bot_module()
    dates = pd.bdate_range("2026-01-01", periods=5)
    curve = pd.DataFrame({"return": [0.0, 0.01, -0.01, 0.02, -0.02]}, index=dates)
    initial_scale = min(1.0, max_lev)

    realized_vol, effective_scale, next_scale = module._compute_target_vol_scales(
        curve,
        target_vol=0.20,
        vol_window=3,
        max_lev=max_lev,
    )

    assert realized_vol.iloc[:2].isna().all()
    assert next_scale.iloc[:2].tolist() == pytest.approx([initial_scale, initial_scale])
    assert effective_scale.iloc[0] == pytest.approx(initial_scale)
    assert effective_scale.iloc[1:].tolist() == pytest.approx(next_scale.iloc[:-1].tolist())
    assert np.isfinite(next_scale.to_numpy()).all()
    assert (next_scale >= 0.0).all()
    assert (next_scale <= max_lev).all()


def test_target_vol_zero_volatility_full_window_uses_max_leverage_next_period():
    module = load_bot_module()
    dates = pd.bdate_range("2026-01-01", periods=4)
    curve = pd.DataFrame({"return": [0.0, 0.0, 0.0, 0.0]}, index=dates)

    realized_vol, effective_scale, next_scale = module._compute_target_vol_scales(
        curve,
        target_vol=0.20,
        vol_window=3,
        max_lev=1.2,
    )

    assert realized_vol.iloc[2:].tolist() == pytest.approx([0.0, 0.0])
    assert next_scale.tolist() == pytest.approx([1.0, 1.0, 1.2, 1.2])
    assert effective_scale.tolist() == pytest.approx([1.0, 1.0, 1.0, 1.2])


@pytest.mark.parametrize(
    ("target_vol", "vol_window", "max_lev"),
    [
        (0.0, 3, 1.2),
        (-0.1, 3, 1.2),
        (math.nan, 3, 1.2),
        (math.inf, 3, 1.2),
        (0.2, True, 1.2),
        (0.2, 1, 1.2),
        (0.2, 3.0, 1.2),
        (0.2, 3, -0.1),
        (0.2, 3, math.nan),
        (0.2, 3, math.inf),
    ],
)
def test_target_vol_rejects_invalid_parameters(target_vol, vol_window, max_lev):
    module = load_bot_module()
    curve = pd.DataFrame({"return": [0.0, 0.01, -0.01]})

    with pytest.raises(ValueError):
        module._compute_target_vol_scales(curve, target_vol, vol_window, max_lev)


@pytest.mark.parametrize("bad_return", [math.nan, math.inf, -math.inf])
def test_target_vol_rejects_nonfinite_returns(bad_return):
    module = load_bot_module()
    curve = pd.DataFrame({"return": [0.0, bad_return, 0.01]})

    with pytest.raises(ValueError, match="(?i)return.*finite"):
        module._compute_target_vol_scales(curve, target_vol=0.20, vol_window=2, max_lev=1.2)


def test_target_vol_rejects_nonfinite_realized_vol_after_warmup():
    module = load_bot_module()
    curve = pd.DataFrame({"return": [1e308, -1e308, 1e308]})

    with pytest.raises(ValueError, match="(?i)realized volatility.*finite"):
        module._compute_target_vol_scales(curve, target_vol=0.20, vol_window=2, max_lev=1.2)


def test_target_vol_rejects_nullable_missing_return_with_value_error():
    module = load_bot_module()
    curve = pd.DataFrame({"return": pd.Series([0.0, pd.NA, 0.01], dtype="object")})

    with pytest.raises(ValueError, match="(?i)return.*finite"):
        module._compute_target_vol_scales(curve, target_vol=0.20, vol_window=2, max_lev=1.2)


def test_target_vol_scale_threshold_starts_from_explicit_initial_scale():
    module = load_bot_module()
    raw = pd.Series([0.62, 0.58, 0.40])

    confirmed = module.apply_target_vol_scale_rebalance_threshold(
        raw,
        threshold=0.075,
        initial_scale=0.60,
    )

    assert confirmed.tolist() == pytest.approx([0.60, 0.60, 0.40])


def test_price_forward_fill_metadata_marks_suspended_asset_only():
    module = load_bot_module()
    dates = pd.to_datetime(["2026-06-17", "2026-06-18"])
    raw = pd.DataFrame(1.0, index=dates, columns=list(module.ASSETS))
    raw.loc[dates[1], "159941.SZ"] = math.nan
    aligned = raw.ffill()
    flags = module._price_forward_fill_flags(raw, aligned, list(module.ASSETS))
    daily = minimal_daily(module, dates=("2026-06-17", "2026-06-18"))

    out = module._attach_price_fill_metadata(daily, flags)

    assert out.loc[1, "price_ffill_159941.SZ"] is True
    assert out.loc[1, "price_ffill_159915.SZ"] is False


def test_trade_leg_with_forward_filled_price_blocks_execution(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    fill_live_quote_pairs(module, daily, row_idx=0, quote_time="2026-06-18 14:54:30")
    daily.loc[0, "actual_position_before"] = "159941.SZ"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "sell_delta"] = 0.5
    daily.loc[0, "buy_delta"] = 0.5
    daily.loc[0, "price_ffill_159941.SZ"] = True
    daily.loc[0, "last_date_159941.SZ"] = "2026-06-17"

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=True,
        now=datetime(2026, 6, 18, 14, 55),
        purpose="execution",
    )

    assert status["stale_price_trade_assets"] == ["159941.SZ"]
    assert status["all_trade_legs_have_current_prices"] is False
    assert status["strategy_actionable_now"] is False
    assert status["action_required_now"] is False
    assert "前值填充" in status["execution_note"]


def test_calendar_failure_reason_prefers_context_local_value():
    module = load_bot_module()
    module._set_calendar_failure("context-local")

    assert module._calendar_failure_reason() == "context-local"


def test_research_source_names_use_canonical_data_source_labels():
    module = load_research_module()

    assert module._canonical_source("eastmoney") == "akshare_em_qfq"
    assert module._canonical_source("sina") == "akshare_sina_raw"

    config = module.RunConfig(
        source="akshare_em_qfq",
        one_way_cost=0.001,
        start_date=pd.Timestamp("2026-01-01"),
        end_date=pd.Timestamp("2026-01-02"),
        output_tag="unit",
        target_vols=(),
        vol_window=80,
        max_lev=1.5,
    )
    assert config.source == "akshare_em_qfq"


def test_external_http_calls_use_reusable_sessions():
    bot_source = BOT_PATH.read_text(encoding="utf-8")
    research_source = RESEARCH_PATH.read_text(encoding="utf-8")

    assert "requests.get(" not in bot_source
    assert "requests.get(" not in research_source
    assert "requests.Session()" in bot_source
    assert "requests.Session()" in research_source


def test_align_prices_forward_fills_single_asset_suspension_after_asset_starts(monkeypatch):
    module = load_bot_module()
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-05"])
    prices = pd.DataFrame(1.0, index=dates, columns=list(module.ASSETS))
    prices.loc[dates[0], "513520.SH"] = 2.0
    prices.loc[dates[1], "513520.SH"] = math.nan
    prices.loc[dates[2], "513520.SH"] = 2.2
    monkeypatch.setattr(module, "_expected_cn_trading_days", lambda start, end: pd.DatetimeIndex(dates))

    aligned, common_last, last_by_asset = module.align_prices_to_common_valid_date(
        prices,
        list(module.ASSETS),
        calendar_validation_mode="warning",
    )

    assert common_last == dates[-1]
    assert aligned.loc[dates[1], "513520.SH"] == pytest.approx(2.0)
    assert last_by_asset["513520.SH"] == dates[-1]


def test_align_prices_rejects_missing_common_trading_day(monkeypatch):
    module = load_bot_module()
    dates = pd.to_datetime(["2026-06-15", "2026-06-16", "2026-06-18"])
    prices = pd.DataFrame(1.0, index=dates, columns=list(module.ASSETS))

    def expected_sessions(start, end):
        return pd.DatetimeIndex(
            pd.to_datetime(["2026-06-15", "2026-06-16", "2026-06-17", "2026-06-18"])
        )

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions, raising=False)

    with pytest.raises(ValueError, match="missing common trading dates.*2026-06-17"):
        module.align_prices_to_common_valid_date(prices, list(module.ASSETS))


def test_held_asset_missing_price_raises_instead_of_zero_return(monkeypatch):
    module = load_bot_module()
    monkeypatch.setattr(module, "LOOKBACK", 2)

    def fake_scores(prices, idx, r2_threshold=None):
        return {"159915.SZ": 1.0}, {"159915.SZ": 0.9}, {"159915.SZ": 1.0}

    monkeypatch.setattr(module, "calc_scores", fake_scores)
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-05"])
    prices = pd.DataFrame(1.0, index=dates, columns=list(module.ASSETS))
    prices.loc[dates[2], "159915.SZ"] = math.nan
    config = module.RunConfig(
        source="akshare_em_qfq",
        one_way_cost=0.001,
        start_date=dates[0],
        end_date=dates[-1],
        output_tag="unit",
        target_vols=(),
        vol_window=80,
        max_lev=1.5,
    )

    with pytest.raises(RuntimeError, match="missing close"):
        module.run_staged_entry(
            prices,
            config,
            module.EntryCase("full_entry", "full_entry", 1.0),
            r2_threshold=0.2,
            switch_buffer=1.0,
        )


def _run_v11_stale_trade_case(monkeypatch, stale_asset, staged=False):
    module = load_bot_module()
    monkeypatch.setattr(module, "LOOKBACK", 2)
    old_asset, new_asset = list(module.ASSETS)[:2]
    dates = pd.bdate_range("2026-01-01", periods=4)
    prices = pd.DataFrame(100.0, index=dates, columns=list(module.ASSETS))
    if staged:
        prices.loc[dates[2], old_asset] = 101.0
        prices.loc[dates[3], old_asset] = 100.0

    def fake_scores(prices, idx, r2_threshold=None):
        target = old_asset if staged or idx < len(prices) - 1 else new_asset
        scores = {old_asset: 1.0, new_asset: 0.5}
        scores[target] = 2.0
        return scores, {code: 0.9 for code in scores}, scores.copy()

    monkeypatch.setattr(module, "calc_scores", fake_scores)
    flags = pd.DataFrame(False, index=dates, columns=list(module.ASSETS))
    flags.loc[dates[-1], stale_asset] = True
    config = module.RunConfig(
        source="akshare_em_qfq",
        one_way_cost=0.001,
        start_date=dates[0],
        end_date=dates[-1],
        output_tag="unit",
        target_vols=(),
        vol_window=80,
        max_lev=1.5,
    )
    case = module.EntryCase(
        "staged" if staged else "full",
        "all_new_asset_50_wait_down" if staged else "full_entry",
        0.5 if staged else 1.0,
    )
    curve = module.run_staged_entry(
        prices,
        config,
        case,
        r2_threshold=0.2,
        switch_buffer=1.0,
        price_ffill_flags=flags,
    )
    return module, curve, dates, old_asset, new_asset


def test_v11_stale_buy_leg_atomically_blocks_switch(monkeypatch):
    module = load_bot_module()
    new_asset = list(module.ASSETS)[1]
    _, curve, dates, old_asset, _ = _run_v11_stale_trade_case(monkeypatch, new_asset)
    row = curve.loc[dates[-1]]

    assert bool(row["trade_blocked_by_stale_price"]) is True
    assert row["blocked_trade_target"] == new_asset
    assert new_asset in row["stale_price_trade_assets"].split(",")
    assert row["position_before"] == old_asset
    assert row["position"] == old_asset
    assert pd.isna(row["trade_target"])
    assert row["turnover"] == pytest.approx(0.0)
    assert row["cost"] == pytest.approx(0.0)


def test_v11_stale_sell_leg_atomically_blocks_switch(monkeypatch):
    module = load_bot_module()
    old_asset = list(module.ASSETS)[0]
    _, curve, dates, _, new_asset = _run_v11_stale_trade_case(monkeypatch, old_asset)
    row = curve.loc[dates[-1]]

    assert bool(row["trade_blocked_by_stale_price"]) is True
    assert row["blocked_trade_target"] == new_asset
    assert old_asset in row["stale_price_trade_assets"].split(",")
    assert row["position"] == row["position_before"] == old_asset
    assert row["turnover"] == pytest.approx(0.0)
    assert row["cost"] == pytest.approx(0.0)


def test_v11_stale_staged_fill_restores_pending_state_and_counters(monkeypatch):
    module = load_bot_module()
    old_asset = list(module.ASSETS)[0]
    _, curve, dates, _, _ = _run_v11_stale_trade_case(monkeypatch, old_asset, staged=True)
    before = curve.loc[dates[-2]]
    row = curve.loc[dates[-1]]

    assert bool(row["trade_blocked_by_stale_price"]) is True
    assert row["position"] == row["position_before"] == old_asset
    assert row["holding_fraction"] == pytest.approx(row["fraction_before"])
    assert row["pending_entry_target"] == before["pending_entry_target"] == old_asset
    assert row["pending_entry_since"] == before["pending_entry_since"]
    assert row["pending_entry_days"] == before["pending_entry_days"]
    assert row["staged_initial_count"] == before["staged_initial_count"]
    assert row["staged_fill_count"] == before["staged_fill_count"]
    assert bool(row["fill_on_down_day"]) is False
    assert row["turnover"] == pytest.approx(0.0)


@pytest.mark.parametrize("bad_mask", ["missing_date", "missing_asset", "na", "string", "duplicate_date", "intraday"])
def test_v11_explicit_ffill_mask_is_strictly_validated(bad_mask):
    module = load_bot_module()
    dates = pd.bdate_range("2026-01-01", periods=2)
    prices = pd.DataFrame(100.0, index=dates, columns=list(module.ASSETS))
    flags = pd.DataFrame(False, index=dates, columns=list(module.ASSETS))
    if bad_mask == "missing_date":
        flags = flags.iloc[:-1]
    elif bad_mask == "missing_asset":
        flags = flags.drop(columns=[list(module.ASSETS)[0]])
    elif bad_mask == "na":
        flags = flags.astype(object)
        flags.iloc[0, 0] = None
    elif bad_mask == "string":
        flags = flags.astype(str)
    elif bad_mask == "duplicate_date":
        duplicate = flags.iloc[[0]].copy()
        duplicate.index = pd.DatetimeIndex([dates[0] + pd.Timedelta(hours=12)])
        flags = pd.concat([flags, duplicate])
    else:
        flags.index = flags.index + pd.Timedelta(hours=12)
    config = module.RunConfig("akshare_em_qfq", 0.001, dates[0], dates[-1], "unit", (), 80, 1.5)

    with pytest.raises((ValueError, RuntimeError), match="(?i)(mask|ffill)"):
        module.run_staged_entry(
            prices,
            config,
            module.EntryCase("full", "full_entry", 1.0),
            0.2,
            1.0,
            price_ffill_flags=flags,
        )


def test_v11_live_quote_is_added_to_raw_availability_before_ffill_flags():
    module = load_bot_module()
    yesterday, today = pd.to_datetime(["2026-01-01", "2026-01-02"])
    raw = pd.DataFrame(1.0, index=[yesterday], columns=list(module.ASSETS))
    updated = pd.DataFrame(1.0, index=[yesterday, today], columns=list(module.ASSETS))
    metadata = {
        code: {"quote_date": today, "quote_price": 2.0 + offset}
        for offset, code in enumerate(module.ASSETS)
    }

    synced = module._sync_live_quote_raw_availability(raw, updated, metadata)
    flags = module._price_forward_fill_flags(synced, updated, list(module.ASSETS))

    assert not flags.loc[today, list(module.ASSETS)].any()


def test_v11_live_daily_path_marks_valid_live_quotes_as_not_forward_filled(monkeypatch):
    module = load_bot_module()
    yesterday, today = pd.to_datetime(["2026-01-01", "2026-01-02"])
    historical = pd.DataFrame(1.0, index=[yesterday], columns=list(module.ASSETS))
    updated = pd.DataFrame(1.0, index=[yesterday, today], columns=list(module.ASSETS))
    metadata = {
        code: {"quote_date": today, "quote_price": 2.0 + offset}
        for offset, code in enumerate(module.ASSETS)
    }
    sources = pd.DataFrame({"source": ["unit"], "adjustment": [module.ADJUSTMENT_QFQ], "source_detail": ["unit"]})

    monkeypatch.setattr(module, "load_close", lambda config: (historical.copy(), sources.copy()))
    monkeypatch.setattr(module, "_load_live_quotes_for_prices", lambda *args, **kwargs: pd.DataFrame({"source": ["unit"]}))
    monkeypatch.setattr(module, "_apply_live_quotes_to_prices", lambda *args, **kwargs: (updated.copy(), metadata))
    monkeypatch.setattr(
        module,
        "align_prices_to_common_valid_date",
        lambda prices, assets: (prices.copy(), today, {code: today for code in module.ASSETS}),
    )

    def fake_build_curves(input_prices, config, price_ffill_flags=None):
        assert not price_ffill_flags.loc[today, list(module.ASSETS)].any()
        daily = minimal_daily(module, dates=("2026-01-01", "2026-01-02"))
        daily.index = pd.DatetimeIndex([yesterday, today])
        return [daily.drop(columns=["date"])]

    monkeypatch.setattr(module, "build_curves", fake_build_curves)

    daily, _ = module._build_v11_daily(end_date=today, data_state="live")

    assert not daily.loc[daily["date"] == today, [f"price_ffill_{code}" for code in module.ASSETS]].iloc[0].any()


def test_v11_build_curves_blocks_stale_target_vol_sell_and_carries_actual_exposure(monkeypatch):
    module = load_bot_module()
    dates = pd.bdate_range("2026-01-01", periods=3)
    asset = list(module.ASSETS)[0]
    prices = pd.DataFrame(100.0, index=dates, columns=list(module.ASSETS))
    flags = pd.DataFrame(False, index=dates, columns=list(module.ASSETS))
    flags.loc[dates[1]:, asset] = True
    base = pd.DataFrame(
        {
            "position_before": ["CASH", asset, asset],
            "position": [asset, asset, asset],
            "fraction_before": [0.0, 1.0, 1.0],
            "holding_fraction": [1.0, 1.0, 1.0],
            "trade_target": [asset, None, None],
            "asset_return": [0.0, 0.0, 0.0],
            "gross_return": [0.0, 0.0, 0.0],
            "return": [0.0, 0.0, 0.0],
            "nav": [1.0, 1.0, 1.0],
            "turnover": [1.0, 0.0, 0.0],
            "cost": [0.0, 0.0, 0.0],
        },
        index=dates,
    )
    monkeypatch.setattr(module, "run_staged_entry", lambda *args, **kwargs: base.copy())
    monkeypatch.setattr(
        module,
        "_compute_target_vol_scales",
        lambda *args: (
            pd.Series(0.1, index=dates),
            pd.Series([1.0, 1.0, 0.5], index=dates),
            pd.Series([1.0, 0.5, 0.5], index=dates),
        ),
    )
    monkeypatch.setattr(module, "apply_overheat_overlay", lambda curve, *args, **kwargs: curve)
    monkeypatch.setattr(module, "build_overheat_features", lambda prices: {})
    config = module.RunConfig("akshare_em_qfq", 0.001, dates[0], dates[-1], "unit", (), 80, 1.5)

    out = module.build_curves(prices, config, price_ffill_flags=flags)[0]

    for date in dates[1:]:
        assert bool(out.loc[date, "trade_blocked_by_stale_price"]) is True
        assert out.loc[date, "turnover"] == pytest.approx(0.0)
        assert out.loc[date, "cost"] == pytest.approx(0.0)
        assert out.loc[date, "final_exposure_after_overheat"] == pytest.approx(1.0)


def test_v11_build_curves_blocks_stale_overheat_sell_and_carries_actual_exposure(monkeypatch):
    module = load_bot_module()
    dates = pd.bdate_range("2026-01-01", periods=3)
    asset = list(module.ASSETS)[0]
    prices = pd.DataFrame(100.0, index=dates, columns=list(module.ASSETS))
    flags = pd.DataFrame(False, index=dates, columns=list(module.ASSETS))
    flags.loc[dates[1]:, asset] = True
    base = pd.DataFrame(
        {
            "position_before": ["CASH", asset, asset], "position": [asset, asset, asset],
            "fraction_before": [0.0, 1.0, 1.0], "holding_fraction": [1.0, 1.0, 1.0],
            "trade_target": [asset, None, None], "asset_return": [0.0, 0.0, 0.0],
            "gross_return": [0.0, 0.0, 0.0], "return": [0.0, 0.0, 0.0],
            "nav": [1.0, 1.0, 1.0], "turnover": [1.0, 0.0, 0.0], "cost": [0.0, 0.0, 0.0],
        }, index=dates,
    )
    monkeypatch.setattr(module, "run_staged_entry", lambda *args, **kwargs: base.copy())
    monkeypatch.setattr(
        module, "_compute_target_vol_scales",
        lambda *args: tuple(pd.Series(1.0, index=dates) for _ in range(3)),
    )
    features = {
        code: pd.DataFrame(
            {"bias": [0.0, 1.0, 1.0], "bias_mom": [0.0, 1.0, 1.0], "same_side": [False, True, True]},
            index=dates,
        ) for code in module.ASSETS
    }
    monkeypatch.setattr(module, "build_overheat_features", lambda prices: features)
    config = module.RunConfig("akshare_em_qfq", 0.001, dates[0], dates[-1], "unit", (), 80, 1.5)

    out = module.build_curves(prices, config, price_ffill_flags=flags)[0]
    for date in dates[1:]:
        assert bool(out.loc[date, "trade_blocked_by_stale_price"]) is True
        assert out.loc[date, "turnover"] == pytest.approx(0.0)
        assert out.loc[date, "final_exposure_after_overheat"] == pytest.approx(
            out.loc[date, "drifted_exposure_before_trade"]
        )
        assert out.loc[date, "actual_position_next"] == asset


def test_v11_stale_zero_overheat_recovery_keeps_actual_full_position(monkeypatch):
    module = load_bot_module()
    dates = pd.bdate_range("2026-01-01", periods=4)
    asset = list(module.ASSETS)[0]
    prices = pd.DataFrame(100.0, index=dates, columns=list(module.ASSETS))
    flags = pd.DataFrame(False, index=dates, columns=list(module.ASSETS))
    flags.loc[dates[2], asset] = True
    base = pd.DataFrame(
        {
            "position_before": ["CASH", asset, asset, asset],
            "position": [asset, asset, asset, asset],
            "fraction_before": [0.0, module.INITIAL_ENTRY_FRACTION, 1.0, 1.0],
            "holding_fraction": [module.INITIAL_ENTRY_FRACTION, 1.0, 1.0, 1.0],
            "trade_target": [asset, asset, None, None],
            "trade_fraction": [module.INITIAL_ENTRY_FRACTION, 1.0, 1.0, 1.0],
            "pending_entry_target": [asset, None, None, None],
            "pending_entry_since": [dates[0], None, None, None],
            "pending_entry_days": [0, 0, 0, 0],
            "staged_initial": [True, False, False, False],
            "fill_on_down_day": [False, True, False, False],
            "asset_return": [0.0, -0.01, 0.0, 0.0],
            "gross_return": [0.0, -0.005, 0.0, 0.0],
            "return": [0.0, -0.005, 0.0, 0.0],
            "nav": [1.0, 0.995, 0.995, 0.995],
            "turnover": [module.INITIAL_ENTRY_FRACTION, 1.0 - module.INITIAL_ENTRY_FRACTION, 0.0, 0.0],
            "cost": [0.0, 0.0, 0.0, 0.0],
        }, index=dates,
    )
    monkeypatch.setattr(module, "run_staged_entry", lambda *args, **kwargs: base.copy())
    monkeypatch.setattr(
        module, "_compute_target_vol_scales",
        lambda *args: tuple(pd.Series(1.0, index=dates) for _ in range(3)),
    )
    features = {
        code: pd.DataFrame(
            {
                "bias": [0.0, 0.0, 1.0, 0.0],
                "bias_mom": [0.0, 0.0, 1.0, 0.0],
                "same_side": [False, False, True, False],
            }, index=dates,
        ) for code in module.ASSETS
    }
    monkeypatch.setattr(module, "build_overheat_features", lambda prices: features)
    config = module.RunConfig("akshare_em_qfq", 0.0, dates[0], dates[-1], "unit", (), 80, 1.5)

    out = module.build_curves(prices, config, price_ffill_flags=flags)[0]

    assert bool(out.loc[dates[2], "trade_blocked_by_stale_price"]) is True
    assert out.loc[dates[2], "final_exposure_after_overheat"] == pytest.approx(1.0)
    assert out.loc[dates[3], "final_exposure_after_overheat"] == pytest.approx(1.0)
    assert bool(out.loc[dates[3], "actual_staged_initial"]) is False
    assert out.loc[dates[3], "actual_position_next"] == asset


def test_v11_stale_overheat_reentry_waits_for_first_fresh_initial_fill(monkeypatch):
    module = load_bot_module()
    dates = pd.bdate_range("2026-01-01", periods=5)
    asset = list(module.ASSETS)[0]
    initial = module.INITIAL_ENTRY_FRACTION
    prices = pd.DataFrame(100.0, index=dates, columns=list(module.ASSETS))
    flags = pd.DataFrame(False, index=dates, columns=list(module.ASSETS))
    flags.loc[dates[3], asset] = True
    base = pd.DataFrame(
        {
            "position_before": ["CASH", asset, asset, asset, asset],
            "position": [asset] * 5,
            "fraction_before": [0.0, initial, 1.0, 1.0, 1.0],
            "holding_fraction": [initial, 1.0, 1.0, 1.0, 1.0],
            "trade_target": [asset, asset, None, None, None],
            "trade_fraction": [initial, 1.0, 1.0, 1.0, 1.0],
            "pending_entry_target": [asset, None, None, None, None],
            "pending_entry_since": [dates[0], None, None, None, None],
            "pending_entry_days": [0] * 5,
            "staged_initial": [True, False, False, False, False],
            "fill_on_down_day": [False, True, False, False, False],
            "asset_return": [0.0, -0.01, 0.0, 0.0, -0.01],
            "gross_return": [0.0, -0.005, 0.0, 0.0, -0.01],
            "return": [0.0, -0.005, 0.0, 0.0, -0.01],
            "nav": [1.0, 0.995, 0.995, 0.995, 0.98505],
            "turnover": [initial, 1.0 - initial, 0.0, 0.0, 0.0],
            "cost": [0.0] * 5,
        }, index=dates,
    )
    monkeypatch.setattr(module, "run_staged_entry", lambda *args, **kwargs: base.copy())
    monkeypatch.setattr(
        module, "_compute_target_vol_scales",
        lambda *args: tuple(pd.Series(1.0, index=dates) for _ in range(3)),
    )
    features = {
        code: pd.DataFrame(
            {
                "bias": [0.0, 0.0, 1.0, 0.0, 0.0],
                "bias_mom": [0.0, 0.0, 1.0, 0.0, 0.0],
                "same_side": [False, False, True, False, False],
            }, index=dates,
        ) for code in module.ASSETS
    }
    monkeypatch.setattr(module, "build_overheat_features", lambda prices: features)
    config = module.RunConfig("akshare_em_qfq", 0.0, dates[0], dates[-1], "unit", (), 80, 1.5)

    out = module.build_curves(prices, config, price_ffill_flags=flags)[0]

    assert out.loc[dates[2], "actual_position_next"] == "CASH"
    assert bool(out.loc[dates[3], "trade_blocked_by_stale_price"]) is True
    assert out.loc[dates[3], "actual_position_next"] == "CASH"
    assert pd.isna(out.loc[dates[3], "actual_pending_target"])
    assert bool(out.loc[dates[3], "actual_staged_initial"]) is False
    assert out.loc[dates[4], "final_exposure_after_overheat"] == pytest.approx(initial)
    assert bool(out.loc[dates[4], "actual_staged_initial"]) is True


def test_v11_recompute_prices_stale_carried_asset_with_its_own_return_and_fails_closed_without_it():
    module = load_bot_module()
    dates = pd.bdate_range("2026-01-01", periods=4)
    asset_a, asset_b = list(module.ASSETS)[:2]
    curve = pd.DataFrame(
        {
            "position_before": ["CASH", asset_a, asset_b, asset_b],
            "position": [asset_a, asset_b, asset_b, asset_b],
            "fraction_before": [0.0, 1.0, 1.0, 1.0],
            "holding_fraction": [1.0, 1.0, 1.0, 1.0],
            "trade_target": [asset_a, asset_b, None, None],
            "asset_return": [0.0, 0.0, -0.20, 0.0],
            f"asset_return_{asset_a}": [0.0, 0.0, 0.10, 0.0],
            f"asset_return_{asset_b}": [0.0, 0.0, -0.20, 0.0],
            "gross_return": [0.0, 0.0, -0.20, 0.0],
            "return": [0.0, 0.0, -0.20, 0.0],
            "nav": [1.0, 1.0, 0.8, 0.8],
            "turnover": [1.0, 2.0, 0.0, 0.0],
            "cost": [0.0] * 4,
        }, index=dates,
    )
    flags = pd.DataFrame(False, index=dates, columns=list(module.ASSETS))
    flags.loc[dates[1:2], asset_b] = True
    ones = pd.Series(1.0, index=dates)

    out = module._recompute_final_exposure_nav(curve, ones, ones, ones, ones, 0.0, flags)

    assert out.loc[dates[2], "actual_position_before"] == asset_a
    assert out.loc[dates[2], "gross_return"] == pytest.approx(0.10)
    assert out.loc[dates[2], "nav"] / out.loc[dates[1], "nav"] == pytest.approx(1.10)
    with pytest.raises(RuntimeError, match="(?i)asset.*return"):
        module._recompute_final_exposure_nav(
            curve.drop(columns=[f"asset_return_{asset_a}"]), ones, ones, ones, ones, 0.0, flags
        )


def test_v11_overlay_stale_audit_merges_with_existing_base_block():
    module = load_bot_module()
    date = pd.Timestamp("2026-01-01")
    asset_a, asset_b = list(module.ASSETS)[:2]
    curve = pd.DataFrame(
        {
            "position_before": ["CASH"], "position": [asset_a],
            "fraction_before": [0.0], "holding_fraction": [1.0],
            "trade_target": [None], "trade_fraction": [math.nan],
            "overheat_scale_next": [1.0],
            "trade_blocked_by_stale_price": [True],
            "blocked_trade_target": [asset_b],
            "stale_price_trade_assets": [asset_b],
        }, index=[date],
    )
    flags = pd.DataFrame(False, index=[date], columns=list(module.ASSETS))
    flags.at[date, asset_a] = True

    out = module._apply_zero_overheat_execution_guard(curve, flags)

    assert out.at[date, "blocked_trade_target"] == asset_b
    assert set(out.at[date, "stale_price_trade_assets"].split(",")) == {asset_a, asset_b}
    assert out.at[date, "overlay_blocked_trade_target"] == asset_a


def test_overheat_missing_features_keep_defense_on_instead_of_recovering():
    module = load_bot_module()
    dates = pd.to_datetime(["2026-01-01", "2026-01-02"])
    curve = pd.DataFrame(
        {
            "position_before": ["CASH", "159915.SZ"],
            "position": ["159915.SZ", "159915.SZ"],
            "fraction_before": [0.0, 1.0],
            "holding_fraction": [1.0, 1.0],
            "gross_return": [0.0, 0.0],
            "return": [0.0, 0.0],
            "nav": [1.0, 1.0],
            "turnover": [1.0, 0.0],
            "cost": [0.001, 0.0],
        },
        index=dates,
    )
    features = {
        "159915.SZ": pd.DataFrame(
            {
                "bias": [0.25, math.nan],
                "bias_mom": [1.0, math.nan],
                "same_side": [True, False],
            },
            index=dates,
        )
    }

    out = module.apply_overheat_overlay(
        curve,
        features,
        module.OverheatCase("unit", 0.20, 0.18, 0.0),
        one_way_cost=0.001,
    )

    assert out["overheat_on"].tolist() == [True, True]
    assert out["overheat_recovered"].tolist() == [False, False]


def test_overheat_zero_exposure_does_not_complete_staged_fill_in_background():
    module = load_bot_module()
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-05"])
    curve = pd.DataFrame(
        {
            "position_before": ["CASH", "159915.SZ", "159915.SZ"],
            "position": ["159915.SZ", "159915.SZ", "159915.SZ"],
            "fraction_before": [0.0, 0.5, 1.0],
            "holding_fraction": [0.5, 1.0, 1.0],
            "pending_entry_target": ["159915.SZ", None, None],
            "pending_entry_since": [dates[0], None, None],
            "pending_entry_days": [0, 0, 0],
            "trade_target": ["159915.SZ", "159915.SZ", None],
            "trade_fraction": [0.5, 1.0, math.nan],
            "staged_initial": [True, False, False],
            "fill_on_down_day": [False, True, False],
            "gross_return": [0.0, 0.0, 0.0],
            "return": [0.0, 0.0, 0.0],
            "nav": [1.0, 1.0, 1.0],
            "turnover": [0.5, 0.5, 0.0],
            "cost": [0.0005, 0.0005, 0.0],
        },
        index=dates,
    )
    features = {
        "159915.SZ": pd.DataFrame(
            {
                "bias": [0.25, 0.24, 0.10],
                "bias_mom": [1.0, 1.0, -1.0],
                "same_side": [True, True, False],
            },
            index=dates,
        )
    }

    out = module.apply_overheat_overlay(
        curve,
        features,
        module.OverheatCase("unit", 0.20, 0.18, 0.0),
        one_way_cost=0.001,
    )

    assert bool(out.loc[dates[1], "fill_on_down_day"]) is False
    assert float(out.loc[dates[1], "holding_fraction"]) == pytest.approx(0.0)
    assert float(out.loc[dates[2], "fraction_before"]) == pytest.approx(0.0)
    assert float(out.loc[dates[2], "holding_fraction"]) == pytest.approx(module.INITIAL_ENTRY_FRACTION)
    assert float(out.loc[dates[2], "final_exposure_after_overheat"]) == pytest.approx(module.INITIAL_ENTRY_FRACTION)


def test_zero_exposure_trade_text_reports_no_buy_instruction():
    module = load_bot_module()
    sig = {
        "position_before": "CASH",
        "position": "159915.SZ",
        "trade_target": "159915.SZ",
        "exposure_effective": 0.0,
        "final_exposure": 0.0,
        "turnover": 0.0,
    }

    assert "不买入" in module._signal_action_text(sig)
    assert module._trade_action_label(sig) == "不买入，保持0敞口"


def test_performance_rebases_window_start_before_compounding_returns():
    module = load_bot_module()
    daily = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-05"]),
            "nav": [1.10, 1.10, 1.21],
            "return": [0.10, 0.0, 0.10],
            "turnover": [0.0, 0.0, 0.0],
            "weight": [1.0, 1.0, 1.0],
            "final_exposure_after_overheat": [0.0, 0.0, 0.0],
            "exposure_effective": [0.5, 0.75, 1.0],
            "position": ["159915.SZ", "159915.SZ", "159915.SZ"],
            "overheat_on": [False, False, False],
            "overheat_on_effective": [False, True, False],
        }
    )

    perf = module.calc_performance(daily, pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-05"))
    yearly = module.calc_yearly_performance(daily, pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-05"))
    window = module._nav_window(daily, pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-05"))

    assert float(window["nav_norm"].iloc[0]) == pytest.approx(1.0)
    assert perf["total"] == pytest.approx(0.10)
    assert yearly[0]["return"] == pytest.approx(0.10)
    assert float(window["nav_norm"].iloc[-1]) == pytest.approx(1.10)
    assert perf["avg_final_exposure"] == pytest.approx(0.75)
    assert perf["overheat_days"] == 1


def test_performance_handler_reports_na_reason_for_failed_mandatory_windows(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-08", "2026-06-09"))

    class CaptureMessage:
        def __init__(self):
            self.parts = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def write(self, value):
            self.parts.append(str(value))

        def attach_file(self, *args, **kwargs):
            return None

    msg = CaptureMessage()

    def fail_calc(daily_arg, start, end):
        raise RuntimeError("window too short")

    monkeypatch.setattr(module, "_get_daily_for_today", lambda data_state="confirmed": (daily, "unit-source"))
    monkeypatch.setattr(module, "_write_nav_curve", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "calc_performance", fail_calc)
    monkeypatch.setattr(module.poe, "start_message", lambda: msg, raising=False)

    module.SubDSixEtfV11Bot()._handle_performance("performance")

    text = "".join(msg.parts)
    assert "N/A: window too short" in text
    assert "| full_sample | N/A:" in text


def test_custom_performance_query_keeps_mandatory_windows():
    module = load_bot_module()

    ranges = module.resolve_performance_ranges(
        "调仓记录 过去两个月",
        now=datetime(2026, 6, 18, 10, 0, tzinfo=module.CN_TZ),
        latest_date=pd.Timestamp("2026-06-18"),
        earliest_date=pd.Timestamp("2020-01-02"),
    )

    labels = [label for label, _start, _end in ranges]
    assert labels[0] == "2026-04-18~2026-06-18"
    for required in ("full_sample", "10Y", "5Y", "3Y", "1Y"):
        assert required in labels


def test_performance_handler_reports_na_when_mandatory_window_history_is_short(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-08", "2026-06-09"))

    class CaptureMessage:
        def __init__(self):
            self.parts = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def write(self, value):
            self.parts.append(str(value))

        def attach_file(self, *args, **kwargs):
            return None

    msg = CaptureMessage()

    monkeypatch.setattr(module, "_get_daily_for_today", lambda data_state="confirmed": (daily, "unit-source"))
    monkeypatch.setattr(module, "_write_nav_curve", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.poe, "start_message", lambda: msg, raising=False)

    module.SubDSixEtfV11Bot()._handle_performance("performance")

    text = "".join(msg.parts)
    assert "| 10Y | N/A: insufficient history" in text
    assert "| 5Y | N/A: insufficient history" in text
    assert "| 3Y | N/A: insufficient history" in text
    assert "| 1Y | N/A: insufficient history" in text


def test_performance_rejects_missing_return_inside_window():
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-01-01", "2026-01-02", "2026-01-05"))
    daily["return"] = [0.01, math.nan, 0.02]

    with pytest.raises(module.poe.BotError, match="missing return"):
        module.calc_performance(daily, pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-05"))


def test_performance_handler_reports_yearly_and_trade_record_failures(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-08", "2026-06-09", "2026-06-10"))

    class CaptureMessage:
        def __init__(self):
            self.parts = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def write(self, value):
            self.parts.append(str(value))

        def attach_file(self, *args, **kwargs):
            return None

    msg = CaptureMessage()

    monkeypatch.setattr(module, "_get_daily_for_today", lambda data_state="confirmed": (daily, "unit-source"))
    monkeypatch.setattr(module, "_write_nav_curve", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "calc_yearly_performance", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("yearly broken")))
    monkeypatch.setattr(module, "format_trade_records_table", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("records broken")))
    monkeypatch.setattr(module.poe, "start_message", lambda: msg, raising=False)

    module.SubDSixEtfV11Bot()._handle_performance("performance")

    text = "".join(msg.parts)
    assert "N/A: yearly broken" in text
    assert "N/A: records broken" in text


def test_force_refresh_replaces_performance_cache(monkeypatch):
    module = load_bot_module()
    calls = []

    def fake_build(end_date=None):
        calls.append(len(calls) + 1)
        return pd.DataFrame({"marker": [calls[-1]]}), f"source-{calls[-1]}"

    monkeypatch.setattr(module, "_build_v11_daily", fake_build)
    if hasattr(module._cached_daily, "cache_clear"):
        module._cached_daily.cache_clear()

    first, _ = module._get_daily_for_today(force_refresh=False)
    refreshed, _ = module._get_daily_for_today(force_refresh=True)
    again, _ = module._get_daily_for_today(force_refresh=False)

    assert int(first["marker"].iloc[0]) == 1
    assert int(refreshed["marker"].iloc[0]) == 2
    assert int(again["marker"].iloc[0]) == 2


def test_call_build_v11_daily_does_not_swallow_internal_unexpected_keyword_typeerror(monkeypatch):
    module = load_bot_module()

    def fake_build(end_date=None, data_state="confirmed", now=None):
        if data_state == "live":
            raise TypeError("unexpected keyword inside provider parser")
        return pd.DataFrame({"marker": ["legacy-fallback"]}), "legacy"

    monkeypatch.setattr(module, "_build_v11_daily", fake_build)

    with pytest.raises(TypeError, match="inside provider parser"):
        module._call_build_v11_daily(
            pd.Timestamp("2026-06-18"),
            "live",
            datetime(2026, 6, 18, 14, 55, tzinfo=module.CN_TZ),
        )


def test_performance_preparation_drops_intraday_today_bar():
    module = load_bot_module()
    daily = minimal_daily(module)

    confirmed = module.prepare_daily_for_performance(
        daily,
        now=datetime(2026, 6, 9, 13, 0),
    )

    assert confirmed["date"].max().date().isoformat() == "2026-06-08"


def test_overheat_guard_recomputes_returns_and_refills_on_actual_down_day():
    module = load_bot_module()
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-05", "2026-01-06"])
    curve = pd.DataFrame(
        {
            "position_before": ["CASH", "159915.SZ", "159915.SZ", "159915.SZ"],
            "position": ["159915.SZ", "159915.SZ", "159915.SZ", "159915.SZ"],
            "fraction_before": [0.0, 0.5, 1.0, 1.0],
            "holding_fraction": [0.5, 1.0, 1.0, 1.0],
            "pending_entry_target": ["159915.SZ", None, None, None],
            "pending_entry_since": [dates[0], None, None, None],
            "pending_entry_days": [0, 0, 0, 0],
            "trade_target": ["159915.SZ", "159915.SZ", None, None],
            "trade_fraction": [0.5, 1.0, math.nan, math.nan],
            "staged_initial": [True, False, False, False],
            "fill_on_down_day": [False, True, False, False],
            "asset_return": [0.0, -0.02, 0.001, -0.01],
            "gross_return": [0.0, -0.02, 0.001, -0.01],
            "return": [0.0, -0.02, 0.001, -0.01],
            "nav": [1.0, 0.98, 0.98098, 0.9711702],
            "turnover": [0.5, 0.5, 0.0, 0.0],
            "cost": [0.0, 0.0, 0.0, 0.0],
        },
        index=dates,
    )
    features = {
        "159915.SZ": pd.DataFrame(
            {
                "bias": [0.25, 0.24, 0.10, 0.11],
                "bias_mom": [1.0, 1.0, -1.0, -1.0],
                "same_side": [True, True, False, False],
            },
            index=dates,
        )
    }

    out = module.apply_overheat_overlay(
        curve,
        features,
        module.OverheatCase("unit", 0.20, 0.18, 0.0),
        one_way_cost=0.0,
    )

    assert float(out.loc[dates[2], "fraction_before"]) == pytest.approx(0.0)
    assert float(out.loc[dates[2], "holding_fraction"]) == pytest.approx(module.INITIAL_ENTRY_FRACTION)
    assert float(out.loc[dates[2], "gross_return"]) == pytest.approx(0.0)
    assert out.loc[dates[0], "actual_entry_state"] == "BLOCKED_BY_OVERHEAT"
    assert pd.isna(out.loc[dates[0], "actual_pending_target"])
    assert out.loc[dates[2], "actual_entry_state"] == "HALF_POSITION_WAIT_DOWN"
    assert pd.Timestamp(out.loc[dates[2], "actual_pending_since"]) == dates[2]
    assert int(out.loc[dates[2], "actual_pending_days"]) == 0
    assert bool(out.loc[dates[2], "actual_staged_initial"]) is True
    assert bool(out.loc[dates[3], "fill_on_down_day"]) is True
    assert out.loc[dates[3], "actual_entry_state"] == "FULL_POSITION"
    assert bool(out.loc[dates[3], "actual_fill_on_down_day"]) is True
    assert float(out.loc[dates[3], "fraction_before"]) == pytest.approx(module.INITIAL_ENTRY_FRACTION)
    assert float(out.loc[dates[3], "holding_fraction"]) == pytest.approx(1.0)
    assert float(out.loc[dates[3], "gross_return"]) == pytest.approx(-0.005)


def test_recompute_nav_does_not_rebalance_same_asset_price_drift_without_signal():
    module = load_bot_module()
    date = pd.Timestamp("2026-01-02")
    curve = pd.DataFrame(
        {
            "position_before": ["159915.SZ"],
            "position": ["159915.SZ"],
            "fraction_before": [0.5],
            "holding_fraction": [0.5],
            "asset_return": [0.10],
            "gross_return": [0.05],
            "return": [0.05],
            "nav": [1.05],
            "turnover": [0.0],
            "cost": [0.0],
        },
        index=[date],
    )
    ones = pd.Series(1.0, index=curve.index)

    out = module._recompute_final_exposure_nav(curve, ones, ones, ones, ones, one_way_cost=0.001)

    drifted = 0.5 * 1.10 / 1.05
    assert float(out.loc[date, "gross_return"]) == pytest.approx(0.05)
    assert float(out.loc[date, "turnover"]) == pytest.approx(0.0)
    assert float(out.loc[date, "rebalance_delta"]) == pytest.approx(0.0)
    assert float(out.loc[date, "buy_delta"]) == pytest.approx(0.0)
    assert float(out.loc[date, "sell_delta"]) == pytest.approx(0.0)
    assert float(out.loc[date, "cost"]) == pytest.approx(0.0)
    assert float(out.loc[date, "final_exposure_after_overheat"]) == pytest.approx(drifted)


def test_recompute_nav_rebalances_same_asset_when_target_vol_scale_changes():
    module = load_bot_module()
    date = pd.Timestamp("2026-01-02")
    curve = pd.DataFrame(
        {
            "position_before": ["159915.SZ"],
            "position": ["159915.SZ"],
            "fraction_before": [0.5],
            "holding_fraction": [0.5],
            "asset_return": [0.10],
            "gross_return": [0.05],
            "return": [0.05],
            "nav": [1.05],
            "turnover": [0.0],
            "cost": [0.0],
        },
        index=[date],
    )
    effective_scale = pd.Series(1.0, index=curve.index)
    next_scale = pd.Series(1.2, index=curve.index)
    ones = pd.Series(1.0, index=curve.index)

    out = module._recompute_final_exposure_nav(
        curve,
        effective_scale,
        next_scale,
        ones,
        ones,
        one_way_cost=0.001,
    )

    drifted = 0.5 * 1.10 / 1.05
    target = 0.5 * 1.2
    expected_turnover = target - drifted
    assert float(out.loc[date, "turnover"]) == pytest.approx(expected_turnover)
    assert float(out.loc[date, "rebalance_delta"]) == pytest.approx(expected_turnover)
    assert float(out.loc[date, "buy_delta"]) == pytest.approx(expected_turnover)
    assert float(out.loc[date, "sell_delta"]) == pytest.approx(0.0)
    assert float(out.loc[date, "final_exposure_after_overheat"]) == pytest.approx(target)


def test_live_signal_without_today_bar_is_not_tradable(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-08",))

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-08", "2026-06-09"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=True,
        now=datetime(2026, 6, 9, 10, 0),
    )

    assert status["latest_date"] == "2026-06-08"
    assert status["expected_latest_session"] == "2026-06-09"
    assert status["live_data_available"] is False
    assert status["tradable"] is False


def test_top_signal_action_uses_drifted_sell_delta():
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-01-02",))
    daily.loc[0, "position_before"] = "159915.SZ"
    daily.loc[0, "position"] = "159915.SZ"
    daily.loc[0, "actual_position_before"] = "159915.SZ"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "exposure_effective"] = 0.5
    daily.loc[0, "drifted_exposure_before_trade"] = 0.5238095238
    daily.loc[0, "final_exposure_after_overheat"] = 0.5
    daily.loc[0, "rebalance_delta"] = -0.0238095238
    daily.loc[0, "buy_delta"] = 0.0
    daily.loc[0, "sell_delta"] = 0.0238095238
    daily.loc[0, "turnover"] = 0.0238095238

    sig = module.latest_signal(daily)

    assert sig["drifted_exposure_before_trade"] == pytest.approx(0.5238095238)
    assert sig["sell_delta"] == pytest.approx(0.0238095238)
    assert "卖出" in module._signal_action_text(sig)
    assert "2.38%" in module._signal_action_text(sig)
    assert "卖出" in module._trade_action_label(sig)


def test_top_signal_action_for_switch_shows_sell_and_buy_delta():
    module = load_bot_module()
    sig = {
        "position_before": "159915.SZ",
        "position": "159941.SZ",
        "base_position_before": "159915.SZ",
        "base_position_next": "159941.SZ",
        "actual_position_before": "159915.SZ",
        "actual_position_next": "159941.SZ",
        "trade_target": "159941.SZ",
        "exposure_effective": 0.5,
        "drifted_exposure_before_trade": 0.55,
        "final_exposure": 0.50,
        "buy_delta": 0.50,
        "sell_delta": 0.55,
        "turnover": 1.05,
    }

    text = module._signal_action_text(sig)

    assert "卖出" in text and "55.00%" in text
    assert "买入" in text and "50.00%" in text
    assert "收盘后目标敞口" in text and "50.00%" in text


def test_empty_to_none_treats_pandas_na_as_missing():
    module = load_bot_module()

    assert module._empty_to_none(pd.NA) is None
    assert module._empty_to_none(pd.NaT) is None
    assert module._empty_to_none("<NA>") is None


def test_signal_report_uses_actual_entry_state_before_pending_target():
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-09",))
    daily.loc[0, "actual_entry_state"] = "FULL_POSITION"
    daily.loc[0, "actual_pending_target"] = pd.NA
    daily.loc[0, "actual_pending_days"] = 0

    report = module.format_signal_report(
        daily,
        "unit-test",
        live=False,
        now=datetime(2026, 6, 9, 16, 0),
    )

    assert "<NA>" not in report
    assert "等待补仓" not in report
    assert "当前无待补仓" in report


def test_non_trading_day_stale_data_is_not_tradable(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-09-29",))

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-09-29", "2026-09-30"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 10, 1, 10, 0),
    )

    assert status["expected_confirmed_session"] == "2026-09-30"
    assert status["actual_latest_session"] == "2026-09-29"
    assert status["tradable"] is False


def test_trading_morning_requires_previous_confirmed_session(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-09",))

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-09", "2026-06-10", "2026-06-11"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 6, 11, 10, 0),
    )

    assert status["expected_confirmed_session"] == "2026-06-10"
    assert status["tradable"] is False


def test_live_status_fails_closed_without_trading_calendar(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-09",))
    monkeypatch.setattr(module, "_expected_cn_trading_days", lambda start, end: None)

    with pytest.raises(RuntimeError, match="交易日历不可用"):
        module.signal_data_status(
            daily,
            live=True,
            now=datetime(2026, 6, 9, 10, 0),
        )


def test_trading_calendar_uses_local_cache_when_akshare_unavailable(monkeypatch, tmp_path):
    module = load_bot_module()
    cache_path = tmp_path / "cn_trading_days_cache.csv"
    pd.DataFrame(
        {
            "trade_date": ["2026-09-29", "2026-09-30"],
            "generated_at": ["2026-10-01T10:00:00+08:00", "2026-10-01T10:00:00+08:00"],
            "coverage_end": ["2026-09-30", "2026-09-30"],
            "source": ["unit", "unit"],
        }
    ).to_csv(cache_path, index=False)
    monkeypatch.setattr(module, "TRADING_CALENDAR_CACHE_PATH", cache_path, raising=False)
    monkeypatch.setattr(module, "_HAS_AKSHARE", False)
    monkeypatch.setattr(module, "_CN_TRADING_DAY_CACHE", None)

    sessions = module._expected_cn_trading_days(
        pd.Timestamp("2026-09-29"),
        pd.Timestamp("2026-09-30"),
    )

    assert sessions.tolist() == [pd.Timestamp("2026-09-29"), pd.Timestamp("2026-09-30")]


def test_trading_calendar_uses_cnfin_when_akshare_and_cache_unavailable(monkeypatch, tmp_path):
    module = load_bot_module()
    cache_path = tmp_path / "missing_cn_trading_days_cache.csv"
    monkeypatch.setattr(module, "TRADING_CALENDAR_CACHE_PATH", cache_path, raising=False)
    monkeypatch.setattr(module, "_HAS_AKSHARE", False)
    monkeypatch.setattr(module, "_CN_TRADING_DAY_CACHE", None)
    monkeypatch.setattr(module, "_CN_TRADING_DAY_CACHE_COVERAGE_END", None)
    calendar = pd.DatetimeIndex(pd.to_datetime(["2026-06-19", "2026-06-22"]))

    def cnfin_calendar(required_start, required_end):
        return calendar, pd.Timestamp("2026-06-22"), required_start, required_end

    monkeypatch.setattr(module, "_load_cnfin_trading_calendar", cnfin_calendar, raising=False)

    sessions = module._expected_cn_trading_days(
        pd.Timestamp("2026-06-19"),
        pd.Timestamp("2026-06-22"),
    )

    assert sessions.tolist() == [pd.Timestamp("2026-06-19"), pd.Timestamp("2026-06-22")]


def test_trading_calendar_uses_cnfin_when_required_start_is_workday_holiday(monkeypatch, tmp_path):
    module = load_bot_module()
    cache_path = tmp_path / "missing_cn_trading_days_cache.csv"
    calendar = pd.DatetimeIndex(pd.to_datetime(["2026-01-05", "2026-01-06"]))

    monkeypatch.setattr(module, "TRADING_CALENDAR_CACHE_PATH", cache_path, raising=False)
    monkeypatch.setattr(module, "_HAS_AKSHARE", False)
    monkeypatch.setattr(module, "_CN_TRADING_DAY_CACHE", None)
    monkeypatch.setattr(module, "_CN_TRADING_DAY_CACHE_COVERAGE_END", None)
    monkeypatch.setattr(
        module,
        "_load_cnfin_trading_calendar",
        lambda required_start, required_end: (
            calendar,
            pd.Timestamp("2026-01-06"),
            pd.Timestamp("2026-01-01"),
            pd.Timestamp("2026-01-06"),
        ),
        raising=False,
    )

    sessions = module._expected_cn_trading_days(
        pd.Timestamp("2026-01-01"),
        pd.Timestamp("2026-01-06"),
    )

    assert sessions.tolist() == [pd.Timestamp("2026-01-05"), pd.Timestamp("2026-01-06")]


def test_trading_calendar_uses_cnfin_when_required_end_is_non_session(monkeypatch, tmp_path):
    module = load_bot_module()
    cache_path = tmp_path / "missing_cn_trading_days_cache.csv"
    calendar = pd.DatetimeIndex(pd.to_datetime(["2026-01-02"]))

    monkeypatch.setattr(module, "TRADING_CALENDAR_CACHE_PATH", cache_path, raising=False)
    monkeypatch.setattr(module, "_HAS_AKSHARE", False)
    monkeypatch.setattr(module, "_CN_TRADING_DAY_CACHE", None)
    monkeypatch.setattr(module, "_CN_TRADING_DAY_CACHE_COVERAGE_END", None)
    monkeypatch.setattr(
        module,
        "_load_cnfin_trading_calendar",
        lambda required_start, required_end: (
            calendar,
            pd.Timestamp("2026-01-02"),
            pd.Timestamp("2026-01-02"),
            pd.Timestamp("2026-01-04"),
        ),
        raising=False,
    )

    sessions = module._expected_cn_trading_days(
        pd.Timestamp("2026-01-02"),
        pd.Timestamp("2026-01-04"),
    )

    assert sessions.tolist() == [pd.Timestamp("2026-01-02")]


def test_official_2026_calendar_covers_july_31_when_quote_calendar_lags(monkeypatch, tmp_path):
    module = load_bot_module()
    cache_path = tmp_path / "missing_cn_trading_days_cache.csv"
    lagged_calendar = pd.DatetimeIndex(pd.to_datetime(["2026-07-30"]))

    monkeypatch.setattr(module, "TRADING_CALENDAR_CACHE_PATH", cache_path, raising=False)
    monkeypatch.setattr(module, "_HAS_AKSHARE", False)
    monkeypatch.setattr(module, "_CN_TRADING_DAY_CACHE", None)
    monkeypatch.setattr(module, "_CN_TRADING_DAY_CACHE_COVERAGE_END", None)
    monkeypatch.setattr(module, "_CN_TRADING_DAY_CACHE_QUERIED_START", None)
    monkeypatch.setattr(module, "_CN_TRADING_DAY_CACHE_QUERIED_END", None)
    monkeypatch.setattr(
        module,
        "_load_cnfin_trading_calendar",
        lambda required_start, required_end: (
            lagged_calendar,
            pd.Timestamp("2026-07-30"),
            required_start,
            required_end,
        ),
        raising=False,
    )

    sessions = module._status_calendar_sessions(
        datetime(2026, 8, 1, 10, 0, tzinfo=module.CN_TZ),
        pd.Timestamp("2026-07-31"),
    )

    assert sessions["calendar_available"] is True
    assert sessions["expected_confirmed_session"] == pd.Timestamp("2026-07-31")


def test_cnfin_trading_calendar_loader_pages_until_required_start(monkeypatch):
    module = load_bot_module()
    calls = []

    class FakeResponse:
        def __init__(self, rows):
            self._rows = rows

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"candle": {"fields": ["min_time"], "000001.SS": self._rows}}}

    first_page = [["2024-01-02", "1", "1", "1", "1", "0"]] * 2001
    first_page[0] = ["2024-01-02", "1", "1", "1", "1", "0"]
    first_page[-1] = ["2026-01-02", "1", "1", "1", "1", "0"]
    second_page = [
        ["2023-12-29", "1", "1", "1", "1", "0"],
        ["2023-12-30", "1", "1", "1", "1", "0"],
    ]

    def fake_http_get(url, params=None, **kwargs):
        calls.append(params)
        return FakeResponse(first_page if len(calls) == 1 else second_page)

    monkeypatch.setattr(module, "_http_get", fake_http_get)

    calendar, coverage_end, queried_start, queried_end = module._load_cnfin_trading_calendar(
        pd.Timestamp("2023-12-29"),
        pd.Timestamp("2026-01-02"),
    )

    assert len(calls) == 2
    assert calls[0]["end_date"] == "20260102"
    assert calls[1]["end_date"] == "20240101"
    assert calendar.min() == pd.Timestamp("2023-12-29")
    assert calendar.max() == pd.Timestamp("2026-01-02")
    assert coverage_end == pd.Timestamp("2026-01-02")
    assert queried_start == pd.Timestamp("2023-12-29")
    assert queried_end == pd.Timestamp("2026-01-02")


def test_cnfin_trading_calendar_loader_rejects_partial_calendar_after_provider_failure(monkeypatch):
    module = load_bot_module()
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            rows = [["2024-01-02", "1", "1", "1", "1", "0"]] * 2001
            rows[-1] = ["2026-01-02", "1", "1", "1", "1", "0"]
            return {"data": {"candle": {"fields": ["min_time"], "000001.SS": rows}}}

    def fake_http_get(*args, **kwargs):
        calls.append(kwargs.get("params"))
        if len(calls) == 1:
            return FakeResponse()
        raise RuntimeError("unit provider failure")

    monkeypatch.setattr(module, "_http_get", fake_http_get)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="partial calendar|coverage|provider"):
        module._load_cnfin_trading_calendar(
            pd.Timestamp("2023-12-29"),
            pd.Timestamp("2026-01-02"),
        )

    assert len(calls) == 4


def test_cnfin_trading_calendar_loader_accepts_explicit_empty_followup_page(monkeypatch):
    module = load_bot_module()
    calls = []

    class FakeResponse:
        def __init__(self, rows):
            self._rows = rows

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"candle": {"fields": ["min_time"], "000001.SS": self._rows}}}

    first_page = [["2024-01-02", "1", "1", "1", "1", "0"]] * 2001
    first_page[-1] = ["2026-01-02", "1", "1", "1", "1", "0"]

    def fake_http_get(*args, **kwargs):
        calls.append(kwargs.get("params"))
        return FakeResponse(first_page if len(calls) == 1 else [])

    monkeypatch.setattr(module, "_http_get", fake_http_get)

    calendar, coverage_end, queried_start, queried_end = module._load_cnfin_trading_calendar(
        pd.Timestamp("2023-12-29"),
        pd.Timestamp("2026-01-02"),
    )

    assert len(calls) == 2
    assert calendar.min() == pd.Timestamp("2024-01-02")
    assert coverage_end == calendar.max() == pd.Timestamp("2026-01-02")
    assert queried_start == pd.Timestamp("2023-12-29")
    assert queried_end == pd.Timestamp("2026-01-02")


def test_cnfin_calendar_cache_preserves_queried_boundaries(monkeypatch, tmp_path):
    module = load_bot_module()
    cache_path = tmp_path / "cn_trading_days_cache.csv"
    calendar = pd.DatetimeIndex(pd.to_datetime(["2026-01-05", "2026-01-06"]))
    monkeypatch.setattr(module, "TRADING_CALENDAR_CACHE_PATH", cache_path, raising=False)

    module._write_cached_cn_trading_days(
        calendar,
        source="CNFin 000001.SS kline",
        queried_start=pd.Timestamp("2026-01-01"),
        queried_end=pd.Timestamp("2026-01-06"),
    )
    loaded_calendar, coverage_end, queried_start, queried_end = module._load_cached_cn_trading_days()

    assert loaded_calendar.equals(calendar)
    assert coverage_end == pd.Timestamp("2026-01-06")
    assert queried_start == pd.Timestamp("2026-01-01")
    assert queried_end == pd.Timestamp("2026-01-06")
    assert module._calendar_is_usable(
        loaded_calendar,
        pd.Timestamp("2026-01-01"),
        pd.Timestamp("2026-01-06"),
        coverage_end,
        queried_start,
        queried_end,
    )


@pytest.mark.parametrize("source", ["akshare.tool_trade_date_hist_sina", "CNFin forged", None])
def test_untrusted_calendar_cache_source_does_not_relax_session_boundaries(monkeypatch, tmp_path, source):
    module = load_bot_module()
    cache_path = tmp_path / "cn_trading_days_cache.csv"
    cache_data = {
        "trade_date": ["2026-01-05", "2026-01-06"],
        "coverage_end": ["2026-01-06", "2026-01-06"],
        "queried_start": ["2026-01-01", "2026-01-01"],
        "queried_end": ["2026-01-06", "2026-01-06"],
    }
    if source is not None:
        cache_data["source"] = [source] * 2
    pd.DataFrame(cache_data).to_csv(cache_path, index=False)
    monkeypatch.setattr(module, "TRADING_CALENDAR_CACHE_PATH", cache_path, raising=False)
    monkeypatch.setattr(module, "_HAS_AKSHARE", False)
    monkeypatch.setattr(module, "_CN_TRADING_DAY_CACHE", None)
    monkeypatch.setattr(module, "_CN_TRADING_DAY_CACHE_COVERAGE_END", None)
    monkeypatch.setattr(
        module,
        "_load_cnfin_trading_calendar",
        lambda required_start, required_end: (_ for _ in ()).throw(RuntimeError("cnfin unavailable")),
    )

    sessions = module._expected_cn_trading_days(
        pd.Timestamp("2026-01-01"),
        pd.Timestamp("2026-01-06"),
    )

    assert sessions is None


def test_stale_calendar_cache_is_rejected_when_market_data_is_newer(monkeypatch, tmp_path):
    module = load_bot_module()
    cache_path = tmp_path / "cn_trading_days_cache.csv"
    pd.DataFrame({"trade_date": ["2026-05-29", "2026-06-01"]}).to_csv(cache_path, index=False)
    monkeypatch.setattr(module, "TRADING_CALENDAR_CACHE_PATH", cache_path, raising=False)
    monkeypatch.setattr(module, "_HAS_AKSHARE", False)
    monkeypatch.setattr(module, "_CN_TRADING_DAY_CACHE", None)
    monkeypatch.setattr(
        module,
        "_load_cnfin_trading_calendar",
        lambda required_start, required_end: (_ for _ in ()).throw(RuntimeError("cnfin unavailable")),
        raising=False,
    )
    daily = minimal_daily(module, dates=("2026-06-17",))

    with pytest.raises(RuntimeError, match="交易日历落后于行情数据"):
        module.signal_data_status(
            daily,
            live=False,
            now=datetime(2026, 6, 18, 10, 0),
            purpose="execution",
        )


def test_generated_at_does_not_extend_calendar_cache_coverage():
    module = load_bot_module()
    raw = pd.DataFrame(
        {
            "trade_date": ["2026-06-01"],
            "coverage_end": ["2026-06-01"],
            "generated_at": ["2026-06-18T16:00:00+08:00"],
            "last_trade_date": ["2026-06-01"],
        }
    )
    calendar = module._normalize_trading_calendar(raw)

    coverage_end = module._calendar_cache_coverage_end(raw, calendar)

    assert coverage_end == pd.Timestamp("2026-06-01")


def test_coverage_end_must_equal_calendar_max():
    module = load_bot_module()
    raw = pd.DataFrame(
        {
            "trade_date": ["2026-06-01"],
            "coverage_end": ["2026-06-18"],
            "last_trade_date": ["2026-06-01"],
        }
    )
    calendar = module._normalize_trading_calendar(raw)

    with pytest.raises(RuntimeError, match="coverage_end=2026-06-18.*calendar.max=2026-06-01"):
        module._calendar_cache_coverage_end(raw, calendar)


def test_calendar_cache_rejects_inconsistent_coverage_metadata(monkeypatch, tmp_path):
    module = load_bot_module()
    cache_path = tmp_path / "cn_trading_days_cache.csv"
    pd.DataFrame(
        {
            "trade_date": ["2026-06-17", "2026-06-18"],
            "coverage_end": ["2026-06-18", "2099-01-01"],
            "source": ["unit", "unit"],
        }
    ).to_csv(cache_path, index=False)
    monkeypatch.setattr(module, "TRADING_CALENDAR_CACHE_PATH", cache_path, raising=False)
    monkeypatch.setattr(module, "_HAS_AKSHARE", False)
    monkeypatch.setattr(module, "_CN_TRADING_DAY_CACHE", None)
    monkeypatch.setattr(
        module,
        "_load_cnfin_trading_calendar",
        lambda required_start, required_end: (_ for _ in ()).throw(RuntimeError("cnfin unavailable")),
        raising=False,
    )

    assert module._expected_cn_trading_days(pd.Timestamp("2026-06-17"), pd.Timestamp("2026-06-18")) is None
    assert "元数据不一致" in module._calendar_failure_reason()


def test_latest_market_date_must_be_a_calendar_session(monkeypatch, tmp_path):
    module = load_bot_module()
    cache_path = tmp_path / "cn_trading_days_cache.csv"
    pd.DataFrame(
        {
            "trade_date": ["2026-05-19", "2026-06-01", "2026-06-18"],
            "coverage_end": ["2026-06-18", "2026-06-18", "2026-06-18"],
            "generated_at": [
                "2026-06-18T16:00:00+08:00",
                "2026-06-18T16:00:00+08:00",
                "2026-06-18T16:00:00+08:00",
            ],
        }
    ).to_csv(cache_path, index=False)
    monkeypatch.setattr(module, "TRADING_CALENDAR_CACHE_PATH", cache_path, raising=False)
    monkeypatch.setattr(module, "_HAS_AKSHARE", False)
    monkeypatch.setattr(module, "_CN_TRADING_DAY_CACHE", None)
    daily = minimal_daily(module, dates=("2026-06-17",))

    with pytest.raises(RuntimeError, match="行情最新日期不在交易日历"):
        module.signal_data_status(
            daily,
            live=False,
            now=datetime(2026, 6, 18, 10, 0),
            purpose="execution",
        )


def test_stale_akshare_calendar_does_not_override_better_local_cache(monkeypatch, tmp_path):
    module = load_bot_module()
    cache_path = tmp_path / "cn_trading_days_cache.csv"
    pd.DataFrame(
        {
            "trade_date": ["2026-06-15", "2026-06-16", "2026-06-17", "2026-06-18"],
            "coverage_end": ["2026-06-18"] * 4,
            "source": ["unit-cache"] * 4,
        }
    ).to_csv(cache_path, index=False)
    monkeypatch.setattr(module, "TRADING_CALENDAR_CACHE_PATH", cache_path, raising=False)
    monkeypatch.setattr(module, "_HAS_AKSHARE", True)
    monkeypatch.setattr(module, "_CN_TRADING_DAY_CACHE", None)
    monkeypatch.setattr(module, "_CN_TRADING_DAY_CACHE_COVERAGE_END", None)
    monkeypatch.setattr(
        module.ak,
        "tool_trade_date_hist_sina",
        lambda: pd.DataFrame({"trade_date": ["2026-05-29", "2026-06-01"]}),
    )

    sessions = module._expected_cn_trading_days(
        pd.Timestamp("2026-06-15"),
        pd.Timestamp("2026-06-18"),
    )

    assert sessions.tolist() == [
        pd.Timestamp("2026-06-15"),
        pd.Timestamp("2026-06-16"),
        pd.Timestamp("2026-06-17"),
        pd.Timestamp("2026-06-18"),
    ]


def test_align_prices_rejects_stale_calendar_cache_instead_of_skipping_common_gap_check(monkeypatch, tmp_path):
    module = load_bot_module()
    cache_path = tmp_path / "cn_trading_days_cache.csv"
    pd.DataFrame({"trade_date": ["2026-05-29", "2026-06-01"]}).to_csv(cache_path, index=False)
    monkeypatch.setattr(module, "TRADING_CALENDAR_CACHE_PATH", cache_path, raising=False)
    monkeypatch.setattr(module, "_HAS_AKSHARE", False)
    monkeypatch.setattr(module, "_CN_TRADING_DAY_CACHE", None)
    monkeypatch.setattr(
        module,
        "_load_cnfin_trading_calendar",
        lambda required_start, required_end: (_ for _ in ()).throw(RuntimeError("cnfin unavailable")),
        raising=False,
    )
    dates = pd.to_datetime(["2026-06-15", "2026-06-17"])
    prices = pd.DataFrame(1.0, index=dates, columns=list(module.ASSETS))

    with pytest.raises(RuntimeError, match="交易日历落后于行情数据"):
        module.align_prices_to_common_valid_date(prices, list(module.ASSETS))


def test_align_prices_rejects_unexpected_non_trading_day(monkeypatch):
    module = load_bot_module()
    dates = pd.to_datetime(["2026-06-19", "2026-06-21"])
    prices = pd.DataFrame(1.0, index=dates, columns=list(module.ASSETS))

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-19"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    with pytest.raises(ValueError, match="unexpected non-trading dates.*2026-06-21"):
        module.align_prices_to_common_valid_date(prices, list(module.ASSETS))


def test_align_prices_requires_calendar_when_validation_is_required(monkeypatch):
    module = load_bot_module()
    dates = pd.to_datetime(["2026-06-15", "2026-06-17"])
    prices = pd.DataFrame(1.0, index=dates, columns=list(module.ASSETS))
    monkeypatch.setattr(module, "_expected_cn_trading_days", lambda start, end: None)

    with pytest.raises(RuntimeError, match="交易日历不可用"):
        module.align_prices_to_common_valid_date(
            prices,
            list(module.ASSETS),
            calendar_validation_mode="required",
        )


def test_empty_akshare_calendar_does_not_overwrite_valid_local_cache(monkeypatch, tmp_path):
    module = load_bot_module()
    cache_path = tmp_path / "cn_trading_days_cache.csv"
    original = pd.DataFrame({"trade_date": ["2026-06-17", "2026-06-18"]})
    original.to_csv(cache_path, index=False)
    monkeypatch.setattr(module, "TRADING_CALENDAR_CACHE_PATH", cache_path, raising=False)
    monkeypatch.setattr(module, "_HAS_AKSHARE", True)
    monkeypatch.setattr(module, "_CN_TRADING_DAY_CACHE", None)
    monkeypatch.setattr(module.ak, "tool_trade_date_hist_sina", lambda: pd.DataFrame({"trade_date": []}))

    sessions = module._expected_cn_trading_days(
        pd.Timestamp("2026-06-17"),
        pd.Timestamp("2026-06-18"),
    )

    assert sessions.tolist() == [pd.Timestamp("2026-06-17"), pd.Timestamp("2026-06-18")]
    cached = pd.read_csv(cache_path)
    assert cached["trade_date"].tolist() == original["trade_date"].tolist()


def test_execution_signal_fails_closed_without_calendar_even_when_not_live(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-09",))
    monkeypatch.setattr(module, "_expected_cn_trading_days", lambda start, end: None)

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 6, 9, 16, 0),
        purpose="execution",
    )

    assert status["calendar_available"] is False
    assert status["data_usable"] is False
    assert status["signal_valid"] is False
    assert status["actionable_now"] is False
    assert status["tradable"] is False
    assert "交易日历不可用" in status["label"]


def test_weekend_signal_is_valid_but_not_actionable_now(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-19",))

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-19"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 6, 20, 10, 0),
        purpose="execution",
    )

    assert status["data_usable"] is True
    assert status["signal_valid"] is True
    assert status["actionable_now"] is False
    assert status["tradable"] is False
    assert status["expected_confirmed_session"] == "2026-06-19"
    assert "休市" in status["execution_note"]


def test_weekend_live_signal_accepts_calendar_covered_to_previous_session(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-26",))
    latest_session = pd.Timestamp("2026-06-26")
    calls = []

    def expected_sessions(start, end):
        calls.append((pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()))
        if pd.Timestamp(end).normalize() > latest_session:
            return None
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-25", "2026-06-26"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)
    module._set_calendar_failure(
        "交易日历落后于行情数据或当前日期，禁止生成可执行信号；"
        "本地缓存交易日历覆盖不足：需要 2026-05-29 至 2026-06-28，实际 2019-12-05 至 2026-06-26"
    )

    status = module.signal_data_status(
        daily,
        live=True,
        now=datetime(2026, 6, 28, 10, 0),
        purpose="execution",
    )

    assert calls[-1][1] == latest_session
    assert status["data_usable"] is True
    assert status["signal_valid"] is True
    assert status["tradable"] is False
    assert status["expected_confirmed_session"] == "2026-06-26"
    assert "休市" in status["execution_note"]


def test_after_close_signal_is_valid_but_not_actionable_at_close_price(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "518880.SH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "sell_delta"] = 0.2
    daily.loc[0, "buy_delta"] = 0.2
    fill_final_quote_pairs(module, daily, row_idx=0, quote_time="2026-06-18 15:01:00")

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 6, 18, 16, 0),
        purpose="execution",
    )

    assert status["data_usable"] is True
    assert status["signal_valid"] is True
    assert status["actionable_now"] is False
    assert status["tradable"] is False
    assert "收盘价成交" in status["execution_note"]


@pytest.mark.parametrize(
    "clock_text",
    ["00:00", "08:00", "12:00", "15:10"],
)
def test_non_continuous_auction_times_are_not_market_open(monkeypatch, clock_text):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)
    hour, minute = map(int, clock_text.split(":"))

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 6, 18, hour, minute),
        purpose="execution",
    )

    assert status["signal_valid"] is True
    assert status["continuous_actionable_now"] is False
    assert status["post_close_actionable_now"] is False
    assert status["market_session_open"] is False
    assert status["actionable_now"] is False
    assert status["tradable"] is False


@pytest.mark.parametrize("clock_text", ["09:30", "10:15", "13:00", "14:56"])
def test_continuous_auction_times_with_trade_legs_are_fully_matchable(monkeypatch, clock_text):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "518880.SH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "sell_delta"] = 0.2
    daily.loc[0, "buy_delta"] = 0.2

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)
    hour, minute = map(int, clock_text.split(":"))

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 6, 18, hour, minute),
        purpose="execution",
    )

    assert status["action_required"] is True
    assert status["exchange_all_legs_can_submit"] is True
    assert status["exchange_all_legs_can_match_immediately"] is True
    assert status["all_legs_can_submit"] is False
    assert status["all_legs_can_match_immediately"] is False
    assert status["partially_executable"] is False
    assert status["continuous_actionable_now"] is False
    assert status["post_close_actionable_now"] is False
    assert status["market_session_open"] is True
    assert status["actionable_now"] is False


def test_no_trade_signal_is_valid_but_not_actionable(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 6, 18, 10, 0),
        purpose="execution",
    )

    assert status["signal_valid"] is True
    assert status["action_required"] is False
    assert status["execution_session"] == "NO_TRADE"
    assert status["all_legs_can_submit"] is False
    assert status["all_legs_can_match_immediately"] is False
    assert status["actionable_now"] is False
    assert status["tradable"] is False


def test_previous_no_trade_signal_is_not_delayed_execution(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-17",))

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-17", "2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 6, 18, 10, 0),
        purpose="execution",
    )

    assert status["signal_valid"] is True
    assert status["action_required"] is False
    assert status["delayed_execution"] is False
    assert status["execution_session"] == "NO_TRADE"
    assert status["actionable_now"] is False
    assert "无需下单" in status["execution_note"]


def test_signal_report_concludes_no_trade_without_protection_warning(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    report = module.format_signal_report(
        daily,
        "unit-test",
        live=False,
        now=datetime(2026, 6, 18, 10, 0),
    )

    assert "原始信号是否包含调仓" not in report
    assert "当前是否需要执行" not in report
    assert "逐ETF报价时间范围" not in report
    assert "【异常提示】" not in report
    assert "信号有效，无需下单" in report
    assert "信号有效但当前不可成交" not in report
    assert "实盘保护: 信号有效" not in report


def test_signal_report_keeps_complete_signal_body_with_compact_status(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    report = module.format_signal_report(
        daily,
        "unit-test",
        live=False,
        now=datetime(2026, 6, 18, 10, 0),
    )

    assert "### 仓位拆解" in report
    assert "### 动量排名" in report
    assert "### 规则状态" in report
    assert "### 净值快照" in report
    assert "### 调仓记录" in report
    assert "数据是否完整" not in report
    assert "交易所是否可以提交全部委托" not in report


def test_signal_report_expands_only_on_abnormal_status(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-17",))

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-17", "2026-06-18", "2026-06-19"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    report = module.format_signal_report(
        daily,
        "unit-test",
        live=False,
        now=datetime(2026, 6, 19, 10, 0),
    )

    assert "### 【异常提示】" in report
    assert "数据不可交易" in report
    assert "预期最新交易日" in report
    assert "实际最新交易日" in report


def test_signal_report_keeps_score_red_lights_out_of_abnormal_section(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "raw_score_513520.SH"] = 6.3242
    daily.loc[0, "score_513520.SH"] = math.nan

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    report = module.format_signal_report(
        daily,
        "unit-test",
        live=False,
        now=datetime(2026, 6, 18, 10, 0),
    )

    assert "### 【异常提示】" not in report
    assert "### 【风控提示】" in report
    assert "红灯" in report


def test_signal_report_uses_post_close_unconfirmed_bar_wording(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    report = module.format_signal_report(
        daily,
        "unit-test",
        live=True,
        now=datetime(2026, 6, 18, 21, 46),
    )

    assert "当前日线bar尚未最终确认" in report
    assert "收盘前仍可能变化" not in report


def test_post_close_fixed_price_is_disabled_before_2026_rule_effective_date(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "518880.SH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "sell_delta"] = 0.2
    daily.loc[0, "buy_delta"] = 0.2

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 6, 18, 15, 6),
        purpose="execution",
    )

    assert status["execution_session"] == "CLOSED"
    assert status["continuous_actionable_now"] is False
    assert status["post_close_actionable_now"] is False
    assert status["actionable_now"] is False


def test_post_close_fixed_price_session_is_not_actionable_without_final_close_timestamp(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-07-06",))
    daily.loc[0, "actual_position_before"] = "518880.SH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "sell_delta"] = 0.2
    daily.loc[0, "buy_delta"] = 0.2

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-07-06"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 7, 6, 15, 6),
        purpose="execution",
    )

    assert status["execution_session"] == "POST_CLOSE"
    assert status["continuous_actionable_now"] is False
    assert status["post_close_actionable_now"] is False
    assert status["actionable_now"] is False
    assert status["official_close_ready"] is False
    assert status["source_quote_time"] is None
    assert status["signal_date"] == "2026-07-06"
    assert status["signal_uses_today_close"] is False


def test_post_close_confirmed_signal_does_not_execute_previous_session_signal(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-07-03",))
    daily.loc[0, "actual_position_before"] = "518880.SH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "sell_delta"] = 0.2
    daily.loc[0, "buy_delta"] = 0.2

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-07-03", "2026-07-06"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 7, 6, 15, 10),
        purpose="execution",
    )

    assert status["execution_session"] == "POST_CLOSE"
    assert status["signal_date"] == "2026-07-03"
    assert status["signal_uses_today_close"] is False
    assert status["official_close_ready"] is False
    assert status["post_close_actionable_now"] is False
    assert status["actionable_now"] is False


def test_post_close_live_signal_does_not_execute_unconfirmed_today_bar(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-07-06",))
    daily.loc[0, "actual_position_before"] = "518880.SH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "sell_delta"] = 0.2
    daily.loc[0, "buy_delta"] = 0.2

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-07-06"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=True,
        now=datetime(2026, 7, 6, 15, 10),
        purpose="execution",
    )

    assert status["execution_session"] == "POST_CLOSE"
    assert status["signal_date"] == "2026-07-06"
    assert status["uses_unconfirmed_bar"] is True
    assert status["signal_uses_today_close"] is False
    assert status["official_close_ready"] is False
    assert status["post_close_actionable_now"] is False
    assert status["actionable_now"] is False


@pytest.mark.parametrize(
    "quote_time",
    ["foo", "2020-01-01 10:00:00", "2026-07-06 08:00:00"],
)
def test_invalid_quote_time_does_not_make_official_close_ready(monkeypatch, quote_time):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-07-06",))
    daily.loc[0, "source_quote_time"] = quote_time
    daily.loc[0, "source_bar_is_final"] = True

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-07-06"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 7, 6, 15, 10),
        purpose="execution",
    )

    assert status["official_close_ready"] is False
    assert status["signal_uses_today_close"] is False
    assert status["post_close_actionable_now"] is False
    assert status["actionable_now"] is False


def test_verified_close_price_still_does_not_enable_post_close_without_feature_flag(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-07-06",))
    daily.loc[0, "actual_position_before"] = "518880.SH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "sell_delta"] = 0.2
    daily.loc[0, "buy_delta"] = 0.2
    fill_final_quote_pairs(module, daily, row_idx=0, quote_time="2026-07-06 15:05:00")

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-07-06"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 7, 6, 15, 10),
        purpose="execution",
    )

    assert status["official_close_ready"] is True
    assert status["signal_uses_today_close"] is True
    assert status["post_close_actionable_now"] is False
    assert status["actionable_now"] is False
    assert "鍏抽棴" in status["execution_note"] or "关闭" in status["execution_note"]


def test_synthesized_confirmed_daily_close_cannot_enable_post_close_fixed_price(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-07-06",))
    daily.loc[0, "actual_position_before"] = "518880.SH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "sell_delta"] = 0.2
    daily.loc[0, "buy_delta"] = 0.2
    for offset, code in enumerate(module.ASSETS):
        daily.loc[0, f"signal_price_{code}"] = 1.0 + offset / 100.0

    last_by_asset = {code: pd.Timestamp("2026-07-06") for code in module.ASSETS}
    daily = module._attach_confirmed_final_close_metadata(
        daily,
        last_by_asset=last_by_asset,
        now=datetime(2026, 7, 6, 15, 31),
    )

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-07-06"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)
    monkeypatch.setattr(module, "POST_CLOSE_FIXED_PRICE_EXECUTION_ENABLED", True)

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 7, 6, 15, 10),
        purpose="execution",
    )

    assert status["official_close_ready"] is True
    assert status["final_close_execution_verified"] is False
    assert status["model_execution_price_available"] is False
    assert status["post_close_actionable_now"] is False
    assert status["action_required_now"] is False
    assert status["actionable_now"] is False
    assert all(not leg["can_use_post_close_fixed_price"] for leg in status["execution_legs"])


def test_explicitly_execution_verified_final_close_can_enable_post_close_fixed_price(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-07-06",))
    daily.loc[0, "actual_position_before"] = "CASH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "sell_delta"] = 0.0
    daily.loc[0, "buy_delta"] = 0.2
    fill_final_quote_pairs(module, daily, row_idx=0, quote_time="2026-07-06 15:05:00")
    daily.loc[0, "source_final_close_execution_verified"] = True
    for code in module.ASSETS:
        daily.loc[0, f"final_close_execution_verified_{code}"] = True

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-07-06"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)
    monkeypatch.setattr(module, "POST_CLOSE_FIXED_PRICE_EXECUTION_ENABLED", True)

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 7, 6, 15, 10),
        purpose="execution",
    )

    assert status["official_close_ready"] is True
    assert status["final_close_execution_verified"] is True
    assert status["model_execution_price_available"] is True
    assert status["post_close_actionable_now"] is True
    assert status["action_required_now"] is True
    assert status["actionable_now"] is True
    assert all(leg["can_use_post_close_fixed_price"] for leg in status["execution_legs"])


def test_execution_session_status_requires_exchange_and_security_type():
    module = load_bot_module()

    assert (
        module._execution_session_status(
            datetime(2026, 7, 6, 15, 10),
            is_trading_day=True,
            exchange="SSE",
            security_type="ETF",
        )
        == "POST_CLOSE"
    )
    assert (
        module._execution_session_status(
            datetime(2026, 7, 6, 15, 10),
            is_trading_day=True,
            exchange="SZSE",
            security_type="ETF",
        )
        == "POST_CLOSE"
    )
    assert (
        module._execution_session_status(
            datetime(2026, 7, 6, 15, 10),
            is_trading_day=True,
            exchange="SSE",
            security_type="BOND",
        )
        == "CLOSED"
    )


def test_execution_session_status_uses_exchange_and_rule_effective_date():
    module = load_bot_module()

    assert (
        module._execution_session_status(
            datetime(2026, 6, 18, 14, 58),
            is_trading_day=True,
            exchange="SSE",
            security_type="ETF",
        )
        == "OPEN_PM"
    )
    assert (
        module._execution_session_status(
            datetime(2026, 6, 18, 14, 58),
            is_trading_day=True,
            exchange="SZSE",
            security_type="ETF",
        )
        == "CLOSE_CALL_ACCEPT"
    )
    assert (
        module._execution_session_status(
            datetime(2026, 7, 6, 14, 58),
            is_trading_day=True,
            exchange="SSE",
            security_type="ETF",
        )
        == "CLOSE_CALL_ACCEPT"
    )


def test_open_call_accept_allows_submit_but_not_immediate_match(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "518880.SH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "sell_delta"] = 0.2
    daily.loc[0, "buy_delta"] = 0.2

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 6, 18, 9, 20),
        purpose="execution",
    )

    assert {leg["execution_session"] for leg in status["execution_legs"]} == {"OPEN_CALL_ACCEPT"}
    assert [leg["exchange_can_submit_order_now"] for leg in status["execution_legs"]] == [True, True]
    assert [leg["can_submit_order_now"] for leg in status["execution_legs"]] == [False, False]
    assert [leg["can_match_immediately"] for leg in status["execution_legs"]] == [False, False]
    assert status["exchange_all_legs_can_submit"] is True
    assert status["all_legs_can_submit"] is False
    assert status["all_legs_can_match_immediately"] is False
    assert status["some_legs_can_match_immediately"] is False
    assert status["partially_executable"] is False
    assert status["actionable_now"] is False


def test_signal_report_keeps_trade_action_when_all_legs_can_submit_in_call_auction(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "518880.SH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "sell_delta"] = 0.2
    daily.loc[0, "buy_delta"] = 0.2
    daily.loc[0, "sell_available_518880.SH"] = True
    fill_live_quote_pairs(module, daily, quote_time="2026-06-18 14:57:30")

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    report = module.format_signal_report(
        daily,
        "unit-test",
        live=True,
        now=datetime(2026, 6, 18, 14, 58),
    )

    assert "交易所是否可以提交全部委托" not in report
    assert "交易所是否可以立即完成全部换仓" not in report
    assert "### 【异常提示】" in report
    assert "等待集合竞价统一撮合" in report
    assert "信号有效但当前不可成交" not in report
    assert "实盘保护: 信号有效" not in report


def test_open_gap_does_not_allow_leg_submission(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "518880.SH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "sell_delta"] = 0.2
    daily.loc[0, "buy_delta"] = 0.2

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 6, 18, 9, 27),
        purpose="execution",
    )

    assert {leg["execution_session"] for leg in status["execution_legs"]} == {"OPEN_GAP"}
    assert [leg["can_submit_order_now"] for leg in status["execution_legs"]] == [False, False]
    assert [leg["can_match_immediately"] for leg in status["execution_legs"]] == [False, False]


def test_signal_status_exposes_sell_and_buy_leg_execution_status(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-07-06",))
    daily.loc[0, "actual_position_before"] = "513520.SH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "sell_delta"] = 0.5
    daily.loc[0, "buy_delta"] = 0.5

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-07-06"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 7, 6, 10, 0),
        purpose="execution",
    )

    assert status["execution_legs"] == [
        {
            "side": "SELL",
            "asset": "513520.SH",
            "exchange": "SSE",
            "security_type": "ETF",
            "exchange_can_submit_order_now": True,
            "exchange_can_match_immediately": True,
            "can_submit_order_now": False,
            "can_match_immediately": False,
            "can_use_post_close_fixed_price": False,
            "signal_price_is_available": False,
            "execution_session": "OPEN_AM",
        },
        {
            "side": "BUY",
            "asset": "159915.SZ",
            "exchange": "SZSE",
            "security_type": "ETF",
            "exchange_can_submit_order_now": True,
            "exchange_can_match_immediately": True,
            "can_submit_order_now": False,
            "can_match_immediately": False,
            "can_use_post_close_fixed_price": False,
            "signal_price_is_available": False,
            "execution_session": "OPEN_AM",
        },
    ]


def test_previous_confirmed_signal_is_valid_but_delayed_not_actionable(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-17",))
    daily.loc[0, "actual_position_before"] = "518880.SH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "sell_delta"] = 0.2
    daily.loc[0, "buy_delta"] = 0.2

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-17", "2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 6, 18, 10, 0),
        purpose="execution",
    )

    assert status["signal_date"] == "2026-06-17"
    assert status["signal_valid"] is True
    assert status["signal_is_current_session"] is False
    assert status["model_execution_price_available"] is False
    assert status["delayed_execution"] is True
    assert status["action_required"] is True
    assert status["all_legs_can_submit"] is False
    assert status["all_legs_can_match_immediately"] is False
    assert status["actionable_now"] is False
    assert status["tradable"] is False


def test_live_intraday_estimate_before_execution_window_is_not_tradable(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "518880.SH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "sell_delta"] = 0.2
    daily.loc[0, "buy_delta"] = 0.2

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=True,
        now=datetime(2026, 6, 18, 10, 0),
        purpose="execution",
    )

    assert status["uses_unconfirmed_bar"] is True
    assert status["exchange_can_execute_now"] is True
    assert status["strategy_execution_window_open"] is False
    assert status["strategy_actionable_now"] is False
    assert status["actionable_now"] is False
    assert status["tradable"] is False


def test_live_execution_window_status_distinguishes_before_open_after(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "518880.SH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "sell_delta"] = 0.2
    daily.loc[0, "buy_delta"] = 0.2

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    before = module.signal_data_status(daily, live=True, now=datetime(2026, 6, 18, 14, 49))
    open_status = module.signal_data_status(daily, live=True, now=datetime(2026, 6, 18, 14, 50))
    after = module.signal_data_status(daily, live=True, now=datetime(2026, 6, 18, 15, 1))

    assert before["strategy_execution_window_status"] == "BEFORE"
    assert "尚未进入策略执行窗口" in before["execution_note"]
    assert open_status["strategy_execution_window_status"] == "OPEN"
    assert open_status["strategy_execution_window_open"] is True
    assert after["strategy_execution_window_status"] == "AFTER"
    assert "策略执行窗口已经结束" in after["execution_note"]
    assert after["strategy_actionable_now"] is False


def test_live_signal_report_uses_live_target_exposure_wording(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "518880.SH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "sell_delta"] = 0.2
    daily.loc[0, "buy_delta"] = 0.2

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    report = module.format_signal_report(
        daily,
        "unit-test",
        live=True,
        now=datetime(2026, 6, 18, 14, 50),
    )

    assert "若现在收盘目标敞口" in report
    assert "收盘后目标敞口" not in report.split("### 结论", 1)[1].split("### 信号摘要", 1)[0]


def test_live_params_snapshot_shows_strategy_execution_window(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    text = module.format_live_params_snapshot(
        daily,
        "unit-test",
        live=True,
        now=datetime(2026, 6, 18, 10, 0),
    )

    assert "策略实时执行窗口: **14:50—15:00**" in text
    assert "窗口外实时信号: **仅供监控，不执行**" in text


def test_exchange_mechanical_status_fields_are_named_explicitly(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "518880.SH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "sell_delta"] = 0.2
    daily.loc[0, "buy_delta"] = 0.2

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 6, 18, 9, 20),
        purpose="execution",
    )

    assert status["exchange_all_legs_can_submit"] is True
    assert status["exchange_can_complete_full_rebalance_now"] is False
    assert status["can_submit_full_order_now"] is False
    assert status["can_complete_full_rebalance_now"] is False

    report = module.format_signal_report(
        daily,
        "unit-test",
        live=False,
        now=datetime(2026, 6, 18, 9, 20),
    )

    assert "是否仅部分交易腿可即时撮合" not in report
    assert "是否存在部分交易腿只能即时撮合" not in report


@pytest.mark.parametrize(
    "now",
    [
        datetime(2026, 6, 18, 9, 20),
        datetime(2026, 6, 18, 10, 0),
        datetime(2026, 6, 18, 14, 49),
    ],
)
def test_live_report_conclusion_does_not_bypass_strategy_permission(monkeypatch, now):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "CASH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "sell_delta"] = 0.0
    daily.loc[0, "buy_delta"] = 0.2

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    report = module.format_signal_report(
        daily,
        "unit-test",
        live=True,
        now=now,
    )

    conclusion = report.split("### 结论", 1)[1].split("### 【异常提示】", 1)[0]
    assert "是否可作为实盘动作" not in report
    assert "### 【异常提示】" in report
    assert "实时估算" in conclusion
    assert "不应下单" in conclusion
    assert "**买入" not in conclusion


@pytest.mark.parametrize(
    ("quote_time", "source_bar_is_final"),
    [
        (None, False),
        ("2026-06-18 10:00:00", False),
        ("2026-06-18 14:54:30", False),
        ("2026-06-18 14:54:30", True),
    ],
)
def test_live_execution_window_requires_all_asset_quote_freshness(
    monkeypatch,
    quote_time,
    source_bar_is_final,
):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "CASH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "buy_delta"] = 0.2
    if quote_time is not None:
        daily.loc[0, "source_quote_time"] = quote_time
    daily.loc[0, "source_bar_is_final"] = source_bar_is_final

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=True,
        now=datetime(2026, 6, 18, 14, 55),
        purpose="execution",
    )

    assert status["strategy_execution_window_open"] is True
    assert status["live_snapshot_fresh"] is False
    assert status["strategy_actionable_now"] is False
    assert status["tradable"] is False


def test_live_fresh_timestamps_without_quote_prices_are_not_actionable(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "CASH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "buy_delta"] = 0.2
    for code in module.ASSETS:
        daily.loc[0, f"quote_time_{code}"] = "2026-06-18 14:54:30"

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=True,
        now=datetime(2026, 6, 18, 14, 55),
        purpose="execution",
    )

    assert status["all_quote_price_time_pairs_valid"] is False
    assert status["price_matrix_uses_live_quotes"] is False
    assert status["live_snapshot_fresh"] is False
    assert status["tradable"] is False


def test_live_fresh_quote_price_must_match_signal_price(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "CASH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "buy_delta"] = 0.2
    fill_live_quote_pairs(module, daily, quote_time="2026-06-18 14:54:30")
    daily.loc[0, f"signal_price_{next(iter(module.ASSETS))}"] += 0.1

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=True,
        now=datetime(2026, 6, 18, 14, 55),
        purpose="execution",
    )

    assert status["all_quote_price_time_pairs_valid"] is True
    assert status["price_matrix_uses_live_quotes"] is False
    assert status["live_snapshot_fresh"] is False
    assert status["tradable"] is False


def test_live_fresh_quote_pairs_can_pass_snapshot_validation(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "CASH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "buy_delta"] = 0.2
    fill_live_quote_pairs(module, daily, quote_time="2026-06-18 14:54:30")

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=True,
        now=datetime(2026, 6, 18, 14, 55),
        purpose="execution",
    )

    assert status["all_quote_price_time_pairs_valid"] is True
    assert status["price_matrix_uses_live_quotes"] is True
    assert status["live_snapshot_fresh"] is True
    assert status["tradable"] is True


def test_live_snapshot_zero_volume_is_monitor_only(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "CASH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "buy_delta"] = 0.2
    fill_live_quote_pairs(module, daily, quote_time="2026-06-18 14:54:30")
    daily.loc[0, "quote_volume_159915.SZ"] = 0

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=True,
        now=datetime(2026, 6, 18, 14, 55),
        purpose="execution",
    )

    assert "159915.SZ" in status["non_executable_quote_assets"]
    assert status["live_snapshot_fresh"] is False
    assert status["tradable"] is False


def test_live_buy_leg_at_limit_up_is_not_tradable(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "CASH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "buy_delta"] = 0.2
    fill_live_quote_pairs(module, daily, quote_time="2026-06-18 14:54:30")
    daily.loc[0, "quote_price_159915.SZ"] = 1.2
    daily.loc[0, "signal_price_159915.SZ"] = 1.2
    daily.loc[0, "quote_limit_up_159915.SZ"] = 1.2

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=True,
        now=datetime(2026, 6, 18, 14, 55),
        purpose="execution",
    )

    leg = status["execution_legs"][0]
    assert leg["side"] == "BUY"
    assert leg["can_submit_order_now"] is False
    assert leg["can_match_immediately"] is False
    assert "buy_at_limit_up" in leg["execution_block_reasons"]
    assert "159915.SZ" in status["limit_blocked_trade_assets"]
    assert status["tradable"] is False


def test_live_sell_leg_at_limit_down_is_not_tradable_even_when_sell_available(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "159941.SZ"
    daily.loc[0, "actual_position_next"] = "CASH"
    daily.loc[0, "sell_delta"] = 0.2
    daily.loc[0, "buy_delta"] = 0.0
    daily.loc[0, "sell_available_159941.SZ"] = True
    fill_live_quote_pairs(module, daily, quote_time="2026-06-18 14:54:30")
    daily.loc[0, "quote_price_159941.SZ"] = 0.9
    daily.loc[0, "signal_price_159941.SZ"] = 0.9
    daily.loc[0, "quote_limit_down_159941.SZ"] = 0.9

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=True,
        now=datetime(2026, 6, 18, 14, 55),
        purpose="execution",
    )

    leg = status["execution_legs"][0]
    assert leg["side"] == "SELL"
    assert leg["can_submit_order_now"] is False
    assert leg["can_match_immediately"] is False
    assert "sell_at_limit_down" in leg["execution_block_reasons"]
    assert "159941.SZ" in status["limit_blocked_trade_assets"]
    assert status["tradable"] is False


def test_live_sell_leg_requires_verified_sell_available_quantity(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "159941.SZ"
    daily.loc[0, "actual_position_next"] = "CASH"
    daily.loc[0, "sell_delta"] = 0.2
    daily.loc[0, "buy_delta"] = 0.0
    fill_live_quote_pairs(module, daily, quote_time="2026-06-18 14:54:30")

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=True,
        now=datetime(2026, 6, 18, 14, 55),
        purpose="execution",
    )

    leg = status["execution_legs"][0]
    assert leg["side"] == "SELL"
    assert leg["can_submit_order_now"] is False
    assert leg["can_match_immediately"] is False
    assert "sell_available_not_verified" in leg["execution_block_reasons"]
    assert "159941.SZ" in status["sell_unavailable_trade_assets"]
    assert status["tradable"] is False


def test_stale_same_day_quote_times_are_listed_as_stale_assets(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    fill_live_quote_pairs(module, daily, quote_time="2026-06-18 10:00:00")

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=True,
        now=datetime(2026, 6, 18, 14, 55),
        purpose="execution",
    )

    assert status["live_snapshot_fresh"] is False
    assert set(status["stale_quote_assets"]) == set(module.ASSETS)


def test_after_close_unverified_today_bar_is_not_confirmed(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 6, 18, 15, 31),
        purpose="execution",
    )

    assert status["official_close_ready"] is False
    assert status["uses_unconfirmed_bar"] is True
    assert status["bar_is_confirmed"] is False
    assert "尚未验证" in status["label"]


def test_confirmed_signal_drops_unverified_today_bar_after_close():
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-17", "2026-06-18"))

    confirmed = module.prepare_daily_for_signal(
        daily,
        live=False,
        now=datetime(2026, 6, 18, 15, 31),
    )

    assert confirmed["date"].max().date().isoformat() == "2026-06-17"


def test_confirmed_signal_keeps_verified_today_bar_after_close():
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-17", "2026-06-18"))
    fill_final_quote_pairs(module, daily, row_idx=1, quote_time="2026-06-18 15:01:00")

    confirmed = module.prepare_daily_for_signal(
        daily,
        live=False,
        now=datetime(2026, 6, 18, 15, 31),
    )

    assert confirmed["date"].max().date().isoformat() == "2026-06-18"


def test_build_confirmed_daily_writes_final_close_fields_after_cutoff(monkeypatch):
    module = load_bot_module()
    dates = pd.to_datetime(["2026-06-17", "2026-06-18"])
    prices = pd.DataFrame(
        {
            code: [1.0 + offset / 10.0, 1.1 + offset / 10.0]
            for offset, code in enumerate(module.ASSETS)
        },
        index=dates,
    )
    sources = pd.DataFrame(
        {
            "code": list(module.ASSETS),
            "name": [module.ASSETS[code] for code in module.ASSETS],
            "source": ["unit qfq"] * len(module.ASSETS),
            "adjustment": [module.ADJUSTMENT_QFQ] * len(module.ASSETS),
            "source_detail": ["unit"] * len(module.ASSETS),
            "first": ["2026-06-17"] * len(module.ASSETS),
            "last": ["2026-06-18"] * len(module.ASSETS),
            "rows": [2] * len(module.ASSETS),
        }
    )

    def fake_build_curves(input_prices, config, price_ffill_flags=None):
        daily = minimal_daily(module, dates=("2026-06-17", "2026-06-18"))
        daily.index = dates
        return [daily.drop(columns=["date"])]

    monkeypatch.setattr(module, "load_close", lambda config: (prices.copy(), sources.copy()))
    monkeypatch.setattr(module, "build_curves", fake_build_curves)
    monkeypatch.setattr(
        module,
        "_expected_cn_trading_days",
        lambda start, end: pd.DatetimeIndex(dates),
    )

    daily, _ = module._build_v11_daily(
        end_date=pd.Timestamp("2026-06-18"),
        data_state="confirmed",
        now=datetime(2026, 6, 18, 15, 31),
    )
    confirmed = module.prepare_daily_for_signal(
        daily,
        live=False,
        now=datetime(2026, 6, 18, 15, 31),
    )
    row = confirmed.sort_values("date").iloc[-1]

    assert pd.Timestamp(row["date"]).date().isoformat() == "2026-06-18"
    assert row["source_bar_is_final"] is True
    for code in module.ASSETS:
        assert row[f"bar_final_{code}"] is True
        assert str(row[f"final_time_{code}"]).startswith("2026-06-18 15:00:00")
        assert row[f"final_price_{code}"] == pytest.approx(row[f"signal_price_{code}"])


def test_confirmed_final_close_does_not_stamp_forward_filled_asset(monkeypatch):
    module = load_bot_module()
    dates = pd.to_datetime(["2026-06-17", "2026-06-18"])
    stale_code = "159941.SZ"
    prices = pd.DataFrame(
        {
            code: [1.0 + offset / 10.0, 1.1 + offset / 10.0]
            for offset, code in enumerate(module.ASSETS)
        },
        index=dates,
    )
    prices.loc[dates[-1], stale_code] = math.nan
    sources = pd.DataFrame(
        {
            "code": list(module.ASSETS),
            "name": [module.ASSETS[code] for code in module.ASSETS],
            "source": ["unit qfq"] * len(module.ASSETS),
            "adjustment": [module.ADJUSTMENT_QFQ] * len(module.ASSETS),
            "source_detail": ["unit"] * len(module.ASSETS),
            "first": ["2026-06-17"] * len(module.ASSETS),
            "last": ["2026-06-18"] * len(module.ASSETS),
            "rows": [2] * len(module.ASSETS),
        }
    )

    def fake_build_curves(input_prices, config, price_ffill_flags=None):
        assert input_prices.loc[dates[-1], stale_code] == pytest.approx(
            prices.loc[dates[0], stale_code]
        )
        assert price_ffill_flags is not None
        assert bool(price_ffill_flags.loc[dates[-1], stale_code]) is True
        daily = minimal_daily(module, dates=("2026-06-17", "2026-06-18"))
        daily.index = dates
        return [daily.drop(columns=["date"])]

    monkeypatch.setattr(module, "load_close", lambda config: (prices.copy(), sources.copy()))
    monkeypatch.setattr(module, "build_curves", fake_build_curves)
    monkeypatch.setattr(
        module,
        "_expected_cn_trading_days",
        lambda start, end: pd.DatetimeIndex(dates),
    )

    daily, _ = module._build_v11_daily(
        end_date=pd.Timestamp("2026-06-18"),
        data_state="confirmed",
        now=datetime(2026, 6, 18, 15, 35),
    )
    row = daily.sort_values("date").iloc[-1]

    assert row[f"last_date_{stale_code}"] == "2026-06-17"
    assert row["source_bar_is_final"] is not True
    assert row.get(f"bar_final_{stale_code}", False) is not True
    assert module._row_verified_final_close(row, datetime(2026, 6, 18, 15, 35)) is False
    confirmed = module.prepare_daily_for_signal(
        daily,
        live=False,
        now=datetime(2026, 6, 18, 15, 35),
    )
    assert confirmed["date"].max().date().isoformat() == "2026-06-17"


def test_global_final_flag_alone_does_not_confirm_six_asset_close(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "source_quote_time"] = "2026-06-18 15:01:00"
    daily.loc[0, "source_bar_is_final"] = True

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 6, 18, 15, 31),
        purpose="execution",
    )

    assert status["official_close_ready"] is False
    assert status["bar_is_confirmed"] is False


def test_signal_data_status_non_live_rejects_intraday_bar_without_pre_filter(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "CASH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "buy_delta"] = 0.2

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 6, 18, 14, 55),
        purpose="execution",
    )

    assert status["uses_unconfirmed_bar"] is True
    assert status["model_execution_price_available"] is False
    assert status["strategy_actionable_now"] is False
    assert status["tradable"] is False


def test_invalid_data_splits_raw_trade_from_current_execution_need(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "CASH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "buy_delta"] = 0.2

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    report = module.format_signal_report(
        daily,
        "unit-test",
        live=False,
        now=datetime(2026, 6, 18, 15, 31),
    )

    assert "原始信号是否包含调仓" not in report
    assert "当前是否需要执行" not in report
    assert "### 【异常提示】" in report
    assert "是否需要下单: **是**" not in report


def test_live_build_path_writes_quote_price_time_and_signal_price(monkeypatch):
    module = load_bot_module()
    dates = pd.to_datetime(["2026-06-17", "2026-06-18"])
    price_frame = pd.DataFrame(
        {
            code: [1.95 + i / 10.0, 2.0 + i / 10.0]
            for i, code in enumerate(module.ASSETS)
        },
        index=dates,
    )
    source_frame = pd.DataFrame(
        {
            "code": list(module.ASSETS),
            "name": [module.ASSETS[code] for code in module.ASSETS],
            "source": "unit",
            "adjustment": module.ADJUSTMENT_QFQ,
            "source_detail": "unit",
            "first": "2026-06-17",
            "last": "2026-06-18",
            "rows": 2,
        }
    )
    quotes = pd.DataFrame(
        {
            "code": list(module.ASSETS),
            "price": [2.0 + i / 10.0 for i, _ in enumerate(module.ASSETS)],
            "quote_time": ["2026-06-18 14:54:30+0800"] * len(module.ASSETS),
            "source": ["unit-live"] * len(module.ASSETS),
        }
    )

    monkeypatch.setattr(module, "load_close", lambda config: (price_frame, source_frame))
    monkeypatch.setattr(module, "load_live_quotes", lambda codes, now=None: quotes)
    monkeypatch.setattr(
        module,
        "_expected_cn_trading_days",
        lambda start, end: pd.DatetimeIndex(dates),
    )

    daily, source_note = module._build_v11_daily(
        end_date=pd.Timestamp("2026-06-18"),
        data_state="live",
        now=datetime(2026, 6, 18, 14, 55),
    )
    last = daily.sort_values("date").iloc[-1]

    assert "unit-live" in source_note
    for code, price in zip(module.ASSETS, quotes["price"]):
        assert last[f"quote_price_{code}"] == pytest.approx(float(price))
        assert str(last[f"quote_time_{code}"]).startswith("2026-06-18 14:54:30")
        assert last[f"signal_price_{code}"] == pytest.approx(float(price))


def _eastmoney_diff_rows(module, codes, price_start=2.0, quote_time=None):
    if quote_time is None:
        quote_time = datetime(2026, 6, 18, 14, 54, 30, tzinfo=module.CN_TZ)
    quote_epoch = int(quote_time.timestamp())
    return [
        {
            "f12": code.split(".", 1)[0],
            "f2": price_start + offset / 10.0,
            "f5": 1000 + offset,
            "f6": (price_start + offset / 10.0) * (1000 + offset),
            "f124": quote_epoch,
            "f297": int(quote_time.strftime("%Y%m%d")),
        }
        for offset, code in enumerate(codes)
    ]


def test_live_quote_loader_rejects_empty_diff_and_uses_backup_endpoint(monkeypatch):
    module = load_bot_module()
    calls = []

    class FakeResponse:
        def __init__(self, rows):
            self.rows = rows

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"diff": self.rows}}

    def fake_get(url, **kwargs):
        calls.append(url)
        if "push2delay.eastmoney.com" in url:
            return FakeResponse(_eastmoney_diff_rows(module, list(module.ASSETS)))
        return FakeResponse([])

    monkeypatch.setattr(module, "_http_get", fake_get)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(module, "_now_bj", lambda: datetime(2026, 6, 18, 14, 55, tzinfo=module.CN_TZ))

    quotes = module.load_live_quotes(list(module.ASSETS), now=datetime(2026, 6, 18, 14, 55))

    assert any("push2delay.eastmoney.com" in item for item in calls)
    assert set(quotes["code"]) == set(module.ASSETS)
    assert len(quotes) == len(module.ASSETS)


def test_live_quote_loader_rejects_partial_primary_response(monkeypatch):
    module = load_bot_module()
    calls = []

    class FakeResponse:
        def __init__(self, rows):
            self.rows = rows

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"diff": self.rows}}

    def fake_get(url, **kwargs):
        calls.append(url)
        if "push2delay.eastmoney.com" in url:
            return FakeResponse(_eastmoney_diff_rows(module, list(module.ASSETS), price_start=3.0))
        return FakeResponse(_eastmoney_diff_rows(module, list(module.ASSETS)[:-1], price_start=2.0))

    monkeypatch.setattr(module, "_http_get", fake_get)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(module, "_now_bj", lambda: datetime(2026, 6, 18, 14, 55, tzinfo=module.CN_TZ))

    quotes = module.load_live_quotes(list(module.ASSETS), now=datetime(2026, 6, 18, 14, 55))

    assert any("push2delay.eastmoney.com" in item for item in calls)
    assert set(quotes["code"]) == set(module.ASSETS)
    assert quotes["price"].min() >= 3.0


def test_live_quote_loader_rejects_duplicate_code_and_reports_missing(monkeypatch):
    module = load_bot_module()
    missing_code = list(module.ASSETS)[-1]
    duplicate_code = list(module.ASSETS)[0]
    bad_codes = [duplicate_code, duplicate_code, *list(module.ASSETS)[1:-1]]

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"diff": _eastmoney_diff_rows(module, bad_codes)}}

    monkeypatch.setattr(module, "_http_get", lambda url, **kwargs: FakeResponse())
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(module, "_now_bj", lambda: datetime(2026, 6, 18, 14, 55, tzinfo=module.CN_TZ))

    with pytest.raises(RuntimeError) as excinfo:
        module.load_live_quotes(list(module.ASSETS), now=datetime(2026, 6, 18, 14, 55))

    message = str(excinfo.value)
    assert "duplicate" in message
    assert duplicate_code in message
    assert "missing" in message
    assert missing_code in message


def test_live_quote_loader_marks_push2delay_as_not_execution_eligible(monkeypatch):
    module = load_bot_module()

    class FakeResponse:
        def __init__(self, url):
            self.url = url

        def raise_for_status(self):
            if "push2.eastmoney.com" in self.url:
                raise module.requests.HTTPError("primary unavailable")

        def json(self):
            return {"data": {"diff": _eastmoney_diff_rows(module, list(module.ASSETS))}}

    monkeypatch.setattr(module, "_http_get", lambda url, **kwargs: FakeResponse(url))
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(module, "_now_bj", lambda: datetime(2026, 6, 18, 14, 55, tzinfo=module.CN_TZ))

    quotes = module.load_live_quotes(list(module.ASSETS), now=datetime(2026, 6, 18, 14, 55))

    assert set(quotes["source"]) == {"Eastmoney push2delay"}
    assert quotes["source_execution_eligible"].tolist() == [False] * len(module.ASSETS)


def test_live_quote_loader_uses_response_received_time_for_future_check(monkeypatch):
    module = load_bot_module()
    quote_time = datetime(2026, 6, 18, 14, 55, 5, tzinfo=module.CN_TZ)

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"diff": _eastmoney_diff_rows(module, list(module.ASSETS), quote_time=quote_time)}}

    monkeypatch.setattr(module, "_http_get", lambda url, **kwargs: FakeResponse())
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        module,
        "_now_bj",
        lambda: datetime(2026, 6, 18, 14, 55, 10, tzinfo=module.CN_TZ),
    )

    quotes = module.load_live_quotes(
        list(module.ASSETS),
        now=datetime(2026, 6, 18, 14, 55, 0, tzinfo=module.CN_TZ),
    )

    assert set(quotes["code"]) == set(module.ASSETS)
    assert str(quotes["quote_time"].iloc[0]).startswith("2026-06-18 14:55:05")


def test_live_quote_loader_rejects_yesterday_primary_and_uses_today_backup(monkeypatch):
    module = load_bot_module()
    calls = []
    yesterday = datetime(2026, 6, 17, 14, 55, 0, tzinfo=module.CN_TZ)
    today = datetime(2026, 6, 18, 14, 55, 0, tzinfo=module.CN_TZ)

    class FakeResponse:
        def __init__(self, rows):
            self.rows = rows

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"diff": self.rows}}

    def fake_get(url, **kwargs):
        calls.append(url)
        if "push2delay.eastmoney.com" in url:
            return FakeResponse(_eastmoney_diff_rows(module, list(module.ASSETS), price_start=3.0, quote_time=today))
        return FakeResponse(_eastmoney_diff_rows(module, list(module.ASSETS), price_start=2.0, quote_time=yesterday))

    monkeypatch.setattr(module, "_http_get", fake_get)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(module, "_now_bj", lambda: datetime(2026, 6, 18, 14, 55, 2, tzinfo=module.CN_TZ))

    quotes = module.load_live_quotes(list(module.ASSETS), now=datetime(2026, 6, 18, 14, 55))

    assert any("push2delay.eastmoney.com" in item for item in calls)
    assert set(quotes["source"]) == {"Eastmoney push2delay"}
    assert quotes["price"].min() >= 3.0


def test_live_snapshot_missing_source_execution_flag_is_monitor_only(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "CASH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "buy_delta"] = 0.2
    for offset, code in enumerate(module.ASSETS):
        price = 1.0 + offset / 100.0
        daily.loc[0, f"quote_price_{code}"] = price
        daily.loc[0, f"quote_time_{code}"] = "2026-06-18 14:54:30"
        daily.loc[0, f"quote_source_{code}"] = "Eastmoney push2"
        daily.loc[0, f"signal_price_{code}"] = price

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=True,
        now=datetime(2026, 6, 18, 14, 55),
        purpose="execution",
    )

    assert set(status["source_ineligible_assets"]) == set(module.ASSETS)
    assert status["strategy_actionable_now"] is False
    assert status["tradable"] is False


def test_live_snapshot_unknown_source_is_monitor_only_even_with_true_flag(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "CASH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "buy_delta"] = 0.2
    fill_live_quote_pairs(module, daily, quote_time="2026-06-18 14:54:30")
    for code in module.ASSETS:
        daily.loc[0, f"quote_source_{code}"] = "Unit test source"
        daily.loc[0, f"source_execution_eligible_{code}"] = True

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=True,
        now=datetime(2026, 6, 18, 14, 55),
        purpose="execution",
    )

    assert set(status["source_ineligible_assets"]) == set(module.ASSETS)
    assert status["live_snapshot_fresh"] is False
    assert status["strategy_actionable_now"] is False


@pytest.mark.parametrize("bad_flag", ["garbage", "2", 2])
def test_live_snapshot_invalid_source_execution_flag_is_monitor_only(monkeypatch, bad_flag):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "CASH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "buy_delta"] = 0.2
    fill_live_quote_pairs(module, daily, quote_time="2026-06-18 14:54:30")
    for code in module.ASSETS:
        daily.loc[0, f"quote_source_{code}"] = "Eastmoney push2"
        daily.loc[0, f"source_execution_eligible_{code}"] = bad_flag

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=True,
        now=datetime(2026, 6, 18, 14, 55),
        purpose="execution",
    )

    assert set(status["source_ineligible_assets"]) == set(module.ASSETS)
    assert status["strategy_actionable_now"] is False
    assert status["tradable"] is False


def test_live_quote_loader_retries_stale_primary_before_backup(monkeypatch):
    module = load_bot_module()
    calls = []
    stale_time = datetime(2026, 6, 18, 10, 0, 0, tzinfo=module.CN_TZ)
    fresh_time = datetime(2026, 6, 18, 14, 54, 50, tzinfo=module.CN_TZ)

    class FakeResponse:
        def __init__(self, rows):
            self.rows = rows

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"diff": self.rows}}

    def fake_get(url, **kwargs):
        calls.append(url)
        if "push2delay.eastmoney.com" in url:
            return FakeResponse(
                _eastmoney_diff_rows(module, list(module.ASSETS), price_start=3.0, quote_time=fresh_time)
            )
        return FakeResponse(
            _eastmoney_diff_rows(module, list(module.ASSETS), price_start=2.0, quote_time=stale_time)
        )

    monkeypatch.setattr(module, "_http_get", fake_get)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(module, "_now_bj", lambda: datetime(2026, 6, 18, 14, 55, 0, tzinfo=module.CN_TZ))

    quotes = module.load_live_quotes(list(module.ASSETS), now=datetime(2026, 6, 18, 14, 55))

    assert sum("push2.eastmoney.com" in item for item in calls) == 2
    assert any("push2delay.eastmoney.com" in item for item in calls)
    assert set(quotes["source"]) == {"Eastmoney push2delay"}
    assert str(quotes["quote_time"].iloc[0]).startswith("2026-06-18 14:54:50")


def test_live_quote_loader_rejects_skewed_primary_before_backup(monkeypatch):
    module = load_bot_module()
    calls = []
    lagging_time = datetime(2026, 6, 18, 14, 53, 0, tzinfo=module.CN_TZ)
    fresh_time = datetime(2026, 6, 18, 14, 54, 50, tzinfo=module.CN_TZ)

    class FakeResponse:
        def __init__(self, rows):
            self.rows = rows

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"diff": self.rows}}

    def skewed_rows():
        rows = _eastmoney_diff_rows(module, list(module.ASSETS), price_start=2.0, quote_time=fresh_time)
        rows[0]["f124"] = int(lagging_time.timestamp())
        rows[0]["f297"] = int(lagging_time.strftime("%Y%m%d"))
        return rows

    def fake_get(url, **kwargs):
        calls.append(url)
        if "push2delay.eastmoney.com" in url:
            return FakeResponse(
                _eastmoney_diff_rows(module, list(module.ASSETS), price_start=3.0, quote_time=fresh_time)
            )
        return FakeResponse(skewed_rows())

    monkeypatch.setattr(module, "_http_get", fake_get)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(module, "_now_bj", lambda: datetime(2026, 6, 18, 14, 55, 0, tzinfo=module.CN_TZ))

    quotes = module.load_live_quotes(list(module.ASSETS), now=datetime(2026, 6, 18, 14, 55))

    assert any("push2delay.eastmoney.com" in item for item in calls)
    assert set(quotes["source"]) == {"Eastmoney push2delay"}
    assert quotes["price"].min() >= 3.0


def test_live_snapshot_from_ineligible_source_is_monitor_only(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "CASH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "buy_delta"] = 0.2
    fill_live_quote_pairs(module, daily, quote_time="2026-06-18 14:54:30")
    for code in module.ASSETS:
        daily.loc[0, f"quote_source_{code}"] = "Eastmoney push2delay"
        daily.loc[0, f"source_execution_eligible_{code}"] = False

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=True,
        now=datetime(2026, 6, 18, 14, 55),
        purpose="execution",
    )

    assert status["all_quote_price_time_pairs_valid"] is True
    assert status["price_matrix_uses_live_quotes"] is True
    assert set(status["source_ineligible_assets"]) == set(module.ASSETS)
    assert status["live_snapshot_fresh"] is False
    assert status["strategy_actionable_now"] is False
    assert "来源尚未获得执行许可" in status["execution_note"]


def test_apply_live_quotes_rejects_partial_snapshot_without_today_row():
    module = load_bot_module()
    prices = pd.DataFrame(
        {code: [1.0 + offset / 10.0] for offset, code in enumerate(module.ASSETS)},
        index=pd.to_datetime(["2026-06-17"]),
    )
    partial = pd.DataFrame(
        {
            "code": [list(module.ASSETS)[0]],
            "price": [2.0],
            "quote_time": ["2026-06-18 14:54:30+0800"],
            "source": ["unit-live"],
            "source_execution_eligible": [True],
        }
    )

    with pytest.raises(RuntimeError, match="Incomplete live quote snapshot"):
        module._apply_live_quotes_to_prices(
            prices,
            partial,
            now=datetime(2026, 6, 18, 14, 55),
        )

    assert pd.Timestamp("2026-06-18") not in prices.index


def test_apply_live_quotes_rejects_extreme_move_from_previous_close():
    module = load_bot_module()
    prices = pd.DataFrame(
        {code: [1.0 + offset / 10.0] for offset, code in enumerate(module.ASSETS)},
        index=pd.to_datetime(["2026-06-17"]),
    )
    quote_prices = [1.0 + offset / 10.0 for offset, _ in enumerate(module.ASSETS)]
    quote_prices[0] = 100.0
    quotes = pd.DataFrame(
        {
            "code": list(module.ASSETS),
            "price": quote_prices,
            "quote_time": ["2026-06-18 14:54:30+0800"] * len(module.ASSETS),
            "source": ["Eastmoney push2"] * len(module.ASSETS),
            "source_execution_eligible": [True] * len(module.ASSETS),
        }
    )

    with pytest.raises(RuntimeError, match="prev_close"):
        module._apply_live_quotes_to_prices(
            prices,
            quotes,
            now=datetime(2026, 6, 18, 14, 55),
        )

    assert pd.Timestamp("2026-06-18") not in prices.index


def test_apply_live_quotes_rejects_large_mismatch_with_history_today_bar():
    module = load_bot_module()
    dates = pd.to_datetime(["2026-06-17", "2026-06-18"])
    prices = pd.DataFrame(
        {code: [1.0 + offset / 10.0, 1.0 + offset / 10.0] for offset, code in enumerate(module.ASSETS)},
        index=dates,
    )
    quote_prices = [1.0 + offset / 10.0 for offset, _ in enumerate(module.ASSETS)]
    quote_prices[0] = 1.5
    quotes = pd.DataFrame(
        {
            "code": list(module.ASSETS),
            "price": quote_prices,
            "quote_time": ["2026-06-18 14:54:30+0800"] * len(module.ASSETS),
            "source": ["Eastmoney push2"] * len(module.ASSETS),
            "source_execution_eligible": [True] * len(module.ASSETS),
        }
    )

    with pytest.raises(RuntimeError, match="history_today"):
        module._apply_live_quotes_to_prices(
            prices,
            quotes,
            now=datetime(2026, 6, 18, 14, 55),
        )

    assert prices.loc[pd.Timestamp("2026-06-18"), list(module.ASSETS)[0]] == pytest.approx(1.0)


def test_live_quote_time_skew_reports_only_lagging_asset(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    fill_live_quote_pairs(module, daily, quote_time="2026-06-18 14:54:30")
    lagging_code = list(module.ASSETS)[0]
    daily.loc[0, f"quote_time_{lagging_code}"] = "2026-06-18 14:53:44"

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=True,
        now=datetime(2026, 6, 18, 14, 55),
        purpose="execution",
    )

    assert status["live_snapshot_fresh"] is False
    assert status["stale_quote_assets"] == [lagging_code]


def test_live_quote_loader_falls_back_when_primary_host_fails(monkeypatch):
    module = load_bot_module()
    calls = []

    class FakeResponse:
        def __init__(self, url, status_code=200):
            self.url = url
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise module.requests.HTTPError(f"{self.status_code} for {self.url}")

        def json(self):
            return {
                "data": {
                    "diff": _eastmoney_diff_rows(
                        module,
                        ["159915.SZ"],
                        price_start=2.5,
                        quote_time=datetime(2026, 6, 18, 14, 54, 3, tzinfo=module.CN_TZ),
                    )
                }
            }

    def fake_get(url, **kwargs):
        calls.append(url)
        if "push2.eastmoney.com" in url:
            return FakeResponse(url, status_code=502)
        return FakeResponse(url)

    monkeypatch.setattr(module, "_http_get", fake_get)
    monkeypatch.setattr(module, "_now_bj", lambda: datetime(2026, 6, 18, 14, 55, tzinfo=module.CN_TZ))

    quotes = module.load_live_quotes(["159915.SZ"])

    assert "push2.eastmoney.com" in calls[0]
    assert any("push2delay.eastmoney.com" in item for item in calls)
    assert quotes.loc[0, "code"] == "159915.SZ"
    assert quotes.loc[0, "price"] == pytest.approx(2.5)
    assert str(quotes.loc[0, "quote_time"]).endswith("+0800")


def test_execution_legs_are_disabled_when_signal_is_invalid(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-09",))
    daily.loc[0, "actual_position_before"] = "518880.SH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "sell_delta"] = 0.2
    daily.loc[0, "buy_delta"] = 0.2

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-09", "2026-06-10", "2026-06-11"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 6, 11, 10, 0),
        purpose="execution",
    )

    assert status["signal_valid"] is False
    assert status["actionable_now"] is False
    assert [leg["can_submit_order_now"] for leg in status["execution_legs"]] == [False, False]
    assert [leg["can_match_immediately"] for leg in status["execution_legs"]] == [False, False]


def test_execution_legs_are_disabled_for_performance_purpose(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "518880.SH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "sell_delta"] = 0.2
    daily.loc[0, "buy_delta"] = 0.2

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 6, 18, 10, 0),
        purpose="performance",
    )

    assert status["signal_valid"] is True
    assert status["actionable_now"] is False
    assert [leg["can_submit_order_now"] for leg in status["execution_legs"]] == [False, False]
    assert [leg["can_match_immediately"] for leg in status["execution_legs"]] == [False, False]


def test_top_execution_session_is_mixed_when_execution_legs_differ(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    daily.loc[0, "actual_position_before"] = "518880.SH"
    daily.loc[0, "actual_position_next"] = "159915.SZ"
    daily.loc[0, "sell_delta"] = 0.2
    daily.loc[0, "buy_delta"] = 0.2

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 6, 18, 14, 58),
        purpose="execution",
    )

    assert status["execution_session"] == "MIXED"
    assert status["exchange_all_legs_can_submit"] is True
    assert status["all_legs_can_submit"] is False
    assert status["all_legs_can_match_immediately"] is False
    assert status["exchange_some_legs_can_match_immediately"] is True
    assert status["some_legs_can_match_immediately"] is False
    assert status["partially_executable"] is True
    assert status["continuous_actionable_now"] is False
    assert status["actionable_now"] is False
    assert [leg["execution_session"] for leg in status["execution_legs"]] == [
        "OPEN_PM",
        "CLOSE_CALL_ACCEPT",
    ]


def test_parse_month_range_rolls_end_year_forward():
    module = load_bot_module()

    start, end = module.parse_date_range("2025年12月到1月", now=datetime(2026, 6, 18))

    assert start == pd.Timestamp("2025-12-01")
    assert end == pd.Timestamp("2026-01-31")


def test_parse_invalid_month_and_day_rejects_instead_of_fallback():
    module = load_bot_module()

    with pytest.raises(ValueError, match="非法"):
        module.parse_date_range("2026-13", now=datetime(2026, 6, 18))
    with pytest.raises(ValueError, match="非法"):
        module.parse_date_range("2026年2月30日", now=datetime(2026, 6, 18))


def test_parse_date_range_default_now_is_beijing_naive(monkeypatch):
    module = load_bot_module()
    monkeypatch.setattr(module, "_now_bj", lambda: datetime(2026, 6, 18, 10, 0, tzinfo=module.CN_TZ))

    start, end = module.parse_date_range("6月1日至今")

    assert start == pd.Timestamp("2026-06-01")
    assert end == pd.Timestamp("2026-06-18")
    assert start.tzinfo is None
    assert end.tzinfo is None


def test_resolve_performance_ranges_uses_beijing_today_when_now_missing(monkeypatch):
    module = load_bot_module()
    monkeypatch.setattr(module, "_now_bj", lambda: datetime(2026, 6, 18, 10, 0, tzinfo=module.CN_TZ))

    ranges = module.resolve_performance_ranges("近1个月", earliest_date=pd.Timestamp("2020-01-02"))

    assert ranges[0] == ("2026-05-18~2026-06-18", pd.Timestamp("2026-05-18"), pd.Timestamp("2026-06-18"))
    labels = [label for label, _start, _end in ranges]
    assert labels[1:6] == ["full_sample", "10Y", "5Y", "3Y", "1Y"]


def test_parse_explicit_reverse_year_month_range_rejected():
    module = load_bot_module()

    with pytest.raises(ValueError, match="结束日期不能早于开始日期"):
        module.parse_date_range("2026-12 到 2025-01", now=datetime(2026, 6, 18))


def test_max_drawdown_counts_window_first_day_loss():
    module = load_bot_module()
    daily = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-01-02"]),
            "nav": [0.90, 0.90],
            "return": [-0.10, 0.0],
            "turnover": [0.0, 0.0],
            "weight": [1.0, 1.0],
            "final_exposure_after_overheat": [1.0, 1.0],
            "exposure_effective": [1.0, 1.0],
            "position": ["159915.SZ", "159915.SZ"],
            "overheat_on": [False, False],
            "overheat_on_effective": [False, False],
        }
    )

    perf = module.calc_performance(daily, pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-02"))
    yearly = module.calc_yearly_performance(daily, pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-02"))
    window = module._nav_window(daily, pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-02"))

    assert perf["maxdd"] == pytest.approx(0.0)
    assert yearly[0]["maxdd"] == pytest.approx(0.0)
    assert float(window["drawdown"].min()) == pytest.approx(0.0)


def test_drawdown_uses_window_peak_without_forcing_initial_one():
    module = load_bot_module()
    wealth = pd.Series([0.90, 0.95, 0.93], dtype=float)

    drawdown = module._drawdown_from_wealth(wealth)

    assert drawdown.tolist() == pytest.approx([0.0, 0.0, 0.93 / 0.95 - 1.0])


def test_standalone_max_drawdown_uses_actual_window_peak():
    module = load_bot_module()
    nav = pd.Series([0.90, 0.95, 0.93], dtype=float)

    assert module.max_drawdown(nav) == pytest.approx(0.93 / 0.95 - 1.0)


def test_live_force_refresh_updates_confirmed_raw_cache(monkeypatch):
    module = load_bot_module()
    calls = []

    def fake_build(end_date=None):
        calls.append(len(calls) + 1)
        return pd.DataFrame({"marker": [calls[-1]]}), f"source-{calls[-1]}"

    monkeypatch.setattr(module, "_build_v11_daily", fake_build)
    module._cached_daily.cache_clear()

    live, _ = module._get_daily_for_today(force_refresh=True, data_state="live")
    confirmed, _ = module._get_daily_for_today(force_refresh=False, data_state="confirmed")

    assert int(live["marker"].iloc[0]) == 1
    assert int(confirmed["marker"].iloc[0]) == 2
    assert calls == [1, 2]


def test_live_force_refresh_reuses_same_state_cache_when_provider_refresh_fails(monkeypatch):
    module = load_bot_module()
    module._cached_daily.cache_clear()
    now = datetime(2026, 6, 18, 14, 55, tzinfo=module.CN_TZ)
    cached_at = datetime(2026, 6, 18, 14, 40, tzinfo=module.CN_TZ)
    key = module._daily_cache_key("2026-06-18", "live")
    cached_daily = pd.DataFrame({"date": [pd.Timestamp("2026-06-18")], "marker": [7]})
    module._DAILY_CACHE[key] = (cached_at, cached_daily, "cached-live-qfq")

    def fail_refresh(end_date, data_state, now):
        raise RuntimeError("All qfq data sources failed. 159915.SZ provider down")

    monkeypatch.setattr(module, "_now_bj", lambda: now)
    monkeypatch.setattr(module, "_call_build_v11_daily", fail_refresh)

    daily, source_note = module._get_daily_for_today(force_refresh=True, data_state="live")

    assert daily["marker"].tolist() == [7]
    assert "cached-live-qfq" in source_note
    assert "refresh failed" in source_note
    assert "159915.SZ provider down" in source_note


def test_align_prices_forward_fills_lagging_latest_asset(monkeypatch):
    module = load_bot_module()
    dates = pd.to_datetime(["2026-06-15", "2026-06-16", "2026-06-17"])
    prices = pd.DataFrame(1.0, index=dates, columns=list(module.ASSETS))
    prices.loc[dates[1], "159915.SZ"] = 1.05
    prices.loc[dates[-1], "159915.SZ"] = math.nan
    monkeypatch.setattr(module, "_expected_cn_trading_days", lambda start, end: pd.DatetimeIndex(dates))

    aligned, common_last, last_by_asset = module.align_prices_to_common_valid_date(
        prices,
        list(module.ASSETS),
    )

    assert common_last == dates[-1]
    assert aligned.loc[dates[-1], "159915.SZ"] == pytest.approx(1.05)
    assert last_by_asset["159915.SZ"] == dates[1]
    assert last_by_asset["159941.SZ"] == dates[-1]


def test_qfq_source_validation_rejects_qfq_raw_label():
    module = load_bot_module()
    sources = pd.DataFrame(
        [
            {
                "code": "159915.SZ",
                "source": "unit",
                "adjustment": "qfq/raw",
            }
        ]
    )

    with pytest.raises(RuntimeError, match="Non-qfq"):
        module._validate_qfq_sources(sources)


def test_qfq_source_validation_rejects_unapproved_source_even_if_labeled_qfq():
    module = load_bot_module()
    sources = pd.DataFrame(
        [
            {
                "code": "159915.SZ",
                "source": "CNFin renamed fallback",
                "adjustment": module.ADJUSTMENT_QFQ,
                "source_detail": "fqt=1",
                "first": "2026-01-01",
                "last": "2026-01-02",
                "rows": 2,
            }
        ]
    )

    with pytest.raises(RuntimeError, match="Unapproved qfq historical source"):
        module._validate_qfq_sources(sources)


def test_latest_signal_exposes_actual_positions_and_missing_overheat_features():
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-09",))
    daily.loc[0, "position_before"] = "159915.SZ"
    daily.loc[0, "position"] = "159915.SZ"
    daily.loc[0, "exposure_effective"] = 1.0
    daily.loc[0, "final_exposure_after_overheat"] = 0.0
    daily.loc[0, "overheat_feature_missing"] = True

    sig = module.latest_signal(daily)

    assert sig["base_position_before"] == "159915.SZ"
    assert sig["base_position_next"] == "159915.SZ"
    assert sig["actual_position_before"] == "159915.SZ"
    assert sig["actual_position_next"] == "CASH"
    assert sig["overheat_feature_missing"] is True


def test_last_actual_trade_date_uses_turnover_not_trade_target():
    module = load_bot_module()
    daily = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]),
            "trade_target": ["159915.SZ", None, "159941.SZ"],
            "turnover": [0.0, 1.0, 0.0],
        }
    )

    assert module._last_base_signal_date(daily) == "2026-01-03"
    assert module._last_actual_trade_date(daily) == "2026-01-02"


def test_signal_report_shows_base_signal_date_and_actual_trade_date():
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-09", "2026-06-10", "2026-06-11"))
    daily.loc[1, "turnover"] = 1.0
    daily.loc[2, "trade_target"] = "159915.SZ"
    daily.loc[2, "turnover"] = 0.0
    fill_final_quote_pairs(module, daily, row_idx=2, quote_time="2026-06-11 15:01:00")

    report = module.format_signal_report(
        daily,
        "unit-test",
        live=False,
        now=datetime(2026, 6, 11, 16, 0),
    )

    assert "上次底层调仓信号: **2026-06-11**" in report
    assert "上次实际成交日: **2026-06-10**" in report


def test_calc_bias_momentum_first_valid_index_is_not_one_day_late():
    module = load_bot_module()
    n = module.CN_BIAS_N + module.CN_MOM_DAY - 1
    close = pd.Series(range(100, 100 + n), index=pd.date_range("2026-01-01", periods=n))

    momentum = module.calc_bias_momentum(close)

    assert pd.notna(momentum.iloc[-1])


def test_weighted_slope_score_handles_extreme_prices_without_overflow(monkeypatch):
    module = load_bot_module()
    values = pd.Series(np.exp(np.linspace(0.0, 700.0, module.LOOKBACK)))

    score, r2 = module.weighted_slope_score_and_r2(values)

    assert math.isnan(score)
    assert 0.0 <= r2 <= 1.0


def _reference_prices_for_live_quality(module, include_today=False):
    codes = list(module.ASSETS)
    dates = [pd.Timestamp("2026-06-17")]
    if include_today:
        dates.append(pd.Timestamp("2026-06-18"))
    return pd.DataFrame(
        {
            code: [1.0 + offset / 10.0 for _ in dates]
            for offset, code in enumerate(codes)
        },
        index=pd.DatetimeIndex(dates),
    )


def test_live_quote_loader_falls_back_when_primary_price_quality_fails(monkeypatch):
    module = load_bot_module()
    codes = list(module.ASSETS)
    prices = _reference_prices_for_live_quality(module)
    quote_time = datetime(2026, 6, 18, 14, 54, 50, tzinfo=module.CN_TZ)
    calls = []

    class FakeResponse:
        def __init__(self, rows):
            self.rows = rows

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"diff": self.rows}}

    def primary_rows():
        rows = _eastmoney_diff_rows(module, codes, price_start=1.0, quote_time=quote_time)
        rows[0]["f2"] = float(prices.iloc[-1, 0]) * 1.40
        return rows

    def backup_rows():
        rows = _eastmoney_diff_rows(module, codes, price_start=1.0, quote_time=quote_time)
        for offset, row in enumerate(rows):
            row["f2"] = float(prices.iloc[-1, offset])
        return rows

    def fake_get(url, **kwargs):
        calls.append(url)
        return FakeResponse(backup_rows() if "backup" in url else primary_rows())

    monkeypatch.setattr(
        module,
        "EASTMONEY_LIVE_ENDPOINTS",
        (
            ("https://unit.test/primary", "Eastmoney push2", True),
            ("https://unit.test/backup", "Eastmoney push2", True),
        ),
    )
    monkeypatch.setattr(module, "_http_get", fake_get)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(module, "_now_bj", lambda: datetime(2026, 6, 18, 14, 55, tzinfo=module.CN_TZ))

    quotes = module.load_live_quotes(
        codes,
        now=datetime(2026, 6, 18, 14, 55),
        reference_prices=prices,
        expected_quote_date=pd.Timestamp("2026-06-18"),
    )

    assert sum("primary" in item for item in calls) == 2
    assert any("backup" in item for item in calls)
    assert quotes["price"].tolist() == pytest.approx(prices.iloc[-1].tolist())


def test_159915_twenty_five_percent_quote_rejected_by_security_price_limit():
    module = load_bot_module()
    prices = _reference_prices_for_live_quality(module)
    quote_prices = prices.iloc[-1].tolist()
    quote_prices[0] = float(prices.iloc[-1, 0]) * 1.25
    quotes = pd.DataFrame(
        {
            "code": list(module.ASSETS),
            "price": quote_prices,
            "quote_time": ["2026-06-18 14:54:30+0800"] * len(module.ASSETS),
            "source": ["Eastmoney push2"] * len(module.ASSETS),
            "source_execution_eligible": [True] * len(module.ASSETS),
        }
    )

    with pytest.raises(RuntimeError, match="price_limit"):
        module._apply_live_quotes_to_prices(
            prices,
            quotes,
            now=datetime(2026, 6, 18, 14, 55),
        )

    assert pd.Timestamp("2026-06-18") not in prices.index


def test_history_today_diff_without_timestamp_tries_backup_candidate(monkeypatch):
    module = load_bot_module()
    codes = list(module.ASSETS)
    prices = _reference_prices_for_live_quality(module, include_today=True)
    quote_time = datetime(2026, 6, 18, 14, 54, 50, tzinfo=module.CN_TZ)
    calls = []

    class FakeResponse:
        def __init__(self, rows):
            self.rows = rows

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"diff": self.rows}}

    def rows_with_multiplier(multiplier):
        rows = _eastmoney_diff_rows(module, codes, price_start=1.0, quote_time=quote_time)
        for offset, row in enumerate(rows):
            row["f2"] = float(prices.iloc[-1, offset]) * multiplier
        return rows

    def fake_get(url, **kwargs):
        calls.append(url)
        if "backup" in url:
            return FakeResponse(rows_with_multiplier(1.0))
        return FakeResponse(rows_with_multiplier(1.04))

    monkeypatch.setattr(
        module,
        "EASTMONEY_LIVE_ENDPOINTS",
        (
            ("https://unit.test/primary", "Eastmoney push2", True),
            ("https://unit.test/backup", "Eastmoney push2", True),
        ),
    )
    monkeypatch.setattr(module, "_http_get", fake_get)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(module, "_now_bj", lambda: datetime(2026, 6, 18, 14, 55, tzinfo=module.CN_TZ))

    quotes = module.load_live_quotes(
        codes,
        now=datetime(2026, 6, 18, 14, 55),
        reference_prices=prices,
        expected_quote_date=pd.Timestamp("2026-06-18"),
    )

    assert any("backup" in item for item in calls)
    assert quotes["price"].tolist() == pytest.approx(prices.iloc[-1].tolist())


def test_live_quote_loader_raises_when_all_candidates_fail_price_quality(monkeypatch):
    module = load_bot_module()
    codes = list(module.ASSETS)
    prices = _reference_prices_for_live_quality(module)
    quote_time = datetime(2026, 6, 18, 14, 54, 50, tzinfo=module.CN_TZ)

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            rows = _eastmoney_diff_rows(module, codes, price_start=1.0, quote_time=quote_time)
            rows[0]["f2"] = float(prices.iloc[-1, 0]) * 1.40
            return {"data": {"diff": rows}}

    monkeypatch.setattr(module, "_http_get", lambda url, **kwargs: FakeResponse())
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(module, "_now_bj", lambda: datetime(2026, 6, 18, 14, 55, tzinfo=module.CN_TZ))

    with pytest.raises(RuntimeError, match="price_limit"):
        module.load_live_quotes(
            codes,
            now=datetime(2026, 6, 18, 14, 55),
            reference_prices=prices,
            expected_quote_date=pd.Timestamp("2026-06-18"),
        )

    assert pd.Timestamp("2026-06-18") not in prices.index


@pytest.mark.parametrize("bad_final_flag", [2, "garbage", None])
def test_final_bar_flag_is_strict_fail_closed(monkeypatch, bad_final_flag):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))
    fill_final_quote_pairs(module, daily, row_idx=0, quote_time="2026-06-18 15:01:00")
    for code in module.ASSETS:
        key = f"bar_final_{code}"
        if bad_final_flag is None:
            daily = daily.drop(columns=[key])
        else:
            daily.loc[0, key] = bad_final_flag

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    status = module.signal_data_status(
        daily,
        live=False,
        now=datetime(2026, 6, 18, 15, 31),
        purpose="execution",
    )

    assert status["official_close_ready"] is False
    assert status["bar_is_confirmed"] is False


def test_monitor_candidate_prefers_lower_max_age_and_skew_over_latest_single_quote(monkeypatch):
    module = load_bot_module()
    codes = list(module.ASSETS)
    now = datetime(2026, 6, 18, 14, 55, 0, tzinfo=module.CN_TZ)
    latest_time = datetime(2026, 6, 18, 14, 54, 50, tzinfo=module.CN_TZ)
    very_old_time = datetime(2026, 6, 18, 10, 54, 50, tzinfo=module.CN_TZ)
    mildly_stale_time = datetime(2026, 6, 18, 14, 52, 50, tzinfo=module.CN_TZ)

    class FakeResponse:
        def __init__(self, rows):
            self.rows = rows

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"diff": self.rows}}

    def primary_rows():
        rows = _eastmoney_diff_rows(module, codes, price_start=2.0, quote_time=latest_time)
        rows[0]["f124"] = int(very_old_time.timestamp())
        rows[0]["f297"] = int(very_old_time.strftime("%Y%m%d"))
        return rows

    def backup_rows():
        return _eastmoney_diff_rows(module, codes, price_start=3.0, quote_time=mildly_stale_time)

    def fake_get(url, **kwargs):
        return FakeResponse(backup_rows() if "backup" in url else primary_rows())

    monkeypatch.setattr(
        module,
        "EASTMONEY_LIVE_ENDPOINTS",
        (
            ("https://unit.test/primary", "Eastmoney push2", True),
            ("https://unit.test/backup", "Eastmoney push2delay", False),
        ),
    )
    monkeypatch.setattr(module, "_http_get", fake_get)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(module, "_now_bj", lambda: now)

    quotes = module.load_live_quotes(codes, now=now)

    assert set(quotes["source"]) == {"Eastmoney push2delay"}
    assert quotes["price"].min() >= 3.0
    assert str(quotes["quote_time"].iloc[0]).startswith("2026-06-18 14:52:50")


def test_live_params_snapshot_lists_live_price_risk_parameters(monkeypatch):
    module = load_bot_module()
    daily = minimal_daily(module, dates=("2026-06-18",))

    def expected_sessions(start, end):
        return pd.DatetimeIndex(pd.to_datetime(["2026-06-18"]))

    monkeypatch.setattr(module, "_expected_cn_trading_days", expected_sessions)

    text = module.format_live_params_snapshot(
        daily,
        "unit-test",
        live=True,
        now=datetime(2026, 6, 18, 10, 0),
    )

    assert "Live price limit by ETF" in text
    assert "159915.SZ=20%" in text
    assert "history today cross-check" in text
    assert "temporary proxy price band" in text
    assert "exchange price band" not in text


def test_price_limit_accepts_exchange_tick_rounded_limit_price():
    module = load_bot_module()
    codes = list(module.ASSETS)
    prices = _reference_prices_for_live_quality(module)
    target_code = "159941.SZ"
    target_idx = codes.index(target_code)
    prices.loc[pd.Timestamp("2026-06-17"), target_code] = 1.006
    quote_prices = prices.iloc[-1].tolist()
    quote_prices[target_idx] = 1.107
    quotes = pd.DataFrame(
        {
            "code": codes,
            "price": quote_prices,
            "quote_time": ["2026-06-18 14:54:30+0800"] * len(codes),
            "source": ["Eastmoney push2"] * len(codes),
            "source_execution_eligible": [True] * len(codes),
        }
    )

    out, _ = module._apply_live_quotes_to_prices(
        prices,
        quotes,
        now=datetime(2026, 6, 18, 14, 55),
    )

    assert out.loc[pd.Timestamp("2026-06-18"), target_code] == pytest.approx(1.107)


def test_live_quote_metadata_derives_limit_bounds_from_prev_close():
    module = load_bot_module()
    codes = list(module.ASSETS)
    prices = _reference_prices_for_live_quality(module)
    target_code = "159941.SZ"
    target_idx = codes.index(target_code)
    prices.loc[pd.Timestamp("2026-06-17"), target_code] = 1.006
    quote_prices = prices.iloc[-1].tolist()
    quote_prices[target_idx] = 1.107
    quotes = pd.DataFrame(
        {
            "code": codes,
            "price": quote_prices,
            "quote_time": ["2026-06-18 14:54:30+0800"] * len(codes),
            "source": ["Eastmoney push2"] * len(codes),
            "source_execution_eligible": [True] * len(codes),
            "prev_close": [
                prices.loc[pd.Timestamp("2026-06-17"), code]
                for code in codes
            ],
            "volume": [1000] * len(codes),
            "amount": [2000] * len(codes),
        }
    )

    _out, metadata = module._apply_live_quotes_to_prices(
        prices,
        quotes,
        now=datetime(2026, 6, 18, 14, 55),
    )

    assert metadata[target_code]["quote_limit_up"] == pytest.approx(1.107)
    assert metadata[target_code]["quote_limit_down"] == pytest.approx(0.905)


def test_price_limit_rejects_quote_above_tick_rounded_limit_price():
    module = load_bot_module()
    codes = list(module.ASSETS)
    prices = _reference_prices_for_live_quality(module)
    target_code = "159941.SZ"
    target_idx = codes.index(target_code)
    prices.loc[pd.Timestamp("2026-06-17"), target_code] = 1.006
    quote_prices = prices.iloc[-1].tolist()
    quote_prices[target_idx] = 1.108
    quotes = pd.DataFrame(
        {
            "code": codes,
            "price": quote_prices,
            "quote_time": ["2026-06-18 14:54:30+0800"] * len(codes),
            "source": ["Eastmoney push2"] * len(codes),
            "source_execution_eligible": [True] * len(codes),
        }
    )

    with pytest.raises(RuntimeError, match="price_limit"):
        module._apply_live_quotes_to_prices(
            prices,
            quotes,
            now=datetime(2026, 6, 18, 14, 55),
        )


def test_quote_price_must_be_etf_tick_multiple():
    module = load_bot_module()
    codes = list(module.ASSETS)
    prices = _reference_prices_for_live_quality(module)
    quote_prices = prices.iloc[-1].tolist()
    quote_prices[codes.index("159941.SZ")] = 1.0065
    quotes = pd.DataFrame(
        {
            "code": codes,
            "price": quote_prices,
            "quote_time": ["2026-06-18 14:54:30+0800"] * len(codes),
            "source": ["Eastmoney push2"] * len(codes),
            "source_execution_eligible": [True] * len(codes),
        }
    )

    with pytest.raises(RuntimeError, match="price_tick"):
        module._apply_live_quotes_to_prices(
            prices,
            quotes,
            now=datetime(2026, 6, 18, 14, 55),
        )


def test_prev_close_one_tick_comparison_uses_decimal_boundary():
    module = load_bot_module()

    assert module._prev_close_matches_reference(1.002, 1.001)
    assert module._prev_close_matches_reference(0.501, 0.500)


def test_vendor_prev_close_must_match_independent_history_reference():
    module = load_bot_module()
    codes = list(module.ASSETS)
    prices = _reference_prices_for_live_quality(module)
    target_code = "159941.SZ"
    target_idx = codes.index(target_code)
    quote_prices = prices.iloc[-1].tolist()
    quote_prices[target_idx] = 10.0
    quotes = pd.DataFrame(
        {
            "code": codes,
            "price": quote_prices,
            "quote_time": ["2026-06-18 14:54:30+0800"] * len(codes),
            "source": ["Eastmoney push2"] * len(codes),
            "source_execution_eligible": [True] * len(codes),
            "prev_close": [10.0 if code == target_code else prices.loc[pd.Timestamp("2026-06-17"), code] for code in codes],
        }
    )

    with pytest.raises(RuntimeError, match="prev_close_reference"):
        module._apply_live_quotes_to_prices(
            prices,
            quotes,
            now=datetime(2026, 6, 18, 14, 55),
        )


def test_vendor_prev_close_small_mismatch_blocks_execution():
    module = load_bot_module()
    codes = list(module.ASSETS)
    prices = _reference_prices_for_live_quality(module)
    target_code = "159941.SZ"
    target_idx = codes.index(target_code)
    prices.loc[pd.Timestamp("2026-06-17"), target_code] = 1.0
    quote_prices = prices.iloc[-1].tolist()
    quote_prices[target_idx] = 1.103
    quotes = pd.DataFrame(
        {
            "code": codes,
            "price": quote_prices,
            "quote_time": ["2026-06-18 14:54:30+0800"] * len(codes),
            "source": ["Eastmoney push2"] * len(codes),
            "source_execution_eligible": [True] * len(codes),
            "prev_close": [
                1.003 if code == target_code else prices.loc[pd.Timestamp("2026-06-17"), code]
                for code in codes
            ],
        }
    )

    with pytest.raises(RuntimeError, match="prev_close_reference"):
        module._apply_live_quotes_to_prices(
            prices,
            quotes,
            now=datetime(2026, 6, 18, 14, 55),
        )


def test_vendor_prev_close_must_be_etf_tick_multiple():
    module = load_bot_module()
    codes = list(module.ASSETS)
    prices = _reference_prices_for_live_quality(module)
    target_code = "159941.SZ"
    prices.loc[pd.Timestamp("2026-06-17"), target_code] = 1.0
    quote_prices = prices.iloc[-1].tolist()
    quotes = pd.DataFrame(
        {
            "code": codes,
            "price": quote_prices,
            "quote_time": ["2026-06-18 14:54:30+0800"] * len(codes),
            "source": ["Eastmoney push2"] * len(codes),
            "source_execution_eligible": [True] * len(codes),
            "prev_close": [
                1.0005 if code == target_code else prices.loc[pd.Timestamp("2026-06-17"), code]
                for code in codes
            ],
        }
    )

    with pytest.raises(RuntimeError, match="prev_close_tick"):
        module._apply_live_quotes_to_prices(
            prices,
            quotes,
            now=datetime(2026, 6, 18, 14, 55),
        )


def test_price_bad_primary_uses_delay_backup_for_monitor_only(monkeypatch):
    module = load_bot_module()
    codes = list(module.ASSETS)
    prices = _reference_prices_for_live_quality(module)
    quote_time = datetime(2026, 6, 18, 14, 54, 50, tzinfo=module.CN_TZ)

    class FakeResponse:
        def __init__(self, rows):
            self.rows = rows

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"diff": self.rows}}

    def rows_for(price_multiplier):
        rows = _eastmoney_diff_rows(module, codes, price_start=1.0, quote_time=quote_time)
        for offset, row in enumerate(rows):
            row["f2"] = float(prices.iloc[-1, offset]) * price_multiplier
            row["f18"] = float(prices.iloc[-1, offset])
        return rows

    def fake_get(url, **kwargs):
        if "push2delay" in url:
            return FakeResponse(rows_for(1.0))
        return FakeResponse(rows_for(1.40))

    monkeypatch.setattr(module, "_http_get", fake_get)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(module, "_now_bj", lambda: datetime(2026, 6, 18, 14, 55, tzinfo=module.CN_TZ))

    quotes = module.load_live_quotes(
        codes,
        now=datetime(2026, 6, 18, 14, 55),
        reference_prices=prices,
        expected_quote_date=pd.Timestamp("2026-06-18"),
    )

    assert set(quotes["source"]) == {"Eastmoney push2delay"}
    assert quotes["source_execution_eligible"].tolist() == [False] * len(codes)


def test_stale_monitor_candidate_must_pass_price_quality_before_selection(monkeypatch):
    module = load_bot_module()
    codes = list(module.ASSETS)
    prices = _reference_prices_for_live_quality(module)
    now = datetime(2026, 6, 18, 14, 55, 0, tzinfo=module.CN_TZ)
    normal_time = datetime(2026, 6, 18, 14, 52, 50, tzinfo=module.CN_TZ)
    bad_time = datetime(2026, 6, 18, 14, 52, 55, tzinfo=module.CN_TZ)

    class FakeResponse:
        def __init__(self, rows):
            self.rows = rows

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"diff": self.rows}}

    def rows_for(quote_time, price_multiplier):
        rows = _eastmoney_diff_rows(module, codes, price_start=1.0, quote_time=quote_time)
        for offset, row in enumerate(rows):
            row["f2"] = float(prices.iloc[-1, offset]) * price_multiplier
            row["f18"] = float(prices.iloc[-1, offset])
        return rows

    def fake_get(url, **kwargs):
        if "backup" in url:
            return FakeResponse(rows_for(bad_time, 2.0))
        return FakeResponse(rows_for(normal_time, 1.0))

    monkeypatch.setattr(
        module,
        "EASTMONEY_LIVE_ENDPOINTS",
        (
            ("https://unit.test/primary", "Eastmoney push2", True),
            ("https://unit.test/backup", "Eastmoney push2delay", False),
        ),
    )
    monkeypatch.setattr(module, "_http_get", fake_get)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(module, "_now_bj", lambda: now)

    quotes = module.load_live_quotes(
        codes,
        now=now,
        reference_prices=prices,
        expected_quote_date=pd.Timestamp("2026-06-18"),
    )

    assert set(quotes["source"]) == {"Eastmoney push2"}
    assert quotes["price"].tolist() == pytest.approx(prices.iloc[-1].tolist())


def test_missing_vendor_prev_close_demotes_candidate_to_monitor_only(monkeypatch):
    module = load_bot_module()
    codes = list(module.ASSETS)
    prices = _reference_prices_for_live_quality(module)
    now = datetime(2026, 6, 18, 14, 55, 0, tzinfo=module.CN_TZ)
    quote_time = datetime(2026, 6, 18, 14, 54, 50, tzinfo=module.CN_TZ)

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            rows = _eastmoney_diff_rows(module, codes, price_start=1.0, quote_time=quote_time)
            for offset, row in enumerate(rows):
                row["f2"] = float(prices.iloc[-1, offset])
                row.pop("f18", None)
            return {"data": {"diff": rows}}

    monkeypatch.setattr(
        module,
        "EASTMONEY_LIVE_ENDPOINTS",
        (("https://unit.test/primary", "Eastmoney push2", True),),
    )
    monkeypatch.setattr(module, "_http_get", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(module, "_now_bj", lambda: now)

    quotes = module.load_live_quotes(
        codes,
        now=now,
        reference_prices=prices,
        expected_quote_date=pd.Timestamp("2026-06-18"),
    )

    assert set(quotes["source"]) == {"Eastmoney push2"}
    assert quotes["source_execution_eligible"].tolist() == [False] * len(codes)


def test_monitor_candidate_prefers_synchronized_over_less_aged_skewed_snapshot(monkeypatch):
    module = load_bot_module()
    codes = list(module.ASSETS)
    now = datetime(2026, 6, 18, 14, 55, 0, tzinfo=module.CN_TZ)
    nine_seconds_ago = datetime(2026, 6, 18, 14, 54, 51, tzinfo=module.CN_TZ)
    one_hundred_nineteen_seconds_ago = datetime(2026, 6, 18, 14, 53, 1, tzinfo=module.CN_TZ)
    one_hundred_twenty_one_seconds_ago = datetime(2026, 6, 18, 14, 52, 59, tzinfo=module.CN_TZ)

    class FakeResponse:
        def __init__(self, rows):
            self.rows = rows

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"diff": self.rows}}

    def skewed_rows():
        rows = _eastmoney_diff_rows(module, codes, price_start=2.0, quote_time=nine_seconds_ago)
        rows[0]["f124"] = int(one_hundred_nineteen_seconds_ago.timestamp())
        rows[0]["f297"] = int(one_hundred_nineteen_seconds_ago.strftime("%Y%m%d"))
        return rows

    def synchronized_rows():
        return _eastmoney_diff_rows(
            module,
            codes,
            price_start=3.0,
            quote_time=one_hundred_twenty_one_seconds_ago,
        )

    def fake_get(url, **kwargs):
        if "backup" in url:
            return FakeResponse(synchronized_rows())
        return FakeResponse(skewed_rows())

    monkeypatch.setattr(
        module,
        "EASTMONEY_LIVE_ENDPOINTS",
        (
            ("https://unit.test/primary", "Eastmoney push2", True),
            ("https://unit.test/backup", "Eastmoney push2delay", False),
        ),
    )
    monkeypatch.setattr(module, "_http_get", fake_get)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(module, "_now_bj", lambda: now)

    quotes = module.load_live_quotes(codes, now=now)

    assert set(quotes["source"]) == {"Eastmoney push2delay"}
    assert quotes["price"].min() >= 3.0


def test_monitor_candidate_prefers_slight_skew_current_over_hours_old_synchronized(monkeypatch):
    module = load_bot_module()
    codes = list(module.ASSETS)
    now = datetime(2026, 6, 18, 14, 55, 0, tzinfo=module.CN_TZ)
    hours_old = datetime(2026, 6, 18, 10, 0, 0, tzinfo=module.CN_TZ)
    five_seconds_ago = datetime(2026, 6, 18, 14, 54, 55, tzinfo=module.CN_TZ)
    thirty_six_seconds_ago = datetime(2026, 6, 18, 14, 54, 24, tzinfo=module.CN_TZ)

    class FakeResponse:
        def __init__(self, rows):
            self.rows = rows

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"diff": self.rows}}

    def hours_old_rows():
        return _eastmoney_diff_rows(module, codes, price_start=2.0, quote_time=hours_old)

    def slightly_skewed_current_rows():
        rows = _eastmoney_diff_rows(module, codes, price_start=3.0, quote_time=five_seconds_ago)
        rows[0]["f124"] = int(thirty_six_seconds_ago.timestamp())
        rows[0]["f297"] = int(thirty_six_seconds_ago.strftime("%Y%m%d"))
        return rows

    def fake_get(url, **kwargs):
        if "backup" in url:
            return FakeResponse(slightly_skewed_current_rows())
        return FakeResponse(hours_old_rows())

    monkeypatch.setattr(
        module,
        "EASTMONEY_LIVE_ENDPOINTS",
        (
            ("https://unit.test/primary", "Eastmoney push2", True),
            ("https://unit.test/backup", "Eastmoney push2delay", False),
        ),
    )
    monkeypatch.setattr(module, "_http_get", fake_get)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(module, "_now_bj", lambda: now)

    quotes = module.load_live_quotes(codes, now=now)

    assert set(quotes["source"]) == {"Eastmoney push2delay"}
    assert quotes["price"].min() >= 3.0
