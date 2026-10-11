# 六ETF朴素版V1.3：每周调仓回测

## Run Metadata / Research Question
2026-09-13。只改变交易允许日：daily与weekly_mon/tue/wed/thu/fri。默认评估周五；全部买入、切换和退回现金均等到指定日，非指定日不执行风险退出。原生产脚本未修改。

## Implementation Anchor
`poe_subd_six_etf_v1_3_bot.py: build_curves -> run_staged_entry`；沿用25日线性加权Top1、0.5<Score<5.5、R²>=0.25、全额建仓、Buffer=1、最大1倍，无叠加层。使用inspect取得原函数，仅在signal_target前加入交易日gate；完整实际函数保留在ledger_with_weekly_gate.py.txt。缓存动量结果不改变公式。

## Data Snapshot
冻结Tencent前复权价格2011-12-09至2026-09-02，3578行，SHA256 0cc4af45158d6aaab4594b869b79309a96e8e3cc2f21a0205c38128913bec2aa。source路径与代码hash见scan_meta.json；保留上市前NaN及已验收price_ffill标记。未刷新数据、未写数据缓存、未切换来源。初始git工作区干净，结束仅新增本次研究目录。
Full/10Y为随上市逐步加入资产的扩展历史研究，不能当成六ETF共同存续期正式绩效。共同存续期从2019-12-05开始；10Y=N/A，原因：不足2520个交易日；其余5Y/3Y/1Y与扩展历史尾部指标一致。共同存续期统计沿用完整账本，不在共同起点重置持仓。

## Cost and Execution Assumptions
中国上市ETF、Asia/Shanghai、252交易日年化，尾部N×252行。单边综合成本0.10%，互换双边成本0.20%，现金收益0。旧持仓赚取当日close-close，新持仓当日收盘交易、下一行开始收益；成本通过乘法进入净值。沿用原收盘信号/收盘成交研究假设。非调仓日持仓不动，信号失效也不退出。节假日取本周指定日之前最后交易日；若之前无交易日则取本周之后首日。尾部未到指定日的周不提前交易。交易腿使用填价时原保护继续禁用，禁用后等下周重新评估。未新增容量、QDII溢价、开盘冲击、逐笔涨跌停/T+1成交仿真。

## Runtime Override Plan / Verification
只在研究进程中替换run_staged_entry，finally恢复；不改正式入口。原基线与cap_5p5_daily逐日持仓/收益/成本/NAV核对通过，最大NAV误差见parity.json。注入gate全部允许时与官方基线精确一致；五个周频变体均通过非指定日无交易、每周最多一个交易日、成本恒等式、净值有限正值、成本净值不超过无成本净值、2700行前缀一致性检查。

## Commands / Output Files
`python -X utf8 quant_param_scan_runs/20260913_mixed_us_cn_momentum_six_etf_v1_3_rebalance_weekly/run_scan.py`。完整命令见command_log.txt。结果scan_summary.csv、window_metrics.csv；逐日数据daily_outputs/；common_lifetime_metrics.csv、behavior_checks.csv、parity.json及scan_meta.json。

## Full-Sample Results / Window Results
所有年化和回撤均来自本次实际运行，百分比；差异单位为百分点，回撤改善为正才代表改善。

| 调仓 | 窗口 | 年化收益 | 最大回撤 | 年化差异 | 回撤改善 | 实际交易日 |
|---|---|---:|---:|---:|---:|---:|
| daily | full | 30.58% | -22.01% | 0.00 | 0.00 | 375 |
| daily | last_10y | 35.36% | -16.31% | 0.00 | 0.00 | 304 |
| daily | last_5y | 54.70% | -15.96% | 0.00 | 0.00 | 152 |
| daily | last_3y | 69.12% | -14.34% | 0.00 | 0.00 | 103 |
| daily | last_1y | 69.38% | -13.43% | 0.00 | 0.00 | 45 |
| weekly_mon | full | 16.30% | -34.67% | -14.28 | -12.66 | 285 |
| weekly_mon | last_10y | 18.66% | -34.67% | -16.71 | -18.36 | 224 |
| weekly_mon | last_5y | 15.80% | -34.67% | -38.91 | -18.70 | 110 |
| weekly_mon | last_3y | 18.59% | -27.16% | -50.54 | -12.82 | 69 |
| weekly_mon | last_1y | -7.48% | -27.16% | -76.86 | -13.73 | 33 |
| weekly_tue | full | 20.01% | -23.69% | -10.57 | -1.68 | 279 |
| weekly_tue | last_10y | 23.33% | -23.69% | -12.03 | -7.38 | 218 |
| weekly_tue | last_5y | 27.93% | -20.61% | -26.77 | -4.65 | 108 |
| weekly_tue | last_3y | 32.04% | -20.61% | -37.08 | -6.28 | 69 |
| weekly_tue | last_1y | 18.79% | -18.48% | -50.59 | -5.06 | 29 |
| weekly_wed | full | 18.58% | -26.42% | -12.00 | -4.41 | 290 |
| weekly_wed | last_10y | 19.14% | -26.42% | -16.23 | -10.11 | 229 |
| weekly_wed | last_5y | 21.24% | -23.13% | -33.46 | -7.17 | 113 |
| weekly_wed | last_3y | 20.70% | -23.13% | -48.43 | -8.79 | 73 |
| weekly_wed | last_1y | 9.11% | -19.24% | -60.27 | -5.82 | 30 |
| weekly_thu | full | 24.46% | -23.20% | -6.12 | -1.19 | 289 |
| weekly_thu | last_10y | 28.86% | -18.11% | -6.51 | -1.80 | 231 |
| weekly_thu | last_5y | 35.60% | -18.11% | -19.11 | -2.15 | 112 |
| weekly_thu | last_3y | 37.37% | -18.11% | -31.76 | -3.78 | 71 |
| weekly_thu | last_1y | 30.75% | -16.53% | -38.63 | -3.10 | 31 |
| weekly_fri | full | 23.06% | -22.60% | -7.52 | -0.59 | 283 |
| weekly_fri | last_10y | 28.53% | -21.85% | -6.84 | -5.54 | 224 |
| weekly_fri | last_5y | 35.12% | -21.85% | -19.58 | -5.89 | 111 |
| weekly_fri | last_3y | 34.40% | -17.90% | -34.72 | -3.56 | 72 |
| weekly_fri | last_1y | 4.94% | -17.90% | -64.44 | -4.48 | 31 |

共同存续期Full（2019-12-05至2026-09-02），10Y统一N/A；5Y/3Y/1Y见上表：

| 调仓 | 年化收益 | 最大回撤 | 实际交易日 |
|---|---:|---:|---:|
| daily | 56.98% | -16.31% | 212 |
| weekly_mon | 29.30% | -34.67% | 150 |
| weekly_tue | 35.35% | -23.69% | 147 |
| weekly_wed | 25.58% | -26.42% | 156 |
| weekly_thu | 41.85% | -18.11% | 155 |
| weekly_fri | 42.20% | -21.85% | 150 |

## Stability Classification
weekday_sensitive_underperformance。五个周频日均在全部五窗口低于daily，最大回撤全部更深。周四在周频变体里较强，但仍明显弱于基线；不能按历史最佳日自动推荐晋级。不是新的独立OOS，历史参数已有多轮筛选。

## Decision / User-Facing Summary
research_only_keep_daily：不建议把所有交易严格限制为每周一次。周五Full年化损失7.52pp，5Y损失19.58pp，1Y损失64.44pp；Full实际交易日375->283，减少24.53%，年均26.41->19.93次。原版本每天评估，不等于每天交易。限制频率所节省的操作有限，收益和回撤代价明显。未修改生产参数、未发布或下单。

## Finalization

- Finalized at: 2026-09-13T21:42:35+08:00
- Decision: research_only_keep_daily
- Stability label: weekday_sensitive_underperformance
- Complete checker: PASS
