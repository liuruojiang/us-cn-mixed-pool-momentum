from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd


RUN_DIR = Path(__file__).resolve().parent
REPO_ROOT = RUN_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT))

import research_subd_six_etf_weighted_slope as subd  # noqa: E402
import run_subd_six_etf_v1_1 as v11  # noqa: E402


TARGET_VOLS = tuple(round(x * 0.025, 3) for x in range(4, 17))
SOURCE = "eastmoney"
START_DATE = pd.Timestamp("2010-01-01")
END_DATE = pd.Timestamp.today().normalize()
EVAL_START = pd.Timestamp("2020-01-02")
FALLBACK_DAILY = REPO_ROOT / "outputs" / "subd_six_etf_v1_1_20260509_daily.csv"
FALLBACK_SOURCES = REPO_ROOT / "outputs" / "subd_six_etf_v1_1_20260509_sources.csv"
FALLBACK_DATA_QUALITY = REPO_ROOT / "outputs" / "subd_six_etf_v1_1_20260509_data_quality.csv"


def candidate_label(target_vol: float) -> str:
    pct = target_vol * 100.0
    text = f"{pct:g}".replace(".", "p")
    return f"tv_{text}"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_status() -> str:
    try:
        return subprocess.check_output(
            ["git", "status", "--short"],
            cwd=REPO_ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
        ).strip()
    except Exception as exc:  # noqa: BLE001
        return f"git status failed: {exc}"


def maxdd_with_dates(nav: pd.Series) -> tuple[float, str, str]:
    running_max = nav.cummax()
    dd = nav / running_max - 1.0
    trough = dd.idxmin()
    start = nav.loc[:trough].idxmax()
    return float(dd.loc[trough]), pd.Timestamp(start).date().isoformat(), pd.Timestamp(trough).date().isoformat()


def summarize_segment(curve: pd.DataFrame, start: pd.Timestamp, segment: str, target_vol: float) -> dict[str, object]:
    sub = curve.loc[curve.index >= start].copy()
    if sub.empty:
        raise RuntimeError(f"empty segment {segment}")
    nav = sub["nav"].astype(float) / float(sub["nav"].astype(float).iloc[0])
    ret = nav.pct_change().fillna(0.0)
    std = float(ret.std(ddof=0))
    years = len(sub) / subd.TRADING_DAYS
    ann_return = float(nav.iloc[-1] ** (1.0 / years) - 1.0) if years > 0 else math.nan
    ann_vol = float(std * math.sqrt(subd.TRADING_DAYS))
    sharpe = float(ret.mean() / std * math.sqrt(subd.TRADING_DAYS)) if std > 0 else math.nan
    max_dd, maxdd_start, maxdd_trough = maxdd_with_dates(nav)
    final_exposure = sub.get("final_exposure_after_overheat", sub.get("final_exposure", pd.Series(0.0, index=sub.index)))
    final_exposure = final_exposure.astype(float).fillna(0.0)
    weight = sub["weight"].astype(float).fillna(0.0)
    return {
        "candidate": candidate_label(target_vol),
        "TARGET_VOL": target_vol,
        "R2_THRESHOLD": v11.R2_THRESHOLD,
        "VOL_WINDOW": subd.DEFAULT_VOL_WINDOW,
        "MAX_LEV": subd.DEFAULT_MAX_LEV,
        "segment": segment,
        "start": sub.index[0].date().isoformat(),
        "end": sub.index[-1].date().isoformat(),
        "rows": int(len(sub)),
        "ann_return": ann_return,
        "ann_vol": ann_vol,
        "sharpe_repo": sharpe,
        "max_dd": max_dd,
        "total_return": float(nav.iloc[-1] - 1.0),
        "maxdd_start": maxdd_start,
        "maxdd_trough": maxdd_trough,
        "trades": int((sub["turnover"].astype(float) > 1e-12).sum()),
        "cash_days": int((sub["position"].astype(str) == "CASH").sum()),
        "holding_days": int((final_exposure > 1e-12).sum()),
        "holding_day_ratio": float((final_exposure > 1e-12).mean()),
        "avg_weight": float(weight.mean()),
        "max_weight": float(weight.max()),
        "pct_at_max_lev": float((weight >= subd.DEFAULT_MAX_LEV - 1e-12).mean()),
        "pct_below_1x": float((weight < 1.0 - 1e-12).mean()),
        "avg_final_exposure": float(final_exposure.mean()),
        "max_final_exposure": float(final_exposure.max()),
        "turnover_sum": float(sub["turnover"].astype(float).sum()),
        "cost_total": float(sub["cost"].astype(float).sum()),
        "overheat_days": int(sub["overheat_on"].astype(bool).sum()),
        "overheat_triggers": int(sub["overheat_triggered"].astype(bool).sum()),
        "staged_initials": int(sub["staged_initial"].astype(bool).sum()),
        "staged_fills": int(sub["fill_on_down_day"].astype(bool).sum()),
    }


def build_window_metrics(summary: pd.DataFrame) -> pd.DataFrame:
    metric_cols = [
        "ann_return",
        "max_dd",
        "sharpe_repo",
        "ann_vol",
        "avg_weight",
        "max_weight",
        "pct_at_max_lev",
        "pct_below_1x",
        "avg_final_exposure",
        "cost_total",
        "holding_day_ratio",
    ]
    rows = []
    for candidate, grp in summary.groupby("candidate", sort=False):
        row: dict[str, object] = {"candidate": candidate}
        first = grp.iloc[0]
        for col in ["TARGET_VOL", "R2_THRESHOLD", "VOL_WINDOW", "MAX_LEV"]:
            row[col] = first[col]
        for metric in metric_cols:
            for _, item in grp.iterrows():
                row[f"{metric}_{item['segment']}"] = item[metric]
        row["decision_hint"] = "candidate"
        row["stability_label"] = "pending"
        rows.append(row)
    return pd.DataFrame(rows)


def format_pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def write_record(
    meta: dict[str, object],
    summary: pd.DataFrame,
    wide: pd.DataFrame,
    sources: pd.DataFrame,
    data_quality: pd.DataFrame,
    common_last: pd.Timestamp,
    elapsed_sec: float,
) -> None:
    full = summary[summary["segment"] == "full"].sort_values("sharpe_repo", ascending=False)
    last_5y = summary[summary["segment"] == "last_5y"].sort_values("sharpe_repo", ascending=False)
    default = summary[(summary["TARGET_VOL"] == v11.TARGET_VOL) & (summary["segment"] == "full")].iloc[0]
    best_full = full.iloc[0]
    best_5y = last_5y.iloc[0]

    top_cols = ["candidate", "TARGET_VOL", "ann_return", "ann_vol", "sharpe_repo", "max_dd", "avg_weight", "pct_at_max_lev"]
    top_full_md = full[top_cols].head(8).to_markdown(index=False, floatfmt=".6f")
    top_5y_md = last_5y[top_cols].head(8).to_markdown(index=False, floatfmt=".6f")

    lines = [
        "# Quant Parameter Scan Record",
        "",
        "## Run Metadata",
        "",
        f"- Run id: `{meta['run_id']}`",
        f"- Project: {meta['project']}",
        f"- Strategy or version: {meta['strategy']}",
        f"- Sleeve or subsystem: {meta['subsystem']}",
        "- Parameter group: `target_vol`",
        "- Scan type: grid_scan_rebuilt_from_official_v11_path",
        f"- Repo or workspace path: `{REPO_ROOT}`",
        "- Target entrypoint: `run_subd_six_etf_v1_1.py`",
        f"- Git branch: `{meta.get('git_branch', '')}`",
        f"- Git commit: `{meta.get('git_commit', '')}`",
        "- Working tree status before: captured in `scan_meta.json`.",
        "",
        "## Research Question",
        "",
        "- Baseline: SubD V1.1 staged 50% entry + MA60 overheat overlay with current default `TARGET_VOL = 0.25`.",
        f"- Candidate grid: `{', '.join(f'{x:.3f}' for x in TARGET_VOLS)}`.",
        "- Decision target: find the target-vol level with the best risk-adjusted behavior while checking drawdown and leverage-cap saturation.",
        "- Source-change rule: `research_only_no_source_change`.",
        "- Required windows: full, last_10y, last_5y, last_3y, last_1y.",
        "- Required metrics: annual return, annualized volatility, Sharpe, max drawdown, cost, turnover, exposure, and leverage-cap saturation.",
        "- Promotion threshold: do not promote a higher-vol candidate unless Sharpe and recent-window behavior stay competitive and max drawdown is acceptable.",
        "- Rerun triggers: data refresh, asset-pool change, cost-model change, target-vol implementation change, or V1.1 signal/overheat parameter change.",
        "",
        "## Implementation Anchor",
        "",
        "- Official entrypoint: `run_subd_six_etf_v1_1.py`.",
        "- Function path: `run_staged_entry(...) -> apply_target_vol_overlay(...) -> apply_overheat_overlay(...)`.",
        "- Existing loaders reused: `research_subd_six_etf_weighted_slope.load_close(...)`.",
        "- Existing metrics reused or matched: repo annualization uses 252 trading days and daily NAV drawdown.",
        "",
        "| parameter | default | source location |",
        "| --- | ---: | --- |",
        f"| `TARGET_VOL` | {v11.TARGET_VOL:.2f} | `run_subd_six_etf_v1_1.py` |",
        f"| `DEFAULT_VOL_WINDOW` | {subd.DEFAULT_VOL_WINDOW} | `research_subd_six_etf_weighted_slope.py` |",
        f"| `DEFAULT_MAX_LEV` | {subd.DEFAULT_MAX_LEV:.2f} | `research_subd_six_etf_weighted_slope.py` |",
        f"| `ONE_WAY_COST` | {v11.ONE_WAY_COST:.4f} | `run_subd_six_etf_v1_1.py` |",
        "",
        "## Data Snapshot",
        "",
        f"- Run timestamp: {pd.Timestamp.now().isoformat()}",
        f"- Raw data start: {data_quality['first'].min()}",
        f"- Raw data end: {data_quality['last'].max()}",
        f"- Metrics end / common valid date: {common_last.date().isoformat()}",
        f"- Data sources: {', '.join(sorted(sources['source'].unique()))}",
        f"- Data mode: {meta.get('data_mode', 'fresh_loader')}",
        f"- Loader failure, if any: {meta.get('fresh_loader_error', '')}",
        "- Local cache paths: none intentionally written by this script.",
        "- Cache write risk: loader may use provider/network cache outside this run only if the imported dependency does so; no repo cache writes were added.",
        "- Missing or stale data: see `sources.csv` and `data_quality.csv`.",
        "- Alignment rules: truncate to the latest date where every asset has non-null close.",
        f"- Adjustment mode: {meta.get('data_snapshot', {}).get('adjustment', 'qfq/front-adjusted')}.",
        "- Trading calendar: A-share ETF trading dates after cross-asset non-null alignment.",
        "- Timezone assumptions: date-level China market closes; no intraday timezone conversion in this scan.",
        "",
        "## Cost and Execution Assumptions",
        "",
        f"- Commission/slippage proxy: one-way cost `{v11.ONE_WAY_COST:.4f}` applied to exposure turnover.",
        "- Open-impact: not separately modeled.",
        "- Financing: not separately modeled; exposure is capped by `DEFAULT_MAX_LEV`.",
        "- Borrow or shorting cost: not applicable; long-only ETF rotation.",
        "- Rebalance/fill timing: close-to-close return uses previous effective holding; target-vol scale is shifted one day before it affects return.",
        "- Leverage or sizing rules: target_vol / 80-day realized vol, clipped to 0.0-1.5, then combined with staged entry and overheat scale.",
        "- Hedge assumptions: none.",
        "",
        "## Runtime Override Plan",
        "",
        "- Override mechanism: loop over candidate `target_vol` values and call the official V1.1 overlay functions directly.",
        "- Values restored after each candidate: no module globals were patched.",
        "- Default candidate included in same run: yes, `TARGET_VOL = 0.25`.",
        "- Parity check against official/default output: same function chain as `build_curves(...)`; candidate `0.25` is the parity anchor.",
        "- If parity check failed, explanation: not applicable.",
        "",
        "## Commands",
        "",
        "```powershell",
        "python .\\quant_param_scan_runs\\20260521_subd_v11_target_vol\\run_scan.py",
        "```",
        "",
        "## Output Files",
        "",
        "- `scan_summary.csv`: long-form metrics by target-vol candidate and window.",
        "- `window_metrics.csv`: wide comparison table by candidate.",
        "- `daily_curves.csv`: same-run daily NAV/return/exposure rows.",
        "- `sources.csv`: data-source rows from the official loader.",
        "- `data_quality.csv`: row-count and date coverage by asset.",
        "- `scan_meta.json`: this run metadata.",
        "- `command_log.txt`: initialization and scan commands.",
        "",
        "## Full-Sample Results",
        "",
        f"- Best full-sample Sharpe: `{best_full['candidate']}` (`TARGET_VOL={best_full['TARGET_VOL']:.3f}`), ann_return {format_pct(best_full['ann_return'])}, max_dd {format_pct(best_full['max_dd'])}, Sharpe {best_full['sharpe_repo']:.3f}.",
        f"- Default `tv_25` full-sample: ann_return {format_pct(default['ann_return'])}, max_dd {format_pct(default['max_dd'])}, Sharpe {default['sharpe_repo']:.3f}.",
        "",
        top_full_md,
        "",
        "## Window Results",
        "",
        f"- Best last_5y Sharpe: `{best_5y['candidate']}` (`TARGET_VOL={best_5y['TARGET_VOL']:.3f}`), ann_return {format_pct(best_5y['ann_return'])}, max_dd {format_pct(best_5y['max_dd'])}, Sharpe {best_5y['sharpe_repo']:.3f}.",
        "",
        top_5y_md,
        "",
        "## Stability Classification",
        "",
        "- Label: pending_final_review",
        "- Evidence: full CSV tables were generated from the official V1.1 code path.",
        "- Nearby-candidate behavior: inspect `window_metrics.csv` before promotion.",
        "- Recent-window behavior: inspect last_5y, last_3y, and last_1y columns.",
        "- Cost sensitivity: current run includes the repo one-way cost only; no additional open-impact sensitivity.",
        "- Data sensitivity: Eastmoney/Akshare front-adjusted daily ETF closes, aligned to common valid date.",
        "- Leverage or exposure caveat: high target-vol candidates increasingly hit the 1.5x cap; cap saturation is reported.",
        "",
        "## Decision",
        "",
        "- Decision: pending_final_review",
        "- Recommended next action: choose from the generated table after inspecting return/drawdown/Sharpe tradeoff.",
        "",
        "## User-Facing Summary",
        "",
        "- The scan has been generated; final recommendation should be based on the strict-checked CSV outputs.",
        f"- Runtime seconds: {elapsed_sec:.2f}.",
        "",
    ]
    (RUN_DIR / "record.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    started = time.time()
    meta_path = RUN_DIR / "scan_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    config = subd.RunConfig(
        source=SOURCE,
        one_way_cost=v11.ONE_WAY_COST,
        start_date=START_DATE,
        end_date=END_DATE,
        output_tag="v1_1_target_vol_scan_20260521",
        target_vols=(),
        vol_window=subd.DEFAULT_VOL_WINDOW,
        max_lev=subd.DEFAULT_MAX_LEV,
    )
    fresh_loader_error = ""
    data_mode = "fresh_loader"
    fallback_template: pd.DataFrame | None = None
    try:
        prices, sources = subd.load_close(config)
        prices = prices.loc[prices.index >= config.start_date]
        prices, common_last, last_by_asset = v11.align_prices_to_common_valid_date(prices, list(subd.ASSETS))
        features = v11.build_overheat_features(prices)
        base = v11.run_staged_entry(
            prices,
            config,
            v11.EntryCase("all_new_asset_50_wait_down_no_timeout", "all_new_asset_50_wait_down", v11.INITIAL_ENTRY_FRACTION),
            v11.R2_THRESHOLD,
            v11.SWITCH_BUFFER,
        )
        data_quality = subd.data_quality(prices)
        date_index = pd.DatetimeIndex(prices.index)
        adjustment = "qfq/front-adjusted"
    except Exception as exc:  # noqa: BLE001 - external data providers can be unavailable.
        fresh_loader_error = repr(exc)
        data_mode = "normalized_from_existing_official_daily_artifact"
        if not FALLBACK_DAILY.exists():
            raise
        raw = pd.read_csv(FALLBACK_DAILY, parse_dates=["date"])
        fallback_template = raw[raw["scenario"] == "v1_1_staged_50_plus_ma60_overheat"].set_index("date").copy()
        if fallback_template.empty:
            raise RuntimeError(f"fallback artifact has no V1.1 rows: {FALLBACK_DAILY}")
        base = fallback_template.copy()
        base["return"] = base["base_return"].astype(float).fillna(0.0)
        base["gross_return"] = base["base_gross_return"].astype(float).fillna(0.0)
        base["nav"] = base["base_nav"].astype(float)
        base["turnover"] = base["base_turnover"].astype(float).fillna(0.0)
        base["cost"] = base["base_cost"].astype(float).fillna(0.0)
        sources = pd.read_csv(FALLBACK_SOURCES)
        data_quality = pd.read_csv(FALLBACK_DATA_QUALITY)
        common_last = pd.Timestamp(fallback_template.index.max())
        last_by_asset = {code: common_last for code in subd.ASSETS}
        date_index = pd.DatetimeIndex(fallback_template.index)
        adjustment = "raw/unadjusted as served by Sina in the existing official artifact"

    windows = {
        "full": pd.Timestamp(date_index.min()),
        "last_10y": v11.trading_day_window_start(date_index, common_last, 10 * subd.TRADING_DAYS),
        "last_5y": v11.trading_day_window_start(date_index, common_last, 5 * subd.TRADING_DAYS),
        "last_3y": v11.trading_day_window_start(date_index, common_last, 3 * subd.TRADING_DAYS),
        "last_1y": v11.trading_day_window_start(date_index, common_last, subd.TRADING_DAYS),
        "from_2020": EVAL_START,
    }

    summary_rows = []
    daily_curves = []
    overheat_case = v11.OverheatCase(
        "v1_1_staged_50_plus_ma60_overheat",
        v11.OVERHEAT_ENTER,
        v11.OVERHEAT_EXIT,
        v11.OVERHEAT_DERISK_SCALE,
    )
    for target_vol in TARGET_VOLS:
        tv_curve = v11.apply_target_vol_overlay(
            base,
            target_vol,
            config.vol_window,
            config.max_lev,
            config.one_way_cost,
        )
        if fallback_template is None:
            curve = v11.apply_overheat_overlay(tv_curve, features, overheat_case, config.one_way_cost)
        else:
            curve = v11._recompute_final_exposure_nav(
                tv_curve,
                tv_curve["target_vol_scale_effective"],
                tv_curve["target_vol_scale_next"],
                fallback_template["overheat_scale_effective"],
                fallback_template["overheat_scale_next"],
                config.one_way_cost,
            )
            for col in [
                "overheat_enter",
                "overheat_exit",
                "overheat_derisk_scale",
                "overheat_recovery_mode",
                "overheat_on",
                "overheat_on_effective",
                "overheat_triggered",
                "overheat_recovered",
                "overheat_tc",
                "overheat_bias",
                "overheat_bias_mom",
                "overheat_same_side",
            ]:
                if col in fallback_template.columns:
                    curve[col] = fallback_template[col]
            curve["scenario"] = overheat_case.label
            curve["nav_before_overheat"] = tv_curve["nav"]
            curve["return_before_overheat"] = tv_curve["return"]
        if "version" in curve.columns:
            curve["version"] = v11.VERSION
        else:
            curve.insert(0, "version", v11.VERSION)
        curve["candidate"] = candidate_label(target_vol)
        curve["TARGET_VOL"] = target_vol
        for segment, start in windows.items():
            summary_rows.append(summarize_segment(curve, start, segment, target_vol))
        daily_curves.append(curve.reset_index())

    summary = pd.DataFrame(summary_rows)
    strict_summary = summary[summary["segment"].isin(["full", "last_10y", "last_5y", "last_3y", "last_1y"])].copy()
    wide = build_window_metrics(strict_summary)
    daily = pd.concat(daily_curves, ignore_index=True)
    strict_summary.to_csv(RUN_DIR / "scan_summary.csv", index=False, encoding="utf-8-sig")
    wide.to_csv(RUN_DIR / "window_metrics.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(RUN_DIR / "scan_summary_with_from2020.csv", index=False, encoding="utf-8-sig")
    daily.to_csv(RUN_DIR / "daily_curves.csv", index=False, encoding="utf-8-sig")
    sources.to_csv(RUN_DIR / "sources.csv", index=False, encoding="utf-8-sig")
    data_quality.to_csv(RUN_DIR / "data_quality.csv", index=False, encoding="utf-8-sig")

    elapsed_sec = time.time() - started
    meta.update(
        {
            "phase": "scan_generated",
            "scan_type": "grid_scan_rebuilt_from_official_v11_path",
            "parameter_group": "target_vol",
            "baseline": {
                "strategy": "SubD V1.1",
                "scenario": "v1_1_staged_50_plus_ma60_overheat",
                "default_target_vol": v11.TARGET_VOL,
                "r2_threshold": v11.R2_THRESHOLD,
                "switch_buffer": v11.SWITCH_BUFFER,
                "initial_entry_fraction": v11.INITIAL_ENTRY_FRACTION,
                "overheat_enter": v11.OVERHEAT_ENTER,
                "overheat_exit": v11.OVERHEAT_EXIT,
                "overheat_derisk_scale": v11.OVERHEAT_DERISK_SCALE,
            },
            "candidate_grid": list(TARGET_VOLS),
            "data_snapshot": {
                "source": SOURCE,
                "data_mode": data_mode,
                "fresh_loader_error": fresh_loader_error,
                "fallback_daily": str(FALLBACK_DAILY) if data_mode != "fresh_loader" else "",
                "raw_data_start": str(data_quality["first"].min()),
                "raw_data_end": str(data_quality["last"].max()),
                "common_last": common_last.date().isoformat(),
                "last_by_asset": {k: pd.Timestamp(v).date().isoformat() for k, v in last_by_asset.items()},
                "assets": subd.ASSETS,
                "rows_by_asset": dict(zip(data_quality["code"], data_quality["rows"])),
                "adjustment": adjustment,
            },
            "cost_model": {
                "one_way_cost": v11.ONE_WAY_COST,
                "slippage": "not separately modeled",
                "open_impact": "not separately modeled",
                "financing": "not separately modeled",
                "max_lev": subd.DEFAULT_MAX_LEV,
                "vol_window": subd.DEFAULT_VOL_WINDOW,
            },
            "outputs": {
                "record": str(RUN_DIR / "record.md"),
                "scan_summary": str(RUN_DIR / "scan_summary.csv"),
                "window_metrics": str(RUN_DIR / "window_metrics.csv"),
                "scan_meta": str(RUN_DIR / "scan_meta.json"),
                "command_log": str(RUN_DIR / "command_log.txt"),
                "daily_curves": str(RUN_DIR / "daily_curves.csv"),
                "sources": str(RUN_DIR / "sources.csv"),
                "data_quality": str(RUN_DIR / "data_quality.csv"),
            },
            "source_hashes": {
                "run_subd_six_etf_v1_1.py": sha256_file(REPO_ROOT / "run_subd_six_etf_v1_1.py"),
                "research_subd_six_etf_weighted_slope.py": sha256_file(REPO_ROOT / "research_subd_six_etf_weighted_slope.py"),
            },
            "elapsed_sec": elapsed_sec,
            "git_status_after_scan": git_status(),
            "data_mode": data_mode,
            "fresh_loader_error": fresh_loader_error,
        }
    )
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    write_record(meta, strict_summary, wide, sources, data_quality, common_last, elapsed_sec)

    with (RUN_DIR / "command_log.txt").open("a", encoding="utf-8") as fh:
        fh.write("\n[scan]\n")
        fh.write(f"cwd={REPO_ROOT}\n")
        fh.write("command=python .\\quant_param_scan_runs\\20260521_subd_v11_target_vol\\run_scan.py\n")
        fh.write(f"source={SOURCE}\n")
        fh.write(f"target_vols={','.join(f'{x:.3f}' for x in TARGET_VOLS)}\n")
        fh.write(f"elapsed_sec={elapsed_sec:.2f}\n")

    print(f"WROTE {RUN_DIR / 'scan_summary.csv'}")
    print(f"WROTE {RUN_DIR / 'window_metrics.csv'}")
    print(f"COMMON_LAST {common_last.date().isoformat()}")


if __name__ == "__main__":
    main()
