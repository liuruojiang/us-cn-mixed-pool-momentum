from pathlib import Path
import json
import pandas as pd

RUN = Path(__file__).resolve().parent
meta_path = RUN / "scan_meta.json"
meta = json.loads(meta_path.read_text(encoding="utf-8"))
meta.update(
    scan_type="single_parameter",
    baseline={"candidate": "score_min_0", "score_min": 0.0},
    candidate_grid=["-inf", -0.2, -0.1, -0.05, 0.0, 0.05, 0.1, 0.2, 0.5],
    cost_model={
        "one_way_cost": 0.001, "lookback": 25, "score_max": 5.0,
        "weight_power": 1, "r2": "off", "switch_buffer": 1.0,
        "initial_entry_fraction": 1.0, "overheat": "off", "target_vol": "off",
        "financing": 0, "cash_yield": 0, "separate_open_impact": False,
    },
    execution={"calendar": "China exchange sessions", "timezone": "Asia/Shanghai",
               "timing": "official close convention; selected holding earns next-row return"},
)
meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
long = pd.read_csv(RUN / "scan_summary.csv")
wide = pd.read_csv(RUN / "window_metrics.csv")
segments = ["full", "last_10y", "last_5y", "last_3y", "last_1y"]
baseline = long[long.candidate == "score_min_0"].set_index("segment")
lines = [
    "# Score下限单参数扫描",
    "",
    "## 范围与真实入口",
    "",
    "- 研究模式；只改SCORE_MIN，生产文件未修改。当前下限0；取消下限用负无穷。",
    "- 正式路径：research_subd_six_etf_weighted_slope.calc_scores -> run_subd_six_etf_v1_1.run_staged_entry；复用前次扫描的指标函数。",
    "- 固定25日线性加权对数斜率、Score上限5、Top1；R2关闭、Buffer=1、全额入场；过热及目标波动率关闭。",
    "- 单个候选的收益/回撤峰值不能直接晋升。需检查邻点、五窗口权衡及默认路径parity。",
    "",
    "## Data Snapshot / 数据与执行",
    "",
    f"- 冻结Tencent qfq六ETF面板，{meta['data_snapshot']['start']}至{meta['data_snapshot']['end']}，{meta['data_snapshot']['rows']}行；这是匹配旧实验的数据，不是实时刷新。",
    f"- 输入：../{meta['data_snapshot']['source_run']}/price_snapshot_qfq.csv.gz。",
    f"- 默认基准：../{meta['data_snapshot']['accepted_base_run']}/daily_outputs/full_entry_1.00.csv.gz。",
    "- 均为中国交易所上市ETF，海外敞口通过境内ETF获得；不把美国直接交易价格混入中国日历。",
    "- 保留已有上市前缺失值/可用资产规则、前向填充标志和候选预热现金行；未增加代理数据。",
    "- 单边0.10%综合交易成本，按成交名义金额扣除；现金无收益、无融资和借券，无独立开盘冲击。",
    "- 保留正式收盘信号/下一行收益约定；未额外模拟盘口、成交量容量、涨跌停无法成交或场内ETF溢价风险，因此不是精细可执行PnL。",
    "- 无额外买入持有基准；本轮对照为完全同数据同成本的Score下限0。",
    "",
    "## 执行与验证",
    "",
    f"- 命令：python -X utf8 {RUN.name}/run_scan.py（工作目录为quant_param_scan_runs的父目录，实际完整命令见command_log.txt）。",
    f"- 耗时：{meta['elapsed_sec']}秒；所有9个候选重新生成日频路径。",
    f"- 当前0对既有纯底座以及runner对Poe校验：{json.dumps(meta['parity_check'], ensure_ascii=False)}。",
    "- 未进行新样本外验证或walk-forward；五个尾部窗口有重叠，不能当成五份独立证据。",
    "- 无生产逻辑编辑，不需要生产回滚；所有运行时SCORE_MIN覆盖在finally中恢复。",
    "",
    "## 五窗口指标",
    "",
    "| 下限 | Full 年化/回撤 | 10Y 年化/回撤 | 5Y 年化/回撤 | 3Y 年化/回撤 | 1Y 年化/回撤 |",
    "|---:|---:|---:|---:|---:|---:|",
]
for _, row in wide.iterrows():
    cells = [f"{row['score_min']:g}"]
    for s in segments:
        cells.append(f"{row[f'ann_return_{s}']:.2%} / {row[f'max_dd_{s}']:.2%}")
    lines.append("| "+" | ".join(cells)+" |")
lines += ["", "## 相对当前下限0的变化（百分点；回撤改善为正）", "",
          "| 下限 | 窗口 | 年化变化 | 回撤改善 |", "|---:|---|---:|---:|"]
for _, row in long.iterrows():
    ref = baseline.loc[row["segment"]]
    lines.append(f"| {row['score_min']:g} | {row['segment']} | {(row['ann_return']-ref.ann_return)*100:+.2f} | {(row['max_dd']-ref.max_dd)*100:+.2f} |")
lines += ["", "## 换手与成本", "", "| 下限 | 全样本交易日 | 全样本成本累计 | 平均持仓率 |", "|---:|---:|---:|---:|"]
for _, row in long[long.segment == "full"].iterrows():
    lines.append(f"| {row['score_min']:g} | {row['trade_days']} | {row['cost_total']:.3f} | {row['holding_day_ratio']:.2%} |")
lines += ["", "## 产物", "", "- scan_summary.csv：9候选×5窗口。",
          "- window_metrics.csv：宽表含相对当前0的收益与回撤变化。",
          "- parity_checks.csv：默认0对既有基准和Poe的一致性。",
          "- daily_outputs：所有候选的逐日持仓、收益、成本及NAV。",
          "- scan_meta.json、command_log.txt：来源、成本、运行状态、命令。",
          "", "## 待审阅", "", "结论由本轮实际计算结果审阅后追加；未授权晋升任何新阈值。", ""]
(RUN / "record.md").write_text("\n".join(lines), encoding="utf-8")
with (RUN / "command_log.txt").open("a", encoding="utf-8") as f:
    f.write(f"\ncommand=python -X utf8 quant_param_scan_runs/{RUN.name}/run_scan.py\n")
    f.write("command=python -X utf8 quant_param_scan_runs/"+RUN.name+"/summarize.py\n")
print(wide[["score_min"]+[x+"_"+s for s in segments for x in ("ann_return","max_dd")]].to_string(index=False))
