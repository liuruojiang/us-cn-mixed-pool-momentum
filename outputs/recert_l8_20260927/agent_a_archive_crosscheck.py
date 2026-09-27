"""Compare independent L8 paths to saved pre-L8 L2/L3/L5/L6 paths."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
L2 = ROOT / "outputs/recert_l2_20260926"
L3 = ROOT / "outputs/recert_l3_20260926"
L5 = ROOT / "outputs/recert_l5_20260926"
L6 = ROOT / "outputs/recert_l6_20260926"
refs = {
    "formal_111": L2 / "formal_daily_20260924.csv.gz",
    "gate_011": L5 / "daily_score_floor_off.csv.gz",
    "gate_101": L5 / "daily_score_ceiling_off.csv.gz",
    "gate_110": L5 / "daily_r2_off.csv.gz",
    "gate_001": L5 / "daily_floor_ceiling_off.csv.gz",
    "gate_010": L5 / "daily_floor_r2_off.csv.gz",
    "gate_100": L5 / "daily_ceiling_r2_off.csv.gz",
    "gate_000": L5 / "daily_all_three_off.csv.gz",
    "weight_p0": L6 / "agent_b_weight_power_0_daily.csv.gz",
    "lookback_29": L6 / "agent_b_lookback_29_daily.csv.gz",
    "lookback_24": L6 / "agent_b_lookback_24_daily.csv.gz",
    "lookback_26": L6 / "agent_b_lookback_26_daily.csv.gz",
    "weight_p075": L6 / "agent_b_weight_power_0p75_daily.csv.gz",
    "weight_p125": L6 / "agent_b_weight_power_1p25_daily.csv.gz",
    "floor_04": L6 / "agent_b_score_floor_0p4_daily.csv.gz",
    "floor_06": L6 / "agent_b_score_floor_0p6_daily.csv.gz",
    "ceiling_525": L6 / "agent_b_score_ceiling_5p25_daily.csv.gz",
    "ceiling_575": L6 / "agent_b_score_ceiling_5p75_daily.csv.gz",
    "r2_0225": L6 / "agent_b_r2_0p225_daily.csv.gz",
    "r2_0275": L6 / "agent_b_r2_0p275_daily.csv.gz",
    "buffer_102": L6 / "agent_b_switch_buffer_1p02_daily.csv.gz",
    "buffer_103": L6 / "agent_b_switch_buffer_1p03_daily.csv.gz",
    "buffer_105": L6 / "agent_b_switch_buffer_1p05_daily.csv.gz",
    "legacy_clean_base": L3 / "baseline_daily_20260924.csv.gz",
}
results = {}
for arm, ref in refs.items():
    actual = pd.read_csv(HERE / "agent_a_daily" / f"{arm}.csv.gz", parse_dates=["date"])
    expected = pd.read_csv(ref, parse_dates=["date"])
    assert actual.date.equals(expected.date), (arm, "date mismatch")
    mismatch = {}
    for col in ("position_before", "position", "trade_target"):
        if col not in expected:
            continue
        a = actual[col].fillna("<NA>").astype(str)
        b = expected[col].fillna("<NA>").astype(str)
        bad = a.ne(b)
        mismatch[col] = {"days": int(bad.sum()), "first": None if not bad.any() else actual.loc[bad,"date"].iloc[0].date().isoformat()}
    maxabs = {}
    for col in ("turnover", "cost", "gross_return", "return", "nav"):
        if col not in expected:
            continue
        x = actual[col].to_numpy(float)
        y = expected[col].to_numpy(float)
        maxabs[col] = float(np.nanmax(np.abs(x-y)))
    results[arm] = {"reference": str(ref.relative_to(ROOT)), "rows": len(actual), "mismatch": mismatch, "maxabs": maxabs}
    if any(v["days"] for v in mismatch.values()) or any(v > 1e-9 for v in maxabs.values()):
        raise AssertionError((arm, results[arm]))
result = {"arms_checked": len(results), "path_days": sum(v["rows"] for v in results.values()),
          "max_nav_abs": max(v["maxabs"].get("nav", 0.0) for v in results.values()), "details": results}
(HERE / "agent_a_archive_crosscheck.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({key: result[key] for key in ("arms_checked", "path_days", "max_nav_abs")}, ensure_ascii=False))
