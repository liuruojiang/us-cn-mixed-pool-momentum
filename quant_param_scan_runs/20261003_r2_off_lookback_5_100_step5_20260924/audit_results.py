"""Recompute all displayed metrics from the exported daily account NAVs."""

from pathlib import Path

import numpy as np
import pandas as pd


RUN = Path(__file__).resolve().parent
WINDOWS = {"full": None, "last_10y": 2520, "last_5y": 1260,
           "last_3y": 756, "last_1y": 252,
           "six_etf_all_scoreable": pd.Timestamp("2020-05-07")}
CANDIDATES = ["formal_25_r2_on"] + [f"r2_off_{n}" for n in range(5, 101, 5)]


def main():
    summary = pd.read_csv(RUN / "scan_summary.csv")
    wide = pd.read_csv(RUN / "window_metrics.csv")
    if (wide.candidate.tolist() != CANDIDATES
            or len(summary) != len(CANDIDATES) * len(WINDOWS)):
        raise RuntimeError("Incomplete candidates or window rows")
    checked = 0
    for candidate in CANDIDATES:
        daily = pd.read_csv(RUN / "daily_outputs" / f"{candidate}.csv.gz", parse_dates=["date"])
        if len(daily) != 3594 or not daily.date.is_monotonic_increasing:
            raise RuntimeError(f"Bad dates: {candidate}")
        if not np.isfinite(daily.nav.to_numpy(float)).all() or not (daily.nav > 0).all():
            raise RuntimeError(f"Bad NAV: {candidate}")
        row_w = wide.loc[wide.candidate == candidate].iloc[0]
        for segment, selector in WINDOWS.items():
            part = (daily if selector is None else
                    daily.loc[daily.date >= selector] if isinstance(selector, pd.Timestamp)
                    else daily.iloc[-selector:])
            nav = part.nav.to_numpy(float)
            annual = (nav[-1] / nav[0]) ** (252 / (len(nav) - 1)) - 1
            drawdown = float(np.min(nav / np.maximum.accumulate(nav) - 1))
            row_l = summary.loc[(summary.candidate == candidate) & (summary.segment == segment)].iloc[0]
            for label, expected, actual in (
                ("long annual", row_l.ann_return, annual),
                ("long drawdown", row_l.max_dd, drawdown),
                ("wide annual", row_w[f"ann_return_{segment}"], annual),
                ("wide drawdown", row_w[f"max_dd_{segment}"], drawdown),
            ):
                if abs(expected - actual) > 1e-10:
                    raise RuntimeError(f"{candidate} {segment} {label}: {expected} != {actual}")
            checked += 1
    print(f"PASS: {checked} candidate-window pairs independently recomputed")


if __name__ == "__main__":
    main()
