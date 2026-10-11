"""Compare same-parameter paths against the preceding formal LOOKBACK grid."""

import json
from pathlib import Path

import numpy as np
import pandas as pd


RUN = Path(__file__).resolve().parent
OLD = RUN.parent / "20261001_lookback_5_99_step2_20260924"


def main():
    rows = []
    for value in range(5, 100, 10):
        name = f"lookback_{value}.csv.gz"
        current = pd.read_csv(RUN / "daily_outputs" / name)
        prior = pd.read_csv(OLD / "daily_outputs" / name)
        if not current.date.equals(prior.date):
            raise RuntimeError(f"Date mismatch at {value}")
        position_diff = int((current.position.fillna("CASH") != prior.position.fillna("CASH")).sum())
        numeric = {field: float(np.max(np.abs(current[field] - prior[field])))
                   for field in ("turnover", "cost", "nav")}
        if position_diff or any(error > 1e-10 for error in numeric.values()):
            raise RuntimeError(f"Path mismatch at {value}: {position_diff}, {numeric}")
        rows.append({"LOOKBACK": value, "position_diff": position_diff, **numeric})
    (RUN / "overlap_checks.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"PASS: {len(rows)} overlapping paths match the prior formal grid")


if __name__ == "__main__":
    main()
