# 原版六ETF朴素版V1.3：当日收盘与次日开盘成交对照

## Run Metadata / Research Question
2026-09-13，保留原版每日信号，仅比较成交时点same_close与next_open。本次不加入周频限制，不修改生产入口，不发布或下单。

## Implementation Anchor / Runtime Override Plan
正式入口poe_subd_six_etf_v1_3_bot.py，build_curves -> run_staged_entry。25日线性加权对数斜率、Top1、严格0.5<Score<5.5、R²>=0.25、Buffer=1、全额建仓、1倍上限，无分批、目标波动率或过热层。
使用正式曲线输出的每日合格Score集合，调用正式_target_from_scores；次日开盘只读取前一行收盘信号。独立现金/份额账本核对全部日度净值。最后2026-09-02收盘信号不在样本内成交。

## Data Snapshot
冻结前复权收盘价2011-12-09至2026-09-02，3578行，SHA256 0cc4af45158d6aaab4594b869b79309a96e8e3cc2f21a0205c38128913bec2aa。实际路径见scan_meta.json。
使用正式Tencent fqkline qfq分页加载函数，保留其来源schema与连续性验证，仅扩展返回同条kline的OHLC字段。六只ETF新取得的有效收盘价与冻结面板完全一致。159915的2021-02-08和513030的2025-01-23仍缺失，沿用原面板标记，不补造开盘价。
独立来源Sina raw OHLC只作验证，不进入绩效。每只ETF各1016个重叠日期；同日open/close比值抵消复权比例，五只完全一致，159941最大相对差异0.0843%，99分位差异0。实际审计见data_audit.json，原始OHLC在prices/。
Full和10Y为资产随上市逐步加入的扩展历史研究。六ETF共同存续期从2019-12-05开始，10Y=N/A（不足2520行）；5Y/3Y/1Y结果与下面尾部窗口一致。共同Full沿用完整账本的进入持仓，不在起点重置。
来源规则：不替换冻结收盘，不填开盘，不将raw价格当qfq。所有新数据仅写本研究目录，不修改正式缓存。运行前已存在上轮周频研究未跟踪目录，予以保留。

## Cost and Execution Assumptions
全部为中国上市ETF，Asia/Shanghai，中国交易日序列；252交易日年化，10Y/5Y/3Y/1Y各取尾部2520/1260/756/252行，不等于精确自然年。
单边综合成本0.10%，ETF互换0.20%，现金收益0，无杠杆。T收盘计算信号，T+1交易日开盘执行。旧资产取得T收盘至T+1开盘收益，按开盘时财富扣成本，再由新资产取得开盘至收盘收益。无交易日使用原close-close估值；ledger中无交易日的overnight_return字段代表整个close-close持有收益，intraday_return为0，避免无用开盘价引入舍入或填价。
缺失/填价交易腿禁止整个换仓，每个早晨按前日信号重新评估；本次实际被阻止的开盘交易为0。未新增容量、QDII溢价、逐笔涨跌停和T+1成交仿真；额外开盘冲击不另建模型，仍采用原统一综合成本。

## Commands / Output Files / Verification
python -X utf8 quant_param_scan_runs/20260913_mixed_us_cn_momentum_six_etf_v1_3_execution_next_open/fetch_prices.py
python -X utf8 quant_param_scan_runs/20260913_mixed_us_cn_momentum_six_etf_v1_3_execution_next_open/audit_data.py
python -X utf8 quant_param_scan_runs/20260913_mixed_us_cn_momentum_six_etf_v1_3_execution_next_open/run_scan.py
命令与耗时见command_log.txt。首次采集脚本因df日期未转换失败，修正日期类型后采集成功；首次报告适配缺少version字段，补齐显示字段后重跑成功。未通过的尝试未作为结果。
正式基线逐日NAV/持仓与cap_5p5_daily匹配；独立同收盘账本与正式基线匹配。next_open通过2700行前缀一致性、独立份额资金核对、非负成本净值支配及有限正值检查。parity.json保存误差与通过状态。
产物：scan_summary.csv、window_metrics.csv、common_lifetime_metrics.csv、daily_outputs/same_close.csv.gz和next_open.csv.gz、parity.json、scan_meta.json、data_audit.json、prices/和可复现脚本。

## Full-Sample Results / Window Results
差异为百分点；回撤改善为正才代表更浅。

| 窗口 | 当日收盘年化 | 次日开盘年化 | 年化差异 | 当日收盘最大回撤 | 次日开盘最大回撤 | 回撤改善 |
|---|---:|---:|---:|---:|---:|---:|
| Full | 30.58% | 28.45% | -2.13 | -22.01% | -22.42% | -0.42 |
| 10Y | 35.36% | 33.62% | -1.75 | -16.31% | -22.42% | -6.11 |
| 5Y | 54.70% | 53.17% | -1.53 | -15.96% | -20.93% | -4.97 |
| 3Y | 69.12% | 71.31% | +2.18 | -14.34% | -16.94% | -2.60 |
| 1Y | 69.38% | 52.10% | -17.29 | -13.43% | -16.94% | -3.51 |

共同存续期Full（2019-12-05至2026-09-02，1636行）：same_close年化56.98%/最大回撤-16.31%，next_open年化54.94%/最大回撤-22.42%。10Y=N/A，5Y/3Y/1Y见上表。
Full交易日375->375，1Y交易日45->45；10Y304->305来自交易时点跨窗口边界移动。不是增加新的策略条件。

## Stability Classification / Decision / User-Facing Summary
execution_timing_material：全样本年化下降2.13pp，近5年下降1.53pp，近3年增加2.18pp，近1年下降17.29pp；全部五窗口回撤更深。next_open更贴近收盘确认后再交易的执行流程，但不能把same_close的风险数字直接用于next_open。
research_only_no_production_change。交付已完成的执行时点测试，暂不晋级或重写生产信号。历史仍为多次重叠使用的拟合样本，没有新增独立OOS。

## Finalization

- Finalized at: 2026-09-13T22:30:42+08:00
- Decision: research_only_no_production_change
- Stability label: execution_timing_material
- Complete checker: PASS
