# 当前已选组合与原始V1.1回测对比

## 1. 结论与范围

- 实跑结果：当前组合降低Full/10Y/5Y/3Y最大回撤，但五窗口年化全部落后原始V1.1，1Y最大回撤也略差；不是全面占优。
- 当前组合只代表用户选定的研究主线，本次无选参、无生产上线、无参数回退。
- 比较的是原始V1.1完整机制与当前组合，不能用本表把收益差归因到某一个被关闭的机制或杠杆。

## 2. 真实代码与数据

- 原始入口：run_subd_six_etf_v1_1.build_curves；明确选择version=1.1输出，不是列表中的V1.0对照。
- 原版完整顺序：calc_scores -> run_staged_entry -> apply_target_vol_overlay -> build_overheat_features/apply_overheat_overlay，保留原same_side_or_exit恢复及零仓执行保护。
- 当前路径：原calc_scores/SCORE_MIN=.5 -> run_staged_entry(full_entry,R2=.25,Buffer1)，不调用目标波动率或过热层。
- 指标全部调用正式summarize/build_performance_windows；现金、成本及预热口径保持。
- 独立Poe实现：poe_subd_six_etf_v1_1_bot.build_curves原版全路径，以及当前参数下run_staged_entry；两条线均独立校验。
- 数据：冻结Tencent fqkline前复权面板，2011-12-09至2026-09-02，3578行。
- 输入：quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/price_snapshot_qfq.csv.gz。
- SHA256：0cc4af45158d6aaab4594b869b79309a96e8e3cc2f21a0205c38128913bec2aa。
- 当前曲线复核：quant_param_scan_runs/20260904_subd_floor_0p5_r2/daily_outputs/r2_0.250.csv.gz。
- 中国ETF交易日历、Asia/Shanghai，252交易日年化，10Y/5Y/3Y/1Y为252*N个交易日，不是按自然年截取。
- 两边保留同一上市后逐步加入及旧缺失值/填充值保护。全六只最早共同有价格日期2019-12-05；Full/10Y不是固定六ETF共同存续期正式证据，未重新独立审计上市历史。代码/数据哈希、逐资产首个观测日见metadata.json。

## 3. 参数对照

| 项目 | 原始V1.1 | 当前已选组合 |
| --- | --- | --- |
| Score区间 | 0<Score<5 | .5<Score<5 |
| R2阈值 | .20 | .25 |
| 回看期/时间权重 | 25日/线性p=1 | 同左 |
| 换仓缓冲 | 1.05 | 1.00关闭 |
| 入场方式 | 50%首仓，首次后续下跌日补满，无超时 | 全额建仓 |
| 目标波动率 | 25%，窗口80日 | 关闭 |
| 杠杆上限/调仓死区 | 1.5倍/7.5个百分点 | 无杠杆，不启用该层 |
| 过热防御 | MA60偏离20%进入、18%退出，降至0；含20日偏离动量、原同向恢复规则 | 关闭 |
| 单边综合成本/现金收益 | .10% / 0 | 同左 |

## 4. 执行命令与验证

工作目录：D:\动量策略\美股A股混合池子动量策略

```powershell
python -X utf8 quant_comparison_runs/20260904_subd_selected_vs_original_v11/run_comparison.py
python -X utf8 -m py_compile quant_comparison_runs/20260904_subd_selected_vs_original_v11/run_comparison.py
git diff --check
git diff --exit-code -- research_subd_six_etf_weighted_slope.py run_subd_six_etf_v1_1.py poe_subd_six_etf_v1_1_bot.py
```

- 实跑耗时90.902秒，5窗口x2策略，保存两条完整日曲线。
- 原版runner/Poe完整机制下收益、NAV、成本、换手、有效敞口、过热缩放及标的完全一致。
- 当前组合runner/Poe的收益、NAV、成本、换手、入场比例及标的完全一致。
- 当前组合与既有选定曲线NAV误差最多7.1054e-15，收益约9.9747e-17；换手、成本、比例、标的完全一致。
- 日期索引、有限值、成本=换手*.001、敞口上限和生产源码哈希检查通过。无正式数据源刷新或缓存更新。
- 本次已补充所选.5/.25组合的独立Poe全日曲线校验，不只是先前扫描的.20抽查。

## 5. 五窗口结果

收益差=当前年化-原版年化；回撤改善=当前最大回撤-原版最大回撤，均为百分点。回撤改善为负表示更差。

### 实测结果

| Window | Original ann/MDD | Selected ann/MDD | Annual delta pp | MDD improvement pp |
| --- | ---: | ---: | ---: | ---: |
| Full | 35.13% / -30.22% | 30.03% / -22.01% | -5.10 | +8.21 |
| 10Y | 40.21% / -20.86% | 33.97% / -17.42% | -6.24 | +3.44 |
| 5Y | 70.12% / -17.35% | 52.98% / -17.07% | -17.14 | +0.28 |
| 3Y | 81.72% / -16.34% | 67.50% / -15.04% | -14.21 | +1.29 |
| 1Y | 62.63% / -12.85% | 59.86% / -13.77% | -2.77 | -0.93 |

## 6. 风险敞口与交易

| 窗口 | 原版年化波动率 | 当前年化波动率 | 原版平均有效敞口 | 当前平均有效敞口 |
| --- | ---: | ---: | ---: | ---: |
| Full | 24.26% | 21.50% | 88.31% | 67.75% |
| 10Y | 24.78% | 22.25% | 101.69% | 78.06% |
| 5Y | 25.77% | 25.22% | 96.62% | 82.62% |
| 3Y | 26.03% | 28.05% | 90.86% | 85.85% |
| 1Y | 27.27% | 30.03% | 79.22% | 80.95% |

- Full交易日数原版849、当前388；按最终有效换手统计，不是底层虚拟轮动计数。
- Full有效敞口超过1倍的日数比例原版50.98%、当前0；原版最高1.5倍，当前1倍。
- Full Sharpe原版1.362、当前1.328；简单参数更少不等于本样本风险调整收益更高。
- Full成本率逐日算术和原版.754803、当前.591000，这不是终值损失百分比；实际成本已逐日扣入NAV。
- 原版Full过热触发13次；其贡献可能样本集中。本次不做独立归因，不能将完整策略收益优势等同于每个机制都稳健。

## 7. 摩擦、时点与证据边界

- 同一单边.10%综合手续费/滑点。原版有效缩放、进出现金和过热恢复交易按正式最终敞口路径重新计成本，不遗漏叠加层成本。
- 原实现为收盘信号/收盘成交研究约定，新仓只取得下一行收益；沿用正式缺失价格/过旧价格交易阻断。具体实现并不保证真实收盘信号能够无摩擦成交。
- 现金收益0；原版杠杆融资费用也按原实现未单独扣除，故不是计入真实融资利息的可执行收益比较。本次没有擅自给原版增加新融资假设。
- 未单独建模盘口流动性、容量、涨跌停/T+1、开盘冲击及场内QDII溢价。
- 同一历史样本已多次用于研究，五窗口相互重叠；没有新独立样本外检验。不能据此证明原版或当前组合谁更不易过拟合。
- 未做统一杠杆/风险预算对齐、逐项叠加归因或下一参数扫描。

## 8. 保存与回滚

- original_v11_daily.csv.gz、selected_research_daily.csv.gz：两条完整路径。
- metrics.csv：正式指标及敞口统计；window_comparison.csv：五窗口直接差值。
- parity_checks.csv、metadata.json：一致性、来源和参数记录。
- result_tables.md、plan.md、run_comparison.py、command_log.txt：重建依据。
- 只新增本研究目录，未改策略源码或当前选定参数，无生产回滚动作。
