"""Build the pure-momentum scan table, chart and durable audit record."""

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[1]
SEGMENTS = (("full", "全样本", "Full"), ("last_10y", "近10年", "10Y"),
            ("last_5y", "近5年", "5Y"), ("last_3y", "近3年", "3Y"),
            ("last_1y", "近1年", "1Y"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pair(row, segment):
    return f"{row[f'ann_return_{segment}']:.2%} / {row[f'max_dd_{segment}']:.2%}"


def main():
    wide = pd.read_csv(RUN / "window_metrics.csv").sort_values("LOOKBACK")
    long = pd.read_csv(RUN / "scan_summary.csv")
    parity = json.loads((RUN / "parity_checks.json").read_text(encoding="utf-8"))
    signal_audit = json.loads((RUN / "signal_audit.json").read_text(encoding="utf-8"))
    if wide.LOOKBACK.tolist() != list(range(5, 100, 2)) or len(long) != 288:
        raise RuntimeError("Incomplete grid or metric rows")
    base = wide.loc[wide.LOOKBACK == 25].iloc[0]
    full_best = wide.loc[wide.ann_return_full.idxmax()]
    common_best = wide.loc[wide.ann_return_six_etf_all_scoreable.idxmax()]
    recent_best = wide.loc[wide.ann_return_last_1y.idxmax()]

    lines = ["# 六 ETF 纯动量：5–99 日回看窗口扫描", "",
             "每格是 **年化净收益 / 最大回撤**。`Score > 0`，Score 上限、R²过滤和切换缓冲关闭；25 日是本次纯动量参考值。价格快照截止 **2026-09-24**；全样本内资产按上市时间逐步加入。", "",
             "| 回看日数 | 全样本 | 近10年 | 近5年 | 近3年 | 近1年 |", "|---:|---:|---:|---:|---:|---:|"]
    for _, row in wide.iterrows():
        label = f"**{int(row.LOOKBACK)}（纯动量参考）**" if row.LOOKBACK == 25 else str(int(row.LOOKBACK))
        lines.append("| " + " | ".join([label] + [pair(row, seg) for seg, _, _ in SEGMENTS]) + " |")
    lines += ["", "## 六只 ETF 均可评分期", "",
              "2020-01-09 至 2026-09-24；其余口径相同。", "",
              "| 回看日数 | 年化净收益 | 最大回撤 |", "|---:|---:|---:|"]
    for _, row in wide.iterrows():
        label = f"**{int(row.LOOKBACK)}（纯动量参考）**" if row.LOOKBACK == 25 else str(int(row.LOOKBACK))
        lines.append(f"| {label} | {row.ann_return_six_etf_all_scoreable:.2%} | {row.max_dd_six_etf_all_scoreable:.2%} |")
    lines += ["", "完整精度、交易和费用字段见 `scan_summary.csv`、`window_metrics.csv`；逐日账户曲线见 `daily_outputs/`。", ""]
    (RUN / "result_tables.md").write_text("\n".join(lines), encoding="utf-8")

    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True, constrained_layout=True)
    colors = ["#1d4ed8", "#0891b2", "#16a34a", "#ea580c", "#9333ea"]
    for color, (segment, _, label) in zip(colors, SEGMENTS):
        axes[0].plot(wide.LOOKBACK, wide[f"ann_return_{segment}"] * 100, label=label, color=color, linewidth=1.7)
        axes[1].plot(wide.LOOKBACK, wide[f"max_dd_{segment}"] * 100, label=label, color=color, linewidth=1.7)
    for ax in axes:
        ax.axvline(25, color="#111827", linestyle="--", linewidth=1.1)
        ax.grid(alpha=.25)
    axes[0].set_title("Six-ETF pure momentum | LOOKBACK sweep | prices through 2026-09-24")
    axes[0].set_ylabel("Annualized net return (%)")
    axes[1].set_ylabel("Max drawdown (%)")
    axes[1].set_xlabel("LOOKBACK (trading days); pure reference = 25")
    axes[0].legend(ncol=5, loc="upper right")
    axes[1].set_xticks(list(range(5, 100, 4)))
    fig.savefig(RUN / "lookback_scan.png", dpi=160)
    plt.close(fig)

    meta_path = RUN / "scan_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update(scan_type="single_parameter", candidate_grid=wide.LOOKBACK.astype(int).tolist(),
                baseline={"pure_reference_LOOKBACK": 25, "eligibility": "Score>0; SCORE_MAX=+inf; r2_threshold=None", "selection": "Top1 full entry or cash; switch_buffer=1", "score": "weighted log-price slope p=1, annualized 252", "formal_v1_3": "preserved, not a candidate in this pure grid"},
                data_snapshot={"source": "L1 verified formal-loader capture of aligned qfq ETF closes and forward-fill flags", "price_path": "outputs/recert_l1_20260926/prices_aligned_qfq_through_20260924.csv.gz", "price_sha256": sha(ROOT / "outputs/recert_l1_20260926/prices_aligned_qfq_through_20260924.csv.gz"), "flags_path": "outputs/recert_l1_20260926/price_ffill_flags_through_20260924.csv.gz", "flags_sha256": sha(ROOT / "outputs/recert_l1_20260926/price_ffill_flags_through_20260924.csv.gz"), "start": "2011-12-09", "end": "2026-09-24", "rows": 3594, "six_etf_all_scoreable_start": "2020-01-09", "calendar": "China ETF sessions", "timezone": "Asia/Shanghai"},
                cost_model={"one_way_cost": .001, "meaning": "combined assumed fee/slippage for each buy or sell leg", "cash_yield": 0, "max_leverage": 1, "execution": "T-close signal and hypothetical same-T-close fill; paper only"},
                source_hashes={"formal_code_sha256": sha(ROOT / "poe_subd_six_etf_v1_3_bot.py"), "runner_sha256": sha(RUN / "run_scan.py"), "audit_sha256": sha(RUN / "audit_results.py"), "signal_audit_sha256": sha(RUN / "audit_signals.py"), "protocol_sha256": sha(RUN / "freeze_protocol.md")},
                parity_check="parity_checks.json: unchanged formal 25-day path vs L2; audit_results.py: 288 candidate-window NAV metrics; audit_signals.py: 172512 independent Top1 candidate-days",
                cache_write_risk="Read-only L1 inputs; only LOOKBACK/SCORE_MIN/SCORE_MAX in-memory overrides; writes this new run folder only.",
                warnings=["Pure Score>0 and no cap differs from historical capped 0<Score<5 base.", "Historical cutoff 2026-09-24, not a current live signal.", "Full period dynamically adds ETFs after listing; use common-scoreable period for fixed six-ETF interpretation.", "Five trailing windows overlap and the sweep is in-sample."])
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 六 ETF 纯动量回看窗口扫描记录", "",
             "## Run Metadata", "", f"- Run id: `{RUN.name}`; scan type `single_parameter`; strategy six ETF V1.3 research-only branch.", "- Git branch, commit and original dirty worktree state: `scan_meta.json`.", "- Formal V1.3 source and Poe configuration were not changed.", "",
             "## Research Question", "", "- Sweep LOOKBACK = 5, 7, ..., 99 days (48 values); step 2 from 5 does not hit 100.", "- Pure reference: 25 days, Score > 0, no upper cap, no R² gate, Buffer=1, Top1 full entry or cash.", "- This is a new uncapped raw-momentum definition. The older capped research base `0<Score<5` and formal V1.3 `0.5<Score<5.5, R²>=0.25` remain separately labeled.", "- Required windows: Full, trailing 10Y/5Y/3Y/1Y, plus six-ETF common scoreable period. Source-change rule: `research_only_no_source_change`.", "",
             "## Implementation Anchor", "", "- `poe_subd_six_etf_v1_3_bot.py` provides the actual weighted log-price slope, `run_staged_entry` single account and `_build_config`; only runtime globals and eligibility arguments change.", "- Formal Score uses 252-day annualization and linear recency weights 1..N. `run_scan.py` restores LOOKBACK/SCORE_MIN/SCORE_MAX after every candidate.", "- Unchanged formal 25-day path matches L2's 3,594 daily positions, turnover and costs exactly, with NAV max error 7.11e−15; pure 25 differs from formal on " + str(parity["pure25_vs_formal25"]["position_diff_days"]) + " holding days. See `parity_checks.json`.", "",
             "## Data Snapshot", "", "- Frozen L1 qfq adjusted ETF closes and forward-fill flags, 2011-12-09 to 2026-09-24, 3,594 China ETF sessions; hashes in `scan_meta.json`.", "- Full/10Y windows dynamically admit ETF members after listing. Six ETF common scoreable period: 2020-01-09 to 2026-09-24. Two previously flagged forward-filled asset-days stay flagged and cannot be traded.", "- Read-only local snapshot; no provider query or cache mutation in this run. Results do not represent the latest 2026-10-01 market close.", "",
             "## Cost and Execution Assumptions", "", "- One ETF or cash; max exposure 1; cash yield 0; no borrow/financing/hedge. A buy and a sell each incur the assumed 0.10% combined one-way fee/slippage.", "- Old holding earns T close-to-close move; T-close signal hypothetically fills at the same close. This is a paper model, without verified actual fills, ETF premium, capacity or impact.", "- All variants share the L1 China ETF session index, Asia/Shanghai, identical 252-day windows, and N−1 NAV changes for annualization.", "",
             "## Runtime Override Plan", "", "- Set `LOOKBACK=N`, `SCORE_MIN=0`, `SCORE_MAX=+inf`, `r2_threshold=None`, `switch_buffer=1`, `full_entry=1` only during each candidate call; formal source unchanged.", "- `audit_results.py` recomputes all 288 candidate-window annual returns and drawdowns from saved NAV to tolerance 1e−10.", "- `audit_signals.py` separately computes weighted slopes and checks all 172,512 Top1 candidate-days. For pure 25, " + str(signal_audit["pure25_selected_days_below_formal_r2_0p25"]) + " selected days had R² below formal 0.25 and " + str(signal_audit["pure25_selected_days_at_or_above_formal_score_cap_5p5"]) + " selected days exceeded the formal Score cap, confirming that both filters were effectively off.", "",
             "## Commands", "", "```powershell", "python -X utf8 quant_param_scan_runs/20261001_pure_momentum_lookback_5_99_20260924/run_scan.py", "python -X utf8 quant_param_scan_runs/20261001_pure_momentum_lookback_5_99_20260924/audit_results.py", "python -X utf8 quant_param_scan_runs/20261001_pure_momentum_lookback_5_99_20260924/audit_signals.py", "python -X utf8 quant_param_scan_runs/20261001_pure_momentum_lookback_5_99_20260924/build_report.py", "```", "",
             "## Output Files", "", "- `scan_summary.csv`: 48 candidates × six windows with trades, costs and deltas against pure 25 days.", "- `window_metrics.csv`: 48 rows with mandatory five-window and common scoreable metrics.", "- `daily_outputs/`: 48 daily account paths; `candidate_event_counts.csv`: position differences against pure 25 days.", "- `result_tables.md`: complete readable results; `lookback_scan.png`: return and drawdown plot.", "- `parity_checks.json`, `signal_audit.json`, `scan_meta.json`, `command_log.txt`: parity, independent signal checks and provenance.", "",
             "## Full-Sample Results", "", f"- Pure 25 days: {pair(base, 'full')}; common scoreable period {base.ann_return_six_etf_all_scoreable:.2%} / {base.max_dd_six_etf_all_scoreable:.2%}.", f"- Highest Full annualized return: {int(full_best.LOOKBACK)} days, {pair(full_best, 'full')}; highest common-period return: {int(common_best.LOOKBACK)} days, {common_best.ann_return_six_etf_all_scoreable:.2%} / {common_best.max_dd_six_etf_all_scoreable:.2%}.", "",
             "## Window Results", "", "| 回看日数 | 全样本 | 近10年 | 近5年 | 近3年 | 近1年 |", "|---:|---:|---:|---:|---:|---:|"]
    focus = sorted(set((5, 21, 23, 25, 27, 29, 99, int(full_best.LOOKBACK), int(common_best.LOOKBACK), int(recent_best.LOOKBACK))))
    for value in focus:
        row = wide.loc[wide.LOOKBACK == value].iloc[0]
        lines.append("| " + " | ".join([str(value)] + [pair(row, seg) for seg, _, _ in SEGMENTS]) + " |")
    lines += ["", f"- Highest last-1Y return: {int(recent_best.LOOKBACK)} days, {pair(recent_best, 'last_1y')}. All 48 rows are in `result_tables.md`.", "",
             "## Stability Classification", "", "- Label: `retrospective_grid_only`. Full, common and recent windows can disagree; five trailing windows overlap and this history has been repeatedly used for strategy research.", "- The scan cannot certify an independent out-of-sample optimum or executable returns. Fee/slippage is a fixed paper assumption; no separate impact sensitivity was run.", "",
             "## Decision", "", "- `research_only_no_promotion`: show the pure-momentum shape while retaining the formal V1.3 parameters and any Poe deployment unchanged.", "- Any later candidate promotion needs a separate decision and a fresh executable-price/data validation. Rerun this grid if the source, input data, costs or execution model changes.", ""]
    (RUN / "record.md").write_text("\n".join(lines), encoding="utf-8")
    with (RUN / "command_log.txt").open("a", encoding="utf-8") as f:
        f.write("\n[2026-10-01 Asia/Shanghai] cwd=" + str(ROOT) + "\n")
        for script in ("run_scan.py", "audit_results.py", "audit_signals.py", "build_report.py"):
            f.write(f"python -X utf8 quant_param_scan_runs/{RUN.name}/{script}\n")
        f.write("No output-affecting environment variables; no provider request or cache mutation.\n")
    print(f"Built pure-momentum report; Full winner {int(full_best.LOOKBACK)}, common winner {int(common_best.LOOKBACK)}, recent winner {int(recent_best.LOOKBACK)}")


if __name__ == "__main__":
    main()
