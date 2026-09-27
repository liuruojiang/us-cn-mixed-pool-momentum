"""Post-hoc comparison of independent account results with L5 main runner."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
ARM_MAP = {
    "111": "formal_v1_3", "011": "score_floor_off", "101": "score_ceiling_off", "110": "r2_off",
    "001": "floor_ceiling_off", "010": "floor_r2_off", "100": "ceiling_r2_off", "000": "all_three_off",
}


def main():
    out = {"arms": {}, "max_nav_abs": 0.0, "max_annual_abs": 0.0, "max_drawdown_abs": 0.0}
    mine_metrics = pd.read_csv(OUT / "agent_b_metrics.csv", dtype={"arm": str})
    main_metrics = pd.read_csv(OUT / "matched_metrics.csv")
    for bitcode, arm in ARM_MAP.items():
        mine = pd.read_csv(OUT / f"agent_b_{bitcode}_daily.csv.gz", parse_dates=["date"]).set_index("date")
        main = pd.read_csv(OUT / f"daily_{arm}.csv.gz", parse_dates=["date"]).set_index("date")
        if not mine.index.equals(main.index):
            raise AssertionError((bitcode, "date mismatch"))
        detail = {}
        for field in ("position_before", "position"):
            detail[field + "_different_days"] = int(np.count_nonzero(mine[field].to_numpy() != main[field].to_numpy()))
        for field in ("turnover", "cost", "return", "nav"):
            detail[field + "_max_abs"] = float(np.max(np.abs(mine[field].to_numpy(float) - main[field].to_numpy(float))))
        pairs = mine_metrics.loc[mine_metrics.arm.eq(bitcode)].set_index("window")
        other = main_metrics.loc[main_metrics.arm.eq(arm)].set_index("window").loc[pairs.index]
        if list(pairs.index) != list(other.index):
            raise AssertionError((bitcode, "window mismatch"))
        detail["annual_n_minus_1_max_abs"] = float(np.max(np.abs(pairs.annual_n_minus_1 - other.annual_n_minus_1)))
        detail["maxdd_max_abs"] = float(np.max(np.abs(pairs.maxdd - other.maxdd)))
        detail["turnover_window_max_abs"] = float(np.max(np.abs(pairs.turnover_sum - other.turnover_sum)))
        detail["fee_window_max_abs"] = float(np.max(np.abs(pairs.fee_amount_initial_capital_units - other.fee_initial_capital_units)))
        out["arms"][bitcode] = detail
        out["max_nav_abs"] = max(out["max_nav_abs"], detail["nav_max_abs"])
        out["max_annual_abs"] = max(out["max_annual_abs"], detail["annual_n_minus_1_max_abs"])
        out["max_drawdown_abs"] = max(out["max_drawdown_abs"], detail["maxdd_max_abs"])
        if any(detail[key] for key in ("position_before_different_days", "position_different_days", "turnover_max_abs", "cost_max_abs")):
            raise AssertionError((bitcode, detail))
        if detail["nav_max_abs"] > 1e-9 or detail["annual_n_minus_1_max_abs"] > 1e-12 or detail["maxdd_max_abs"] > 1e-12:
            raise AssertionError((bitcode, detail))
    example = {}
    day = pd.Timestamp("2012-02-06")
    for bitcode in ("111", "011", "110", "010"):
        main = pd.read_csv(OUT / f"daily_{ARM_MAP[bitcode]}.csv.gz", parse_dates=["date"]).set_index("date")
        example[bitcode] = str(main.at[day, "position"])
    out["pair_only_example_2012_02_06"] = example
    assert example == {"111": "CASH", "011": "CASH", "110": "CASH", "010": "159915.SZ"}
    one_year = mine_metrics.loc[mine_metrics.window.eq("1Y")].set_index("arm")
    add = float(one_year.at["011", "annual_n_minus_1"] + one_year.at["110", "annual_n_minus_1"] - one_year.at["111", "annual_n_minus_1"])
    actual = float(one_year.at["010", "annual_n_minus_1"])
    out["one_year_additive_counterexample"] = {"naive_additive": add, "actual_pair": actual, "overstatement_pp": 100 * (add - actual)}
    (OUT / "agent_b_main_crosscheck.json").write_text(json.dumps(out, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
