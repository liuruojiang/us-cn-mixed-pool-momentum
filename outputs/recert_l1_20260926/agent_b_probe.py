"""Independent read-only market-data probe for L1 recertification.

Does not import the strategy module or write to its caches.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
END = pd.Timestamp("2026-09-24")
CODES = ["159915.SZ", "159941.SZ", "513030.SH", "513520.SH", "159985.SZ", "518880.SH"]
OLD = ROOT / "quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/price_snapshot_qfq.csv.gz"
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"}


def get_json(url: str, params: dict) -> dict:
    last = None
    for n in range(3):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            last = exc
            time.sleep(n + 1)
    raise RuntimeError(f"{url}: {type(last).__name__}: {last}")


def tencent(code: str) -> tuple[pd.Series, str]:
    number, suffix = code.split(".")
    key = ("sz" if suffix == "SZ" else "sh") + number
    until = END
    all_rows = []
    all_keys = []
    for _ in range(16):
        j = get_json(
            "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
            {"param": f"{key},day,2010-01-01,{until.date()},640,qfq"},
        )
        node = (j.get("data") or {}).get(key) or {}
        payload_key = "qfqday" if "qfqday" in node else "day" if "day" in node else "missing"
        if payload_key == "missing":
            raise RuntimeError(f"{code}: qfqday/day missing")
        all_keys.append(payload_key)
        rows = node[payload_key]
        if not rows:
            break
        all_rows.extend(rows)
        first = pd.Timestamp(rows[0][0])
        if len(rows) < 640 or first <= pd.Timestamp("2010-01-01"):
            break
        until = first - pd.Timedelta(days=1)
    if len(set(all_keys)) != 1:
        raise RuntimeError(f"{code}: payload key changed: {all_keys}")
    df = pd.DataFrame(all_rows)
    s = pd.Series(df.iloc[:, 2].astype(float).to_numpy(), index=pd.to_datetime(df.iloc[:, 0]), name=code)
    s = s[~s.index.duplicated(keep="last")].sort_index().loc[:END]
    if s.empty or s.index.max() != END:
        raise RuntimeError(f"{code}: stale/empty ending {s.index.max() if not s.empty else None}")
    return s, all_keys[0]


def cnfin_recent(code: str) -> pd.Series:
    j = get_json(
        "https://quotedata.cnfin.com/quote/v1/kline",
        {
            "prod_code": code,
            "candle_period": "6",
            "get_type": "range",
            "start_date": "20260801",
            "end_date": "20260924",
            "fields": "open_px,high_px,low_px,close_px,business_amount,business_balance",
        },
    )
    candle = (j.get("data") or {}).get("candle") or {}
    columns = candle.get("fields") or []
    if "min_time" not in columns or "close_px" not in columns:
        raise RuntimeError(f"{code}: CNFin missing columns: {columns}")
    df = pd.DataFrame(candle.get(code) or [], columns=columns)
    s = pd.Series(df["close_px"].astype(float).to_numpy(), index=pd.to_datetime(df["min_time"].astype(str)), name=code)
    s = s[~s.index.duplicated(keep="last")].sort_index().loc[:END]
    if s.empty or s.index.max() != END:
        raise RuntimeError(f"{code}: CNFin stale/empty ending {s.index.max() if not s.empty else None}")
    return s


def main() -> None:
    OUT.mkdir(exist_ok=True)
    tencent_series = {}
    cnfin_series = {}
    metadata = {}
    for code in CODES:
        tencent_series[code], key = tencent(code)
        cnfin_series[code] = cnfin_recent(code)
        metadata[code] = {"tencent_payload": key}
        print(code, key, len(tencent_series[code]), tencent_series[code].index.min().date(), tencent_series[code].iloc[-1], len(cnfin_series[code]), cnfin_series[code].iloc[-1], flush=True)
    refreshed = pd.concat(tencent_series.values(), axis=1).sort_index()
    recent_raw = pd.concat(cnfin_series.values(), axis=1).sort_index()
    refreshed.index.name = "date"
    recent_raw.index.name = "date"
    refreshed.to_csv(OUT / "agent_b_tencent_qfq.csv.gz", float_format="%.6f")
    recent_raw.to_csv(OUT / "agent_b_cnfin_recent_raw.csv", float_format="%.6f")
    old = pd.read_csv(OLD, parse_dates=["date"]).set_index("date")
    audit = {"old_rows": len(old), "new_rows": len(refreshed), "new_last": str(refreshed.index.max().date()), "symbols": {}, "source": {}}
    for code in CODES:
        a = old[code].dropna()
        b = refreshed[code].dropna()
        common = a.index.intersection(b.index)
        diffs = (a.loc[common] - b.loc[common]).abs()
        changed = diffs[diffs > 1e-9]
        tail = recent_raw[code].dropna().index.intersection(b.index)
        raw_diff = (recent_raw.loc[tail, code] - b.loc[tail]).abs()
        audit["symbols"][code] = {
            "old_start": str(a.index.min().date()), "old_end": str(a.index.max().date()), "old_rows": len(a),
            "new_start": str(b.index.min().date()), "new_end": str(b.index.max().date()), "new_rows": len(b),
            "old_new_common_rows": len(common), "old_new_changed_rows": len(changed),
            "first_old_new_change": str(changed.index.min().date()) if len(changed) else None,
            "first_old_new_old_close": float(a.loc[changed.index.min()]) if len(changed) else None,
            "first_old_new_new_close": float(b.loc[changed.index.min()]) if len(changed) else None,
            "old_new_max_abs_diff": float(diffs.max()),
            "2026_09_24_qfq": float(b.loc[END]), "2026_09_24_raw": float(recent_raw.loc[END, code]),
            "recent_raw_common_rows": len(tail), "recent_raw_qfq_changed_rows": int((raw_diff > 1e-9).sum()),
            "recent_raw_qfq_max_abs_diff": float(raw_diff.max()),
            "tencent_payload_key": metadata[code]["tencent_payload"],
        }
    for name in ["agent_b_tencent_qfq.csv.gz", "agent_b_cnfin_recent_raw.csv"]:
        p = OUT / name
        audit["source"][name] = hashlib.sha256(p.read_bytes()).hexdigest()
    (OUT / "agent_b_data_audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
