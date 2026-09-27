"""Independent eight-cell gate-interaction replay for six-ETF V1.3.

Reads frozen L1 prices and flags, and does not import any strategy function.
Run: python -X utf8 outputs/recert_l5_20260926/agent_a_interactions.py
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
L1 = ROOT / "outputs/recert_l1_20260926"
L2 = ROOT / "outputs/recert_l2_20260926"
L4 = ROOT / "outputs/recert_l4_20260926"
ASSETS = ("159915.SZ", "159941.SZ", "513030.SH", "513520.SH", "159985.SZ", "518880.SH")
GATES = ("floor", "ceiling", "r2")


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scores_from_closes(closes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n, k = closes.shape
    score = np.full((n, k), np.nan)
    fit_quality = np.full((n, k), np.nan)
    x = np.arange(25, dtype=float)
    w = np.arange(1, 26, dtype=float)
    sw = float(w.sum())
    x_bar = float(np.sum(w * x) / sw)
    x_var = float(np.sum(w * (x - x_bar) ** 2))
    for day in range(24, n):
        for asset in range(k):
            p = closes[day-24:day+1, asset]
            if len(p) != 25 or not np.isfinite(p).all() or np.any(p <= 0):
                continue
            y = np.log(p)
            if np.ptp(y) <= 1e-12:
                continue
            y_bar = float(np.sum(w * y) / sw)
            y_var = float(np.sum(w * (y - y_bar) ** 2))
            if y_var <= 0:
                continue
            slope = float(np.sum(w * (x - x_bar) * (y - y_bar)) / x_var)
            intercept = y_bar - slope * x_bar
            fit_quality[day, asset] = max(0.0, 1.0 - float(np.sum(w * (y - slope*x - intercept) ** 2)) / y_var)
            ann = 252 * slope
            if math.isfinite(ann) and ann <= math.log(np.finfo(float).max):
                score[day, asset] = math.expm1(ann)
    return score, fit_quality


def eligibility(score: np.ndarray, r2: np.ndarray, off: frozenset[str]) -> np.ndarray:
    eligible = np.isfinite(score)
    if "floor" not in off:
        eligible &= score > .5
    if "ceiling" not in off:
        eligible &= score < 5.5
    if "r2" not in off:
        eligible &= np.isfinite(r2) & (r2 >= .25)
    return eligible


def run(dates: pd.DatetimeIndex, close: np.ndarray, stale: np.ndarray, score: np.ndarray,
        eligible: np.ndarray) -> pd.DataFrame:
    old = "CASH"
    cash, shares, last_nav = 1., 0., 1.
    idx = {a: j for j, a in enumerate(ASSETS)}
    rows = []
    for t, date in enumerate(dates):
        marked = cash if old == "CASH" else shares * close[t, idx[old]]
        if not math.isfinite(marked) or marked <= 0:
            raise AssertionError((date, old, marked))
        wanted = "CASH" if not eligible[t].any() else ASSETS[int(np.argmax(np.where(eligible[t], score[t], -np.inf)))]
        touched = (old, wanted) if wanted != old else ()
        blocked = any(bool(stale[t, idx[a]]) for a in touched if a != "CASH")
        new = old if blocked else wanted
        turnover = 0 if new == old else int(old != "CASH") + int(new != "CASH")
        fee_rate = .001 * turnover
        post_fee = marked * (1. - fee_rate)
        if new == "CASH":
            cash, shares = post_fee, 0.
        else:
            cash, shares = 0., post_fee / close[t, idx[new]]
        nav = cash if new == "CASH" else shares * close[t, idx[new]]
        rows.append((date, old, wanted, new, int(eligible[t].sum()), blocked, turnover,
                     fee_rate, marked / last_nav - 1., nav / last_nav - 1., nav))
        old, last_nav = new, nav
    return pd.DataFrame(rows, columns=("date", "position_before", "wanted", "position",
                                      "eligible_count", "stale_trade_blocked", "turnover",
                                      "cost", "gross_return", "return", "nav"))


def parity(x: pd.DataFrame, y: pd.DataFrame) -> dict:
    assert pd.DatetimeIndex(x.date).equals(pd.DatetimeIndex(y.date))
    ans = {}
    for col in ("position_before", "wanted", "position", "turnover", "cost", "return", "nav"):
        if col not in y.columns:
            continue
        if col in ("position_before", "wanted", "position"):
            ans[col + "_different_days"] = int(np.count_nonzero(x[col].to_numpy() != y[col].to_numpy()))
        else:
            ans[col + "_max_abs"] = float(np.max(np.abs(x[col].to_numpy(float) - y[col].to_numpy(float))))
    return ans


def case_name(off: frozenset[str]) -> str:
    return "formal" if not off else "_".join(g for g in GATES if g in off) + "_off"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((L1 / "capture_manifest.json").read_text(encoding="utf-8"))
    for key in ("aligned", "flags"):
        p = Path(manifest[key]["path"])
        assert hash_file(p) == manifest[key]["sha256"]
    prices = pd.read_csv(manifest["aligned"]["path"], parse_dates=["date"]).set_index("date")
    flags = pd.read_csv(manifest["flags"]["path"], parse_dates=["date"]).set_index("date")
    assert prices.index.equals(flags.index) and len(prices) == 3594
    assert str(prices.index.max().date()) == "2026-09-24"
    closes = prices.loc[:, ASSETS].to_numpy(float)
    stale = flags.loc[:, ASSETS].to_numpy(bool)
    score, r2 = scores_from_closes(closes)
    cases = [frozenset(combo) for num in range(4) for combo in itertools.combinations(GATES, num)]
    elig = {case_name(off): eligibility(score, r2, off) for off in cases}
    curves = {case_name(off): run(prices.index, closes, stale, score, elig[case_name(off)]) for off in cases}
    for name, curve in curves.items():
        curve.to_csv(OUT / f"agent_a_{name}_daily.csv.gz", index=False, compression="gzip", float_format="%.17g")
    reference = pd.read_csv(L2 / "formal_daily_20260924.csv.gz", parse_dates=["date"])
    report = {"source_price_sha": hash_file(Path(manifest["aligned"]["path"])),
              "source_flags_sha": hash_file(Path(manifest["flags"]["path"])),
              "rows": len(prices), "first": str(prices.index[0].date()), "last": str(prices.index[-1].date()),
              "formal_parity": parity(curves["formal"], reference), "cases": {}, "pair_interactions": {}}
    assert report["formal_parity"]["position_different_days"] == 0
    assert report["formal_parity"]["turnover_max_abs"] == 0
    assert report["formal_parity"]["nav_max_abs"] < 1e-9
    one_map = {"floor_off": "daily_score_floor_off_20260924.csv.gz",
               "ceiling_off": "daily_score_ceiling_off_20260924.csv.gz",
               "r2_off": "daily_r2_off_20260924.csv.gz"}
    for name, fname in one_map.items():
        report[name + "_l4_parity"] = parity(curves[name], pd.read_csv(L4 / fname, parse_dates=["date"]))
        assert report[name + "_l4_parity"]["position_different_days"] == 0
        assert report[name + "_l4_parity"]["turnover_max_abs"] == 0
        assert report[name + "_l4_parity"]["nav_max_abs"] < 1e-9
    main_names = {
        "formal": "daily_formal_v1_3.csv.gz",
        "floor_off": "daily_score_floor_off.csv.gz",
        "ceiling_off": "daily_score_ceiling_off.csv.gz",
        "r2_off": "daily_r2_off.csv.gz",
        "floor_ceiling_off": "daily_floor_ceiling_off.csv.gz",
        "floor_r2_off": "daily_floor_r2_off.csv.gz",
        "ceiling_r2_off": "daily_ceiling_r2_off.csv.gz",
        "floor_ceiling_r2_off": "daily_all_three_off.csv.gz",
    }
    report["main_l5_parity"] = {}
    for name, filename in main_names.items():
        main_path = OUT / filename
        if not main_path.exists():
            continue
        match = parity(curves[name], pd.read_csv(main_path, parse_dates=["date"]))
        report["main_l5_parity"][name] = match
        assert match["position_before_different_days"] == 0
        assert match["position_different_days"] == 0
        assert match["turnover_max_abs"] == 0
        assert match["cost_max_abs"] == 0
        assert match["nav_max_abs"] < 1e-9
    formal_target = curves["formal"].wanted.to_numpy()
    for off in cases:
        name = case_name(off)
        e = elig[name]
        curve = curves[name]
        target = curve.wanted.to_numpy()
        diff = np.flatnonzero(target != formal_target)
        fresh = e & ~elig["formal"]
        case = {"off": sorted(off), "eligible_asset_days": int(e.sum()),
                "new_eligible_asset_days_vs_formal": int(fresh.sum()),
                "new_eligible_dates_vs_formal": int(fresh.any(axis=1).sum()),
                "target_difference_days_vs_formal": int(len(diff)),
                "first_target_difference": str(prices.index[diff[0]].date()) if len(diff) else None,
                "position_difference_days_vs_formal": int((curve.position.to_numpy() != curves["formal"].position.to_numpy()).sum()),
                "trade_days": int((curve.turnover > 0).sum()), "turnover": int(curve.turnover.sum()),
                "cost_fraction_sum": float(curve.cost.sum()), "end_nav": float(curve.nav.iloc[-1]),
                "stale_trade_blocks": int(curve.stale_trade_blocked.sum())}
        report["cases"][name] = case
        if len(diff) and not fresh[diff[0]].any():
            raise AssertionError((name, "target differs without newly eligible asset"))
    for left, right in itertools.combinations(GATES, 2):
        pair = frozenset((left, right))
        name = case_name(pair)
        a, b = case_name(frozenset((left,))), case_name(frozenset((right,)))
        e_pair, e_a, e_b = elig[name], elig[a], elig[b]
        joint_only = e_pair & ~e_a & ~e_b
        target_pair = curves[name].wanted.to_numpy()
        targ_a, targ_b = curves[a].wanted.to_numpy(), curves[b].wanted.to_numpy()
        decisive = np.flatnonzero((target_pair != targ_a) & (target_pair != targ_b))
        selected_joint_only = np.array([False if t == "CASH" else bool(joint_only[i, ASSETS.index(t)])
                                        for i, t in enumerate(target_pair)])
        first = int(decisive[0]) if len(decisive) else None
        first_joint = int(np.flatnonzero(selected_joint_only)[0]) if selected_joint_only.any() else None
        report["pair_interactions"][name] = {
            "components": (a, b), "joint_only_eligible_asset_days": int(joint_only.sum()),
            "joint_only_eligible_dates": int(joint_only.any(axis=1).sum()),
            "joint_only_selected_dates": int(selected_joint_only.sum()),
            "first_joint_only_selection": None if first_joint is None else {
                "date": str(prices.index[first_joint].date()), "asset": target_pair[first_joint],
                "score": float(score[first_joint, ASSETS.index(target_pair[first_joint])]),
                "r2": float(r2[first_joint, ASSETS.index(target_pair[first_joint])]),
                "formal_target": formal_target[first_joint],
                "single_targets": (targ_a[first_joint], targ_b[first_joint]),
                "pair_target": target_pair[first_joint],
                "pair_position_before": str(curves[name].position_before.iloc[first_joint]),
                "pair_position_after": str(curves[name].position.iloc[first_joint]),
                "pair_turnover": int(curves[name].turnover.iloc[first_joint]),
                "single_positions_before": (str(curves[a].position_before.iloc[first_joint]),
                                            str(curves[b].position_before.iloc[first_joint])),
                "single_turnovers": (int(curves[a].turnover.iloc[first_joint]),
                                     int(curves[b].turnover.iloc[first_joint])),
            },
            "pair_target_differs_from_both_singles_days": int(len(decisive)),
            "first_pair_target_differs_from_both_singles": None if first is None else {
                "date": str(prices.index[first].date()), "formal": formal_target[first],
                "single_a": targ_a[first], "single_b": targ_b[first], "pair": target_pair[first]
            },
            "pair_target_not_equal_either_single_days": int(len(decisive)),
        }
    triple_target = curves["floor_ceiling_r2_off"].wanted.to_numpy()
    single_targets = [curves[case_name(frozenset((g,)))].wanted.to_numpy() for g in GATES]
    pair_targets = [curves[case_name(frozenset(pair))].wanted.to_numpy()
                    for pair in itertools.combinations(GATES, 2)]
    all_single_different = np.logical_and.reduce([triple_target != s for s in single_targets])
    all_pair_different = np.logical_and.reduce([triple_target != s for s in pair_targets])
    report["triple_interaction"] = {
        "triple_target_differs_from_all_three_singles_days": int(all_single_different.sum()),
        "first_such_date": str(prices.index[np.flatnonzero(all_single_different)[0]].date())
            if all_single_different.any() else None,
        "triple_target_differs_from_all_three_pairs_days": int(all_pair_different.sum()),
        "triple_target_differs_from_floor_r2_pair_days": int(
            (triple_target != curves["floor_r2_off"].wanted.to_numpy()).sum()),
    }
    assert not all_pair_different.any()
    # Two disjoint score bands cannot fail the lower and upper gate together.
    assert report["pair_interactions"]["floor_ceiling_off"]["joint_only_eligible_asset_days"] == 0
    # A bitwise OR of single eligibility is wrong when two simultaneous failures occur.
    r2_floor = report["pair_interactions"]["floor_r2_off"]
    assert r2_floor["joint_only_eligible_asset_days"] > 0
    # Prefix recomputation tests all eight cells against future leakage.
    prefix_n = int(np.searchsorted(prices.index, pd.Timestamp("2024-12-31"), side="right"))
    prefix_score, prefix_r2 = scores_from_closes(closes[:prefix_n])
    assert np.allclose(prefix_score, score[:prefix_n], atol=0, rtol=0, equal_nan=True)
    assert np.allclose(prefix_r2, r2[:prefix_n], atol=0, rtol=0, equal_nan=True)
    for off in cases:
        name = case_name(off)
        prefix = run(prices.index[:prefix_n], closes[:prefix_n], stale[:prefix_n], prefix_score,
                     eligibility(prefix_score, prefix_r2, off))
        assert parity(prefix, curves[name].iloc[:prefix_n])["nav_max_abs"] == 0
    report["future_data_prefix_checked_through"] = str(prices.index[prefix_n-1].date())
    (OUT / "agent_a_interactions.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
