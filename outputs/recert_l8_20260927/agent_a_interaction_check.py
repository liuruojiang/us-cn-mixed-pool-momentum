"""Independent L8 trigger and joint-path diagnostics from audit A curves."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
arms = pd.read_csv(HERE / "agent_a_matrix.csv", dtype=str).arm.tolist()
curves = {arm: pd.read_csv(HERE / "agent_a_daily" / f"{arm}.csv.gz", parse_dates=["date"]) for arm in arms}
formal = curves["formal_111"]
events = {}
for arm, df in curves.items():
    different = df.position.ne(formal.position)
    candidate_different = df.best_candidate.ne(formal.best_candidate)
    events[arm] = {
        "candidate_diff_days": int(candidate_different.sum()),
        "first_candidate_diff": None if not candidate_different.any() else df.loc[candidate_different, "date"].iloc[0].date().isoformat(),
        "position_diff_days": int(different.sum()),
        "first_position_diff": None if not different.any() else df.loc[different, "date"].iloc[0].date().isoformat(),
        "buffer_block_days": int(df.buffer_blocked.sum()),
        "stale_block_days": int(df.stale_blocked.sum()),
        "model_trade_days": int((df.turnover > 0).sum()),
        "two_leg_days": int((df.turnover == 2).sum()),
        "turnover_sum": float(df.turnover.sum()),
        "fee_cash_units": float(df.fee_cash.sum()),
        "cash_days": int(df.position.eq("CASH").sum()),
        "average_old_exposure": float(df.position_before.ne("CASH").mean()),
        "end_nav": float(df.nav.iloc[-1]),
        "min_cash": float(df.cash.min()),
        "min_shares": float(df.shares.min()),
    }
pairs = {
    "gate_010": ("gate_011", "gate_110"),
    "ceiling_525_buffer_105": ("ceiling_525", "buffer_105"),
    "ceiling_525_r2_off": ("ceiling_525", "gate_110"),
    "weight_p0_lookback_29": ("weight_p0", "lookback_29"),
}
joint = {}
for arm, (left, right) in pairs.items():
    df, a, b = curves[arm], curves[left], curves[right]
    both_distinct_target = df.best_candidate.ne(a.best_candidate) & df.best_candidate.ne(b.best_candidate)
    both_distinct_position = df.position.ne(a.position) & df.position.ne(b.position)
    nav_f, nav_a, nav_b, nav_j = [curves[name].nav.iloc[-1] for name in ("formal_111", left, right, arm)]
    joint[arm] = {
        "single_arms": [left, right],
        "joint_target_novel_days": int(both_distinct_target.sum()),
        "first_joint_target_novel": None if not both_distinct_target.any() else df.loc[both_distinct_target, "date"].iloc[0].date().isoformat(),
        "joint_position_novel_days": int(both_distinct_position.sum()),
        "first_joint_position_novel": None if not both_distinct_position.any() else df.loc[both_distinct_position, "date"].iloc[0].date().isoformat(),
        "end_nav": float(nav_j),
        "log_nav_interaction_residual": float(np.log(nav_j) - np.log(nav_a) - np.log(nav_b) + np.log(nav_f)),
    }
out = {"events": events, "joint": joint}
(HERE / "agent_a_interactions.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(joint, ensure_ascii=False, indent=2))
