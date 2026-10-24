"""Independent takeover reporting checks using preserved real qfq daily data.

Only the archived-loader boundary and Poe transport are replaced. No synthetic
market prices are used. Explicit corrupted-metadata and transport faults are
diagnostic tests, not strategy performance evidence.
"""
import importlib.util
import io
import json
import os
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SAVED = ROOT / "outputs/doublecheck_script_audit_20261007/final_network"
EVIDENCE = Path(os.environ.get("V13_TAKEOVER_REPORT_EVIDENCE", ROOT / "outputs/takeover_fix_20261024/scratch/reporting"))


@pytest.fixture
def context(monkeypatch):
    spec = importlib.util.spec_from_file_location("takeover_reporting", ROOT / "poe_subd_six_etf_v1_3_bot.py")
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)
    daily = pd.read_csv(SAVED / "confirmed_daily.csv.gz", parse_dates=["date"])
    calendar = pd.DatetimeIndex(pd.to_datetime(pd.read_csv(ROOT / "outputs/script_audit_20261007/calendar_cache_for_replay.csv")["trade_date"]))
    monkeypatch.setattr(bot, "_http_get", lambda *a, **k: pytest.fail("No network in frozen replay"))
    monkeypatch.setattr(bot, "_HAS_AKSHARE", False)
    monkeypatch.setattr(bot, "_load_cached_cn_trading_days", lambda: (calendar, calendar.max(), calendar.min(), calendar.max()))
    monkeypatch.setattr(bot, "_now_bj", lambda: datetime(2026, 10, 24, 16, tzinfo=bot.CN_TZ))
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    return bot, daily


class Capture:
    BotError = RuntimeError

    def __init__(self, query, fail_suffix=None):
        self.query = SimpleNamespace(text=query)
        self.writes, self.attachments, self.attempts = [], [], []
        self.fail_suffix = fail_suffix

    def start_message(self): return self
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def write(self, text): self.writes.append(text)
    def overwrite(self, text): self.writes = [text]
    def attach_file(self, **item):
        self.attempts.append(item["name"])
        if self.fail_suffix and item["name"].endswith(self.fail_suffix):
            raise RuntimeError("diagnostic attachment upload failure")
        self.attachments.append(item)


def run_query(context, monkeypatch, query, charts=False):
    bot, daily = context
    capture = Capture(query)
    monkeypatch.setattr(bot, "poe", capture)
    monkeypatch.setattr(bot, "_get_daily_for_today", lambda **k: (daily.copy(), "archived real qfq diagnostic replay"))
    if not charts:
        monkeypatch.setattr(bot, "_write_nav_curve", lambda *a, **k: None)
    bot.SubDSixEtfV13Bot().run()
    return capture


@pytest.mark.parametrize("separator,case", [("，", "chinese_comma"), (",", "ascii_comma"), ("、", "enumeration"), ("；", "semicolon"), ("和", "conjunction")])
def test_all_explicit_years_reach_actual_handler_csv(context, monkeypatch, separator, case):
    _, daily = context
    query = f"交易记录 2024年{separator}2025年"
    cap = run_query(context, monkeypatch, query)
    exports = {item["name"]: pd.read_csv(io.BytesIO(item["contents"])) for item in cap.attachments}
    expected_counts = {
        str(year): int((daily.date.between(f"{year}-01-01", f"{year}-12-31") & daily.turnover.gt(1e-12)).sum())
        for year in (2024, 2025)
    }
    evidence = {"query": query, "actual_exports": {name: len(frame) for name, frame in exports.items()}, "expected_trade_rows": expected_counts}
    (EVIDENCE / f"requested_years_{case}.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    (EVIDENCE / f"requested_years_{case}.txt").write_text("".join(cap.writes), encoding="utf-8")
    assert len(exports) == 2, evidence
    for year in (2024, 2025):
        frame = exports[f"subd_v13_trade_records_{year}-01-01_{year}-12-31.csv"]
        expected = daily.loc[daily.date.between(f"{year}-01-01", f"{year}-12-31") & daily.turnover.gt(1e-12)]
        assert set(pd.to_datetime(frame.date)) == set(expected.date)
        assert frame.cost.sum() == pytest.approx(expected.cost.sum())


@pytest.mark.parametrize("separator", ["，", ",", "、"])
def test_invalid_later_explicit_date_not_silently_ignored(context, separator):
    bot, _ = context
    with pytest.raises(ValueError, match="非法日期"):
        bot.parse_all_date_ranges(f"交易记录 2024年{separator}2025-02-30", now="2026-10-24")


@pytest.mark.parametrize("separator,case", [("，", "chinese_comma"), (",", "ascii_comma"), ("、", "enumeration")])
def test_disjoint_month_ranges_reach_handler_csv(context, monkeypatch, separator, case):
    query = f"交易记录 2024年11月至2025年1月{separator}2025年6月至2025年8月"
    cap = run_query(context, monkeypatch, query)
    expected = {"subd_v13_trade_records_2024-11-01_2025-01-31.csv", "subd_v13_trade_records_2025-06-01_2025-08-31.csv"}
    actual = {item["name"] for item in cap.attachments}
    evidence = {"query": query, "actual": sorted(actual), "expected": sorted(expected)}
    (EVIDENCE / f"requested_months_{case}.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    assert actual == expected, evidence


@pytest.mark.parametrize("query,kind", [("实时 信号 净值曲线", "live_signal"), ("实 时 参数 回撤", "live_params"), ("交易记录 2024年", "performance"), ("参数", "params")])
def test_dispatch_preserves_live_and_static_intent(context, query, kind):
    bot, _ = context
    assert bot.classify_query(query) == kind


@pytest.mark.parametrize("query", ["信号", "实时信号", "实时参数"])
def test_stale_archived_data_never_claims_execution(context, monkeypatch, query):
    cap = run_query(context, monkeypatch, query)
    output = "".join(cap.writes)
    assert "数据滞后" in output
    assert "信号有效，无需下单。" not in output
    if query == "实时参数":
        assert "当前是否需要执行: **否**" in output
    else:
        assert "不输出实盘动作" in output


def test_nav_csv_metric_agreement_and_png_signature(context, monkeypatch):
    bot, daily = context
    cap = run_query(context, monkeypatch, "净值曲线 2025年", charts=True)
    nav_csv = next(item for item in cap.attachments if "_nav_" in item["name"] and item["name"].endswith(".csv"))
    nav_png = next(item for item in cap.attachments if item["name"].endswith(".png"))
    points = pd.read_csv(io.BytesIO(nav_csv["contents"]))
    expected = daily.loc[daily.date.between("2025-01-01", "2025-12-31")]
    assert list(pd.to_datetime(points.date)) == list(expected.date)
    assert nav_png["contents"].startswith(b"\x89PNG\r\n\x1a\n")
    assert points.nav_norm.iloc[0] == 1.0
    metric = bot.calc_performance(daily, pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-31"))
    assert points.nav_norm.iloc[-1] - 1 == pytest.approx(metric["total"])
    assert points.drawdown.min() == pytest.approx(metric["maxdd"])
    for item in (nav_csv, nav_png):
        (EVIDENCE / item["name"]).write_bytes(item["contents"])


def test_csv_upload_failure_preserves_real_png_and_reports_na(context):
    bot, daily = context
    cap = Capture("净值曲线", fail_suffix=".csv")
    bot._write_nav_curve(cap, daily, "2025", pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-31"))
    assert len(cap.attachments) == 1
    assert cap.attachments[0]["name"].endswith(".png")
    assert "逐日CSV: N/A:" in "".join(cap.writes)
