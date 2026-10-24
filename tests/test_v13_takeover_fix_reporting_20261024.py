"""Independent comma-parser fix review; frozen real daily inputs, no network."""
import importlib.util
import io
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "outputs/takeover_fix_20261024/report_review"


@pytest.fixture
def context(monkeypatch):
    spec = importlib.util.spec_from_file_location("independent_parser_fix", ROOT / "poe_subd_six_etf_v1_3_bot.py")
    bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot)
    daily = pd.read_csv(ROOT / "outputs/doublecheck_script_audit_20261007/final_network/confirmed_daily.csv.gz", parse_dates=["date"])
    monkeypatch.setattr(bot, "_http_get", lambda *a, **k: pytest.fail("No network permitted"))
    monkeypatch.setattr(bot, "_now_bj", lambda: datetime(2026, 10, 24, 16, tzinfo=bot.CN_TZ))
    monkeypatch.setattr(bot, "_get_daily_for_today", lambda **k: (daily.copy(), "real frozen qfq diagnostic replay"))
    monkeypatch.setattr(bot, "_write_nav_curve", lambda *a, **k: None)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    return bot, daily


class Capture:
    BotError = RuntimeError

    def __init__(self, query):
        self.query = SimpleNamespace(text=query)
        self.writes, self.attachments = [], []
    def start_message(self): return self
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def write(self, text): self.writes.append(text)
    def attach_file(self, **item): self.attachments.append(item)


@pytest.mark.parametrize("case,query,windows", [
    ("mixed", "交易记录 2024年，2025年;2026年1月、2025年和2024年", [("2024-01-01", "2024-12-31"), ("2025-01-01", "2025-12-31"), ("2026-01-01", "2026-01-31")]),
    ("empty_parts", "交易记录 ，,；2024年 ， ,\n2025年,， ;", [("2024-01-01", "2024-12-31"), ("2025-01-01", "2025-12-31")]),
    ("whitespace", "交易记录 2024年\t，\n 2025年 ,\t2026年1月", [("2024-01-01", "2024-12-31"), ("2025-01-01", "2025-12-31"), ("2026-01-01", "2026-01-31")]),
    ("all_separators", "交易记录 2024年，以及2025年；2024年;2025年、2024年和2025年", [("2024-01-01", "2024-12-31"), ("2025-01-01", "2025-12-31")]),
    ("overlapping", "交易记录 2024年12月至2025年2月，2025年1月,2025年2月", [("2024-12-01", "2025-02-28"), ("2025-01-01", "2025-01-31"), ("2025-02-01", "2025-02-28")]),
    ("dedupe_grammar", "交易记录 2024年，2024-01-01到2024-12-31，2025年", [("2024-01-01", "2024-12-31"), ("2025-01-01", "2025-12-31")]),
    ("leap_date", "交易记录 2024-02-29,2025-01-02，2025-01-02", [("2024-02-29", "2024-02-29"), ("2025-01-02", "2025-01-02")]),
    ("empty_windows", "交易记录 2000年，2030年，2025年", [("2000-01-01", "2000-12-31"), ("2030-01-01", "2030-12-31"), ("2025-01-01", "2025-12-31")]),
    ("fractional_years", "交易记录 过去0.5年，过去1.5年", [("2026-04-24", "2026-10-24"), ("2025-04-24", "2026-10-24")]),
])
def test_mixed_lists_export_every_unique_explicit_window(context, monkeypatch, case, query, windows):
    bot, daily = context
    cap = Capture(query)
    monkeypatch.setattr(bot, "poe", cap)
    bot.SubDSixEtfV13Bot().run()
    exported = {item["name"]: pd.read_csv(io.BytesIO(item["contents"])) for item in cap.attachments}
    expected_names = {f"subd_v13_trade_records_{start}_{end}.csv" for start, end in windows}
    assert set(exported) == expected_names
    for start, end in windows:
        frame = exported[f"subd_v13_trade_records_{start}_{end}.csv"]
        expected = daily.loc[daily.date.between(start, end) & daily.turnover.gt(1e-12)]
        assert list(pd.to_datetime(frame.date)) == list(expected.sort_values("date", ascending=False).date)
        assert frame.cost.sum() == pytest.approx(expected.cost.sum())
        assert frame.turnover.sum() == pytest.approx(expected.turnover.sum())
    (EVIDENCE / f"fix_{case}.json").write_text(json.dumps({"query": query, "exports": {name: len(frame) for name, frame in exported.items()}}, ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.mark.parametrize("query", [
    "交易记录 2024年，2025-02-30", "交易记录 2024年,2025年13月", "交易记录 2024年，2025-12-01到2025-01-01",
    "交易记录 2024年, ,2025-02-29，2026年", "交易记录 2024年；2025年，2026-04-31", "交易记录 2024年,2025年0月",
])
def test_invalid_later_item_blocks_partial_exports(context, monkeypatch, query):
    bot, _ = context
    cap = Capture(query)
    monkeypatch.setattr(bot, "poe", cap)
    with pytest.raises(RuntimeError, match="非法日期|结束日期不能早于开始日期"):
        bot.SubDSixEtfV13Bot().run()
    assert cap.attachments == []
    assert cap.writes == []
