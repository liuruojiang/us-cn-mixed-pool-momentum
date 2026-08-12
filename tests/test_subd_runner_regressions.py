import importlib.util
import math
import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "run_subd_six_etf_v1_1.py"
BOT_PATH = ROOT / "poe_subd_six_etf_v1_1_bot.py"


def load_runner_module():
    spec = importlib.util.spec_from_file_location("run_subd_v11_under_test", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_bot_module():
    spec = importlib.util.spec_from_file_location("poe_subd_v11_perf_windows_under_test", BOT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _unit_config(module, end_date):
    return module.subd.RunConfig(
        source="akshare_em_qfq",
        one_way_cost=0.001,
        start_date=pd.Timestamp("2026-01-01"),
        end_date=pd.Timestamp(end_date),
        output_tag="unit",
        target_vols=(),
        vol_window=80,
        max_lev=1.5,
    )


def _synthetic_overlay_curve(module, dates, asset):
    return pd.DataFrame(
        {
            "position_before": ["CASH", asset, asset],
            "position": [asset, asset, asset],
            "fraction_before": [0.0, 1.0, 1.0],
            "holding_fraction": [1.0, 1.0, 1.0],
            "trade_target": [asset, None, None],
            "asset_return": [0.0, 0.10, -0.05],
            f"asset_return_{asset}": [0.0, 0.10, -0.05],
            "gross_return": [0.0, 0.10, -0.05],
            "return": [0.0, 0.10, -0.05],
            "nav": [1.0, 1.10, 1.045],
            "turnover": [1.0, 0.0, 0.0],
            "cost": [0.0, 0.0, 0.0],
            **{
                f"price_ffill_{code}": [False, False, False]
                for code in module.subd.ASSETS
            },
        },
        index=dates,
    )


def test_runner_align_prices_forward_fills_single_asset_suspension_with_metadata(monkeypatch):
    module = load_runner_module()
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-05"])
    assets = list(module.subd.ASSETS)
    suspended = assets[0]
    prices = pd.DataFrame(1.0, index=dates, columns=assets)
    prices.loc[dates[1], suspended] = math.nan
    prices.loc[dates[2], suspended] = 1.2

    monkeypatch.setattr(module, "_expected_cn_trading_days", lambda start, end: pd.DatetimeIndex(dates))

    aligned, common_last, last_by_asset = module.align_prices_to_common_valid_date(prices, assets)
    flags = aligned.attrs["price_ffill_flags"]

    assert common_last == dates[-1]
    assert last_by_asset[suspended] == dates[-1]
    assert aligned.loc[dates[1], suspended] == pytest.approx(1.0)
    assert bool(flags.loc[dates[1], suspended]) is True
    assert bool(flags.loc[dates[1], assets[1]]) is False


def test_runner_blocks_trade_when_target_price_is_forward_filled(monkeypatch):
    module = load_runner_module()
    assets = list(module.subd.ASSETS)
    held = assets[0]
    target = assets[1]
    dates = pd.to_datetime(["2026-01-01", "2026-01-02"])
    prices = pd.DataFrame(1.0, index=dates, columns=assets)
    flags = pd.DataFrame(False, index=dates, columns=assets)
    flags.loc[dates[1], target] = True
    prices.attrs["price_ffill_flags"] = flags

    monkeypatch.setattr(module.subd, "LOOKBACK", 1)

    def fake_scores(_prices, idx, r2_threshold=None):
        if idx == 0:
            return {held: 1.0}, {held: 0.9}
        return {held: 1.0, target: 2.0}, {held: 0.9, target: 0.9}

    monkeypatch.setattr(module.subd, "calc_scores", fake_scores)

    out = module.run_staged_entry(
        prices,
        _unit_config(module, dates[-1]),
        module.EntryCase("full_entry", "full_entry", 1.0),
        r2_threshold=0.2,
        switch_buffer=1.0,
    )

    assert out.loc[dates[0], "position"] == held
    assert bool(out.loc[dates[1], "trade_blocked_by_stale_price"]) is True
    assert out.loc[dates[1], "stale_price_trade_assets"] == target
    assert out.loc[dates[1], "position"] == held
    assert out.loc[dates[1], "turnover"] == pytest.approx(0.0)


def test_runner_overlay_carries_drifted_exposure_without_daily_target_rebalance():
    module = load_runner_module()
    asset = next(iter(module.subd.ASSETS))
    dates = pd.bdate_range("2026-01-05", periods=3)
    curve = _synthetic_overlay_curve(module, dates, asset)
    scale = pd.Series(1.5, index=dates, dtype=float)
    ones = pd.Series(1.0, index=dates, dtype=float)

    out = module._recompute_final_exposure_nav(
        curve,
        scale,
        scale,
        ones,
        ones,
        one_way_cost=0.0,
    )

    expected_day_two = 1.5 * 1.10 / 1.15
    assert out.loc[dates[1], "drifted_exposure_before_trade"] == pytest.approx(expected_day_two)
    assert out.loc[dates[1], "final_exposure_after_overheat"] == pytest.approx(expected_day_two)
    assert out.loc[dates[1], "rebalance_delta"] == pytest.approx(0.0)
    assert out.loc[dates[1], "turnover"] == pytest.approx(0.0)
    assert out.loc[dates[2], "turnover"] == pytest.approx(0.0)


def test_runner_overlay_hard_caps_drifted_exposure_with_auditable_cost():
    module = load_runner_module()
    asset = next(iter(module.subd.ASSETS))
    dates = pd.bdate_range("2026-01-05", periods=3)
    curve = _synthetic_overlay_curve(module, dates, asset)
    curve["asset_return"] = [0.0, -0.10, 0.0]
    curve[f"asset_return_{asset}"] = [0.0, -0.10, 0.0]
    curve["gross_return"] = curve["asset_return"]
    curve["return"] = curve["asset_return"]
    curve["nav"] = (1.0 + curve["return"]).cumprod()
    scale = pd.Series(1.5, index=dates, dtype=float)
    ones = pd.Series(1.0, index=dates, dtype=float)

    out = module._recompute_final_exposure_nav(
        curve,
        scale,
        scale,
        ones,
        ones,
        one_way_cost=0.001,
        max_lev=1.5,
    )

    drifted = 1.5 * 0.90 / 0.85
    cap_turnover = drifted - 1.5
    assert out.loc[dates[1], "drifted_exposure_before_trade"] == pytest.approx(drifted)
    assert out.loc[dates[1], "final_exposure_after_overheat"] == pytest.approx(1.5)
    assert bool(out.loc[dates[1], "exposure_cap_rebalance"]) is True
    assert out.loc[dates[1], "exposure_cap_turnover"] == pytest.approx(cap_turnover)
    assert out.loc[dates[1], "exposure_cap_cost"] == pytest.approx(cap_turnover * 0.001)
    assert out.loc[dates[1], "turnover"] == pytest.approx(cap_turnover)
    assert out.loc[dates[1], "cost"] == pytest.approx(cap_turnover * 0.001)
    assert out["final_exposure_after_overheat"].max() <= 1.5 + 1e-12


def test_runner_overlay_fails_closed_when_stale_price_prevents_hard_cap():
    module = load_runner_module()
    asset = next(iter(module.subd.ASSETS))
    dates = pd.bdate_range("2026-01-05", periods=3)
    curve = _synthetic_overlay_curve(module, dates, asset)
    curve["asset_return"] = [0.0, -0.10, 0.0]
    curve[f"asset_return_{asset}"] = [0.0, -0.10, 0.0]
    flags = pd.DataFrame(False, index=dates, columns=list(module.subd.ASSETS), dtype=bool)
    flags.loc[dates[1], asset] = True
    scale = pd.Series(1.5, index=dates, dtype=float)
    ones = pd.Series(1.0, index=dates, dtype=float)

    with pytest.raises(RuntimeError, match="Cannot enforce max_lev hard cap with stale"):
        module._recompute_final_exposure_nav(
            curve,
            scale,
            scale,
            ones,
            ones,
            one_way_cost=0.001,
            price_ffill_flags=flags,
            max_lev=1.5,
        )


@pytest.mark.parametrize("max_lev", [True, math.nan, math.inf, -0.01, "not-a-number"])
def test_runner_and_poe_overlay_direct_entries_reject_invalid_explicit_hard_cap(max_lev):
    runner = load_runner_module()
    bot = load_bot_module()
    asset = next(iter(runner.subd.ASSETS))
    dates = pd.bdate_range("2026-01-05", periods=3)
    curve = _synthetic_overlay_curve(runner, dates, asset)
    scale = pd.Series(1.0, index=dates, dtype=float)

    for module in (runner, bot):
        with pytest.raises(
            ValueError,
            match="max_lev hard cap must be a finite nonnegative number",
        ):
            module._recompute_final_exposure_nav(
                curve,
                scale,
                scale,
                scale,
                scale,
                one_way_cost=0.001,
                max_lev=max_lev,
            )


@pytest.mark.parametrize("asset_return", [-2.0 / 3.0, -0.70, math.inf])
def test_runner_overlay_fails_closed_before_nav_becomes_nonpositive_or_nonfinite(asset_return):
    module = load_runner_module()
    asset = next(iter(module.subd.ASSETS))
    dates = pd.bdate_range("2026-01-05", periods=2)
    curve = _synthetic_overlay_curve(module, pd.bdate_range("2026-01-05", periods=3), asset).iloc[:2].copy()
    curve.loc[dates[1], "asset_return"] = asset_return
    curve.loc[dates[1], f"asset_return_{asset}"] = asset_return
    scale = pd.Series(1.5, index=dates, dtype=float)
    ones = pd.Series(1.0, index=dates, dtype=float)

    with pytest.raises(RuntimeError, match="finite|positive"):
        module._recompute_final_exposure_nav(
            curve,
            scale,
            scale,
            ones,
            ones,
            one_way_cost=0.001,
            max_lev=1.5,
        )


def test_runner_overlay_ledger_matches_poe_for_drift_and_hard_cap():
    runner = load_runner_module()
    bot = load_bot_module()
    asset = next(iter(runner.subd.ASSETS))
    dates = pd.bdate_range("2026-01-05", periods=3)
    curve = _synthetic_overlay_curve(runner, dates, asset)
    curve["asset_return"] = [0.0, -0.10, 0.02]
    curve[f"asset_return_{asset}"] = [0.0, -0.10, 0.02]
    flags = pd.DataFrame(False, index=dates, columns=list(runner.subd.ASSETS), dtype=bool)
    scale = pd.Series(1.5, index=dates, dtype=float)
    ones = pd.Series(1.0, index=dates, dtype=float)

    runner_out = runner._recompute_final_exposure_nav(
        curve,
        scale,
        scale,
        ones,
        ones,
        one_way_cost=0.001,
        price_ffill_flags=flags,
        max_lev=1.5,
    )
    bot_out = bot._recompute_final_exposure_nav(
        curve,
        scale,
        scale,
        ones,
        ones,
        one_way_cost=0.001,
        price_ffill_flags=flags,
        max_lev=1.5,
    )

    assert runner_out.columns.tolist() == bot_out.columns.tolist()
    numeric_columns = [
        "exposure_effective",
        "final_exposure",
        "final_exposure_after_overheat",
        "drifted_exposure_before_trade",
        "rebalance_delta",
        "buy_delta",
        "sell_delta",
        "turnover",
        "cost",
        "exposure_cap_turnover",
        "exposure_cap_cost",
        "gross_return",
        "return",
        "nav",
    ]
    for column in numeric_columns:
        assert runner_out[column].tolist() == pytest.approx(bot_out[column].tolist())
    assert runner_out["exposure_cap_rebalance"].tolist() == bot_out[
        "exposure_cap_rebalance"
    ].tolist()
    assert runner_out["actual_position_before"].tolist() == bot_out[
        "actual_position_before"
    ].tolist()
    assert runner_out["actual_position_next"].tolist() == bot_out[
        "actual_position_next"
    ].tolist()


def test_runner_and_poe_do_not_double_attribute_policy_turnover_to_hard_cap():
    runner = load_runner_module()
    bot = load_bot_module()
    asset = next(iter(runner.subd.ASSETS))
    dates = pd.bdate_range("2026-01-05", periods=2)
    curve = _synthetic_overlay_curve(runner, pd.bdate_range("2026-01-05", periods=3), asset).iloc[:2].copy()
    curve.loc[dates[1], "asset_return"] = -0.10
    curve.loc[dates[1], f"asset_return_{asset}"] = -0.10
    curve.loc[dates[1], "trade_target"] = asset
    flags = pd.DataFrame(False, index=dates, columns=list(runner.subd.ASSETS), dtype=bool)
    scale = pd.Series(1.5, index=dates, dtype=float)
    ones = pd.Series(1.0, index=dates, dtype=float)

    outputs = [
        module._recompute_final_exposure_nav(
            curve,
            scale,
            scale,
            ones,
            ones,
            one_way_cost=0.001,
            price_ffill_flags=flags,
            max_lev=1.5,
        )
        for module in (runner, bot)
    ]

    for out in outputs:
        assert out.loc[dates[1], "turnover"] > 0.0
        assert bool(out.loc[dates[1], "exposure_cap_rebalance"]) is False
        assert out.loc[dates[1], "exposure_cap_turnover"] == pytest.approx(0.0)
        assert out.loc[dates[1], "exposure_cap_cost"] == pytest.approx(0.0)
    assert outputs[0]["exposure_cap_rebalance"].tolist() == outputs[1][
        "exposure_cap_rebalance"
    ].tolist()


@pytest.mark.parametrize("mask_mode", ["embedded_columns", "explicit_mask"])
def test_runner_overlay_stale_price_blocks_entire_rebalance_then_retries(mask_mode):
    module = load_runner_module()
    asset = next(iter(module.subd.ASSETS))
    dates = pd.bdate_range("2026-01-05", periods=3)
    curve = _synthetic_overlay_curve(module, dates, asset)
    flags = pd.DataFrame(False, index=dates, columns=list(module.subd.ASSETS), dtype=bool)
    flags.loc[dates[1], asset] = True
    if mask_mode == "embedded_columns":
        curve.loc[dates[1], f"price_ffill_{asset}"] = True
        explicit_flags = None
    else:
        explicit_flags = flags
    effective = pd.Series([1.0, 1.0, 1.5], index=dates, dtype=float)
    next_scale = pd.Series([1.0, 1.5, 1.5], index=dates, dtype=float)
    ones = pd.Series(1.0, index=dates, dtype=float)

    out = module._recompute_final_exposure_nav(
        curve,
        effective,
        next_scale,
        ones,
        ones,
        one_way_cost=0.0,
        price_ffill_flags=explicit_flags,
    )

    assert bool(out.loc[dates[1], "trade_blocked_by_stale_price"]) is True
    assert out.loc[dates[1], "stale_price_trade_assets"] == asset
    assert out.loc[dates[1], "turnover"] == pytest.approx(0.0)
    assert out.loc[dates[1], "final_exposure_after_overheat"] == pytest.approx(
        out.loc[dates[1], "drifted_exposure_before_trade"]
    )
    assert out.loc[dates[2], "turnover"] > 0.0
    assert out.loc[dates[2], "final_exposure_after_overheat"] == pytest.approx(1.5)


def test_runner_zero_overheat_guard_preserves_position_state_until_stale_exit_is_executable():
    module = load_runner_module()
    asset = next(iter(module.subd.ASSETS))
    dates = pd.bdate_range("2026-01-05", periods=3)
    guarded_input = pd.DataFrame(
        {
            "position_before": ["CASH", asset, asset],
            "position": [asset, asset, asset],
            "fraction_before": [0.0, 1.0, 1.0],
            "holding_fraction": [1.0, 1.0, 1.0],
            "trade_target": [asset, None, None],
            "trade_fraction": [1.0, math.nan, math.nan],
            "pending_entry_target": [None, None, None],
            "pending_entry_since": [None, None, None],
            "pending_entry_days": [0, 0, 0],
            "staged_initial": [False, False, False],
            "fill_on_down_day": [False, False, False],
            "asset_return": [0.0, 0.01, 0.01],
            "overheat_scale_next": [1.0, 0.0, 0.0],
        },
        index=dates,
    )
    flags = pd.DataFrame(False, index=dates, columns=list(module.subd.ASSETS), dtype=bool)
    flags.loc[dates[1], asset] = True

    out = module._apply_zero_overheat_execution_guard(guarded_input, flags)

    assert out.loc[dates[0], "holding_fraction"] == pytest.approx(module.INITIAL_ENTRY_FRACTION)
    assert out.loc[dates[1], "holding_fraction"] == pytest.approx(module.INITIAL_ENTRY_FRACTION)
    assert out.loc[dates[1], "actual_entry_state"] == "HALF_POSITION_WAIT_DOWN"
    assert out.loc[dates[2], "holding_fraction"] == pytest.approx(0.0)
    assert out.loc[dates[2], "actual_entry_state"] == "BLOCKED_BY_OVERHEAT"


def test_runner_staged_entry_emits_each_asset_return_for_carried_state(monkeypatch):
    module = load_runner_module()
    assets = list(module.subd.ASSETS)
    dates = pd.bdate_range("2026-01-05", periods=2)
    prices = pd.DataFrame(1.0, index=dates, columns=assets)
    prices.loc[dates[1], assets[1]] = 1.25
    monkeypatch.setattr(module.subd, "LOOKBACK", 99)

    out = module.run_staged_entry(
        prices,
        _unit_config(module, dates[-1]),
        module.EntryCase("full_entry", "full_entry", 1.0),
        r2_threshold=0.2,
        switch_buffer=1.0,
    )

    assert out.loc[dates[0], f"asset_return_{assets[1]}"] == pytest.approx(0.0)
    assert out.loc[dates[1], f"asset_return_{assets[1]}"] == pytest.approx(0.25)


def test_runner_performance_window_rebases_first_return_to_zero():
    module = load_runner_module()
    dates = pd.bdate_range("2026-01-05", periods=3)
    sub = pd.DataFrame(
        {"return": [0.50, 0.10, -0.20], "nav": [1.50, 1.65, 1.32]},
        index=dates,
    )

    ret = module._daily_returns_for_window(sub)

    assert ret.tolist() == pytest.approx([0.0, 0.10, -0.20])


@pytest.mark.parametrize("bad_return", [math.nan, math.inf, -math.inf, -1.0, -1.01])
@pytest.mark.parametrize("bad_position", [0, 1])
def test_runner_performance_window_rejects_invalid_return_even_on_rebased_row(
    bad_return, bad_position
):
    module = load_runner_module()
    dates = pd.bdate_range("2026-01-05", periods=3)
    returns = [0.0, 0.10, -0.20]
    returns[bad_position] = bad_return
    sub = pd.DataFrame({"return": returns}, index=dates)

    with pytest.raises(ValueError, match="finite|greater than -1"):
        module._daily_returns_for_window(sub)


@pytest.mark.parametrize("bad_return", [math.nan, math.inf, -math.inf, "not-a-number"])
def test_runner_target_vol_rejects_nonfinite_returns(bad_return):
    module = load_runner_module()
    curve = pd.DataFrame({"return": [0.0, bad_return, 0.01]})

    with pytest.raises(ValueError, match="return values must be finite"):
        module._compute_target_vol_scales(curve, 0.25, 2, 1.5)


@pytest.mark.parametrize(
    ("target_vol", "vol_window", "max_lev", "message"),
    [
        (True, 2, 1.5, "target_vol"),
        (math.nan, 2, 1.5, "target_vol"),
        (math.inf, 2, 1.5, "target_vol"),
        (0.0, 2, 1.5, "target_vol"),
        (0.25, True, 1.5, "vol_window"),
        (0.25, 2.5, 1.5, "vol_window"),
        (0.25, 1, 1.5, "vol_window"),
        (0.25, 2, True, "max_lev"),
        (0.25, 2, math.nan, "max_lev"),
        (0.25, 2, math.inf, "max_lev"),
        (0.25, 2, -0.01, "max_lev"),
    ],
)
def test_runner_target_vol_parameter_contract_matches_poe(
    target_vol, vol_window, max_lev, message
):
    module = load_runner_module()
    curve = pd.DataFrame({"return": [0.0, 0.01, -0.01]})

    with pytest.raises(ValueError, match=message):
        module._compute_target_vol_scales(curve, target_vol, vol_window, max_lev)


def test_runner_target_vol_warmup_scale_respects_max_leverage():
    module = load_runner_module()
    curve = pd.DataFrame({"return": [0.0, 0.0, 0.0, 0.0]})

    realized, effective, next_scale = module._compute_target_vol_scales(
        curve,
        target_vol=0.25,
        vol_window=3,
        max_lev=0.5,
    )

    assert realized.iloc[:2].isna().all()
    assert effective.tolist() == pytest.approx([0.5, 0.5, 0.5, 0.5])
    assert next_scale.tolist() == pytest.approx([0.5, 0.5, 0.5, 0.5])


def test_runner_mandatory_performance_windows_include_full_and_10y():
    module = load_runner_module()
    dates = pd.bdate_range("2012-01-02", "2026-06-26")

    windows = module.build_performance_windows(
        dates,
        pd.Timestamp("2026-06-26"),
        pd.Timestamp("2020-01-02"),
    )

    labels = list(windows)
    assert labels[:5] == ["full_sample", "10Y", "5Y", "3Y", "1Y"]
    assert windows["full_sample"] == dates[0]
    assert windows["10Y"] == module.trading_day_window_start(
        dates,
        pd.Timestamp("2026-06-26"),
        10 * module.subd.TRADING_DAYS,
    )
    for label, years in (("10Y", 10), ("5Y", 5), ("3Y", 3), ("1Y", 1)):
        assert len(dates[(dates >= windows[label]) & (dates <= dates[-1])]) == (
            years * module.subd.TRADING_DAYS
        )
    assert windows["from_2020"] == pd.Timestamp("2020-01-02")


@pytest.mark.parametrize("bad_order", ["duplicate", "decreasing"])
def test_runner_performance_windows_reject_non_unique_or_non_increasing_dates(bad_order):
    module = load_runner_module()
    dates = pd.bdate_range("2012-01-02", periods=3000)
    if bad_order == "duplicate":
        bad_dates = dates.insert(100, dates[100])
    else:
        bad_dates = dates[::-1]

    with pytest.raises(ValueError, match="unique|increasing"):
        module.build_performance_windows(bad_dates, dates[-1], pd.Timestamp("2020-01-02"))


def test_runner_performance_window_rejects_insufficient_rows_for_named_horizon():
    module = load_runner_module()
    dates = pd.bdate_range("2025-01-02", periods=251)

    with pytest.raises(ValueError, match="requires 252 unique trading dates"):
        module.trading_day_window_start(dates, dates[-1], module.subd.TRADING_DAYS)


def test_runner_raw_sina_results_are_explicitly_diagnostic_only():
    module = load_runner_module()

    raw_status, raw_note = module.classify_source_evidence("sina")
    qfq_status, qfq_note = module.classify_source_evidence("eastmoney")

    assert raw_status == "diagnostic_only"
    assert "raw/unadjusted" in raw_note
    assert "diagnostic" in raw_note.lower()
    assert qfq_status == "formal"
    assert "qfq" in qfq_note.lower()


def test_runner_evidence_annotation_is_written_into_every_output_row():
    module = load_runner_module()
    frame = pd.DataFrame({"value": [1, 2]})

    annotated = module.attach_source_evidence(frame, "akshare_sina_raw")

    assert annotated["result_status"].tolist() == ["diagnostic_only", "diagnostic_only"]
    assert all("raw/unadjusted" in value for value in annotated["result_note"])


def test_runner_build_curves_cannot_return_unlabelled_raw_results(monkeypatch):
    module = load_runner_module()
    dates = pd.bdate_range("2026-01-05", periods=2)
    prices = pd.DataFrame(1.0, index=dates, columns=list(module.subd.ASSETS))
    raw_config = module.subd.RunConfig(
        source="akshare_sina_raw",
        one_way_cost=0.001,
        start_date=dates[0],
        end_date=dates[-1],
        output_tag="unit",
        target_vols=(),
        vol_window=80,
        max_lev=1.5,
    )
    intermediate = pd.DataFrame({"placeholder": [1]}, index=[dates[0]])
    monkeypatch.setattr(module, "run_staged_entry", lambda *args, **kwargs: intermediate.copy())
    monkeypatch.setattr(module, "apply_target_vol_overlay", lambda *args, **kwargs: intermediate.copy())
    monkeypatch.setattr(module, "build_overheat_features", lambda *args, **kwargs: {})
    monkeypatch.setattr(module, "apply_overheat_overlay", lambda *args, **kwargs: intermediate.copy())
    monkeypatch.setattr(
        module,
        "tag_original",
        lambda curve: pd.DataFrame(
            {"version": ["1.0"], "scenario": ["original"]}, index=curve.index
        ),
    )

    curves = module.build_curves(prices, raw_config)

    assert len(curves) == 2
    for curve in curves:
        assert curve["result_status"].tolist() == ["diagnostic_only"]
        assert "raw/unadjusted" in curve["result_note"].iloc[0]


def test_runner_expected_cn_trading_days_uses_local_cache_when_research_helper_missing(tmp_path, monkeypatch):
    module = load_runner_module()
    cache_path = tmp_path / "cn_trading_days_cache.csv"
    pd.DataFrame(
        {
            "trade_date": ["2026-01-01", "2026-01-02", "2026-01-05"],
            "coverage_end": ["2026-12-31"] * 3,
            "source": ["unit"] * 3,
        }
    ).to_csv(cache_path, index=False)
    monkeypatch.setattr(module, "TRADING_CALENDAR_CACHE_PATH", cache_path, raising=False)
    monkeypatch.setattr(module.subd, "ak", None)

    days = module._expected_cn_trading_days(pd.Timestamp("2026-01-02"), pd.Timestamp("2026-01-05"))

    assert days.tolist() == [pd.Timestamp("2026-01-02"), pd.Timestamp("2026-01-05")]


def test_poe_default_performance_ranges_include_mandatory_windows_when_sample_start_known():
    module = load_bot_module()

    ranges = module.resolve_performance_ranges(
        "",
        latest_date=pd.Timestamp("2026-06-26"),
        earliest_date=pd.Timestamp("2011-12-09"),
    )

    labels = [label for label, _start, _end in ranges]
    assert labels[:5] == ["full_sample", "10Y", "5Y", "3Y", "1Y"]
    assert ranges[0] == ("full_sample", pd.Timestamp("2011-12-09"), pd.Timestamp("2026-06-26"))
