# 独立执行／输出 Double-check（2026-10-07）

本轮没有推翻上一轮 E01–E06 的修复结论，没有在可触达的正式调用中发现需要新增生产修复的反例。新增 **38 项独立挑战测试，38 passed／1 warning**。警告仍是 fastapi_poe 的已有 Pydantic 配置弃用提示。本结论只覆盖以下执行、日期和输出边界，不代表无条件证明全部脚本没有缺陷。

审计源码 SHA256：`7a4cf15ff1603764dbf3469aab9b85f33756c98129116b4ce7dedb46eb48e1e3`；正式对象为 `poe_subd_six_etf_v1_3_bot.py`，没有改动生产代码、旧测试或旧证据。

## 独立挑战与结果

| 原结论 | 本轮不同于上一轮的挑战 | 观察结果 |
| --- | --- | --- |
| E01：请求范围不扩大为全样本交易记录 | 直接运行正式 Poe handler；读取已保存的真实 3,597 行日曲线，测试真实有交易单日 09-24、无交易单日 09-30、休市单日 10-07、09-17～09-25、9 月、9 月至今、0.5 年以及 2001.06 至今。期望记录直接按真实输入的日期和 turnover 独立过滤。 | 8 条 CSV 日期列表与独立结果完全一致；空范围仍为空；强制 Full／10Y／5Y／3Y／1Y 表继续显示。只禁用了无关的图片生成；记录选择、正式准备、窗口解析、表格与 CSV 都走真实函数。 |
| E02：非法数据不继续出数 | 在真实曲线末 4 行分别注入 NaT、同一天不同小时的重复记录、-100% return、0 NAV、NaN wealth；分别调用年度绩效、净值 CSV、交易记录 CSV。 | 15 个组合全部明确拒绝，未通过窄日期窗口绕过共同验证。故障值仅为诊断输入，不是行情。 |
| E03：未确认尾行全部排除 | 针对已保存真实价格附加明确诊断 final 元数据；单资产分别为字符串 false、14:59:59 时间、晚于 now 的时间、错误日期、最终价／信号价不符、缺失 bar_final。全局 final 标志均为 True。另附一条价格与元数据看似完整的未来行。 | 所有 6 个单资产反例均无法被全局标志覆盖，当日尾行被剔除；未来行也被剔除，而合法当日行保留。 |
| 确认收盘不等于可执行成交 | 构造有真实交易腿的诊断 CASH→ETF BUY，附六资产有效最终价／时间，但最终价执行认证全部 False；同输入设置显式认证 True 作阳性对照。 | 无执行认证时绩效保留当天，但 tradable=False；所有认证 True 的阳性对照 tradable=True，证明阻断不是因为没有交易腿。没有部署或模拟实际成交。 |
| E04／E05：日期修复保留已有语法 | 显式年月范围、跨年“12 月到 1 月”、含完整起年后省略终年日期、1.5 年、UTC 日期转为北京时间后的 0.5 年。额外实际枚举 2000–2026 年 ×12 月 ×4 分隔符的年月至今和年月区间，共 2,592 次调用。 | 5 项持久化测试通过；额外 2,592 次解析无差异。没有自行给小数月份新增定义。 |
| E06：较老强刷不覆盖较新缓存 | 混合请求：14:54 强制刷新在下载时阻塞，14:55 普通请求完成构建及缓存后，允许旧请求完成；分别检查返回结果、缓存时间与来源。再检查 handler 取得的 daily 被调用方改坏时不会污染后续缓存。 | 较新普通请求的缓存保留，旧请求仍返回自己的结果；缓存副本隔离通过。 |

## 证据与边界

- 真实输入：`outputs/script_audit_20261007/current_network/confirmed_daily.csv.gz`，3,597 行，2011-12-09～2026-09-30，SHA256 `06fcc794fa86288a4cf528b522ad751882fbf5affa652d7e383e6f5348aaeb8c`。这是上一轮保存的实际正式构建结果，未重下载，不冒充本轮实时行情。
- 新测试：`tests/test_v13_doublecheck_execution_20261007.py`；实跑报告：`outputs/doublecheck_script_audit_20261007/execution_after.xml`。
- 年月解析枚举脚本与结果：`outputs/doublecheck_script_audit_20261007/execution_date_probe.py`、`execution_date_probe.json`；可用 `python -X utf8 -B outputs/doublecheck_script_audit_20261007/execution_date_probe.py` 复现 2,592 次调用及不计为缺陷的探索观察。初次探索在上述 7a4cf15 基线；保存脚本的实跑恰逢主 Agent 修复，JSON 内源码为 `f6e7a9b772f21c81a837ce5ec9a908fd9cc9e3a6bec319ecba0a9ad3ddbb6471`，同样无差异；不能把该 JSON 哈希误记为本报告 38 项基线测试的哈希。
- 命令：`python -X utf8 -B -m pytest tests/test_v13_doublecheck_execution_20261007.py -q -p no:cacheprovider --basetemp=outputs/tmp/doublecheck_execution_20261007_recheck --junitxml=outputs/doublecheck_script_audit_20261007/execution_after.xml`，最终 38 passed／1 warning，11.24 秒。
- 实际源码入口：`_handle_performance` 6334、`trade_records_frame` 5572、`_validated_daily_frame` 5193、`prepare_daily_for_signal` 4237、`_row_verified_final_close` 3796、`_row_final_close_execution_verified` 3819、`parse_date_range` 4965、`_get_daily_for_today` 4607、`_cached_daily` 3568。行号属于上述审计基线。
- 小数月份沿用既有 `max(1, int(number))`，未来“至今”日期可以返回起点晚于终点；这些只经过探索，不计为已证实缺陷或新增格式支持。没有项目规则给出小数月份的精确语义；未来倒序范围走空数据／N/A，没有扩大交易 CSV 到全历史。
- 托管端运行时、账户可卖数量、实际成交、完整历史公司行动／停牌／涨跌停未得到新增认证；本轮不发布策略绩效，也不更改参数或数据源。
