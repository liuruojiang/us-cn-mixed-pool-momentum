"""Six-ETF naive V1.3: real frozen-panel parity and local Poe-runtime contracts."""
import hashlib
import importlib.util
import json
import os
import runpy
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
BOT_PATH = ROOT / "poe_subd_six_etf_v1_3_bot.py"
ARTIFACTS = ROOT / "outputs/subd_six_etf_v1_3_acceptance_20260904"
ACCEPTED = ROOT / "quant_comparison_runs/20260904_subd_selected_score_max_5p5"


@pytest.fixture(scope="module")
def bot():
    spec = importlib.util.spec_from_file_location("six_etf_naive_v13_test", BOT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def real_run(bot):
    meta = json.loads((ACCEPTED / "metadata.json").read_text(encoding="utf-8"))
    # Metadata preserves the historical host path; replay uses this checkout's input.
    path = ROOT / "quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/price_snapshot_qfq.csv.gz"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == meta["data"]["sha256"]
    prices = pd.read_csv(path, parse_dates=["date"]).set_index("date")
    saved = pd.read_csv(ACCEPTED / "cap_5p5_daily.csv.gz", parse_dates=["date"]).set_index("date")
    flags = saved[[f"price_ffill_{code}" for code in bot.ASSETS]].copy()
    flags.columns = list(bot.ASSETS)
    flags = flags.astype(bool)
    curve = bot.build_curves(prices, bot._build_config(prices.index[-1]), flags)[0]
    daily = bot._normalize_daily(curve)
    daily = bot._attach_signal_prices(daily, prices)
    daily = bot._attach_price_fill_metadata(daily, flags)
    last_dates = {code: prices[code].last_valid_index() for code in bot.ASSETS}
    now = datetime(2026, 9, 3, 10, 0, tzinfo=bot.CN_TZ)
    daily = bot._attach_confirmed_final_close_metadata(daily, last_dates, now=now)
    daily["common_last_date"] = "2026-09-02"
    for code, date in last_dates.items():
        daily[f"last_date_{code}"] = str(date.date())
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    curve.to_csv(ARTIFACTS / "daily.csv.gz", index_label="date")
    return prices, flags, saved, curve, daily


def test_frozen_curve_and_all_five_windows_match_selected(bot, real_run):
    prices, flags, saved, curve, daily = real_run
    assert curve.index.equals(saved.index)
    differences = {}
    for col in ["nav", "return", "turnover", "cost", "fraction_before", "holding_fraction"]:
        differences[col] = float(np.max(np.abs(curve[col] - saved[col])))
        np.testing.assert_allclose(curve[col], saved[col], rtol=0, atol=1e-10 if col == "nav" else 1e-12)
    assert curve.position.equals(saved.position)
    assert curve.position_before.equals(saved.position_before)
    expected = pd.read_csv(ACCEPTED / "metrics.csv").query("scenario == 'cap_5p5'")
    rows = []
    for label, start, end in bot._default_performance_ranges_for_daily(daily, prices.index[-1], prices.index[0])[:5]:
        metrics = bot.calc_performance(daily, start, end)
        metrics["window"] = "Full" if label == "full_sample" else label
        old = expected[expected.window == metrics["window"]].iloc[0]
        assert metrics["annual"] == pytest.approx(old.cagr, abs=1e-12)
        assert metrics["maxdd"] == pytest.approx(old.maxdd, abs=1e-12)
        metrics["ann_delta_pp"] = 100 * (metrics["annual"] - old.cagr)
        metrics["mdd_improvement_pp"] = 100 * (metrics["maxdd"] - old.maxdd)
        rows.append(metrics)
    pd.DataFrame(rows).to_csv(ARTIFACTS / "metrics.csv", index=False)
    (ARTIFACTS / "parity.json").write_text(json.dumps({"passed": True, "max_abs_diff": differences, "data": str(prices.index[0]), "end": str(prices.index[-1]), "rows": len(prices), "bot_sha256": hashlib.sha256(BOT_PATH.read_bytes()).hexdigest()}, indent=2), encoding="utf-8")


def test_trade_legs_cash_and_disabled_overlays(bot, real_run):
    _, _, _, curve, daily = real_run
    assert bot.VERSION == "1.3"
    assert (bot.SCORE_MIN, bot.SCORE_MAX, bot.R2_THRESHOLD, bot.LOOKBACK) == (.5, 5.5, .25, 25)
    assert bot.TARGET_VOL is None
    assert not bot.TARGET_VOL_ENABLED and not bot.OVERHEAT_ENABLED and not bot.STAGED_ENTRY_ENABLED
    assert bot.INITIAL_ENTRY_FRACTION == bot.DEFAULT_MAX_LEV == bot.SWITCH_BUFFER == 1
    assert set(curve.holding_fraction) <= {0, 1}
    assert curve.pending_entry_target.isna().all()
    assert not curve.staged_initial.any() and not curve.fill_on_down_day.any()
    assert not curve.overheat_on.any()
    assert (curve.weight == 1).all()
    np.testing.assert_allclose(curve.buy_delta + curve.sell_delta, curve.turnover)
    np.testing.assert_allclose(curve.cost, curve.turnover * .001)
    cash = curve.position_before.eq("CASH") & curve.turnover.eq(0)
    assert (curve.loc[cash, "return"] == 0).all()
    switch = curve.position_before.ne("CASH") & curve.position.ne("CASH") & curve.position_before.ne(curve.position)
    assert switch.any()
    assert (curve.loc[switch, "buy_delta"] == 1).all()
    assert (curve.loc[switch, "sell_delta"] == 1).all()
    for _, row in daily.loc[switch.to_numpy()].head(5).iterrows():
        sig = bot.latest_signal(pd.DataFrame([row]))
        assert sig["buy_delta"] == sig["sell_delta"] == 1
        text = bot._signal_action_text(sig)
        assert "买" in text and "卖" in text


@pytest.mark.parametrize("score,r2,eligible", [(.5,.25,False),(.500001,.25,True),(5.499999,.25,True),(5.5,.25,False),(1,.249999,False),(1,.25,True),(np.nan,.5,False),(1,np.nan,False)])
def test_exact_score_and_r2_boundaries(bot, monkeypatch, score, r2, eligible):
    prices = pd.DataFrame(1., index=pd.bdate_range("2026-01-01", periods=25), columns=bot.ASSETS)
    monkeypatch.setattr(bot, "weighted_slope_score_and_r2", lambda window: (score, r2))
    scores, _, _ = bot.calc_scores(prices, 24, bot.R2_THRESHOLD)
    assert bool(scores) == eligible
    assert (bot._momentum_status(score, r2) == "入选") == eligible


def test_adapter_never_calls_disabled_layers(bot, real_run, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("disabled overlay called")
    for name in ["apply_target_vol_overlay", "apply_overheat_overlay", "build_overheat_features", "_recompute_final_exposure_nav"]:
        monkeypatch.setattr(bot, name, forbidden)
    prices, flags, *_ = real_run
    result = bot.build_curves(prices.iloc[:30], bot._build_config(prices.index[29]), flags.iloc[:30])[0]
    assert len(result) == 30


class CapturePoe:
    def __init__(self, query):
        self.query = SimpleNamespace(text=query)
        self.writes = []
        self.attachments = []
        self.BotError = RuntimeError
    def update_settings(self, settings):
        self.settings = settings
    def start_message(self):
        return self
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def write(self, text):
        self.writes.append(text)
    def overwrite(self, text):
        pass
    def attach_file(self, **kwargs):
        assert isinstance(kwargs["contents"], bytes) and kwargs["contents"]
        self.attachments.append(kwargs)


def test_injected_poe_runtime_and_decimal_parameter_display():
    runtime = CapturePoe("参数")
    runpy.run_path(str(BOT_PATH), init_globals={"poe": runtime}, run_name="__main__")
    text = "".join(runtime.writes)
    assert "0.5 < Score < 5.5" in text and "0.25" in text
    assert "**100%**" in text and "MA60过热防守 | **关闭**" in text
    assert "等下跌日补足" not in text and "V1.1" not in text
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "poe_params.txt").write_text(text, encoding="utf-8")


@pytest.mark.parametrize("query", ["信号", "实时信号", "实时参数", "表现", "交易记录 过去两个月", "净值曲线 过去两年"])
def test_query_routes_render_real_frozen_data(bot, real_run, monkeypatch, query):
    *_, daily = real_run
    runtime = CapturePoe(query)
    monkeypatch.setattr(bot, "poe", runtime)
    monkeypatch.setattr(bot, "_get_daily_for_today", lambda **kwargs: (daily.copy(), "frozen historical acceptance fixture; NOT live quotes"))
    monkeypatch.setattr(bot, "_now_bj", lambda: datetime(2026, 9, 3, 10, 0, tzinfo=bot.CN_TZ))
    # Calendar fixture only for local rendering tests; source loader is not bypassed in network smoke tests.
    monkeypatch.setattr(bot, "_expected_cn_trading_days", lambda start, end: pd.bdate_range(start, end))
    bot.SubDSixEtfV13Bot().run()
    text = "".join(runtime.writes)
    assert text and "V1.1" not in text and "先建50%" not in text
    assert "NoneType" not in text and "生成失败" not in text
    if bot.classify_query(query) == "performance":
        for window in ["full_sample", "10Y", "5Y", "3Y", "1Y"]:
            assert window in text
        assert "30.58%" in text and "-22.01%" in text
        assert any(a["name"].endswith(".csv") for a in runtime.attachments)
        assert any(a["name"].endswith(".png") for a in runtime.attachments)
        for a in runtime.attachments:
            (ARTIFACTS / a["name"]).write_bytes(a["contents"])
    else:
        assert "关闭" in text
    (ARTIFACTS / f"poe_{query.replace(' ', '_')}.txt").write_text(text, encoding="utf-8")


def test_failed_live_params_keeps_static_parameters(bot, monkeypatch):
    runtime = CapturePoe("实时参数")
    monkeypatch.setattr(bot, "poe", runtime)
    def fail(**kwargs):
        raise RuntimeError("provider unavailable")
    monkeypatch.setattr(bot, "_get_daily_for_today", fail)
    bot.SubDSixEtfV13Bot().run()
    text = "".join(runtime.writes)
    assert "加载失败" in text and "0.5 < Score < 5.5" in text


@pytest.mark.parametrize("query", ["信号", "实时信号", "表现"])
def test_provider_failures_are_not_silent_success(bot, monkeypatch, query):
    runtime = CapturePoe(query)
    monkeypatch.setattr(bot, "poe", runtime)
    def fail(**kwargs):
        raise ValueError("provider unavailable")
    monkeypatch.setattr(bot, "_get_daily_for_today", fail)
    with pytest.raises(RuntimeError, match="provider unavailable"):
        bot.SubDSixEtfV13Bot().run()


def test_missing_prices_stale_execution_and_input_checks(bot, real_run):
    prices, flags, *_ = real_run
    config = bot._build_config(prices.index[-1])
    with pytest.raises(ValueError, match="Missing required"):
        bot.build_curves(prices.drop(columns=list(bot.ASSETS)[0]), config)
    with pytest.raises(ValueError, match="unique, sorted"):
        bot.build_curves(prices.iloc[::-1], config)
    with pytest.raises(ValueError, match="finite and positive"):
        bad = prices.iloc[:30].copy()
        bad.iloc[0, 0] = np.inf
        bot.build_curves(bad, config)
    short = prices.iloc[:24]
    warmup = bot.build_curves(short, config, flags.iloc[:24])[0]
    assert warmup.position.eq("CASH").all() and warmup.nav.eq(1).all()


def test_no_future_leakage_on_frozen_prefix(bot, real_run):
    prices, flags, _, curve, _ = real_run
    # Prefix parity verifies scoring/state do not consume future rows.
    prefix = bot.build_curves(prices.iloc[:160], bot._build_config(prices.index[159]), flags.iloc[:160])[0]
    np.testing.assert_array_equal(prefix.nav, curve.nav.iloc[:160])
    assert prefix.position.equals(curve.position.iloc[:160])


def test_score_red_light_preserves_decimal_ceiling(bot, real_run):
    *_, daily = real_run
    frame = daily.tail(1).copy()
    code = next(iter(bot.ASSETS))
    frame[f"raw_score_{code}"] = 5.5
    frame[f"r2_{code}"] = .5
    assert "≥ 5.5" in "\n".join(bot._score_red_light_lines(frame))


@pytest.mark.skipif(os.environ.get("SUBD_V13_NETWORK_SMOKE") != "1", reason="Opt-in real-provider Poe-compatible smoke")
def test_real_network_poe_queries(bot, monkeypatch):
    """Local Poe interface with unmodified official network/data/engine path, not poe.com."""
    network_dir = ARTIFACTS / "network"
    network_dir.mkdir(parents=True, exist_ok=True)
    captures = []
    original_get = bot._get_daily_for_today
    def audited_get(**kwargs):
        daily, source = original_get(**kwargs)
        state = kwargs.get("data_state", "confirmed")
        daily.to_csv(network_dir / f"{state}_daily.csv.gz", index=False)
        captures.append({"state": state, "source": source, "rows": len(daily), "last_date": str(daily.date.max())})
        return daily, source
    monkeypatch.setattr(bot, "_get_daily_for_today", audited_get)
    bot._clear_daily_cache()
    results = []
    for query in ["参数", "信号", "表现", "交易记录 过去两个月", "净值曲线 过去两年", "实时信号", "实时参数"]:
        print(f"NETWORK QUERY: {query}", flush=True)
        runtime = CapturePoe(query)
        monkeypatch.setattr(bot, "poe", runtime)
        bot.SubDSixEtfV13Bot().run()
        text = "".join(runtime.writes)
        assert text and "NoneType" not in text and "生成失败" not in text
        assert "V1.1" not in text and "先建50%" not in text
        (network_dir / f"{query.replace(' ', '_')}.txt").write_text(text, encoding="utf-8")
        for attachment in runtime.attachments:
            (network_dir / attachment["name"]).write_bytes(attachment["contents"])
        if bot.classify_query(query) == "performance":
            assert all(label in text for label in ["full_sample", "10Y", "5Y", "3Y", "1Y"])
            assert len(runtime.attachments) >= 2
        results.append({"query": query, "passed": True, "attachments": len(runtime.attachments)})
        (network_dir / "results.json").write_text(json.dumps({"runtime": "local Poe-compatible; official real-data call chain; not hosted Poe", "queries": results, "data_captures": captures}, ensure_ascii=False, indent=2), encoding="utf-8")
