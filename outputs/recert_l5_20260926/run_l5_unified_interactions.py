"""L5 eight fixed gate combinations through one cash/ETF account per path."""

import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
L1 = ROOT / "outputs/recert_l1_20260926"
L2 = ROOT / "outputs/recert_l2_20260926"
L4 = ROOT / "outputs/recert_l4_20260926"
BOT = ROOT / "poe_subd_six_etf_v1_3_bot.py"
END = pd.Timestamp("2026-09-24")
ARMS = {
    "formal_v1_3": (True, True, True),
    "score_floor_off": (False, True, True),
    "score_ceiling_off": (True, False, True),
    "r2_off": (True, True, False),
    "floor_ceiling_off": (False, False, True),
    "floor_r2_off": (False, True, False),
    "ceiling_r2_off": (True, False, False),
    "all_three_off": (False, False, False),
}
PAIRS = (
    ("floor_ceiling_off", "score_floor_off", "score_ceiling_off", "floor", "ceiling"),
    ("floor_r2_off", "score_floor_off", "r2_off", "floor", "r2"),
    ("ceiling_r2_off", "score_ceiling_off", "r2_off", "ceiling", "r2"),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def same_curve(actual, saved):
    assert len(actual) == len(saved)
    assert pd.DatetimeIndex(actual.date).equals(pd.DatetimeIndex(saved.date))
    out = {"rows": len(actual), "position_diff_days": int((actual.position.fillna("<NA>").astype(str).to_numpy() != saved.position.fillna("<NA>").astype(str).to_numpy()).sum()),
           "position_before_diff_days": int((actual.position_before.fillna("<NA>").astype(str).to_numpy() != saved.position_before.fillna("<NA>").astype(str).to_numpy()).sum())}
    for field in ("turnover", "cost", "gross_return", "return", "nav"):
        a = pd.to_numeric(actual[field], errors="coerce").to_numpy(float)
        b = pd.to_numeric(saved[field], errors="coerce").to_numpy(float)
        out[field + "_na_mismatch"] = int((np.isnan(a) ^ np.isnan(b)).sum())
        d = np.abs(a - b)
        out[field + "_max_abs"] = float(np.nanmax(d)) if np.isfinite(d).any() else 0.0
    return out


def metrics(frame, arm, window, start):
    part = frame.loc[frame.date >= start].copy()
    nav = part.nav.astype(float).reset_index(drop=True)
    assert len(nav) > 1 and nav.notna().all() and (nav > 0).all()
    dd = nav / nav.cummax() - 1.0
    low = int(dd.argmin())
    high = int(nav.iloc[:low+1].argmax())
    ratio = float(nav.iloc[-1] / nav.iloc[0])
    fee_base = frame.nav.shift(1).fillna(1.0) * (1.0 + frame.gross_return)
    return {
        "arm": arm, "window": window, "start": str(part.date.iloc[0].date()), "end": str(part.date.iloc[-1].date()),
        "nav_rows": len(part), "nav_changes": len(part)-1, "annual_n_minus_1": ratio**(252.0/(len(part)-1))-1.0,
        "total_return": ratio-1.0, "maxdd": float(dd.iloc[low]),
        "maxdd_peak_date": str(part.date.iloc[high].date()), "maxdd_trough_date": str(part.date.iloc[low].date()),
        "ending_nav": float(nav.iloc[-1]), "trade_days": int((part.turnover > 0).sum()),
        "two_sided_switch_days": int((part.turnover == 2).sum()), "turnover_sum": float(part.turnover.sum()),
        "sum_cost_fraction": float(part.cost.sum()),
        "fee_initial_capital_units": float((fee_base.loc[part.index] * part.cost).sum()),
        "cash_days": int((part.position == "CASH").sum()),
        "avg_carried_exposure": float(part.fraction_before.mean()),
        "max_exposure": float(part.holding_fraction.max()),
        "stale_trade_block_days": int(part.trade_blocked_by_stale_price.sum()),
    }


def new_joint_masks(formal, first, second, assets):
    masks = pd.DataFrame(False, index=formal.index, columns=assets)
    for code in assets:
        s = pd.to_numeric(formal[f"raw_score_{code}"], errors="coerce")
        r = pd.to_numeric(formal[f"r2_{code}"], errors="coerce")
        lower_fail = s.notna() & (s <= 0.5)
        upper_fail = s.notna() & (s >= 5.5)
        r2_fail = s.notna() & (r.isna() | (r < 0.25))
        failures = {"floor": lower_fail, "ceiling": upper_fail, "r2": r2_fail}
        others = [k for k in ("floor", "ceiling", "r2") if k not in (first, second)]
        assert len(others) == 1
        masks[code] = failures[first] & failures[second] & ~failures[others[0]]
    return masks


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((L1 / "capture_manifest.json").read_text(encoding="utf-8"))
    assert sha(BOT) == manifest["entrypoint_sha256"]
    for k in ("aligned", "flags"):
        assert sha(manifest[k]["path"]) == manifest[k]["sha256"]
    prices = pd.read_csv(manifest["aligned"]["path"], parse_dates=["date"]).set_index("date")
    flags = pd.read_csv(manifest["flags"]["path"], parse_dates=["date"]).set_index("date").astype(bool)
    assert len(prices) == 3594 and prices.index[-1] == END and prices.index.equals(flags.index)
    spec = importlib.util.spec_from_file_location("six_etf_v13_l5", BOT)
    bot = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = bot
    spec.loader.exec_module(bot)
    assert (bot.SCORE_MIN, bot.SCORE_MAX, bot.R2_THRESHOLD, bot.SWITCH_BUFFER, bot.ONE_WAY_COST) == (0.5, 5.5, 0.25, 1.0, 0.001)
    assert bot.LOOKBACK == 25 and bot._build_config(end_date=END).max_lev == 1.0
    config = bot._build_config(end_date=END)
    case = bot.EntryCase("full_entry", "full_entry", 1.0)
    source_bounds = bot.SCORE_MIN, bot.SCORE_MAX
    curves = {}
    try:
        for name, (floor_on, ceiling_on, r2_on) in ARMS.items():
            bot.SCORE_MIN = 0.5 if floor_on else -math.inf
            bot.SCORE_MAX = 5.5 if ceiling_on else math.inf
            curves[name] = bot.run_staged_entry(prices, config, case, 0.25 if r2_on else None, 1.0, price_ffill_flags=flags).reset_index()
    finally:
        bot.SCORE_MIN, bot.SCORE_MAX = source_bounds
    full = curves["formal_v1_3"]
    parity = {}
    controls = {"formal_v1_3": L2 / "formal_daily_20260924.csv.gz"}
    controls.update({name: L4 / f"daily_{name}_20260924.csv.gz" for name in ("score_floor_off", "score_ceiling_off", "r2_off")})
    for name, path in controls.items():
        saved = pd.read_csv(path, parse_dates=["date"])
        check = same_curve(curves[name], saved)
        if check["position_diff_days"] or check["position_before_diff_days"] or any(v > (1e-10 if "nav_max" in k else 1e-12) for k,v in check.items() if k.endswith("_max_abs")) or any(v for k,v in check.items() if k.endswith("_na_mismatch")):
            raise RuntimeError(f"L5 unchanged control failed: {name} {check}")
        parity[name] = {"reference": str(path), "reference_sha256": sha(path), **check}
    windows = [("Full", pd.Timestamp(full.date.iloc[0]))]
    windows += [(name, pd.Timestamp(full.date.iloc[-n])) for name,n in (("10Y",2520),("5Y",1260),("3Y",756),("1Y",252))]
    windows.append(("six_etf_all_scoreable", pd.Timestamp("2020-01-09")))
    all_metrics = []
    for name, frame in curves.items():
        assert pd.DatetimeIndex(frame.date).equals(pd.DatetimeIndex(full.date))
        assert np.isfinite(frame.nav.to_numpy(float)).all()
        assert (frame.holding_fraction.between(0,1)).all() and (frame.fraction_before.between(0,1)).all()
        for window, start in windows:
            all_metrics.append(metrics(frame, name, window, start))
        frame.to_csv(OUT / f"daily_{name}.csv.gz", index=False, compression="gzip", float_format="%.16g")
    pd.DataFrame(all_metrics).to_csv(OUT / "matched_metrics.csv", index=False)
    pairs = []
    for pair_name, a_name, b_name, first, second in PAIRS:
        pair = curves[pair_name]
        a, b = curves[a_name], curves[b_name]
        joint = new_joint_masks(full, first, second, list(bot.ASSETS))
        novel_target = (pair.best_candidate.fillna("<NA>").to_numpy() != a.best_candidate.fillna("<NA>").to_numpy()) & (pair.best_candidate.fillna("<NA>").to_numpy() != b.best_candidate.fillna("<NA>").to_numpy())
        winner_joint = np.array([bool(joint.iloc[i].get(pair.best_candidate.iloc[i], False)) for i in range(len(pair))])
        diff_formal = pair.position.fillna("<NA>").to_numpy() != full.position.fillna("<NA>").to_numpy()
        first_novel = str(pair.date.iloc[np.flatnonzero(novel_target)[0]].date()) if novel_target.any() else None
        log_residual = float(math.log(pair.nav.iloc[-1] * full.nav.iloc[-1] / (a.nav.iloc[-1] * b.nav.iloc[-1])))
        pairs.append({
            "pair_arm": pair_name, "joint_only_new_eligible_asset_days": int(joint.to_numpy().sum()),
            "joint_only_new_eligible_dates": int(joint.any(axis=1).sum()),
            "joint_only_winner_days": int(winner_joint.sum()),
            "pair_target_novel_days": int(novel_target.sum()), "first_pair_target_novel": first_novel,
            "position_diff_vs_formal_days": int(diff_formal.sum()),
            "end_nav": float(pair.nav.iloc[-1]), "log_nav_interaction_residual": log_residual,
        })
    pd.DataFrame(pairs).to_csv(OUT / "pair_interactions.csv", index=False)
    total = curves["all_three_off"]
    triple = {
        "all_off_end_nav": float(total.nav.iloc[-1]),
        "all_off_position_diff_vs_formal_days": int((total.position.fillna("<NA>").to_numpy() != full.position.fillna("<NA>").to_numpy()).sum()),
        "all_off_position_diff_vs_l3_pure_baseline_days": None,
    }
    l3_path = ROOT / "outputs/recert_l3_20260926/baseline_daily_20260924.csv.gz"
    l3 = pd.read_csv(l3_path, parse_dates=["date"])
    assert pd.DatetimeIndex(l3.date).equals(pd.DatetimeIndex(total.date))
    triple["all_off_position_diff_vs_l3_pure_baseline_days"] = int((total.position.fillna("<NA>").to_numpy() != l3.position.fillna("<NA>").to_numpy()).sum())
    triple["l3_pure_baseline_sha256"] = sha(l3_path)
    frozen = {
        "git_commit": manifest["git_head"], "formal_code_sha256": sha(BOT),
        "prices_sha256": sha(manifest["aligned"]["path"]), "flags_sha256": sha(manifest["flags"]["path"]),
        "cutoff": str(END.date()), "rows": len(full),
        "formal_and_single_off_parity": parity, "triple": triple,
        "curve_sha256": {name: sha(OUT / f"daily_{name}.csv.gz") for name in ARMS},
        "metrics_sha256": sha(OUT / "matched_metrics.csv"), "pairs_sha256": sha(OUT / "pair_interactions.csv"),
    }
    (OUT / "run_manifest.json").write_text(json.dumps(frozen, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"parity": parity, "pairs": pairs, "triple": triple, "full_metrics": [r for r in all_metrics if r["window"]=="Full"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
