import importlib.util
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
BOT_PATHS = (
    ROOT / "poe_subd_six_etf_v1_1_bot.py",
    ROOT / "poe_subd_mixed_pool_v1_3_bot.py",
    ROOT / "poe_subd_six_etf_v1_3_bot.py",
)


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


@pytest.fixture(params=BOT_PATHS, ids=("v1_1", "mixed_v1_3", "six_etf_v1_3"))
def module(request):
    path = request.param
    spec = importlib.util.spec_from_file_location(f"{path.stem}_cross_validated_test", path)
    loaded = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(loaded)
    return loaded


def test_direct_sina_loader_parses_raw_daily_close_without_akshare(module, monkeypatch):
    payload = {
        "result": {
            "status": {"code": 0},
            "data": [
                {"day": "2019-12-05", "close": "0.986"},
                {"day": "2019-12-06", "close": "0.984"},
            ],
        }
    }
    monkeypatch.setattr(module, "_http_get", lambda *args, **kwargs: FakeResponse(payload))

    close = module._load_sina_raw_one_close("159985.SZ", pd.Timestamp("2019-12-06"))

    assert close.index.tolist() == list(pd.to_datetime(["2019-12-05", "2019-12-06"]))
    assert close.tolist() == pytest.approx([0.986, 0.984])
    assert close.attrs["adjustment"] == module.ADJUSTMENT_CROSS_VALIDATED_RAW


def test_direct_cnfin_loader_parses_raw_daily_close(module, monkeypatch):
    payload = {
        "data": {
            "candle": {
                "fields": ["min_time", "open_px", "high_px", "low_px", "close_px"],
                "159985.SZ": [
                    [20191205, 0.983, 0.995, 0.978, 0.986],
                    [20191206, 0.993, 0.996, 0.982, 0.984],
                ],
            }
        }
    }
    monkeypatch.setattr(module, "_http_get", lambda *args, **kwargs: FakeResponse(payload))

    close = module._load_cnfin_raw_one_close("159985.SZ", pd.Timestamp("2019-12-06"))

    assert close.index.tolist() == list(pd.to_datetime(["2019-12-05", "2019-12-06"]))
    assert close.tolist() == pytest.approx([0.986, 0.984])
    assert close.attrs["adjustment"] == module.ADJUSTMENT_CROSS_VALIDATED_RAW


def test_cross_validated_raw_uses_only_common_dates(module, monkeypatch):
    dates = pd.bdate_range("2019-12-05", periods=600)
    sina = pd.Series(1.0 + pd.RangeIndex(600) / 10000.0, index=dates, name="159985.SZ")
    cnfin_dates = dates.append(pd.DatetimeIndex([dates[-1] + pd.offsets.BDay(1)]))
    cnfin = pd.Series(
        list(sina.to_numpy() + 0.001) + [float(sina.iloc[-1] + 0.002)],
        index=cnfin_dates,
        name="159985.SZ",
    )
    monkeypatch.setattr(module, "_load_sina_raw_one_close", lambda *args, **kwargs: sina)
    monkeypatch.setattr(module, "_load_cnfin_raw_one_close", lambda *args, **kwargs: cnfin)

    close = module._load_cross_validated_raw_one_close("159985.SZ", cnfin_dates[-1])

    assert close.index.equals(dates)
    assert close.tolist() == pytest.approx(sina.tolist())
    assert close.attrs["source_detail"] == module.SOURCE_DETAIL_SINA_CNFIN_CROSS_VALIDATED


@pytest.mark.parametrize(
    ("code", "first_date", "rows", "difference", "match"),
    [
        ("513030.SH", "2019-12-05", 600, 0.0, "unsupported"),
        ("159985.SZ", "2019-12-06", 600, 0.0, "listing"),
        ("159985.SZ", "2019-12-05", 499, 0.0, "overlap"),
        ("159985.SZ", "2019-12-05", 600, 0.002, "difference"),
    ],
)
def test_cross_validated_raw_rejects_invalid_contract(
    module, monkeypatch, code, first_date, rows, difference, match
):
    dates = pd.bdate_range(first_date, periods=rows)
    sina = pd.Series(1.0 + pd.RangeIndex(rows) / 10000.0, index=dates, name=code)
    cnfin = pd.Series(sina.to_numpy() + difference, index=dates, name=code)
    monkeypatch.setattr(module, "_load_sina_raw_one_close", lambda *args, **kwargs: sina)
    monkeypatch.setattr(module, "_load_cnfin_raw_one_close", lambda *args, **kwargs: cnfin)

    with pytest.raises(RuntimeError, match=match):
        module._load_cross_validated_raw_one_close(code, dates[-1])


def test_public_loader_uses_cross_validated_raw_only_after_qfq_failures(module, monkeypatch):
    dates = pd.bdate_range("2019-12-05", periods=600)
    fallback = pd.Series(1.0 + pd.RangeIndex(600) / 10000.0, index=dates, name="159985.SZ")
    fallback.attrs["source_detail"] = module.SOURCE_DETAIL_SINA_CNFIN_CROSS_VALIDATED
    calls = []

    def fail(name):
        def loader(*args, **kwargs):
            calls.append(name)
            raise RuntimeError(name)

        return loader

    def cross_loader(*args, **kwargs):
        calls.append("cross")
        return fallback

    monkeypatch.setattr(module, "_load_akshare_eastmoney_qfq_one_close", fail("akshare"))
    monkeypatch.setattr(module, "_load_tencent_qfq_one_close", fail("tencent"))
    monkeypatch.setattr(module, "_load_eastmoney_one_close", fail("eastmoney"))
    monkeypatch.setattr(module, "_load_cross_validated_raw_one_close", cross_loader)

    if module.VERSION == "1.3":
        with pytest.raises(RuntimeError, match="All historical data sources failed"):
            module._load_public_close_with_per_code_fallback(["159985.SZ"], dates[-1])
        assert calls == ["akshare", "tencent", "eastmoney"]
    else:
        prices, sources = module._load_public_close_with_per_code_fallback(
            ["159985.SZ"], dates[-1]
        )

        assert calls == ["akshare", "tencent", "eastmoney", "cross"]
        assert prices.columns.tolist() == ["159985.SZ"]
        assert sources.loc[0, "source"] == module.SOURCE_SINA_CNFIN_CROSS_VALIDATED
        assert sources.loc[0, "adjustment"] == module.ADJUSTMENT_CROSS_VALIDATED_RAW
        assert sources.loc[0, "source_detail"] == module.SOURCE_DETAIL_SINA_CNFIN_CROSS_VALIDATED


def test_public_loader_never_tries_raw_pair_for_other_codes(module, monkeypatch):
    calls = []
    monkeypatch.setattr(
        module,
        "_load_akshare_eastmoney_qfq_one_close",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("akshare")),
    )
    monkeypatch.setattr(
        module,
        "_load_tencent_qfq_one_close",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("tencent")),
    )
    monkeypatch.setattr(
        module,
        "_load_eastmoney_one_close",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("eastmoney")),
    )
    monkeypatch.setattr(
        module,
        "_load_cross_validated_raw_one_close",
        lambda *args, **kwargs: calls.append("cross"),
    )

    with pytest.raises(RuntimeError, match="All historical data sources failed"):
        module._load_public_close_with_per_code_fallback(
            ["513030.SH"], pd.Timestamp("2026-08-07")
        )

    assert calls == []
