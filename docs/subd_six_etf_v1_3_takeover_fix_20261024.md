# 六 ETF V1.3 接手缺陷修复、验证与交付

2026-10-24，Asia/Shanghai。接手审计确认的两个 P2 缺陷均已修复。此前 7 个失败反例全部通过；修后一次全仓运行 **797 passed / 1 skipped**，没有失败或设置错误。三个独立 Agent 的数据、报告、数学复审均通过。

## 修复对象与恢复点

- 正式入口：`poe_subd_six_etf_v1_3_bot.py`，六只中国上市 ETF 朴素 V1.3。V1.1 与旧 mixed-pool V1.3 未改。
- 修复前提交：`f1fe6ac989e21c60b230cd75ad0949bad1a45cf3`；源码 SHA256 `8354e9c4b835c77f11809d5d0b727f54e75e7f7bc5a1fc5aa282ccb73bfd1f57`。
- 修复前完整字节快照：[before_fix.py](../outputs/takeover_fix_20261024/source_snapshots/before_fix.py)。已与该提交逐字节核对，可直接用于回退及同输入重放。
- 修后源码 SHA256：`daf96cf4b39ab2919c9e8b7d82e74f96177748a1f4c5a6be2da7b5637e4965ca`。
- AST 对比仅有 `_recover_calendar_price_conflict` 与 `parse_all_date_ranges` 两个函数变化。评分、筛选、持仓、成本、收益和窗口函数均未修改。

## 两项修复

1. **日历完整性与可用性。** 官方参考明确覆盖的 2026 区间始终核对会话集合，行情和供应商日历共同漏日不再逃过校验，日历多报休市日也不再误挡完整行情。真实假期/周末的伪造价格行仍被拒绝；参考覆盖外保留原供应商会话门禁，无日历仍关闭。只在此前支持的合法价格冲突下限次强刷；复核后的组合日历只驻内存，不冒充供应商原始缓存写盘。
2. **多区间导出。** 解析增加中英文逗号分隔，与顿号、分号、“和”“以及”兼容。`交易记录 2024年，2025年` 正确导出 30+35 条；跨月双区间正确导出 9+5 条。保留重复窗口去重、非法日期/逆序拒绝，以及每个请求区间独立表格和 CSV。

反例为真实冻结数据上的故障注入，并不证明当前远端供应商实际故障。未从行情反推交易日历，未扩展官方参考年份，未使用 QVeris。

## 实跑证据

| 检查 | 结果 | 证据 |
|---|---|---|
| 修后一次全仓测试 | **797 通过、1 跳过**，275.38 秒，1 个已有第三方弃用警告 | [日志](../outputs/takeover_fix_20261024/full_suite.log)、[JUnit](../outputs/takeover_fix_20261024/full_suite.xml) |
| 初轮相关回归 | 82 通过，含原 7 个失败反例 | [日志](../outputs/takeover_fix_20261024/targeted.log) |
| 数据独立复审 | 59 项相关既有测试、10 项新增边界均通过 | [数据复审](../outputs/takeover_fix_20261024/data/review.md) |
| 报告独立复审 | 原 20 项与新增 15 项均通过 | [报告复审](../outputs/takeover_fix_20261024/report_review/review.md) |
| 数学独立复审 | **3,597 行 × 105 列 exact parity**，独立 WLS/账本、7 个前缀、成本与持仓检查均通过 | [数学说明](../outputs/takeover_fix_20261024/math/review.md)、[结果 JSON](../outputs/takeover_fix_20261024/math/result.json) |
| 测试夹具可移植性 | Git 提取改为读取已核验的同字节快照，10 项再次通过 | [日志](../outputs/takeover_fix_20261024/portable_data.log) |

表中各组测试存在重叠，不累计成新的通过数。全仓 797 为一次运行的唯一通过数；仅 1 项已有可选网络测试跳过。全仓后只将配对测试的基线读取由 `git show` 改为已保留的同 hash 快照，业务断言未变，并重新运行该文件，便于无 Git 历史的交付包复现。正式源码 hash 始终未变。

旧失败报告与证据保留在 [接手审计](subd_six_etf_v1_3_takeover_audit_20261024.md) 和 `outputs/takeover_audit_20261024/`。为避免修后测试覆盖旧失败导出，只调整了报告测试的输出目录；旧测试原始字节保存在 [before_reporting_output_isolation.py](../outputs/takeover_fix_20261024/source_snapshots/before_reporting_output_isolation.py)，与旧 evidence manifest 中的 hash 一致。旧清单描述的是修复前时点，不能拿修后测试文件替代旧字节。

## 正常输入历史结果保持不变

真实输入为 `outputs/doublecheck_script_audit_20261007/final_network/` 的腾讯前复权原始价格、来源表与日度快照，2011-12-09～2026-09-30，3,597 行。数学回放使用同目录上级的 `math_calendar_final.csv`；数据分支使用 `outputs/script_audit_20261007/calendar_cache_for_replay.csv` 并截取至 2026-09-24（3,594 行）。核验输入 hash 后沿正式构建链重放，未重新下载行情。

| 窗口 | 实际起止 | 年化收益 | 最大回撤 |
|---|---|---:|---:|
| Full | 2011-12-09～2026-09-30 | 30.56% | -22.01% |
| 10Y | 2016-05-19～2026-09-30 | 36.23% | -16.31% |
| 5Y | 2021-07-22～2026-09-30 | 55.58% | -15.96% |
| 3Y | 2023-08-18～2026-09-30 | 65.36% | -14.34% |
| 1Y | 2025-09-16～2026-09-30 | 63.68% | -13.87% |

数值来自本次重算的[五窗口 CSV](../outputs/takeover_fix_20261024/math/window_metrics.csv)，不是 10 月 24 日最新业绩。252 交易日年化，窗口含 N−1 次净值变化；Full/10Y 为上市后逐步加入的可用池。WLS25、严格 `0.5 < Score < 5.5`、R²≥0.25、筛选后 Top1、一次全仓、单边费用 0.001、现金收益 0，均不变。旧仓计当日 close-close 收益，同收盘纸面换仓，新仓从下一行参与；无新增滑点。未认证点时复权、实际涨跌停/停牌成交、T+1、容量、券商账户或订单。

## 复现与同步

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -X utf8 -B outputs/audit_sync_20261007/restore_audit_snapshots.py
python -X utf8 -B outputs/audit_sync_20261024/restore_audit_snapshots.py
New-Item -ItemType Directory -Force outputs/takeover_fix_20261024/scratch | Out-Null
python -X utf8 -B -m pytest tests -q -p no:cacheprovider --basetemp=outputs/takeover_fix_20261024/scratch/user_replay
```

已从 Git 暂存区逐字节导出 14 个必要代码/数据文件到独立目录；不依赖原工作区备份或 Git 历史。该副本的 57 项新增测试全部通过，独立数学重算再次确认 3,597×105 完全一致。见 [独立测试](../outputs/takeover_fix_20261024/isolated_tests.xml)、[数学重算](../outputs/takeover_fix_20261024/isolated_math_result.json)、[交付核验](../outputs/takeover_fix_20261024/delivery_verification.json)。这不是 GitHub 托管 runner 验收。

同名 basetemp 会被 pytest 管理，复现时选择新的临时子目录，不指向归档证据。独立数学审计器位于 `outputs/takeover_fix_20261024/math/independent_math_audit.py`，会写本目录数学产物；需要重算时使用独立验证副本，避免重写归档。原始输入、修前快照、测试源码及审计证据均保留。

修复已按用户授权提交并推送到 `liuruojiang/us-cn-mixed-pool-momentum` 的 `main`：[5a217bf](https://github.com/liuruojiang/us-cn-mixed-pool-momentum/commit/5a217bf5836caab32a7923870ae77b34f5ea8234)。推送后再次 fetch 并核对远端 ref、本地 HEAD、origin/main 三者完全一致；远端源码字节 hash 与受测源码一致。见 [推送验收](../outputs/takeover_fix_20261024/repair_remote_verification.json)。现有分支没有必须合入的新增提交，没有重复合并、强推、Poe 托管部署或下单。README 与 TASK_STATE 已更新；清理结果与本段验收作为后续文档提交同步，正式源码不变。

## 清理边界

依照用户顺序，在修复验证、提交推送和远端核对完成后，已物理删除两轮审计的 **4 个新 scratch 目录、83 个普通文件（3,610,212 字节）及 34 个内部目录链接**。删除前创建 ZIP 恢复包并逐文件核验；删除后再验证恢复包 hash 和目录确实不存在，所有跟踪文件未受清理影响。恢复包位于本项目 `.codex_backups/`，完整路径和 SHA256 见 [清理验收](../outputs/takeover_fix_20261024/cleanup_result.json)，执行日志见 [cleanup_execution.log](../outputs/takeover_fix_20261024/cleanup_execution.log)。本轮新增 policy 拒绝数为 **0**。

仍有回归价值的测试源码、真实行情、失败/通过证据和恢复点保留。清理脚本 `cleanup_after_fix_20261024.bat` 已完成本轮用途，无需再次运行；其固定清单仅覆盖上述新临时目录，未包含旧受阻目标。

旧 23 个目标已经在另一个对话中被自动审批以 `blocked by policy` 拒绝，未给出解除渠道。本轮未重试这些删除，也未换删除脚本。已核验这 23 个旧目标仍存在，完整路径见 [剩余手动清理清单](../outputs/takeover_fix_20261024/manual_cleanup_remaining.json)；本机便于打开的文字清单为 `D:/Codex/repository-sync/20261024-takeover-fix-handoff/旧目标手动清理清单.txt`，供用户使用文件管理器处理。原 19 目录的恢复 ZIP 已在旧记录中核验，不能将另 4 项默认说成包含在该包内。旧记录见 `outputs/audit_sync_20261024/cleanup_record.json`。最终 Git 工作区干净与旧目标物理清理未完成分别记录。
