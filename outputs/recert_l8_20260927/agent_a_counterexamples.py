"""Explicit wrong-path counterexamples against independent L8 cash/share ledger."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
formal = pd.read_csv(HERE / "agent_a_daily/formal_111.csv.gz", parse_dates=["date"]).set_index("date")
equal = pd.read_csv(HERE / "agent_a_daily/weight_p0.csv.gz", parse_dates=["date"]).set_index("date")
joint = pd.read_csv(HERE / "agent_a_daily/gate_010.csv.gz", parse_dates=["date"]).set_index("date")
floor = pd.read_csv(HERE / "agent_a_daily/gate_011.csv.gz", parse_dates=["date"]).set_index("date")
r2 = pd.read_csv(HERE / "agent_a_daily/gate_110.csv.gz", parse_dates=["date"]).set_index("date")

fee_day = formal.loc[pd.Timestamp("2013-08-30")]
assert fee_day.turnover == 2
wrong_one_leg_return = (1.0 + fee_day.gross_return) * (1.0 - 0.001) - 1.0
fee_error = float(wrong_one_leg_return - fee_day["return"])
assert fee_error > 0.0009

first_buy = formal.loc[pd.Timestamp("2012-02-14")]
assert first_buy.position_before == "CASH" and first_buy.position != "CASH"
wrong_new_asset_return = float(first_buy["return"] + 0.0)  # placeholder below from frozen price ratio
prices = pd.read_csv(HERE.parent / "recert_l1_20260926/prices_aligned_qfq_through_20260924.csv.gz", index_col=0, parse_dates=True)
asset = first_buy.position
asset_return = float(prices.at[pd.Timestamp("2012-02-14"), asset] / prices.loc[:"2012-02-14", asset].iloc[-2] - 1.0)
wrong_new_asset_return = float((1.0 + asset_return) * (1.0 - 0.001) - 1.0)
assert abs(wrong_new_asset_return - first_buy["return"]) > 0.001

stale_day = equal.loc[pd.Timestamp("2025-01-23")]
assert bool(stale_day.stale_blocked) and stale_day.turnover == 0 and stale_day.cost == 0

joint_day = pd.Timestamp("2012-02-06")
assert joint.loc[joint_day, "position"] != floor.loc[joint_day, "position"]
assert joint.loc[joint_day, "position"] != r2.loc[joint_day, "position"]
assert joint.loc[joint_day, "turnover"] == 0

no_cost = np.cumprod(1.0 + formal.gross_return.to_numpy(float))
costed = formal.nav.to_numpy(float)
assert np.all(costed <= no_cost + 1e-10)

year = formal.tail(252).nav.to_numpy(float)
correct_ann = float((year[-1] / year[0]) ** (252.0 / 251.0) - 1.0)
wrong_ann = float((year[-1] / year[0]) ** (252.0 / 252.0) - 1.0)
result = {
    "two_leg_fee_2013_08_30": {"turnover": int(fee_day.turnover), "correct_return": float(fee_day["return"]), "wrong_one_leg_return": wrong_one_leg_return, "error": fee_error},
    "new_holding_same_day_return_2012_02_14": {"old": first_buy.position_before, "new": asset, "correct_return": float(first_buy["return"]), "wrong_return": wrong_new_asset_return, "error": wrong_new_asset_return-float(first_buy["return"])},
    "stale_trade_2025_01_23": {"arm": "weight_p0", "blocked": bool(stale_day.stale_blocked), "position": stale_day.position, "turnover": int(stale_day.turnover), "cost": float(stale_day.cost)},
    "floor_r2_joint_2012_02_06": {"joint_position": joint.loc[joint_day, "position"], "floor_only_position": floor.loc[joint_day, "position"], "r2_only_position": r2.loc[joint_day, "position"], "joint_turnover": int(joint.loc[joint_day, "turnover"])},
    "formal_costed_never_exceeds_no_cost": True,
    "formal_no_cost_end_nav": float(no_cost[-1]),
    "formal_costed_end_nav": float(costed[-1]),
    "one_year_first_base_annual": {"correct_n_minus_1": correct_ann, "wrong_n": wrong_ann, "difference_pp": (correct_ann-wrong_ann)*100},
}
(HERE / "agent_a_counterexamples.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
