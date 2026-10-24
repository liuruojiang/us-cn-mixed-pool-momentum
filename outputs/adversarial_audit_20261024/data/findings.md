# 六 ETF V1.3 数据链对抗审计（2026-10-24）

审计正式文件 `poe_subd_six_etf_v1_3_bot.py`，SHA256 `e6934e11f76fb5b35a0b7ec61401189735710d96735d3431d9f7be1dd30af881`。仅审计，没有修改生产代码、共享缓存、参数或旧证据。未使用 QVeris、未联网抓行情、未发送或下单。

## D1 / P2：缺少末日的 CNFin 日历被长时间缓存，正常行情恢复后仍无法构建

- **位置**：`_calendar_is_usable` 第 2142–2146 行；缓存快捷返回第 2336–2352 行；CNFin 把请求边界作为覆盖元数据返回第 2245–2250 行；构建报错第 2541–2546 行。官方 2026 日历后备位于 `_status_calendar_sessions` 第 4175 行起，在历史对齐失败后没有机会挽救构建。
- **触发条件**：其他日历来源不可用，使用 CNFin 的指数 K 线日期作为日历；CNFin 请求至实际交易日 D，但响应因数据延迟或短缺只到 D−1；该响应的 `queried_end=D` 被当成足够覆盖。之后价格或供应商恢复到 D，当前进程仍复用旧日历。
- **可复现输入**：真实冻结前复权价格 `outputs/recert_l1_20260926/prices_raw_qfq_through_20260924.csv.gz`，3,594 行，2011-12-09 至 2026-09-24；独立归档 `calendar_cache_for_audit.csv` 对应日期与价格日期完全相等。**只对模拟 CNFin 响应删除最后真实日期 2026-09-24**，没有改价格。请求范围和分页仍由正式函数发出。首次读取后将模拟供应商恢复为完整真实日期。
- **实跑**：首次 HTTP 调用 2 次、日历止于 2026-09-23；正式 `_calendar_is_usable` 返回 `true`。供应商恢复后，真实 `align_prices_to_common_valid_date` 仍抛 `ValueError: Prices contain unexpected non-trading dates: 2026-09-24`，HTTP 次数仍为 2，说明没有刷新机会。仅将进程内日历缓存设为 `None` 后，同一真实价格成功对齐为 3,594 行、末日 2026-09-24，HTTP 次数增至 4。
- **影响边界**：这是可执行反例确认的数据可用性 bug，可能让正常信号/绩效构建持续失败，直到进程缓存被失效或请求边界推进；它不是放行错误交易的证据，也不是当前 CNFin 已发生该故障的证明。故障注入结果不得作为策略收益或网络验收。
- **窄修复建议**：把“已请求至 D”与“已独立确认 D 是休市或有完整行情”区分。遇到价格日期与行情型日历冲突时，先使候选日历缓存失效并限次刷新，同时使用独立官方日历复核合法日期；仍冲突则报错。为行情型日历缓存添加采集时刻/刷新机制可缓解，但 TTL 本身不能证明末日缺失是休市。不得直接忽略 unexpected dates，也不得从待校验价格自行发明交易日历。
- **反方与控制**：拒绝未经确认的日期是正确的防守；bug 在已经失真的日历被认为永久有效、且无法尝试恢复。清除缓存后的负对照仍严格拒绝注入的周末 2026-09-19 和元旦休市日 2026-01-01，修复不得降低这两项防守。

## 已运行的独立核验

1. `python -X utf8 -B outputs/adversarial_audit_20261024/data/probe_calendar_cache.py`：复现上述结果；`calendar_cache_result.json` 保存输入及源码 hash、缓存调用数、报错与负对照。
2. `python -X utf8 -B -m pytest tests/test_v13_audit_data_20261007.py tests/test_v13_doublecheck_data_20261007.py -q -p no:cacheprovider --junitxml=outputs/adversarial_audit_20261024/data/existing_data_regressions.xml`：**47 passed**，1 条第三方 Pydantic 废弃警告。前轮关于首日锚点、分页、非交易日、坏价格、全市场缺日、缓存年龄等已有防守未见回归。

本分工没有重算策略收益；Full、10Y、5Y、3Y、1Y 年化与最大回撤均 N/A（本次是数据可用性反例，不是策略测评）。未经独立确认的单资产停牌/缺价与过期 `day` 复权白名单仍属数据认证边界，不能仅凭源码猜测升级成已发生 bug。
