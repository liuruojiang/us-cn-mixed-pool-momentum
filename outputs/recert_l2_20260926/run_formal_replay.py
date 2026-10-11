"""Replay the V1.3 formal chain on the frozen L1 2026-09-24 data capture.

The only runtime substitution is the historical loader's network return value:
it is replaced with L1's byte-identified capture from that same loader. The
strategy, calendar alignment, signal, trades, account and metrics are original.
"""

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
BOT = ROOT / "poe_subd_six_etf_v1_3_bot.py"
OLD = ROOT / "outputs/subd_six_etf_v1_3_acceptance_20260904/daily.csv.gz"
OLD_METRICS = ROOT / "outputs/subd_six_etf_v1_3_acceptance_20260904/metrics.csv"
CUTOFF = pd.Timestamp("2026-09-24")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((L1 / "capture_manifest.json").read_text(encoding="utf-8"))
    assert sha256(BOT) == manifest["entrypoint_sha256"]
    assert sha256(Path(manifest["raw"]["path"])) == manifest["raw"]["sha256"]
    assert sha256(Path(manifest["sources"]["path"])) == manifest["sources"]["sha256"]
    raw = pd.read_csv(manifest["raw"]["path"], parse_dates=["date"]).set_index("date")
    sources = pd.read_csv(manifest["sources"]["path"])
    assert raw.index[-1] == CUTOFF and len(raw) == 3594

    spec = importlib.util.spec_from_file_location("six_etf_v13_l2_formal", BOT)
    bot = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = bot
    spec.loader.exec_module(bot)
    bot._validate_qfq_sources(sources)
    bot.TRADING_CALENDAR_CACHE_PATH = L1 / "calendar_cache_for_audit.csv"
    original_loader = bot.load_close
    try:
        bot.load_close = lambda config: (raw.copy(), sources.copy())
        daily, source_note = bot._build_v13_daily(end_date=CUTOFF, data_state="confirmed")
    finally:
        bot.load_close = original_loader
    assert len(daily) == len(raw)
    assert pd.Timestamp(daily["date"].iloc[-1]) == CUTOFF

    old = pd.read_csv(OLD, parse_dates=["date"])
    prefix = daily.iloc[: len(old)].copy()
    assert pd.DatetimeIndex(prefix["date"]).equals(pd.DatetimeIndex(old["date"]))
    string_fields = ["version", "scenario", "position_before", "position", "trade_target", "best_candidate"]
    numeric_fields = ["fraction_before", "holding_fraction", "turnover", "cost", "return", "nav", "gross_return", "asset_return"]
    parity = {"old_rows": len(old), "new_rows": len(daily), "cutoff": str(CUTOFF.date()), "source_note": source_note, "string_mismatch": {}, "max_abs_diff": {}}
    for field in string_fields:
        left = prefix[field].fillna("<NA>").astype(str)
        right = old[field].fillna("<NA>").astype(str)
        parity["string_mismatch"][field] = int((left.to_numpy() != right.to_numpy()).sum())
    for field in numeric_fields:
        left = pd.to_numeric(prefix[field], errors="coerce").to_numpy(dtype=float)
        right = pd.to_numeric(old[field], errors="coerce").to_numpy(dtype=float)
        mismatch_na = np.isnan(left) ^ np.isnan(right)
        parity["max_abs_diff"][field] = float(np.nanmax(np.abs(left - right))) if np.isfinite(left - right).any() else 0.0
        parity["max_abs_diff"][field + "_na_mismatch"] = int(mismatch_na.sum())
    if any(parity["string_mismatch"].values()) or any(v > (1e-10 if k == "nav" else 1e-12) for k, v in parity["max_abs_diff"].items()):
        raise RuntimeError(f"Old formal daily parity failed: {parity}")

    windows = [("Full", pd.Timestamp(daily["date"].iloc[0]))]
    windows += [(label, bot.trading_day_window_start(daily["date"], CUTOFF, n)) for label, n in [("10Y", 2520), ("5Y", 1260), ("3Y", 756), ("1Y", 252)]]
    metrics = []
    for label, start in windows:
        values = bot.calc_performance(daily, start, CUTOFF)
        metrics.append({"window": label, **values})
    old_metrics = pd.read_csv(OLD_METRICS).set_index("window")
    old_window_parity = {}
    old_cutoff = pd.Timestamp("2026-09-02")
    for label, n in [("Full", None), ("10Y", 2520), ("5Y", 1260), ("3Y", 756), ("1Y", 252)]:
        before = daily.loc[daily["date"] <= old_cutoff]
        start = pd.Timestamp(before["date"].iloc[0]) if n is None else bot.trading_day_window_start(before["date"], old_cutoff, n)
        current = bot.calc_performance(before, start, old_cutoff)
        old_window_parity[label] = {field: float(current[field] - old_metrics.loc[label, field]) for field in ("annual", "maxdd", "total")}
    parity["old_window_metric_diffs"] = old_window_parity
    if any(abs(v) > 1e-10 for d in old_window_parity.values() for v in d.values()):
        raise RuntimeError("Old formal metric parity failed")

    daily_path = OUT / "formal_daily_20260924.csv.gz"
    metrics_path = OUT / "formal_metrics_20260924.csv"
    daily.to_csv(daily_path, index=False, compression="gzip", float_format="%.16g")
    pd.DataFrame(metrics).to_csv(metrics_path, index=False)
    parity["formal_daily_sha256"] = sha256(daily_path)
    parity["formal_metrics_sha256"] = sha256(metrics_path)
    (OUT / "formal_parity.json").write_text(json.dumps(parity, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"daily_rows": len(daily), "daily_sha256": parity["formal_daily_sha256"], "old_max_nav_diff": parity["max_abs_diff"]["nav"], "old_metric_diffs": old_window_parity, "metrics": metrics}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
