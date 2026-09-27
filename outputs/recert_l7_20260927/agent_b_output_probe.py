"""L7 output audit on L1's 2026-09-24 frozen panel; no live publishing."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
L1 = ROOT / "outputs/recert_l1_20260926"
L2 = ROOT / "outputs/recert_l2_20260926"
BOT = ROOT / "poe_subd_six_etf_v1_3_bot.py"


class Capture:
    def __init__(self):
        self.parts = []
        self.files = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def write(self, value):
        self.parts.append(str(value))

    def overwrite(self, value):
        self.parts = [str(value)]

    def attach_file(self, **kw):
        self.files.append(kw)

    @property
    def text(self):
        return "".join(self.parts)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(cond, msg):
    if not cond:
        raise AssertionError(msg)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((L1 / "capture_manifest.json").read_text(encoding="utf-8"))
    require(sha(BOT) == manifest["entrypoint_sha256"], "formal source changed")
    for key in ("raw", "aligned", "flags", "sources"):
        require(sha(Path(manifest[key]["path"])) == manifest[key]["sha256"], f"L1 {key} changed")
    formal = pd.read_csv(L2 / "formal_daily_20260924.csv.gz", parse_dates=["date"])
    independent = pd.read_csv(L2 / "agent_b_rebuilt_daily.csv.gz", parse_dates=["date"])
    require(len(formal) == len(independent) == 3594, "row count")
    require(formal.date.iloc[-1] == independent.date.iloc[-1] == pd.Timestamp("2026-09-24"), "cutoff")
    require(formal.date.equals(independent.date), "date index")
    for col in ("position_before", "position"):
        require(formal[col].astype(str).equals(independent[col].astype(str)), f"independent {col}")
    for col in ("turnover", "cost", "return", "nav"):
        delta = np.max(np.abs(formal[col].to_numpy(float) - independent[col].to_numpy(float)))
        require(delta <= (2e-10 if col == "nav" else 1e-12), f"independent {col}: {delta}")

    spec = importlib.util.spec_from_file_location("l7_six_etf_formal", BOT)
    bot = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = bot
    spec.loader.exec_module(bot)
    bot.TRADING_CALENDAR_CACHE_PATH = L1 / "calendar_cache_for_audit.csv"
    bot._get_daily_for_today = lambda **_: (formal.copy(), "L1 2026-09-24 frozen capture; L2 formal replay")
    messages = {}
    for query in ("表现", "信号", "交易记录 过去两个月", "净值曲线 过去两年"):
        cap = Capture()
        bot.poe.start_message = lambda c=cap: c
        bot.poe.query = SimpleNamespace(text=query)
        bot.SubDSixEtfV13Bot().run()
        messages[query] = cap
    perf, sig, recent, curve = (messages[q] for q in messages)
    require("最新日度数据: **2026-09-24**" in perf.text, "performance endpoint")
    require("信号日: **2026-09-24**" in sig.text, "signal endpoint")
    require("2026-09-24" in recent.text and "2026-09-24" in curve.text, "other endpoints")

    last = independent.iloc[-1]
    require(last.position == "159941.SZ" and last.position_before == "CASH", "last independent holding")
    require(last.turnover == 1 and abs(last.cost - 0.001) < 1e-14, "last independent fee")
    require("159941" in sig.text and "2026-09-24" in sig.text, "last signal asset")
    require("目标turnover: **100.00%**，成本: **0.100%**" in sig.text, "last signal cost")

    rows = {}
    for line in perf.text.splitlines():
        cells = [x.strip() for x in line.strip().strip("|").split("|")]
        if cells and cells[0] in ("full_sample", "10Y", "5Y", "3Y", "1Y") and len(cells) >= 12:
            rows["Full" if cells[0] == "full_sample" else cells[0]] = cells
    require(len(rows) == 5, f"five windows absent: {list(rows)}; report lines: {[x for x in perf.text.splitlines() if x.startswith('|')][:9]}")
    metrics = []
    for label in ("Full", "10Y", "5Y", "3Y", "1Y"):
        cells = rows[label]
        start, end = cells[1].split("~")
        sub = independent.loc[(independent.date >= start) & (independent.date <= end)].copy()
        n = len(sub)
        wealth = float(sub.nav.iloc[-1] / sub.nav.iloc[0])
        annual_correct = wealth ** (252 / (n - 1)) - 1
        annual_formal = wealth ** (252 / n) - 1
        dd = float((sub.nav / sub.nav.cummax() - 1).min())
        trades = int((sub.turnover > 1e-12).sum())
        shown_annual = float(cells[4].rstrip("%")) / 100
        shown_dd = float(cells[5].rstrip("%")) / 100
        require(end == "2026-09-24" and int(cells[2]) == n, f"{label} range/rows")
        require(abs(shown_annual - annual_formal) < 0.000051, f"{label} shown annual")
        require(abs(shown_dd - dd) < 0.000051, f"{label} shown drawdown")
        require(int(cells[8]) == trades, f"{label} trades")
        metrics.append({"window": label, "start": start, "end": end, "rows": n,
                        "annual_display": shown_annual, "annual_formal_n": annual_formal,
                        "annual_independent_n_minus_1": annual_correct,
                        "display_understates_pp": 100 * (annual_correct - annual_formal),
                        "maxdd_display": shown_dd, "maxdd_independent": dd, "trades": trades})

    attachments = {}
    for query, cap in messages.items():
        attachments[query] = []
        for item in cap.files:
            data = item["contents"]
            attachments[query].append({"name": item["name"], "type": item["content_type"],
                                        "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    csvs = [x for x in perf.files if x["name"].endswith(".csv")]
    pngs = [x for x in perf.files if x["name"].endswith(".png")]
    require(len(csvs) == len(pngs) == 1, "full-window attachment count")
    csv = pd.read_csv(io.BytesIO(csvs[0]["contents"]), encoding="utf-8-sig")
    require(len(csv) == int((independent.turnover > 0).sum()) == 379, "full CSV event count")
    require(csv.date.iloc[0] == "2026-09-24" and csv.date.iloc[-1] == "2012-02-14", "CSV endpoints")
    require(csv.date.is_unique, "duplicate event date")
    ledger = independent.set_index(independent.date.dt.strftime("%Y-%m-%d"))
    require(np.array_equal(csv.date.to_numpy(), ledger.loc[csv.date].index.to_numpy()), "CSV date alignment")
    for col in ("turnover", "cost"):
        err = np.max(np.abs(csv[col].to_numpy(float) - ledger.loc[csv.date, col].to_numpy(float)))
        require(err < 1e-12, f"CSV {col}: {err}")
    for col, ledger_col in (("actual_position_before", "position_before"), ("actual_position_next", "position")):
        require(np.array_equal(csv[col].to_numpy(str), ledger.loc[csv.date, ledger_col].to_numpy(str)), f"CSV {col}")
    require(np.max(np.abs(csv.buy_delta.to_numpy(float) + csv.sell_delta.to_numpy(float) - csv.turnover.to_numpy(float))) < 1e-12, "buy/sell turnover")
    require(np.max(np.abs(csv.cost.to_numpy(float) - 0.001 * csv.turnover.to_numpy(float))) < 1e-12, "cost equation")
    switch = csv.loc[(csv.actual_position_before != "CASH") & (csv.actual_position_next != "CASH") &
                     (csv.actual_position_before != csv.actual_position_next)]
    require(len(switch) == 194 and (switch.buy_delta == 1).all() and (switch.sell_delta == 1).all(), "double-sided switches")
    require("### 调仓记录 (379条)" in perf.text and "| 2026-09-24 |" in perf.text, "trade text")
    require("2026-09-24" in csvs[0]["name"] and "2011-12-09" in csvs[0]["name"], "CSV filename range")
    recent_csv_file = next(x for x in recent.files if x["name"].endswith(".csv"))
    recent_csv = pd.read_csv(io.BytesIO(recent_csv_file["contents"]), encoding="utf-8-sig")
    require(recent_csv.date.iloc[0] == "2026-09-24", "recent CSV actual end")
    require(recent_csv_file["name"].endswith("2026-09-27.csv"), "recent CSV nominal end")
    require("2026-09-24" in recent.text, "recent text actual endpoint")
    require(not any("nav" in x["name"].lower() and x["name"].endswith(".csv") for x in perf.files),
            "unexpected NAV CSV attachment")
    img = Image.open(io.BytesIO(pngs[0]["contents"]))
    img.verify()
    image_size = Image.open(io.BytesIO(pngs[0]["contents"])).size
    require(image_size[0] > 1000 and image_size[1] > 500, "PNG geometry")

    # A real output fault: a nonfinite final return affects all five report windows.
    broken = formal.copy()
    broken.loc[broken.index[-1], "return"] = np.nan
    bot._get_daily_for_today = lambda **_: (broken.copy(), "L7 NaN injection")
    cap = Capture()
    bot.poe.start_message = lambda: cap
    bot.poe.query = SimpleNamespace(text="表现")
    injected_error = ""
    try:
        bot.SubDSixEtfV13Bot().run()
    except Exception as exc:
        injected_error = str(exc)
    require("missing return inside daily data" in injected_error and "2026-09-24" in injected_error, "invalid return rejection")
    require(len(cap.files) == 0, "invalid data must not attach files")

    (OUT / "agent_b_full_response.txt").write_text(perf.text, encoding="utf-8")
    (OUT / "agent_b_signal_response.txt").write_text(sig.text, encoding="utf-8")
    (OUT / "agent_b_trade_records.csv").write_bytes(csvs[0]["contents"])
    (OUT / "agent_b_nav_full.png").write_bytes(pngs[0]["contents"])
    summary = {"input": "L1 2026-09-24 capture -> L2 formal replay and independent cash/shares ledger",
               "source_sha256": sha(BOT), "l1_aligned_sha256": manifest["aligned"]["sha256"],
               "cutoff": "2026-09-24", "daily_rows": 3594, "last_signal_asset": last.position,
               "last_signal_turnover": float(last.turnover), "last_signal_cost": float(last.cost),
               "window_metrics": metrics, "full_csv_events": len(csv), "full_csv_switches": len(switch),
               "full_csv_date_first": csv.date.iloc[0], "full_csv_date_last": csv.date.iloc[-1],
               "recent_csv_actual_last": recent_csv.date.iloc[0],
               "recent_csv_filename": recent_csv_file["name"],
               "nav_curve_csv_present": False,
               "actual_trade_date_label_is_model_turnover_only": True,
               "png_size": image_size, "attachments": attachments,
               "nan_injection": {"rejected_before_render": True, "error": injected_error,
                                 "attachment_count": len(cap.files)}}
    (OUT / "agent_b_output_checks.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("window_metrics", "attachments")}, ensure_ascii=False, indent=2))
    print(pd.DataFrame(metrics).to_string(index=False))


if __name__ == "__main__":
    main()
