# 六 ETF V1.3 修复交付、同步与清理（2026-10-24）

用户授权合并、提交、同步本轮修复，并清理无用测试文件。目标仓库为 [`liuruojiang/us-cn-mixed-pool-momentum`](https://github.com/liuruojiang/us-cn-mixed-pool-momentum)，目标分支 `main`。

## 集成范围

- 同步前本地与远端 `main` 都为 `14a74c21e1f64e6c2605d29021580e9c5242588a`。已刷新远端并检查所有本地、远端分支，没有尚未合入 `main` 的提交；无需制造重复合并。
- 纳入本轮正式六 ETF V1.3 修复、50 项新增回归测试、旧节假日测试夹具修正、两轮独立审计及失败/通过证据。有效测试不作为垃圾删除。
- 正式源码 SHA256 保持 `8354e9c4b835c77f11809d5d0b727f54e75e7f7bc5a1fc5aa282ccb73bfd1f57`；最终全仓验收为 **740 passed / 1 skipped**，同输入 3,597 行 × 105 列完全一致，详见[修复审计报告](subd_six_etf_v1_3_repair_audit_20261024.md)。
- 新增两份可移植审计源码快照，并保留其原始字节；不是将整个本地备份目录提交到 Git。`.gitattributes` 保护证据与被清单引用文件的换行和哈希。
- 代码与证据同步不代表 Poe 托管部署、策略参数晋级或订单执行。

## 新检出目录复现

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -X utf8 -B outputs/audit_sync_20261007/restore_audit_snapshots.py
python -X utf8 -B outputs/audit_sync_20261024/restore_audit_snapshots.py
python -X utf8 -B outputs/repair_audit_20261024/verify_delivery.py
python -X utf8 -B -m pytest tests/test_v13_repair_20261024.py tests/test_v13_postfix_data_20261024.py tests/test_v13_postfix_reporting_20261024.py -q -p no:cacheprovider
```

恢复工具先核验源码 hash，仅创建缺失的快照；已存在但内容不同时停止，绝不覆盖。数学脚本可以在独立验证副本中运行：`outputs/repair_audit_20261024/math/final_8354e9c4/independent_math_audit.py`。它会重写该副本的数学产物，因此应先核验原归档清单，不能把重跑后的文件当成原次运行字节。

已从暂存区导出 400 文件独立副本，在独立目录恢复四份源码快照并核验交付；50 项新增测试全部通过（91.38 秒、1 个已有第三方警告），数学独立重算再次确认 3,597 × 105 exact parity、7 个前缀及成本单调性。未读取原工作区备份；不是新增 50 项独立测试，也不是 GitHub 托管 runner 验收。结果见[独立验收](../outputs/audit_sync_20261024/isolated_validation.json)、[测试 XML](../outputs/audit_sync_20261024/isolated_tests.xml)及[数学重算结果](../outputs/audit_sync_20261024/isolated_math_result.json)。

本次按用户授权向 `main` 作普通提交及非强制推送；发布版本以 `main` 提交历史及推送后的远端 ref 核对为准。暂存导出清单记录验证时的集合，后续只补充本文和同步验收证据，正式源码不变。

## 清理结果与阻塞

- 已逐路径核对 19 个临时/缓存目录，确认全部位于本工作区，未包含 Git 已跟踪文件；共 388 个普通文件，22,484,955 字节（约 21.44 MiB）。
- 已在工作区外生成并逐文件核验恢复包：`D:\Codex\repository-sync\20261024-us-cn-mixed-pool\cleanup_backup.zip`。路径、文件 hash 与归档 hash 见[清理记录](../outputs/audit_sync_20261024/cleanup_record.json)。
- **物理删除未完成，删除数为 0。** 自动审批审查在命令启动前返回 `blocked by policy`，未给出更具体原因或正式解除渠道。依照工作区规则停止全部目标，没有换命令、工具或脚本绕过；原文件均已核对仍存在。
- 上轮已经被拒绝的 `outputs/adversarial_audit_20261024/pytest_tmp/` 及三个 `2026-09-26_2026-09-24_signal.txt`、`2026-09-26_2026-09-25_signal.txt`、`2026-09-27_2026-09-24_signal.txt` 也原地保留，没有重试。
- 测试工作目录加入 `.gitignore`；三个未纳入审计证据的旧诊断文本仅加入本机 `.git/info/exclude`。这仅避免临时文件混入提交，**不是物理删除**。Git 状态干净不代表上述文件已经消失。
- 正式回归测试、冻结行情、审计失败/通过记录、研究结论与恢复点均保留。物理清理仍需用户通过获准的本机文件管理渠道处理；本次不声称已完成。
