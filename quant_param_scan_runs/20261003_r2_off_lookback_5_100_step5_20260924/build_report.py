"""Build readable six-window tables, chart, and audit metadata."""

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
GRID = list(range(5, 101, 5))
SEGMENTS = (("full", "全样本"), ("last_10y", "近10年"),
            ("last_5y", "近5年"), ("last_3y", "近3年"), ("last_1y", "近1年"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pair(row, segment):
    return f"{row[f'ann_return_{segment}']:.2%} / {row[f'max_dd_{segment}']:.2%}"


def main():
    wide = pd.read_csv(RUN / "window_metrics.csv")
    long = pd.read_csv(RUN / "scan_summary.csv")
    off = wide.loc[wide.role != "formal_reference"].sort_values("LOOKBACK")
    if off.LOOKBACK.tolist() != GRID or len(wide) != 21 or len(long) != 21 * 6:
        raise RuntimeError("Incomplete grid or result rows")
    formal = wide.loc[wide.candidate == "formal_25_r2_on"].iloc[0]
    off25 = wide.loc[wide.candidate == "r2_off_25"].iloc[0]
    full_best = off.loc[off.ann_return_full.idxmax()]
    common_best = off.loc[off.ann_return_six_etf_all_scoreable.idxmax()]
    year_best = off.loc[off.ann_return_last_1y.idxmax()]

    lines = ["# 六 ETF V1.3：仅关闭 R² 后的回看窗口扫描", "",
             "冻结 p=1、严格 `0.5<Score<5.5`、Top1、费用和纸面同收盘时钟；只把 R² 资格门槛设为关闭并扫 LOOKBACK。价格截至 2026-09-24。每格为年化净收益 / 最大回撤。", "",
             "| 回看日数 | 全样本 | 近10年 | 近5年 | 近3年 | 近1年 |",
             "|---:|---:|---:|---:|---:|---:|"]
    lines.append("| **25（正式，R²开启）** | " + " | ".join(pair(formal, s) for s, _ in SEGMENTS) + " |")
    for _, row in off.iterrows():
        label = "**25（R²关闭）**" if row.LOOKBACK == 25 else str(int(row.LOOKBACK))
        lines.append("| " + " | ".join([label] + [pair(row, s) for s, _ in SEGMENTS]) + " |")
    lines += ["", "## 六只 ETF 均可计算 100 日 Score 的共同区间", "",
              "2020-05-07 至 2026-09-24。", "",
              "| 回看日数 | 年化净收益 | 最大回撤 |", "|---:|---:|---:|"]
    lines.append(f"| **25（正式，R²开启）** | {formal.ann_return_six_etf_all_scoreable:.2%} | {formal.max_dd_six_etf_all_scoreable:.2%} |")
    for _, row in off.iterrows():
        label = "**25（R²关闭）**" if row.LOOKBACK == 25 else str(int(row.LOOKBACK))
        lines.append(f"| {label} | {row.ann_return_six_etf_all_scoreable:.2%} | {row.max_dd_six_etf_all_scoreable:.2%} |")
    lines += ["", "完整精度、成本、换手和逐日账户见 `scan_summary.csv`、`window_metrics.csv`、`daily_outputs/`。", ""]
    (RUN / "result_tables.md").write_text("\n".join(lines), encoding="utf-8")

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True, constrained_layout=True)
    for segment, label, color in (("full", "Full", "#1d4ed8"),
                                   ("last_10y", "10Y", "#0891b2"),
                                   ("last_5y", "5Y", "#16a34a"),
                                   ("last_3y", "3Y", "#ea580c"),
                                   ("last_1y", "1Y", "#9333ea")):
        axes[0].plot(off.LOOKBACK, off[f"ann_return_{segment}"] * 100, label=label, color=color)
        axes[1].plot(off.LOOKBACK, off[f"max_dd_{segment}"] * 100, label=label, color=color)
    for ax in axes:
        ax.axvline(25, color="black", linestyle="--", linewidth=1)
        ax.grid(alpha=0.25)
    axes[0].set_title("R2 off; Score limits and weight p=1 retained")
    axes[0].set_ylabel("Annualized net return (%)")
    axes[1].set_ylabel("Max drawdown (%)")
    axes[1].set_xlabel("LOOKBACK (trading days); formal R2-on reference = 25")
    axes[1].set_xticks(GRID)
    axes[0].legend(ncol=5)
    fig.savefig(RUN / "lookback_scan.png", dpi=150)
    plt.close(fig)

    meta_path = RUN / "scan_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    price = ROOT / "outputs/recert_l1_20260926/prices_aligned_qfq_through_20260924.csv.gz"
    flags = ROOT / "outputs/recert_l1_20260926/price_ffill_flags_through_20260924.csv.gz"
    meta.update(
        scan_type="single_parameter_conditional_on_r2_off",
        candidate_grid=GRID,
        baseline={"formal_reference": "formal_25_r2_on", "conditional_baseline": "r2_off_25",
                  "fixed_parameters": "weight p=1; strict 0.5<Score<5.5; Buffer=1; Top1 full entry or cash; cost=0.001 per leg"},
        data_snapshot={"price_path": str(price.relative_to(ROOT)), "price_sha256": sha(price),
                       "flags_path": str(flags.relative_to(ROOT)), "flags_sha256": sha(flags),
                       "source": "L1 formal-loader capture; Tencent-labelled front-adjusted close",
                       "start": "2011-12-09", "end": "2026-09-24", "rows": 3594,
                       "all_100d_scoreable_start": "2020-05-07", "timezone": "Asia/Shanghai"},
        cost_model={"one_way_cost": 0.001, "cash_yield": 0, "max_leverage": 1,
                    "execution": "T-close signal and hypothetical same-T-close fill; paper account"},
        source_hashes={"formal_code_sha256": sha(ROOT / "poe_subd_six_etf_v1_3_bot.py"),
                       "runner_sha256": sha(RUN / "run_scan.py"),
                       "audit_results_sha256": sha(RUN / "audit_results.py"),
                       "audit_signals_sha256": sha(RUN / "audit_signals.py")},
        parity_check="formal25 vs L2; R2-off25 vs L4; independent NAV metric and Top1 signal audits",
        cache_write_risk="Read-only L1 prices/flags; in-memory LOOKBACK and R2 argument override; writes only this run directory",
        warnings=["Frozen cutoff 2026-09-24; later market dates excluded", "Full sample adds ETFs as listed",
                  "Five trailing windows overlap and are in-sample", "Same-close fill is a paper assumption"],
    )
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    record = ["# 六 ETF V1.3：R² 关闭、回看窗口 5–100 日扫描", "",
              "## Run Metadata", "", f"- Run id: `{RUN.name}`", "- Research-only conditional single-parameter scan.", "- Git state: `scan_meta.json`.", "",
              "## Research Question", "", "- Disable only the R² eligibility gate, then vary LOOKBACK = 5, 10, ..., 100; keep Score limits 0.5 and 5.5, p=1, Top1 and all other account rules fixed.",
              "- Include the formal 25-day R²-on object as a same-batch reference outside the conditional grid, plus R²-off 25-day as the within-grid baseline.",
              "- Source-change rule: `research_only_no_source_change`; no strategy or provider code edited.", "",
              "## Implementation Anchor", "", "- `poe_subd_six_etf_v1_3_bot.py` weighted slope and `run_staged_entry`; direct call with `r2_threshold=None` and runtime LOOKBACK override, restored after each run.",
              "- L6 helper supplies unchanged metric and account parity checks; independent signals are checked with a separate closed-form weighted slope.", "",
              "## Data Snapshot", "", "- L1 front-adjusted saved panel and forward-fill flags, 2011-12-09 to 2026-09-24, 3,594 China ETF sessions; hashes in `scan_meta.json`.",
              "- All six ETFs can form a 100-day Score from 2020-05-07; before then Full/10Y dynamically add listed assets.",
              "- Two flagged filled asset-days cannot be traded. No provider refresh or cache write.", "",
              "## Cost and Execution Assumptions", "", "- Single ETF or cash; no leverage or financing; cash yield 0; each buy/sell leg costs an assumed 0.10% including slippage.",
              "- Old holding receives T close-to-close return; T close signal hypothetically fills at same close. ETF premium, capacity, actual fill and impact remain unverified.",
              "- Each trailing window takes its first NAV as base and uses N−1 NAV changes for annualization.", "",
              "## Runtime Override Plan", "", "- Formal 25 must match L2, and R²-off 25 must match L4, before interpreting the grid.",
              "- Audit every 21 × 6 metric pair from exported NAV and 20 × 3,594 Top1 signal days independently.", "",
              "## Commands", "", "```powershell",
              f"python -X utf8 quant_param_scan_runs/{RUN.name}/run_scan.py",
              f"python -X utf8 quant_param_scan_runs/{RUN.name}/audit_results.py",
              f"python -X utf8 quant_param_scan_runs/{RUN.name}/audit_signals.py",
              f"python -X utf8 quant_param_scan_runs/{RUN.name}/build_report.py", "```", "",
              "## Output Files", "", "- `scan_summary.csv`, `window_metrics.csv`, `daily_outputs/`, `parity_checks.json`, `signal_audit.json`, `result_tables.md`, `lookback_scan.png`, `scan_meta.json`, `command_log.txt`.", "",
              "## Full-Sample Results", "", f"- Formal 25 R² on: {pair(formal, 'full')}; R²-off 25: {pair(off25, 'full')}.",
              f"- R²-off Full return peak: {int(full_best.LOOKBACK)} days, {pair(full_best, 'full')}; common-period peak: {int(common_best.LOOKBACK)} days, {common_best.ann_return_six_etf_all_scoreable:.2%} / {common_best.max_dd_six_etf_all_scoreable:.2%}.", "",
              "## Window Results", "", "- All 21 paths across five required windows and the common period: `result_tables.md`.",
              f"- Highest trailing 1Y return: {int(year_best.LOOKBACK)} days, {pair(year_best, 'last_1y')}.", "",
              "## Stability Classification", "", "- Complete after validation; historical windows overlap and no independent holdout is included.", "",
              "## Decision", "", "- Complete after validation; research results do not change formal production parameters.", "",
              "## User-Facing Summary", "", "- The R²-off grid is a conditional research test; compare its 25-day baseline separately with the formal 25-day rule.", ""]
    (RUN / "record.md").write_text("\n".join(record), encoding="utf-8")
    with (RUN / "command_log.txt").open("a", encoding="utf-8") as log:
        log.write(f"\n[{datetime.now(timezone(timedelta(hours=8))).isoformat()}] cwd={ROOT}\n")
        for name in ("run_scan.py", "audit_results.py", "audit_signals.py", "build_report.py"):
            log.write(f"python -X utf8 quant_param_scan_runs/{RUN.name}/{name}\n")
        log.write("No provider request or cache mutation; no output-affecting environment variables.\n")
    print(f"Report ready: Full best {int(full_best.LOOKBACK)}, common best {int(common_best.LOOKBACK)}, 1Y best {int(year_best.LOOKBACK)}")


if __name__ == "__main__":
    main()
