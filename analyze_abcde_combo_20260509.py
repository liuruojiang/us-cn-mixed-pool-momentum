from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "docs" / "abcde_combo_20260509"
MICROCAP_ROOT = ROOT.parent / "微盘股对冲策略"
MICROCAP_V18 = MICROCAP_ROOT / "outputs" / "microcap_top100_mom11_targetvol30_max2_v1_8_costed_nav.csv"
SUBD_DAILY = ROOT / "outputs" / "subd_six_etf_v1_1_20260509_daily.csv"
SCRIPT = ROOT / "mnt_bot V 7.6 plus.py"

PROPOSAL_WEIGHTS = {
    "Sub-A": 0.10,
    "Sub-B": 0.15,
    "Sub-C": 0.10,
    "Sub-D": 0.20,
    "Microcap": 0.40,
}
BASELINE_WEIGHTS = {
    "Sub-A": 0.10,
    "Sub-A-DK": 0.15,
    "Sub-B": 0.60,
    "Microcap": 0.15,
}
WINDOWS = {
    "full_common": None,
    "10Y": pd.DateOffset(years=10),
    "5Y": pd.DateOffset(years=5),
    "3Y": pd.DateOffset(years=3),
    "1Y": pd.DateOffset(years=1),
}


class Msg:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, text: str) -> None:
        self.lines.append(str(text))


def load_module():
    spec = importlib.util.spec_from_file_location("mnt_v76_abcde_combo", SCRIPT)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    module.poe = SimpleNamespace(
        update_settings=lambda *_args, **_kwargs: None,
        BotError=RuntimeError,
        default_chat=None,
        query=SimpleNamespace(text="", attachments=[]),
        call=lambda *_args, **_kwargs: "",
        start_message=lambda: None,
    )
    spec.loader.exec_module(module)
    return module


def load_abcs_from_v76(mod) -> tuple[dict[str, pd.Series], dict[str, object]]:
    msg = Msg()
    engine = mod.CombinedStrategyV76()
    cn_close, cn_dk_close, us_rot_close, us_prod_daily = engine._fetch_data(
        msg,
        include_cn_live_snapshot=False,
        include_us_live_snapshot=False,
    )
    results = engine._run_strategies(cn_close, cn_dk_close, us_rot_close, us_prod_daily)
    cn_result, cn_dk_result, us_rot_result, _prod_monthly, prod_sig_a, prod_sig_b, *_ = results
    if prod_sig_a is None:
        prod_monthly = us_prod_daily.resample("M").last()
        last_daily = us_prod_daily.index[-1]
        last_monthly_period = prod_monthly.index[-1].to_period("M")
        today_period = pd.Timestamp(mod.beijing_now().date()).to_period("M")
        if last_daily.to_period("M") == last_monthly_period == today_period:
            prod_monthly = prod_monthly.iloc[:-1]
        prod_sig_a = mod.make_abs_mom_signals(prod_monthly, mod.PROD_ABS_MOM_LB)
        prod_sig_b = mod.make_sma_signals(prod_monthly, mod.PROD_SMA_WINDOW, mod.PROD_SMA_BAND)
        if not mod.PROD_USE_TIMING:
            prod_sig_a = pd.DataFrame(1.0, index=prod_sig_a.index, columns=prod_sig_a.columns)
            prod_sig_b = prod_sig_a.copy()
    subc_ret = mod._get_subc_daily_ret(us_prod_daily, prod_sig_a, prod_sig_b)
    returns = {
        "Sub-A": cn_result["return"].dropna().astype(float),
        "Sub-A-DK": cn_dk_result["return"].dropna().astype(float),
        "Sub-B": us_rot_result["return"].dropna().astype(float),
        "Sub-C": subc_ret.dropna().astype(float),
    }
    audit = {
        "entrypoint": "mnt_bot V 7.6 plus.py: CombinedStrategyV76._fetch_data + _run_strategies + _get_subc_daily_ret",
        "uses_us_open": bool(getattr(engine, "_us_open", None)),
        "us_open_ticker_count": len(getattr(engine, "_us_open", {}) or {}),
        "subb_execution": "T close signal -> T+1 open execution via V7.6 official path",
        "fetch_log_tail": msg.lines[-25:],
        "input_ranges": {
            "cn_close": range_info_df(cn_close),
            "cn_dk_close": range_info_df(cn_dk_close),
            "us_rot_close": range_info_df(us_rot_close),
            "us_prod_daily": range_info_df(us_prod_daily),
        },
    }
    return returns, audit


def load_subd() -> pd.Series:
    df = pd.read_csv(SUBD_DAILY, parse_dates=["date"])
    df = df[df["version"].astype(str).eq("1.1")].copy()
    df = df.sort_values("date").set_index("date")
    return df["return"].dropna().astype(float)


def load_microcap_v18() -> pd.Series:
    df = pd.read_csv(MICROCAP_V18, parse_dates=["date"]).sort_values("date").set_index("date")
    return df["return_net"].dropna().astype(float)


def range_info(series: pd.Series) -> dict[str, object]:
    s = series.dropna()
    return {
        "start": s.index.min().date().isoformat(),
        "end": s.index.max().date().isoformat(),
        "rows": int(len(s)),
        "duplicate_dates": int(s.index.duplicated().sum()),
        "return_column": s.name,
    }


def range_info_df(df: pd.DataFrame) -> dict[str, object]:
    return {
        "start": df.index.min().date().isoformat(),
        "end": df.index.max().date().isoformat(),
        "rows": int(len(df)),
        "duplicate_dates": int(df.index.duplicated().sum()),
        "columns": list(map(str, df.columns)),
    }


def build_fixed_weight_return(
    daily: dict[str, pd.Series],
    weights: dict[str, float],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.Series:
    idx = pd.DatetimeIndex(sorted(set().union(*(set(s.loc[start:end].index) for s in daily.values()))))
    frame = pd.DataFrame({name: daily[name].reindex(idx) for name in weights if name in daily})
    frame = frame.loc[(frame.index >= start) & (frame.index <= end)].fillna(0.0)
    ret = sum(frame[name] * weights.get(name, 0.0) for name in frame.columns)
    return ret.rename("return")


def metrics(ret: pd.Series) -> dict[str, float]:
    ret = ret.dropna().astype(float)
    nav = (1.0 + ret).cumprod()
    years = len(ret) / 252.0
    cagr = nav.iloc[-1] ** (1.0 / years) - 1.0 if years > 0 else math.nan
    vol = ret.std(ddof=0) * math.sqrt(252.0)
    sharpe = ret.mean() / ret.std(ddof=0) * math.sqrt(252.0) if ret.std(ddof=0) > 0 else math.nan
    maxdd = (nav / nav.cummax() - 1.0).min()
    return {
        "start": ret.index.min().date().isoformat(),
        "end": ret.index.max().date().isoformat(),
        "days": int(len(ret)),
        "total_return": float(nav.iloc[-1] - 1.0),
        "cagr": float(cagr),
        "vol": float(vol),
        "sharpe": float(sharpe),
        "maxdd": float(maxdd),
        "calmar": float(cagr / abs(maxdd)) if maxdd < 0 else math.nan,
    }


def window_part(ret: pd.Series, offset: pd.DateOffset | None) -> pd.Series:
    if offset is None:
        return ret
    start = ret.index.max() - offset
    return ret.loc[ret.index >= start]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mod = load_module()
    daily, audit = load_abcs_from_v76(mod)
    daily["Sub-D"] = load_subd()
    daily["Microcap"] = load_microcap_v18()

    common_start = max(s.dropna().index.min() for s in daily.values())
    common_end = min(s.dropna().index.max() for s in daily.values())
    proposal_sum = sum(PROPOSAL_WEIGHTS.values())
    proposal_normalized = {k: v / proposal_sum for k, v in PROPOSAL_WEIGHTS.items()}
    scenarios = {
        "proposal_A10_B15_C10_D20_E40_cash5": PROPOSAL_WEIGHTS,
        "proposal_A10_B15_C10_D20_E40_normalized": proposal_normalized,
        "baseline_A10_ADK15_B60_E15": BASELINE_WEIGHTS,
    }

    scenario_returns = {
        name: build_fixed_weight_return(daily, weights, common_start, common_end)
        for name, weights in scenarios.items()
    }
    rows = []
    for scenario, ret in scenario_returns.items():
        for window, offset in WINDOWS.items():
            part = window_part(ret, offset)
            rows.append({"scenario": scenario, "window": window, **metrics(part)})
    summary = pd.DataFrame(rows)
    summary.to_csv(OUT_DIR / "abcde_combo_summary.csv", index=False, encoding="utf-8-sig")

    daily_out = pd.DataFrame({f"{name}_return": ret for name, ret in scenario_returns.items()})
    for name, ret in scenario_returns.items():
        daily_out[f"{name}_nav"] = (1.0 + ret).cumprod()
    for name, ret in daily.items():
        daily_out[f"sleeve_{name}_return"] = ret.reindex(daily_out.index)
    daily_out.to_csv(OUT_DIR / "abcde_combo_daily.csv", encoding="utf-8-sig")

    sleeve_rows = [{"sleeve": name, **range_info(ret), **metrics(ret.loc[common_start:common_end].fillna(0.0))} for name, ret in daily.items()]
    sleeves = pd.DataFrame(sleeve_rows)
    sleeves.to_csv(OUT_DIR / "abcde_combo_sleeves.csv", index=False, encoding="utf-8-sig")

    audit.update(
        {
            "classification": "formal V7.6 A/B/C path plus Sub-D V1.1 and Microcap v1.8 costed NAV; proposal sum 95% treated as 5% cash",
            "common_start": common_start.date().isoformat(),
            "common_end": common_end.date().isoformat(),
            "weights": scenarios,
            "sleeves": {name: range_info(ret) for name, ret in daily.items()},
            "source_files": {
                "script": str(SCRIPT),
                "subd_daily": str(SUBD_DAILY),
                "microcap_v18": str(MICROCAP_V18),
            },
        }
    )
    (OUT_DIR / "abcde_combo_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(summary.to_string(index=False))
    print(f"WROTE {OUT_DIR / 'abcde_combo_summary.csv'}")
    print(f"WROTE {OUT_DIR / 'abcde_combo_daily.csv'}")
    print(f"WROTE {OUT_DIR / 'abcde_combo_audit.json'}")


if __name__ == "__main__":
    main()
