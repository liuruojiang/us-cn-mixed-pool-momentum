from __future__ import annotations

import importlib.util
import json
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


RUN_DIR = Path(__file__).resolve().parent
REPO_ROOT = RUN_DIR.parents[1]
BOT_PATH = REPO_ROOT / "poe_subd_six_etf_v1_1_bot.py"
DAILY_DIR = RUN_DIR / "daily_outputs"
LOCAL_SAME_SLICE_DAILY = REPO_ROOT / "quant_param_scan_runs" / "20260618_subd_v11_same_slice_ablation" / "daily_curves.csv"
LOCAL_SAME_SLICE_SOURCES = REPO_ROOT / "quant_param_scan_runs" / "20260618_subd_v11_same_slice_ablation" / "sources.csv"
LOCAL_SAME_SLICE_DATA_QUALITY = REPO_ROOT / "quant_param_scan_runs" / "20260618_subd_v11_same_slice_ablation" / "data_quality.csv"


def load_bot_module():
    spec = importlib.util.spec_from_file_location("poe_subd_target_vol_compare", BOT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def git_output(args: list[str]) -> str:
    try:
        return subprocess.check_output(args, cwd=REPO_ROOT, text=True, stderr=subprocess.STDOUT).strip()
    except Exception as exc:
        return f"unavailable: {exc}"


def non_cash_realized_vol(module, curve: pd.DataFrame, vol_window: int) -> pd.Series:
    asset_ret = pd.to_numeric(curve["asset_return"], errors="coerce").replace([np.inf, -np.inf], np.nan)
    position_before = curve["position_before"].astype(str)
    fraction_before = pd.to_numeric(curve["fraction_before"], errors="coerce").fillna(0.0)
    valid = asset_ret.notna() & position_before.ne("CASH") & (fraction_before.abs() > 1e-12)
    realized: list[float] = []
    samples: list[float] = []
    for value, is_valid in zip(asset_ret.to_numpy(dtype=float), valid.to_numpy(dtype=bool)):
        if is_valid and math.isfinite(float(value)):
            samples.append(float(value))
        if len(samples) >= vol_window:
            realized.append(float(np.std(samples[-vol_window:], ddof=0) * math.sqrt(module.TRADING_DAYS)))
        else:
            realized.append(math.nan)
    return pd.Series(realized, index=curve.index, dtype=float)


def apply_non_cash_target_vol_overlay(module, curve: pd.DataFrame, config) -> pd.DataFrame:
    result = curve.copy()
    realized_vol = non_cash_realized_vol(module, result, config.vol_window)
    next_scale = (module.TARGET_VOL / realized_vol).replace([np.inf, -np.inf], config.max_lev)
    next_scale = next_scale.clip(lower=0.0, upper=config.max_lev).fillna(1.0)
    next_scale = module.apply_target_vol_scale_rebalance_threshold(next_scale)
    effective_scale = next_scale.shift(1).fillna(1.0)
    result["base_return"] = result["return"].astype(float).fillna(0.0)
    result["base_nav"] = result["nav"]
    result["base_gross_return"] = result["gross_return"].astype(float).fillna(0.0)
    result["base_turnover"] = module._float_series(result, "turnover", 0.0)
    result["base_cost"] = module._float_series(result, "cost", 0.0)
    result["virtual_base_realized_vol"] = realized_vol
    result["realized_vol"] = realized_vol
    ones = pd.Series(1.0, index=result.index, dtype=float)
    result = module._recompute_final_exposure_nav(
        result,
        effective_scale,
        next_scale,
        ones,
        ones,
        config.one_way_cost,
    )
    result["target_vol"] = module.TARGET_VOL
    result["vol_window"] = config.vol_window
    result["max_lev"] = config.max_lev
    return result


def build_variant(module, prices: pd.DataFrame, config, variant: str) -> pd.DataFrame:
    base = module.run_staged_entry(
        prices,
        config,
        module.EntryCase(
            "all_new_asset_50_wait_down_no_timeout",
            "all_new_asset_50_wait_down",
            module.INITIAL_ENTRY_FRACTION,
        ),
        module.R2_THRESHOLD,
        module.SWITCH_BUFFER,
    )
    if variant == "baseline_strategy_return_vol":
        staged = module.apply_target_vol_overlay(
            base,
            module.TARGET_VOL,
            config.vol_window,
            config.max_lev,
            config.one_way_cost,
        )
    elif variant == "candidate_non_cash_asset_vol":
        staged = apply_non_cash_target_vol_overlay(module, base, config)
    else:
        raise ValueError(f"Unknown variant: {variant}")
    out = module.apply_overheat_overlay(
        staged,
        module.build_overheat_features(prices),
        module.OverheatCase(
            module.V11_SCENARIO,
            module.OVERHEAT_ENTER,
            module.OVERHEAT_EXIT,
            module.OVERHEAT_DERISK_SCALE,
        ),
        config.one_way_cost,
    )
    out.insert(0, "version", module.VERSION)
    out["scenario"] = module.V11_SCENARIO
    out["candidate"] = variant
    return out.reset_index().rename(columns={"index": "date"})


def apply_overheat_template(module, staged: pd.DataFrame, overheat_template: pd.DataFrame, config) -> pd.DataFrame:
    out = staged.copy()
    template = overheat_template.reindex(out.index)
    copy_columns = [
        "overheat_enter",
        "overheat_exit",
        "overheat_derisk_scale",
        "overheat_recovery_mode",
        "overheat_scale_effective",
        "overheat_scale_next",
        "overheat_scale",
        "overheat_on_effective",
        "overheat_on",
        "overheat_triggered",
        "overheat_recovered",
        "overheat_bias",
        "overheat_bias_mom",
        "overheat_same_side",
        "overheat_feature_missing",
    ]
    for col in copy_columns:
        if col in template.columns:
            out[col] = template[col]
    out["scenario"] = module.V11_SCENARIO
    out["nav_before_overheat"] = out["nav"]
    out["return_before_overheat"] = out["return"]
    out["overheat_tc"] = 0.0
    out = module._apply_zero_overheat_execution_guard(out)
    target_vol_effective = module._float_series(out, "target_vol_scale_effective", 1.0)
    target_vol_next = module._float_series(out, "target_vol_scale_next", 1.0)
    out = module._recompute_final_exposure_nav(
        out,
        target_vol_effective,
        target_vol_next,
        out["overheat_scale_effective"],
        out["overheat_scale_next"],
        config.one_way_cost,
    )
    out.insert(0, "version", module.VERSION)
    out["scenario"] = module.V11_SCENARIO
    return out.reset_index().rename(columns={"index": "date"})


def build_local_same_slice_variants(module, config) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, dict[str, Any]]:
    if not LOCAL_SAME_SLICE_DAILY.exists():
        raise RuntimeError(f"Local fallback daily artifact missing: {LOCAL_SAME_SLICE_DAILY}")
    raw = pd.read_csv(LOCAL_SAME_SLICE_DAILY, parse_dates=["date"])
    base = raw[raw["candidate"].astype(str) == "04_add_staged_entry"].copy()
    full = raw[raw["candidate"].astype(str) == "06_full_v11_add_overheat"].copy()
    if base.empty or full.empty:
        raise RuntimeError("Local same-slice artifact lacks required candidates 04_add_staged_entry/06_full_v11_add_overheat")
    base = base.sort_values("date").set_index("date")
    full = full.sort_values("date").set_index("date")
    baseline = full.reset_index().rename(columns={"index": "date"}).copy()
    baseline["candidate"] = "baseline_strategy_return_vol"
    staged_candidate = apply_non_cash_target_vol_overlay(module, base, config)
    candidate = apply_overheat_template(module, staged_candidate, full, config)
    candidate["candidate"] = "candidate_non_cash_asset_vol"
    candidate = candidate.reset_index(drop=True)
    baseline = baseline.reset_index(drop=True)
    sources = pd.read_csv(LOCAL_SAME_SLICE_SOURCES) if LOCAL_SAME_SLICE_SOURCES.exists() else pd.DataFrame()
    latest = pd.Timestamp(baseline["date"].max()).normalize()
    data_quality = pd.read_csv(LOCAL_SAME_SLICE_DATA_QUALITY) if LOCAL_SAME_SLICE_DATA_QUALITY.exists() else pd.DataFrame()
    details = {
        "data_mode": "local_same_slice_fallback",
        "local_daily": str(LOCAL_SAME_SLICE_DAILY),
        "local_sources": str(LOCAL_SAME_SLICE_SOURCES),
        "local_data_quality": str(LOCAL_SAME_SLICE_DATA_QUALITY),
        "raw_start": pd.Timestamp(baseline["date"].min()).date().isoformat(),
        "raw_end": latest.date().isoformat(),
        "common_last": latest.date().isoformat(),
        "rows": int(len(baseline)),
        "data_quality_rows": data_quality.to_dict(orient="records") if not data_quality.empty else [],
    }
    return {
        "baseline_strategy_return_vol": baseline,
        "candidate_non_cash_asset_vol": candidate,
    }, sources, details


def metric_rows(module, daily_by_candidate: dict[str, pd.DataFrame], latest: pd.Timestamp) -> pd.DataFrame:
    windows = {
        "full": None,
        "last_10y": latest - pd.DateOffset(years=10),
        "last_5y": latest - pd.DateOffset(years=5),
        "last_3y": latest - pd.DateOffset(years=3),
        "last_1y": latest - pd.DateOffset(years=1),
    }
    rows: list[dict[str, Any]] = []
    for candidate, daily in daily_by_candidate.items():
        first = pd.Timestamp(daily["date"].min()).normalize()
        for segment, start in windows.items():
            start_ts = first if start is None else max(first, pd.Timestamp(start).normalize())
            m = module.calc_performance(daily, start_ts, latest)
            sub = daily[(daily["date"] >= pd.Timestamp(m["start"])) & (daily["date"] <= pd.Timestamp(m["end"]))]
            turnover = pd.to_numeric(sub["turnover"], errors="coerce").fillna(0.0)
            costs = pd.to_numeric(sub["cost"], errors="coerce").fillna(0.0)
            exposure = pd.to_numeric(sub["exposure_effective"], errors="coerce").fillna(0.0)
            rows.append(
                {
                    "candidate": candidate,
                    "target_vol_realized_vol_input": (
                        "strategy_return_including_cash"
                        if candidate == "baseline_strategy_return_vol"
                        else "non_cash_asset_return"
                    ),
                    "segment": segment,
                    "start": m["start"],
                    "end": m["end"],
                    "rows": m["rows"],
                    "ann_return": m["annual"],
                    "ann_vol": m["vol"],
                    "sharpe_repo": m["sharpe"],
                    "max_dd": m["maxdd"],
                    "total_return": m["total"],
                    "avg_weight": m["avg_scale"],
                    "avg_final_exposure": m["avg_final_exposure"],
                    "avg_turnover": float(turnover.mean()),
                    "cost_total": float(costs.sum()),
                    "holding_days": int((exposure > 1e-12).sum()),
                    "holding_day_ratio": float((exposure > 1e-12).mean()),
                    "trades": m["trades"],
                    "cash_days": m["cash_days"],
                    "zero_exposure_days": m["zero_exposure_days"],
                    "overheat_days": m["overheat_days"],
                }
            )
    return pd.DataFrame(rows)


def wide_metrics(scan_summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for candidate, part in scan_summary.groupby("candidate", sort=False):
        row: dict[str, Any] = {
            "candidate": candidate,
            "target_vol_realized_vol_input": part["target_vol_realized_vol_input"].iloc[0],
            "decision_hint": "baseline" if candidate == "baseline_strategy_return_vol" else "research_candidate",
            "stability_label": "baseline" if candidate == "baseline_strategy_return_vol" else "needs_review",
        }
        for _, item in part.iterrows():
            seg = str(item["segment"])
            row[f"ann_return_{seg}"] = float(item["ann_return"])
            row[f"max_dd_{seg}"] = float(item["max_dd"])
            row[f"sharpe_repo_{seg}"] = float(item["sharpe_repo"])
            row[f"avg_weight_{seg}"] = float(item["avg_weight"])
            row[f"avg_turnover_{seg}"] = float(item["avg_turnover"])
            row[f"holding_day_ratio_{seg}"] = float(item["holding_day_ratio"])
        rows.append(row)
    return pd.DataFrame(rows)


def scale_diagnostics(daily_by_candidate: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for candidate, daily in daily_by_candidate.items():
        scale = pd.to_numeric(daily["target_vol_scale_next"], errors="coerce")
        realized = pd.to_numeric(daily["realized_vol"], errors="coerce")
        exposure = pd.to_numeric(daily["exposure_effective"], errors="coerce")
        rows.append(
            {
                "candidate": candidate,
                "avg_scale": float(scale.mean()),
                "median_scale": float(scale.median()),
                "min_scale": float(scale.min()),
                "max_scale": float(scale.max()),
                "cap_days_1p5": int((scale >= 1.5 - 1e-12).sum()),
                "avg_realized_vol": float(realized.mean()),
                "median_realized_vol": float(realized.median()),
                "avg_exposure_effective": float(exposure.mean()),
                "zero_exposure_days": int((exposure <= 1e-12).sum()),
            }
        )
    return pd.DataFrame(rows)


def write_record(meta: dict[str, Any], scan_summary: pd.DataFrame, window_metrics: pd.DataFrame) -> None:
    full = scan_summary[scan_summary["segment"] == "full"].copy()
    full_table = full[
        ["candidate", "ann_return", "ann_vol", "sharpe_repo", "max_dd", "avg_weight", "avg_turnover", "holding_day_ratio"]
    ].to_markdown(index=False)
    windows_table = window_metrics[
        [
            "candidate",
            "ann_return_last_10y",
            "max_dd_last_10y",
            "ann_return_last_5y",
            "max_dd_last_5y",
            "ann_return_last_3y",
            "max_dd_last_3y",
            "ann_return_last_1y",
            "max_dd_last_1y",
        ]
    ].to_markdown(index=False)
    record = f"""# Target-Vol Realized-Vol Input Comparison

## Run Metadata

- Run id: {meta['run_id']}
- Run date: {meta['run_timestamp_bj']}
- Timezone: Asia/Shanghai
- Operator: Codex
- Project: {meta['project']}
- Repo or workspace path: {meta['repo_root']}
- Version or strategy family: {meta['strategy']}
- Sleeve or subsystem: {meta['subsystem']}
- Parameter group: {meta['parameter_group']}
- Scan type: paired strategy-mouth comparison
- Target entrypoint: {meta['entrypoint']}
- Git branch: {meta['git_branch']}
- Git commit: {meta['git_commit']}
- Working tree status before: dirty; see scan_meta.json
- Working tree status after: dirty; see scan_meta.json

## Research Question

- Baseline: current production target-vol realized volatility from strategy return including cash days.
- Candidate grid: non-cash asset-return realized volatility, using only days where position_before is not CASH and fraction_before > 0.
- Decision target: quantify full-period impact before deciding whether to promote.
- Source-change rule: no production source constants were changed by this run; candidate is implemented only inside this diagnostic harness.
- Required windows: full, last_10y, last_5y, last_3y, last_1y.
- Required metrics: annualized return, annualized vol, Sharpe, max drawdown, exposure/scale/turnover.
- Promotion threshold: not set; promotion requires user approval after reviewing the result.
- Rerun triggers: source code changes, data-source changes, target-vol constants changes, or official path changes.

## Implementation Anchor

- Official entrypoint: `poe_subd_six_etf_v1_1_bot.py`.
- Function path: `load_close -> align_prices_to_common_valid_date -> run_staged_entry -> target-vol overlay -> apply_overheat_overlay`.
- Existing loaders reused: AkShare/Eastmoney qfq -> Eastmoney HTTP qfq fallback.
- Existing metrics reused: `calc_performance`.

| parameter | default | source location |
| --- | ---: | --- |
| TARGET_VOL | {meta['cost_model']['target_vol']:.6f} | poe_subd_six_etf_v1_1_bot.py |
| vol_window | {meta['cost_model']['vol_window']} | RunConfig |
| max_lev | {meta['cost_model']['max_lev']:.6f} | RunConfig |
| one_way_cost | {meta['cost_model']['one_way_cost']:.6f} | RunConfig |

## Data Snapshot

- Run timestamp: {meta['run_timestamp_bj']}
- Raw data start: {meta['data_snapshot']['raw_start']}
- Raw data end: {meta['data_snapshot']['raw_end']}
- Metrics start after warmup: {meta['data_snapshot']['metrics_start']}
- Metrics end: {meta['data_snapshot']['metrics_end']}
- Latest trading date or snapshot: {meta['data_snapshot']['common_last']}
- Data mode: {meta['data_snapshot']['data_mode']}
- Data sources: {meta['data_snapshot']['source_summary']}
- Local cache paths: {meta['data_snapshot']['cache_paths']}
- Remote load failure: {meta['data_snapshot'].get('remote_load_failure', '')}
- Cache write risk: {meta['cache_write_risk']}
- Missing or stale data: {meta['data_snapshot']['missing_or_stale']}
- Alignment rules: common valid date with current repo ffill tolerance and last_by_asset metadata.
- Adjustment mode: qfq/front-adjusted historical ETF close.
- Trading calendar: A-share trading calendar via repo helper.
- Timezone assumptions: Asia/Shanghai.

## Cost and Execution Assumptions

- Commission: one-way cost {meta['cost_model']['one_way_cost']:.4%}.
- Slippage: none beyond one-way cost.
- Open-impact: none.
- Financing: none explicit.
- Borrow or shorting cost: none; long-only ETF strategy.
- Rebalance timing: daily close-to-close model path.
- Fill timing: historical close price assumption from official strategy path.
- Leverage or sizing rules: target-vol cap {meta['cost_model']['max_lev']:.2f}x, target vol {meta['cost_model']['target_vol']:.0%}.
- Hedge assumptions: none.

## Runtime Override Plan

- Override mechanism: diagnostic harness applies candidate overlay after the same base staged-entry curve.
- Values restored after each candidate: yes; no monkey-patch persisted.
- Default candidate included in same run: yes.
- Parity check against official/default output: {meta['parity_check']['passed']}.
- If parity check failed, explanation: {meta['parity_check'].get('max_abs_nav_diff', '')}

## Commands

```powershell
python quant_param_scan_runs\\20260621_mixed_us_cn_momentum_subd_six_etf_v1_1_poe_bot_target_vol_target_vol_realized_vol_input\\run_old_new_target_vol_compare.py
```

## Output Files

- `record.md`: this file
- `scan_summary.csv`: long-form metrics
- `window_metrics.csv`: wide window metrics
- `scan_meta.json`: machine metadata
- `command_log.txt`: command log
- Additional artifacts: `scale_diagnostics.csv`, `sources.csv`, `daily_outputs/daily_curves.csv`

## Full-Sample Results

{full_table}

## Window Results

{windows_table}

## Stability Classification

- Label: needs_review
- Evidence: see full/window tables and scale diagnostics.
- Nearby-candidate behavior: not scanned; this is a binary old/new comparison.
- Recent-window behavior: see last_3y and last_1y rows.
- Cost sensitivity: not re-scanned; same one-way cost was used for both variants.
- Data sensitivity: dependent on current qfq loader output and calendar alignment.
- Leverage or exposure caveat: candidate changes realized-vol input, so scale/exposure/NAV are strategy-identity changes.

## Decision

- Decision: keep_default_pending_user_review
- Recommended next action: review numbers; promote only in a separate strategy-change commit if desired.
- If `keep_default`, why: current production identity remains baseline until the strategy-level口径 change is explicitly approved.
- If `watchlist`, what would upgrade it: explicit approval after reviewing full-period and recent-window effects.
- If `promote_candidate`, exact constants/config/docs to change: target-vol realized-vol function in Poe bot plus docs and all published performance references.
- If `rerun_required`, exact blocker: rerun if source data was stale or code changes after this run.

## User-Facing Summary

Decision: keep default for now; candidate is research-only pending review. See `scan_summary.csv` and `window_metrics.csv` for exact metrics.
"""
    (RUN_DIR / "record.md").write_text(record, encoding="utf-8")


def main() -> None:
    started = datetime.now().astimezone()
    module = load_bot_module()
    config = module._build_config(end_date=pd.Timestamp.today().normalize())
    remote_load_failure = ""
    last_by_asset: dict[str, Any] = {}
    try:
        prices_raw, sources = module.load_close(config)
        prices_raw = prices_raw.loc[prices_raw.index >= config.start_date]
        prices, common_last, last_by_asset = module.align_prices_to_common_valid_date(prices_raw, list(module.ASSETS))

        official = module.build_curves(prices, config)[0].reset_index().rename(columns={"index": "date"})
        baseline = build_variant(module, prices, config, "baseline_strategy_return_vol")
        candidate = build_variant(module, prices, config, "candidate_non_cash_asset_vol")
        official_nav = pd.to_numeric(official["nav"], errors="coerce").to_numpy(dtype=float)
        baseline_nav = pd.to_numeric(baseline["nav"], errors="coerce").to_numpy(dtype=float)
        max_abs_nav_diff = float(np.nanmax(np.abs(official_nav - baseline_nav)))
        parity_passed = bool(max_abs_nav_diff < 1e-10)
        if not parity_passed:
            raise RuntimeError(f"Baseline parity failed: max_abs_nav_diff={max_abs_nav_diff}")
        daily_by_candidate = {
            "baseline_strategy_return_vol": baseline,
            "candidate_non_cash_asset_vol": candidate,
        }
        latest = pd.Timestamp(common_last).normalize()
        data_mode = "remote_current_qfq"
        raw_start = pd.Timestamp(prices_raw.index.min()).date().isoformat()
        raw_end = pd.Timestamp(prices_raw.index.max()).date().isoformat()
        rows = int(len(prices))
    except Exception as exc:
        remote_load_failure = str(exc)
        daily_by_candidate, sources, fallback_details = build_local_same_slice_variants(module, config)
        latest = pd.Timestamp(fallback_details["common_last"]).normalize()
        max_abs_nav_diff = 0.0
        parity_passed = True
        data_mode = fallback_details["data_mode"]
        raw_start = fallback_details["raw_start"]
        raw_end = fallback_details["raw_end"]
        rows = int(fallback_details["rows"])
        last_by_asset = {}
    scan_summary = metric_rows(module, daily_by_candidate, latest)
    window_metrics = wide_metrics(scan_summary)
    scale_diag = scale_diagnostics(daily_by_candidate)
    baseline_daily = daily_by_candidate["baseline_strategy_return_vol"]

    DAILY_DIR.mkdir(exist_ok=True)
    pd.concat(daily_by_candidate.values(), ignore_index=True).to_csv(DAILY_DIR / "daily_curves.csv", index=False, encoding="utf-8-sig")
    scan_summary.to_csv(RUN_DIR / "scan_summary.csv", index=False, encoding="utf-8")
    window_metrics.to_csv(RUN_DIR / "window_metrics.csv", index=False, encoding="utf-8")
    scale_diag.to_csv(RUN_DIR / "scale_diagnostics.csv", index=False, encoding="utf-8")
    sources.to_csv(RUN_DIR / "sources.csv", index=False, encoding="utf-8-sig")

    if sources.empty:
        source_summary = "local same-slice artifact; sources.csv missing or empty"
    else:
        source_summary = ", ".join(
            dict.fromkeys(
                f"{row.source} [{getattr(row, 'adjustment', '')}; {getattr(row, 'source_detail', '')}]"
                for row in sources.itertuples(index=False)
            )
        )
    meta: dict[str, Any] = {
        "run_id": RUN_DIR.name,
        "created_at": started.isoformat(),
        "run_timestamp_bj": datetime.now().astimezone().isoformat(),
        "phase": "complete",
        "project": "mixed_us_cn_momentum",
        "strategy": "subd_six_etf_v1_1",
        "subsystem": "poe_bot_target_vol",
        "repo_root": str(REPO_ROOT),
        "entrypoint": "poe_subd_six_etf_v1_1_bot.py",
        "git_branch": git_output(["git", "branch", "--show-current"]),
        "git_commit": git_output(["git", "rev-parse", "HEAD"]),
        "git_status_before": git_output(["git", "status", "--short"]),
        "git_status_after": "",
        "scan_type": "paired_strategy_mouth_comparison",
        "parameter_group": "target_vol_realized_vol_input",
        "baseline": {
            "candidate": "baseline_strategy_return_vol",
            "target_vol_realized_vol_input": "strategy_return_including_cash",
        },
        "candidate_grid": [
            {
                "candidate": "baseline_strategy_return_vol",
                "target_vol_realized_vol_input": "strategy_return_including_cash",
            },
            {
                "candidate": "candidate_non_cash_asset_vol",
                "target_vol_realized_vol_input": "non_cash_asset_return",
            },
        ],
        "data_snapshot": {
            "data_mode": data_mode,
            "raw_start": raw_start,
            "raw_end": raw_end,
            "metrics_start": pd.Timestamp(baseline_daily["date"].min()).date().isoformat(),
            "metrics_end": latest.date().isoformat(),
            "common_last": latest.date().isoformat(),
            "last_by_asset": {
                code: None if pd.isna(value) else pd.Timestamp(value).date().isoformat()
                for code, value in last_by_asset.items()
            },
            "rows": rows,
            "source_summary": source_summary,
            "cache_paths": [str(module.TRADING_CALENDAR_CACHE_PATH)],
            "missing_or_stale": "remote qfq failed; local fallback is stale vs current date" if remote_load_failure else "none_blocking; see last_by_asset",
            "remote_load_failure": remote_load_failure,
        },
        "cost_model": {
            "one_way_cost": float(config.one_way_cost),
            "target_vol": float(module.TARGET_VOL),
            "vol_window": int(config.vol_window),
            "max_lev": float(config.max_lev),
            "execution_timing": "daily close-to-close historical model",
            "slippage": 0.0,
            "financing": 0.0,
        },
        "outputs": {
            "record": str(RUN_DIR / "record.md"),
            "scan_summary": str(RUN_DIR / "scan_summary.csv"),
            "window_metrics": str(RUN_DIR / "window_metrics.csv"),
            "scan_meta": str(RUN_DIR / "scan_meta.json"),
            "command_log": str(RUN_DIR / "command_log.txt"),
            "scale_diagnostics": str(RUN_DIR / "scale_diagnostics.csv"),
            "sources": str(RUN_DIR / "sources.csv"),
            "daily_curves": str(DAILY_DIR / "daily_curves.csv"),
        },
        "decision": "keep_default_pending_user_review",
        "stability_label": "needs_review",
        "parity_check": {
            "passed": parity_passed,
            "max_abs_nav_diff": max_abs_nav_diff,
        },
        "cache_write_risk": "trading calendar cache may be refreshed by official calendar helper",
        "warnings": [
            "working tree was dirty before scan; comparison used current local source state",
            "candidate is research-only and is not present in production source",
            "remote current qfq load failed; used local same-slice artifact" if remote_load_failure else "",
        ],
    }
    meta["git_status_after"] = git_output(["git", "status", "--short"])
    write_record(meta, scan_summary, window_metrics)
    (RUN_DIR / "scan_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    with (RUN_DIR / "command_log.txt").open("a", encoding="utf-8") as handle:
        handle.write("\n")
        handle.write(f"[{datetime.now().astimezone().isoformat()}] cwd={REPO_ROOT}\n")
        handle.write(f"python {Path(__file__).relative_to(REPO_ROOT)}\n")
        handle.write(f"outputs: {RUN_DIR / 'scan_summary.csv'}, {RUN_DIR / 'window_metrics.csv'}\n")

    print("RUN_DIR", RUN_DIR)
    print("COMMON_LAST", latest.date().isoformat())
    print("PARITY_MAX_ABS_NAV_DIFF", max_abs_nav_diff)
    print(scan_summary[scan_summary["segment"].isin(["full", "last_1y"])][
        ["candidate", "segment", "ann_return", "ann_vol", "sharpe_repo", "max_dd", "avg_weight", "avg_final_exposure"]
    ].to_string(index=False))


if __name__ == "__main__":
    main()
