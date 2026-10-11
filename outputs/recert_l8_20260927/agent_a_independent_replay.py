"""Independent L8 weighted-moment signals and single-account ETF share ledger.

Reads the frozen L1 panel and preregistered L8 matrix. Never imports the Poe bot
or its score, ledger, or metric helpers.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
L1 = ROOT / "outputs/recert_l1_20260926"
ASSETS = ("159915.SZ", "159941.SZ", "513030.SH", "513520.SH", "159985.SZ", "518880.SH")
FEE = 0.001
EXPECTED = {
    "prices": "20a9a3bec118a4bc5b6829e19699d506d1617acee2dfe8ea7bb836e1404211e8",
    "flags": "39c1d4afc5dc73d59ee3742dc4e275a87ab6f400ecfc7b709796e83c46486ee1",
    "matrix": "2fa744ed1b44825ca47bb5e4e0124fbe024c17cd8823b109319b80608830ed42",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(value: str) -> float | None:
    return None if value == "off" else float(value)


def moment_scores(price: np.ndarray, lookback: int, power: float) -> tuple[np.ndarray, np.ndarray]:
    """Compute weighted log-price slope via moments, independent of polyfit."""
    n, a = price.shape
    score = np.full((n, a), np.nan)
    fit = np.full((n, a), np.nan)
    windows = np.lib.stride_tricks.sliding_window_view(price, lookback, axis=0)
    valid_price = np.isfinite(windows).all(axis=2) & (windows > 0).all(axis=2)
    logprice = np.log(np.where(valid_price[:, :, None], windows, 1.0))
    logprice -= logprice[:, :, :1]
    x = np.arange(lookback, dtype=float)
    weight = (x + 1.0) ** power
    mean_x = float(np.dot(weight, x) / weight.sum())
    centered_x = x - mean_x
    denom = float(np.dot(weight, centered_x**2))
    mean_y = np.tensordot(logprice, weight, axes=(2, 0)) / weight.sum()
    centered_y = logprice - mean_y[:, :, None]
    slope = np.tensordot(centered_y, weight * centered_x, axes=(2, 0)) / denom
    total = np.tensordot(centered_y**2, weight, axes=(2, 0))
    residual = centered_y - slope[:, :, None] * centered_x
    error = np.tensordot(residual**2, weight, axes=(2, 0))
    valid = valid_price & (np.ptp(logprice, axis=2) > 1e-12) & (total > 0)
    exponent = slope * 252.0
    score_valid = valid & np.isfinite(exponent) & (exponent <= math.log(np.finfo(float).max))
    with np.errstate(over="ignore", invalid="ignore"):
        score[lookback - 1 :] = np.where(score_valid, np.expm1(exponent), np.nan)
        fit[lookback - 1 :] = np.where(valid, np.maximum(0.0, 1.0 - error / total), np.nan)
    return score, fit


def replay(dates: pd.DatetimeIndex, price: np.ndarray, stale: np.ndarray,
           score: np.ndarray, fit: np.ndarray, arm: dict[str, str]) -> pd.DataFrame:
    floor = parse(arm["score_floor"])
    ceiling = parse(arm["score_ceiling"])
    r2 = parse(arm["r2_threshold"])
    buffer = float(arm["switch_buffer"])
    eligible = np.isfinite(score)
    if floor is not None:
        eligible &= score > floor
    if ceiling is not None:
        eligible &= score < ceiling
    if r2 is not None:
        eligible &= np.isfinite(fit) & (fit >= r2)

    cash, shares, held, nav_prev = 1.0, 0.0, -1, 1.0
    entries: list[dict] = []
    for t, date in enumerate(dates):
        old = held
        marked = cash if old < 0 else cash + shares * price[t, old]
        if not np.isfinite(marked) or marked <= 0:
            raise AssertionError((arm["arm"], date, "invalid marked equity"))
        candidates = np.flatnonzero(eligible[t])
        best = int(candidates[np.argmax(score[t, candidates])]) if len(candidates) else -1
        target = best
        buffer_blocked = bool(
            old >= 0 and best >= 0 and old != best and eligible[t, old]
            and buffer > 1.0 and score[t, best] <= score[t, old] * buffer
        )
        if buffer_blocked:
            target = old
        stale_legs = [j for j in (old, target) if j >= 0 and old != target and stale[t, j]]
        stale_blocked = bool(stale_legs)
        if stale_blocked:
            target = old
        sells = int(old >= 0 and target != old)
        buys = int(target >= 0 and target != old)
        turnover = sells + buys
        fee_paid = marked * FEE * turnover
        if sells:
            cash += shares * price[t, old]
            shares = 0.0
            cash -= marked * FEE
        if buys:
            cash -= marked * FEE
            shares = cash / price[t, target]
            cash = 0.0
        held = target
        nav = cash if held < 0 else cash + shares * price[t, held]
        if cash < -1e-10 or shares < -1e-10 or abs(nav - (marked - fee_paid)) > 1e-9:
            raise AssertionError((arm["arm"], date, "cash/share accounting", cash, shares, nav, marked - fee_paid))
        entries.append({
            "date": date,
            "position_before": "CASH" if old < 0 else ASSETS[old],
            "best_candidate": "CASH" if best < 0 else ASSETS[best],
            "position": "CASH" if held < 0 else ASSETS[held],
            "trade_target": "" if old == held else ("CASH" if held < 0 else ASSETS[held]),
            "buffer_blocked": buffer_blocked,
            "stale_blocked": stale_blocked,
            "eligible_assets": len(candidates),
            "buy_legs": buys, "sell_legs": sells,
            "turnover": turnover, "cost": FEE * turnover,
            "fee_cash": fee_paid,
            "cash": cash, "shares": shares,
            "gross_return": marked / nav_prev - 1.0,
            "return": nav / nav_prev - 1.0,
            "nav": nav,
        })
        nav_prev = nav
    return pd.DataFrame(entries).set_index("date")


def metrics(curve: pd.DataFrame, arm: str) -> list[dict]:
    windows: list[tuple[str, object]] = [
        ("Full", None), ("10Y", 2520), ("5Y", 1260), ("3Y", 756), ("1Y", 252),
        ("six_etf_all_scoreable", pd.Timestamp("2020-01-09")),
    ]
    results = []
    for label, window in windows:
        sub = curve if window is None else (curve.tail(window) if isinstance(window, int) else curve.loc[window:])
        nav = sub.nav.to_numpy(float)
        peak = np.maximum.accumulate(nav)
        dd = nav / peak - 1.0
        trough_i = int(np.argmin(dd))
        peak_i = int(np.argmax(nav[:trough_i + 1]))
        results.append({
            "arm": arm, "window": label, "start": sub.index[0].date().isoformat(),
            "end": sub.index[-1].date().isoformat(), "rows": len(sub),
            "annual_n_minus_1": float((nav[-1] / nav[0]) ** (252.0 / (len(sub) - 1)) - 1.0),
            "maxdd": float(dd.min()),
            "peak": sub.index[peak_i].date().isoformat(),
            "trough": sub.index[trough_i].date().isoformat(),
            "end_nav": float(nav[-1]),
            "trade_days": int((sub.turnover > 0).sum()),
            "two_leg_switch_days": int((sub.turnover == 2).sum()),
            "turnover_sum": float(sub.turnover.sum()),
            "fee_cash_units": float(sub.fee_cash.sum()),
            "cash_days": int(sub.position.eq("CASH").sum()),
            "average_old_exposure": float(sub.position_before.ne("CASH").mean()),
            "buffer_block_days": int(sub.buffer_blocked.sum()),
            "stale_block_days": int(sub.stale_blocked.sum()),
        })
    return results


def main() -> None:
    matrix_path = HERE / "agent_a_matrix.csv"
    price_path = L1 / "prices_aligned_qfq_through_20260924.csv.gz"
    flags_path = L1 / "price_ffill_flags_through_20260924.csv.gz"
    for key, path in (("matrix", matrix_path), ("prices", price_path), ("flags", flags_path)):
        if sha(path) != EXPECTED[key]:
            raise AssertionError((key, "frozen SHA mismatch", sha(path)))
    matrix = pd.read_csv(matrix_path, dtype=str).fillna("").to_dict("records")
    prices = pd.read_csv(price_path, index_col=0, parse_dates=True)
    flags = pd.read_csv(flags_path, index_col=0, parse_dates=True).astype(bool)
    if not prices.index.equals(flags.index) or list(prices.columns) != list(ASSETS):
        raise AssertionError("L1 price/flag identity mismatch")
    dates = pd.DatetimeIndex(prices.index)
    pv = prices.to_numpy(float)
    stale = flags.to_numpy(bool)
    signal_cache = {}
    all_metrics = []
    overview = {}
    curve_dir = HERE / "agent_a_daily"
    curve_dir.mkdir(exist_ok=True)
    for arm in matrix:
        key = (int(arm["lookback"]), float(arm["weight_power"]))
        if key not in signal_cache:
            signal_cache[key] = moment_scores(pv, *key)
        signal, fit = signal_cache[key]
        daily = replay(dates, pv, stale, signal, fit, arm)
        daily.to_csv(curve_dir / f'{arm["arm"]}.csv.gz', compression="gzip", index_label="date")
        all_metrics.extend(metrics(daily, arm["arm"]))
        overview[arm["arm"]] = {
            "position_days": int(daily.position.ne("CASH").sum()),
            "end_nav": float(daily.nav.iloc[-1]),
            "trade_days": int((daily.turnover > 0).sum()),
            "turnover_sum": float(daily.turnover.sum()),
            "fee_cash_units": float(daily.fee_cash.sum()),
            "min_cash": float(daily.cash.min()),
            "min_shares": float(daily.shares.min()),
            "max_account_bridge_abs": float(np.max(np.abs(daily.nav - (daily.nav.shift(1).fillna(1.0) * (1.0 + daily.gross_return) * (1.0 - daily.cost))))),
        }
    pd.DataFrame(all_metrics).to_csv(HERE / "agent_a_metrics.csv", index=False)
    (HERE / "agent_a_overview.json").write_text(json.dumps(overview, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"paths": len(matrix), "rows_per_path": len(dates), "signal_configs": len(signal_cache),
                      "formal": overview["formal_111"], "max_bridge": max(v["max_account_bridge_abs"] for v in overview.values())}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
