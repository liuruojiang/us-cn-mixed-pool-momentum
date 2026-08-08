import importlib.util
import math
from contextvars import copy_context
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
BOT_PATH = ROOT / "poe_subd_mixed_pool_v1_3_bot.py"


def load_bot_module():
    spec = importlib.util.spec_from_file_location("poe_subd_mixed_pool_v1_3_under_test", BOT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
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


def test_v13_performance_failure_is_not_suppressed_by_other_rendered_context(monkeypatch):
    module = load_bot_module()
    bot = module.SubDMixedPoolV13Bot()
    other_request = copy_context()
    monkeypatch.setattr(module.poe, "query", SimpleNamespace(text="表现"), raising=False)

    def interleaved_handler(_query):
        other_request.run(module._set_performance_response_rendered, True)
        raise RuntimeError("request A failed")

    monkeypatch.setattr(bot, "_handle_performance", interleaved_handler)

    with pytest.raises(module.poe.BotError, match="request A failed"):
        bot.run()


def minimal_signal_daily(module, date="2026-06-18"):
    row = {
        "date": pd.Timestamp(date),
        "version": module.VERSION,
        "scenario": module.V11_SCENARIO,
        "position_before": "CASH",
        "position": "159985.SZ",
        "actual_position_before": "CASH",
        "actual_position_next": "159985.SZ",
        "trade_target": "159985.SZ",
        "trade_fraction": 1.0,
        "holding_fraction": 1.0,
        "fraction_before": 0.0,
        "buy_delta": 1.0,
        "sell_delta": 0.0,
        "best_candidate": "159985.SZ",
        "best_candidate_score": 1.0,
        "current_score": math.nan,
        "buffer_blocked": False,
        "nav": 1.0,
        "return": 0.0,
        "weight": 1.0,
        "target_vol_scale_effective": 1.0,
        "target_vol_scale_next": 1.0,
        "overheat_scale_effective": 1.0,
        "overheat_scale_next": 1.0,
        "final_exposure_after_overheat": 1.0,
        "exposure_effective": 0.0,
        "turnover": 1.0,
        "cost": 0.001,
        "overheat_on": False,
        "overheat_on_effective": False,
        "overheat_triggered": False,
        "overheat_recovered": False,
        "common_last_date": date,
        "realized_vol": 0.2,
        "base_nav": 1.0,
        "nav_before_overheat": 1.0,
        "overheat_bias": 0.0,
        "overheat_bias_mom": 0.0,
        "pending_entry_target": "",
        "pending_entry_days": 0,
        "fill_on_down_day": False,
        "staged_initial": False,
    }
    for code in module.ASSETS:
        price = 1.0
        row[f"raw_score_{code}"] = 1.0 if code == "159985.SZ" else -1.0
        row[f"score_{code}"] = row[f"raw_score_{code}"]
        row[f"r2_{code}"] = 0.5
        row[f"eligible_{code}"] = code == "159985.SZ"
        row[f"last_date_{code}"] = date
        row[f"quote_price_{code}"] = price
        row[f"quote_time_{code}"] = f"{date} 14:54:30"
        row[f"quote_source_{code}"] = "Eastmoney push2"
        row[f"source_execution_eligible_{code}"] = True
        row[f"quote_volume_{code}"] = 1000.0
        row[f"quote_amount_{code}"] = 1000.0
        row[f"quote_limit_down_{code}"] = 0.9
        row[f"quote_limit_up_{code}"] = 1.1
        row[f"signal_price_{code}"] = price
    return pd.DataFrame([row])


def test_v13_has_no_global_display_policy():
    module = load_bot_module()

    assert not hasattr(module, "FORMAL_CROSS_MARKET_MODEL_AVAILABLE")
    assert not hasattr(module, "V13_RESEARCH_ONLY_REASON")
    assert not hasattr(module, "_v13_policy_state")
    assert not hasattr(module, "_v13_policy_notice")


def test_v13_introduction_advertises_normal_display_queries(monkeypatch):
    import fastapi_poe

    captured = []
    monkeypatch.setattr(fastapi_poe, "update_settings", captured.append, raising=False)

    load_bot_module()

    assert len(captured) == 1
    introduction = captured[0].introduction_message
    assert "research-only" not in introduction
    assert "不可执行" not in introduction
    assert '发送 **"交易记录 过去两个月"** -> 调仓记录表 + 完整CSV' in introduction
    assert '发送 **"净值曲线 过去两年"** / **"收益曲线 今年"** -> 绩效表 + 净值曲线' in introduction


def test_v13_performance_reaches_provider_without_policy_only_refusal(monkeypatch):
    module = load_bot_module()
    provider_calls = []

    class ProviderReached(Exception):
        pass

    def provider_spy(*args, **kwargs):
        provider_calls.append((args, kwargs))
        raise ProviderReached

    monkeypatch.setattr(module, "_get_daily_for_today", provider_spy)

    with pytest.raises(ProviderReached):
        module.SubDMixedPoolV13Bot()._handle_performance("表现")

    assert len(provider_calls) == 1


def test_v13_signal_report_displays_normally_without_policy_banner(monkeypatch):
    module = load_bot_module()
    daily = minimal_signal_daily(module)
    monkeypatch.setattr(
        module,
        "_expected_cn_trading_days",
        lambda start, end: pd.DatetimeIndex(pd.to_datetime(["2026-06-18"])),
    )

    report = module.format_signal_report(
        daily,
        "unit-test",
        live=True,
        now=datetime(2026, 6, 18, 14, 55),
    )

    assert "research-only" not in report
    assert "不可执行" not in report.split("### 信号摘要", 1)[0]
    assert "## SubD混合池子 V1.3 实时操作信号" in report
    assert "动量排名" in report


def test_v13_signal_status_has_no_policy_only_metadata(monkeypatch):
    module = load_bot_module()
    daily = minimal_signal_daily(module)
    monkeypatch.setattr(
        module,
        "_expected_cn_trading_days",
        lambda start, end: pd.DatetimeIndex(pd.to_datetime(["2026-06-18"])),
    )

    execution = module.signal_data_status(
        daily,
        live=True,
        now=datetime(2026, 6, 18, 14, 55),
        purpose="execution",
    )
    assert execution["exchange_all_legs_can_submit"] is True
    assert execution["strategy_actionable_now"] is True
    assert execution["actionable_now"] is True
    assert execution["tradable"] is True
    assert "research_only" not in execution
    assert "research_only_reason" not in execution


def test_v13_parameter_and_introduction_surfaces_have_no_policy_warning(monkeypatch):
    module = load_bot_module()
    writes = []

    class FakeMessage:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def write(self, value):
            writes.append(str(value))

        def overwrite(self, value):
            writes.append(str(value))

    monkeypatch.setattr(module.poe, "start_message", lambda: FakeMessage())

    module.SubDMixedPoolV13Bot()._handle_params(live=False)
    surface_text = "".join(writes) + module._v13_introduction_message()
    assert "research-only" not in surface_text
    assert "不可执行" not in surface_text


def test_v13_live_build_fails_closed_when_mixed_pool_live_quotes_are_unavailable(monkeypatch):
    module = load_bot_module()
    prices = pd.DataFrame(
        {
            "QQQ": [100.0, 101.0],
            "GLD": [200.0, 201.0],
            "CN_CYB_399006": [3000.0, 3010.0],
            "KMLM": [25.0, 25.1],
            "159985.SZ": [1.0, 1.01],
        },
        index=pd.to_datetime(["2026-01-01", "2026-01-02"]),
    )
    sources = pd.DataFrame(
        [{"code": code, "source": "unit", "source_detail": "unit"} for code in module.ASSETS]
    )

    monkeypatch.setattr(module, "load_close", lambda config: (prices, sources))
    monkeypatch.setattr(
        module,
        "_load_live_quotes_for_prices",
        lambda codes, prices, now=None: (_ for _ in ()).throw(RuntimeError("unit live unavailable")),
    )

    with pytest.raises(Exception, match="unit live unavailable"):
        module._build_v11_daily(end_date=pd.Timestamp("2026-01-02"), data_state="live")


def test_v13_live_signal_handler_does_not_display_confirmed_fallback_when_proxy_live_quotes_unsupported(monkeypatch):
    module = load_bot_module()
    calls = []
    writes = []
    reports = []

    class FakeMessage:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def write(self, value):
            writes.append(str(value))

        def overwrite(self, value):
            writes.append(str(value))

    def fake_get_daily(force_refresh=False, data_state="confirmed"):
        calls.append((force_refresh, data_state))
        if data_state == "live":
            raise module.UnsupportedLiveQuoteSymbols({"QQQ"})
        return pd.DataFrame({"date": [pd.Timestamp("2026-01-02")]}), "confirmed source"

    def fake_report(daily, source_note, live=False, now=None):
        reports.append((daily, source_note, live, now))
        return "confirmed fallback report"

    monkeypatch.setattr(module.poe, "start_message", lambda: FakeMessage())
    monkeypatch.setattr(module, "_get_daily_for_today", fake_get_daily)
    monkeypatch.setattr(module, "format_signal_report", fake_report)

    module.SubDMixedPoolV13Bot()._handle_signal(live=True)

    assert calls == [(True, "live")]
    assert reports == []
    output = "\n".join(writes)
    assert "live quotes unavailable" in output
    assert "confirmed fallback report" not in output
    assert "using confirmed close signal" not in output


def test_v13_mixed_pool_live_quote_loader_fetches_yahoo_and_china_sources(monkeypatch):
    module = load_bot_module()
    now = datetime(2026, 6, 18, 14, 55, tzinfo=module.CN_TZ)
    quote_epoch = int(datetime(2026, 6, 18, 14, 54, 30, tzinfo=module.CN_TZ).timestamp())
    calls = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    yahoo_prices = {"QQQ": 501.25, "GLD": 235.75, "KMLM": 27.92}

    def yahoo_payload(ticker):
        price = yahoo_prices[ticker]
        return {
            "chart": {
                "result": [
                    {
                        "timestamp": [quote_epoch - 60, quote_epoch],
                        "meta": {"exchangeTimezoneName": "America/New_York"},
                        "indicators": {
                            "quote": [
                                {
                                    "close": [price - 0.1, price],
                                    "volume": [1000, 2000],
                                }
                            ]
                        },
                    }
                ],
                "error": None,
            }
        }

    eastmoney_payload = {
        "data": {
            "diff": [
                {
                    "f12": "399006",
                    "f14": "创业板指",
                    "f2": 3010.5,
                    "f5": 100,
                    "f6": 200000.0,
                    "f18": 3000.0,
                    "f124": quote_epoch,
                },
                {
                    "f12": "159985",
                    "f14": "豆粕ETF",
                    "f2": 2.18,
                    "f5": 200,
                    "f6": 436.0,
                    "f18": 2.15,
                    "f124": quote_epoch,
                },
            ]
        }
    }

    def fake_http_get(url, params=None, **kwargs):
        calls.append((url, params or {}))
        if "query1.finance.yahoo.com" in url:
            ticker = url.rsplit("/", 1)[-1]
            return FakeResponse(yahoo_payload(ticker))
        return FakeResponse(eastmoney_payload)

    monkeypatch.setattr(module, "_now_bj", lambda: now)
    monkeypatch.setattr(
        module,
        "EASTMONEY_LIVE_ENDPOINTS",
        (("https://unit.test/eastmoney", "Eastmoney push2", True),),
    )
    monkeypatch.setattr(module, "_http_get", fake_http_get)

    quotes = module.load_live_quotes(list(module.ASSETS), now=now)

    assert quotes["code"].tolist() == list(module.ASSETS)
    assert quotes.set_index("code").loc["QQQ", "price"] == pytest.approx(501.25)
    assert quotes.set_index("code").loc["CN_CYB_399006", "price"] == pytest.approx(3010.5)
    assert quotes.set_index("code").loc["159985.SZ", "price"] == pytest.approx(2.18)
    assert set(quotes.loc[quotes["code"].isin(["QQQ", "GLD", "KMLM"]), "source"]) == {
        "Yahoo Finance chart 1m"
    }
    assert "0.399006" in calls[-1][1]["secids"]
    assert "0.159985" in calls[-1][1]["secids"]


def test_v13_live_price_validation_skips_yahoo_prev_close_against_adjusted_history():
    module = load_bot_module()
    prices = pd.DataFrame(
        {
            "QQQ": [100.0],
            "GLD": [200.0],
            "CN_CYB_399006": [3000.0],
            "KMLM": [25.0],
            "159985.SZ": [2.15],
        },
        index=pd.to_datetime(["2026-06-17"]),
    )
    quotes = pd.DataFrame(
        [
            {
                "code": "QQQ",
                "price": 101.89,
                "quote_time": "2026-06-18 14:54:30+0800",
                "source": "Yahoo Finance chart 1m",
                "source_execution_eligible": False,
                "prev_close": 101.89,
                "limit_down": math.nan,
                "limit_up": math.nan,
                "volume": 1000.0,
                "amount": 101890.0,
            }
        ],
        columns=module.LIVE_QUOTE_COLUMNS,
    )

    module._validate_live_quote_prices_against_history(
        prices,
        quotes,
        pd.Timestamp("2026-06-18"),
    )


def test_v13_live_price_validation_allows_small_index_prev_close_rounding_diff():
    module = load_bot_module()
    prices = pd.DataFrame(
        {"CN_CYB_399006": [3911.90]},
        index=pd.to_datetime(["2026-07-07"]),
    )
    quotes = pd.DataFrame(
        [
            {
                "code": "CN_CYB_399006",
                "price": 3845.35,
                "quote_time": "2026-07-08 15:00:00+0800",
                "source": "Eastmoney push2",
                "source_execution_eligible": False,
                "prev_close": 3911.91,
                "limit_down": math.nan,
                "limit_up": math.nan,
                "volume": 1000.0,
                "amount": 3845350.0,
            }
        ],
        columns=module.LIVE_QUOTE_COLUMNS,
    )

    module._validate_live_quote_prices_against_history(
        prices,
        quotes,
        pd.Timestamp("2026-07-08"),
    )


def test_v13_proxy_assets_are_not_treated_as_a_share_etfs():
    module = load_bot_module()

    assert module._security_type_for_asset("159985.SZ") == "ETF"
    summary = module._live_price_limit_summary()
    assert "159985.SZ=10%" in summary
    assert "proxy/non-CN live execution unsupported=CN_CYB_399006, GLD, KMLM, QQQ" in summary
    for code in ["QQQ", "GLD", "KMLM", "CN_CYB_399006"]:
        assert module._security_type_for_asset(code) == "PROXY"
        assert math.isnan(module._live_price_limit_ratio(code))
        status = module._execution_session_status(
            datetime(2026, 7, 2, 14, 55, tzinfo=module.CN_TZ),
            is_trading_day=True,
            asset_code=code,
            security_type=module._security_type_for_asset(code),
        )
        assert status == "CLOSED"


def test_v13_cnfin_calendar_accepts_workday_holiday_required_start(monkeypatch, tmp_path):
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


def test_v13_cnfin_calendar_accepts_non_session_required_end(monkeypatch, tmp_path):
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


def test_v13_official_2026_calendar_covers_july_31_when_quote_calendar_lags(
    monkeypatch,
    tmp_path,
):
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


def test_v13_cnfin_calendar_loader_rejects_partial_calendar_after_provider_failure(monkeypatch):
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


def test_v13_cnfin_calendar_loader_accepts_explicit_empty_followup_page(monkeypatch):
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


def test_v13_cnfin_calendar_cache_preserves_queried_boundaries(monkeypatch, tmp_path):
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


@pytest.mark.parametrize("source", ["CNFin forged", None])
def test_v13_untrusted_calendar_cache_source_does_not_relax_boundaries(
    monkeypatch, tmp_path, source
):
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


def test_v13_price_forward_fill_flags_use_raw_unfilled_prices():
    module = load_bot_module()
    dates = pd.to_datetime(["2026-01-01", "2026-01-02"])
    raw = pd.DataFrame(
        {
            "QQQ": [100.0, math.nan],
            "GLD": [200.0, 201.0],
            "CN_CYB_399006": [3000.0, 3010.0],
            "KMLM": [25.0, 25.1],
            "159985.SZ": [1.0, 1.01],
        },
        index=dates,
    )
    aligned = raw.ffill()

    flags = module._price_forward_fill_flags(raw, aligned, list(module.ASSETS))

    assert bool(flags.loc[dates[1], "QQQ"]) is True
    assert bool(flags.loc[dates[1], "GLD"]) is False


def test_v13_build_passes_raw_unfilled_mask_into_curves(monkeypatch):
    module = load_bot_module()
    dates = pd.to_datetime(["2026-01-01", "2026-01-02"])
    prices = pd.DataFrame(1.0, index=dates, columns=list(module.ASSETS))
    raw_unfilled = prices.copy()
    raw_unfilled.loc[dates[-1], "QQQ"] = math.nan
    prices.attrs["raw_unfilled_prices"] = raw_unfilled
    sources = pd.DataFrame(
        [{"code": code, "source": "unit", "source_detail": "unit"} for code in module.ASSETS]
    )

    def fake_build_curves(input_prices, config, price_ffill_flags=None):
        assert price_ffill_flags is not None
        assert bool(price_ffill_flags.loc[dates[-1], "QQQ"]) is True
        assert bool(price_ffill_flags.loc[dates[-1], "GLD"]) is False
        return [
            pd.DataFrame(
                {"version": [module.VERSION], "scenario": [module.V11_SCENARIO]},
                index=pd.DatetimeIndex([dates[-1]], name="date"),
            )
        ]

    monkeypatch.setattr(module, "load_close", lambda config: (prices.copy(), sources.copy()))
    monkeypatch.setattr(module, "build_curves", fake_build_curves)

    daily, _ = module._build_v11_daily(end_date=dates[-1], data_state="confirmed")

    assert bool(daily.iloc[-1]["price_ffill_QQQ"]) is True


def _run_v13_stale_trade_case(monkeypatch, stale_asset, staged=False):
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
        source="proxy_mixed_v1_3",
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


def test_v13_stale_buy_leg_atomically_blocks_switch(monkeypatch):
    module = load_bot_module()
    new_asset = list(module.ASSETS)[1]
    _, curve, dates, old_asset, _ = _run_v13_stale_trade_case(monkeypatch, new_asset)
    row = curve.loc[dates[-1]]

    assert bool(row["trade_blocked_by_stale_price"]) is True
    assert row["blocked_trade_target"] == new_asset
    assert new_asset in row["stale_price_trade_assets"].split(",")
    assert row["position_before"] == old_asset
    assert row["position"] == old_asset
    assert pd.isna(row["trade_target"])
    assert row["turnover"] == pytest.approx(0.0)
    assert row["cost"] == pytest.approx(0.0)


def test_v13_stale_sell_leg_atomically_blocks_switch(monkeypatch):
    module = load_bot_module()
    old_asset = list(module.ASSETS)[0]
    _, curve, dates, _, new_asset = _run_v13_stale_trade_case(monkeypatch, old_asset)
    row = curve.loc[dates[-1]]

    assert bool(row["trade_blocked_by_stale_price"]) is True
    assert row["blocked_trade_target"] == new_asset
    assert old_asset in row["stale_price_trade_assets"].split(",")
    assert row["position"] == row["position_before"] == old_asset
    assert row["turnover"] == pytest.approx(0.0)
    assert row["cost"] == pytest.approx(0.0)


def test_v13_stale_staged_fill_restores_pending_state_and_counters(monkeypatch):
    module = load_bot_module()
    old_asset = list(module.ASSETS)[0]
    _, curve, dates, _, _ = _run_v13_stale_trade_case(monkeypatch, old_asset, staged=True)
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
def test_v13_explicit_ffill_mask_is_strictly_validated(bad_mask):
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
    config = module.RunConfig("proxy_mixed_v1_3", 0.001, dates[0], dates[-1], "unit", (), 80, 1.5)

    with pytest.raises((ValueError, RuntimeError), match="(?i)(mask|ffill)"):
        module.run_staged_entry(
            prices,
            config,
            module.EntryCase("full", "full_entry", 1.0),
            0.2,
            1.0,
            price_ffill_flags=flags,
        )


def test_v13_live_quote_is_added_to_raw_availability_before_ffill_flags():
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


def test_v13_build_curves_blocks_stale_nav_defense_sell_and_carries_actual_exposure(monkeypatch):
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
        "nav_defense_state",
        lambda *args: pd.DataFrame(
            {
                "nav_defense_base_dd": [0.0, -0.1, -0.1],
                "nav_defense_scale_effective": [1.0, 1.0, 0.5],
                "nav_defense_scale_next": [1.0, 0.5, 0.5],
                "nav_defense_on_effective": [False, False, True],
                "nav_defense_on_next": [False, True, True],
                "nav_defense_triggered": [False, True, False],
                "nav_defense_recovered": [False, False, False],
            },
            index=dates,
        ),
    )
    monkeypatch.setattr(module, "apply_overheat_overlay", lambda curve, *args, **kwargs: curve)
    monkeypatch.setattr(module, "build_overheat_features", lambda prices: {})
    config = module.RunConfig("proxy_mixed_v1_3", 0.001, dates[0], dates[-1], "unit", (), 80, 1.5)

    out = module.build_curves(prices, config, price_ffill_flags=flags)[0]

    for date in dates[1:]:
        assert bool(out.loc[date, "trade_blocked_by_stale_price"]) is True
        assert out.loc[date, "turnover"] == pytest.approx(0.0)
        assert out.loc[date, "cost"] == pytest.approx(0.0)
        assert out.loc[date, "final_exposure_after_overheat"] == pytest.approx(1.0)


def test_v13_build_curves_blocks_stale_overheat_sell_and_carries_actual_exposure(monkeypatch):
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
        module, "nav_defense_state",
        lambda *args: pd.DataFrame(
            {
                "nav_defense_base_dd": [0.0] * 3, "nav_defense_scale_effective": [1.0] * 3,
                "nav_defense_scale_next": [1.0] * 3, "nav_defense_on_effective": [False] * 3,
                "nav_defense_on_next": [False] * 3, "nav_defense_triggered": [False] * 3,
                "nav_defense_recovered": [False] * 3,
            }, index=dates,
        ),
    )
    features = {
        code: pd.DataFrame(
            {"bias": [0.0, 1.0, 1.0], "bias_mom": [0.0, 1.0, 1.0], "same_side": [False, True, True]},
            index=dates,
        ) for code in module.ASSETS
    }
    monkeypatch.setattr(module, "build_overheat_features", lambda prices: features)
    config = module.RunConfig("proxy_mixed_v1_3", 0.001, dates[0], dates[-1], "unit", (), 80, 1.5)

    out = module.build_curves(prices, config, price_ffill_flags=flags)[0]
    for date in dates[1:]:
        assert bool(out.loc[date, "trade_blocked_by_stale_price"]) is True
        assert out.loc[date, "turnover"] == pytest.approx(0.0)
        assert out.loc[date, "final_exposure_after_overheat"] == pytest.approx(
            out.loc[date, "drifted_exposure_before_trade"]
        )
        assert out.loc[date, "actual_position_next"] == asset


def test_v13_stale_zero_overheat_recovery_keeps_actual_full_position(monkeypatch):
    module = load_bot_module()
    dates = pd.bdate_range("2026-01-01", periods=4)
    asset = list(module.ASSETS)[0]
    prices = pd.DataFrame(100.0, index=dates, columns=list(module.ASSETS))
    flags = pd.DataFrame(False, index=dates, columns=list(module.ASSETS))
    flags.loc[dates[2], asset] = True
    initial = module.INITIAL_ENTRY_FRACTION
    base = pd.DataFrame(
        {
            "position_before": ["CASH", asset, asset, asset],
            "position": [asset, asset, asset, asset],
            "fraction_before": [0.0, initial, 1.0, 1.0],
            "holding_fraction": [initial, 1.0, 1.0, 1.0],
            "trade_target": [asset, asset, None, None],
            "trade_fraction": [initial, 1.0, 1.0, 1.0],
            "pending_entry_target": [asset, None, None, None],
            "pending_entry_since": [dates[0], None, None, None],
            "pending_entry_days": [0, 0, 0, 0],
            "staged_initial": [True, False, False, False],
            "fill_on_down_day": [False, True, False, False],
            "asset_return": [0.0, -0.01, 0.0, 0.0],
            "gross_return": [module.CASH_DAILY_RETURN, -0.01 * initial, 0.0, 0.0],
            "return": [module.CASH_DAILY_RETURN, -0.01 * initial, 0.0, 0.0],
            "nav": [1.0, 0.9975, 0.9975, 0.9975],
            "turnover": [initial, 1.0 - initial, 0.0, 0.0],
            "cost": [0.0, 0.0, 0.0, 0.0],
        }, index=dates,
    )
    monkeypatch.setattr(module, "run_staged_entry", lambda *args, **kwargs: base.copy())
    monkeypatch.setattr(
        module, "nav_defense_state",
        lambda *args: pd.DataFrame(
            {
                "nav_defense_base_dd": [0.0] * 4,
                "nav_defense_scale_effective": [1.0] * 4,
                "nav_defense_scale_next": [1.0] * 4,
                "nav_defense_on_effective": [False] * 4,
                "nav_defense_on_next": [False] * 4,
                "nav_defense_triggered": [False] * 4,
                "nav_defense_recovered": [False] * 4,
            }, index=dates,
        ),
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
    config = module.RunConfig("proxy_mixed_v1_3", 0.0, dates[0], dates[-1], "unit", (), 80, 1.5)

    out = module.build_curves(prices, config, price_ffill_flags=flags)[0]

    assert bool(out.loc[dates[2], "trade_blocked_by_stale_price"]) is True
    assert out.loc[dates[2], "final_exposure_after_overheat"] == pytest.approx(1.0)
    assert out.loc[dates[3], "final_exposure_after_overheat"] == pytest.approx(1.0)
    assert bool(out.loc[dates[3], "actual_staged_initial"]) is False
    assert out.loc[dates[3], "actual_position_next"] == asset


def test_v13_stale_overheat_reentry_waits_for_first_fresh_initial_fill(monkeypatch):
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
            "gross_return": [module.CASH_DAILY_RETURN, -0.01 * initial, 0.0, 0.0, -0.01],
            "return": [module.CASH_DAILY_RETURN, -0.01 * initial, 0.0, 0.0, -0.01],
            "nav": [1.0, 0.9975, 0.9975, 0.9975, 0.987525],
            "turnover": [initial, 1.0 - initial, 0.0, 0.0, 0.0],
            "cost": [0.0] * 5,
        }, index=dates,
    )
    monkeypatch.setattr(module, "run_staged_entry", lambda *args, **kwargs: base.copy())
    monkeypatch.setattr(
        module, "nav_defense_state",
        lambda *args: pd.DataFrame(
            {
                "nav_defense_base_dd": [0.0] * 5,
                "nav_defense_scale_effective": [1.0] * 5,
                "nav_defense_scale_next": [1.0] * 5,
                "nav_defense_on_effective": [False] * 5,
                "nav_defense_on_next": [False] * 5,
                "nav_defense_triggered": [False] * 5,
                "nav_defense_recovered": [False] * 5,
            }, index=dates,
        ),
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
    config = module.RunConfig("proxy_mixed_v1_3", 0.0, dates[0], dates[-1], "unit", (), 80, 1.5)

    out = module.build_curves(prices, config, price_ffill_flags=flags)[0]

    assert out.loc[dates[2], "actual_position_next"] == "CASH"
    assert bool(out.loc[dates[3], "trade_blocked_by_stale_price"]) is True
    assert out.loc[dates[3], "actual_position_next"] == "CASH"
    assert pd.isna(out.loc[dates[3], "actual_pending_target"])
    assert bool(out.loc[dates[3], "actual_staged_initial"]) is False
    assert out.loc[dates[4], "final_exposure_after_overheat"] == pytest.approx(initial)
    assert bool(out.loc[dates[4], "actual_staged_initial"]) is True


def test_v13_recompute_prices_stale_carried_asset_with_its_own_return_and_fails_closed_without_it():
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


def test_v13_overlay_stale_audit_merges_with_existing_base_block():
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


def test_v13_raw_sina_fallback_is_not_allowed_in_formal_load_close(monkeypatch):
    module = load_bot_module()
    dates = pd.to_datetime(["2026-01-01", "2026-01-02"])

    monkeypatch.setattr(module, "_expected_cn_trading_days", lambda start, end: pd.DatetimeIndex(dates))
    monkeypatch.setattr(
        module,
        "_fetch_yahoo_adj_close",
        lambda ticker, start, end: pd.Series([1.0, 1.1], index=dates, name=ticker),
    )
    monkeypatch.setattr(
        module,
        "_fetch_eastmoney_index_close",
        lambda secid, beg, end, name: pd.Series([1.0, 1.1], index=dates, name=name),
    )
    monkeypatch.setattr(
        module,
        "_load_public_close_with_per_code_fallback",
        lambda codes, end_date: (_ for _ in ()).throw(RuntimeError("qfq unavailable")),
    )
    monkeypatch.setattr(
        module,
        "_load_akshare_sina_raw_one_close",
        lambda code, end_date: pd.Series([1.0, 1.1], index=dates, name=code),
    )

    with pytest.raises(RuntimeError, match="qfq unavailable"):
        module.load_close(module._build_config(end_date=pd.Timestamp("2026-01-02")))


@pytest.mark.parametrize(
    ("code", "symbol"),
    [
        ("513030.SH", "sh513030"),
        ("513520.SH", "sh513520"),
        ("159985.SZ", "sz159985"),
    ],
)
def test_v13_tencent_qfq_loader_accepts_verified_day_key(monkeypatch, code, symbol):
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


def test_v13_tencent_qfq_loader_rejects_day_key_for_non_allowlisted_code(monkeypatch):
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


def test_v13_tencent_verified_day_detail_reaches_source_metadata(monkeypatch):
    module = load_bot_module()
    monkeypatch.setitem(module.ASSETS, "513030.SH", "GERMANY_ETF")

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


def test_v13_tencent_qfq_loader_rejects_day_only_page_after_qfq_history(monkeypatch):
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


def test_v13_tencent_qfq_loader_rejects_provider_failure_after_qfq_history(monkeypatch):
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


def test_v13_yahoo_adjusted_close_rejects_quote_close_fallback(monkeypatch):
    module = load_bot_module()

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "chart": {
                    "result": [
                        {
                            "timestamp": [1609459200, 1609545600],
                            "indicators": {"quote": [{"close": [100.0, 50.0]}]},
                        }
                    ]
                }
            }

    monkeypatch.setattr(module, "_http_get", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="adjusted close"):
        module._fetch_yahoo_adj_close(
            "QQQ",
            pd.Timestamp("2021-01-01"),
            pd.Timestamp("2021-01-02"),
        )


def test_v13_cyb_index_uses_cnfin_when_eastmoney_and_akshare_fail(monkeypatch):
    module = load_bot_module()
    monkeypatch.setattr(module, "_HAS_AKSHARE", False)
    monkeypatch.setattr(
        module,
        "_http_get",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("eastmoney down")),
    )

    def cnfin_fallback(secid, beg, end, name):
        idx = pd.to_datetime(["2026-01-01", "2026-01-02"])
        series = pd.Series([4000.0, 4017.27], index=idx, name=name)
        series.attrs["source_name"] = "CNFin quote kline"
        series.attrs["source_detail"] = "prod_code=399006.SZ; no pre-2010 backfill"
        return series

    monkeypatch.setattr(module, "_fetch_cnfin_index_close_fallback", cnfin_fallback, raising=False)

    out = module._fetch_eastmoney_index_close(
        "0.399006",
        "20260101",
        "20260102",
        "CN_CYB_399006",
    )

    assert out.loc[pd.Timestamp("2026-01-02")] == 4017.27
    assert out.attrs["source_name"] == "CNFin quote kline"


def test_v13_load_close_fails_closed_before_fetch_when_cn_calendar_unavailable(monkeypatch):
    module = load_bot_module()

    monkeypatch.setattr(module, "_expected_cn_trading_days", lambda start, end: None)
    monkeypatch.setattr(
        module,
        "_fetch_yahoo_adj_close",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("provider fetch must not run")),
    )
    monkeypatch.setattr(
        module,
        "_fetch_eastmoney_index_close",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("provider fetch must not run")),
    )
    monkeypatch.setattr(
        module,
        "_load_public_close_with_per_code_fallback",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("provider fetch must not run")),
    )

    with pytest.raises(RuntimeError, match="trading calendar|交易日历"):
        module.load_close(module._build_config(end_date=pd.Timestamp("2026-01-02")))


def test_v13_default_performance_windows_use_trading_day_rows():
    module = load_bot_module()
    dates = pd.bdate_range("2011-01-03", periods=3000)
    daily = pd.DataFrame({"date": dates})

    ranges = module.resolve_performance_ranges_for_daily(
        "",
        daily,
        latest_date=dates[-1],
        earliest_date=dates[0],
    )
    starts = {label: start for label, start, _end in ranges}

    assert starts["full_sample"] == dates[0]
    assert starts["10Y"] == dates[-10 * module.TRADING_DAYS]
    assert starts["5Y"] == dates[-5 * module.TRADING_DAYS]
    assert starts["3Y"] == dates[-3 * module.TRADING_DAYS]
    assert starts["1Y"] == dates[-1 * module.TRADING_DAYS]
    assert starts["10Y"] != dates[-1] - pd.DateOffset(years=10)
