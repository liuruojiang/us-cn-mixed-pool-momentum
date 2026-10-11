"""Read-only current official build and same-run Poe response checks."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "final_network"
OUT.mkdir(exist_ok=True)
SOURCE = ROOT / "poe_subd_six_etf_v1_3_bot.py"
spec = importlib.util.spec_from_file_location("current_v13_audit", SOURCE)
bot = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bot
spec.loader.exec_module(bot)
code_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
original_load = bot.load_close


def capture_load(config):
    prices, sources = original_load(config)
    prices.to_csv(OUT / "raw_prices_qfq.csv.gz", index_label="date")
    sources.to_csv(OUT / "sources.csv", index=False)
    return prices, sources


class Capture:
    BotError = RuntimeError

    def __init__(self, query):
        self.query = SimpleNamespace(text=query)
        self.writes = []
        self.attachments = []

    def start_message(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def write(self, value):
        self.writes.append(str(value))

    def overwrite(self, value):
        pass

    def attach_file(self, **item):
        (OUT / item["name"]).write_bytes(item["contents"])
        self.attachments.append(item["name"])


bot.load_close = capture_load
started = bot._now_bj()
print("Official current data build started", started.isoformat(), flush=True)
daily, source = bot._build_v13_daily(data_state="confirmed")
daily.to_csv(OUT / "confirmed_daily.csv.gz", index=False)
now = bot._now_bj()
prepared = bot.prepare_daily_for_performance(daily, now=now)
latest = prepared.date.max()
status = bot.signal_data_status(prepared, live=False, now=now)
metrics = []
for window, start, end in bot._default_performance_ranges_for_daily(prepared, latest, prepared.date.min())[:5]:
    metrics.append({"window": window, **bot.calc_performance(prepared, start, end)})
import pandas as pd
pd.DataFrame(metrics).to_csv(OUT / "window_metrics.csv", index=False)
# The official network download and build above are unmodified. UI checks reuse
# precisely that run's daily frame; they do not initiate more provider requests.
bot._get_daily_for_today = lambda **kwargs: (daily.copy(), source)
queries = ["参数", "信号", "表现", "交易记录 2026-09-30", "交易记录 2026-10-07", "表现 2001-06至今"]
captures = []
for query in queries:
    runtime = Capture(query)
    bot.poe = runtime
    bot.SubDSixEtfV13Bot().run()
    content = "".join(runtime.writes)
    assert content and "查询失败" not in content
    (OUT / f"{query.replace(' ', '_')}.txt").write_text(content, encoding="utf-8")
    captures.append({"query": query, "attachments": runtime.attachments})
files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file()}
result = {"status": "PASS", "official_build": "unmodified source fallback, alignment, engine and bar metadata",
          "ui_basis": "same fresh official build reused for response rendering; no further network refresh",
          "started_at_bj": started.isoformat(), "finished_at_bj": now.isoformat(),
          "code_sha256": code_hash, "rows": len(daily), "start": str(daily.date.min().date()),
          "end": str(latest.date()), "source": source,
          "calendar_available": status["calendar_available"], "signal_valid": status["signal_valid"],
          "tradable": status["tradable"], "queries": captures, "files": files,
          "limitations": "local Poe-compatible UI only; current holiday does not test active-session live quotes or broker fills"}
(OUT / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({key: value for key, value in result.items() if key != "files"}, ensure_ascii=False, indent=2))
