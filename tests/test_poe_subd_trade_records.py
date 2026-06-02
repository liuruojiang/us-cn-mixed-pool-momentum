import importlib.util
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BOT_PATH = ROOT / "poe_subd_six_etf_v1_1_bot.py"


def load_bot_module():
    spec = importlib.util.spec_from_file_location("poe_subd_six_etf_v1_1_bot", BOT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def sample_daily():
    return pd.DataFrame(
        [
            {
                "date": "2026-05-19",
                "version": "1.1",
                "position_before": "159915.SZ",
                "fraction_before": 1.0,
                "position": "159941.SZ",
                "holding_fraction": 0.5,
                "trade_target": "159941.SZ",
                "trade_fraction": 0.5,
                "turnover": 1.6523324516,
                "cost": 0.0016523324,
                "final_exposure_after_overheat": 0.5507774839,
                "staged_initial": True,
                "fill_on_down_day": False,
            },
            {
                "date": "2026-05-26",
                "version": "1.1",
                "position_before": "159941.SZ",
                "fraction_before": 0.5,
                "position": "159941.SZ",
                "holding_fraction": 1.0,
                "trade_target": "159941.SZ",
                "trade_fraction": 1.0,
                "turnover": 0.5507774839,
                "cost": 0.0005507775,
                "final_exposure_after_overheat": 1.1015549678,
                "staged_initial": False,
                "fill_on_down_day": True,
            },
            {
                "date": "2026-05-27",
                "version": "1.1",
                "position_before": "159941.SZ",
                "fraction_before": 1.0,
                "position": "159941.SZ",
                "holding_fraction": 1.0,
                "trade_target": "",
                "trade_fraction": float("nan"),
                "turnover": 0.0,
                "cost": 0.0,
                "final_exposure_after_overheat": 1.1015549678,
                "staged_initial": False,
                "fill_on_down_day": False,
            },
        ]
    )


def test_trade_records_table_shows_recent_adjustments_newest_first():
    bot = load_bot_module()

    text = bot.format_trade_records_table(sample_daily(), limit=5)

    assert "### 调仓记录 (2条)" in text
    assert "| 日期 | 策略 | 操作 | 基础仓位 | 目标敞口 | 换手 | 成本 | 说明 |" in text
    assert text.index("2026-05-26") < text.index("2026-05-19")
    assert "补: 纳指ETF(159941.SZ)" in text
    assert "减: 创业板100ETF(159915.SZ) / 加: 纳指ETF(159941.SZ)" in text
    assert "下跌日补仓" in text
    assert "新资产先建50%" in text


def test_trade_record_query_routes_to_performance_handler():
    bot = load_bot_module()

    assert bot.classify_query("最近的交易记录") == "performance"
    assert bot.classify_query("调仓记录 过去两个月") == "performance"


def test_trade_records_csv_bytes_include_full_query_window_records():
    bot = load_bot_module()

    csv_bytes = bot.trade_records_csv_bytes(
        sample_daily(),
        start=pd.Timestamp("2026-05-20"),
        end=pd.Timestamp("2026-05-27"),
    )

    text = csv_bytes.decode("utf-8-sig")
    assert "date,strategy,operation" in text
    assert "2026-05-26,SubD V1.1,补: 纳指ETF(159941.SZ)" in text
    assert "下跌日补仓" in text
    assert "2026-05-19" not in text
    assert "2026-05-27" not in text
