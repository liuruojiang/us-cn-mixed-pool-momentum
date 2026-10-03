"""Build readable R²-threshold grid tables, plot, and provenance record."""

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
GRID = [i / 20 for i in range(41)]
SEGMENTS = (("full", "全样本"), ("last_10y", "近10年"),
            ("last_5y", "近5年"), ("last_3y", "近3年"), ("last_1y", "近1年"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pair(row, segment):
    return f"{row[f'ann_return_{segment}']:.2%} / {row[f'max_dd_{segment}']:.2%}"


def main():
    wide = pd.read_csv(RUN / "window_metrics.csv").sort_values("R2_THRESHOLD")
    long = pd.read_csv(RUN / "scan_summary.csv")
    if wide.R2_THRESHOLD.tolist() != GRID or len(long) != len(GRID) * 6:
        raise RuntimeError("Incomplete grid or result rows")
    base = wide.loc[wide.R2_THRESHOLD == .25].iloc[0]
    full_best = wide.loc[wide.ann_return_full.idxmax()]
    common_best = wide.loc[wide.ann_return_six_etf_all_scoreable.idxmax()]
    year_best = wide.loc[wide.ann_return_last_1y.idxmax()]
    cash_only = wide.loc[wide.trade_days_full == 0, "R2_THRESHOLD"].tolist()
    parity = json.loads((RUN / "parity_checks.json").read_text(encoding="utf-8"))

    lines = ["# 六 ETF V1.3：R²门槛 0～2，步长 0.05", "",
             "固定 25 日、p=1、严格 `0.5<Score<5.5`、Top1 和账户规则，只改变同一回归的 R²入选下限。价格截至 2026-09-24。每格为年化净收益 / 最大回撤。", "",
             "| R²门槛 | 全样本 | 近10年 | 近5年 | 近3年 | 近1年 |",
             "|---:|---:|---:|---:|---:|---:|"]
    for _, row in wide.iterrows():
        label = "**0.25（正式）**" if row.R2_THRESHOLD == .25 else f"{row.R2_THRESHOLD:.2f}"
        lines.append("| " + " | ".join([label] + [pair(row, s) for s, _ in SEGMENTS]) + " |")
    lines += ["", "## 六只 ETF 均可计算 25 日 Score 的共同区间", "",
              "2020-01-09 至 2026-09-24。", "",
              "| R²门槛 | 年化净收益 | 最大回撤 |", "|---:|---:|---:|"]
    for _, row in wide.iterrows():
        label = "**0.25（正式）**" if row.R2_THRESHOLD == .25 else f"{row.R2_THRESHOLD:.2f}"
        lines.append(f"| {label} | {row.ann_return_six_etf_all_scoreable:.2%} | {row.max_dd_six_etf_all_scoreable:.2%} |")
    lines += ["", "没有交易的全现金路径收益和回撤均为 0；其波动率为 0，Sharpe 无定义。机读表中的 `sharpe_repo=0` 仅为严格数值格式占位，`sharpe_defined=False` 标识真实含义。", "",
              "完整精度、成本、换手和逐日账户见 `scan_summary.csv`、`window_metrics.csv`、`daily_outputs/`。", ""]
    (RUN / "result_tables.md").write_text("\n".join(lines), encoding="utf-8")

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True, constrained_layout=True)
    for segment, label, color in (("full", "Full", "#1d4ed8"),
                                   ("last_10y", "10Y", "#0891b2"),
                                   ("last_5y", "5Y", "#16a34a"),
                                   ("last_3y", "3Y", "#ea580c"),
                                   ("last_1y", "1Y", "#9333ea")):
        axes[0].plot(wide.R2_THRESHOLD, wide[f"ann_return_{segment}"] * 100, label=label, color=color)
        axes[1].plot(wide.R2_THRESHOLD, wide[f"max_dd_{segment}"] * 100, label=label, color=color)
    for ax in axes:
        ax.axvline(.25, color="black", linestyle="--", linewidth=1)
        ax.axvspan(1.0, 2.0, color="gray", alpha=.08)
        ax.grid(alpha=.25)
    axes[0].set_ylabel("Annualized net return (%)")
    axes[1].set_ylabel("Max drawdown (%)")
    axes[1].set_xlabel("R2 eligibility threshold; formal = 0.25")
    axes[1].set_xticks([i / 4 for i in range(9)])
    axes[0].legend(ncol=5)
    fig.savefig(RUN / "r2_threshold_scan.png", dpi=150)
    plt.close(fig)

    meta_path = RUN / "scan_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    price = ROOT / "outputs/recert_l1_20260926/prices_aligned_qfq_through_20260924.csv.gz"
    flags = ROOT / "outputs/recert_l1_20260926/price_ffill_flags_through_20260924.csv.gz"
    meta.update(
        scan_type="single_parameter", parameter_group="R2_THRESHOLD", candidate_grid=GRID,
        baseline={"formal_R2_THRESHOLD": .25,
                  "other_parameters": "LOOKBACK=25; weight p=1; strict 0.5<Score<5.5; Buffer=1; Top1 full entry or cash"},
        data_snapshot={"price_path": str(price.relative_to(ROOT)), "price_sha256": sha(price),
                       "flags_path": str(flags.relative_to(ROOT)), "flags_sha256": sha(flags),
                       "source": "L1 formal-loader capture; Tencent-labelled front-adjusted close",
                       "start": "2011-12-09", "end": "2026-09-24", "rows": 3594,
                       "all_25d_scoreable_start": "2020-01-09", "timezone": "Asia/Shanghai"},
        cost_model={"one_way_cost": .001, "cash_yield": 0, "max_leverage": 1,
                    "execution": "T-close signal and hypothetical same-T-close fill; paper account"},
        source_hashes={"formal_code_sha256": sha(ROOT / "poe_subd_six_etf_v1_3_bot.py"),
                       "runner_sha256": sha(RUN / "run_scan.py"),
                       "audit_results_sha256": sha(RUN / "audit_results.py"),
                       "audit_signals_sha256": sha(RUN / "audit_signals.py")},
        parity_check="formal 0.25 vs L2; threshold zero vs L4 R2-off; independent NAV and Top1 signal audits",
        cash_only_thresholds=cash_only,
        max_observed_weighted_r2=parity["max_observed_weighted_r2"],
        zero_vol_sharpe_policy="sharpe_repo numeric 0 is a schema placeholder only where sharpe_defined=False; true Sharpe is undefined",
        cache_write_risk="Read-only L1 prices and flags; pass R2 threshold to formal account engine without source edit; writes only this run directory",
        warnings=["Frozen cutoff 2026-09-24; later market dates excluded", "Full sample adds ETFs as listed",
                  "Trailing windows overlap and are in-sample", "Same-close fill is a paper assumption"],
    )
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    record = ["# 六 ETF V1.3：R²门槛 0～2 扫描", "",
              "## Run Metadata", "", f"- Run id: `{RUN.name}`", "- Research-only single-parameter scan.", "- Git state: `scan_meta.json`.", "",
              "## Research Question", "", "- Grid: R² threshold 0, 0.05, ..., 2.00. Formal 0.25 is included in the same run.",
              "- Only R² eligibility lower bound changes; LOOKBACK=25, weight p=1, strict Score bounds, Top1 and account rules fixed.",
              "- Score and R² come from the same weighted regression. Mathematically R²≤1, so >1 is an intentionally included cash-only boundary region.",
              "- Source-change rule: `research_only_no_source_change`; no formal strategy or provider file edited.", "",
              "## Implementation Anchor", "", "- Official `poe_subd_six_etf_v1_3_bot.py` scoring/account engine receives each R² threshold as a runtime argument; no global parameter or source edit.",
              "- The zero-threshold path bridges to the prior R²-off audit because valid weighted R² values are clamped at zero.", "",
              "## Data Snapshot", "", "- L1 front-adjusted saved panel and forward-fill flags, 2011-12-09 to 2026-09-24, 3,594 China ETF sessions; hashes in `scan_meta.json`.",
              "- Six-ETF common 25-day scoreable start: 2020-01-09; earlier Full/10Y dynamically add listed assets.",
              "- Two flagged filled asset-days cannot be traded. No provider refresh or cache write.", "",
              "## Cost and Execution Assumptions", "", "- Single ETF or cash; no leverage/financing; cash yield 0; each buy/sell leg has assumed 0.10% fee/slippage.",
              "- T close signal hypothetically fills at T close, after old holding receives that day's close-to-close return. ETF premium, capacity and actual fill are unverified.",
              "- Trailing windows use first NAV as base and N−1 NAV changes for annualization.",
              "- Cash-only paths have zero volatility and undefined Sharpe. Strict artifact format stores 0 only as a placeholder with `sharpe_defined=False`; this is not a measured Sharpe of zero.", "",
              "## Runtime Override Plan", "", "- Formal 0.25 path must match L2; 0 path must match L4 R²-off. Independent audits recompute all 41×6 NAV windows and all 41×3,594 Top1 candidate-days.", "",
              "## Commands", "", "```powershell",
              f"python -X utf8 quant_param_scan_runs/{RUN.name}/run_scan.py",
              f"python -X utf8 quant_param_scan_runs/{RUN.name}/audit_results.py",
              f"python -X utf8 quant_param_scan_runs/{RUN.name}/audit_signals.py",
              f"python -X utf8 quant_param_scan_runs/{RUN.name}/build_report.py", "```", "",
              "## Output Files", "", "- `scan_summary.csv`, `window_metrics.csv`, `daily_outputs/`, `parity_checks.json`, `signal_audit.json`, `result_tables.md`, `r2_threshold_scan.png`, `scan_meta.json`, `command_log.txt`.", "",
              "## Full-Sample Results", "", f"- Formal 0.25: {pair(base, 'full')}; zero threshold: {pair(wide.iloc[0], 'full')}.",
              f"- Full return peak: threshold {full_best.R2_THRESHOLD:.2f}, {pair(full_best, 'full')}; common-period peak: {common_best.R2_THRESHOLD:.2f}, {common_best.ann_return_six_etf_all_scoreable:.2%} / {common_best.max_dd_six_etf_all_scoreable:.2%}.",
              f"- First all-cash threshold in this grid: {min(cash_only):.2f}; observed maximum weighted R²: {parity['max_observed_weighted_r2']:.8f}.", "",
              "## Window Results", "", "- All 41 paths across five required windows and common period: `result_tables.md`.",
              f"- Highest trailing 1Y return: threshold {year_best.R2_THRESHOLD:.2f}, {pair(year_best, 'last_1y')}.", "",
              "## Stability Classification", "", "- Complete after validation; windows overlap and no independent holdout is included.", "",
              "## Decision", "", "- Complete after validation; research results do not change formal parameters.", "",
              "## User-Facing Summary", "", "- Thresholds above 1 necessarily produce cash-only paths; substantive economic comparison lies below 1.", ""]
    (RUN / "record.md").write_text("\n".join(record), encoding="utf-8")
    with (RUN / "command_log.txt").open("a", encoding="utf-8") as log:
        log.write(f"\n[{datetime.now(timezone(timedelta(hours=8))).isoformat()}] cwd={ROOT}\n")
        for name in ("run_scan.py", "audit_results.py", "audit_signals.py", "build_report.py"):
            log.write(f"python -X utf8 quant_param_scan_runs/{RUN.name}/{name}\n")
        log.write("No provider request or cache mutation; no output-affecting environment variables.\n")
    print(f"Report ready: Full best {full_best.R2_THRESHOLD:.2f}, common best {common_best.R2_THRESHOLD:.2f}, 1Y best {year_best.R2_THRESHOLD:.2f}")


if __name__ == "__main__":
    main()
