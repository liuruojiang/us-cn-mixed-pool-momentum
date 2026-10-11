"""Compare all 27x6 main window metrics and trigger counts to independent A."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
main = pd.read_csv(HERE / "matched_metrics.csv")
audit = pd.read_csv(HERE / "agent_a_metrics.csv")
audit.window = audit.window.replace({"six_etf_all_scoreable": "SixScoreable"})
joined = main.merge(audit, on=["arm", "window"], suffixes=("_main", "_audit"), validate="one_to_one")
assert len(joined) == len(main) == len(audit) == 162
fields = {
    "annual": ("annual_net", "annual_n_minus_1"),
    "maxdd": ("maxdd", "maxdd"),
    "end_nav": ("end_nav", "end_nav"),
    "trade_days": ("trade_days", "trade_days"),
    "two_leg_days": ("two_leg_days", "two_leg_switch_days"),
    "turnover": ("turnover", "turnover_sum"),
    "paid_fee": ("paid_fee_initial_capital", "fee_cash_units"),
    "cash_days": ("cash_days", "cash_days"),
    "avg_exposure": ("average_carried_exposure", "average_old_exposure"),
    "buffer_block_days": ("buffer_block_days", "buffer_block_days"),
    "stale_block_days": ("stale_trade_block_days", "stale_block_days"),
}
maxdiff = {}
for label, (left, right) in fields.items():
    lm = left + "_main" if left in audit.columns else left
    ra = right + "_audit" if right in main.columns else right
    diffs = np.abs(joined[lm].to_numpy(float) - joined[ra].to_numpy(float))
    maxdiff[label] = float(np.max(diffs))
    assert maxdiff[label] < 1e-9, (label, maxdiff[label])
identity_fields = [("start_main", "start_audit"), ("end_main", "end_audit"),
                   ("rows_main", "rows_audit"), ("peak_date", "peak"), ("trough_date", "trough")]
identity = {}
for l, r in identity_fields:
    lm = l if l in joined else l + "_main"
    ra = r if r in joined else r + "_audit"
    identity[l] = int(joined[lm].astype(str).ne(joined[ra].astype(str)).sum())
assert all(v == 0 for v in identity.values())

triggers = pd.read_csv(HERE / "trigger_counts.csv").fillna("")
audit_events = json.loads((HERE / "agent_a_interactions.json").read_text(encoding="utf-8"))["events"]
trigger_mismatch = []
for row in triggers.itertuples(index=False):
    a = audit_events[row.arm]
    checks = {
        "target_diff_days": (int(row.target_diff_days), a["candidate_diff_days"]),
        "holding_diff_days": (int(row.holding_diff_days), a["position_diff_days"]),
        "first_target_diff": (str(row.first_target_diff), a["first_candidate_diff"] or ""),
        "first_holding_diff": (str(row.first_holding_diff), a["first_position_diff"] or ""),
        "buffer_block_days": (int(row.buffer_block_days), a["buffer_block_days"]),
    }
    for key, (x, y) in checks.items():
        if x != y:
            trigger_mismatch.append({"arm": row.arm, "field": key, "main": x, "audit": y})
assert not trigger_mismatch, trigger_mismatch

result = {"windows_checked": len(joined), "max_numeric_abs_difference": maxdiff,
          "identity_mismatch_counts": identity, "trigger_rows_checked": len(triggers),
          "trigger_mismatches": trigger_mismatch}
(HERE / "agent_a_metric_crosscheck.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
