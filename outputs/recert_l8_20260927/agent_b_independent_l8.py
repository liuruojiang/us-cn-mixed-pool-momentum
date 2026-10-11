"""L8 independent 27-arm single-account replay from L1 prices only.

Uses the previously independently written L6 moment estimator and cash/share
ledger, not any formal strategy score, trading or metric function.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
L1 = ROOT / "outputs/recert_l1_20260926"
L2 = ROOT / "outputs/recert_l2_20260926"
MATRIX = HERE / "agent_a_matrix.csv"
ASSETS = ("159915.SZ", "159941.SZ", "513030.SH", "513520.SH", "159985.SZ", "518880.SH")
WINDOWS = (("Full", None), ("10Y", 2520), ("5Y", 1260), ("3Y", 756), ("1Y", 252),
           ("six_etf_all_scoreable", "2020-01-09"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(condition, message):
    if not bool(condition):
        raise AssertionError(message)


def load_independent_engine():
    path = ROOT / "outputs/recert_l6_20260926/agent_b_independent_matrix.py"
    spec = importlib.util.spec_from_file_location("l8_own_independent_ledger", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, sha(path)


def number_or_off(value: str):
    return None if value == "off" else float(value)


def read_arm(row):
    return {"id": row["arm"], "group": row["role"], "role": row["role"],
            "lookback": int(row["lookback"]), "weight_power": float(row["weight_power"]),
            "score_min": number_or_off(row["score_floor"]),
            "score_max": number_or_off(row["score_ceiling"]),
            "r2_threshold": number_or_off(row["r2_threshold"]),
            "switch_buffer": float(row["switch_buffer"]), "core_enabled": True}


def metrics(daily, arm):
    rows = []
    for window, width in WINDOWS:
        sub = daily if width is None else (daily.loc[width:] if isinstance(width, str) else daily.tail(width))
        nav = sub.nav.to_numpy(float)
        norm = nav / nav[0]
        dd = norm / np.maximum.accumulate(norm) - 1
        trough = int(np.argmin(dd))
        peak = int(np.argmax(norm[:trough + 1]))
        trade = sub.turnover.to_numpy(int)
        rows.append({"arm": arm["id"], "window": window, "start": str(sub.index[0].date()),
                     "end": str(sub.index[-1].date()), "rows": len(sub),
                     "total_return": float(norm[-1] - 1),
                     "annual_n_minus_1": float(norm[-1] ** (252 / (len(sub) - 1)) - 1),
                     "maxdd": float(dd.min()), "peak_date": str(sub.index[peak].date()),
                     "trough_date": str(sub.index[trough].date()), "end_nav": float(nav[-1]),
                     "trade_days": int((trade > 0).sum()),
                     "double_switch_days": int((trade == 2).sum()),
                     "turnover_sum": int(trade.sum()), "cost_fraction_sum": float(sub.cost.sum()),
                     "fee_cash_sum": float(sub.fee_cash.sum()),
                     "cash_end_days": int(sub.position.eq("CASH").sum()),
                     "average_carried_exposure": float(sub.position_before.ne("CASH").mean()),
                     "max_exposure": 1.0 if sub.position_before.ne("CASH").any() else 0.0,
                     "buffer_block_days": int(sub.buffer_blocked.sum()),
                     "stale_block_days": int(sub.stale_blocked.sum())})
    return rows


def main():
    check(sha(MATRIX) == "2fa744ed1b44825ca47bb5e4e0124fbe024c17cd8823b109319b80608830ed42",
          "matrix differs from prefreeze")
    manifest = json.loads((L1 / "capture_manifest.json").read_text(encoding="utf-8"))
    for key in ("aligned", "flags"):
        check(sha(Path(manifest[key]["path"])) == manifest[key]["sha256"], f"L1 {key} changed")
    matrix = pd.read_csv(MATRIX, dtype=str, keep_default_na=False)
    check(len(matrix) == 27 and matrix.arm.is_unique and matrix.arm.iloc[0] == "formal_111", "matrix identity")
    price = pd.read_csv(manifest["aligned"]["path"], parse_dates=["date"]).set_index("date")
    flags = pd.read_csv(manifest["flags"]["path"], parse_dates=["date"]).set_index("date")
    check(price.index.equals(flags.index) and len(price) == 3594 and
          str(price.index[-1].date()) == "2026-09-24", "panel identity")
    px = price.loc[:, ASSETS].to_numpy(float)
    stale = flags.loc[:, ASSETS].to_numpy(bool)
    engine, engine_hash = load_independent_engine()
    score_cache = {}
    curves = {}
    arm_info = {}
    metric_rows = []
    for row in matrix.to_dict("records"):
        arm = read_arm(row)
        pair = (arm["lookback"], arm["weight_power"])
        if pair not in score_cache:
            score_cache[pair] = engine.independent_signals(px, *pair)
        score, fit = score_cache[pair]
        daily = engine.independent_replay(price.index, px, stale, score, fit, arm)
        # The account has one cash/ETF slot and all turnover is discrete 0/1/2.
        check((daily.cash >= -1e-10).all() and (daily.shares >= -1e-10).all(), f"{arm['id']} borrow/short")
        check(set(daily.turnover) <= {0, 1, 2}, f"{arm['id']} turnover domain")
        check(np.max(np.abs(daily.cost.to_numpy(float) - .001 * daily.turnover.to_numpy(float))) < 1e-12,
              f"{arm['id']} fee ratio")
        check(not ((daily.stale_blocked) & (daily.turnover > 0)).any(), f"{arm['id']} stale trade")
        check(np.max(np.abs(daily.nav.to_numpy(float) - (daily.marked_before_trade - daily.fee_cash).to_numpy(float))) < 1e-10,
              f"{arm['id']} ledger bridge")
        out = HERE / f"agent_b_{arm['id']}_daily.csv.gz"
        daily.to_csv(out, compression="gzip", float_format="%.17g")
        curves[arm["id"]] = daily
        metric_rows.extend(metrics(daily, arm))
        arm_info[arm["id"]] = {"daily": str(out), "sha256": sha(out), "parameters": arm,
                               "end_nav": float(daily.nav.iloc[-1]),
                               "trade_days": int(daily.turnover.gt(0).sum()),
                               "double_switch_days": int(daily.turnover.eq(2).sum()),
                               "turnover_sum": int(daily.turnover.sum()),
                               "fee_cash_sum": float(daily.fee_cash.sum()),
                               "cash_days": int(daily.position.eq("CASH").sum()),
                               "buffer_block_days": int(daily.buffer_blocked.sum()),
                               "stale_block_days": int(daily.stale_blocked.sum()),
                               "min_cash": float(daily.cash.min()),
                               "min_shares": float(daily.shares.min()),
                               "max_bridge_error": float(daily.attrs["max_accounting_bridge_error"])}
    formal = curves["formal_111"]
    archived = pd.read_csv(L2 / "formal_daily_20260924.csv.gz", parse_dates=["date"]).set_index("date")
    check(formal.index.equals(archived.index), "formal calendar")
    for col in ("position_before", "position"):
        check(formal[col].equals(archived[col]), f"formal L2 {col}")
    l2_error = {}
    for col in ("turnover", "cost", "return", "nav"):
        diff = float(np.max(np.abs(formal[col].to_numpy(float) - archived[col].to_numpy(float))))
        l2_error[col] = diff
        check(diff < (2e-10 if col == "nav" else 1e-12), f"formal L2 {col} {diff}")
    activation = []
    for arm, daily in curves.items():
        if arm == "formal_111":
            continue
        changed = daily.position.ne(formal.position)
        trade_changed = daily.turnover.ne(formal.turnover)
        target_changed = daily.desired.ne(formal.desired)
        activation.append({"arm": arm, "position_diff_days": int(changed.sum()),
                           "first_position_diff": str(changed[changed].index[0].date()) if changed.any() else "",
                           "target_diff_days": int(target_changed.sum()),
                           "first_target_diff": str(target_changed[target_changed].index[0].date()) if target_changed.any() else "",
                           "trade_diff_days": int(trade_changed.sum()),
                           "first_trade_diff": str(trade_changed[trade_changed].index[0].date()) if trade_changed.any() else ""})
    activation_path = HERE / "agent_b_activation.csv"
    pd.DataFrame(activation).to_csv(activation_path, index=False)
    metric_path = HERE / "agent_b_metrics.csv"
    pd.DataFrame(metric_rows).to_csv(metric_path, index=False, float_format="%.17g")

    # Concrete fee and signal-clock counterexamples, evaluated on the formal account.
    switch = formal[formal.turnover.eq(2)].iloc[0]
    first_buy = formal[(formal.position_before.eq("CASH")) & (formal.position.ne("CASH"))].iloc[0]
    buy_day = first_buy.name
    asset = first_buy.position
    t = price.index.get_loc(buy_day)
    new_asset_today_return = px[t, ASSETS.index(asset)] / px[t - 1, ASSETS.index(asset)] - 1
    bad_new_asset_net_return = (1 + new_asset_today_return) * (1 - first_buy.cost) - 1
    counterexample = {"double_switch": {"date": str(switch.name.date()),
                                        "turnover": int(switch.turnover), "cost": float(switch.cost),
                                        "fee_cash_required": float(switch.fee_cash),
                                        "omitted_sell_leg_cash_error": float(switch.marked_before_trade * .001)},
                      "first_buy": {"date": str(buy_day.date()), "asset": asset,
                                    "correct_gross_return": float(first_buy.gross_return),
                                    "correct_net_return": float(first_buy["return"]),
                                    "wrong_new_asset_today_return": float(new_asset_today_return),
                                    "wrong_net_if_counted_early": float(bad_new_asset_net_return)}}

    result = {"status": "independent_computed_pending_main_crosscheck", "matrix_sha256": sha(MATRIX),
              "prices_sha256": manifest["aligned"]["sha256"], "flags_sha256": manifest["flags"]["sha256"],
              "independent_engine_sha256": engine_hash, "arms": arm_info,
              "formal_l2_max_abs_diff": l2_error, "counterexample": counterexample,
              "metrics_sha256": sha(metric_path), "activation_sha256": sha(activation_path)}
    out = HERE / "agent_b_independent_audit.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"arms": len(arm_info), "metrics_rows": len(metric_rows), "formal_l2": l2_error,
                      "max_bridge_error": max(v["max_bridge_error"] for v in arm_info.values()),
                      "min_cash": min(v["min_cash"] for v in arm_info.values()),
                      "min_shares": min(v["min_shares"] for v in arm_info.values()),
                      "stale_block_arms": {k: v["stale_block_days"] for k, v in arm_info.items() if v["stale_block_days"]},
                      "counterexample": counterexample}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
