"""One-at-a-time V1.3 filter-off paper replays on the L1 frozen snapshot."""

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
BOT = ROOT / "poe_subd_six_etf_v1_3_bot.py"
END = pd.Timestamp("2026-09-24")
ARMS = (
    ("formal_v1_3", 0.5, 5.5, 0.25),
    ("score_floor_off", -math.inf, 5.5, 0.25),
    ("score_ceiling_off", 0.5, math.inf, 0.25),
    ("r2_off", 0.5, 5.5, None),
)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare_formal(actual, saved):
    assert pd.DatetimeIndex(actual["date"]).equals(pd.DatetimeIndex(saved["date"]))
    out = {"rows": len(actual), "string_mismatch": {}, "numeric_max_abs": {}, "numeric_na_mismatch": {}}
    for field in ("position_before", "position", "trade_target", "best_candidate"):
        a = actual[field].fillna("<NA>").astype(str).to_numpy()
        b = saved[field].fillna("<NA>").astype(str).to_numpy()
        out["string_mismatch"][field] = int(np.count_nonzero(a != b))
    for field in ("turnover", "cost", "gross_return", "return", "nav"):
        a = pd.to_numeric(actual[field], errors="coerce").to_numpy(dtype=float)
        b = pd.to_numeric(saved[field], errors="coerce").to_numpy(dtype=float)
        out["numeric_na_mismatch"][field] = int(np.count_nonzero(np.isnan(a) ^ np.isnan(b)))
        d = np.abs(a - b)
        out["numeric_max_abs"][field] = float(np.nanmax(d)) if np.isfinite(d).any() else 0.0
    return out


def window_metrics(frame, arm, label, start, end):
    part = frame.loc[(frame["date"] >= start) & (frame["date"] <= end)].copy()
    nav = part["nav"].astype(float).reset_index(drop=True)
    assert len(nav) >= 2 and nav.notna().all() and (nav > 0).all()
    dd = nav / nav.cummax() - 1.0
    low = int(dd.argmin())
    high = int(nav.iloc[:low+1].argmax())
    ratio = float(nav.iloc[-1] / nav.iloc[0])
    before_cost = frame["nav"].shift(1).fillna(1.0) * (1.0 + frame["gross_return"])
    fee = before_cost.loc[part.index] * part["cost"]
    return {
        "arm": arm, "window": label, "start": str(part["date"].iloc[0].date()), "end": str(part["date"].iloc[-1].date()),
        "nav_rows": len(part), "nav_changes": len(part)-1,
        "total_return": ratio-1.0, "annual_n_minus_1": ratio**(252.0/(len(part)-1))-1.0,
        "maxdd": float(dd.iloc[low]), "maxdd_peak_date": str(part["date"].iloc[high].date()),
        "maxdd_trough_date": str(part["date"].iloc[low].date()),
        "ending_nav": float(nav.iloc[-1]),
        "trade_days": int((part["turnover"]>0).sum()),
        "two_sided_switch_days": int((part["turnover"]==2).sum()),
        "turnover_sum": float(part["turnover"].sum()), "sum_cost_fraction": float(part["cost"].sum()),
        "fees_initial_capital_units": float(fee.sum()),
        "avg_carried_exposure": float(part["fraction_before"].mean()),
        "cash_end_days": int((part["position"]=="CASH").sum()),
        "stale_trade_block_days": int(part["trade_blocked_by_stale_price"].sum()),
    }


def rescued_matrix(formal, kind, assets):
    result = pd.DataFrame(False, index=formal.index, columns=assets)
    for asset in assets:
        s = pd.to_numeric(formal[f"raw_score_{asset}"], errors="coerce")
        r = pd.to_numeric(formal[f"r2_{asset}"], errors="coerce")
        if kind == "score_floor_off":
            result[asset] = s.notna() & (s <= 0.5) & (s < 5.5) & (r >= 0.25)
        elif kind == "score_ceiling_off":
            result[asset] = s.notna() & (s > 0.5) & (s >= 5.5) & (r >= 0.25)
        elif kind == "r2_off":
            result[asset] = s.notna() & (s > 0.5) & (s < 5.5) & (r.isna() | (r < 0.25))
        else:
            raise ValueError(kind)
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((L1 / "capture_manifest.json").read_text(encoding="utf-8"))
    assert sha256(BOT) == manifest["entrypoint_sha256"]
    for key in ("aligned", "flags"):
        assert sha256(manifest[key]["path"]) == manifest[key]["sha256"]
    prices = pd.read_csv(manifest["aligned"]["path"], parse_dates=["date"]).set_index("date")
    flags = pd.read_csv(manifest["flags"]["path"], parse_dates=["date"]).set_index("date").astype(bool)
    assert len(prices) == 3594 and prices.index[-1] == END and prices.index.equals(flags.index)
    spec = importlib.util.spec_from_file_location("six_etf_v13_l4", BOT)
    bot = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = bot
    spec.loader.exec_module(bot)
    assert bot.LOOKBACK == 25 and bot.SCORE_MIN == 0.5 and bot.SCORE_MAX == 5.5
    assert bot.R2_THRESHOLD == 0.25 and bot.SWITCH_BUFFER == 1.0
    config = bot._build_config(end_date=END)
    assert config.one_way_cost == 0.001 and config.max_lev == 1.0
    case = bot.EntryCase("full_entry", "full_entry", 1.0)
    saved_globals = bot.SCORE_MIN, bot.SCORE_MAX
    curves = {}
    try:
        for name, lower, upper, r2 in ARMS:
            bot.SCORE_MIN, bot.SCORE_MAX = lower, upper
            curves[name] = bot.run_staged_entry(prices, config, case, r2, 1.0, price_ffill_flags=flags).reset_index()
    finally:
        bot.SCORE_MIN, bot.SCORE_MAX = saved_globals
    formal = curves["formal_v1_3"]
    saved = pd.read_csv(L2 / "formal_daily_20260924.csv.gz", parse_dates=["date"])
    parity = compare_formal(formal, saved)
    if any(parity["string_mismatch"].values()) or any(parity["numeric_na_mismatch"].values()) or any(v > (1e-10 if k == "nav" else 1e-12) for k,v in parity["numeric_max_abs"].items()):
        raise RuntimeError(f"Formal baseline parity failed: {parity}")
    windows = [("Full", pd.Timestamp(formal["date"].iloc[0]))]
    for label, n in (("10Y",2520),("5Y",1260),("3Y",756),("1Y",252)):
        windows.append((label, pd.Timestamp(formal["date"].iloc[-n])))
    windows.append(("six_etf_all_scoreable", pd.Timestamp("2020-01-09")))
    metrics = []
    for name, frame in curves.items():
        assert pd.DatetimeIndex(frame["date"]).equals(pd.DatetimeIndex(formal["date"]))
        for label, start in windows:
            metrics.append(window_metrics(frame, name, label, start, END))
        frame.to_csv(OUT / f"daily_{name}_20260924.csv.gz", index=False, compression="gzip", float_format="%.16g")
    pd.DataFrame(metrics).to_csv(OUT / "matched_metrics.csv", index=False)
    records = []
    event_rows = []
    for name, frame in curves.items():
        if name == "formal_v1_3":
            continue
        resc = rescued_matrix(formal, name, list(bot.ASSETS))
        bestdiff = frame["best_candidate"].fillna("<NA>").to_numpy() != formal["best_candidate"].fillna("<NA>").to_numpy()
        posdiff = frame["position"].fillna("<NA>").to_numpy() != formal["position"].fillna("<NA>").to_numpy()
        trade_diff = frame["trade_target"].fillna("<NA>").to_numpy() != formal["trade_target"].fillna("<NA>").to_numpy()
        selected_resc = np.array([bool(resc.iloc[i].get(frame["best_candidate"].iloc[i], False)) for i in range(len(frame))])
        assert not np.any(bestdiff & ~resc.any(axis=1).to_numpy()) if name == "score_ceiling_off" else True
        row = {
            "arm": name, "new_eligible_asset_days": int(resc.to_numpy().sum()),
            "days_with_new_eligible_asset": int(resc.any(axis=1).sum()),
            "best_candidate_diff_days": int(bestdiff.sum()),
            "newly_eligible_asset_is_best_days": int(selected_resc.sum()),
            "position_diff_days": int(posdiff.sum()), "trade_target_diff_days": int(trade_diff.sum()),
            "first_best_candidate_diff": str(frame["date"].iloc[np.flatnonzero(bestdiff)[0]].date()) if bestdiff.any() else None,
            "first_position_diff": str(frame["date"].iloc[np.flatnonzero(posdiff)[0]].date()) if posdiff.any() else None,
            "first_trade_target_diff": str(frame["date"].iloc[np.flatnonzero(trade_diff)[0]].date()) if trade_diff.any() else None,
            "raw_score_max_abs_diff": float(np.nanmax([np.nanmax(np.abs(pd.to_numeric(frame[f"raw_score_{asset}"], errors="coerce").to_numpy(dtype=float)-pd.to_numeric(formal[f"raw_score_{asset}"], errors="coerce").to_numpy(dtype=float))) for asset in bot.ASSETS])),
        }
        records.append(row)
        for i in np.flatnonzero(bestdiff | trade_diff):
            asset = frame["best_candidate"].iloc[i]
            event_rows.append({
                "arm": name, "date": str(frame["date"].iloc[i].date()),
                "formal_best": formal["best_candidate"].iloc[i], "off_best": asset,
                "off_best_newly_eligible": bool(resc.iloc[i].get(asset, False)),
                "formal_position_before": formal["position_before"].iloc[i],
                "off_position_before": frame["position_before"].iloc[i],
                "formal_position": formal["position"].iloc[i], "off_position": frame["position"].iloc[i],
                "formal_trade": formal["trade_target"].iloc[i], "off_trade": frame["trade_target"].iloc[i],
                "off_best_raw_score": frame.get(f"raw_score_{asset}", pd.Series(np.nan, index=frame.index)).iloc[i] if asset in bot.ASSETS else np.nan,
                "off_best_r2": frame.get(f"r2_{asset}", pd.Series(np.nan, index=frame.index)).iloc[i] if asset in bot.ASSETS else np.nan,
                "formal_nav": formal["nav"].iloc[i], "off_nav": frame["nav"].iloc[i],
            })
    pd.DataFrame(records).to_csv(OUT / "activation_summary.csv", index=False)
    pd.DataFrame(event_rows).to_csv(OUT / "decision_events.csv", index=False)
    parity.update({"formal_code_sha256": sha256(BOT), "price_sha256": sha256(manifest["aligned"]["path"]), "flag_sha256": sha256(manifest["flags"]["path"]), "saved_formal_sha256": sha256(L2 / "formal_daily_20260924.csv.gz")})
    (OUT / "formal_parity.json").write_text(json.dumps(parity, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"parity":parity, "activation":records, "metrics_full":[r for r in metrics if r["window"]=="Full"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
