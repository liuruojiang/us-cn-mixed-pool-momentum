import importlib.util
import math
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
V11_PATH = ROOT / "poe_subd_six_etf_v1_1_bot.py"
V13_PATH = ROOT / "poe_subd_mixed_pool_v1_3_bot.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=[(V11_PATH, "review_v11"), (V13_PATH, "review_v13")])
def bot_module(request):
    path, name = request.param
    return load_module(path, name)


def yearly_daily() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-12-31", "2026-01-02"]),
            "nav": [1.0, 1.1],
            "turnover": [0.0, 0.0],
            "exposure_effective": [1.0, 1.0],
        }
    )


def test_v13_eval_range_label_matches_eval_start():
    module = load_module(V13_PATH, "review_v13_label")
    labels = [item[0] for item in module._default_performance_ranges(pd.Timestamp("2026-08-07"))]
    assert f"from_{module.EVAL_START.year}" in labels
    assert "from_2020" not in labels


def test_v13_short_mandatory_window_reports_insufficient_rows():
    module = load_module(V13_PATH, "review_v13_short_window")
    dates = pd.bdate_range("2026-01-01", periods=100)
    daily = pd.DataFrame({"date": dates})
    start = dict(
        (label, value)
        for label, value, _ in module._default_performance_ranges_for_daily(
            daily, dates[-1], dates[0]
        )
    )["1Y"]
    reason = module._mandatory_window_na_reason(
        "1Y", start, dates[0], available_rows=len(dates)
    )
    assert reason == "insufficient history: 100 rows < 252 trading days"


def test_v13_mandatory_windows_keep_252_row_convention():
    module = load_module(V13_PATH, "review_v13_window_convention")
    dates = pd.bdate_range("2015-01-01", periods=3000)
    daily = pd.DataFrame({"date": dates})
    ranges = {
        label: (start, end)
        for label, start, end in module._default_performance_ranges_for_daily(
            daily, dates[-1], dates[0]
        )
    }
    assert dates.get_loc(ranges["1Y"][1]) - dates.get_loc(ranges["1Y"][0]) + 1 == 252
    assert dates.get_loc(ranges["10Y"][1]) - dates.get_loc(ranges["10Y"][0]) + 1 == 2520


def test_yearly_returns_keep_first_session_after_year_boundary(bot_module):
    rows = bot_module.calc_yearly_performance(
        yearly_daily(), pd.Timestamp("2025-12-31"), pd.Timestamp("2026-01-02")
    )
    assert rows[1]["return"] == pytest.approx(0.10)


def test_standalone_iso_date_is_not_parsed_as_month_range(bot_module):
    start, end = bot_module.parse_date_range("2026-08-05的表现")
    assert start == pd.Timestamp("2026-08-05")
    assert end == pd.Timestamp("2026-08-05")


def _capture_params(module, monkeypatch) -> str:
    writes: list[str] = []

    class Message:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def write(self, value):
            writes.append(value)

        def overwrite(self, *_):
            return None

    monkeypatch.setattr(module.poe, "start_message", lambda: Message())
    bot_class = getattr(module, "SubDSixEtfV11Bot", None) or module.SubDMixedPoolV13Bot
    bot_class()._handle_params(live=False)
    return "".join(writes)


def test_v11_params_describe_cross_validated_raw_fallback(monkeypatch):
    module = load_module(V11_PATH, "review_v11_params")
    text = _capture_params(module, monkeypatch)
    assert "Sina + CNFin交叉验证raw fallback" in text
    assert "SELL腿" in text and "可卖数量" in text


def test_v13_params_and_snapshot_disclose_actual_rules(monkeypatch):
    module = load_module(V13_PATH, "review_v13_params_text")
    text = _capture_params(module, monkeypatch)
    assert str(module.LOOKBACK) in module._score_rule_text()
    assert "R²过滤关闭" in module._score_rule_text()
    assert "SELL腿" in text and "可卖数量" in text
    assert "跨市场" in module._mixed_market_timing_notice(live=False)
    assert "盘前/隔夜" in module._mixed_market_timing_notice(live=True)


@pytest.mark.parametrize("path", [V11_PATH, V13_PATH])
def test_introduction_describes_confirmed_cache(path):
    text = path.read_text(encoding="utf-8")
    assert "5分钟缓存" in text
    assert "查询时刷新" not in text


def test_v13_unsupported_live_symbols_use_typed_error():
    module = load_module(V13_PATH, "review_v13_unsupported")
    with pytest.raises(module.UnsupportedLiveQuoteSymbols) as caught:
        module.load_live_quotes(
            ["NOT_SUPPORTED"], now=datetime(2026, 8, 5, 14, 55)
        )
    assert caught.value.codes == ("NOT_SUPPORTED",)
    assert module._is_proxy_live_quote_unsupported_error(caught.value)


def test_v13_non_cn_price_limit_bounds_are_nan():
    module = load_module(V13_PATH, "review_v13_non_cn_bounds")
    lower, upper = module._price_limit_bounds_from_prev_close("QQQ", 100.0)
    assert math.isnan(lower) and math.isnan(upper)


@pytest.mark.parametrize(
    "args",
    [(True, 20, 1.0), (0.2, True, 1.0), (0.2, 20, True)],
)
def test_v13_target_vol_helpers_reject_bool_inputs(args):
    module = load_module(V13_PATH, "review_v13_target_vol")
    curve = pd.DataFrame({"return": [0.0] * 30})
    with pytest.raises(ValueError):
        module._compute_target_vol_scales(curve, *args)


def test_v13_qfq_loaders_use_strategy_start(monkeypatch):
    module = load_module(V13_PATH, "review_v13_qfq_start")
    akshare_calls = []
    http_calls = []
    monkeypatch.setattr(module, "_HAS_AKSHARE", True)
    monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    monkeypatch.setattr(
        module.ak,
        "fund_etf_hist_em",
        lambda **kwargs: akshare_calls.append(kwargs) or pd.DataFrame(),
    )
    with pytest.raises(RuntimeError):
        module._load_akshare_eastmoney_qfq_one_close(
            "159985.SZ", pd.Timestamp("2026-01-02")
        )
    assert akshare_calls[0]["start_date"] == module.START_DATE.strftime("%Y%m%d")

    response = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"data": {"klines": []}},
    )

    def fake_get(*args, **kwargs):
        http_calls.append(kwargs["params"])
        return response

    monkeypatch.setattr(module, "_http_get", fake_get)
    with pytest.raises(RuntimeError):
        module._load_eastmoney_one_close(
            "159985.SZ", pd.Timestamp("2026-01-02")
        )
    assert http_calls[0]["beg"] == module.START_DATE.strftime("%Y%m%d")


def test_cross_validated_raw_warns_before_sina_cap(bot_module, monkeypatch):
    listing_date = bot_module.CROSS_VALIDATED_RAW_CODES["159985.SZ"]
    index = pd.bdate_range(
        listing_date, periods=bot_module.SINA_DAILY_KLINE_WARN_ROWS
    )
    series = pd.Series(1.0, index=index, name="159985.SZ")
    monkeypatch.setattr(
        bot_module, "_load_sina_raw_one_close", lambda *_: series.copy()
    )
    monkeypatch.setattr(
        bot_module, "_load_cnfin_raw_one_close", lambda *_: series.copy()
    )
    monkeypatch.setattr(
        bot_module, "_validate_adjusted_close_continuity", lambda *_: None
    )
    out = bot_module._load_cross_validated_raw_one_close(
        "159985.SZ", index[-1]
    )
    assert "Sina history cap warning" in out.attrs["source_detail"]


def test_tencent_schema_failure_does_not_retry(bot_module, monkeypatch):
    calls = []
    symbol = bot_module._tencent_fq_symbol("159941.SZ")
    response = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"data": {symbol: {"day": []}}},
    )
    monkeypatch.setattr(bot_module.time, "sleep", lambda *_: None)
    monkeypatch.setattr(
        bot_module,
        "_http_get",
        lambda *args, **kwargs: calls.append(1) or response,
    )
    with pytest.raises(RuntimeError, match="missing qfqday"):
        bot_module._load_tencent_qfq_one_close(
            "159941.SZ", pd.Timestamp("2026-01-02")
        )
    assert len(calls) == 1


@pytest.mark.parametrize("path", [V11_PATH, V13_PATH])
def test_calendar_failure_reason_is_request_local(path):
    module = load_module(path, f"review_calendar_context_{path.stem}")
    module._set_calendar_failure("request-a")
    with ThreadPoolExecutor(max_workers=1) as pool:
        other_request_reason = pool.submit(module._calendar_failure_reason).result()
    assert other_request_reason == ""
    assert module._calendar_failure_reason() == "request-a"


@pytest.mark.parametrize("path", [V11_PATH, V13_PATH])
def test_calendar_cache_path_is_namespaced_by_strategy_start(path):
    module = load_module(path, f"review_calendar_path_{path.stem}")
    assert module.START_DATE.strftime("%Y%m%d") in module.TRADING_CALENDAR_CACHE_PATH.name


def test_v13_yahoo_snapshot_is_reused_across_eastmoney_retries(monkeypatch):
    module = load_module(V13_PATH, "review_v13_yahoo_reuse")
    yahoo_calls = []
    monkeypatch.setattr(
        module,
        "_load_yahoo_live_quotes",
        lambda *args, **kwargs: yahoo_calls.append(1) or pd.DataFrame(),
    )
    monkeypatch.setattr(
        module,
        "_fetch_eastmoney_live_quotes_from_endpoint",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("eastmoney down")),
    )
    monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    with pytest.raises(RuntimeError, match="unavailable"):
        module.load_live_quotes(
            ["QQQ", "159915.SZ"], now=datetime(2026, 8, 5, 14, 55)
        )
    assert len(yahoo_calls) == 1


@pytest.mark.parametrize("path", [V11_PATH, V13_PATH])
def test_daily_cache_build_is_single_flight(path, monkeypatch):
    module = load_module(path, f"review_daily_singleflight_{path.stem}")
    calls = []

    def fake_build(*args, **kwargs):
        calls.append(1)
        time.sleep(0.05)
        return pd.DataFrame({"date": [pd.Timestamp("2026-08-07")]}), "test"

    monkeypatch.setattr(module, "_call_build_v11_daily", fake_build)
    monkeypatch.setattr(module, "_now_bj", lambda: datetime(2026, 8, 8, 10, 0))
    module._cached_daily.cache_clear()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(module._cached_daily, "2026-08-07") for _ in range(2)]
        [future.result() for future in futures]
    assert len(calls) == 1


@pytest.mark.parametrize("path", [V11_PATH, V13_PATH])
def test_live_price_quality_rejection_backs_off_before_retry(path, monkeypatch):
    module = load_module(path, f"review_live_backoff_{path.stem}")
    sleeps = []
    candidate = pd.DataFrame(
        {
            "code": ["159915.SZ"],
            "price": [1.0],
            "prev_close": [1.0],
            "quote_time": ["2026-08-05 14:55:00"],
            "source": ["test"],
            "source_execution_eligible": [True],
        }
    )
    monkeypatch.setattr(module, "EASTMONEY_LIVE_ENDPOINTS", (("u", "s", True),))
    monkeypatch.setattr(module.time, "sleep", lambda seconds: sleeps.append(seconds))
    monkeypatch.setattr(
        module,
        "_validate_live_quote_prices_against_history",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            module.IncompleteLiveSnapshot("bad price")
        ),
    )
    if path == V11_PATH:
        response = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"data": {"diff": [{}]}},
        )
        monkeypatch.setattr(module, "_http_get", lambda *args, **kwargs: response)
        monkeypatch.setattr(
            module, "_normalize_live_quote_rows", lambda *args, **kwargs: candidate.copy()
        )
    else:
        monkeypatch.setattr(
            module,
            "_fetch_eastmoney_live_quotes_from_endpoint",
            lambda *args, **kwargs: candidate.copy(),
        )
        monkeypatch.setattr(
            module, "_normalize_live_quote_frame", lambda frame, *args, **kwargs: frame
        )
    with pytest.raises(RuntimeError, match="unavailable"):
        module.load_live_quotes(
            ["159915.SZ"],
            now=datetime(2026, 8, 5, 14, 55),
            reference_prices=pd.DataFrame({"159915.SZ": [1.0]}),
        )
    assert sleeps == [0.5]


@pytest.mark.parametrize("path", [V11_PATH, V13_PATH])
def test_execution_legs_select_latest_date_not_physical_last_row(path, monkeypatch):
    module = load_module(path, f"review_execution_sort_{path.stem}")
    daily = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-08-07", "2026-08-06"]),
            "sell_delta": [0.5, 0.0],
            "buy_delta": [0.0, 0.5],
            "actual_position_before": ["159915.SZ", "CASH"],
            "actual_position_next": ["CASH", "159915.SZ"],
        }
    )
    monkeypatch.setattr(
        module,
        "_execution_leg_status",
        lambda side, code, *args, **kwargs: {"side": side, "code": code},
    )
    legs = module._execution_legs_status(
        daily,
        datetime(2026, 8, 7, 14, 55),
        is_trading_day=True,
        signal_price_is_available=True,
        execution_enabled=True,
    )
    assert legs == [{"side": "SELL", "code": "159915.SZ"}]


@pytest.mark.parametrize("path", [V11_PATH, V13_PATH])
def test_build_config_defaults_to_beijing_today(path, monkeypatch):
    module = load_module(path, f"review_config_bj_{path.stem}")
    expected = pd.Timestamp("1999-12-31")
    monkeypatch.setattr(module, "_bj_today_naive", lambda: expected)
    assert module._build_config().end_date == expected


@pytest.mark.parametrize("path", [V11_PATH, V13_PATH])
def test_attach_live_metadata_parses_daily_dates_once(path, monkeypatch):
    module = load_module(path, f"review_metadata_parse_{path.stem}")
    real_to_datetime = module.pd.to_datetime
    calls = []

    def counted_to_datetime(*args, **kwargs):
        calls.append(1)
        return real_to_datetime(*args, **kwargs)

    monkeypatch.setattr(module.pd, "to_datetime", counted_to_datetime)
    daily = pd.DataFrame({"date": ["2026-08-07"]})
    metadata = {
        code: {"quote_date": pd.Timestamp("2026-08-07"), "quote_price": 1.0}
        for code in ("159915.SZ", "159941.SZ")
    }
    module._attach_live_quote_metadata(daily, metadata)
    assert len(calls) == 1


def _scalar_bias_momentum(module, close_series):
    prices = close_series.to_numpy(dtype=float)
    result = np.full(len(prices), np.nan)
    ma = close_series.rolling(module.CN_BIAS_N).mean().to_numpy()
    first_valid = module.CN_BIAS_N + module.CN_MOM_DAY - 2
    x = np.arange(module.CN_MOM_DAY, dtype=float)
    for end in range(first_valid, len(prices)):
        start = end - module.CN_MOM_DAY + 1
        window_prices = prices[start : end + 1]
        window_ma = ma[start : end + 1]
        if (
            not np.isfinite(window_prices).all()
            or not np.isfinite(window_ma).all()
            or (window_ma < 1e-10).any()
        ):
            continue
        bias = window_prices / window_ma
        if bias[0] < 1e-10:
            continue
        result[end] = np.polyfit(x, bias / bias[0], 1)[0] * 10000
    return pd.Series(result, index=close_series.index)


@pytest.mark.parametrize("path", [V11_PATH, V13_PATH])
@pytest.mark.parametrize("case", ["seeded", "nan_zero", "short"])
def test_bias_momentum_matches_scalar_oracle(path, case):
    module = load_module(path, f"review_bias_parity_{path.stem}_{case}")
    rng = np.random.default_rng(20260808)
    if case == "short":
        values = 100 * np.cumprod(1 + rng.normal(0, 0.01, 50))
    else:
        values = 100 * np.cumprod(1 + rng.normal(0, 0.01, 1200))
        if case == "nan_zero":
            values[250] = np.nan
            values[600:665] = 0.0
    series = pd.Series(values, index=pd.bdate_range("2020-01-01", periods=len(values)))
    expected = _scalar_bias_momentum(module, series)
    actual = module.calc_bias_momentum(series)
    np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=1e-10, equal_nan=True)


@pytest.mark.parametrize("path", [V11_PATH, V13_PATH])
def test_bias_momentum_does_not_call_polyfit_per_window(path, monkeypatch):
    module = load_module(path, f"review_bias_vectorized_{path.stem}")
    series = pd.Series(np.linspace(90.0, 110.0, 500))
    monkeypatch.setattr(
        module.np,
        "polyfit",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("scalar loop")),
    )
    result = module.calc_bias_momentum(series)
    assert result.notna().any()
