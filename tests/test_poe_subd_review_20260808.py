import importlib.util
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
V11_PATH = ROOT / "poe_subd_six_etf_v1_1_bot.py"
V13_PATH = ROOT / "poe_subd_mixed_pool_v1_3_bot.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=[(V11_PATH, "review_v11"), (V13_PATH, "review_v13")])
def bot_module(request):
    path, name = request.param
    return load_module(path, name)


def yearly_daily() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-12-31", "2026-01-02"]),
            "nav": [1.0, 1.1],
            "turnover": [0.0, 0.0],
            "exposure_effective": [1.0, 1.0],
        }
    )


def test_v13_eval_range_label_matches_eval_start():
    module = load_module(V13_PATH, "review_v13_label")
    labels = [item[0] for item in module._default_performance_ranges(pd.Timestamp("2026-08-07"))]
    assert f"from_{module.EVAL_START.year}" in labels
    assert "from_2020" not in labels


def test_v13_short_mandatory_window_reports_insufficient_rows():
    module = load_module(V13_PATH, "review_v13_short_window")
    dates = pd.bdate_range("2026-01-01", periods=100)
    daily = pd.DataFrame({"date": dates})
    start = dict(
        (label, value)
        for label, value, _ in module._default_performance_ranges_for_daily(
            daily, dates[-1], dates[0]
        )
    )["1Y"]
    reason = module._mandatory_window_na_reason(
        "1Y", start, dates[0], available_rows=len(dates)
    )
    assert reason == "insufficient history: 100 rows < 252 trading days"


def test_v13_mandatory_windows_keep_252_row_convention():
    module = load_module(V13_PATH, "review_v13_window_convention")
    dates = pd.bdate_range("2015-01-01", periods=3000)
    daily = pd.DataFrame({"date": dates})
    ranges = {
        label: (start, end)
        for label, start, end in module._default_performance_ranges_for_daily(
            daily, dates[-1], dates[0]
        )
    }
    assert dates.get_loc(ranges["1Y"][1]) - dates.get_loc(ranges["1Y"][0]) + 1 == 252
    assert dates.get_loc(ranges["10Y"][1]) - dates.get_loc(ranges["10Y"][0]) + 1 == 2520


def test_yearly_returns_keep_first_session_after_year_boundary(bot_module):
    rows = bot_module.calc_yearly_performance(
        yearly_daily(), pd.Timestamp("2025-12-31"), pd.Timestamp("2026-01-02")
    )
    assert rows[1]["return"] == pytest.approx(0.10)


def test_standalone_iso_date_is_not_parsed_as_month_range(bot_module):
    start, end = bot_module.parse_date_range("2026-08-05的表现")
    assert start == pd.Timestamp("2026-08-05")
    assert end == pd.Timestamp("2026-08-05")


def _capture_params(module, monkeypatch) -> str:
    writes: list[str] = []

    class Message:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def write(self, value):
            writes.append(value)

        def overwrite(self, *_):
            return None

    monkeypatch.setattr(module.poe, "start_message", lambda: Message())
    bot_class = getattr(module, "SubDSixEtfV11Bot", None) or module.SubDMixedPoolV13Bot
    bot_class()._handle_params(live=False)
    return "".join(writes)


def test_v11_params_describe_cross_validated_raw_fallback(monkeypatch):
    module = load_module(V11_PATH, "review_v11_params")
    text = _capture_params(module, monkeypatch)
    assert "Sina + CNFin交叉验证raw fallback" in text
    assert "SELL腿" in text and "可卖数量" in text


def test_v13_params_and_snapshot_disclose_actual_rules(monkeypatch):
    module = load_module(V13_PATH, "review_v13_params_text")
    text = _capture_params(module, monkeypatch)
    assert str(module.LOOKBACK) in module._score_rule_text()
    assert "R²过滤关闭" in module._score_rule_text()
    assert "SELL腿" in text and "可卖数量" in text
    assert "跨市场" in module._mixed_market_timing_notice(live=False)
    assert "盘前/隔夜" in module._mixed_market_timing_notice(live=True)


@pytest.mark.parametrize("path", [V11_PATH, V13_PATH])
def test_introduction_describes_confirmed_cache(path):
    text = path.read_text(encoding="utf-8")
    assert "5分钟缓存" in text
    assert "查询时刷新" not in text
