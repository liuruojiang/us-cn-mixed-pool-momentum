"""L3 clean baseline replay on the immutable L1 2026-09-24 price capture."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
L1 = ROOT / "outputs/recert_l1_20260926"
L2 = ROOT / "outputs/recert_l2_20260926"
BOT = ROOT / "poe_subd_six_etf_v1_3_bot.py"
OLD = ROOT / "quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/daily_outputs/r2_off_buffer_1.00.csv.gz"
CUTOFF = pd.Timestamp("2026-09-24")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare_prefix(new, old):
    assert len(new) >= len(old)
    prefix = new.iloc[:len(old)].reset_index(drop=True)
    assert pd.DatetimeIndex(prefix["date"]).equals(pd.DatetimeIndex(old["date"]))
    strings = ("position_before", "position", "trade_target", "best_candidate")
    numbers = ("fraction_before", "holding_fraction", "turnover", "cost", "return", "nav", "gross_return", "asset_return", "best_candidate_score", "current_score")
    result = {"rows": len(old), "last_date": str(pd.Timestamp(old["date"].iloc[-1]).date()), "string_mismatch": {}, "max_abs_diff": {}, "na_mismatch": {}}
    for field in strings:
        a = prefix[field].fillna("<NA>").astype(str).to_numpy()
        b = old[field].fillna("<NA>").astype(str).to_numpy()
        result["string_mismatch"][field] = int(np.count_nonzero(a != b))
    for field in numbers:
        a = pd.to_numeric(prefix[field], errors="coerce").to_numpy(dtype=float)
        b = pd.to_numeric(old[field], errors="coerce").to_numpy(dtype=float)
        result["na_mismatch"][field] = int(np.count_nonzero(np.isnan(a) ^ np.isnan(b)))
        diff = np.abs(a - b)
        result["max_abs_diff"][field] = float(np.nanmax(diff)) if np.isfinite(diff).any() else 0.0
    return result


def metrics(frame, label, start, end):
    part = frame.loc[(frame["date"] >= start) & (frame["date"] <= end)].reset_index(drop=True)
    if len(part) < 2:
        return {"window": label, "start": str(start.date()), "end": str(end.date()), "nav_rows": len(part), "annual_n_minus_1": None, "maxdd": None, "reason": "fewer than two NAV rows"}
    n = part["nav"].astype(float)
    nav_ratio = float(n.iloc[-1] / n.iloc[0])
    peak = n.cummax()
    dd = n / peak - 1.0
    trough = int(dd.argmin())
    peak_idx = int(n.iloc[:trough + 1].argmax())
    before_cost_nav = frame["nav"].shift(1).fillna(1.0) * (1.0 + frame["gross_return"])
    part_fee = before_cost_nav.loc[(frame["date"] >= start) & (frame["date"] <= end)] * part["cost"].to_numpy()
    return {
        "window": label, "start": str(part["date"].iloc[0].date()), "end": str(part["date"].iloc[-1].date()),
        "nav_rows": len(part), "nav_changes": len(part) - 1, "total_return": nav_ratio - 1.0,
        "annual_n_minus_1": nav_ratio ** (252.0 / (len(part) - 1)) - 1.0,
        "maxdd": float(dd.iloc[trough]), "maxdd_peak_date": str(part["date"].iloc[peak_idx].date()),
        "maxdd_trough_date": str(part["date"].iloc[trough].date()),
        "model_trade_days": int((part["turnover"] > 0).sum()),
        "turnover_sum": float(part["turnover"].sum()), "sum_cost_fraction": float(part["cost"].sum()),
        "fee_sum_initial_capital_units": float(part_fee.sum()),
        "avg_carried_exposure": float(part["fraction_before"].mean()),
        "cash_end_days": int((part["position"] == "CASH").sum()),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((L1 / "capture_manifest.json").read_text(encoding="utf-8"))
    assert sha256(BOT) == manifest["entrypoint_sha256"]
    for key in ("aligned", "flags"):
        assert sha256(manifest[key]["path"]) == manifest[key]["sha256"]
    prices = pd.read_csv(manifest["aligned"]["path"], parse_dates=["date"]).set_index("date")
    flags = pd.read_csv(manifest["flags"]["path"], parse_dates=["date"]).set_index("date").astype(bool)
    assert len(prices) == 3594 and prices.index[-1] == CUTOFF and prices.index.equals(flags.index)
    spec = importlib.util.spec_from_file_location("six_etf_v13_l3_baseline", BOT)
    bot = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = bot
    spec.loader.exec_module(bot)
    config = bot._build_config(end_date=CUTOFF)
    assert config.one_way_cost == 0.001 and bot.LOOKBACK == 25
    old_min, old_max = bot.SCORE_MIN, bot.SCORE_MAX
    try:
        bot.SCORE_MIN, bot.SCORE_MAX = 0.0, 5.0
        baseline = bot.run_staged_entry(prices, config, bot.EntryCase("full_entry_clean_base", "full_entry", 1.0), None, 1.0, price_ffill_flags=flags).reset_index()
    finally:
        bot.SCORE_MIN, bot.SCORE_MAX = old_min, old_max
    old = pd.read_csv(OLD, parse_dates=["date"])
    parity = compare_prefix(baseline, old)
    parity.update({"old_file_sha256": sha256(OLD), "formal_code_sha256": sha256(BOT), "price_sha256": sha256(manifest["aligned"]["path"]), "flags_sha256": sha256(manifest["flags"]["path"])})
    if any(parity["string_mismatch"].values()) or any(parity["na_mismatch"].values()) or any(v > (1e-10 if k == "nav" else 1e-12) for k, v in parity["max_abs_diff"].items()):
        (OUT / "old_baseline_parity.json").write_text(json.dumps(parity, ensure_ascii=False, indent=2), encoding="utf-8")
        raise RuntimeError(f"Old baseline parity failed: {parity}")
    formal = pd.read_csv(L2 / "formal_daily_20260924.csv.gz", parse_dates=["date"])
    assert pd.DatetimeIndex(baseline["date"]).equals(pd.DatetimeIndex(formal["date"]))
    last = pd.Timestamp(baseline["date"].iloc[-1])
    windows = [("Full", pd.Timestamp(baseline["date"].iloc[0]))]
    for label, n in (("10Y", 2520), ("5Y", 1260), ("3Y", 756), ("1Y", 252)):
        windows.append((label, pd.Timestamp(baseline["date"].iloc[-n])))
    rows = []
    for label, start in windows:
        for arm, daily in (("clean_baseline", baseline), ("formal_v1_3", formal)):
            rows.append({"arm": arm, **metrics(daily, label, start, last)})
    common_start = pd.Timestamp("2019-12-05")
    for arm, daily in (("clean_baseline", baseline), ("formal_v1_3", formal)):
        rows.append({"arm": arm, **metrics(daily, "six_etf_common", common_start, last)})
    all_scoreable_start = pd.Timestamp("2020-01-09")
    assert prices.loc[:all_scoreable_start].tail(bot.LOOKBACK).notna().all().all()
    for arm, daily in (("clean_baseline", baseline), ("formal_v1_3", formal)):
        rows.append({"arm": arm, **metrics(daily, "six_etf_all_scoreable", all_scoreable_start, last)})
    diff_dates = baseline.loc[baseline["position"].fillna("<NA>").to_numpy() != formal["position"].fillna("<NA>").to_numpy(), "date"]
    comparisons = {
        "rows": len(baseline), "cutoff": str(CUTOFF.date()), "baseline_last_nav": float(baseline["nav"].iloc[-1]),
        "formal_last_nav": float(formal["nav"].iloc[-1]), "position_diff_days": len(diff_dates),
        "first_position_diff_date": str(diff_dates.iloc[0].date()) if len(diff_dates) else None,
        "baseline_trade_days": int((baseline["turnover"] > 0).sum()),
        "formal_trade_days": int((formal["turnover"] > 0).sum()),
        "baseline_double_swaps": int((baseline["turnover"] == 2).sum()),
        "formal_double_swaps": int((formal["turnover"] == 2).sum()),
        "baseline_stale_trade_blocks": int(baseline["trade_blocked_by_stale_price"].sum()),
        "formal_stale_trade_blocks": int(formal["trade_blocked_by_stale_price"].sum()),
    }
    baseline_path = OUT / "baseline_daily_20260924.csv.gz"
    baseline.to_csv(baseline_path, index=False, compression="gzip", float_format="%.16g")
    metric_path = OUT / "matched_metrics_20260924.csv"
    pd.DataFrame(rows).to_csv(metric_path, index=False)
    parity["baseline_daily_sha256"] = sha256(baseline_path)
    parity["matched_metrics_sha256"] = sha256(metric_path)
    (OUT / "old_baseline_parity.json").write_text(json.dumps(parity, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "comparison_summary.json").write_text(json.dumps(comparisons, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"parity": parity, "comparisons": comparisons, "metrics": rows}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
