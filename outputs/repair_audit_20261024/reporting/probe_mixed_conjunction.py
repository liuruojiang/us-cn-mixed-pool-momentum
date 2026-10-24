"""Diagnostic actual-query replay: mixed Chinese separators must not drop a year."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('reporting_audit_test_support', ROOT / 'tests/test_v13_postfix_reporting_20261024.py')
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
query = '交易记录 2024年、2025年和2026年'
with pytest.MonkeyPatch.context() as monkeypatch:
    context = support.context.__wrapped__(monkeypatch)
    bot, daily = context
    cap = support.run_query(context, monkeypatch, query)
    actual = {a['name']: len(pd.read_csv(io.BytesIO(a['contents']))) for a in cap.attachments}
    expected = {f'subd_v13_trade_records_{year}-01-01_{year}-12-31.csv': int((daily.date.dt.year.eq(year) & daily.turnover.gt(1e-12)).sum()) for year in (2024, 2025, 2026)}
    out = {'query': query, 'code_sha256': hashlib.sha256((ROOT / 'poe_subd_six_etf_v1_3_bot.py').read_bytes()).hexdigest(), 'expected': expected, 'actual': actual, 'missing': sorted(set(expected) - set(actual)), 'same_single_delimiter_control': str(bot.parse_all_date_ranges('交易记录 2024年、2025年、2026年', now=pd.Timestamp('2026-10-24')))}
    Path(__file__).with_name('mixed_conjunction_result.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    Path(__file__).with_name('mixed_conjunction_report.txt').write_text(''.join(cap.writes), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=True))
    assert actual == expected, 'Explicitly requested 2026 silently omitted by mixed conjunction parsing'
