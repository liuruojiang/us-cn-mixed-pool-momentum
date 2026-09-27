"""Independent L3 clean-baseline identity/clock audit; no production imports.

Runs on the preserved old panel and the L1 refreshed panel. The old panel
comparison is against the preserved r2_off_buffer_1.00 daily output.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
OLD_DIR = ROOT / "quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer"
OLD_CURVE = OLD_DIR / "daily_outputs/r2_off_buffer_1.00.csv.gz"
OLD_PRICE = OLD_DIR / "price_snapshot_qfq.csv.gz"
NEW_DIR = ROOT / "outputs/recert_l1_20260926"
NEW_PRICE = NEW_DIR / "prices_aligned_qfq_through_20260924.csv.gz"
NEW_FLAGS = NEW_DIR / "price_ffill_flags_through_20260924.csv.gz"
CODES = ["159915.SZ", "159941.SZ", "513030.SH", "513520.SH", "159985.SZ", "518880.SH"]


def read_prices(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=["date"]).set_index("date")[CODES].astype(float)


def score_25(window: np.ndarray) -> tuple[float, float]:
    if not np.isfinite(window).all() or (window <= 0).any():
        return math.nan, math.nan
    y = np.log(window)
    if np.ptp(y) <= 1e-12:
        return math.nan, math.nan
    # Weighted moments rather than the project's polyfit path.
    y = y - y[0]
    x = np.arange(25, dtype=float)
    w = np.arange(1, 26, dtype=float)
    xb, yb = np.average(x, weights=w), np.average(y, weights=w)
    cov = np.dot(w, (x - xb) * (y - yb))
    varx = np.dot(w, (x - xb) ** 2)
    slope = cov / varx
    intercept = yb - slope * xb
    residual = y - (intercept + slope * x)
    r2 = max(0., 1. - np.dot(w, residual ** 2) / np.dot(w, (y - yb) ** 2))
    return math.expm1(slope * 252.), r2


def replay(prices: pd.DataFrame, flags: pd.DataFrame, *, score_min: float = 0.,
           score_max: float = 5., r2_min: float | None = None) -> pd.DataFrame:
    vals = prices.to_numpy(float)
    flagged = flags[CODES].reindex(prices.index).fillna(False).to_numpy(bool)
    position, nav = "CASH", 1.
    rows = []
    for t, date in enumerate(prices.index):
        old = position
        scores: dict[str, float] = {}
        r2_map: dict[str, float] = {}
        if t >= 24:
            for j, code in enumerate(CODES):
                sc, r2 = score_25(vals[t - 24:t + 1, j])
                if math.isfinite(r2):
                    r2_map[code] = r2
                if score_min < sc < score_max and (r2_min is None or r2 >= r2_min):
                    scores[code] = sc
        best = max(scores, key=scores.get) if scores else "CASH"
        target = best
        blocked = False
        if target != old:
            legs = ([old] if old != "CASH" else []) + ([target] if target != "CASH" else [])
            blocked = any(flagged[t, CODES.index(code)] for code in legs)
            if blocked:
                target = old
        gross = 0. if old == "CASH" or t == 0 else vals[t, CODES.index(old)] / vals[t - 1, CODES.index(old)] - 1.
        turnover = 0. if target == old else (int(old != "CASH") + int(target != "CASH"))
        cost = turnover * .001
        prior_nav = nav
        nav = prior_nav * (1. + gross) * (1. - cost)
        position = target
        rows.append({"date": date, "position_before": old, "best_candidate": best, "position": position,
                     "gross_return": gross, "turnover": turnover, "cost": cost,
                     "return": nav / prior_nav - 1., "nav": nav,
                     "best_candidate_score": scores.get(best, math.nan),
                     "best_candidate_r2": r2_map.get(best, math.nan),
                     "trade_blocked_by_stale_price": blocked})
    return pd.DataFrame(rows).set_index("date")


def compare(a: pd.DataFrame, b: pd.DataFrame) -> dict:
    if not a.index.equals(b.index):
        raise AssertionError("date index differs")
    out = {}
    for col in ("position_before", "best_candidate", "position"):
        mismatch = a[col].fillna("CASH").ne(b[col].fillna("CASH"))
        out[f"{col}_mismatch"] = int(mismatch.sum())
        out[f"{col}_first_mismatch"] = str(mismatch[mismatch].index[0].date()) if mismatch.any() else None
    for col in ("gross_return", "turnover", "cost", "return", "nav", "best_candidate_score"):
        x, y = a[col].to_numpy(float), b[col].to_numpy(float)
        mismatch = np.isnan(x) != np.isnan(y)
        diffs = np.abs(x - y)
        out[f"{col}_na_mismatch"] = int(mismatch.sum())
        out[f"{col}_max_abs_diff"] = float(np.nanmax(diffs)) if np.isfinite(diffs).any() else 0.
    return out


def main() -> None:
    old_prices = read_prices(OLD_PRICE)
    old_saved = pd.read_csv(OLD_CURVE, parse_dates=["date"]).set_index("date")
    old_flags = old_saved[[f"price_ffill_{c}" for c in CODES]].rename(columns={f"price_ffill_{c}": c for c in CODES}).astype(bool)
    old_replay = replay(old_prices, old_flags)
    bridge = compare(old_replay, old_saved)
    assert all(bridge[f"{c}_mismatch"] == 0 for c in ("position_before", "best_candidate", "position"))
    assert all(bridge[f"{c}_na_mismatch"] == 0 for c in ("gross_return", "turnover", "cost", "return", "nav", "best_candidate_score"))
    assert all(bridge[f"{c}_max_abs_diff"] < 1e-10 for c in ("gross_return", "turnover", "cost", "return", "nav", "best_candidate_score"))
    new_prices = read_prices(NEW_PRICE)
    new_flags = pd.read_csv(NEW_FLAGS, parse_dates=["date"]).set_index("date")
    if set(CODES) != set(new_flags.columns):
        new_flags = new_flags.rename(columns={f"price_ffill_{c}": c for c in CODES})
    new_replay = replay(new_prices, new_flags)
    new_replay.to_csv(OUT / "agent_a_independent_clean_daily.csv.gz", index_label="date", compression="gzip")
    truncated_prices = new_prices.loc[:"2024-12-31"]
    truncated = replay(truncated_prices, new_flags.loc[truncated_prices.index])
    prefix_check = compare(truncated, new_replay.loc[truncated.index])
    assert all(prefix_check[f"{c}_mismatch"] == 0 for c in ("position_before", "best_candidate", "position"))
    assert prefix_check["nav_max_abs_diff"] == 0.
    wrong_v13_gates = replay(new_prices, new_flags, score_min=.5, score_max=5.5, r2_min=.25)
    wrong_no_floor = replay(new_prices, new_flags, score_min=-math.inf)
    wrong_r2_gate = replay(new_prices, new_flags, r2_min=.2)
    variant_checks = {}
    for name, variant in (("v13_gates", wrong_v13_gates), ("no_score_floor", wrong_no_floor), ("r2_0p20", wrong_r2_gate)):
        diff = variant.position.ne(new_replay.position)
        variant_checks[name] = {"different_position_days": int(diff.sum()),
                                "first_position_difference": str(diff[diff].index[0].date()) if diff.any() else None,
                                "nav_end": float(variant.nav.iloc[-1])}
    old_prefix = compare(new_replay.loc[old_replay.index], old_replay)
    assert all(old_prefix[f"{c}_mismatch"] == 0 for c in ("position_before", "best_candidate", "position"))
    assert old_prefix["nav_max_abs_diff"] < 1e-10
    result = {"old_rows": len(old_replay), "new_rows": len(new_replay),
              "old_bridge": bridge, "new_old_prefix": old_prefix,
              "future_data_prefix": prefix_check,
              "old_nav_end": float(old_replay.nav.iloc[-1]), "new_nav_end": float(new_replay.nav.iloc[-1]),
              "new_trade_days": int(new_replay.turnover.gt(0).sum()),
              "new_trade_blocked_days": int(new_replay.trade_blocked_by_stale_price.sum()),
              "wrong_baseline_counterexamples": variant_checks}
    (OUT / "agent_a_identity_results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
