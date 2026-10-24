# 修复后独立数据/日历对抗审计

首轮审计代码 SHA256：`aead84a29508c28df28c1b10e4b75a7eb98acfb93927c46b3f897545d9b59a7b`。生产代码只读；新增独立测试 `tests/test_v13_postfix_data_20261024.py`。

输入为真实冻结 `outputs/doublecheck_script_audit_20261007/final_network/raw_prices_qfq.csv.gz`（本轮裁到 2026-09-24，3,594 行）、同目录 `confirmed_daily.csv.gz` 及 `outputs/script_audit_20261007/calendar_cache_for_replay.csv`。时钟、截尾日历、网络失败均为明确诊断注入，未请求实时行情，未修改共享缓存。测试不产生策略收益结论。

## 首轮发现

1. **P2 / F2 残留：跨年窗口导致独立官方日历失效。** 初版修复的 4227 行把整个 `required_start` 至 `required_end` 传给仅支持 2026 年的官方日历。模拟 2026-01-10 周六，真实日线截到 01-08，CNFin 日历漏 01-09 但查询覆盖记录到 01-10。30 日窗口起点 2025-12-11，官方日历返回 None；状态因此仍报 `expected_confirmed_session=2026-01-08`、`signal_valid=True`。反例为 `test_january_weekend_uses_official_recent_session_across_year`。建议按官方实际覆盖裁剪，保留跨年前会话，覆盖外不能将 query end 当完整性证据。
2. **F2 同根覆盖外反例。** 模拟 2027-01-09，真实行情及截尾日历到 2026-09-24、query end 为 2027-01-09，仍返回有效信号。反例为 `test_status_beyond_official_coverage_does_not_trust_query_end`。这不是已发生的供应商故障，也不证明真实下单已放行。
3. **P2 / F3 残留：网络失败时恢复结果未贯穿 provider→alignment。** 初版修复 2358–2361 清空缓存后刷新失败；2518–2528 用旧 expected 历史加官方 2026 修复，provider 接收完整真实价格，但该局部结果不保留。随后的 alignment 在无磁盘缓存（可对应磁盘写入失败）条件下重新请求日历失败，3594 行被整体拒绝。反例为 `test_provider_to_alignment_recovers_under_persistent_fault[network]`。建议强刷失败保留既有候选用于同样的独立复核，或显式传递校正后的日历与来源。该问题属于恢复可用性，不是错误交易放行。

## 首轮通过的边界

- 持续截尾而网络正常时，provider→alignment 正确用官方参考恢复，调用数有界。
- 全市场缺失正常交易日仍拒绝；元旦和周末插入假 bar 仍拒绝。
- 2025 年官方范围之外的行情/日历冲突保持拒绝，不从行情推断交易日。
- 4 线程强制刷新每次绕过内存/磁盘缓存，最大 provider 并发为 1，返回元数据一致。
- 元旦周末依然识别上一年度 12-31 为最近会话。

命令：`python -X utf8 -B -m pytest tests/test_v13_postfix_data_20261024.py -q -p no:cacheprovider --junitxml=outputs/repair_audit_20261024/data/independent_before_round2.xml`。

首轮结果 **7 passed、3 failed**；3 个失败对应以上 2 类残留问题。警告是第三方 Pydantic 已有弃用提示。证据：`independent_before_round2.xml`。后续修复与复验结果另记，不覆盖首轮证据。

## 补修复验结论

主 Agent 完成补修后，独立核对源码 SHA256 `f8953b458cad5bc3947c7d5c4833fa67394a909eb60b549dbd89da4931cfd13f`，上述 **10 项全部通过**（10.07 秒）。命令同上，输出改为 `independent_after_round2.xml`，首轮失败 XML 原样保留。

- F2 对官方参考的起点裁剪到 2026 年，合并更早已知会话；2026-01-10 正确要求 01-09，01-08 日线失效；元旦保留 2025-12-31 会话。
- 覆盖外旧数据不能仅依赖 `queried_end` 获得有效状态。已实际观测到紧邻周五的周末以及完整未来日历覆盖保留其既有正常路径；这不为未知年度生成假期。
- F3 强刷和官方合并在同一 `RLock` 内完成，经复核的合成日历保留在进程内存，未冒充原供应商写入磁盘；网络强刷失败时 provider→alignment 完整链仍能复核真实数据。
- 原缺日、假日期、官方覆盖外冲突、缓存绕过及线程串行负对照继续通过。源码复核未发现补修引入新的高置信缺陷；不据此扩大为所有网络或多进程场景均无缺陷。

## 限制

最终报表解析函数补修后再次核对 SHA256 `8354e9c4b835c77f11809d5d0b727f54e75e7f7bc5a1fc5aa282ccb73bfd1f57`，仅复跑原有 10 项，结果 **10 passed、1 warning，5.52 秒**。最终证据为 `independent_final.xml`，之前 `f8953b45` 及首轮失败证据均保留；未扩大审计范围。

仅验证同进程线程锁，不认证不同进程同时写磁盘的原子性；未扩大审计到磁盘缓存既有非原子写入设计。未验证实时供应商稳定性、官方日历日后的公告更新或 Poe 托管实例。
