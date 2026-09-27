"""Independent CNFin raw daily history comparison for six ETF L1 audit."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pandas as pd
import requests

OUT = Path(__file__).resolve().parent
CODES = ["159915.SZ", "159941.SZ", "513030.SH", "513520.SH", "159985.SZ", "518880.SH"]
END = pd.Timestamp("2026-09-24")


def fetch(code: str) -> pd.Series:
    until = END
    rows = []
    fields = None
    for _ in range(10):
        params = {
            "prod_code": code, "candle_period": "6", "get_type": "range",
            "start_date": "20100101", "end_date": until.strftime("%Y%m%d"),
            "fields": "open_px,high_px,low_px,close_px,business_amount,business_balance",
        }
        error = None
        for n in range(3):
            try:
                resp = requests.get("https://quotedata.cnfin.com/quote/v1/kline", params=params, timeout=30)
                resp.raise_for_status()
                candle = (resp.json().get("data") or {}).get("candle") or {}
                fields = candle.get("fields") or []
                page = candle.get(code) or []
                break
            except Exception as exc:
                error = exc
                time.sleep(n + 1)
        else:
            raise RuntimeError(f"{code}: {error}")
        if not page:
            break
        rows.extend(page)
        first = pd.Timestamp(str(page[0][0]))
        if len(page) < 2001 or first <= pd.Timestamp("2010-01-01"):
            break
        until = first - pd.Timedelta(days=1)
    df = pd.DataFrame(rows, columns=fields)
    s = pd.Series(df["close_px"].astype(float).to_numpy(), index=pd.to_datetime(df["min_time"].astype(str)), name=code)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s


def main() -> None:
    qfq = pd.read_csv(OUT / "agent_b_tencent_qfq.csv.gz", parse_dates=["date"]).set_index("date")
    series = {}
    comparison = {}
    for code in CODES:
        raw = fetch(code)
        series[code] = raw
        q = qfq[code].dropna()
        common = raw.index.intersection(q.index)
        delta = (raw.loc[common] - q.loc[common]).abs()
        changed = delta[delta > 1e-9]
        raw_only = raw.index.difference(q.index)
        q_only = q.index.difference(raw.index)
        comparison[code] = {
            "raw_first": str(raw.index.min().date()), "raw_last": str(raw.index.max().date()), "raw_rows": len(raw),
            "common_rows": len(common), "changed_rows": len(changed),
            "first_changed": str(changed.index.min().date()) if len(changed) else None,
            "max_abs_diff": float(delta.max()),
            "raw_only_dates": [str(x.date()) for x in raw_only[:10]],
            "qfq_only_dates": [str(x.date()) for x in q_only[:10]],
        }
        print(code, json.dumps(comparison[code]), flush=True)
    panel = pd.concat(series.values(), axis=1).sort_index()
    panel.index.name = "date"
    path = OUT / "agent_b_cnfin_full_raw.csv.gz"
    panel.to_csv(path, float_format="%.6f")
    comparison["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    (OUT / "agent_b_cnfin_full_audit.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
