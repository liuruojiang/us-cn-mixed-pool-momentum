"""Independently reconstruct weighted-slope Score, R² gate, and Top1 target."""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[1]
L1 = ROOT / "outputs/recert_l1_20260926"
ASSETS = ("159915.SZ", "159941.SZ", "513030.SH", "513520.SH", "159985.SZ", "518880.SH")
LOOKBACK = 25
POWERS = [i / 2 for i in range(11)]


def label(power):
    return f"weight_p{power:g}".replace(".", "p")


def independent_scores_and_r2(prices, power):
    n = LOOKBACK
    x = np.arange(n, dtype=float)
    w = np.arange(1, n + 1, dtype=float) ** power
    xbar = np.average(x, weights=w)
    basis = w * (x - xbar)
    denom = np.sum(w * (x - xbar) ** 2)
    score_out = np.full((len(prices), len(ASSETS)), np.nan)
    r2_out = np.full_like(score_out, np.nan)
    for col, code in enumerate(ASSETS):
        values = prices[code].to_numpy(float)
        windows = np.lib.stride_tricks.sliding_window_view(values, n)
        valid = np.isfinite(windows).all(axis=1) & (windows > 0).all(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            y = np.log(windows)
            valid &= (np.max(y, axis=1) - np.min(y, axis=1)) > 1e-12
        slope = y @ basis / denom
        ybar = np.sum(y * w, axis=1) / np.sum(w)
        fit = ybar[:, None] + slope[:, None] * (x - xbar)
        ss_tot = np.sum(w * (y - ybar[:, None]) ** 2, axis=1)
        ss_res = np.sum(w * (y - fit) ** 2, axis=1)
        valid &= (ss_tot > 0) & np.isfinite(slope)
        with np.errstate(over="ignore", invalid="ignore"):
            annual_log = slope * 252.0
            score = np.exp(annual_log) - 1.0
        valid &= annual_log <= math.log(np.finfo(float).max)
        r2 = np.maximum(0.0, 1.0 - ss_res / ss_tot)
        score[~valid] = np.nan
        r2[~valid] = np.nan
        score_out[n - 1:, col] = score
        r2_out[n - 1:, col] = r2
    return score_out, r2_out


def main():
    manifest = json.loads((L1 / "capture_manifest.json").read_text(encoding="utf-8"))
    prices = pd.read_csv(manifest["aligned"]["path"], parse_dates=["date"]).set_index("date")
    rejected = {}
    checked = 0
    for power in POWERS:
        candidate = label(power)
        curve = pd.read_csv(RUN / "daily_outputs" / f"{candidate}.csv.gz")
        scores, r2 = independent_scores_and_r2(prices, power)
        passes_score = np.isfinite(scores) & (scores > .5) & (scores < 5.5)
        rejected[str(power)] = int(np.sum(passes_score & (r2 < .25)))
        valid = passes_score & (r2 >= .25)
        ranked = np.where(valid, scores, -np.inf)
        best_idx = np.argmax(ranked, axis=1)
        any_valid = valid.any(axis=1)
        expected = np.where(any_valid, np.array(ASSETS, dtype=object)[best_idx], "CASH")
        actual = curve.best_candidate.fillna("CASH").astype(str).to_numpy()
        mismatches = np.flatnonzero(expected != actual)
        if len(mismatches):
            i = int(mismatches[0])
            raise RuntimeError(f"{candidate} first target mismatch {curve.date.iloc[i]}: {expected[i]} != {actual[i]}")
        checked += len(curve)
    report = {"candidate_count": len(POWERS), "candidate_days_checked": checked,
              "target_mismatches": 0, "score_passing_asset_days_rejected_by_r2": rejected,
              "method": "separate weighted-moment slope and R2 computation on L1 closes; strict Score and R2 gate before Top1"}
    (RUN / "signal_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"PASS: {checked} candidate-days of independent Score/R2/Top1 checks")


if __name__ == "__main__":
    main()
