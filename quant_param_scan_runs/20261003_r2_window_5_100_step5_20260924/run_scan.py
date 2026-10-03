"""Research-only R² lookback scan with the formal 25-day Score held fixed."""

import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
RUN = Path(__file__).resolve().parent
L1 = ROOT / "outputs/recert_l1_20260926"
L2 = ROOT / "outputs/recert_l2_20260926"
L6 = ROOT / "quant_param_scan_runs/20260926_six_etf_v1_3_l6_parameter_basis_20260924"
BOT = ROOT / "poe_subd_six_etf_v1_3_bot.py"
GRID = tuple(range(5, 101, 5))
COMMON_100_START = pd.Timestamp("2020-05-07")
WINDOWS = (("full", None), ("last_10y", 2520), ("last_5y", 1260),
           ("last_3y", 756), ("last_1y", 252),
           ("all_six_100d_scoreable", COMMON_100_START))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def label(value):
    return f"r2_window_{value:03d}"


def weighted_r2(window, size):
    values = window.dropna().astype(float)
    if len(values) != size or (values <= 0).any() or not np.isfinite(values.to_numpy()).all():
        return math.nan
    y = np.log(values.to_numpy())
    if float(np.ptp(y)) <= 1e-12:
        return math.nan
    y = y - y[0]
    x = np.arange(size, dtype=float)
    weights = np.arange(1, size + 1, dtype=float)
    slope, intercept = np.polyfit(x, y, 1, w=np.sqrt(weights))
    fitted = slope * x + intercept
    y_bar = float(np.average(y, weights=weights))
    ss_tot = float(np.sum(weights * (y - y_bar) ** 2))
    if ss_tot <= 0:
        return math.nan
    ss_res = float(np.sum(weights * (y - fitted) ** 2))
    return max(0.0, 1.0 - ss_res / ss_tot)


def precompute_formal_score_and_r2(prices, bot):
    scores = np.full((len(prices), len(bot.ASSETS)), np.nan)
    r2 = np.full_like(scores, np.nan)
    for idx in range(bot.LOOKBACK - 1, len(prices)):
        for col, code in enumerate(bot.ASSETS):
            window = prices[code].iloc[idx - bot.LOOKBACK + 1:idx + 1]
            scores[idx, col], r2[idx, col] = bot.weighted_slope_score_and_r2(window)
    return scores, r2


def precompute_r2(prices, bot, size):
    result = np.full((len(prices), len(bot.ASSETS)), np.nan)
    for idx in range(size - 1, len(prices)):
        for col, code in enumerate(bot.ASSETS):
            result[idx, col] = weighted_r2(prices[code].iloc[idx - size + 1:idx + 1], size)
    return result


def metrics(frame, candidate, value, role, segment, start):
    part = frame if start is None else frame.loc[frame.date >= start]
    part = part.reset_index(drop=True)
    nav = part.nav.to_numpy(float)
    if len(nav) < 2 or not np.isfinite(nav).all() or not (nav > 0).all():
        raise RuntimeError(f"Invalid NAV in {candidate}/{segment}")
    returns = nav[1:] / nav[:-1] - 1.0
    ratio = float(nav[-1] / nav[0])
    annual = ratio ** (252.0 / (len(nav) - 1)) - 1.0
    std = float(np.std(returns, ddof=1))
    vol = std * math.sqrt(252.0)
    defined = std > 0
    sharpe = float(np.mean(returns) / std * math.sqrt(252.0)) if defined else 0.0
    dd = nav / np.maximum.accumulate(nav) - 1.0
    low = int(np.argmin(dd))
    high = int(np.argmax(nav[:low + 1]))
    fee_base = frame.nav.shift(1).fillna(1.0) * (1.0 + frame.gross_return)
    part_index = frame.index[frame.date >= start] if start is not None else frame.index
    paid_fee = float((fee_base.loc[part_index] * frame.loc[part_index, "cost"]).sum())
    return {
        "candidate": candidate, "group": "R2_WINDOW", "value": value, "role": role,
        "R2_WINDOW": value, "SCORE_WINDOW": 25, "segment": segment,
        "start": str(part.date.iloc[0].date()), "end": str(part.date.iloc[-1].date()),
        "rows": len(part), "nav_changes": len(part) - 1,
        "ann_return": annual, "ann_vol": vol, "sharpe_repo": sharpe,
        "sharpe_defined": defined,
        "max_dd": float(dd[low]), "max_dd_peak": str(part.date.iloc[high].date()),
        "max_dd_trough": str(part.date.iloc[low].date()), "total_return": ratio - 1.0,
        "end_nav": float(nav[-1]), "trade_days": int((part.turnover > 0).sum()),
        "two_sided_switch_days": int((part.turnover == 2).sum()),
        "turnover_total": float(part.turnover.sum()), "cost_rate_total": float(part.cost.sum()),
        "paid_fee_initial_capital_units": paid_fee,
        "cash_days": int((part.position == "CASH").sum()),
        "avg_carried_exposure": float(part.fraction_before.mean()),
        "stale_trade_block_days": int(part.trade_blocked_by_stale_price.sum()),
        "buffer_block_days": int(part.buffer_blocked.sum()),
    }


def main():
    manifest = json.loads((L1 / "capture_manifest.json").read_text(encoding="utf-8"))
    for key in ("aligned", "flags"):
        if sha(manifest[key]["path"]) != manifest[key]["sha256"]:
            raise RuntimeError(f"L1 {key} hash mismatch")
    prices = pd.read_csv(manifest["aligned"]["path"], parse_dates=["date"]).set_index("date")
    flags = pd.read_csv(manifest["flags"]["path"], parse_dates=["date"]).set_index("date").astype(bool)
    if (len(prices) != 3594 or prices.index[-1] != pd.Timestamp("2026-09-24")
            or not prices.index.equals(flags.index)):
        raise RuntimeError("L1 price or flag coverage mismatch")
    bot = load_module("six_etf_v13_r2_window_grid", BOT)
    helper = load_module("six_etf_v13_l6_r2_window_helpers", L6 / "run_l6_scan.py")
    if (bot.LOOKBACK, bot.SCORE_MIN, bot.SCORE_MAX, bot.R2_THRESHOLD,
        bot.SWITCH_BUFFER, bot.ONE_WAY_COST, bot.TARGET_VOL_ENABLED,
        bot.OVERHEAT_ENABLED, bot.STAGED_ENTRY_ENABLED) != (25, .5, 5.5, .25, 1., .001, False, False, False):
        raise RuntimeError("Formal constants changed")
    all100 = prices[list(bot.ASSETS)].notna().rolling(100).sum().eq(100).all(axis=1)
    if all100.loc[all100].index[0] != COMMON_100_START:
        raise RuntimeError("Common 100-day scoreability date changed")
    config = bot._build_config(end_date=pd.Timestamp("2026-09-24"))
    case = bot.EntryCase("full_entry", "full_entry", 1.0)
    formal = bot.run_staged_entry(prices, config, case, .25, 1.0,
                                  price_ffill_flags=flags).reset_index()
    official = pd.read_csv(L2 / "formal_daily_20260924.csv.gz", parse_dates=["date"])
    formal_l2 = helper.assert_same_path(formal, official, "formal_25d_vs_L2")
    print("Unchanged formal path vs L2 PASS; precomputing official 25-day Score", flush=True)
    score25, r2_25 = precompute_formal_score_and_r2(prices, bot)
    original_calc_scores = bot.calc_scores
    out = RUN / "daily_outputs"
    out.mkdir(exist_ok=True)
    long_rows, wide_rows, event_rows = [], [], []
    formal_runtime = None
    for i, size in enumerate(GRID, 1):
        r2_values = r2_25 if size == 25 else precompute_r2(prices, bot, size)
        if size == 25:
            for idx in (24, 99, 500, 2000, 3593):
                for col, code in enumerate(bot.ASSETS):
                    actual = weighted_r2(prices[code].iloc[idx - 24:idx + 1], 25)
                    expected = r2_25[idx, col]
                    if not (np.isnan(actual) and np.isnan(expected)) and not np.isclose(actual, expected, atol=1e-12, rtol=0):
                        raise RuntimeError(f"Custom R2 and official R2 mismatch {idx}/{code}")

        def lookup_calc_scores(prices_arg, idx, r2_threshold=None):
            if len(prices_arg) != len(prices) or not prices_arg.index.equals(prices.index):
                raise RuntimeError("Runtime prices differ from frozen panel")
            scores, r2_map, raw = {}, {}, {}
            for col, code in enumerate(bot.ASSETS):
                score = float(score25[idx, col])
                r2 = float(r2_values[idx, col])
                if not math.isnan(score):
                    raw[code] = score
                if not math.isnan(r2):
                    r2_map[code] = r2
                if (bot.SCORE_MIN < score < bot.SCORE_MAX
                        and (r2_threshold is None or (not math.isnan(r2) and r2 >= r2_threshold))):
                    scores[code] = score
            return scores, r2_map, raw

        bot.calc_scores = lookup_calc_scores
        try:
            curve = bot.run_staged_entry(prices, config, case, .25, 1.0,
                                         price_ffill_flags=flags).reset_index()
        finally:
            bot.calc_scores = original_calc_scores
        if size == 25:
            formal_runtime = helper.assert_same_path(curve, formal, "separate_r2_25d_vs_formal")
            for code in bot.ASSETS:
                field = f"r2_{code}"
                if not np.allclose(curve[field], formal[field], atol=0, rtol=0, equal_nan=True):
                    raise RuntimeError(f"Formal R2 field mismatch {code}")
            print("Separated R2-window 25-day path vs formal PASS", flush=True)
        if not pd.DatetimeIndex(curve.date).equals(pd.DatetimeIndex(formal.date)):
            raise RuntimeError(f"Date mismatch: {size}")
        if not np.isfinite(curve.nav.to_numpy(float)).all() or not (curve.nav > 0).all():
            raise RuntimeError(f"Invalid NAV: {size}")
        if not (curve.holding_fraction.between(0, 1).all()
                and curve.fraction_before.between(0, 1).all()):
            raise RuntimeError(f"Invalid exposure: {size}")
        if curve.buffer_blocked.any() or curve.staged_initial.any() or curve.staged_fill_count.any():
            raise RuntimeError(f"Disabled layer fired: {size}")
        candidate = label(size)
        path = out / f"{candidate}.csv.gz"
        curve.to_csv(path, index=False, compression="gzip", float_format="%.16g")
        role = "formal" if size == 25 else "candidate"
        wide = {"candidate": candidate, "R2_WINDOW": size, "SCORE_WINDOW": 25, "role": role}
        for segment, window in WINDOWS:
            start = (None if window is None else pd.Timestamp(curve.date.iloc[-window])
                     if isinstance(window, int) else window)
            row = metrics(curve, candidate, size, role, segment, start)
            long_rows.append(row)
            wide[f"ann_return_{segment}"] = row["ann_return"]
            wide[f"max_dd_{segment}"] = row["max_dd"]
            wide[f"sharpe_repo_{segment}"] = row["sharpe_repo"]
            wide[f"sharpe_defined_{segment}"] = row["sharpe_defined"]
            if segment == "full":
                wide.update(end_nav_full=row["end_nav"], trade_days_full=row["trade_days"],
                            turnover_total_full=row["turnover_total"], cash_days_full=row["cash_days"])
        wide_rows.append(wide)
        different = (curve.position.fillna("<NA>").astype(str).to_numpy()
                     != formal.position.fillna("<NA>").astype(str).to_numpy())
        event_rows.append({"candidate": candidate, "R2_WINDOW": size,
                           "position_diff_days_vs_formal": int(different.sum()),
                           "first_diff_vs_formal": str(curve.date.iloc[np.flatnonzero(different)[0]].date()) if different.any() else "",
                           "daily_path": str(path.relative_to(ROOT)), "daily_sha256": sha(path)})
        print(f"{i:02d}/{len(GRID)} R2 window={size:3d} full={wide['ann_return_full']:.4%} / {wide['max_dd_full']:.4%} trades={wide['trade_days_full']}", flush=True)
    summary = pd.DataFrame(long_rows)
    wide = pd.DataFrame(wide_rows)
    base = summary.loc[summary.candidate == label(25)].set_index("segment")
    for field in ("ann_return", "max_dd", "trade_days", "turnover_total", "cash_days"):
        summary[f"formal_{field}"] = summary.segment.map(base[field])
    summary["delta_ann_vs_formal_pp"] = (summary.ann_return - summary.formal_ann_return) * 100
    summary["dd_improvement_vs_formal_pp"] = (summary.max_dd - summary.formal_max_dd) * 100
    summary.to_csv(RUN / "scan_summary.csv", index=False)
    wide.to_csv(RUN / "window_metrics.csv", index=False)
    pd.DataFrame(event_rows).to_csv(RUN / "candidate_event_counts.csv", index=False)
    (RUN / "parity_checks.json").write_text(json.dumps({
        "formal_unpatched_vs_L2": formal_l2,
        "separate_r2_window_25_vs_formal": formal_runtime,
        "formal_code_sha256": sha(BOT),
        "price_sha256": sha(manifest["aligned"]["path"]),
        "flags_sha256": sha(manifest["flags"]["path"]),
        "candidate_count": len(GRID),
        "score_window": 25,
        "r2_threshold": .25,
        "all_six_100d_scoreable_start": str(COMMON_100_START.date()),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"COMPLETE {len(GRID)} candidates, {len(summary)} window rows", flush=True)


if __name__ == "__main__":
    main()
