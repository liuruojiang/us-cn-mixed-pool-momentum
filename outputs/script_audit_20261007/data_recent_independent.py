"""Independent 10-session Tencent/Sina probes; never writes formal caches."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import pandas as pd
import requests

OUT = Path(__file__).resolve().parent
CODES = ["159915.SZ", "159941.SZ", "513030.SH", "513520.SH", "159985.SZ", "518880.SH"]
SYMBOLS = {code: ("sz" if code.endswith("SZ") else "sh") + code.split(".")[0] for code in CODES}
SSE_URL = "https://www.sse.com.cn/disclosure/announcement/general/c/c_20251222_10802507.shtml"
EXPECTED = pd.bdate_range("2026-09-16", "2026-09-30").difference(pd.DatetimeIndex(["2026-09-25"]))
EXPECTED_STR = [str(date.date()) for date in EXPECTED]
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Referer": "https://gu.qq.com/"}


def probe(code, provider, timeout=12):
    symbol = SYMBOLS[code]
    if provider == "Tencent":
        url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        params = {"param": f"{symbol},day,2026-09-16,2026-10-07,10,qfq"}
    else:
        url = "https://quotes.sina.cn/cn/api/openapi.php/CN_MarketDataService.getKLineData"
        params = {"symbol": symbol, "scale": "240", "ma": "no", "datalen": "10"}
    receipt = {"code": code, "provider": provider, "url": url, "params": params}
    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
        receipt["received_at_bj"] = datetime.now(timezone(timedelta(hours=8))).isoformat()
        receipt["http_status"] = response.status_code
        receipt["response_sha256"] = hashlib.sha256(response.content).hexdigest()
        response.raise_for_status()
        raw = response.json()
        suffix = "" if timeout == 12 else f"_retry{timeout}s"
        raw_path = OUT / f"data_recent_{provider.lower()}_{code}{suffix}.json"
        raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        receipt["raw_receipt_path"] = raw_path.name
        if provider == "Tencent":
            node = raw.get("data", {}).get(symbol, {})
            payload_key = "qfqday" if "qfqday" in node else "day"
            receipt["payload_key"] = payload_key
            rows = [{"date": str(pd.Timestamp(row[0]).date()), "close": float(row[2])} for row in node[payload_key]]
            receipt["price_basis"] = "qfq request; actual payload key recorded (day is not universal qfq proof)"
        else:
            payload = raw.get("result", {}).get("data", [])
            rows = [{"date": str(pd.Timestamp(row["day"]).date()), "close": float(row["close"])} for row in payload]
            receipt["price_basis"] = "raw/unadjusted"
        receipt["rows"] = rows
        receipt["row_count"] = len(rows)
        receipt["last"] = max(row["date"] for row in rows)
        receipt["exact_expected_sessions"] = sorted(row["date"] for row in rows) == EXPECTED_STR
        receipt["ok"] = True
    except Exception as exc:
        receipt["ok"] = False
        receipt["error"] = f"{type(exc).__name__}: {exc}"
    return receipt


def main():
    receipts = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(probe, code, provider) for code in CODES for provider in ["Tencent", "Sina"]]
        for future in as_completed(futures):
            receipts.append(future.result())
    receipts.sort(key=lambda receipt: (receipt["code"], receipt["provider"]))
    comparisons = []
    for code in CODES:
        pair = {r["provider"]: r for r in receipts if r["code"] == code}
        item = {"code": code}
        if all(pair[provider]["ok"] for provider in ["Tencent", "Sina"]):
            left = {r["date"]: r["close"] for r in pair["Tencent"]["rows"]}
            right = {r["date"]: r["close"] for r in pair["Sina"]["rows"]}
            overlap = sorted(set(left) & set(right))
            item.update({"both_exact_expected_sessions": all(pair[p]["exact_expected_sessions"] for p in pair), "overlap_rows": len(overlap), "max_abs_close_diff": max((abs(left[d]-right[d]) for d in overlap), default=None), "tencent_last": pair["Tencent"]["last"], "sina_last": pair["Sina"]["last"], "tencent_0930_close": left.get("2026-09-30"), "sina_0930_close": right.get("2026-09-30")})
        else:
            item["blocked_sources"] = {p: pair[p].get("error", "unknown") for p in pair if not pair[p]["ok"]}
        comparisons.append(item)
    report = {"classification": "current direct public-source price/date cross-check; recent window only, not full-history qfq certification", "run_at_bj": datetime.now(timezone(timedelta(hours=8))).isoformat(), "official_calendar_url": SSE_URL, "expected_sessions": EXPECTED_STR, "receipts": receipts, "comparisons": comparisons}
    (OUT / "data_recent_independent_results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"run_at_bj": report["run_at_bj"], "expected_rows": len(EXPECTED_STR), "comparisons": comparisons}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
