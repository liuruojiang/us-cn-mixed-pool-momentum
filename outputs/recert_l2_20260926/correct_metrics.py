"""L2 corrected display metrics from saved formal daily NAV, with first NAV as anchor."""

from pathlib import Path

import numpy as np
import pandas as pd


OUT = Path(__file__).resolve().parent
DAILY = OUT / "formal_daily_20260924.csv.gz"
OFFICIAL = OUT / "formal_metrics_20260924.csv"
TARGET = OUT / "corrected_metrics_20260924.csv"


def main():
    daily = pd.read_csv(DAILY, parse_dates=["date"])
    official = pd.read_csv(OFFICIAL).set_index("window")
    if not daily["date"].is_monotonic_increasing or not daily["date"].is_unique:
        raise ValueError("Invalid daily dates")
    nav = daily["nav"].to_numpy(float)
    gross = daily["gross_return"].to_numpy(float)
    fee = daily["cost"].to_numpy(float)
    previous = np.r_[1.0, nav[:-1]]
    assert np.allclose(nav, previous * (1 + gross) * (1 - fee), rtol=1e-12, atol=1e-12)
    assert np.allclose(daily["return"].to_numpy(float), nav / previous - 1, rtol=0, atol=1e-12)
    assert np.allclose(daily["buy_delta"] + daily["sell_delta"], daily["turnover"], rtol=0, atol=1e-12)
    daily["fee_initial_capital"] = previous * (1 + gross) * fee
    results = []
    for label, length in [("Full", None), ("10Y", 2520), ("5Y", 1260), ("3Y", 756), ("1Y", 252)]:
        sub = daily if length is None else daily.tail(length)
        wealth = sub["nav"].to_numpy(float) / float(sub["nav"].iloc[0])
        days = len(sub) - 1
        annual = float(wealth[-1] ** (252 / days) - 1)
        peaks = np.maximum.accumulate(np.r_[1.0, wealth])
        drawdowns = np.r_[1.0, wealth] / peaks - 1
        trough = int(np.argmin(drawdowns))
        if trough == 0:
            peak_date = trough_date = str(sub["date"].iloc[0].date())
        else:
            peak_pos = int(np.argmax(np.r_[1.0, wealth][: trough + 1]))
            peak_date = str(sub["date"].iloc[max(peak_pos - 1, 0)].date())
            trough_date = str(sub["date"].iloc[trough - 1].date())
        official_annual = float(official.loc[label, "annual"])
        maxdd = float(drawdowns.min())
        if abs(maxdd - float(official.loc[label, "maxdd"])) > 1e-10:
            raise ValueError(f"Max drawdown differs: {label}")
        results.append({
            "window": label,
            "start": str(sub["date"].iloc[0].date()),
            "end": str(sub["date"].iloc[-1].date()),
            "nav_rows": len(sub),
            "observed_nav_changes": days,
            "total_return": float(wealth[-1] - 1),
            "annual_official_n": official_annual,
            "annual_corrected_n_minus_1": annual,
            "annual_correction_pp": (annual - official_annual) * 100,
            "maxdd": maxdd,
            "maxdd_peak_date": peak_date,
            "maxdd_trough_date": trough_date,
            "model_trade_days": int((sub["turnover"] > 1e-12).sum()),
            "turnover_sum": float(sub["turnover"].sum()),
            "sum_cost_fraction": float(sub["cost"].sum()),
            "fee_sum_initial_capital_units": float(sub["fee_initial_capital"].sum()),
            "avg_carried_exposure": float(sub["fraction_before"].mean()),
            "cash_end_days": int((sub["position"] == "CASH").sum()),
        })
    result = pd.DataFrame(results)
    result.to_csv(TARGET, index=False)
    old_dir = OUT.parents[1] / "outputs/subd_six_etf_v1_3_acceptance_20260904"
    old = pd.read_csv(old_dir / "daily.csv.gz", parse_dates=["date"])
    old_report = pd.read_csv(old_dir / "metrics.csv").set_index("window")
    old_rows = []
    for label, length in [("Full", None), ("10Y", 2520), ("5Y", 1260), ("3Y", 756), ("1Y", 252)]:
        sub = old if length is None else old.tail(length)
        ratio = float(sub["nav"].iloc[-1] / sub["nav"].iloc[0])
        corrected = ratio ** (252 / (len(sub) - 1)) - 1
        reported = float(old_report.loc[label, "annual"])
        old_rows.append({"window": label, "start": str(sub["date"].iloc[0].date()),
                         "end": str(sub["date"].iloc[-1].date()), "rows": len(sub),
                         "annual_old_report_n": reported, "annual_corrected_n_minus_1": corrected,
                         "annual_correction_pp": (corrected - reported) * 100,
                         "maxdd_unchanged": float(old_report.loc[label, "maxdd"])})
    pd.DataFrame(old_rows).to_csv(OUT / "old_20260902_metric_invalidation.csv", index=False)
    print(result.to_string(index=False))


if __name__ == "__main__":
    main()
