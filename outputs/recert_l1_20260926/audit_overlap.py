"""L1 raw/aligned overlap audit; never calculates signals or performance."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
OLD = ROOT / "quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/price_snapshot_qfq.csv.gz"
NEW_RAW = OUT / "prices_raw_qfq_through_20260924.csv.gz"
NEW_ALIGNED = OUT / "prices_aligned_qfq_through_20260924.csv.gz"
FLAGS = OUT / "price_ffill_flags_through_20260924.csv.gz"


def read(path):
    frame = pd.read_csv(path, parse_dates=["date"]).set_index("date")
    assert frame.index.is_unique and frame.index.is_monotonic_increasing
    return frame


def mismatches(left, right):
    missing = left.isna() ^ right.isna()
    numeric = left.notna() & right.notna() & ~np.isclose(left, right, rtol=0, atol=1e-12)
    return missing | numeric


def main():
    old, raw, aligned, flags = map(read, (OLD, NEW_RAW, NEW_ALIGNED, FLAGS))
    cols = list(old.columns)
    assert cols == list(raw.columns) == list(aligned.columns) == list(flags.columns)
    assert old.index.equals(raw.index[: len(old)])
    assert aligned.index.equals(raw.index)
    overlap = raw.index.intersection(old.index)
    raw_bad = mismatches(old.loc[overlap, cols], raw.loc[overlap, cols])
    aligned_bad = mismatches(old.loc[overlap, cols], aligned.loc[overlap, cols])
    raw_diffs = []
    for row, col in zip(*np.where(raw_bad.to_numpy())):
        day, code = overlap[row], cols[col]
        raw_diffs.append({"date": str(day.date()), "code": code,
                          "old_snapshot": float(old.at[day, code]) if pd.notna(old.at[day, code]) else None,
                          "new_raw": float(raw.at[day, code]) if pd.notna(raw.at[day, code]) else None,
                          "new_aligned": float(aligned.at[day, code]) if pd.notna(aligned.at[day, code]) else None,
                          "ffill_flag": bool(flags.at[day, code])})
    old_hash = hashlib.sha256(OLD.read_bytes()).hexdigest()
    report = {
        "old_snapshot_sha256": old_hash,
        "new_raw_sha256": hashlib.sha256(NEW_RAW.read_bytes()).hexdigest(),
        "new_aligned_sha256": hashlib.sha256(NEW_ALIGNED.read_bytes()).hexdigest(),
        "old_rows": len(old), "new_rows": len(raw),
        "overlap_rows": len(overlap),
        "new_dates": [str(d.date()) for d in raw.index.difference(old.index)],
        "old_vs_new_raw_mismatch_count": int(raw_bad.to_numpy().sum()),
        "old_vs_new_raw_first_mismatch": raw_diffs[0] if raw_diffs else None,
        "old_vs_new_raw_all_mismatches": raw_diffs,
        "old_vs_new_aligned_mismatch_count": int(aligned_bad.to_numpy().sum()),
        "new_date_missing_count_by_asset": {code: int(raw.loc[raw.index.difference(old.index), code].isna().sum()) for code in cols},
        "ffill_dates_by_asset": {code: [str(d.date()) for d in flags.index[flags[code].astype(bool)]] for code in cols},
        "latest_close": {code: float(raw.iloc[-1][code]) for code in cols},
    }
    (OUT / "overlap_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if len(report["new_dates"]) != 16 or report["old_vs_new_aligned_mismatch_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
