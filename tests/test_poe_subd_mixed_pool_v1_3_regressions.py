import importlib.util
import math
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


def test_v13_live_signal_handler_falls_back_to_confirmed_when_proxy_live_quotes_unsupported(monkeypatch):
    module = load_bot_module()
    calls = []
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

    def fake_get_daily(force_refresh=False, data_state="confirmed"):
        calls.append((force_refresh, data_state))
        if data_state == "live":
            raise module.poe.BotError(
                "live quotes unavailable: live quotes unsupported for proxy/non-CN symbols: QQQ"
            )
        return pd.DataFrame({"date": [pd.Timestamp("2026-01-02")]}), "confirmed source"

    def fake_report(daily, source_note, live=False, now=None):
        assert live is False
        assert "confirmed source" in source_note
        assert "live quotes unavailable" in source_note
        return "confirmed fallback report"

    monkeypatch.setattr(module.poe, "start_message", lambda: FakeMessage())
    monkeypatch.setattr(module, "_get_daily_for_today", fake_get_daily)
    monkeypatch.setattr(module, "format_signal_report", fake_report)

    module.SubDMixedPoolV13Bot()._handle_signal(live=True)

    assert calls == [(True, "live"), (False, "confirmed")]
    assert any("confirmed fallback report" in item for item in writes)


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


def test_v13_load_close_falls_back_to_bdays_when_cn_calendar_unavailable(monkeypatch):
    module = load_bot_module()
    dates = pd.to_datetime(["2026-01-01", "2026-01-02"])

    monkeypatch.setattr(module, "_expected_cn_trading_days", lambda start, end: None)
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
        lambda codes, end_date: (
            pd.DataFrame({codes[0]: [1.0, 1.1]}, index=dates),
            pd.DataFrame(
                [
                    {
                        "code": codes[0],
                        "name": module.ASSETS[codes[0]],
                        "source": "unit qfq",
                        "adjustment": module.ADJUSTMENT_QFQ,
                        "source_detail": module.SOURCE_DETAIL_TENCENT_QFQ,
                        "first_date": "2026-01-01",
                        "last_date": "2026-01-02",
                        "first_used": "2026-01-01",
                        "rows": 2,
                    }
                ]
            ),
        ),
    )

    prices, sources = module.load_close(module._build_config(end_date=pd.Timestamp("2026-01-02")))

    assert prices.index.tolist() == list(pd.bdate_range("2026-01-01", "2026-01-02"))
    assert prices.columns.tolist() == list(module.ASSETS)
    assert not sources.empty


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
