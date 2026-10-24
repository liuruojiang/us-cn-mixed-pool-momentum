# 六 ETF V1.3 接手审计：数据与日历独立反例

审计入口：`poe_subd_six_etf_v1_3_bot.py`，分派基线 HEAD `f1fe6ac`。测试创建时未修改正式源码、历史证据或缓存。仅新增本测试及该输出目录；没有远端行情调用或下单。

## 结果

6 个诊断测试：3 通过、3 失败；失败对应同一日历校验不对称缺口，不代表 3 个独立缺陷。

### P2：有官方参考时，行情与供应商日历无差集即可绕过日历核对

精确位置：`_recover_calendar_price_conflict` 第 2499–2501 行（初始基线）；`unexpected = observed.difference(expected)` 为空立即返回。官方 2026 日历直到后续分支才调用。

* 完整性反例：在真实冻结 3594 行、6 ETF 前复权行情及供应商日历中均删去 `2026-09-22`；这是程序内已有官方参考明确确认的交易日。对齐函数接受缺失行情，正式 `_load_public_close_with_per_code_fallback -> load_close -> _build_v13_daily` 也成功返回，而非报缺失交易日。跳过一个整日会改变后续 25 日评分窗口与逐日交易/波动率时间轴。没有把故障注入收益当成实盘收益。
* 可用性反例：只给供应商日历加上官方确认休市的 `2026-01-01`，行情保持真实原样；完整行情被错误拒绝为 `Prices are missing common trading dates: 2026-01-01`。这是拒绝服务式可用性影响，不能描述为误下单。
* 对照：正常冻结行情+日历通过；仅行情删 `2026-09-22` 能拒绝；仅供应商日历删该日能借官方参考恢复并通过。

建议最小修复：在官方参考明确覆盖区间内，不仅在 `observed - expected` 非空时才校验日历。将该区间的供应商会话集合与官方集合核对/替换，区间外仍保留原供应商门禁。不能通过从价格日期反推日历修复。共同漏日存在两个同时故障，故严重程度标为 P2，且未证明当前远端供应商发生了这种故障。

## 可复现证据

- 测试：`tests/test_v13_takeover_data_20261024.py`
- 完整日志：`outputs/takeover_audit_20261024/data/pytest_chain.txt`
- JUnit：`outputs/takeover_audit_20261024/data/results_chain.xml`
- 真实行情：`outputs/doublecheck_script_audit_20261007/final_network/raw_prices_qfq.csv.gz`，测试截取至 2026-09-24，3594 行、6 资产。
- 日历：`outputs/script_audit_20261007/calendar_cache_for_replay.csv`；独立已发布休市参考使用正式源码的 `_load_official_cn_trading_calendar_2026`。
- 命令：`python -B -m pytest -q -p no:cacheprovider tests/test_v13_takeover_data_20261024.py --basetemp=outputs/takeover_audit_20261024/data/scratch/pytest_chain --junitxml=outputs/takeover_audit_20261024/data/results_chain.xml`

## 范围与剩余边界

源码检查包含供应商 qfq 选源、历史日期/价格校验、CNFin 日历分页、磁盘/内存缓存、收盘元数据与实时新鲜度链路。新增执行反例聚焦日历完整性，不将阅读源码等同于上述所有路径全面通过。没有重拉最新行情，也没有验证实时生产部署。官方参考仅覆盖 2026，不能将修复扩展为猜测其他年份交易日。

本子任务可手动清理的临时目录仅 `outputs/takeover_audit_20261024/data/scratch/`；测试源码、失败日志、JUnit 和本报告属于需要保留的复现证据。
