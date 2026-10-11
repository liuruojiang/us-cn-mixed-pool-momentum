"""Independent NAV-based review of report statistics; does not import the bot."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
daily = pd.read_csv(ROOT / "outputs/recert_l2_20260926/formal_daily_20260924.csv.gz", parse_dates=["date"])
daily = daily.sort_values("date").reset_index(drop=True)
assert len(daily) == 3594 and daily.date.iloc[-1] == pd.Timestamp("2026-09-24")
windows = {"Full": 3594, "10Y": 2520, "5Y": 1260, "3Y": 756, "1Y": 252}
rows = []
for label, count in windows.items():
    part = daily.tail(count)
    nav = part.nav.to_numpy(float)
    observed = nav[1:] / nav[:-1] - 1.0
    stored = part["return"].to_numpy(float)[1:]
    assert np.max(np.abs(observed - stored)) < 1e-12
    first_zero = np.r_[0.0, observed]
    total = nav[-1] / nav[0] - 1.0
    row = {
        "window": label,
        "start": part.date.iloc[0].date().isoformat(),
        "end": part.date.iloc[-1].date().isoformat(),
        "nav_rows": count,
        "observed_changes": count - 1,
        "total": total,
        "annual_n_minus_1": float((nav[-1] / nav[0]) ** (252.0 / (count - 1)) - 1.0),
        "annual_n_with_injected_zero": float((nav[-1] / nav[0]) ** (252.0 / count) - 1.0),
        "vol_n_minus_1": float(np.std(observed, ddof=0) * np.sqrt(252.0)),
        "vol_with_injected_zero": float(np.std(first_zero, ddof=0) * np.sqrt(252.0)),
        "sharpe_n_minus_1": float(np.mean(observed) / np.std(observed, ddof=0) * np.sqrt(252.0)),
        "sharpe_with_injected_zero": float(np.mean(first_zero) / np.std(first_zero, ddof=0) * np.sqrt(252.0)),
        "maxdd_with_first_nav_base": float((nav / np.maximum.accumulate(nav) - 1.0).min()),
    }
    rows.append(row)

yearly = []
sub = daily[(daily.date >= pd.Timestamp("2020-01-02")) & (daily.date <= pd.Timestamp("2026-09-24"))]
for year, part in sub.groupby(sub.date.dt.year):
    first = part.iloc[0]
    idx = int(first.name)
    before = daily.iloc[idx - 1] if idx > 0 else None
    actual_ret = part["return"].to_numpy(float)
    reported_ret = actual_ret.copy()
    if year == 2020:
        reported_ret[0] = 0.0
    reported_wealth = np.cumprod(1.0 + reported_ret)
    actual_wealth = np.cumprod(1.0 + actual_ret)
    reported_dd = reported_wealth / np.maximum.accumulate(reported_wealth) - 1.0
    actual_dd_with_prior_base = np.r_[1.0, actual_wealth] / np.maximum.accumulate(np.r_[1.0, actual_wealth]) - 1.0
    yearly.append({
        "year": int(year),
        "display_start": first.date.date().isoformat(),
        "first_day_stored_return": float(first["return"]),
        "prior_row_date": None if before is None else before.date.date().isoformat(),
        "first_day_nav_change_from_prior_row": None if before is None else float(first.nav / before.nav - 1.0),
        "first_year_report_zeroes_first_return": bool(year == 2020),
        "reported_calendar_return": float(reported_wealth[-1] - 1.0),
        "actual_calendar_return_with_prior_close": float(actual_wealth[-1] - 1.0),
        "reported_maxdd": float(reported_dd.min()),
        "maxdd_with_prior_close_base": float(actual_dd_with_prior_base.min()),
        "reported_vol": float(np.std(reported_ret, ddof=0) * np.sqrt(252.0)),
        "calendar_vol": float(np.std(actual_ret, ddof=0) * np.sqrt(252.0)),
    })

result = {"windows": rows, "yearly_first_rows": yearly}
(OUT / "agent_a_metric_probe.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
