"""Independent weighted-moment reconstruction of Score, R² and Top1."""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[1]
L1 = ROOT / "outputs/recert_l1_20260926"
ASSETS = ("159915.SZ", "159941.SZ", "513030.SH", "513520.SH", "159985.SZ", "518880.SH")
GRID = list(range(5, 101, 5))


def label(value):
    return f"r2_window_{value:03d}"


def independent_fit(prices, size):
    x = np.arange(size, dtype=float)
    w = np.arange(1, size + 1, dtype=float)
    xbar = np.average(x, weights=w)
    basis = w * (x - xbar)
    denom = np.sum(w * (x - xbar) ** 2)
    score_out = np.full((len(prices), len(ASSETS)), np.nan)
    r2_out = np.full_like(score_out, np.nan)
    for col, code in enumerate(ASSETS):
        values = prices[code].to_numpy(float)
        windows = np.lib.stride_tricks.sliding_window_view(values, size)
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
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            annual_log = slope * 252.0
            score = np.exp(annual_log) - 1.0
            r2 = np.maximum(0.0, 1.0 - ss_res / ss_tot)
        valid &= annual_log <= math.log(np.finfo(float).max)
        score[~valid] = np.nan
        r2[~valid] = np.nan
        score_out[size - 1:, col] = score
        r2_out[size - 1:, col] = r2
    return score_out, r2_out


def main():
    manifest = json.loads((L1 / "capture_manifest.json").read_text(encoding="utf-8"))
    prices = pd.read_csv(manifest["aligned"]["path"], parse_dates=["date"]).set_index("date")
    score25, _ = independent_fit(prices, 25)
    score_pass = np.isfinite(score25) & (score25 > .5) & (score25 < 5.5)
    eligible_days = {}
    max_r2_error = 0.0
    checked = 0
    for size in GRID:
        candidate = label(size)
        curve = pd.read_csv(RUN / "daily_outputs" / f"{candidate}.csv.gz")
        _, r2 = independent_fit(prices, size)
        # The formal account engine does not request any signal before Score25
        # itself has enough observations, even when the R² window is shorter.
        r2[:24, :] = np.nan
        valid = score_pass & (r2 >= .25)
        ranked = np.where(valid, score25, -np.inf)
        best_idx = np.argmax(ranked, axis=1)
        any_valid = valid.any(axis=1)
        expected = np.where(any_valid, np.array(ASSETS, dtype=object)[best_idx], "CASH")
        actual = curve.best_candidate.fillna("CASH").astype(str).to_numpy()
        mismatches = np.flatnonzero(expected != actual)
        if len(mismatches):
            i = int(mismatches[0])
            raise RuntimeError(f"{candidate} Top1 mismatch {curve.date.iloc[i]}: {expected[i]} != {actual[i]}")
        observed_r2 = curve[[f"r2_{code}" for code in ASSETS]].to_numpy(float)
        if not np.array_equal(np.isnan(r2), np.isnan(observed_r2)):
            raise RuntimeError(f"{candidate} R2 validity mismatch")
        error = float(np.nanmax(np.abs(r2 - observed_r2)))
        max_r2_error = max(max_r2_error, error)
        if error > 1e-10:
            raise RuntimeError(f"{candidate} R2 numeric mismatch: {error}")
        eligible_days[str(size)] = int(any_valid.sum())
        checked += len(curve)
    (RUN / "signal_audit.json").write_text(json.dumps({
        "candidate_count": len(GRID), "candidate_days_checked": checked,
        "target_mismatches": 0, "max_r2_absolute_error": max_r2_error,
        "days_with_eligible_candidate": eligible_days,
        "method": "independent weighted-moment Score25 and R2-N on L1 closes; strict Score gate and R2 >= 0.25 before Top1"
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PASS: {checked} candidate-days; max R2 error {max_r2_error:.3g}")


if __name__ == "__main__":
    main()
