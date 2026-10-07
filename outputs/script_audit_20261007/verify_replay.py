"""Same-input official-chain replay for script repairs; no provider refresh."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
L1 = ROOT / "outputs/recert_l1_20260926"
PRE_EDIT = ROOT / ".codex_backups/20261007_163920/poe_subd_six_etf_v1_3_bot.py"
CURRENT = ROOT / "poe_subd_six_etf_v1_3_bot.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    manifest = json.loads((L1 / "capture_manifest.json").read_text(encoding="utf-8"))
    inputs = {}
    for key in ("raw", "aligned", "flags"):
        path = L1 / Path(manifest[key]["path"]).name
        assert sha(path) == manifest[key]["sha256"], f"changed frozen input: {key}"
        inputs[key] = {"path": str(path), "sha256": sha(path)}
    prices = pd.read_csv(inputs["raw"]["path"], parse_dates=["date"]).set_index("date")
    sources = pd.read_csv(L1 / "sources_formal_loader.csv")
    snapshot_flags = pd.read_csv(inputs["flags"]["path"], parse_dates=["date"]).set_index("date")
    calendar_source = L1 / "calendar_cache_for_audit.csv"
    calendar_copy = HERE / "calendar_cache_for_replay.csv"
    daily_runs = {}
    bots = {}
    params = ("LOOKBACK", "SCORE_MIN", "SCORE_MAX", "R2_THRESHOLD", "SWITCH_BUFFER",
              "INITIAL_ENTRY_FRACTION", "DEFAULT_MAX_LEV", "ONE_WAY_COST", "TARGET_VOL",
              "TARGET_VOL_ENABLED", "OVERHEAT_ENABLED", "STAGED_ENTRY_ENABLED")
    for label, path in (("before", PRE_EDIT), ("after", CURRENT)):
        bot = load(path, f"script_audit_replay_{label}")
        bots[label] = bot
        # Only the data download is replaced by the previously verified raw qfq
        # snapshot. Alignment, flags, engine, bar metadata and reporting are official.
        bot.load_close = lambda config: (prices.copy(), sources.copy())
        calendar_copy.write_bytes(calendar_source.read_bytes())
        bot.TRADING_CALENDAR_CACHE_PATH = calendar_copy
        daily, source = bot._build_v13_daily(
            end_date=pd.Timestamp("2026-09-24"), data_state="confirmed",
            now=datetime(2026, 9, 26, 12, 0, tzinfo=bot.CN_TZ),
        )
        assert len(daily) == 3594 and daily.date.max() == pd.Timestamp("2026-09-24")
        actual_flags = daily[[f"price_ffill_{code}" for code in bot.ASSETS]].to_numpy(bool)
        np.testing.assert_array_equal(actual_flags, snapshot_flags[list(bot.ASSETS)].to_numpy(bool))
        daily.to_csv(HERE / f"daily_{label}.csv.gz", index=False)
        daily_runs[label] = daily
    assert {name: getattr(bots["before"], name) for name in params} == {
        name: getattr(bots["after"], name) for name in params
    }, "formal parameters changed"
    before, after = daily_runs["before"], daily_runs["after"]
    assert before.date.equals(after.date)
    differences = {}
    for column in ("nav", "return", "turnover", "cost", "buy_delta", "sell_delta",
                   "fraction_before", "holding_fraction", "exposure_effective"):
        differences[column] = float(np.max(np.abs(before[column] - after[column])))
        np.testing.assert_array_equal(before[column], after[column])
    for column in ("position", "position_before", "trade_blocked_by_stale_price"):
        assert before[column].equals(after[column]), column
    bot = bots["after"]
    rows = []
    for window, start, end in bot._default_performance_ranges_for_daily(
        after, after.date.max(), after.date.min()
    )[:5]:
        old = bots["before"].calc_performance(before, start, end)
        new = bot.calc_performance(after, start, end)
        assert old == new, window
        rows.append({"window": window, **new, "annual_delta_pp": 0.0, "maxdd_delta_pp": 0.0})
    pd.DataFrame(rows).to_csv(HERE / "same_input_window_metrics.csv", index=False)
    result = {
        "status": "PASS", "basis": "frozen verified qfq input; not fresh live data",
        "official_chain": "_build_v13_daily -> load_close(frozen raw) -> align -> fill flags -> build_curves -> metadata -> normalize -> official metrics",
        "data": inputs, "rows": len(after), "start": str(after.date.min().date()),
        "end": str(after.date.max().date()), "source": source,
        "pre_edit_code_sha256": sha(PRE_EDIT), "current_code_sha256": sha(CURRENT),
        "parameters": {name: getattr(bot, name) for name in params},
        "max_abs_differences": differences, "fee_identity_max_abs": float(np.max(np.abs(
            after.cost - after.turnover * bot.ONE_WAY_COST))),
        "assumptions": "China-listed ETF qfq; same-close paper execution; old position owns close-close return; one-way cost 0.001; cash return 0; no broker fills/capacity validation",
    }
    (HERE / "same_input_replay.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
