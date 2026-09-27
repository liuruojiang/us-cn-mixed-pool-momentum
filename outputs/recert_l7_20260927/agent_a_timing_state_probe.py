"""Isolated L7 timing/state probe against the frozen 2026-09-24 input."""
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import poe_subd_six_etf_v1_3_bot as bot

L1 = ROOT / "outputs/recert_l1_20260926"
OUT = Path(__file__).resolve().parent
prices = pd.read_csv(L1 / "prices_aligned_qfq_through_20260924.csv.gz", index_col=0, parse_dates=True)
flags = pd.read_csv(L1 / "price_ffill_flags_through_20260924.csv.gz", index_col=0, parse_dates=True).astype(bool)
cut = pd.Timestamp("2026-09-02")
full = bot.build_curves(prices, bot._build_config(prices.index[-1]), flags)[0]
prefix_prices = prices.loc[:cut]
prefix_flags = flags.loc[:cut]
prefix = bot.build_curves(prefix_prices, bot._build_config(cut), prefix_flags)[0]
common = full.loc[prefix.index]
cols = ["position_before", "position", "trade_target", "turnover", "cost", "return", "nav"]
categorical = ["position_before", "position", "trade_target"]
numeric = [col for col in cols if col not in categorical]
categorical_diff = {col: int((common[col].fillna("<NA>") != prefix[col].fillna("<NA>")).sum()) for col in categorical}
numeric_max = {col: float(np.max(np.abs(common[col] - prefix[col]))) for col in numeric}
assert all(v == 0 for v in categorical_diff.values())
assert all(v <= 1e-10 for v in numeric_max.values())

# Deliberately wrong: start a new run at the extension rather than replaying the prior state.
tail = prices.loc[prices.index > cut]
tail_flags = flags.loc[tail.index]
reset = bot.build_curves(tail, bot._build_config(prices.index[-1]), tail_flags)[0]
first_tail = tail.index[0]
first_tail_diff = {
    "date": first_tail.date().isoformat(),
    "formal_position_before": str(full.loc[first_tail, "position_before"]),
    "reset_position_before": str(reset.loc[first_tail, "position_before"]),
    "formal_nav": float(full.loc[first_tail, "nav"]),
    "reset_nav": float(reset.loc[first_tail, "nav"]),
    "formal_score_available": bool(full.loc[first_tail, [f"score_{code}" for code in bot.ASSETS]].notna().any()),
    "reset_score_available": bool(reset.loc[first_tail, [f"score_{code}" for code in bot.ASSETS]].notna().any()),
}
assert first_tail_diff["formal_score_available"] and not first_tail_diff["reset_score_available"]

# Make the current source path's display metadata from the frozen panel, without fetching current quotes.
daily = bot._normalize_daily(full)
daily = bot._attach_signal_prices(daily, prices)
daily = bot._attach_price_fill_metadata(daily, flags)
daily["common_last_date"] = prices.index[-1].date().isoformat()
for code in bot.ASSETS:
    daily[f"last_date_{code}"] = prices[code].last_valid_index().date().isoformat()
before = datetime(2026, 9, 24, 14, 55, tzinfo=bot.CN_TZ)
after = datetime(2026, 9, 24, 15, 31, tzinfo=bot.CN_TZ)
weekend = datetime(2026, 9, 27, 12, 0, tzinfo=bot.CN_TZ)
pre_cut = bot.prepare_daily_for_signal(daily, live=False, now=before)
daily_final = bot._attach_confirmed_final_close_metadata(
    daily, {code: prices[code].last_valid_index() for code in bot.ASSETS}, now=after
)
post_cut = bot.prepare_daily_for_signal(daily_final, live=False, now=after)
weekend_daily = bot.prepare_daily_for_signal(daily_final, live=False, now=weekend)
weekend_status = bot.signal_data_status(weekend_daily, live=False, now=weekend)
weekend_report = bot.format_signal_report(daily_final, "frozen L1 input; no broker fills", live=False, now=weekend)
actual_trade_label = next(line for line in weekend_report.splitlines() if "上次实际成交日" in line)
assert pre_cut.date.iloc[-1] == pd.Timestamp("2026-09-23")
assert post_cut.date.iloc[-1] == pd.Timestamp("2026-09-24")
assert weekend_status["expected_confirmed_session"] == "2026-09-24"
assert weekend_status["signal_valid"] and not weekend_status["strategy_actionable_now"]
assert weekend_status["delayed_execution"]
assert bot._last_actual_trade_date(weekend_daily) == "2026-09-24"
assert "2026-09-24" in actual_trade_label

# A mixed-pool row with the same VERSION string must not enter this formal daily adapter.
mixed_row = daily.tail(1).copy()
mixed_row["scenario"] = "mixed_pool_v1_3"
mixed_rejected = False
try:
    bot._normalize_daily(mixed_row)
except Exception as exc:
    mixed_rejected = "未找到 SubD six-ETF v1.3" in str(exc)
assert mixed_rejected

result = {
    "input_rows": len(prices),
    "input_last": prices.index[-1].date().isoformat(),
    "prefix_rows": len(prefix),
    "prefix_last": cut.date().isoformat(),
    "prefix_categorical_differences": categorical_diff,
    "prefix_numeric_max_abs_differences": numeric_max,
    "wrong_reset_first_difference": first_tail_diff,
    "confirmed_signal_before_1530": pre_cut.date.iloc[-1].date().isoformat(),
    "confirmed_signal_after_1530": post_cut.date.iloc[-1].date().isoformat(),
    "weekend_status": {key: weekend_status[key] for key in [
        "signal_date", "expected_confirmed_session", "signal_valid", "calendar_available",
        "raw_signal_has_trade", "delayed_execution", "model_execution_price_available",
        "strategy_actionable_now", "tradable", "execution_note", "label"
    ]},
    "mixed_scenario_rejected": mixed_rejected,
    "report_actual_trade_label": actual_trade_label,
    "broker_fill_source_present": False,
}
(OUT / "agent_a_timing_state_probe.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
