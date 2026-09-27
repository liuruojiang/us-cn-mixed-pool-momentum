"""Independent post-fix L7 audit from the saved 2026-09-24 L1 capture."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import re
import sys
from datetime import datetime
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
EPS = 1e-10


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


def require(ok, message):
    if not bool(ok):
        raise AssertionError(message)


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    return sha_bytes(path.read_bytes())


def compact_digest(frame):
    cols = ["date", "position_before", "position", "turnover", "cost", "return", "nav"]
    x = frame[cols].copy()
    x["date"] = pd.to_datetime(x["date"]).dt.strftime("%Y-%m-%d")
    for col in ("turnover", "cost", "return", "nav"):
        x[col] = x[col].astype(float).round(8)
    return sha_bytes(x.to_csv(index=False).encode("utf-8"))


def load_bot():
    spec = importlib.util.spec_from_file_location("l7_postfix_independent", BOT)
    bot = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = bot
    spec.loader.exec_module(bot)
    bot.TRADING_CALENDAR_CACHE_PATH = L1 / "calendar_cache_for_audit.csv"
    return bot


def query(bot, daily, name):
    cap = Capture()
    bot._get_daily_for_today = lambda **_: (daily.copy(), "L1 frozen qfq 2026-09-24, local replay")
    bot.poe.start_message = lambda: cap
    bot.poe.query = SimpleNamespace(text=name)
    bot.SubDSixEtfV13Bot().run()
    return cap


def percent(text):
    return float(text.strip().rstrip("%")) / 100


def parse_table(text, keys):
    found = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells[0] in keys:
            found[cells[0]] = cells
    return found


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((L1 / "capture_manifest.json").read_text(encoding="utf-8"))
    for item in ("raw", "aligned", "flags", "sources"):
        require(file_sha(Path(manifest[item]["path"])) == manifest[item]["sha256"], f"L1 {item} hash")
    bot = load_bot()
    raw = pd.read_csv(manifest["raw"]["path"], parse_dates=["date"]).set_index("date")
    sources = pd.read_csv(manifest["sources"]["path"])
    bot._validate_qfq_sources(sources)
    previous_loader = bot.load_close
    try:
        bot.load_close = lambda config: (raw.copy(), sources.copy())
        replay, source_note = bot._build_v13_daily(end_date=pd.Timestamp("2026-09-24"), data_state="confirmed",
                                                   now=datetime(2026, 9, 27, 10, 0, tzinfo=bot.CN_TZ))
    finally:
        bot.load_close = previous_loader
    saved = pd.read_csv(L2 / "formal_daily_20260924.csv.gz", parse_dates=["date"])
    independent = pd.read_csv(L2 / "agent_b_rebuilt_daily.csv.gz", parse_dates=["date"])
    require(len(replay) == len(saved) == len(independent) == 3594, "daily row count")
    require(replay.date.iloc[-1] == pd.Timestamp("2026-09-24"), "replay cutoff")
    require(replay.date.equals(saved.date) and replay.date.equals(independent.date), "daily dates")
    for col in ("position_before", "position"):
        require(replay[col].astype(str).equals(independent[col].astype(str)), f"independent {col}")
    daily_diffs = {}
    for col in ("turnover", "cost", "gross_return", "return", "nav"):
        reference = independent if col in independent else saved
        delta = float(np.max(np.abs(replay[col].to_numpy(float) - reference[col].to_numpy(float))))
        daily_diffs[col] = delta
        require(delta < (2e-10 if col == "nav" else 1e-12), f"daily {col} {delta}")
    require(compact_digest(replay) == compact_digest(saved), "economics digest changed")

    captures = {q: query(bot, replay, q) for q in
                ("表现", "信号", "交易记录 过去两个月", "净值曲线 过去两年")}
    perf, sig, recent, curve = (captures[q] for q in captures)
    require("信号日: **2026-09-24**" in sig.text, "signal date")
    require("上次模型调仓日: **2026-09-24**" in sig.text, "model trade label")
    require("上次实际成交日" not in sig.text, "actual fill claim remains")
    require("100.00%" in sig.text and "0.100%" in sig.text and "159941.SZ" in sig.text, "last event signal")
    require("最新日度数据: **2026-09-24**" in perf.text, "performance endpoint")

    window_rows = parse_table(perf.text, ("full_sample", "10Y", "5Y", "3Y", "1Y"))
    require(len(window_rows) == 5, "five windows")
    checks = []
    for label, cells in window_rows.items():
        start, end = cells[1].split("~")
        sub = independent[(independent.date >= start) & (independent.date <= end)].copy()
        n = len(sub)
        changes = sub.nav.pct_change(fill_method=None).iloc[1:]
        total = float(sub.nav.iloc[-1] / sub.nav.iloc[0] - 1)
        annual = float((1 + total) ** (252 / (n - 1)) - 1)
        norm = sub.nav / sub.nav.iloc[0]
        dd = float((norm / norm.cummax() - 1).min())
        vol = float(changes.std(ddof=0) * np.sqrt(252))
        sharpe = float(changes.mean() / changes.std(ddof=0) * np.sqrt(252))
        trades = int((sub.turnover > 1e-12).sum())
        displayed = {"total": percent(cells[3]), "annual": percent(cells[4]),
                     "maxdd": percent(cells[5]), "vol": percent(cells[6]),
                     "sharpe": float(cells[7]), "trades": int(cells[8])}
        for key, expected in (("total", total), ("annual", annual), ("maxdd", dd), ("vol", vol)):
            require(abs(displayed[key] - expected) <= 0.000051, f"{label} {key}")
        require(abs(displayed["sharpe"] - sharpe) <= 0.0051, f"{label} sharpe")
        require(displayed["trades"] == trades and int(cells[2]) == n and end == "2026-09-24", f"{label} rows/trades/end")
        checks.append({"label": label, "start": start, "end": end, "rows": n,
                       "annual_independent": annual, "maxdd_independent": dd,
                       "vol_independent": vol, "sharpe_independent": sharpe,
                       "trades": trades, "displayed": displayed})

    yearly = parse_table(perf.text, ("2020",))
    require("2020" in yearly, "2020 yearly row")
    y = yearly["2020"]
    ystart, yend = y[1].split("~")
    ypart = independent[(independent.date >= ystart) & (independent.date <= yend)].copy()
    first_day_ret = float(ypart["return"].iloc[0])
    year_wealth = (1 + ypart["return"].astype(float)).cumprod()
    yreturn = float(year_wealth.iloc[-1] - 1)
    ydd = float((year_wealth / np.maximum(1.0, year_wealth.cummax()) - 1).min())
    require(abs(percent(y[3]) - yreturn) <= 0.000051, "2020 includes first day return")
    require(abs(percent(y[4]) - ydd) <= 0.000051, "2020 drawdown baseline")
    require(int(y[2]) == len(ypart), "2020 rows")

    attachment_results = {}
    for name in ("表现", "交易记录 过去两个月", "净值曲线 过去两年"):
        cap = captures[name]
        nav_csvs = [f for f in cap.files if f["name"].startswith("subd_v13_nav_") and f["name"].endswith(".csv")]
        nav_pngs = [f for f in cap.files if f["name"].startswith("subd_v13_nav_") and f["name"].endswith(".png")]
        trade_csvs = [f for f in cap.files if f["name"].startswith("subd_v13_trade_records_") and f["name"].endswith(".csv")]
        require(len(nav_csvs) == len(nav_pngs) == len(trade_csvs) == 1, f"{name} attachment trio")
        nav_file, png_file, trade_file = nav_csvs[0], nav_pngs[0], trade_csvs[0]
        require(Path(nav_file["name"]).stem == Path(png_file["name"]).stem, f"{name} paired stem")
        points = pd.read_csv(io.BytesIO(nav_file["contents"]), encoding="utf-8-sig")
        require(points.columns.tolist() == ["date", "nav_norm", "drawdown"], f"{name} NAV columns")
        require(points.date.iloc[-1] == "2026-09-24", f"{name} NAV end")
        require(nav_file["name"].endswith(f"{points.date.iloc[0]}_2026-09-24.csv"), f"{name} NAV filename")
        require(png_file["name"].endswith(f"{points.date.iloc[0]}_2026-09-24.png"), f"{name} PNG filename")
        require(trade_file["name"].endswith("2026-09-24.csv"), f"{name} trade filename end")
        ref = independent.set_index(independent.date.dt.strftime("%Y-%m-%d")).loc[points.date].copy()
        expected_nav = ref.nav.to_numpy(float) / float(ref.nav.iloc[0])
        expected_dd = expected_nav / np.maximum.accumulate(expected_nav) - 1
        require(np.max(np.abs(points.nav_norm.to_numpy(float) - expected_nav)) < EPS, f"{name} NAV series")
        require(np.max(np.abs(points.drawdown.to_numpy(float) - expected_dd)) < EPS, f"{name} DD series")
        require(abs(points.nav_norm.iloc[0] - 1) < EPS, f"{name} NAV base")
        img = Image.open(io.BytesIO(png_file["contents"]))
        require(img.format == "PNG" and img.size[0] > 1000 and img.size[1] > 500, f"{name} PNG")
        records = pd.read_csv(io.BytesIO(trade_file["contents"]), encoding="utf-8-sig")
        if len(records):
            require(records.date.iloc[0] <= "2026-09-24", f"{name} last trade")
            require(np.max(np.abs(records.cost.astype(float) - .001 * records.turnover.astype(float))) < EPS, f"{name} fees")
        attachment_results[name] = {"range": [points.date.iloc[0], points.date.iloc[-1]],
                                    "nav_rows": len(points), "nav_end": float(points.nav_norm.iloc[-1]),
                                    "drawdown_min": float(points.drawdown.min()), "trade_rows": len(records),
                                    "names": [f["name"] for f in cap.files],
                                    "sha256": {f["name"]: sha_bytes(f["contents"]) for f in cap.files}}
    require("2026-09-27.csv" not in " ".join(attachment_results["交易记录 过去两个月"]["names"]), "weekend filename")

    broken = replay.copy()
    broken.loc[broken.index[-1], "return"] = np.nan
    cap = Capture()
    bot._get_daily_for_today = lambda **_: (broken.copy(), "NaN injection")
    bot.poe.start_message = lambda: cap
    bot.poe.query = SimpleNamespace(text="表现")
    error = ""
    try:
        bot.SubDSixEtfV13Bot().run()
    except Exception as exc:
        error = str(exc)
    require("missing return inside daily data" in error and "2026-09-24" in error and not cap.files, "NaN fail closed")

    result = {"status": "PASS", "source_sha256_postfix": file_sha(BOT),
              "source_sha256_l1": manifest["entrypoint_sha256"],
              "source_note": source_note, "l1_raw_sha256": manifest["raw"]["sha256"],
              "l1_aligned_sha256": manifest["aligned"]["sha256"],
              "l2_formal_file_sha256": file_sha(L2 / "formal_daily_20260924.csv.gz"),
              "daily_economics_digest_replay": compact_digest(replay),
              "daily_economics_digest_l2": compact_digest(saved),
              "daily_max_abs_diff": daily_diffs, "window_checks": checks,
              "year_2020": {"first_day": ystart, "first_day_return": first_day_ret,
                            "rows": len(ypart), "return": yreturn, "maxdd": ydd,
                            "displayed_return": percent(y[3]), "displayed_maxdd": percent(y[4])},
              "signal_model_trade_label": True, "attachment_checks": attachment_results,
              "nan_injection": {"error": error, "attachments": len(cap.files)}}
    (OUT / "agent_b_postfix_checks.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "agent_b_postfix_full_response.txt").write_text(perf.text, encoding="utf-8")
    (OUT / "agent_b_postfix_signal_response.txt").write_text(sig.text, encoding="utf-8")
    for f in perf.files:
        (OUT / f"agent_b_{f['name']}").write_bytes(f["contents"])
    print(json.dumps({k: v for k, v in result.items() if k not in ("window_checks", "attachment_checks")}, ensure_ascii=False, indent=2))
    print(pd.DataFrame(checks)[["label", "rows", "annual_independent", "maxdd_independent", "vol_independent", "sharpe_independent"]].to_string(index=False))


if __name__ == "__main__":
    main()
