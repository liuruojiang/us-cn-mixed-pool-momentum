"""Describe the four new paper trades in normalized initial-capital units."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
prices = pd.read_csv(ROOT / "outputs/recert_l1_20260926/prices_aligned_qfq_through_20260924.csv.gz").set_index("date")
formal = pd.read_csv(OUT / "formal_daily_20260924.csv.gz").set_index("date")
ledger = pd.read_csv(OUT / "agent_b_rebuilt_daily.csv.gz").set_index("date")

events = []
for i, (date, row) in enumerate(ledger.iterrows()):
    if date <= "2026-09-02" or row["turnover"] <= 0:
        continue
    prior_shares = 0.0 if i == 0 else float(ledger.iloc[i - 1]["shares"])
    old_code = row["position_before"]
    new_code = row["position"]
    events.append({
        "date": date,
        "model_signal_and_trade_clock": "T close; confirmed historical bar available only after close",
        "old_asset": old_code,
        "target_asset": new_code,
        "selected_candidate": formal.at[date, "best_candidate"],
        "selected_score": formal.at[date, "best_candidate_score"],
        "sell_asset": old_code if old_code != "CASH" else "",
        "sell_price_model_close": float(prices.at[date, old_code]) if old_code != "CASH" else None,
        "sell_shares_initial_capital_units": prior_shares if old_code != "CASH" else 0.0,
        "buy_asset": new_code if new_code != "CASH" else "",
        "buy_price_model_close": float(prices.at[date, new_code]) if new_code != "CASH" else None,
        "buy_shares_initial_capital_units": float(row["shares"]) if new_code != "CASH" else 0.0,
        "cost_fraction_of_day_wealth": float(row["cost"]),
        "cost_initial_capital_units": float(row["fee_cash"]),
        "nav_after_model_trade": float(row["nav"]),
    })

result = pd.DataFrame(events)
result.to_csv(OUT / "new_trade_events_20260903_20260924.csv", index=False)
print(result.to_string(index=False))
