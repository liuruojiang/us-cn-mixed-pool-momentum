"""Read-only independent replay of the L7 report fix on frozen L1 prices."""
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import poe_subd_six_etf_v1_3_bot as bot

OUT = Path(__file__).resolve().parent
L1 = ROOT / "outputs/recert_l1_20260926"
prices = pd.read_csv(L1 / "prices_aligned_qfq_through_20260924.csv.gz", index_col=0, parse_dates=True)
flags = pd.read_csv(L1 / "price_ffill_flags_through_20260924.csv.gz", index_col=0, parse_dates=True).astype(bool)
new_curve = bot.build_curves(prices, bot._build_config(prices.index[-1]), flags)[0].reset_index()
old_curve = pd.read_csv(ROOT / "outputs/recert_l2_20260926/formal_daily_20260924.csv.gz", parse_dates=["date"])
check_cols = ["position_before", "position", "trade_target", "turnover", "cost", "return", "nav"]
assert new_curve.date.equals(old_curve.date)
categorical = ["position_before", "position", "trade_target"]
numeric = [col for col in check_cols if col not in categorical]
curve_delta = {
    "rows": len(new_curve),
    "last": new_curve.date.iloc[-1].date().isoformat(),
    "categorical_mismatch_counts": {col: int((new_curve[col].fillna("<NA>") != old_curve[col].fillna("<NA>")).sum()) for col in categorical},
    "numeric_max_abs_differences": {col: float(np.max(np.abs(new_curve[col].to_numpy(float) - old_curve[col].to_numpy(float)))) for col in numeric},
}
assert all(value == 0 for value in curve_delta["categorical_mismatch_counts"].values())
assert all(value < 1e-10 for value in curve_delta["numeric_max_abs_differences"].values())

reference = json.loads((ROOT / "outputs/recert_l7_20260927/agent_a_metric_probe.json").read_text(encoding="utf-8"))
by_window = {item["window"]: item for item in reference["windows"]}
report_metrics = []
for label, expected in by_window.items():
    actual = bot.calc_performance(old_curve, pd.Timestamp(expected["start"]), pd.Timestamp(expected["end"]))
    differences = {
        field: float(actual[reported] - expected[independent])
        for field, reported, independent in [
            ("annual", "annual", "annual_n_minus_1"),
            ("vol", "vol", "vol_n_minus_1"),
            ("sharpe", "sharpe", "sharpe_n_minus_1"),
            ("maxdd", "maxdd", "maxdd_with_first_nav_base"),
        ]
    }
    assert all(abs(value) < 1e-10 for value in differences.values())
    report_metrics.append({"window": label, "actual": {field: actual[field] for field in ["start", "end", "rows", "annual", "vol", "sharpe", "maxdd"]}, "difference_from_independent": differences})

single_error = ""
try:
    bot.calc_performance(old_curve, pd.Timestamp("2026-09-24"), pd.Timestamp("2026-09-24"))
except Exception as exc:
    single_error = str(exc)
assert "至少需要两个" in single_error

year_rows = bot.calc_yearly_performance(old_curve, bot.EVAL_START, pd.Timestamp("2026-09-24"))
year_2020 = next(row for row in year_rows if row["year"] == 2020)
year_ref = next(row for row in reference["yearly_first_rows"] if row["year"] == 2020)
year_deltas = {
    "return": float(year_2020["return"] - year_ref["actual_calendar_return_with_prior_close"]),
    "vol": float(year_2020["vol"] - year_ref["calendar_vol"]),
    "maxdd": float(year_2020["maxdd"] - year_ref["maxdd_with_prior_close_base"]),
}
assert all(abs(value) < 1e-10 for value in year_deltas.values())

# Counterexample: first calendar-year day loses 10%, then stays flat.
synthetic = pd.DataFrame({
    "date": pd.to_datetime(["2025-12-31", "2026-01-02", "2026-01-05"]),
    "nav": [1.0, 0.9, 0.9], "return": [0.0, -0.1, 0.0],
    "turnover": [0.0] * 3, "exposure_effective": [0.0] * 3,
})
synthetic_year = bot.calc_yearly_performance(synthetic, pd.Timestamp("2026-01-01"), pd.Timestamp("2026-12-31"))[0]
assert math.isclose(synthetic_year["return"], -0.1, abs_tol=1e-12)
assert math.isclose(synthetic_year["maxdd"], -0.1, abs_tol=1e-12)

result = {
    "source_sha256": hashlib.sha256((ROOT / "poe_subd_six_etf_v1_3_bot.py").read_bytes()).hexdigest(),
    "curve_parity_with_l2": curve_delta,
    "five_windows": report_metrics,
    "single_row_error": single_error,
    "year_2020": year_2020,
    "year_2020_difference_from_independent": year_deltas,
    "synthetic_first_day_loss": {"return": synthetic_year["return"], "maxdd": synthetic_year["maxdd"]},
}
(OUT / "agent_a_postfix_probe.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
