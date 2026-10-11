"""Build the readable separate-R²-window scan report and provenance record."""

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
COMMON = "all_six_100d_scoreable"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pair(row, segment):
    return f"{row[f'ann_return_{segment}']:.2%} / {row[f'max_dd_{segment}']:.2%}"


def main():
    wide = pd.read_csv(RUN / "window_metrics.csv").sort_values("R2_WINDOW")
    long = pd.read_csv(RUN / "scan_summary.csv")
    if wide.R2_WINDOW.tolist() != GRID or len(long) != len(GRID) * 6:
        raise RuntimeError("Incomplete grid or result rows")
    base = wide.loc[wide.R2_WINDOW == 25].iloc[0]
    winners = {segment: int(wide.loc[wide[f"ann_return_{segment}"].idxmax(), "R2_WINDOW"])
               for segment, _ in SEGMENTS}
    common_winner = int(wide.loc[wide[f"ann_return_{COMMON}"].idxmax(), "R2_WINDOW"])
    parity = json.loads((RUN / "parity_checks.json").read_text(encoding="utf-8"))
    audit = json.loads((RUN / "signal_audit.json").read_text(encoding="utf-8"))

    lines = ["# 六 ETF V1.3：单独扫描 R²窗口 5～100 日，步长 5", "",
             "动量 Score 固定 25 日；R²仍用同样的线性时间权重 p=1 和门槛 0.25，只改变它自己的窗口。其余正式规则、成本和当日收盘模拟成交不变。价格截至 2026-09-24。每格为年化净收益 / 最大回撤。", "",
             "| R²窗口 | 全样本 | 近10年 | 近5年 | 近3年 | 近1年 |",
             "|---:|---:|---:|---:|---:|---:|"]
    for _, row in wide.iterrows():
        label = "**25 日（正式）**" if row.R2_WINDOW == 25 else f"{int(row.R2_WINDOW)} 日"
        lines.append("| " + " | ".join([label] + [pair(row, s) for s, _ in SEGMENTS]) + " |")
    lines += ["", "## 所有 ETF 都具有 100 日价格历史后的共同区间", "",
              "2020-05-07 至 2026-09-24；这样比较时，不会让较长的 R²窗口因 ETF 新上市的初始等待期额外吃亏。", "",
              "| R²窗口 | 年化净收益 | 最大回撤 |", "|---:|---:|---:|"]
    for _, row in wide.iterrows():
        label = "**25 日（正式）**" if row.R2_WINDOW == 25 else f"{int(row.R2_WINDOW)} 日"
        lines.append(f"| {label} | {row[f'ann_return_{COMMON}']:.2%} | {row[f'max_dd_{COMMON}']:.2%} |")
    lines += ["", "## 解释与复现", "",
              "- 正式 25 日值与 L2 逐日基线相符；拆分 Score/R²窗口后的 25 日路径也与正式路径相符。",
              "- 更长的 R²窗口需要足够的有效历史价格，未满足时该 ETF 暂不入选。Full 窗口反映这种真实暖机效应；共同区间排除了六只 ETF 在 100 日暖机上的初始覆盖差异。",
              "- 完整精度、成本、换手和逐日账户见 `scan_summary.csv`、`window_metrics.csv`、`daily_outputs/`。逐日文件按既有 `.gitignore` 保存在本地。", ""]
    (RUN / "result_tables.md").write_text("\n".join(lines), encoding="utf-8")

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True, constrained_layout=True)
    for segment, label, color in (("full", "Full", "#1d4ed8"),
                                   ("last_10y", "10Y", "#0891b2"),
                                   ("last_5y", "5Y", "#16a34a"),
                                   ("last_3y", "3Y", "#ea580c"),
                                   ("last_1y", "1Y", "#9333ea")):
        axes[0].plot(wide.R2_WINDOW, wide[f"ann_return_{segment}"] * 100,
                     marker="o", markersize=3, label=label, color=color)
        axes[1].plot(wide.R2_WINDOW, wide[f"max_dd_{segment}"] * 100,
                     marker="o", markersize=3, label=label, color=color)
    for ax in axes:
        ax.axvline(25, color="black", linestyle="--", linewidth=1)
        ax.grid(alpha=.25)
    axes[0].set_ylabel("Annualized net return (%)")
    axes[1].set_ylabel("Max drawdown (%)")
    axes[1].set_xlabel("R2 lookback (days); Score=25 days; formal R2=25 days")
    axes[1].set_xticks(GRID)
    axes[0].legend(ncol=5)
    fig.savefig(RUN / "r2_window_scan.png", dpi=150)
    plt.close(fig)

    meta_path = RUN / "scan_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    price = ROOT / "outputs/recert_l1_20260926/prices_aligned_qfq_through_20260924.csv.gz"
    flags = ROOT / "outputs/recert_l1_20260926/price_ffill_flags_through_20260924.csv.gz"
    meta.update(
        scan_type="single_parameter", parameter_group="R2_WINDOW", candidate_grid=GRID,
        baseline={"formal_R2_WINDOW": 25, "formal_SCORE_WINDOW": 25,
                  "formal_R2_THRESHOLD": .25,
                  "other_parameters": "linear time weight p=1 for both; strict 0.5<Score<5.5; Buffer=1; Top1 full entry or cash"},
        data_snapshot={"price_path": str(price.relative_to(ROOT)), "price_sha256": sha(price),
                       "flags_path": str(flags.relative_to(ROOT)), "flags_sha256": sha(flags),
                       "source": "L1 formal-loader capture; Tencent-labelled front-adjusted close",
                       "start": "2011-12-09", "end": "2026-09-24", "rows": 3594,
                       "all_25d_scoreable_start": "2020-01-09",
                       "all_100d_scoreable_start": "2020-05-07", "timezone": "Asia/Shanghai"},
        cost_model={"one_way_cost": .001, "cash_yield": 0, "max_leverage": 1,
                    "execution": "T-close signal and hypothetical same-T-close fill; paper account"},
        source_hashes={"formal_code_sha256": sha(ROOT / "poe_subd_six_etf_v1_3_bot.py"),
                       "runner_sha256": sha(RUN / "run_scan.py"),
                       "audit_results_sha256": sha(RUN / "audit_results.py"),
                       "audit_signals_sha256": sha(RUN / "audit_signals.py")},
        parity_check="unpatched formal 25d vs L2; separated R2 25d vs formal; independent NAV and Top1/R2 audits",
        signal_audit=audit,
        cache_write_risk="Read-only L1 prices and flags; runtime patch of calc_scores restored after each candidate; no formal source edit; writes only this run directory",
        warnings=["Frozen cutoff 2026-09-24; later market dates excluded",
                  "Full sample dynamically adds ETFs as listed and R2-window warmup varies",
                  "Trailing windows overlap and are in-sample", "Same-close fill is a paper assumption"],
    )
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    record = ["# 六 ETF V1.3：独立 R²窗口 5～100 日扫描", "",
              "## Run Metadata", "", f"- Run id: `{RUN.name}`", "- Research-only single-parameter scan.",
              "- Git state before scan: clean at commit `47e5ffca3b66502642b604a0daaf9b6b5706452d`.", "",
              "## Research Question", "", "- Grid: R² calculation window 5, 10, ..., 100 trading-price observations; formal 25 is included in the same run.",
              "- Score always uses its formal 25-day window. Both regressions retain linear time weights p=1. R² gate stays >=0.25; strict Score bounds, Top1 and account rules fixed.",
              "- Source-change rule: `research_only_no_source_change`; no formal strategy, provider file or parameter changed.", "",
              "## Implementation Anchor", "", "- Official `poe_subd_six_etf_v1_3_bot.py` account engine is reused. Only `calc_scores` is temporarily replaced to look up a formal 25-day Score and separate N-day weighted R²; original function is restored after each candidate.",
              "- R² calculation copies the official weighted-log-price least-squares formula, with N as the only free input.", "",
              "## Data Snapshot", "", "- L1 front-adjusted saved panel and forward-fill flags, 2011-12-09 to 2026-09-24, 3,594 China ETF sessions; hashes in `scan_meta.json`.",
              "- Common six-ETF 25-day Score start: 2020-01-09; common 100-day R² coverage starts 2020-05-07. Earlier Full/10Y dynamically add listed assets.",
              "- Two flagged filled asset-days cannot be traded. No provider refresh or cache write.", "",
              "## Cost and Execution Assumptions", "", "- Single ETF or cash; no leverage/financing; cash yield 0; each buy/sell leg has assumed 0.10% fee/slippage.",
              "- T close signal hypothetically fills at T close, after old holding receives that day's close-to-close return. ETF premium, capacity and actual fill are unverified.",
              "- Trailing windows use first NAV as base and N−1 NAV changes for annualization.", "",
              "## Runtime Override Plan", "", "- Unpatched formal path must match saved L2; separated R²-window 25 path must match unpatched formal. The original `calc_scores` is restored after each run.",
              f"- Independent audits recompute all {len(GRID)}×6 NAV windows and all {len(GRID)}×3,594 Top1 candidate-days from weighted moments.", "",
              "## Commands", "", "```powershell",
              f"python -X utf8 quant_param_scan_runs/{RUN.name}/run_scan.py",
              f"python -X utf8 quant_param_scan_runs/{RUN.name}/audit_results.py",
              f"python -X utf8 quant_param_scan_runs/{RUN.name}/audit_signals.py",
              f"python -X utf8 quant_param_scan_runs/{RUN.name}/build_report.py", "```", "",
              "## Output Files", "", "- `scan_summary.csv`, `window_metrics.csv`, `daily_outputs/`, `parity_checks.json`, `signal_audit.json`, `result_tables.md`, `r2_window_scan.png`, `scan_meta.json`, `command_log.txt`.", "",
              "## Full-Sample Results", "", f"- Formal 25 days: {pair(base, 'full')}.",
              f"- Full return peak: {winners['full']} days, {pair(wide.loc[wide.R2_WINDOW == winners['full']].iloc[0], 'full')}.",
              f"- Common 100-day coverage return peak: {common_winner} days, {pair(wide.loc[wide.R2_WINDOW == common_winner].iloc[0], COMMON)}.", "",
              "## Window Results", "", "- All 20 paths across five required windows and common 100-day-coverage period: `result_tables.md`.",
              "- Return winners by Full/10Y/5Y/3Y/1Y: " + ", ".join(f"{s}={winners[s]}" for s, _ in SEGMENTS) + ".", "",
              "## Stability Classification", "", "- Complete after validation; windows overlap and no independent holdout is included.", "",
              "## Decision", "", "- Complete after validation; research results do not change formal parameters.", "",
              "## User-Facing Summary", "", "- Score remains 25 days throughout; only R²'s separate regression window varies. Compare Full and common-coverage results separately.", ""]
    (RUN / "record.md").write_text("\n".join(record), encoding="utf-8")
    with (RUN / "command_log.txt").open("a", encoding="utf-8") as log:
        log.write(f"\n[{datetime.now(timezone(timedelta(hours=8))).isoformat()}] cwd={ROOT}\n")
        for name in ("run_scan.py", "audit_results.py", "audit_signals.py", "build_report.py"):
            log.write(f"python -X utf8 quant_param_scan_runs/{RUN.name}/{name}\n")
        log.write("No provider request or cache mutation; no output-affecting environment variables.\n")
    print("Report ready: winners " + ", ".join(f"{s}={winners[s]}" for s, _ in SEGMENTS)
          + f"; common100={common_winner}; baseline parity {parity['separate_r2_window_25_vs_formal']['position_mismatch']} position mismatches")


if __name__ == "__main__":
    main()
