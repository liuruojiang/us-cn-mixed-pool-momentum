"""Replay existing adversarial data/execution checks against the new six-ETF bot."""
import importlib.util
import inspect
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKS = [
    "test_live_snapshot_unknown_source_is_monitor_only_even_with_true_flag",
    "test_live_quote_loader_retries_stale_primary_before_backup",
    "test_live_quote_loader_rejects_skewed_primary_before_backup",
    "test_live_snapshot_from_ineligible_source_is_monitor_only",
    "test_apply_live_quotes_rejects_partial_snapshot_without_today_row",
    "test_apply_live_quotes_rejects_extreme_move_from_previous_close",
    "test_apply_live_quotes_rejects_large_mismatch_with_history_today_bar",
    "test_live_quote_time_skew_reports_only_lagging_asset",
    "test_live_quote_loader_falls_back_when_primary_host_fails",
    "test_execution_legs_are_disabled_when_signal_is_invalid",
    "test_execution_legs_are_disabled_for_performance_purpose",
    "test_qfq_source_validation_rejects_qfq_raw_label",
    "test_qfq_source_validation_rejects_unapproved_source_even_if_labeled_qfq",
    "test_mandatory_windows_use_exact_unique_trading_day_counts",
    "test_formal_v11_load_close_rejects_raw_diagnostic_fallback",
    "test_live_quote_loader_falls_back_when_primary_price_quality_fails",
    "test_159915_twenty_five_percent_quote_rejected_by_security_price_limit",
    "test_history_today_diff_without_timestamp_tries_backup_candidate",
    "test_live_quote_loader_raises_when_all_candidates_fail_price_quality",
    "test_monitor_candidate_prefers_lower_max_age_and_skew_over_latest_single_quote",
    "test_price_limit_accepts_exchange_tick_rounded_limit_price",
    "test_price_limit_rejects_quote_above_tick_rounded_limit_price",
    "test_quote_price_must_be_etf_tick_multiple",
    "test_prev_close_one_tick_comparison_uses_decimal_boundary",
    "test_vendor_prev_close_must_match_independent_history_reference",
    "test_vendor_prev_close_small_mismatch_blocks_execution",
    "test_vendor_prev_close_must_be_etf_tick_multiple",
    "test_price_bad_primary_uses_delay_backup_for_monitor_only",
    "test_stale_monitor_candidate_must_pass_price_quality_before_selection",
    "test_missing_vendor_prev_close_demotes_candidate_to_monitor_only",
]


@pytest.mark.parametrize("check", CHECKS)
def test_replay_adversarial_check_on_v13(check, monkeypatch):
    bot = load(ROOT / "poe_subd_six_etf_v1_3_bot.py", f"safety_v13_{check}")
    shared = load(ROOT / "tests/test_poe_subd_external_review_regressions.py", f"shared_{check}")
    # Alias only the historical fixture's scenario field; production code has no V1.1 aliases.
    monkeypatch.setattr(bot, "V11_SCENARIO", bot.V13_SCENARIO, raising=False)
    monkeypatch.setattr(shared, "load_bot_module", lambda: bot)
    function = getattr(shared, check)
    kwargs = {"monkeypatch": monkeypatch} if "monkeypatch" in inspect.signature(function).parameters else {}
    function(**kwargs)


@pytest.mark.parametrize("name", ["test_get_daily_for_today_force_refresh_bypasses_same_day_cache", "test_confirmed_signal_drops_intraday_today_bar", "test_intraday_cache_is_invalid_after_confirmed_close_boundary"])
def test_cache_and_confirmation_contracts(name, monkeypatch):
    # A translated copy in memory reuses the exact existing test, without editing old tests.
    path = ROOT / "tests/test_poe_subd_live_signal_freshness.py"
    source = path.read_text(encoding="utf-8").replace("v1_1", "v1_3").replace("V11", "V13").replace("v11", "v13")
    namespace = {"__file__": str(path), "__name__": "v13_freshness_replay"}
    exec(compile(source, str(path), "exec"), namespace)
    function = namespace[name]
    kwargs = {"monkeypatch": monkeypatch} if "monkeypatch" in inspect.signature(function).parameters else {}
    function(**kwargs)
