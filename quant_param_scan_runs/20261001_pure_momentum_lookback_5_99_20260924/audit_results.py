"""Independently recompute the exported annual returns and drawdowns from daily NAV."""

from pathlib import Path

import numpy as np
import pandas as pd


RUN = Path(__file__).resolve().parent
WINDOWS = {"full": None, "last_10y": 2520, "last_5y": 1260,
           "last_3y": 756, "last_1y": 252,
           "six_etf_all_scoreable": pd.Timestamp("2020-01-09")}


def main():
    summary = pd.read_csv(RUN / "scan_summary.csv")
    wide = pd.read_csv(RUN / "window_metrics.csv")
    if len(wide) != 48 or len(summary) != 48 * 6:
        raise RuntimeError("Incomplete result files")
    checked = 0
    for value in range(5, 100, 2):
        candidate = f"lookback_{value}"
        daily = pd.read_csv(RUN / "daily_outputs" / f"{candidate}.csv.gz", parse_dates=["date"])
        if len(daily) != 3594 or not daily.date.is_monotonic_increasing:
            raise RuntimeError(f"Bad dates: {candidate}")
        if not np.isfinite(daily.nav.to_numpy(float)).all() or not (daily.nav > 0).all():
            raise RuntimeError(f"Bad NAV: {candidate}")
        if daily.stop_triggered.any() or daily.buffer_blocked.any() or daily.staged_initial.any() or daily.staged_fill_count.any():
            raise RuntimeError(f"A disabled overlay fired: {candidate}")
        if (daily.cost - daily.turnover * .001).abs().max() > 1e-12:
            raise RuntimeError(f"Cost/turnover mismatch: {candidate}")
        selected = daily.best_candidate.fillna("CASH") != "CASH"
        if (daily.loc[selected, "best_candidate_score"] <= 0).any():
            raise RuntimeError(f"Nonpositive momentum selected: {candidate}")
        row_w = wide.loc[wide.candidate == candidate].iloc[0]
        for segment, n in WINDOWS.items():
            part = daily if n is None else (daily.loc[daily.date >= n] if isinstance(n, pd.Timestamp) else daily.iloc[-n:])
            nav = part.nav.to_numpy(float)
            annual = (nav[-1] / nav[0]) ** (252 / (len(nav) - 1)) - 1
            drawdown = float(np.min(nav / np.maximum.accumulate(nav) - 1))
            row_l = summary.loc[(summary.candidate == candidate) & (summary.segment == segment)].iloc[0]
            for name, got, expected in (("annual", annual, row_l.ann_return),
                                        ("drawdown", drawdown, row_l.max_dd),
                                        ("wide annual", annual, row_w[f"ann_return_{segment}"]),
                                        ("wide drawdown", drawdown, row_w[f"max_dd_{segment}"])):
                if abs(got - expected) > 1e-10:
                    raise RuntimeError(f"{candidate} {segment} {name}: {got} != {expected}")
            checked += 1
    print(f"PASS: {checked} candidate-window pairs independently recomputed from exported NAV")


if __name__ == "__main__":
    main()
