"""Cross-check the raw Top1 signal with a separate weighted-regression formula."""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[1]
L1 = ROOT / "outputs/recert_l1_20260926"
ASSETS = ("159915.SZ", "159941.SZ", "513030.SH", "513520.SH", "159985.SZ", "518880.SH")


def score_array(prices, n):
    x = np.arange(n, dtype=float)
    w = np.arange(1, n + 1, dtype=float)
    x_bar = np.average(x, weights=w)
    basis = w * (x - x_bar)
    denom = np.sum(w * (x - x_bar) ** 2)
    out = np.full((len(prices), len(ASSETS)), np.nan)
    for col, code in enumerate(ASSETS):
        values = prices[code].to_numpy(float)
        windows = np.lib.stride_tricks.sliding_window_view(values, n)
        valid = np.isfinite(windows).all(axis=1) & (windows > 0).all(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            y = np.log(windows)
            valid &= (np.max(y, axis=1) - np.min(y, axis=1)) > 1e-12
        slope = y @ basis / denom
        annual = slope * 252.0
        valid &= np.isfinite(annual) & (annual <= math.log(np.finfo(float).max))
        with np.errstate(over="ignore", invalid="ignore"):
            score = np.exp(annual) - 1.0
        score[~valid] = np.nan
        out[n - 1:, col] = score
    return out


def main():
    manifest = json.loads((L1 / "capture_manifest.json").read_text(encoding="utf-8"))
    prices = pd.read_csv(manifest["aligned"]["path"], parse_dates=["date"]).set_index("date")
    mismatch_count = 0
    total = 0
    selected_below_formal_r2 = 0
    selected_above_formal_cap = 0
    for n in range(5, 100, 2):
        curve = pd.read_csv(RUN / "daily_outputs" / f"lookback_{n}.csv.gz")
        scores = score_array(prices, n)
        valid = np.isfinite(scores) & (scores > 0)
        ranked = np.where(valid, scores, -np.inf)
        best_idx = np.argmax(ranked, axis=1)
        any_valid = valid.any(axis=1)
        expected = np.where(any_valid, np.array(ASSETS, dtype=object)[best_idx], "CASH")
        actual = curve.best_candidate.fillna("CASH").astype(str).to_numpy()
        mismatches = np.flatnonzero(expected != actual)
        if len(mismatches):
            first = int(mismatches[0])
            raise RuntimeError(f"lookback_{n} best candidate mismatch at {curve.date.iloc[first]}: expected={expected[first]} actual={actual[first]}")
        if n == 25:
            rows = np.flatnonzero(any_valid)
            selected_scores = scores[rows, best_idx[rows]]
            selected_r2 = np.array([curve.iloc[i][f"r2_{expected[i]}"] for i in rows], dtype=float)
            selected_below_formal_r2 = int(np.sum(selected_r2 < .25))
            selected_above_formal_cap = int(np.sum(selected_scores >= 5.5))
        total += len(curve)
    (RUN / "signal_audit.json").write_text(json.dumps({
        "candidate_count": 48,
        "candidate_days_checked": total,
        "best_candidate_mismatches": mismatch_count,
        "pure25_selected_days_below_formal_r2_0p25": selected_below_formal_r2,
        "pure25_selected_days_at_or_above_formal_score_cap_5p5": selected_above_formal_cap,
        "method": "independent weighted-slope closed form on L1 aligned closes; Top1 among finite Score>0",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PASS: {total} candidate-days of independent Top1 signals; pure25 below-R2={selected_below_formal_r2}, above-cap={selected_above_formal_cap}")


if __name__ == "__main__":
    main()
