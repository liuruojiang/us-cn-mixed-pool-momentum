"""Independent L6 variable-parameter signal and self-financing ledger audit.

The calculation reads only the frozen L1 price panel/flags. No production
scoring, execution, or performance helper is imported. A JSON parameter matrix
can be supplied after its values are frozen by the L6 executor.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
L1 = HERE.parent / "recert_l1_20260926"
L2 = HERE.parent / "recert_l2_20260926"
L4 = HERE.parent / "recert_l4_20260926"
ASSETS = ("159915.SZ", "159941.SZ", "513030.SH", "513520.SH", "159985.SZ", "518880.SH")
FEE = 0.001
WINDOWS = (("Full", None), ("10Y", 2520), ("5Y", 1260), ("3Y", 756),
           ("1Y", 252), ("six_etf_all_scoreable", "2020-01-09"))
FORMAL = {"id": "formal", "group": "parity", "lookback": 25,
          "weight_power": 1.0, "score_min": 0.5, "score_max": 5.5,
          "r2_threshold": 0.25, "switch_buffer": 1.0, "core_enabled": True}
PARITY = ({**FORMAL, "id": "parity_formal"},
          {**FORMAL, "id": "parity_floor_off", "score_min": None},
          {**FORMAL, "id": "parity_ceiling_off", "score_max": None},
          {**FORMAL, "id": "parity_r2_off", "r2_threshold": None})


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def independent_signals(price: np.ndarray, lookback: int, power: float) -> tuple[np.ndarray, np.ndarray]:
    if lookback < 3 or not np.isfinite(power):
        raise ValueError((lookback, power))
    rows, assets = price.shape
    score = np.full((rows, assets), np.nan)
    fit = np.full((rows, assets), np.nan)
    # Batch the windows across time and assets; the regression uses weighted
    # moments rather than the production polyfit implementation.
    blocks = np.lib.stride_tricks.sliding_window_view(price, lookback, axis=0)
    good = np.isfinite(blocks).all(axis=-1) & (blocks > 0).all(axis=-1)
    safe = np.where(good[..., None], blocks, 1.0)
    y = np.log(safe)
    valid = good & (np.ptp(y, axis=-1) > 1e-12)
    y -= y[..., :1]
    x = np.arange(lookback, dtype=float)
    weight = (x + 1.0) ** power
    wx = float(np.dot(weight, x) / weight.sum())
    dx = x - wx
    denom = float(np.dot(weight, dx * dx))
    wy = np.einsum("tak,k->ta", y, weight) / weight.sum()
    dy = y - wy[..., None]
    slope = np.einsum("tak,k->ta", dy, weight * dx) / denom
    total = np.einsum("tak,k->ta", dy * dy, weight)
    residual = dy - slope[..., None] * dx
    error = np.einsum("tak,k->ta", residual * residual, weight)
    valid &= np.isfinite(total) & (total > 0)
    exponent = slope * 252.0
    score_valid = valid & np.isfinite(exponent) & (exponent <= math.log(np.finfo(float).max))
    with np.errstate(over="ignore", invalid="ignore"):
        raw = np.expm1(exponent)
        r2 = np.maximum(0.0, 1.0 - error / total)
    score[lookback - 1:] = np.where(score_valid, raw, np.nan)
    fit[lookback - 1:] = np.where(valid, r2, np.nan)
    return score, fit


def independent_replay(index: pd.DatetimeIndex, price: np.ndarray, stale: np.ndarray,
                       score: np.ndarray, fit: np.ndarray, arm: dict) -> pd.DataFrame:
    eligible = np.isfinite(score)
    if arm.get("score_min") is not None:
        eligible &= score > float(arm["score_min"])
    if arm.get("score_max") is not None:
        eligible &= score < float(arm["score_max"])
    if arm.get("r2_threshold") is not None:
        eligible &= np.isfinite(fit) & (fit >= float(arm["r2_threshold"]))
    if not arm.get("core_enabled", True):
        eligible[:] = False
    cash = 1.0
    shares = 0.0
    asset = -1
    previous_nav = 1.0
    max_bridge_error = 0.0
    records = []
    for t, day in enumerate(index):
        before = asset
        marked = cash + (shares * price[t, asset] if asset >= 0 else 0.0)
        if not (np.isfinite(marked) and marked > 0):
            raise AssertionError((arm["id"], day, "invalid pre-trade wealth"))
        candidate = np.flatnonzero(eligible[t])
        wanted = int(candidate[np.argmax(score[t, candidate])]) if len(candidate) else -1
        buffer_blocked = False
        buffer = float(arm.get("switch_buffer", 1.0))
        if (before >= 0 and wanted >= 0 and before != wanted
                and eligible[t, before] and buffer > 1.0
                and score[t, wanted] <= score[t, before] * buffer):
            wanted = before
            buffer_blocked = True
        blocked = wanted != before and any(stale[t, j] for j in (before, wanted) if j >= 0)
        target = before if blocked else wanted
        turnover = int(before >= 0 and target != before) + int(target >= 0 and target != before)
        fee_cash = marked * FEE * turnover
        if target != before:
            if before >= 0:
                cash += shares * price[t, before]
                shares = 0.0
                cash -= marked * FEE
            if target >= 0:
                buy_fee = marked * FEE
                invest = cash - buy_fee
                if invest < -1e-12:
                    raise AssertionError((arm["id"], day, "negative buying power"))
                shares = invest / price[t, target]
                cash -= invest + buy_fee
            asset = target
        if cash < -1e-11 or shares < -1e-11:
            raise AssertionError((arm["id"], day, "borrow or short", cash, shares))
        nav = cash + (shares * price[t, asset] if asset >= 0 else 0.0)
        bridge_error = abs(nav - (marked - fee_cash))
        max_bridge_error = max(max_bridge_error, bridge_error)
        if bridge_error > 1e-10 * max(1.0, nav):
            raise AssertionError((arm["id"], day, "accounting bridge", bridge_error))
        records.append({
            "date": day, "position_before": ASSETS[before] if before >= 0 else "CASH",
            "desired": ASSETS[wanted] if wanted >= 0 else "CASH",
            "position": ASSETS[asset] if asset >= 0 else "CASH",
            "eligible_count": len(candidate), "buffer_blocked": buffer_blocked,
            "stale_blocked": bool(blocked),
            "cash": cash, "shares": shares, "marked_before_trade": marked,
            "turnover": turnover, "cost": turnover * FEE, "fee_cash": fee_cash,
            "gross_return": marked / previous_nav - 1.0,
            "return": nav / previous_nav - 1.0, "nav": nav,
        })
        previous_nav = nav
    daily = pd.DataFrame(records).set_index("date")
    daily.attrs["max_accounting_bridge_error"] = max_bridge_error
    return daily


def window_metrics(daily: pd.DataFrame, arm: dict) -> list[dict]:
    result = []
    for label, width in WINDOWS:
        sub = daily if width is None else (daily.loc[width:] if isinstance(width, str) else daily.tail(width))
        if len(sub) < 2:
            result.append({"arm": arm["id"], "window": label, "reason": "fewer than two rows"})
            continue
        relative = sub.nav.to_numpy(dtype=float) / float(sub.nav.iloc[0])
        peaks = np.maximum.accumulate(relative)
        drawdown = relative / peaks - 1.0
        trough = int(np.argmin(drawdown))
        peak = int(np.argmax(relative[:trough + 1]))
        result.append({
            "arm": arm["id"], "group": arm.get("group", ""), "window": label,
            "start": str(sub.index[0].date()), "end": str(sub.index[-1].date()),
            "rows": len(sub), "annual_n_minus_1": float(relative[-1] ** (252.0 / (len(sub) - 1)) - 1.0),
            "maxdd": float(drawdown.min()), "peak_date": str(sub.index[peak].date()),
            "trough_date": str(sub.index[trough].date()), "end_nav": float(sub.nav.iloc[-1]),
            "trade_days": int((sub.turnover > 0).sum()), "turnover_sum": float(sub.turnover.sum()),
            "fee_cash_initial_capital_units": float(sub.fee_cash.sum()),
            "cash_days": int(sub.position.eq("CASH").sum()),
        })
    return result


def parity(daily: pd.DataFrame, expected_path: Path) -> dict:
    archived = pd.read_csv(expected_path, parse_dates=["date"]).set_index("date")
    if not daily.index.equals(archived.index):
        raise AssertionError((expected_path, "calendar mismatch"))
    result = {"reference": str(expected_path), "rows": len(daily)}
    for key in ("position_before", "position", "turnover", "cost", "gross_return", "return", "nav"):
        if key not in archived:
            continue
        if key.startswith("position"):
            different = daily[key].ne(archived[key])
            result[key + "_mismatch"] = int(different.sum())
            result[key + "_first_mismatch"] = str(different[different].index[0].date()) if different.any() else None
        else:
            delta = (daily[key] - archived[key]).abs()
            result[key + "_max_abs"] = float(delta.max())
            result[key + "_first_gt_1e-10"] = str(delta[delta > 1e-10].index[0].date()) if (delta > 1e-10).any() else None
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, help="frozen CSV matrix with group,candidate,value,role,provenance")
    args = parser.parse_args()
    price_file = L1 / "prices_aligned_qfq_through_20260924.csv.gz"
    stale_file = L1 / "price_ffill_flags_through_20260924.csv.gz"
    panel = pd.read_csv(price_file, parse_dates=["date"]).set_index("date")
    flags = pd.read_csv(stale_file, parse_dates=["date"]).set_index("date")
    if len(panel) != 3594 or str(panel.index[-1].date()) != "2026-09-24" or not panel.index.equals(flags.index):
        raise AssertionError("L1 snapshot identity changed")
    px = panel.loc[:, ASSETS].to_numpy(dtype=float)
    stale = flags.loc[:, ASSETS].to_numpy(dtype=bool)
    arms = list(PARITY)
    if args.matrix:
        frozen = pd.read_csv(args.matrix, dtype=str, keep_default_na=False)
        required = {"group", "candidate", "value", "role", "provenance"}
        if not required.issubset(frozen.columns):
            raise ValueError("incomplete frozen matrix")
        for row in frozen.to_dict("records"):
            arm = {**FORMAL, "id": row["candidate"], "group": row["group"],
                   "role": row["role"], "provenance": row["provenance"]}
            group = row["group"]
            if group not in {"lookback", "weight_power", "score_floor", "score_ceiling", "r2_threshold", "switch_buffer"}:
                raise ValueError(group)
            field = {"score_floor": "score_min", "score_ceiling": "score_max"}.get(group, group)
            arm[field] = None if row["value"] == "off" else (int(row["value"]) if group == "lookback" else float(row["value"]))
            arms.append(arm)
        # Disabling the whole signal core yields cash at zero yield. It is a
        # resource/account anchor, not a competing tuned lookback or Sharpe.
        arms.append({**FORMAL, "id": "core_off_cash", "group": "lookback",
                     "role": "core_off_diagnostic", "core_enabled": False})
    ids = [item["id"] for item in arms]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate arm ID")
    cache = {}
    report = {"inputs": {"prices": str(price_file), "prices_sha256": sha256(price_file),
                         "flags": str(stale_file), "flags_sha256": sha256(stale_file)},
              "matrix": str(args.matrix) if args.matrix else None,
              "matrix_sha256": sha256(args.matrix) if args.matrix else None,
              "arms": {}, "parity": {}}
    metric_rows = []
    expected = {"parity_formal": L2 / "formal_daily_20260924.csv.gz",
                "parity_floor_off": L4 / "daily_score_floor_off_20260924.csv.gz",
                "parity_ceiling_off": L4 / "daily_score_ceiling_off_20260924.csv.gz",
                "parity_r2_off": L4 / "daily_r2_off_20260924.csv.gz"}
    for arm in arms:
        pair = (int(arm["lookback"]), float(arm["weight_power"]))
        if pair not in cache:
            cache[pair] = independent_signals(px, *pair)
        score, fit = cache[pair]
        daily = independent_replay(panel.index, px, stale, score, fit, arm)
        path = HERE / f"agent_b_{arm['id']}_daily.csv.gz"
        daily.to_csv(path, compression="gzip", float_format="%.17g")
        metric_rows.extend(window_metrics(daily, arm))
        report["arms"][arm["id"]] = {"parameters": arm, "daily": str(path), "daily_sha256": sha256(path),
            "end_nav": float(daily.nav.iloc[-1]), "trade_days": int(daily.turnover.gt(0).sum()),
            "turnover_sum": float(daily.turnover.sum()), "fee_cash_sum": float(daily.fee_cash.sum()),
            "cash_days": int(daily.position.eq("CASH").sum()),
            "buffer_block_days": int(daily.buffer_blocked.sum()),
            "stale_block_days": int(daily.stale_blocked.sum()),
            "min_cash": float(daily.cash.min()), "min_shares": float(daily.shares.min()),
            "max_accounting_bridge_error": daily.attrs["max_accounting_bridge_error"]}
        if arm["id"] in expected:
            report["parity"][arm["id"]] = parity(daily, expected[arm["id"]])
    pd.DataFrame(metric_rows).to_csv(HERE / "agent_b_metrics.csv", index=False, float_format="%.17g")
    (HERE / "agent_b_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"arms": len(arms), "parity": report["parity"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
