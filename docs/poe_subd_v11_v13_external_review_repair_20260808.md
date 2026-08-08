# Poe SubD V1.1 / V1.3 外部审查修订记录（2026-08-08）

## 结论

对外部审查的 29 项意见逐项做了代码核查。结果为：19 项已修复，1 项性能优化通过门槛后上线，4 项按本轮边界记录但不改变策略假设，1 项因与本仓库已确认口径冲突而拒绝，4 项留待独立重构/性能轮次。两份正式脚本均已通过真实数据的 `confirmed` 构建；本轮没有改变资产池、信号参数、成本、成交时点、现金收益或正式 target-vol 启用状态。

## 范围与可恢复性

- 正式脚本：`poe_subd_six_etf_v1_1_bot.py`、`poe_subd_mixed_pool_v1_3_bot.py`
- 回归测试：`tests/test_poe_subd_review_20260808.py`，以及两份既有回归测试中的相容性更新
- 修订前备份：`D:\Codex\home\worktrees\美股A股混合池子动量策略\poe-subd-review-repair\.codex_backups\20260808_190718`
- 备份核验：两份正式脚本及 manifest 均存在
- 修订前基线：`python -m pytest -q` 为 322 passed、1 warning。实施计划中的“287 passed”是计划编写时的旧预期，最终以实际基线为准。

## 逐项处置

| # | Disposition | Evidence | Notes |
|---:|---|---|---|
| 1 | fixed | V1.3 新增 `_eval_start_label()`；两处区间标签随 `EVAL_START.year` 生成 | 当前为 `from_2017`，不再显示错误的 `from_2020` |
| 2 | fixed | 强制窗口增加 `available_rows` 与 `MANDATORY_WINDOW_TRADING_DAYS` 校验 | 历史不足时明确输出实际行数与所需交易日数 |
| 3 | rejected | 回归测试锁定 1Y=252、10Y=2520 行；`docs/new_strategy_test_standard_process.md` 与既有研究口径均采用交易日窗口 | 标签表示策略报告的标准交易日窗口，不改成 242 日或自然年，避免跨版本比较口径漂移 |
| 4 | fixed | V1.3 `_score_rule_text()` 动态使用 `LOOKBACK`、分数区间和 `R2_THRESHOLD` | 当前正确披露 28 日与“R²过滤关闭” |
| 5 | fixed | V1.1 参数页改为披露 Sina + CNFin 交叉验证 raw fallback 与白名单限制 | 与实际 per-code fallback 接线一致 |
| 6 | fixed | 新增 `UnsupportedLiveQuoteSymbols`，判断改为异常类型 | 删除脆弱的字符串匹配降级路径 |
| 7 | documented | 两份参数页明确 SELL 腿必须有已验证可卖数量 | 保留既定 fail-closed 行为；未授权接入券商持仓源 |
| 8 | fixed | 非 CN 代码的涨跌停比例为非有限值时直接返回 `(nan, nan)` | 消除 `Decimal('nan').quantize()` 潜在异常 |
| 9 | fixed | 两份脚本增加 1900/1970 行预警并写入 source detail | 保留所有上市日、重叠率、价差和连续性验证；分页方案待供应商接口支持确认后再评估 |
| 10 | fixed | V1.3 dormant target-vol helper 同步 V1.1 的类型、有限值、warmup、零波动和初始 scale 契约 | `TARGET_VOL=None` 保持不变，未启用该叠加层 |
| 11 | fixed | V1.3 AkShare 与 Eastmoney qfq 请求均使用 `START_DATE.strftime('%Y%m%d')` | 不再硬编码 2010-01-01 |
| 12 | documented | V1.3 报告新增跨市场 T 日收盘时序提示 | 明示 US→CN 同日收盘不可执行；未改变信号滞后假设 |
| 13 | documented | 同一跨市场提示披露中国长假对美国收益的压缩 | 未改变混合日历/reindex 口径 |
| 14 | documented | live 报告明确 Yahoo 盘前/隔夜 1 分钟价仅作 monitor-only 估算 | 未将其描述或处理成美国正式收盘价 |
| 15 | fixed | 年度表先计算完整区间 `_report_return`，再按年分组 | 不再在每个自然年边界重复清零首日收益 |
| 16 | fixed | 日历失败原因改为纯 `ContextVar`；日历与日线缓存分别用 `RLock` 保护完整事务 | 并发测试验证另一线程看不到当前请求的失败原因；日线构建为 single-flight |
| 17 | fixed | 日历缓存文件名加入策略起始日 | V1.1 使用 `..._20100101.csv`，V1.3 使用 `..._20070101.csv` |
| 18 | fixed | 质量/时效/权限拒绝路径恢复条件退避；V1.3 Yahoo 快照移出东财 endpoint×attempt 循环 | 回归测试验证 Yahoo 只抓一次且首次拒绝后 sleep 0.5 秒 |
| 19 | fixed | Tencent 缺少 `qfqday` 或 payload key 变化使用 `DeterministicProviderSchemaError` 立即短路 | 回归测试验证只请求一次 |
| 20 | fixed | `_execution_legs_status` 在取最后一行前按 `date` 排序 | 乱序输入测试验证取实际最新日期 |
| 21 | fixed | `_build_config()` 默认结束日使用 `_bj_today_naive()` | 与全脚本北京时间口径统一 |
| 22 | deferred | 已复核死代码清单，无本轮行为缺陷依赖其删除 | 删除会扩大审查面，留给共享核心重构轮次 |
| 23 | fixed | 两份 introduction 改为“最多复用5分钟缓存” | 与 confirmed 5 分钟 TTL 实现一致 |
| 24 | fixed | 两份 `parse_date_range` 在月份模式前增加独立 ISO 单日模式 | `2026-08-05的表现` 解析为同日起止 |
| 25 | promoted | 标量 oracle 覆盖 seeded/NaN/zero/short；10,000 行标量 0.461044 s、向量 0.002924 s，157.68x | 超过预设 5x 门槛；两份脚本采用 runner 已验证的闭式斜率向量化 |
| 26 | deferred | `_apply_zero_overheat_execution_guard` 未出现正确性故障 | 数组化需要独立逐行状态机对拍，不混入本轮 |
| 27 | deferred | 主策略/overlay 循环未出现正确性故障 | 属于较大性能重构，需要独立基准、全曲线 parity 和真实数据验证 |
| 28 | fixed | 两份 `_attach_live_quote_metadata` 把日期转换移到 code 循环外 | 回归测试验证多代码时仅解析一次 |
| 29 | deferred | 本轮用对称双脚本测试、逐项表和同一提交内双向修复降低漂移风险 | “共享核心 + 单文件生成”会改变部署构建方式，留给独立架构轮次 |

## RED/GREEN 证据

- 绩效标签、短历史窗口、年度边界和 ISO 单日解析均先由聚焦测试复现旧行为，再修至通过；252/2520 行测试从一开始即通过，用作第 3 项拒绝的口径保护。
- 缓存/并发/重试组在修改前为 9 failures，修改后为 9 passed。
- 最新行与重复日期转换组在修改前复现 4 failures；修正北京时间测试的辨识度后，最终 6 passed。
- 向量化组先通过 6 个 parity 用例并由 2 个“不得逐窗调用 polyfit”测试保持 RED，替换实现后为 8 passed。
- 聚焦三套最终验证：331 passed、1 warning。
- 全仓最终验证：`python -m pytest -q` 为 366 passed、1 warning。唯一 warning 来自 `fastapi_poe` 的 Pydantic class-based config 弃用提示。
- 语法验证：`python -m py_compile poe_subd_six_etf_v1_1_bot.py poe_subd_mixed_pool_v1_3_bot.py`，退出码 0。
- 说明：直接运行 Windows `pytest.exe` 时，runner 的同目录绝对导入会因入口脚本未把仓库根目录放进 `sys.path` 而有 4 个导入失败；使用仓库标准调用 `python -m pytest` 后 366 项全部通过。这是测试启动环境差异，不是本轮代码回归。

## 真实官方路径验证

验证时间为北京时间 2026-08-08；调用每份 bot 的 `_call_build_v11_daily(current_bj_date, "confirmed", now_bj)`，未 monkeypatch loader、日历或新鲜度检查，未用 CNFin raw 替换正式 qfq 结果。

### V1.1

- 状态：成功
- 请求结束日：2026-08-08；实际最后交易日：2026-08-07
- 日度输出：3,560 行，2011-12-09 至 2026-08-07
- 数据源/调整：AkShare Eastmoney qfq；Tencent qfq（含已对 Eastmoney fqt=1 验证的 day 响应）；均为 `qfq/front-adjusted`
- 活跃标志：`v1_1_staged_50_plus_ma60_overheat`，R²=0.2，target-vol=0.25，switch buffer=1.05，单边成本=0.001，盘后固定价执行关闭

### V1.3

- 状态：成功
- 请求结束日：2026-08-08；实际最后交易日：2026-08-07
- 日度输出：4,762 行，2007-01-04 至 2026-08-07
- 数据源/调整：Yahoo adjusted close（total-return）、AkShare 创业板价格指数、Tencent qfq；动态资产从各自首个可用日并入
- 活跃标志：`v1_3_kmlm_soy_cash3_nav_overheat`，R²过滤关闭，target-vol关闭，switch buffer=1.15，单边成本=0.001，盘后固定价执行关闭

## 保留的策略边界

- SELL 腿在没有券商可卖数量验证时继续 fail-closed。
- V1.3 的混合市场日期对齐、中国长假压缩及 live 盘前/隔夜估算只增加披露，不修改回测信号或执行时点。
- 强制报告窗口继续使用 252/756/1260/2520 个交易行；所有展示仍须包含 full、10Y、5Y、3Y、1Y，历史不足时给出明确 N/A 原因。
- 未删除死代码，未重写主策略状态机，未引入新数据源或新正式策略结果。
