# 六 ETF 朴素版 V1.3 回测重新认证：L0 版本与对象冻结

日期：2026-09-26。流程参考：用户提供的《量化策略回测重新认证：通用执行手册 v1.2》。本层只认证本地版本、旧记录和输入身份，不重新运行回测绩效，也不推进 L1。

## 首页裁决

**L0 PASS（本地身份链）；当前行情新鲜度待 L1。**认证对象是本仓库登记的六只中国上市 ETF 朴素版 V1.3，正式计算入口 `poe_subd_six_etf_v1_3_bot.py`，本地提交 `5f539ff7ef93aa805c563bfa4d6581fc841f0bb6`，源码 SHA256 `21a5867f51367d215a6f9913dafae1a462bf2316f7c59e7a860d43448c63ee72`。这是本地已验收版本；不代表 Poe 托管部署、实际下单或实盘净值。未联网确认远端是否有更新。

| 本层问题 | 结论 |
| --- | --- |
| 测了什么 | 本地 Git/源码/登记一致性；两个 V1.3 家族区分；冻结价格面板和旧曲线的身份、哈希、日期；研究目录是否改变正式版；错误身份注入。 |
| 没测什么 | 价格逐行正确性、供应商修订/复权、历史可知性、信号与成交时钟、现金/费用/净值、五窗口绩效、执行适用性。 |
| 正式版本与数据终点 | 六 ETF 朴素版 V1.3；用于旧回测桥接的冻结 Tencent 前复权面板截至 **2026-09-02**，3578 行；不冒充当前最新行情。 |
| 真实/模拟 | 冻结输入为真实市场历史报价的前复权面板；旧曲线是纸面模型回测产物，没有真实成交回执。 |
| 正式/关停/候选年化收益、最大回撤 | **N/A**：L0 无账户绩效测试。Full、10Y、5Y、3Y、1Y 均 N/A；旧报告数字仍待 L1/L2 独立认证。 |
| 关键事件与资源占用 | **N/A**：本层没有新模型成交或账户；仅定位旧参数曲线的首个身份差异，不评价其盈亏。 |
| 下一层 | L1 数据与时点：审冻结面板的逐行来源、覆盖、复权、交易日和可知时间；另核刷新数据的最新完整交易日，不混入旧版冻结一致性测试。完成 L1 后再次停等确认。 |

## 项目卡与旧记录边界

- 资产池：`159915.SZ`、`159941.SZ`、`513030.SH`、`513520.SH`、`159985.SZ`、`518880.SH`。25 日线性加权对数回归 Top1；严格 `0.5 < Score < 5.5`；`R² >= 0.25`；Buffer 1、全额建仓、最多 1 倍；过热、目标波动率、分批关闭；现金收益 0，单边综合成本 0.001。来源：正式源码第 98–142、3324–3347 行及版本文档。
- 代码链：`_build_v13_daily -> load_close -> align_prices_to_common_valid_date -> build_curves -> run_staged_entry(full_entry)`。A 股 ETF 交易日、Asia/Shanghai；旧回测口径为收盘信号/收盘模型成交，旧持仓取得当日 close-close 收益，新持仓从下一行开始。年化约定 252 个交易日；L0 未验证这些计算。
- 冻结价格输入：`quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/price_snapshot_qfq.csv.gz`；SHA256 `0cc4af45158d6aaab4594b869b79309a96e8e3cc2f21a0205c38128913bec2aa`；2011-12-09 至 2026-09-02，3578 行。六 ETF 共同可用历史从 2019-12-05 开始，较早 Full/10Y 包含资产逐步上市的阶段。
- 旧选定研究曲线：`quant_comparison_runs/20260904_subd_selected_score_max_5p5/cap_5p5_daily.csv.gz`，标识 `selected_research/cap_5p5`；正式 V1.3 冻结验收曲线：`outputs/subd_six_etf_v1_3_acceptance_20260904/daily.csv.gz`，标识 `1.3/v1_3_naive_score_0p5_5p5_r2_0p25`。本次只读对比两份保存 CSV 的日期、持仓、仓位、换手、成本、净收益和 NAV，3578 行逐值一致。此为谱系桥接，不能替代独立账本审计。
- 历史 Score 上限 5 是被 5.5 替代的旧研究臂；六 ETF V1.1 有其他增强机制；`poe_subd_mixed_pool_v1_3_bot.py` 是 QQQ/GLD/KMLM 等另一资产池的独立家族。9 月 13 日的次日开盘和周频目录均是未跟踪研究结果，`decision` 为 `research_only_no_production_change` / `research_only_keep_daily`；正式源码 Git blob 与 HEAD 相同。以上旧记录不作为现行六 ETF V1.3 的绩效真值或生产晋级依据。
- 原始历史报价获取顺序为 AkShare/Eastmoney qfq、经验证 Tencent fqkline qfq、Eastmoney HTTP qfq；上述冻结输入具体为 Tencent qfq。9 月 4 日盘中网络抓取的末行不能替换 9 月 2 日冻结输入或充当已确认收盘。

## 双审计、首差异与反例

审计 A 独立从 Git、登记和源码提取资产及常量，给出[版本身份报告](../recert_l0_version_audit_20260926/agent_a_version_identity.md)与只读[身份闸门](../recert_l0_version_audit_20260926/agent_a_version_identity.py)。审计 B 独立从文件字节、CSV 列与日期、旧产物标签重建[输入/产物身份表](../l0_data_identity_audit_b_20260926.md)；未复用执行者的记账或指标函数。两人先独立核查，再交叉质询：A 确认旧研究曲线与正式验收曲线逐日相同只支持身份桥接；B 确认 9 月 13 日研究结果及旧 Score 差异不改变正式源码和冻结输入。

首个**产物身份差异**是旧研究曲线 `selected_research/cap_5p5` 对正式验收曲线 `1.3/v1_3_naive_score_0p5_5p5_r2_0p25`。首个**旧参数路径差异**在 2013-05-08：Score 上限 5 的旧线退回现金，上限 5.5 的新线继续持有 `159915.SZ`，两线当日成本、净收益、NAV 开始分开。这里仅定位旧记录，不认证收益算式。

本次重跑 `python -X utf8 outputs/recert_l0_version_audit_20260926/agent_a_version_identity.py --self-test`，退出码 0：正确六 ETF V1.3 ACCEPT、冻结输入哈希 MATCH；错用混合池 V1.3 REJECT；内存注入旧 Score 上限 5 REJECT。审计 B 另用列/哈希/时间字段拒绝研究曲线冒充价格输入、9 月 4 日盘中抓取冒充冻结输入、未晋级研究目录冒充正式版本。反例覆盖本层结论相关的身份混淆；不覆盖 L1/L2 的前视或漏费错误。

## 限制与停止点

L0 PASS 只说明本地待测对象已经明确。旧报告的 30.58% 等数字未经本轮独立复算，不能标为本次通过。冻结价格截止 2026-09-02，距当前日期有缺口；后续刷新须单独保存来源、截至日与哈希。当前没有 P0 或影响 L0 身份判断的 P1；数据/账户问题仍未测试。按用户要求，**本记录交付后停止，不运行 L1，等待确认**。
