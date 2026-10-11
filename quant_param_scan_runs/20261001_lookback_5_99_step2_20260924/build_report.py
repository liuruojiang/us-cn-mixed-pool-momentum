"""Build readable tables, a plot, and complete metadata for the LOOKBACK sweep."""

import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[1]
SEGMENTS = (("full", "全样本"), ("last_10y", "近10年"),
            ("last_5y", "近5年"), ("last_3y", "近3年"),
            ("last_1y", "近1年"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pair(row, segment):
    return f"{row[f'ann_return_{segment}']:.2%} / {row[f'max_dd_{segment}']:.2%}"


def main():
    wide = pd.read_csv(RUN / "window_metrics.csv").sort_values("LOOKBACK")
    long = pd.read_csv(RUN / "scan_summary.csv")
    if wide.LOOKBACK.tolist() != list(range(5, 100, 2)) or len(long) != 48 * 6:
        raise RuntimeError("Grid or window rows incomplete")
    base = wide.loc[wide.LOOKBACK == 25].iloc[0]

    lines = ["# 六ETF V1.3 回看窗口 5–99 日扫描（步长 2）", "",
             "价格快照截止 **2026-09-24**。每格为 **年化净收益 / 最大回撤**；同一前复权价格、标记、费用、账户和纸面同收盘成交模型。全样本从 2011-12-09 起，资产按上市时间逐步加入；六只 ETF 均可评分期另见下表。", "",
             "| 回看日数 | 全样本 | 近10年 | 近5年 | 近3年 | 近1年 |", "|---:|---:|---:|---:|---:|---:|"]
    for _, row in wide.iterrows():
        label = f"**{int(row.LOOKBACK)}（正式）**" if row.LOOKBACK == 25 else str(int(row.LOOKBACK))
        lines.append("| " + " | ".join([label] + [pair(row, seg) for seg, _ in SEGMENTS]) + " |")
    lines += ["", "## 六只 ETF 均可评分期", "",
              "2020-01-09 至 2026-09-24；其余条件相同。", "",
              "| 回看日数 | 年化净收益 | 最大回撤 |", "|---:|---:|---:|"]
    for _, row in wide.iterrows():
        label = f"**{int(row.LOOKBACK)}（正式）**" if row.LOOKBACK == 25 else str(int(row.LOOKBACK))
        lines.append(f"| {label} | {row.ann_return_six_etf_all_scoreable:.2%} | {row.max_dd_six_etf_all_scoreable:.2%} |")
    lines += ["", "完整精度和交易/费用字段见 `scan_summary.csv`、`window_metrics.csv`；逐日账户曲线见 `daily_outputs/`。", ""]
    (RUN / "result_tables.md").write_text("\n".join(lines), encoding="utf-8")

    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True, constrained_layout=True)
    colors = ["#1d4ed8", "#0891b2", "#16a34a", "#ea580c", "#9333ea"]
    for color, (segment, _) in zip(colors, SEGMENTS):
        label = {"full": "Full", "last_10y": "10Y", "last_5y": "5Y", "last_3y": "3Y", "last_1y": "1Y"}[segment]
        axes[0].plot(wide.LOOKBACK, wide[f"ann_return_{segment}"] * 100, label=label, color=color, linewidth=1.7)
        axes[1].plot(wide.LOOKBACK, wide[f"max_dd_{segment}"] * 100, label=label, color=color, linewidth=1.7)
    for ax in axes:
        ax.axvline(25, color="#111827", linestyle="--", linewidth=1.1)
        ax.grid(alpha=.25)
    axes[0].set_title("Six-ETF V1.3 LOOKBACK sweep | adjusted closes through 2026-09-24")
    axes[0].set_ylabel("Annualized net return (%)")
    axes[1].set_ylabel("Max drawdown (%)")
    axes[1].set_xlabel("LOOKBACK (trading days); formal = 25")
    axes[0].legend(ncol=5, loc="upper right")
    axes[1].set_xticks(list(range(5, 100, 4)))
    fig.savefig(RUN / "lookback_scan.png", dpi=160)
    plt.close(fig)

    meta_path = RUN / "scan_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update(scan_type="single_parameter", candidate_grid=wide.LOOKBACK.astype(int).tolist(),
                baseline={"formal_LOOKBACK": 25, "other_parameters": "weight p=1; 0.5<Score<5.5; R2>=0.25; Buffer=1; full-entry Top1 or cash", "comparison_rule": "same L1 panel, same cash/ETF account, one variable only"},
                data_snapshot={"source": "L1 verified formal-loader capture; Tencent-labelled qfq adjusted close", "price_path": str(Path("outputs/recert_l1_20260926/prices_aligned_qfq_through_20260924.csv.gz")), "price_sha256": sha(ROOT / "outputs/recert_l1_20260926/prices_aligned_qfq_through_20260924.csv.gz"), "flags_path": "outputs/recert_l1_20260926/price_ffill_flags_through_20260924.csv.gz", "flags_sha256": sha(ROOT / "outputs/recert_l1_20260926/price_ffill_flags_through_20260924.csv.gz"), "start": "2011-12-09", "end": "2026-09-24", "rows": 3594, "six_etf_all_scoreable_start": "2020-01-09", "timezone": "Asia/Shanghai", "calendar": "China ETF sessions"},
                cost_model={"one_way_cost": .001, "meaning": "combined assumed fee/slippage per buy or sell leg", "cash_yield": 0, "max_leverage": 1, "execution": "T-close signal and hypothetical same-T-close fill; paper-only, without verified actual fills, premiums, capacity or open impact"},
                source_hashes={"formal_code_sha256": sha(ROOT / "poe_subd_six_etf_v1_3_bot.py"), "runner_sha256": sha(RUN / "run_scan.py"), "audit_sha256": sha(RUN / "audit_results.py")},
                parity_check="parity_checks.json: 25-day path vs L2 and 23/25/27/29 vs L6; audit_results.py independently recomputed 288 candidate-window returns and drawdowns from exported NAV",
                cache_write_risk="Read-only saved L1 prices and flags; imports the formal module and overrides LOOKBACK in memory; writes only this run folder.",
                warnings=["Historical frozen cutoff 2026-09-24; not an up-to-date live signal.", "2011 full sample dynamically adds ETFs after listing; use the separate common scoreable window for fixed six-ETF interpretation.", "Five trailing windows overlap and parameter selection on them is in-sample."])
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    common_best = wide.loc[wide.ann_return_six_etf_all_scoreable.idxmax()]
    full_best = wide.loc[wide.ann_return_full.idxmax()]
    recent_best = wide.loc[wide.ann_return_last_1y.idxmax()]
    lines = ["# 六 ETF V1.3：LOOKBACK 5–99 日、步长 2 的纸面扫描", "",
             "## Run Metadata", "", f"- Run id: `{RUN.name}`", "- Scan type: `single_parameter`", "- Strategy: six ETF V1.3 Sub-D", "- Decision scope: research only; formal parameters unchanged", "- Git branch/commit and pre-run dirty status: see `scan_meta.json`", "",
             "## Research Question", "", "- Formal baseline: LOOKBACK 25 days.", "- Grid: 5, 7, ..., 99 trading days (48 values); 100 is off-grid at step 2.", "- Change only LOOKBACK, which jointly sets the weighted-log-slope Score and R² regression length. Keep all other formal filters and account rules fixed.", "- Compare Full, last 10Y/5Y/3Y/1Y and the six-ETF common scoreable period. No production promotion from this retrospective sweep.", "- Source-change rule: `research_only_no_source_change`; any strategy, data or cost rule change requires a new run.", "",
             "## Implementation Anchor", "", "- Official module: `poe_subd_six_etf_v1_3_bot.py`; `run_staged_entry` with `EntryCase(full_entry)` and `_build_config`.", "- The runner imports reusable L6 `run_one`, `metrics` and exact-path parity helpers. It changes `bot.LOOKBACK` only in memory and restores it for each candidate.", "- Frozen formal parameters: LOOKBACK=25, p=1, strict 0.5<Score<5.5, R²≥0.25, Buffer=1, one-way cost 0.001.", "",
             "## Data Snapshot", "", "- L1 formal loader's Tencent-labelled qfq adjusted-close panel plus forward-fill flags, 2011-12-09 to 2026-09-24, 3,594 China ETF sessions; SHA-256 paths in `scan_meta.json`.", "- Six ETF common scoreable period: 2020-01-09 to 2026-09-24. Earlier Full/10Y results add assets as they become available; they are not a fixed six-ETF pool.", "- Two flagged forward-filled asset-days remain flagged and cannot be traded. No data refresh or cache write occurred in this run.", "- Historical frozen data are used for comparability; no claim of a latest 2026-10-01 market close or executable signal.", "",
             "## Cost and Execution Assumptions", "", "- One-way combined fee/slippage 0.10% per buy/sell leg; full single ETF or cash; cash return 0; max ETF exposure 1; no financing, borrowing or hedge.", "- Old holding earns T close-to-close return; T close signal hypothetically fills at that same close. True fill price, ETF premium, capacity and market impact remain unverified. These are paper NAVs.", "- Dates follow the saved China ETF session index in Asia/Shanghai. Each trailing window uses its first NAV as base and N−1 NAV changes for annualization.", "",
             "## Runtime Override Plan", "", "- Only `LOOKBACK` is overridden; all other formal code is imported unchanged.", "- The formal 25-day path matches L2's 3,594 daily positions/turnover/cost exactly, with NAV error ≤7.11e−15; 23/25/27/29 also match L6 saved daily paths (see `parity_checks.json`).", "- Formal source hash differs from the older L6 hash because of later report changes; daily economic parity above verifies this scan's unchanged baseline.", "",
             "## Commands", "", "```powershell", "python -X utf8 quant_param_scan_runs/20261001_lookback_5_99_step2_20260924/run_scan.py", "python -X utf8 quant_param_scan_runs/20261001_lookback_5_99_step2_20260924/audit_results.py", "python -X utf8 quant_param_scan_runs/20261001_lookback_5_99_step2_20260924/build_report.py", "```", "",
             "## Output Files", "", "- `scan_summary.csv`: 48 candidates × six windows with costs, holdings and differences against formal.", "- `window_metrics.csv`: 48 candidate rows, required five windows and common scoreable period.", "- `daily_outputs/`: 48 full daily account paths.", "- `result_tables.md`: complete five-window and common-period display.", "- `lookback_scan.png`: return and drawdown curves.", "- `parity_checks.json`: baseline and overlap path parity; `audit_results.py` independently recomputed all 288 candidate-window annual returns and drawdowns from saved NAV with tolerance 1e−10.", "- `scan_meta.json`, `command_log.txt`: machine-readable scope and commands.", "",
             "## Full-Sample Results", "", f"- Formal 25 days: {pair(base, 'full')} (annualized net return / max drawdown); common scoreable period {base.ann_return_six_etf_all_scoreable:.2%} / {base.max_dd_six_etf_all_scoreable:.2%}.", f"- Highest Full annualized return: {int(full_best.LOOKBACK)} days, {pair(full_best, 'full')}; highest common-period annualized return: {int(common_best.LOOKBACK)} days, {common_best.ann_return_six_etf_all_scoreable:.2%} / {common_best.max_dd_six_etf_all_scoreable:.2%}.", "",
             "## Window Results", "", "| 回看日数 | 全样本 | 近10年 | 近5年 | 近3年 | 近1年 |", "|---:|---:|---:|---:|---:|---:|"]
    for value in (21, 23, 25, 27, 29):
        row = wide.loc[wide.LOOKBACK == value].iloc[0]
        lines.append("| " + " | ".join([str(value)] + [pair(row, seg) for seg, _ in SEGMENTS]) + " |")
    lines += ["", f"- Highest last-1Y annualized return is {int(recent_best.LOOKBACK)} days: {pair(recent_best, 'last_1y')}; this differs from the Full/common-period winner.", "- All 48 values and five mandatory windows are in `result_tables.md`; exact metrics and costs are in the CSV files.", "",
             "## Stability Classification", "", "- Label: `local_peak_unvalidated`.", "- 25 days is the peak Full and common scoreable annualized return in this specified grid; the immediate 23/27-day neighbors remain positive but have lower annualized return. The 27-day Full drawdown is shallower, and 21/23 days lead the most recent year.", "- Returns deteriorate for very short and long windows. The five windows overlap, and the historical sample has been used in earlier parameter selection; this is not fresh out-of-sample evidence.", "- Only the existing one-way 0.10% model cost is included. No independent fill or premium sensitivity was added.", "",
             "## Decision", "", "- `keep_default`: preserve formal LOOKBACK=25 and all source settings. The scan is a research comparison, not authorization to update a Poe-hosted bot or place orders.", "- If a new candidate is considered later, require a new independent sample or executable-price validation under the same fixed rules.", ""]
    (RUN / "record.md").write_text("\n".join(lines), encoding="utf-8")

    with (RUN / "command_log.txt").open("a", encoding="utf-8") as f:
        f.write("\n[2026-10-01 Asia/Shanghai] cwd=" + str(ROOT) + "\n")
        f.write("python -X utf8 quant_param_scan_runs/20261001_lookback_5_99_step2_20260924/run_scan.py\n")
        f.write("python -X utf8 quant_param_scan_runs/20261001_lookback_5_99_step2_20260924/audit_results.py\n")
        f.write("python -X utf8 quant_param_scan_runs/20261001_lookback_5_99_step2_20260924/build_report.py\n")
        f.write("No output-affecting environment variables; no provider request or cache mutation.\n")
    print(f"Built tables and chart; Full winner {int(full_best.LOOKBACK)}, recent winner {int(recent_best.LOOKBACK)}")


if __name__ == "__main__":
    main()
