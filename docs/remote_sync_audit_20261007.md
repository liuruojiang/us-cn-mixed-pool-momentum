# 两轮审计修订的 GitHub 同步（2026-10-07）

根据用户“做好远端同步”的授权，同步正式六 ETF V1.3 的两轮修订、5 份新增测试、审计报告、真实行情快照、对抗反例及 XML／CSV／PNG 证据。

目标为 [`liuruojiang/us-cn-mixed-pool-momentum`](https://github.com/liuruojiang/us-cn-mixed-pool-momentum) 的既有分支 `codex/previous-research-sync-20260821`。沿用该分支的普通提交及非强制推送；不合并 main。同步前本地与远端均为 `5ddedd4d20dd5472058a17137255aeffb1849367`，没有额外远端提交需要处理。最终发布提交以该分支的 Git 记录及推送后的 SHA 核对为准。

## 已验证内容

- 正式脚本仍为 SHA256 `e6934e11f76fb5b35a0b7ec61401189735710d96735d3431d9f7be1dd30af881`；同步准备没有修改交易规则或脚本逻辑。
- 两轮累计验收为 690 个唯一测试通过、1 个可选网络测试跳过。同步时额外从暂存区文件生成独立的 140 文件验证副本，在不同目录实际运行新增的全部 **124 项测试，124 passed／1 warning**；不是新增 124 个独立测试，也不冒充 GitHub 托管 runner。
- 独立副本中的数学／证据重算及交付核验通过，没有读取原工作目录的备份或价格。验证所用日历是已同步真实归档的一份运行时副本，不是新下载，也不替代正式日历刷新。
- 第一轮和第二轮真实下载 manifest 各列明的 15 个文件在暂存区 hash 全匹配；源码及冻结证据暂存字节与本地原文件相同。新增 `.gitattributes` 规则保留两轮审计目录及源码快照的字节和换行，不改写历史诊断 traceback 的空白。
- 新增文件未超过 50 MiB；未检出所检查的私钥、GitHub token、AWS access-key 模式。检查不打印可能的凭据值。

证据见 [`staging_manifest.json`](../outputs/audit_sync_20261007/staging_manifest.json)、[`staged_subset_tests.xml`](../outputs/audit_sync_20261007/staged_subset_tests.xml) 和 [`isolated_validation.json`](../outputs/audit_sync_20261007/isolated_validation.json)。暂存清单记录的是导出验证副本时的集合，之后只补充同步说明及验证结果，正式源码不变。

## 在新检出目录复现

本机 `.codex_backups/` 继续由 Git 忽略。另保存两份必要的、逐字节验证的审计源码输入：

- [修改前 b49 源码](../outputs/audit_sync_20261007/source_snapshots/before_first_audit.py)：SHA256 `b49c86944f0ef843f0eb23eebe396122fee0db5a90c6250789f21b3d110df988`。
- [第一轮修复后 7a 源码](../outputs/audit_sync_20261007/source_snapshots/before_doublecheck.py)：SHA256 `7a4cf15ff1603764dbf3469aab9b85f33756c98129116b4ce7dedb46eb48e1e3`。

新检出后先运行以下准备，再按两份审计报告的命令复核：

```powershell
python -X utf8 -B outputs/audit_sync_20261007/restore_audit_snapshots.py
python -X utf8 -B outputs/doublecheck_script_audit_20261007/evidence_recompute.py
python -X utf8 -B outputs/doublecheck_script_audit_20261007/verify_delivery.py
```

恢复工具只从上述已验 hash 的两份源码建立所需的本地恢复点；已存在但内容不同的文件会保留并报错，绝不覆盖。独立证据核验的旧绝对路径仅作为来源记录，实际读取当前检出目录的对应冻结文件，避免依赖原机器路径。

[第一轮审计](subd_six_etf_v1_3_script_audit_20261007.md)与 [Double-check 补修](subd_six_etf_v1_3_script_doublecheck_20261007.md)保留各自版本、运行时间和认证边界。本次 GitHub 同步不包括 Poe 托管端部署、订单提交、策略参数晋级或实盘成交认证。
