"""Execute the pre-frozen L6 one-parameter-at-a-time matrix on the formal engine."""

import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
RUN = Path(__file__).resolve().parent
L1 = ROOT / "outputs/recert_l1_20260926"
L2 = ROOT / "outputs/recert_l2_20260926"
L4 = ROOT / "outputs/recert_l4_20260926"
BOT = ROOT / "poe_subd_six_etf_v1_3_bot.py"
MATRIX = RUN / "parameter_matrix.csv"
PROTOCOL = RUN / "freeze_protocol.md"
END = pd.Timestamp("2026-09-24")
FORMAL_SHA = "21a5867f51367d215a6f9913dafae1a462bf2316f7c59e7a860d43448c63ee72"
MATRIX_SHA = "12fb6719c38f10078bedf908eac8a46d64ac26b633e8b237546d4e42f107fff4"
PROTOCOL_SHA = "93362ab6ce21681d4be412d8f250ccc8213ae7bc5e634fb1cff80d714b56146c"
GROUPS = ("lookback", "weight_power", "score_floor", "score_ceiling", "r2_threshold", "switch_buffer")
WINDOWS = (("full", None), ("last_10y", 2520), ("last_5y", 1260), ("last_3y", 756), ("last_1y", 252))
ALL_SCOREABLE = pd.Timestamp("2020-01-09")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def score_with_power(window, lookback, power, annual_days):
    values = window.dropna().astype(float)
    if len(values) != lookback or (values <= 0).any() or not np.isfinite(values.to_numpy(float)).all():
        return math.nan, math.nan
    y = np.log(values.to_numpy())
    if float(np.ptp(y)) <= 1e-12:
        return math.nan, math.nan
    y = y - y[0]
    x = np.arange(len(y), dtype=float)
    weights = np.arange(1, len(y)+1, dtype=float) ** power
    slope, intercept = np.polyfit(x, y, 1, w=np.sqrt(weights))
    fitted = slope*x + intercept
    ybar = float(np.average(y, weights=weights))
    sst = float(np.sum(weights*(y-ybar)**2))
    if sst <= 0:
        return math.nan, math.nan
    ssr = float(np.sum(weights*(y-fitted)**2))
    r2 = max(0.0, 1.0-ssr/sst)
    annual_log = float(slope)*annual_days
    if not math.isfinite(annual_log) or annual_log > math.log(sys.float_info.max):
        return math.nan, r2
    return math.exp(annual_log)-1.0, r2


def metrics(frame, candidate, group, value, role, segment, start):
    part = frame if start is None else frame.loc[frame.date >= start]
    part = part.reset_index(drop=True)
    nav = part.nav.to_numpy(float)
    assert len(nav) >= 2 and np.isfinite(nav).all() and (nav > 0).all()
    daily_returns = nav[1:]/nav[:-1]-1.0
    ratio = float(nav[-1]/nav[0])
    annual = ratio**(252.0/(len(nav)-1))-1.0
    vol = float(np.std(daily_returns, ddof=1)*math.sqrt(252.0)) if len(daily_returns) > 1 else 0.0
    std = float(np.std(daily_returns, ddof=1)) if len(daily_returns)>1 else 0.0
    assert std > 0
    sharpe = float(np.mean(daily_returns)/std*math.sqrt(252.0))
    dd = nav / np.maximum.accumulate(nav)-1.0
    low = int(np.argmin(dd))
    high = int(np.argmax(nav[:low+1]))
    fee_base = frame.nav.shift(1).fillna(1.0)*(1.0+frame.gross_return)
    part_index = frame.index[frame.date >= start] if start is not None else frame.index
    paid_fee = float((fee_base.loc[part_index]*frame.loc[part_index,"cost"]).sum())
    return {
        "candidate": candidate, "group": group, "value": value, "role": role,
        "segment": segment, "start": str(part.date.iloc[0].date()), "end": str(part.date.iloc[-1].date()),
        "rows": len(part), "nav_changes": len(part)-1,
        "ann_return": annual, "ann_vol": vol, "sharpe_repo": sharpe,
        "max_dd": float(dd[low]), "max_dd_peak": str(part.date.iloc[high].date()),
        "max_dd_trough": str(part.date.iloc[low].date()), "total_return": ratio-1.0,
        "end_nav": float(nav[-1]), "trade_days": int((part.turnover > 0).sum()),
        "two_sided_switch_days": int((part.turnover == 2).sum()),
        "turnover_total": float(part.turnover.sum()), "cost_rate_total": float(part.cost.sum()),
        "paid_fee_initial_capital_units": paid_fee,
        "cash_days": int((part.position == "CASH").sum()),
        "avg_carried_exposure": float(part.fraction_before.mean()),
        "stale_trade_block_days": int(part.trade_blocked_by_stale_price.sum()),
        "buffer_block_days": int(part.buffer_blocked.sum()),
    }


def run_one(bot, prices, flags, config, row, original_score):
    lookback, score_min, score_max = bot.LOOKBACK, bot.SCORE_MIN, bot.SCORE_MAX
    r2, buffer, score_func = 0.25, 1.0, original_score
    group, value = row["group"], row["value"]
    try:
        if group == "lookback":
            bot.LOOKBACK = int(value)
        elif group == "weight_power":
            power = float(value)
            if power != 1.0:
                bot.weighted_slope_score_and_r2 = lambda window: score_with_power(window, bot.LOOKBACK, power, bot.TRADING_DAYS)
        elif group == "score_floor":
            bot.SCORE_MIN = -math.inf if value == "off" else float(value)
        elif group == "score_ceiling":
            bot.SCORE_MAX = math.inf if value == "off" else float(value)
        elif group == "r2_threshold":
            r2 = None if value == "off" else float(value)
        elif group == "switch_buffer":
            buffer = float(value)
        else:
            raise ValueError(group)
        return bot.run_staged_entry(
            prices, config, bot.EntryCase("full_entry", "full_entry", 1.0),
            r2, buffer, price_ffill_flags=flags,
        ).reset_index()
    finally:
        bot.LOOKBACK, bot.SCORE_MIN, bot.SCORE_MAX = lookback, score_min, score_max
        bot.weighted_slope_score_and_r2 = score_func


def assert_same_path(actual, old, tag):
    assert len(actual) == len(old) and pd.DatetimeIndex(actual.date).equals(pd.DatetimeIndex(old.date))
    out = {"tag": tag, "rows": len(actual), "position_mismatch": 0, "turnover_max_abs": 0.0, "cost_max_abs": 0.0, "nav_max_abs": 0.0}
    out["position_mismatch"] = int((actual.position.fillna("<NA>").astype(str).to_numpy()!=old.position.fillna("<NA>").astype(str).to_numpy()).sum())
    for field in ("turnover", "cost", "nav"):
        out[field+"_max_abs"] = float(np.nanmax(np.abs(actual[field].to_numpy(float)-old[field].to_numpy(float))))
    if out["position_mismatch"] or out["turnover_max_abs"]>1e-12 or out["cost_max_abs"]>1e-12 or out["nav_max_abs"]>1e-10:
        raise RuntimeError(f"Unchanged path parity failed: {out}")
    return out


def main():
    assert sha(BOT) == FORMAL_SHA and sha(MATRIX) == MATRIX_SHA and sha(PROTOCOL) == PROTOCOL_SHA
    manifest = json.loads((L1 / "capture_manifest.json").read_text(encoding="utf-8"))
    for key in ("aligned", "flags"):
        assert sha(manifest[key]["path"]) == manifest[key]["sha256"]
    prices = pd.read_csv(manifest["aligned"]["path"], parse_dates=["date"]).set_index("date")
    flags = pd.read_csv(manifest["flags"]["path"], parse_dates=["date"]).set_index("date").astype(bool)
    assert len(prices) == 3594 and prices.index[-1] == END and prices.index.equals(flags.index)
    matrix = pd.read_csv(MATRIX, dtype=str, keep_default_na=False)
    assert len(matrix) == 39 and tuple(matrix.group.drop_duplicates()) == GROUPS
    assert matrix.candidate.is_unique and (matrix.groupby("group").role.apply(lambda x: x.str.contains("formal").sum())==1).all()
    spec = importlib.util.spec_from_file_location("six_etf_v13_l6", BOT)
    bot = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = bot
    spec.loader.exec_module(bot)
    assert (bot.LOOKBACK, bot.SCORE_MIN, bot.SCORE_MAX, bot.R2_THRESHOLD, bot.SWITCH_BUFFER, bot.ONE_WAY_COST) == (25,0.5,5.5,0.25,1.0,0.001)
    config = bot._build_config(end_date=END)
    original_score = bot.weighted_slope_score_and_r2
    daily_dir = RUN / "daily_outputs"
    daily_dir.mkdir(exist_ok=True)
    formal_row = matrix.loc[matrix.candidate=="lookback_25"].iloc[0].to_dict()
    formal = run_one(bot, prices, flags, config, formal_row, original_score)
    formal_path = daily_dir / "formal_v1_3.csv.gz"
    formal.to_csv(formal_path, index=False, compression="gzip", float_format="%.16g")
    parity = [assert_same_path(formal, pd.read_csv(L2/"formal_daily_20260924.csv.gz", parse_dates=["date"]), "formal_vs_L2")]
    print("formal parity PASS", flush=True)
    rows = []
    triggered = []
    for i, row in matrix.iterrows():
        item = row.to_dict()
        candidate = item["candidate"]
        group = item["group"]
        if "formal" in item["role"]:
            curve = formal
            curve_path = formal_path
        else:
            curve = run_one(bot, prices, flags, config, item, original_score)
            curve_path = daily_dir / f"{candidate}.csv.gz"
            curve.to_csv(curve_path, index=False, compression="gzip", float_format="%.16g")
        assert pd.DatetimeIndex(curve.date).equals(pd.DatetimeIndex(formal.date))
        assert np.isfinite(curve.nav.to_numpy(float)).all() and (curve.nav>0).all()
        assert curve.holding_fraction.between(0,1).all() and curve.fraction_before.between(0,1).all()
        for segment, n in WINDOWS:
            start = None if n is None else pd.Timestamp(curve.date.iloc[-n])
            rows.append(metrics(curve, candidate, group, item["value"], item["role"], segment, start))
        rows.append(metrics(curve, candidate, group, item["value"], item["role"], "six_etf_all_scoreable", ALL_SCOREABLE))
        target_diff = curve.best_candidate.fillna("<NA>").astype(str).to_numpy()!=formal.best_candidate.fillna("<NA>").astype(str).to_numpy()
        pos_diff = curve.position.fillna("<NA>").astype(str).to_numpy()!=formal.position.fillna("<NA>").astype(str).to_numpy()
        trade_diff = curve.trade_target.fillna("<NA>").astype(str).to_numpy()!=formal.trade_target.fillna("<NA>").astype(str).to_numpy()
        triggered.append({"candidate":candidate,"group":group,"value":item["value"],"role":item["role"],
                          "target_diff_days":int(target_diff.sum()),"position_diff_days":int(pos_diff.sum()),"trade_target_diff_days":int(trade_diff.sum()),
                          "first_target_diff":str(curve.date.iloc[np.flatnonzero(target_diff)[0]].date()) if target_diff.any() else "",
                          "first_position_diff":str(curve.date.iloc[np.flatnonzero(pos_diff)[0]].date()) if pos_diff.any() else "",
                          "buffer_block_days":int(curve.buffer_blocked.sum()),
                          "daily_path":str(curve_path.relative_to(ROOT)),"daily_sha256":sha(curve_path)})
        if candidate in ("score_floor_off","score_ceiling_off","r2_off"):
            old = pd.read_csv(L4/f"daily_{candidate}_20260924.csv.gz", parse_dates=["date"])
            parity.append(assert_same_path(curve, old, candidate+"_vs_L4"))
        print(f"{i+1:02d}/{len(matrix)} {group} {candidate} END_NAV={curve.nav.iloc[-1]:.8f}", flush=True)
    summary = pd.DataFrame(rows)
    full = summary.loc[summary.segment=="full"].set_index("candidate")
    for field in ("ann_return", "max_dd", "trade_days", "turnover_total", "cash_days"):
        summary["formal_"+field] = summary.apply(lambda r: summary.loc[(summary.candidate==matrix.loc[(matrix.group==r.group)&matrix.role.str.contains("formal"),"candidate"].iloc[0]) & (summary.segment==r.segment),field].iloc[0],axis=1)
    summary["delta_ann_pp"] = (summary.ann_return-summary.formal_ann_return)*100.0
    summary["dd_improvement_pp"] = (summary.max_dd-summary.formal_max_dd)*100.0
    summary.to_csv(RUN/"scan_summary.csv", index=False)
    wide = []
    for _, mrow in matrix.iterrows():
        sub = summary.loc[summary.candidate==mrow.candidate].set_index("segment")
        x = {"candidate":mrow.candidate,"group":mrow.group,"value":mrow.value,"role":mrow.role,"provenance":mrow.provenance}
        for seg,_ in WINDOWS:
            x[f"ann_return_{seg}"] = float(sub.at[seg,"ann_return"])
            x[f"max_dd_{seg}"] = float(sub.at[seg,"max_dd"])
            x[f"delta_ann_pp_{seg}"] = float(sub.at[seg,"delta_ann_pp"])
            x[f"dd_improvement_pp_{seg}"] = float(sub.at[seg,"dd_improvement_pp"])
        x["end_nav_full"] = float(sub.at["full","end_nav"])
        x["trade_days_full"] = int(sub.at["full","trade_days"])
        x["turnover_total_full"] = float(sub.at["full","turnover_total"])
        x["ann_return_six_etf_all_scoreable"] = float(sub.at["six_etf_all_scoreable","ann_return"])
        x["max_dd_six_etf_all_scoreable"] = float(sub.at["six_etf_all_scoreable","max_dd"])
        wide.append(x)
    pd.DataFrame(wide).to_csv(RUN/"window_metrics.csv", index=False)
    pd.DataFrame(triggered).to_csv(RUN/"candidate_event_counts.csv", index=False)
    (RUN/"parity_checks.json").write_text(json.dumps({"formal_code_sha256":sha(BOT),"matrix_sha256":sha(MATRIX),"protocol_sha256":sha(PROTOCOL),"price_sha256":sha(manifest["aligned"]["path"]),"flags_sha256":sha(manifest["flags"]["path"]),"parity":parity},ensure_ascii=False,indent=2),encoding="utf-8")
    print("COMPLETE: 39 matrix rows,",len(summary),"window rows",flush=True)


if __name__ == "__main__":
    main()
