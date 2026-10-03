"""Check R²-off Top1 candidates using an independent weighted-slope formula."""

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[1]
L1 = ROOT / "outputs/recert_l1_20260926"
OLD_AUDIT = RUN.parent / "20261001_pure_momentum_lookback_5_99_20260924" / "audit_signals.py"
spec = importlib.util.spec_from_file_location("independent_weighted_slope_audit", OLD_AUDIT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def main():
    manifest = json.loads((L1 / "capture_manifest.json").read_text(encoding="utf-8"))
    prices = pd.read_csv(manifest["aligned"]["path"], parse_dates=["date"]).set_index("date")
    first_scoreable = {}
    eligible_below_r2 = 0
    checked = 0
    for n in range(5, 101, 5):
        curve = pd.read_csv(RUN / "daily_outputs" / f"r2_off_{n}.csv.gz")
        scores = module.score_array(prices, n)
        valid = np.isfinite(scores) & (scores > 0.5) & (scores < 5.5)
        ranked = np.where(valid, scores, -np.inf)
        best_idx = np.argmax(ranked, axis=1)
        any_valid = valid.any(axis=1)
        expected = np.where(any_valid, np.array(module.ASSETS, dtype=object)[best_idx], "CASH")
        actual = curve.best_candidate.fillna("CASH").astype(str).to_numpy()
        mismatches = np.flatnonzero(expected != actual)
        if len(mismatches):
            i = int(mismatches[0])
            raise RuntimeError(f"r2_off_{n} mismatch on {curve.date.iloc[i]}: {expected[i]} != {actual[i]}")
        first_scoreable[str(n)] = str(curve.date.iloc[np.flatnonzero(any_valid)[0]]) if any_valid.any() else None
        if n == 25:
            rows = np.flatnonzero(any_valid)
            selected_r2 = np.array([curve.iloc[i][f"r2_{expected[i]}"] for i in rows], dtype=float)
            eligible_below_r2 = int(np.sum(selected_r2 < 0.25))
        checked += len(curve)
    report = {"candidate_count": 20, "candidate_days_checked": checked,
              "best_candidate_mismatches": 0,
              "r2_off_25_selected_days_below_formal_threshold": eligible_below_r2,
              "first_scoreable_candidate_date": first_scoreable,
              "method": "independent weighted-slope closed form; strict 0.5<Score<5.5; Top1; no R2 gate"}
    (RUN / "signal_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"PASS: {checked} candidate-days; R2-off 25 selected below 0.25 on {eligible_below_r2} days")


if __name__ == "__main__":
    main()
