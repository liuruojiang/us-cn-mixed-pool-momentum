"""Compare independent L8 cash/share accounts with main and audit A outputs."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
ARMS = pd.read_csv(HERE / "agent_a_matrix.csv", dtype=str, keep_default_na=False).arm.tolist()


def check(ok, message):
    if not bool(ok):
        raise AssertionError(message)


def main():
    detail = []
    worst = {"nav": 0.0, "return": 0.0, "gross_return": 0.0, "fee_cash": 0.0}
    all_main_available = all((HERE / "daily" / f"{arm}.csv.gz").exists() for arm in ARMS)
    for arm in ARMS:
        b = pd.read_csv(HERE / f"agent_b_{arm}_daily.csv.gz", parse_dates=["date"]).set_index("date")
        a = pd.read_csv(HERE / "agent_a_daily" / f"{arm}.csv.gz", parse_dates=["date"]).set_index("date")
        m = pd.read_csv(HERE / "daily" / f"{arm}.csv.gz", parse_dates=["date"]).set_index("date") if all_main_available else None
        check(b.index.equals(a.index) and (m is None or b.index.equals(m.index)) and len(b) == 3594, f"{arm} dates")
        row = {"arm": arm, "rows": len(b)}
        for source, ref in (("main", m), ("a", a)):
            if ref is None:
                continue
            for col in ("position_before", "position", "turnover", "cost", "gross_return", "return", "nav"):
                if col in ("position_before", "position"):
                    bad = b[col].astype(str).ne(ref[col].astype(str))
                    row[f"{source}_{col}_mismatches"] = int(bad.sum())
                    row[f"{source}_{col}_first"] = str(bad[bad].index[0].date()) if bad.any() else ""
                    check(not bad.any(), f"{arm} {source} {col} {row[f'{source}_{col}_first']}")
                else:
                    delta = np.abs(b[col].to_numpy(float) - ref[col].to_numpy(float))
                    row[f"{source}_{col}_max_abs"] = float(delta.max())
                    row[f"{source}_{col}_first_gt_tol"] = str(b.index[delta > (1e-10 if col == "nav" else 1e-12)][0].date()) if (delta > (1e-10 if col == "nav" else 1e-12)).any() else ""
                    check(not row[f"{source}_{col}_first_gt_tol"], f"{arm} {source} {col}")
                    if col in worst:
                        worst[col] = max(worst[col], row[f"{source}_{col}_max_abs"])
            if "fee_cash" in ref:
                delta = np.abs(b.fee_cash.to_numpy(float) - ref.fee_cash.to_numpy(float))
                row[f"{source}_fee_cash_max_abs"] = float(delta.max())
                worst["fee_cash"] = max(worst["fee_cash"], row[f"{source}_fee_cash_max_abs"])
                check(delta.max() < 1e-10, f"{arm} {source} fee cash")
            if "stale_blocked" in ref:
                check(b.stale_blocked.astype(bool).equals(ref.stale_blocked.astype(bool)), f"{arm} {source} stale block")
            if "buffer_blocked" in ref:
                check(b.buffer_blocked.astype(bool).equals(ref.buffer_blocked.astype(bool)), f"{arm} {source} buffer block")
        detail.append(row)
    bmetrics = pd.read_csv(HERE / "agent_b_metrics.csv")
    ametrics = pd.read_csv(HERE / "agent_a_metrics.csv")
    mmetrics = pd.read_csv(HERE / "matched_metrics.csv") if (HERE / "matched_metrics.csv").exists() else None
    check(len(bmetrics) == len(ametrics) == 162, "metric row count")
    ab = bmetrics.merge(ametrics, on=["arm", "window"], suffixes=("_b", "_a"), validate="one_to_one")
    check(len(ab) == 162, "metric join")
    metric_diff = {}
    for bname, aname in (("annual_n_minus_1", "annual_n_minus_1"), ("maxdd", "maxdd"),
                         ("end_nav", "end_nav"), ("trade_days", "trade_days"),
                         ("turnover_sum", "turnover_sum")):
        delta = np.abs(ab[f"{bname}_b"].to_numpy(float) - ab[f"{aname}_a"].to_numpy(float))
        metric_diff[bname] = float(delta.max())
        check(delta.max() < (1e-9 if bname == "end_nav" else 1e-10), f"A metric {bname}")
    if mmetrics is not None:
        mmetrics["window"] = mmetrics["window"].replace({"SixScoreable": "six_etf_all_scoreable"})
        bm = bmetrics.merge(mmetrics, on=["arm", "window"], suffixes=("_b", "_main"), validate="one_to_one")
        check(len(bm) == 162, "main metric join")
        for bname, mname in (("annual_n_minus_1", "annual_net"), ("maxdd", "maxdd"),
                             ("end_nav", "end_nav"), ("trade_days", "trade_days"),
                             ("turnover_sum", "turnover"), ("fee_cash_sum", "paid_fee_initial_capital"),
                             ("cash_end_days", "cash_days"),
                             ("average_carried_exposure", "average_carried_exposure")):
            bcol = f"{bname}_b" if bname in mmetrics.columns else bname
            mcol = f"{mname}_main" if mname in bmetrics.columns else mname
            delta = np.abs(bm[bcol].to_numpy(float) - bm[mcol].to_numpy(float))
            metric_diff["main_" + bname] = float(delta.max())
            check(delta.max() < (1e-9 if bname in ("end_nav", "fee_cash_sum") else 1e-10), f"main metric {bname}")
    trigger_parity = None
    trigger_file = HERE / "trigger_counts.csv"
    if trigger_file.exists():
        a = pd.read_csv(HERE / "agent_b_activation.csv").fillna("").set_index("arm")
        m = pd.read_csv(trigger_file).fillna("").set_index("arm")
        audit = json.loads((HERE / "agent_b_independent_audit.json").read_text(encoding="utf-8"))
        trigger_parity = {}
        for arm in ARMS[1:]:
            for bname, mname in (("position_diff_days", "holding_diff_days"),
                                 ("first_position_diff", "first_holding_diff")):
                check(str(a.at[arm, bname]) == str(m.at[arm, mname]), f"{arm} trigger {bname}")
            # Main target_diff is the pre-buffer Top1. B's desired is after
            # buffer, so compare target only where buffer is inactive.
            if audit["arms"][arm]["parameters"]["switch_buffer"] == 1.0:
                for bname, mname in (("target_diff_days", "target_diff_days"),
                                     ("first_target_diff", "first_target_diff")):
                    check(str(a.at[arm, bname]) == str(m.at[arm, mname]), f"{arm} trigger {bname}")
            check(audit["arms"][arm]["buffer_block_days"] == int(m.at[arm, "buffer_block_days"]),
                  f"{arm} buffer blocks")
        trigger_parity = {"arms_checked": len(ARMS) - 1,
                          "holding_count_first_date_and_buffer_blocks_match": True,
                          "target_checked_where_buffer_off": True}
    pd.DataFrame(detail).to_csv(HERE / "agent_b_main_crosscheck.csv", index=False)
    report = {"status": "PASS" if all_main_available and mmetrics is not None else "A_only_PASS_main_pending",
              "arms": len(ARMS), "daily_pairs": len(ARMS) * 3594,
              "metric_rows": len(ab), "main_metrics_available": mmetrics is not None,
              "max_daily_diffs": worst, "max_metric_diffs": metric_diff,
              "trigger_parity": trigger_parity,
              "first_economic_mismatch": None}
    (HERE / "agent_b_main_crosscheck.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if report["status"] == "PASS":
        audit_file = HERE / "agent_b_independent_audit.json"
        audit = json.loads(audit_file.read_text(encoding="utf-8"))
        audit["status"] = "PASS_after_main_and_A_crosscheck"
        audit["crosscheck"] = "agent_b_main_crosscheck.json"
        audit_file.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
