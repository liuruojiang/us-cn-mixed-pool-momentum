# 2026-10-24 独立报表／执行状态对抗审计

正式对象：`poe_subd_six_etf_v1_3_bot.py`，源码 SHA256 `e6934e11f76fb5b35a0b7ec61401189735710d96735d3431d9f7be1dd30af881`。只审计，未修改生产代码、正式参数或历史证据。确认两个局部问题；第一个为真实价格基础上的缺失故障注入，第二个为不修改数据的正常查询。

## R1 / P2：缺价导致引擎阻单后，信号报告反而声称有效且无需下单

**触发条件：** 当天目标资产历史价格缺失，且实时补价不可用。生产对齐会以前值填充；候选仍合格，但引擎因缺价阻止换仓。

**实跑路径：** 保存的实际 qfq 价格截至 2026-09-24，唯一故障为 `159941.SZ` 当日 close 置 NaN。替换价格下载为保存文件、日历读取为保存日历、实时行情返回空帧；其余正式 `_build_v13_daily(data_state='live') → align_prices_to_common_valid_date → _price_forward_fill_flags → build_curves → signal_data_status → format_signal_report` 全部运行。时间固定 2026-09-24 14:55；这是诊断时钟和缺价注入，不宣称该日真实发生缺价，也不宣称历史收盘数据为当时可知的盘中数据。

| 观察 | 原始价格对照 | 唯一 close 缺失注入 |
|---|---|---|
| before → after | CASH → 159941.SZ | CASH → CASH |
| best_candidate | 159941.SZ | 159941.SZ |
| trade_blocked_by_stale_price | False | True |
| blocked_trade_target | 空 | 159941.SZ |
| 引擎 stale_price_trade_assets | 空 | 159941.SZ |
| turnover | 1.0 | 0.0 |
| status stale_price_trade_assets | [] | [] |
| status raw_signal_has_trade | True | False |
| status execution_note | 实时行情快照未通过新鲜度校验 | 信号有效，无需下单。 |
| strategy_actionable_now | False | False |

**源码原因：** 引擎 1906–1911 行保留阻单元数据并清空实际动作；4120–4151 行只按阻断后的实际 buy/sell legs 重建 stale 列表，漏掉 `trade_blocked_by_stale_price`、`blocked_trade_target` 和保存的 `stale_price_trade_assets`。4502–4505 和 5837–5839 行优先把无实际腿解释为有效且无需下单，异常区也不展示缺价原因。

**影响与边界：** 这是信号解释／数据故障可见性错误，不是引擎漏收成本或错误放行成交；注入和对照均未放行下单。用户无法从结论区知道系统有买入意图，但因行情缺失被阻止。正常保存数据无缺失注入时无此问题。

**修复建议：** 将“策略有目标变更但被阻断”作为独立状态；向状态/信号函数传播引擎阻单字段，在“无需下单”分支前报告资产、阻断目标与原因，继续保持可执行状态为 False。不要把阻单意图转换为虚构的实际成交腿，也不要修改收益、目标选择或成交记录过滤。回归应覆盖 CASH→ETF、ETF→ETF、ETF→CASH，以及确实无候选/无变更的阴性对照。

**反方解释：** 引擎阻单是正确行为，“无需下单”作为操作结果并非错误交易指令；但“信号有效”且不展示任何缺价异常，会把数据阻断和正常维持仓位混为一谈，因此按 P2 报表状态问题处理，不能提升为已发生实盘损失。

证据：`reporting_results.json` 的 `fault_injection`，`missing_quote_signal.txt`、`missing_quote_last_row.json`、`unchanged_baseline_signal.txt`。未经注入基线 3,594 行的 date、before/after position、holding_fraction、turnover、cost、return、nav 与先前正式保存曲线逐行一致，容差 1e-12。

## R2 / P2：明确请求多个交易记录区间时，仅交付最短一个区间

**正常输入：** `交易记录 2024年、2025年`。不修改保存的 3,597 行实际日度数据，执行正式 `SubDSixEtfV13Bot().run()`。仅将 `_get_daily_for_today` 绑定保存曲线并跳过不相关图片生成；查询分类、区间解析、正式数据准备、报表和 CSV 均为原实现。

**实跑结果：** 解析器正确得到两个区间，2024 年 30 条调仓记录、2025 年 35 条，明确请求合计 65 条。绩效表列出两个区间，但只有一个交易 CSV，内含 2025 年 35 条；2024 年 30 条没有交付。由于 5157 行按区间长度排序，2025 年 365 天比闰年 2024 年 366 天短，因此不是按用户输入顺序取第一年。

**源码原因：** 6367 行把 `ranges[0]` 同时作为图表和交易记录唯一范围；6423–6442 行只对该范围生成记录与附件。

**修复建议：** 显式请求区间与自动追加的 full/10Y/5Y/3Y/1Y 分开保存；对每个显式请求区间分别输出明确标注范围的记录及 CSV，或交付有区间说明的去重并集。不要因修复而把自动强制展示窗口全部展开成重复附件。保留当前单区间查询与空窗口行为。

**反方解释：** 有意仅为主要图表提供一份匹配记录，能解释为何实现复用 `chart_range`，但不能解释正常多区间交易记录请求为何在正确解析后静默漏掉其余区间。附件文件名显示 2025 年使错误可被细心发现，故不是数值伪造；属于请求范围交付不完整。

证据：`reporting_results.json` 的 `multi_window`、`multi_window_response.txt`、`subd_v13_trade_records_2025-01-02_2025-12-31.csv`。

## 复现与输入边界

命令：`python -X utf8 -B outputs/adversarial_audit_20261024/reporting/probe_reporting.py`。

- 真实价格与日度来源：`outputs/doublecheck_script_audit_20261007/final_network/`，2011-12-09～2026-09-30；日度 3,597 行。
- 保存日历：`outputs/script_audit_20261007/calendar_cache_for_replay.csv`。
- 所有输入与源码哈希见 `reporting_results.json`。JSON 中少数 NumPy bool 经序列化显示为字符串 `"True"`/`"False"`，只属表示形式；正式输出状态字段仍为原生布尔。
- 没有网络下载或券商调用；没有提交订单；未发布新的策略收益指标。以上验证不等同于托管 Poe 服务端认证。
- 主审独立发现的周末陈旧日线判断问题不在本报告重复计数。无基于缺价注入重算的策略收益结论。
