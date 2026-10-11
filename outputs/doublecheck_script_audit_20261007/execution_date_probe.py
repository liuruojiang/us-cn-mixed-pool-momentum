"""Reproduce the exhaustive supported year/month parser double-check."""
import hashlib
import importlib.util
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CODE = ROOT / "poe_subd_six_etf_v1_3_bot.py"
spec = importlib.util.spec_from_file_location("v13_date_doublecheck", CODE)
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)
now = datetime(2026, 10, 7)
cases, mismatches = 0, []
for mode in ("to_now", "range"):
    for year in range(2000, 2027):
        for month in range(1, 13):
            for sep in ("-", "/", ".", "年"):
                tail = "月" if sep == "年" else ""
                start_text = f"{year}{sep}{month:02}{tail}"
                expected_start = pd.Timestamp(year, month, 1)
                if mode == "to_now":
                    query = f"{start_text}至今"
                    expected_end = pd.Timestamp("2026-10-07")
                else:
                    end_month = month % 12 + 1
                    query = f"{start_text}到{year + 1}{sep}{end_month:02}{tail}"
                    expected_end = pd.Timestamp(year + 1, end_month, 1) + pd.offsets.MonthEnd(0)
                cases += 1
                result = bot.parse_date_range(query, now=now)
                if result != (expected_start, expected_end):
                    mismatches.append({"query": query, "actual": [str(value) for value in result]})
observations = {}
for query in ("过去1.5个月", "过去半个月", "2026-12至今", "2026-12-01至今"):
    observations[query] = [str(value) for value in bot.parse_date_range(query, now=now)]
result = {
    "code_sha256": hashlib.sha256(CODE.read_bytes()).hexdigest(),
    "now_bj_day": "2026-10-07",
    "supported_grammar_cases": cases,
    "mismatches": mismatches,
    "status": "PASS" if not mismatches else "FAIL",
    "observations_not_classified_as_bugs": observations,
    "basis": "actual parser calls; no market prices or strategy returns simulated",
}
out = Path(__file__).with_name("execution_date_probe.json")
out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
