"""Independent L4 single-gate ablations on the frozen L1 six-ETF panel.

No V1.3 strategy function is imported. Prices and the immutable L2 formal
curve are the only inputs. Run: python -X utf8 outputs/recert_l4_20260926/agent_a_independent_ablation.py
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
L1 = ROOT / "outputs/recert_l1_20260926"
L2 = ROOT / "outputs/recert_l2_20260926"
ASSETS = ("159915.SZ", "159941.SZ", "513030.SH", "513520.SH", "159985.SZ", "518880.SH")
SETTINGS = {
    "formal_independent": (0.5, 5.5, 0.25),
    "floor_off": (-math.inf, 5.5, 0.25),
    "ceiling_off": (0.5, math.inf, 0.25),
    "r2_off": (0.5, 5.5, None),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score_and_r2(panel: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Weighted covariance/variance calculation, independent of np.polyfit."""
    n, m = panel.shape
    score = np.full((n, m), np.nan)
    r2 = np.full((n, m), np.nan)
    x = np.arange(25, dtype=float)
    w = np.arange(1, 26, dtype=float)
    wx = np.dot(w, x) / w.sum()
    xx = np.dot(w, (x - wx) ** 2)
    for t in range(24, n):
        for j in range(m):
            values = panel[t - 24 : t + 1, j]
            if not np.isfinite(values).all() or np.any(values <= 0):
                continue
            y = np.log(values)
            if np.ptp(y) <= 1e-12:
                continue
            wy = np.dot(w, y) / w.sum()
            yy = np.dot(w, (y - wy) ** 2)
            if yy <= 0:
                continue
            slope = np.dot(w, (x - wx) * (y - wy)) / xx
            intercept = wy - slope * wx
            residual = np.dot(w, (y - slope * x - intercept) ** 2)
            r2[t, j] = max(0.0, 1.0 - residual / yy)
            annual = 252 * slope
            if np.isfinite(annual) and annual < math.log(np.finfo(float).max):
                score[t, j] = math.expm1(annual)
    return score, r2


def eligible(score: np.ndarray, r2: np.ndarray, lo: float, hi: float, r2_min: float | None) -> np.ndarray:
    return np.isfinite(score) & (score > lo) & (score < hi) & (
        np.isfinite(r2) & (r2 >= r2_min) if r2_min is not None else True
    )


def select(row_score: np.ndarray, row_eligible: np.ndarray) -> str:
    if not row_eligible.any():
        return "CASH"
    return ASSETS[int(np.argmax(np.where(row_eligible, row_score, -np.inf)))]


def replay(dates: pd.DatetimeIndex, panel: np.ndarray, stale: np.ndarray,
           score: np.ndarray, r2: np.ndarray, lo: float, hi: float,
           r2_min: float | None) -> pd.DataFrame:
    e = eligible(score, r2, lo, hi, r2_min)
    position = "CASH"
    shares, cash, prev_nav = 0.0, 1.0, 1.0
    rows = []
    index = {asset: j for j, asset in enumerate(ASSETS)}
    for t, date in enumerate(dates):
        before = position
        marked = cash if before == "CASH" else shares * panel[t, index[before]]
        if not np.isfinite(marked) or marked <= 0:
            raise ValueError(f"Nonpositive marked wealth at {date}: {before}")
        wanted = select(score[t], e[t])
        to_touch = (before, wanted) if wanted != before else ()
        blocked = any(stale[t, index[a]] for a in to_touch if a != "CASH")
        after = before if blocked else wanted
        turnover = 0 if after == before else int(before != "CASH") + int(after != "CASH")
        cost = 0.001 * turnover
        wealth_after_fee = marked * (1.0 - cost)
        if after == "CASH":
            cash, shares = wealth_after_fee, 0.0
        else:
            cash, shares = 0.0, wealth_after_fee / panel[t, index[after]]
        position = after
        nav = cash if after == "CASH" else shares * panel[t, index[after]]
        rows.append({"date": date, "position_before": before, "wanted": wanted,
                     "position": after, "eligible_count": int(e[t].sum()),
                     "stale_trade_blocked": bool(blocked), "turnover": turnover,
                     "cost": cost, "gross_return": marked / prev_nav - 1.0,
                     "return": nav / prev_nav - 1.0, "nav": nav})
        prev_nav = nav
    return pd.DataFrame(rows)


def compare(a: pd.DataFrame, b: pd.DataFrame) -> dict:
    assert pd.DatetimeIndex(a.date).equals(pd.DatetimeIndex(b.date))
    result = {}
    for col in ("position_before", "position", "turnover", "cost", "gross_return", "return", "nav"):
        if col.startswith("position"):
            result[col + "_mismatch"] = int(np.count_nonzero(a[col].to_numpy() != b[col].to_numpy()))
        else:
            result[col + "_max_abs"] = float(np.max(np.abs(a[col].to_numpy(float) - b[col].to_numpy(float))))
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((L1 / "capture_manifest.json").read_text(encoding="utf-8"))
    for item in ("aligned", "flags"):
        assert sha256(Path(manifest[item]["path"])) == manifest[item]["sha256"]
    price = pd.read_csv(manifest["aligned"]["path"], parse_dates=["date"]).set_index("date")
    flags = pd.read_csv(manifest["flags"]["path"], parse_dates=["date"]).set_index("date")
    formal_path = L2 / "formal_daily_20260924.csv.gz"
    formal = pd.read_csv(formal_path, parse_dates=["date"])
    assert len(price) == 3594 and str(price.index[-1].date()) == "2026-09-24"
    assert price.index.equals(flags.index) and price.index.equals(pd.DatetimeIndex(formal.date))
    panel = price.loc[:, ASSETS].to_numpy(dtype=float)
    stale = flags.loc[:, ASSETS].to_numpy(dtype=bool)
    score, r2 = score_and_r2(panel)
    curves = {name: replay(price.index, panel, stale, score, r2, *setting)
              for name, setting in SETTINGS.items()}
    formal_parity = compare(curves["formal_independent"], formal)
    if any(v > 1e-9 for k, v in formal_parity.items() if k.endswith("max_abs")) or any(
        v for k, v in formal_parity.items() if k.endswith("mismatch")
    ):
        raise AssertionError(f"Independent formal replay failed: {formal_parity}")
    all_e = {name: eligible(score, r2, *setting) for name, setting in SETTINGS.items()}
    summary = {"prices_sha256": sha256(Path(manifest["aligned"]["path"])),
               "flags_sha256": sha256(Path(manifest["flags"]["path"])),
               "formal_daily_sha256": sha256(formal_path), "formal_parity": formal_parity,
               "rows": len(price), "cutoff": "2026-09-24", "arms": {}}
    ref = curves["formal_independent"]
    for name, curve in curves.items():
        curve.to_csv(OUT / f"agent_a_{name}_daily.csv.gz", index=False, compression="gzip", float_format="%.17g")
        m = all_e[name] & ~all_e["formal_independent"]
        raw_gate = m.any(axis=1)
        first_trigger = np.flatnonzero(raw_gate)
        wanted_diff = np.flatnonzero(curve.wanted.to_numpy() != ref.wanted.to_numpy())
        position_diff = np.flatnonzero(curve.position.to_numpy() != ref.position.to_numpy())
        first_wanted = int(wanted_diff[0]) if len(wanted_diff) else None
        first_pos = int(position_diff[0]) if len(position_diff) else None
        first_event = None
        if first_wanted is not None:
            t = first_wanted
            first_event = {"date": str(price.index[t].date()), "formal_wanted": str(ref.wanted.iloc[t]),
                           "arm_wanted": str(curve.wanted.iloc[t]), "formal_before": str(ref.position_before.iloc[t]),
                           "arm_before": str(curve.position_before.iloc[t]),
                           "newly_eligible": [{"asset": ASSETS[j], "score": float(score[t,j]),
                                               "r2": float(r2[t,j])} for j in np.flatnonzero(m[t])],
                           "winner_score": float(score[t, ASSETS.index(curve.wanted.iloc[t])]) if curve.wanted.iloc[t] != "CASH" else None}
        selected_newly_eligible = sum(
            bool(m[t, ASSETS.index(asset)]) for t, asset in enumerate(curve.wanted)
            if asset != "CASH"
        )
        if any(curve.wanted.iloc[t] == "CASH" or not m[t, ASSETS.index(curve.wanted.iloc[t])]
               for t in wanted_diff):
            raise AssertionError(f"A changed winner was not rescued by the sole disabled gate: {name}")
        setting = [None if value is None else str(value) if not np.isfinite(value) else value
                   for value in SETTINGS[name]]
        summary["arms"][name] = {
            "setting": setting, "new_eligible_asset_days": int(m.sum()),
            "new_eligible_days": int(raw_gate.sum()),
            "newly_eligible_asset_wins_days": int(selected_newly_eligible),
            "first_new_eligible_date": str(price.index[first_trigger[0]].date()) if len(first_trigger) else None,
            "wanted_diff_days": len(wanted_diff), "first_wanted_diff_date": str(price.index[first_wanted].date()) if first_wanted is not None else None,
            "position_diff_days": len(position_diff), "first_position_diff_date": str(price.index[first_pos].date()) if first_pos is not None else None,
            "first_wanted_event": first_event, "trade_days": int((curve.turnover > 0).sum()),
            "turnover_sum": float(curve.turnover.sum()), "cost_fraction_sum": float(curve.cost.sum()),
            "last_nav": float(curve.nav.iloc[-1]), "stale_trade_blocks": int(curve.stale_trade_blocked.sum()),
            "inactive_trigger_invariant": bool((curve.wanted.loc[~raw_gate].to_numpy() == ref.wanted.loc[~raw_gate].to_numpy()).all())
        }
        if not summary["arms"][name]["inactive_trigger_invariant"]:
            raise AssertionError(f"Gate mutation changed selection without any newly eligible asset: {name}")
    # Prefix check recalculates every score and account state without access to later rows.
    end = int(np.searchsorted(price.index, pd.Timestamp("2024-12-31"), side="right"))
    short_score, short_r2 = score_and_r2(panel[:end])
    assert np.allclose(short_score, score[:end], equal_nan=True, atol=0, rtol=0)
    assert np.allclose(short_r2, r2[:end], equal_nan=True, atol=0, rtol=0)
    for name, setting in SETTINGS.items():
        short = replay(price.index[:end], panel[:end], stale[:end], short_score, short_r2, *setting)
        assert compare(short, curves[name].iloc[:end])["nav_max_abs"] == 0.0
    summary["prefix_no_future_data_through"] = str(price.index[end-1].date())
    b_names = {"formal_independent": "formal_rebuilt", "floor_off": "lower_off",
               "ceiling_off": "upper_off", "r2_off": "r2_off"}
    b_parity = {}
    for name, b_name in b_names.items():
        b_path = OUT / f"agent_b_{b_name}_daily.csv.gz"
        if b_path.exists():
            b_parity[name] = compare(curves[name], pd.read_csv(b_path, parse_dates=["date"]))
            if b_parity[name]["position_mismatch"] or b_parity[name]["turnover_max_abs"] != 0 or b_parity[name]["cost_max_abs"] != 0 or b_parity[name]["nav_max_abs"] > 1e-9:
                raise AssertionError(f"Independent agent disagreement for {name}: {b_parity[name]}")
    summary["other_independent_agent_parity"] = b_parity
    main_names = {"formal_independent": "formal_v1_3", "floor_off": "score_floor_off",
                  "ceiling_off": "score_ceiling_off", "r2_off": "r2_off"}
    main_parity = {}
    for name, main_name in main_names.items():
        main_path = OUT / f"daily_{main_name}_20260924.csv.gz"
        if main_path.exists():
            main_parity[name] = compare(curves[name], pd.read_csv(main_path, parse_dates=["date"]))
            if main_parity[name]["position_mismatch"] or main_parity[name]["turnover_max_abs"] != 0 or main_parity[name]["cost_max_abs"] != 0 or main_parity[name]["nav_max_abs"] > 1e-9:
                raise AssertionError(f"Main runner disagreement for {name}: {main_parity[name]}")
    summary["main_runner_parity"] = main_parity
    activation_path = OUT / "activation_summary.csv"
    if activation_path.exists():
        activation = pd.read_csv(activation_path).set_index("arm")
        activation_parity = {}
        for name, main_name in main_names.items():
            if name == "formal_independent":
                continue
            expected = summary["arms"][name]
            observed = activation.loc[main_name]
            activation_parity[name] = {
                "new_eligible_asset_days": int(observed.new_eligible_asset_days) - expected["new_eligible_asset_days"],
                "new_eligible_days": int(observed.days_with_new_eligible_asset) - expected["new_eligible_days"],
                "best_candidate_diff_days": int(observed.best_candidate_diff_days) - expected["wanted_diff_days"],
                "position_diff_days": int(observed.position_diff_days) - expected["position_diff_days"],
                "first_best_candidate_diff_matches": str(observed.first_best_candidate_diff) == expected["first_wanted_diff_date"],
            }
            if any(v != 0 for k, v in activation_parity[name].items() if k != "first_best_candidate_diff_matches") or not activation_parity[name]["first_best_candidate_diff_matches"]:
                raise AssertionError(f"Activation attribution disagreement: {name}: {activation_parity[name]}")
        summary["main_activation_parity"] = activation_parity
    (OUT / "agent_a_ablation_audit.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
