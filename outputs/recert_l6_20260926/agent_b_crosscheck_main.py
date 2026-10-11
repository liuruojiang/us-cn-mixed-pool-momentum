"""Cross-question every independent L6 candidate against the formal-engine run."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
MAIN = HERE.parents[1] / "quant_param_scan_runs/20260926_six_etf_v1_3_l6_parameter_basis_20260924"
FIELDS = ("turnover", "cost", "gross_return", "return", "nav")
WINDOW_MAP = {"Full": "full", "10Y": "last_10y", "5Y": "last_5y",
              "3Y": "last_3y", "1Y": "last_1y", "six_etf_all_scoreable": "six_etf_all_scoreable"}


def main() -> None:
    frozen = pd.read_csv(MAIN / "parameter_matrix.csv", dtype=str, keep_default_na=False)
    metrics = pd.read_csv(HERE / "agent_b_metrics.csv")
    main_metrics = pd.read_csv(MAIN / "scan_summary.csv")
    records = []
    mismatches = []
    worst = {key: 0.0 for key in FIELDS}
    for row in frozen.itertuples(index=False):
        candidate = row.candidate
        independent = pd.read_csv(HERE / f"agent_b_{candidate}_daily.csv.gz", parse_dates=["date"]).set_index("date")
        filename = "formal_v1_3.csv.gz" if "formal" in row.role else f"{candidate}.csv.gz"
        main = pd.read_csv(MAIN / "daily_outputs" / filename, parse_dates=["date"]).set_index("date")
        if not independent.index.equals(main.index):
            raise AssertionError((candidate, "calendar mismatch"))
        mismatch = {}
        for key in ("position_before", "position"):
            delta = independent[key].ne(main[key])
            mismatch[key] = int(delta.sum())
            if delta.any():
                mismatches.append({"candidate": candidate, "field": key,
                                   "first": str(delta[delta].index[0].date())})
        for key in FIELDS:
            delta = (independent[key] - main[key]).abs()
            mismatch[key] = float(delta.max())
            worst[key] = max(worst[key], mismatch[key])
            if (delta > 1e-10).any():
                mismatches.append({"candidate": candidate, "field": key,
                                   "first": str(delta[delta > 1e-10].index[0].date()),
                                   "error": float(delta.max())})
        bool_delta = independent.buffer_blocked.astype(bool).ne(main.buffer_blocked.astype(bool))
        mismatch["buffer_blocked_days"] = int(bool_delta.sum())
        if bool_delta.any():
            mismatches.append({"candidate": candidate, "field": "buffer_blocked",
                               "first": str(bool_delta[bool_delta].index[0].date())})
        for our_window, their_segment in WINDOW_MAP.items():
            ours = metrics.loc[(metrics.arm == candidate) & metrics.window.eq(our_window)].iloc[0]
            theirs = main_metrics.loc[(main_metrics.candidate == candidate) & main_metrics.segment.eq(their_segment)].iloc[0]
            for our_key, their_key in (("annual_n_minus_1", "ann_return"), ("maxdd", "max_dd"),
                                       ("end_nav", "end_nav"), ("turnover_sum", "turnover_total"),
                                       ("fee_cash_initial_capital_units", "paid_fee_initial_capital_units")):
                difference = abs(float(ours[our_key]) - float(theirs[their_key]))
                if difference > 1e-9:
                    mismatches.append({"candidate": candidate, "field": f"{our_window}.{our_key}",
                                       "error": difference})
            if int(ours.trade_days) != int(theirs.trade_days) or int(ours.cash_days) != int(theirs.cash_days):
                mismatches.append({"candidate": candidate, "field": f"{our_window}.events"})
        records.append({"candidate": candidate, "group": row.group, **mismatch})
    pd.DataFrame(records).to_csv(HERE / "agent_b_main_crosscheck.csv", index=False, float_format="%.17g")
    result = {"matrix_rows": len(frozen), "path_rows_checked": len(frozen) * 3594,
              "numeric_field_max_abs": worst, "mismatches": mismatches,
              "all_daily_positions_fees_metrics_match": len(mismatches) == 0}
    (HERE / "agent_b_main_crosscheck.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if mismatches:
        raise AssertionError(f"{len(mismatches)} L6 crosscheck mismatches")


if __name__ == "__main__":
    main()
