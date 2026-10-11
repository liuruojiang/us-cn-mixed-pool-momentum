"""Audit every R² threshold's Top1 target using independent weighted moments."""

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[1]
L1 = ROOT / "outputs/recert_l1_20260926"
AUDIT = RUN.parent / "20261003_formal_weight_power_0_5_step0p5_20260924" / "audit_signals.py"
spec = importlib.util.spec_from_file_location("independent_weighted_moments_for_r2_scan", AUDIT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
GRID = [i / 20 for i in range(41)]


def label(value):
    return f"r2_{value:.2f}".replace(".", "p")


def main():
    manifest = json.loads((L1 / "capture_manifest.json").read_text(encoding="utf-8"))
    prices = pd.read_csv(manifest["aligned"]["path"], parse_dates=["date"]).set_index("date")
    scores, r2 = module.independent_scores_and_r2(prices, 1.0)
    valid_score = np.isfinite(scores) & (scores > .5) & (scores < 5.5)
    max_r2 = float(np.nanmax(r2))
    counts = {}
    checked = 0
    for value in GRID:
        candidate = label(value)
        curve = pd.read_csv(RUN / "daily_outputs" / f"{candidate}.csv.gz")
        valid = valid_score & (r2 >= value)
        ranked = np.where(valid, scores, -np.inf)
        best_idx = np.argmax(ranked, axis=1)
        any_valid = valid.any(axis=1)
        expected = np.where(any_valid, np.array(module.ASSETS, dtype=object)[best_idx], "CASH")
        actual = curve.best_candidate.fillna("CASH").astype(str).to_numpy()
        mismatches = np.flatnonzero(expected != actual)
        if len(mismatches):
            i = int(mismatches[0])
            raise RuntimeError(f"{candidate} first target mismatch {curve.date.iloc[i]}: {expected[i]} != {actual[i]}")
        counts[f"{value:.2f}"] = int(any_valid.sum())
        checked += len(curve)
    report = {"candidate_count": len(GRID), "candidate_days_checked": checked,
              "target_mismatches": 0, "max_observed_weighted_r2": max_r2,
              "days_with_eligible_candidate": counts,
              "method": "separate weighted-moment slope/R2 calculation on L1 closes; strict Score gate then R2 threshold then Top1"}
    (RUN / "signal_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"PASS: {checked} candidate-days; independent max weighted R2={max_r2:.8f}")


if __name__ == "__main__":
    main()
