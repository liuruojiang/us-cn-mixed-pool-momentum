# 六 ETF V1.3 接手后的独立多智能体对抗测试

日期：2026-10-24，Asia/Shanghai。本轮完成审计，确认 **2 个 P2 缺陷，尚未修复**。7 个失败反例归并为 2 个根因；不能将原有测试通过或数学一致性当作本轮整体通过。

## 对象与交接

- 已读取同项目对话「对最新版本开展多智能体对抗测试」（`01a16c6f-1660-7b90-9452-edcfa27dd5c6`），核对其修复、提交与清理阻塞记录。
- 当前提交：`f1fe6ac989e21c60b230cd75ad0949bad1a45cf3`。
- 正式入口：`poe_subd_six_etf_v1_3_bot.py`，六只中国上市 ETF 朴素版，不是旧 mixed-pool V1.3。
- 源码 SHA256：`8354e9c4b835c77f11809d5d0b727f54e75e7f7bc5a1fc5aa282ccb73bfd1f57`。
- 本轮未修改正式代码、参数或任何原已跟踪文件，未提交、推送、部署或下单。新增内容为测试、复现证据、本报告及手动清理工具。

三个子 Agent 分别独立检查数据/日历、执行状态/报告、数学/时序/账本。主 Agent 阅读反例和实际源码，再统一实跑新增 32 项测试。上一轮结果仅作交接，本轮有独立执行证据。

## 已确认缺陷

| 编号 | 级别与位置 | 实际反例及影响 | 最小修复建议 |
|---|---|---|---|
| F1 | P2；`_recover_calendar_price_conflict`，2499–2501 行 | 行情和供应商日历都删去官方明确存在的 2026-09-22 时，对齐及正式 provider → load_close → `_build_v13_daily` 仍成功返回，漏日没有被检出。只在日历加入官方休市的 2026-01-01 时，真实完整行情又被错误拒绝。 | 在已有官方参考覆盖的 2026 区间始终核对会话集合，不仅在行情日期超出供应商日历时才核对；覆盖外保持原门禁，不能从价格日期反推交易日历。 |
| F2 | P2；`parse_all_date_ranges`，5239 行 | `交易记录 2024年，2025年` 及英文逗号形式只导出 2024 年 30 条，静默漏掉 2025 年 35 条。两个跨月区间以逗号分隔时，同样漏掉第二个窗口的 5 条。 | 扩充分隔符识别中英文逗号，保留非法日期拒绝、去重及各窗口独立导出；用正式处理器和附件验证，不能只测解析函数。 |

F1 的共同漏日反例需要两个输入同时异常；会影响日数及后续 25 日评分窗口，但本轮没有将注入后的数值当成正常策略收益。日历多报休市日的表现是可用性故障，不是误下单。F1 两种表现归于同一处提前返回。F2 的四个失败用例也只计一个根因。

所有异常均为真实冻结数据上的明确诊断注入，**未证明当前供应商存在这些故障**。源码已内置的 2026 官方参考用于独立于供应商输入的会话对照，本轮没有重新上网核验公告，也未扩大该参考的有效年份。

## 实跑验收及计数

| 检查 | 结果 | 证据 |
|---|---|---|
| 原有 741 项测试首跑 | 719 通过、1 跳过、21 环境设置错误 | [首跑日志](../outputs/takeover_audit_20261024/baseline.log)、[JUnit](../outputs/takeover_audit_20261024/baseline.xml) |
| 对上述 21 项精确补跑 | 21 全部通过 | [补跑日志](../outputs/takeover_audit_20261024/baseline_setup_rerun.log)、[JUnit](../outputs/takeover_audit_20261024/baseline_setup_rerun.xml)、[节点清单](../outputs/takeover_audit_20261024/baseline_setup_rerun_targets.json) |
| 原有测试按唯一节点合并 | **740 通过、1 跳过**，不是一次全仓全绿运行 | [汇总验收](../outputs/takeover_audit_20261024/verification.json) |
| 新增对抗测试，主 Agent 统一运行 | **25 通过、7 失败**，无设置错误 | [完整日志](../outputs/takeover_audit_20261024/adversarial.log)、[JUnit](../outputs/takeover_audit_20261024/adversarial.xml) |
| 正常输入全列一致性 | **3,597 行 × 105 列 exact parity** | [数学结果](../outputs/takeover_audit_20261024/math/result.json) |
| 独立 WLS、份额/现金账本、前缀和成本 | 通过；NAV 最大浮点差 `8.53e-14`，7 个前缀全部通过 | [数学说明](../outputs/takeover_audit_20261024/math/review.md) |

21 项首跑错误全部是本轮主 Agent 未预建 pytest 临时目录的父目录导致 `FileNotFoundError`，发生在夹具设置阶段；修正运行目录后按原断言补跑，没有修改测试或产品源码。原始失败证据保留，不算产品缺陷。已有 1 项可选网络测试跳过；Pydantic 弃用警告保留。

新增测试分支：数据 3 通过/3 失败，报告 16 通过/4 失败，数学 6 通过。新增数学不变量还覆盖真实换仓日旧持仓收益归属、零成本/较高成本账本、各资产价格单位变换、未来 200 行扰动、输入列顺序。报告正对照覆盖顿号/分号/和、非法日期、旧数据的不可执行状态、真实 PNG/CSV 与绩效的一致性，以及 CSV 上传失败明确标 N/A。

所有原有与新增节点合计 773 个：765 通过、7 失败、1 跳过，按独立运行和精确补跑去重汇总，不是一次 `pytest tests` 的运行结果。新增失败测试未标 xfail，保留为后续修复的验收门槛。

## 数据、口径与历史五窗口

完整数学复验使用 `outputs/doublecheck_script_audit_20261007/final_network/` 的 Tencent 前复权真实行情、来源表及正式日度快照，2011-12-09～2026-09-30，3,597 行。数学回放日历为 `outputs/doublecheck_script_audit_20261007/math_calendar_final.csv`；数据/报告分支使用 `outputs/script_audit_20261007/calendar_cache_for_replay.csv`。输入 hash 核验后沿正式构建链重放；新输出保存在本轮目录，没有覆盖原次证据。日历反例截取至 2026-09-24，共 3,594 行。

| 窗口 | 实际起止 | 行数 | 年化收益 | 最大回撤 |
|---|---|---:|---:|---:|
| Full | 2011-12-09～2026-09-30 | 3,597 | 30.56% | -22.01% |
| 10Y | 2016-05-19～2026-09-30 | 2,520 | 36.23% | -16.31% |
| 5Y | 2021-07-22～2026-09-30 | 1,260 | 55.58% | -15.96% |
| 3Y | 2023-08-18～2026-09-30 | 756 | 65.36% | -14.34% |
| 1Y | 2025-09-16～2026-09-30 | 252 | 63.68% | -13.87% |

表格来自本轮实际重算的[指标 CSV](../outputs/takeover_audit_20261024/math/window_metrics.csv)。这些是 **9 月 30 日截止的冻结历史模型**，不是 10 月 24 日最新表现。窗口沿正式 252 交易日口径，N−1 次净值变化；Full/10Y 为上市后逐步加入资产的可用池。

参数仍为 WLS25、严格 `0.5 < Score < 5.5`、R²≥0.25、筛选后 Top1、一次全仓、单边费用 0.001、现金收益 0；没有新增滑点。旧仓计当日 close-close 收益，同日收盘纸面换仓，新仓从下一行参与。费用按乘法扣减。未认证点时复权、真实涨跌停/停牌成交、T+1、容量或券商账户/订单；没有新基准比较或参数晋级。

## 复现

在仓库根目录执行，使用全新临时子目录；pytest 会管理其 basetemp，勿指向需要保留的目录：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
New-Item -ItemType Directory -Force outputs/takeover_audit_20261024/scratch | Out-Null
python -X utf8 -B -m pytest tests/test_v13_takeover_data_20261024.py tests/test_v13_takeover_reporting_20261024.py tests/test_v13_takeover_math_20261024.py -q -p no:cacheprovider --basetemp=outputs/takeover_audit_20261024/scratch/user_rerun
```

在当前未修复源码上，预期 25 passed / 7 failed。独立数学审计器位于 `outputs/takeover_audit_20261024/math/independent_math_audit.py`；再次运行会重写它所在目录的数学产物，复现时先另建副本并调整输出位置，勿覆盖本轮归档证据。

分支说明：[数据审计](../outputs/takeover_audit_20261024/data/findings.md)、[报告审计](../outputs/takeover_audit_20261024/reporting/findings.md)、[数学审计](../outputs/takeover_audit_20261024/math/review.md)。

## 最后一步：手动清理批处理

最终交付根目录的 `cleanup_takeover_tests_20261024.bat`。由用户双击运行，无需逐项输入编号；先核验本轮临时文件清单与 hash，再生成并逐文件校验 ZIP 恢复包，之后只删除清单内两个本轮 scratch 目录。失败会停下并保留窗口；文件内容或集合变化时拒绝删除。恢复包放在本项目 `.codex_backups/`。

范围：`outputs/takeover_audit_20261024/scratch/`、`outputs/takeover_audit_20261024/data/scratch/`，共 41 个普通文件，另有 17 个 pytest 自动创建的内部目录链接。脚本不沿链接递归，逐项核验链接目标后只移除链接本身；文件和链接清单一并保存在恢复包。正式回归测试、新增反例、历史行情、审计报告和失败/通过证据均保留。`--preview` 只读检查；本轮只验证预览入口和脚本语法，不执行删除，也不声称物理清理已经完成。实际范围与 hash 见 `outputs/takeover_audit_20261024/manual_cleanup_plan.json`，启动验收见 `outputs/takeover_audit_20261024/manual_cleanup_preview.json`。

**旧目标仍受阻：**另一个对话的自动审批曾以 `blocked by policy` 拒绝 19 个目录及另 4 个目标，未提供具体原因或正式解除渠道。按项目规则，本轮未重试删除，也不把这些目标放入替代删除脚本。它们仍原地保留，详见[原清理记录](../outputs/audit_sync_20261024/cleanup_record.json)。本批处理不能完成这些旧目标的清理。
