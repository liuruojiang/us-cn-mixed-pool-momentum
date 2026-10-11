"""Render the formal R²-on recency-weight scan and record provenance."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[1]
POWERS = [i / 2 for i in range(11)]
SEGMENTS = (("full", "全样本"), ("last_10y", "近10年"),
            ("last_5y", "近5年"), ("last_3y", "近3年"), ("last_1y", "近1年"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pair(row, segment):
    return f"{row[f'ann_return_{segment}']:.2%} / {row[f'max_dd_{segment}']:.2%}"


def main():
    wide = pd.read_csv(RUN / "window_metrics.csv").sort_values("WEIGHT_POWER")
    long = pd.read_csv(RUN / "scan_summary.csv")
    if wide.WEIGHT_POWER.tolist() != POWERS or len(long) != len(POWERS) * 6:
        raise RuntimeError("Incomplete grid or result rows")
    base = wide.loc[wide.WEIGHT_POWER == 1].iloc[0]
    full_best = wide.loc[wide.ann_return_full.idxmax()]
    common_best = wide.loc[wide.ann_return_six_etf_all_scoreable.idxmax()]
    year_best = wide.loc[wide.ann_return_last_1y.idxmax()]

    lines = ["# 六 ETF 正式 V1.3：时间权重指数 p=0～5，步长 0.5", "",
             "保留 25 日窗口、严格 `0.5<Score<5.5` 和 **R²≥0.25**，仅改变回归时间权重 `w_t=t^p`。价格截至 2026-09-24；每格为年化净收益 / 最大回撤。", "",
             "| 权重指数 p | 全样本 | 近10年 | 近5年 | 近3年 | 近1年 |",
             "|---:|---:|---:|---:|---:|---:|"]
    for _, row in wide.iterrows():
        label = "**1.0（正式）**" if row.WEIGHT_POWER == 1 else f"{row.WEIGHT_POWER:.1f}"
        lines.append("| " + " | ".join([label] + [pair(row, s) for s, _ in SEGMENTS]) + " |")
    lines += ["", "## 六只 ETF 均可计算 25 日 Score 的共同区间", "",
              "2020-01-09 至 2026-09-24。", "",
              "| 权重指数 p | 年化净收益 | 最大回撤 |", "|---:|---:|---:|"]
    for _, row in wide.iterrows():
        label = "**1.0（正式）**" if row.WEIGHT_POWER == 1 else f"{row.WEIGHT_POWER:.1f}"
        lines.append(f"| {label} | {row.ann_return_six_etf_all_scoreable:.2%} | {row.max_dd_six_etf_all_scoreable:.2%} |")
    lines += ["", "完整精度、成本、换手和逐日账户见 `scan_summary.csv`、`window_metrics.csv`、`daily_outputs/`。", ""]
    (RUN / "result_tables.md").write_text("\n".join(lines), encoding="utf-8")

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True, constrained_layout=True)
    for segment, label, color in (("full", "Full", "#1d4ed8"),
                                   ("last_10y", "10Y", "#0891b2"),
                                   ("last_5y", "5Y", "#16a34a"),
                                   ("last_3y", "3Y", "#ea580c"),
                                   ("last_1y", "1Y", "#9333ea")):
        axes[0].plot(wide.WEIGHT_POWER, wide[f"ann_return_{segment}"] * 100, label=label, color=color)
        axes[1].plot(wide.WEIGHT_POWER, wide[f"max_dd_{segment}"] * 100, label=label, color=color)
    for ax in axes:
        ax.axvline(1, color="black", linestyle="--", linewidth=1)
        ax.grid(alpha=.25)
    axes[0].set_ylabel("Annualized net return (%)")
    axes[1].set_ylabel("Max drawdown (%)")
    axes[1].set_xlabel("Weight power p; formal = 1.0, R2 gate active")
    axes[1].set_xticks(POWERS)
    axes[0].legend(ncol=5)
    fig.savefig(RUN / "weight_power_scan.png", dpi=150)
    plt.close(fig)

    meta_path = RUN / "scan_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    price = ROOT / "outputs/recert_l1_20260926/prices_aligned_qfq_through_20260924.csv.gz"
    flags = ROOT / "outputs/recert_l1_20260926/price_ffill_flags_through_20260924.csv.gz"
    meta.update(
        scan_type="single_parameter", parameter_group="WEIGHT_POWER",
        candidate_grid=POWERS,
        baseline={"formal_weight_power": 1.0, "other_parameters": "LOOKBACK=25; strict 0.5<Score<5.5; R2>=0.25; Buffer=1; Top1 full entry or cash"},
        data_snapshot={"price_path": str(price.relative_to(ROOT)), "price_sha256": sha(price),
                       "flags_path": str(flags.relative_to(ROOT)), "flags_sha256": sha(flags),
                       "source": "L1 formal-loader capture; Tencent-labelled front-adjusted close",
                       "start": "2011-12-09", "end": "2026-09-24", "rows": 3594,
                       "all_25d_scoreable_start": "2020-01-09", "timezone": "Asia/Shanghai"},
        cost_model={"one_way_cost": 0.001, "cash_yield": 0, "max_leverage": 1,
                    "execution": "T-close signal and hypothetical same-T-close fill; paper account"},
        source_hashes={"formal_code_sha256": sha(ROOT / "poe_subd_six_etf_v1_3_bot.py"),
                       "runner_sha256": sha(RUN / "run_scan.py"),
                       "l6_score_helper_sha256": sha(ROOT / "quant_param_scan_runs/20260926_six_etf_v1_3_l6_parameter_basis_20260924/run_l6_scan.py"),
                       "audit_results_sha256": sha(RUN / "audit_results.py"),
                       "audit_signals_sha256": sha(RUN / "audit_signals.py")},
        parity_check="p=1 formal vs L2 and p=0 vs L8; independent NAV metric and Score/R2/Top1 signal audits",
        cache_write_risk="Read-only L1 prices/flags; in-memory scoring function override restored after each candidate; writes only this run directory",
        warnings=["Frozen cutoff 2026-09-24; later market dates excluded", "Full sample adds ETFs as listed",
                  "Trailing windows overlap and are in-sample", "Same-close fill is a paper assumption"],
    )
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    record = ["# 六 ETF V1.3：正式条件下权重指数 p=0～5 扫描", "",
              "## Run Metadata", "", f"- Run id: `{RUN.name}`", "- Research-only single-parameter scan.", "- Git state: `scan_meta.json`.", "",
              "## Research Question", "", "- Grid: p=0, 0.5, ..., 5.0. Formal p=1.0 is included in the same run.",
              "- Only time-weight exponent changes: `w_t=t^p` for t=1..25 from oldest to newest. Keep R²≥0.25 active, along with LOOKBACK=25 and strict Score bounds.",
              "- Source-change rule: `research_only_no_source_change`; no formal strategy or provider file edited.", "",
              "## Implementation Anchor", "", "- Official `poe_subd_six_etf_v1_3_bot.py` account engine, with the existing L6 weighted-regression helper used only to supply candidate p Scores and R² values.",
              "- The p=1 candidate invokes the original formal scoring function; p≠1 functions are swapped in memory and restored after each run.", "",
              "## Data Snapshot", "", "- L1 front-adjusted saved panel and forward-fill flags, 2011-12-09 to 2026-09-24, 3,594 China ETF sessions; hashes in `scan_meta.json`.",
              "- All six ETFs can form a 25-day Score from 2020-01-09. Before then Full/10Y dynamically add listed assets.",
              "- Two flagged filled asset-days cannot be traded. No provider refresh or cache write.", "",
              "## Cost and Execution Assumptions", "", "- Single ETF or cash, no leverage/financing, cash yield 0; each buy/sell leg costs an assumed 0.10% including slippage.",
              "- Old holding receives T close-to-close return; T close signal hypothetically fills at same close. ETF premium, capacity and actual fill are unverified.",
              "- Each trailing window uses first NAV as base and N−1 NAV changes for annualization.", "",
              "## Runtime Override Plan", "", "- p=1 must match L2 formal and p=0 must bridge to L8 before interpreting candidates.",
              "- Independently recompute all 11×6 NAV metric pairs and 11×3,594 Score/R²/Top1 candidate-days.", "",
              "## Commands", "", "```powershell",
              f"python -X utf8 quant_param_scan_runs/{RUN.name}/run_scan.py",
              f"python -X utf8 quant_param_scan_runs/{RUN.name}/audit_results.py",
              f"python -X utf8 quant_param_scan_runs/{RUN.name}/audit_signals.py",
              f"python -X utf8 quant_param_scan_runs/{RUN.name}/build_report.py", "```", "",
              "## Output Files", "", "- `scan_summary.csv`, `window_metrics.csv`, `daily_outputs/`, `parity_checks.json`, `signal_audit.json`, `result_tables.md`, `weight_power_scan.png`, `scan_meta.json`, `command_log.txt`.", "",
              "## Full-Sample Results", "", f"- Formal p=1: {pair(base, 'full')}; common period {base.ann_return_six_etf_all_scoreable:.2%} / {base.max_dd_six_etf_all_scoreable:.2%}.",
              f"- Full return peak: p={full_best.WEIGHT_POWER:g}, {pair(full_best, 'full')}; common-period peak: p={common_best.WEIGHT_POWER:g}, {common_best.ann_return_six_etf_all_scoreable:.2%} / {common_best.max_dd_six_etf_all_scoreable:.2%}.", "",
              "## Window Results", "", "- All 11 paths across five required windows and common period: `result_tables.md`.",
              f"- Highest trailing 1Y return: p={year_best.WEIGHT_POWER:g}, {pair(year_best, 'last_1y')}.", "",
              "## Stability Classification", "", "- Complete after validation; windows overlap and no independent holdout is included.", "",
              "## Decision", "", "- Complete after validation; research results do not change formal parameters.", "",
              "## User-Facing Summary", "", "- This run keeps R² active throughout and varies only the time-weight exponent.", ""]
    (RUN / "record.md").write_text("\n".join(record), encoding="utf-8")
    with (RUN / "command_log.txt").open("a", encoding="utf-8") as log:
        log.write(f"\n[{datetime.now(timezone(timedelta(hours=8))).isoformat()}] cwd={ROOT}\n")
        for name in ("run_scan.py", "audit_results.py", "audit_signals.py", "build_report.py"):
            log.write(f"python -X utf8 quant_param_scan_runs/{RUN.name}/{name}\n")
        log.write("No provider request or cache mutation; no output-affecting environment variables.\n")
    print(f"Report ready: Full best p={full_best.WEIGHT_POWER:g}, common best p={common_best.WEIGHT_POWER:g}, 1Y best p={year_best.WEIGHT_POWER:g}")


if __name__ == "__main__":
    main()
