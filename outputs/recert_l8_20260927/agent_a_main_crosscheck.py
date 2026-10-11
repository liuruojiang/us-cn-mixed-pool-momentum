"""Cross-check every frozen L8 main-run daily path against audit A ledger."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
matrix = pd.read_csv(HERE / "agent_a_matrix.csv", dtype=str).fillna("")
arms = matrix.arm.tolist()
main_paths = [HERE / "daily" / f"{arm}.csv.gz" for arm in arms]
missing = [path.name for path in main_paths if not path.exists()]
if missing:
    raise SystemExit(f"Main paths not yet complete: {missing}")

result = {}
for arm, path in zip(arms, main_paths):
    main = pd.read_csv(path, parse_dates=["date"])
    independent = pd.read_csv(HERE / "agent_a_daily" / f"{arm}.csv.gz", parse_dates=["date"])
    if not main.date.equals(independent.date):
        raise AssertionError((arm, "dates"))
    categorical = {}
    for col in ("position_before", "best_candidate", "position", "trade_target"):
        a = main[col].fillna("<NA>").astype(str)
        b = independent[col].fillna("<NA>").astype(str)
        bad = a.ne(b)
        categorical[col] = {"mismatch_days": int(bad.sum()), "first_difference": None if not bad.any() else main.loc[bad, "date"].iloc[0].date().isoformat()}
    binary = {}
    for main_col, ind_col in (("buffer_blocked", "buffer_blocked"), ("trade_blocked_by_stale_price", "stale_blocked")):
        a = main[main_col].astype(bool)
        b = independent[ind_col].astype(bool)
        bad = a.ne(b)
        binary[main_col] = {"mismatch_days": int(bad.sum()), "first_difference": None if not bad.any() else main.loc[bad, "date"].iloc[0].date().isoformat()}
    numeric = {}
    for col in ("turnover", "cost", "gross_return", "return", "nav"):
        diff = np.abs(main[col].to_numpy(float) - independent[col].to_numpy(float))
        bad = diff > 1e-9
        numeric[col] = {"max_abs": float(np.max(diff)), "first_gt_1e_9": None if not bad.any() else main.date.iloc[int(np.argmax(bad))].date().isoformat()}
    result[arm] = {"rows": len(main), "categorical": categorical, "binary": binary, "numeric": numeric}

summary = {
    "paths": len(result),
    "path_days": sum(v["rows"] for v in result.values()),
    "categorical_mismatch_days": sum(x["mismatch_days"] for v in result.values() for x in v["categorical"].values()),
    "binary_mismatch_days": sum(x["mismatch_days"] for v in result.values() for x in v["binary"].values()),
    "max_nav_abs": max(v["numeric"]["nav"]["max_abs"] for v in result.values()),
    "max_return_abs": max(v["numeric"]["return"]["max_abs"] for v in result.values()),
    "numeric_gt_1e_9": sum(x["first_gt_1e_9"] is not None for v in result.values() for x in v["numeric"].values()),
}
output = {"summary": summary, "details": result}
(HERE / "agent_a_main_crosscheck.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
if summary["categorical_mismatch_days"] or summary["binary_mismatch_days"] or summary["numeric_gt_1e_9"]:
    raise AssertionError("L8 main versus independent A first differences: inspect JSON")
