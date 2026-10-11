from pathlib import Path
import json
import numpy as np
import pandas as pd

RUN = Path(__file__).resolve().parent
OLD = RUN.parent / "20260904_mixed_us_cn_momentum_subd_pure_momentum_core_six_etf_mixed_pool_score_min_absolute_momentum_floor"
checks = []
for label in ("0", "0p2", "0p5"):
    file = f"score_min_{label}.csv.gz"
    new = pd.read_csv(RUN / "daily_outputs" / file, index_col="date")
    old = pd.read_csv(OLD / "daily_outputs" / file, index_col="date")
    assert new.index.equals(old.index), file
    for column in ("return", "nav", "turnover", "fraction_before", "cost"):
        diff = float(np.abs(new[column].to_numpy() - old[column].to_numpy()).max())
        assert diff < (1e-10 if column == "nav" else 1e-12), (file, column, diff)
        checks.append({"candidate": label, "metric": column, "max_abs_diff": diff})
    mismatches = int((new.position != old.position).sum())
    assert mismatches == 0
    checks.append({"candidate": label, "metric": "position_mismatch", "max_abs_diff": mismatches})
pd.DataFrame(checks).to_csv(RUN / "rerun_checks.csv", index=False)
wide = pd.read_csv(RUN / "window_metrics.csv")
segments = ["full", "last_10y", "last_5y", "last_3y", "last_1y"]
base = wide[wide.score_min == 0].iloc[0]
anchor = wide[wide.score_min == 0.5].iloc[0]
rows = []
for _, row in wide.iterrows():
    value = float(row.score_min)
    ret = {s: float(row[f"ann_return_{s}"] - base[f"ann_return_{s}"]) for s in segments}
    dd = {s: float(row[f"max_dd_{s}"] - base[f"max_dd_{s}"]) for s in segments}
    tol = all(ret[s] >= (-0.03 if s in ("last_3y", "last_1y") else -0.01) - 1e-12 for s in segments)
    improve_count = sum(d > 1e-10 for d in dd.values())
    entry = dict(score_min=value, full_mdd_improved=dd["full"] > 1e-10,
                 mdd_improvement_window_count=improve_count, return_tolerance_ok=tol,
                 economic_screen_pass=bool(tol and dd["full"] > 1e-10 and improve_count >= 3),
                 grid_edge=bool(value in (0.2, 1.0)))
    for s in segments:
        entry[f"ann_delta_vs_0_{s}_pp"] = ret[s] * 100
        entry[f"mdd_improve_vs_0_{s}_pp"] = dd[s] * 100
        entry[f"ann_delta_vs_0p5_{s}_pp"] = float(row[f"ann_return_{s}"] - anchor[f"ann_return_{s}"]) * 100
    rows.append(entry)
ridge = pd.DataFrame(rows)
ridge.to_csv(RUN / "ridge_width.csv", index=False)
print(ridge[["score_min", "return_tolerance_ok", "mdd_improvement_window_count", "economic_screen_pass"]].to_string(index=False))
print("Rerun max diff:", max(row["max_abs_diff"] for row in checks))
meta_path = RUN / "scan_meta.json"
meta = json.loads(meta_path.read_text(encoding="utf-8"))
meta["rerun_parity"] = {"values": [0.0, 0.2, 0.5], "passed": True,
                       "max_abs_diff": max(row["max_abs_diff"] for row in checks)}
meta["width_screen"] = {"reference": "score_min_0", "return_loss_tolerance_pp": {"full": 1, "10Y": 1, "5Y": 1, "3Y": 3, "1Y": 3},
                       "required_mdd_improvement_windows": 3, "full_mdd_improvement_required": True,
                       "note": "economic screen is not independent OOS validation"}
meta["outputs"]["ridge_width"] = str(RUN / "ridge_width.csv")
meta["outputs"]["rerun_checks"] = str(RUN / "rerun_checks.csv")
meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
