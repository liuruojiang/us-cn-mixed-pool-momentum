"""Recompute every window metric from saved daily NAV without the strategy metrics helper."""

from pathlib import Path

import numpy as np
import pandas as pd


RUN = Path(__file__).resolve().parent
WINDOWS = {"full": None, "last_10y": 2520, "last_5y": 1260,
           "last_3y": 756, "last_1y": 252,
           "six_etf_all_scoreable": pd.Timestamp("2020-01-09")}
POWERS = [i / 2 for i in range(11)]


def label(power):
    return f"weight_p{power:g}".replace(".", "p")


def main():
    summary = pd.read_csv(RUN / "scan_summary.csv")
    wide = pd.read_csv(RUN / "window_metrics.csv")
    expected = [label(p) for p in POWERS]
    if wide.candidate.tolist() != expected or len(summary) != len(expected) * len(WINDOWS):
        raise RuntimeError("Incomplete candidate or window rows")
    checked = 0
    for candidate in expected:
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
            for tag, expected_value, actual_value in (
                ("long annual", row_l.ann_return, annual),
                ("long drawdown", row_l.max_dd, drawdown),
                ("wide annual", row_w[f"ann_return_{segment}"], annual),
                ("wide drawdown", row_w[f"max_dd_{segment}"], drawdown),
            ):
                if abs(expected_value - actual_value) > 1e-10:
                    raise RuntimeError(f"{candidate} {segment} {tag}: {expected_value} != {actual_value}")
            checked += 1
    print(f"PASS: {checked} candidate-window metric pairs recomputed from exported NAV")


if __name__ == "__main__":
    main()
