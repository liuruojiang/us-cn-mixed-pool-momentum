# 六 ETF 朴素版 V1.3 脚本全面审计与修复（2026-10-07）

> **同日后续 Double-check：**本记录保留第一轮 7a 源码及证据。三个新的独立 Agent 支持下述 14 类问题的实跑证据，但发现三个遗漏边界，已在 e693 源码补修；累计 690 个唯一测试通过。当前源码、最新正式构建和本轮回滚见[独立复核与补修记录](subd_six_etf_v1_3_script_doublecheck_20261007.md)。

本地第一轮修复完成。主 Agent 与三个独立 Agent 对最新正式六 ETF V1.3 的计算、数据、执行和报告链进行对抗审计，确认并修复 **14 类脚本缺陷，其中 2 类为 P1 历史截断风险**。新增 59 项回归／防护测试：37 项缺陷反例在修改前失败，另有 22 项已通过的对照／保护复测；修改后全仓库 **625 passed、1 skipped、1 warning**。正式参数和正常历史交易路径未变。

审计对象是 [`poe_subd_six_etf_v1_3_bot.py`](../poe_subd_six_etf_v1_3_bot.py)，Poe 名称 `SubD-Six-ETF-Naive-V13`，不是历史混合代理池 V1.3。本次只修改该正式脚本，保留原 V1.1、mixed-pool V1.3 和研究候选。审计阶段未部署 Poe、推送远端或提交订单；后续用户授权的 GitHub 同步见[同步记录](remote_sync_audit_20261007.md)。

## 代码与恢复点

- 起始工作区干净，基线 commit：`5ddedd4d20dd5472058a17137255aeffb1849367`。
- 修改前源码 SHA256：`b49c86944f0ef843f0eb23eebe396122fee0db5a90c6250789f21b3d110df988`。
- 修复后源码 SHA256：`7a4cf15ff1603764dbf3469aab9b85f33756c98129116b4ce7dedb46eb48e1e3`。
- 可恢复备份：[`../.codex_backups/20261007_163920/poe_subd_six_etf_v1_3_bot.py`](../.codex_backups/20261007_163920/poe_subd_six_etf_v1_3_bot.py)，备份 manifest 同目录。
- 本次证据集中在 [`outputs/script_audit_20261007`](../outputs/script_audit_20261007/)。旧价格、决策、研究曲线均保留。回放工具使用任务内日历副本；旧日历归档恢复为审计开始前的 Git 状态。

## 缺陷与最终处理

下表中的反例均已实际运行。故障注入只用于证明脚本行为，不作为行情或策略收益。

| ID | 级别 | 已证实问题与影响 | 最终修复 |
| --- | --- | --- | --- |
| D01 | P1 | 主源只返回最后 20／640 行仍成功，完整备用源未调用。20 行反例使正式 daily 起点从 2011-12-09 缩至 2013-07-29，并令最新创业板 ETF 评分缺失。 | 每个 provider 接收前验证日期、正价、评分行数及既有已验证历史首日；失败进入原备用链。 |
| D02 | P1 | 腾讯第二页提前为空或重复第一页时静默返回 640 行，丢弃 2011–2024 历史。 | 校验逐页日期和请求范围、分页进展与最终覆盖；拒绝局部历史。 |
| D03 | P2 | 重复日、NaT、常量 0／Inf 未在主源接收前正确回退；NaT 会在日期切片时静默消失。 | AkShare／Eastmoney 在裁剪前校验，生成来源记录成功后才同步加入价格与记录。 |
| D04 | P2 | 对齐 helper 把坏文本转为 NaN 后前填，却漏记填价标记。正式 parser 已拒绝普通坏文本，此反例限定于 helper 合同。 | 非空非数字价格直接报错，保留真实缺价的既有填价语义。 |
| D05 | P2 | expected 日历为空集合时跳过检查，短窗口内休市假 bar 被接受。 | 空日历集合也检查多余非交易日。 |
| D06 | P2 | 远端日历为 None 时不使用已有可信官方 2026 后备，国庆休市日被显示为普通工作日。原逻辑已禁止执行。 | None／空集合也尝试官方后备，超出其覆盖或全部日历失败仍关闭执行。 |
| D07 | P2 | 正常缓存命中允许负年龄，即晚于当前时刻的缓存。 | 要求 `0 <= age <= TTL`。 |
| M01 | P2 | 历史截止日期只截价格、不截填价 mask，合法完整快照回放报错；空截面错误不明确。 | 校验完整价格与 mask 后同步裁剪，并明确拒绝空截面。 |
| E01 | P2 | 单日、无数据日或无交易日查询因绩效 N/A 回退至全历史交易记录。 | 记录表／CSV始终过滤请求窗口；空范围保持空表。文件名采用该窗口实际可用日度数据边界。 |
| E02 | P2 | 年度、净值图／CSV及交易记录 CSV 绕过共同校验，重复日或非法 NAV 仍出数。 | 三处入口统一日期唯一和数值合法性校验。 |
| E03 | P2 | 正式准备函数不剔除单行未确认 bar；有多条未来／未确认尾行时只剔除一条。 | 持续剔除所有未确认尾行，剔空明确报错。 |
| E04 | P2 | `2001-06至今` 被年月日短正则截成 2026-01-06；`2026-06至今` 报错。 | 限制 MM-DD 的前置数字／日期边界，保留年月正确解析。 |
| E05 | P2 | `过去0.5年` 未识别，默默使用默认范围。 | 相对窗口捕获已有数字解析器支持的小数，半年为六个月。 |
| E06 | P2 | 较早启动的并发强制刷新后完成，覆盖较新请求已写入的缓存。 | 缓存写入比较请求时点，每个请求保留自身返回结果。 |

覆盖锚点 `VERIFIED_HISTORY_FIRST` 来自既有真实源表 [`sources_formal_loader.csv`](../outputs/recert_l1_20260926/sources_formal_loader.csv)，代表已经验证存在的最低历史覆盖，**不是 ETF 上市日**。没有增加正式数据源，没有把原始未复权 fallback 接入正式路径，也没有改变单资产缺价支持 NAV 连续、填价交易腿禁止成交的政策。

## 独立计算与同输入核验

正式链保持 25 日线性加权对数回归、严格 `0.5 < Score < 5.5`、`R² >= 0.25`、筛选后 Top1、一次全额建仓、Buffer=1、无杠杆／目标波动率／过热／分批，现金收益 0，单边综合成本 0.001。

独立数学 Agent 在真实 3,594 行快照（2011-12-09 至 2026-09-24）上，以加权 covariance 公式及 ETF 份额／现金账本重新计算，未复用正式评分和持仓函数。候选、持仓、填价阻止、换手及费用逐行零差异；NAV 最大误差 `8.53e-14`，Score 最大误差 `1.36e-12`，R² 最大误差 `6.66e-16`。四个历史前缀通过无未来行依赖检查，成本进入净收益，且同持仓路径成本后 NAV 不超过无成本 NAV。见 [`math_evidence.json`](../outputs/script_audit_20261007/math_evidence.json)。

另以修复前备份与最终源码走相同正式构建链，仅将下载替换为已验证的原始 qfq 快照；价格对齐、填价 mask、计算、bar 元数据及正式指标函数仍由各自源码执行。**持仓、收益、NAV、换手、成本和买卖腿全部零差异，五窗口年化及最大回撤也完全一致**。见 [`same_input_replay.json`](../outputs/script_audit_20261007/same_input_replay.json) 和 [`same_input_window_metrics.csv`](../outputs/script_audit_20261007/same_input_window_metrics.csv)。这是冻结输入修复核验，不冒充最新行情。

## 当前真实数据与输出

2026-10-07 16:55–16:56（北京时间）使用最终源码，实际走未改动的正式下载备用链、对齐及构建流程，得到 3,597 行，2011-12-09 至 **2026-09-30**。六只来源均为正式接受的 Tencent qfq／已验证 day-key。原始面板、来源表、日曲线、查询正文、PNG／CSV和 SHA256 均见 [`current_network/manifest.json`](../outputs/script_audit_20261007/current_network/manifest.json)。Poe兼容 UI 检查复用这一次新鲜正式构建结果，没有把旧快照或多个数据运行拼接。

当前同次运行的五窗口纸面结果如下，详见 [`window_metrics.csv`](../outputs/script_audit_20261007/current_network/window_metrics.csv)：

| 窗口 | 实际区间 | 年化收益 | 最大回撤 |
| --- | --- | ---: | ---: |
| Full | 2011-12-09～2026-09-30 | 30.56% | -22.01% |
| 10Y | 2016-05-19～2026-09-30 | 36.23% | -16.31% |
| 5Y | 2021-07-22～2026-09-30 | 55.58% | -15.96% |
| 3Y | 2023-08-18～2026-09-30 | 65.36% | -14.34% |
| 1Y | 2025-09-16～2026-09-30 | 63.68% | -13.87% |

Full／10Y仍是资产随可用历史逐步加入的模型结果，不能当作固定六只共同存续期或实际账户表现。窗口按尾部 N×252 行，首行已形成 NAV 为基点，以 N−1 次变化年化；旧持仓拥有当日 close-close 收益，新仓从下一行开始，纸面同收盘成交，单边成本 0.10%，现金收益 0。未加入新基准。

数据 Agent 独立取得腾讯与新浪六只最近 10 个完整交易日（09-16～09-30）的价格，60 组日期／收盘价完全一致，最大绝对差 0。原始 payload 和首轮超时后的单次恢复证据见 [`data_recent_final_comparison.json`](../outputs/script_audit_20261007/data_recent_final_comparison.json)。近期同价不重新认证整个历史 qfq 的公司行动或点时语义。

今天为国庆休市，正式信号显示上一交易日确认收盘，`calendar_available=True`、`signal_valid=True`、`tradable=False`。交易所安排来源：[上交所 2026 节假日公告](https://www.sse.com.cn/disclosure/announcement/general/c/c_20251222_10802507.shtml)。实际本地查询检查包括参数、信号、表现、单日交易记录、休市日空交易记录及早年起始范围；实时信号／实时参数、盘口和异常分支另由真实历史输入及明确故障注入验证，没有宣称今天完成交易时段实时成交验收。

## 验收、复现与边界

原测试基线为 566 passed／1 skipped。新增 59 项测试包括真实冻结价格故障注入、确定性并发反例、精确日期／范围检查及 14 项关键执行保护；修复后完整测试为 **625 passed／1 skipped／1 warning**，见 [`full_suite_after.xml`](../outputs/script_audit_20261007/full_suite_after.xml)。跳过项是可选七查询全网络测试；本次另行完成上文正式真实下载与六查询本地 UI 检查。警告为 fastapi_poe/Pydantic 的既有弃用提示。

同一批 59 项反例另在修复前备份源码上完整重跑，结果 **37 failed／22 passed／0 error**；最终源码上这 59 项全部通过。修复前实跑 XML见 [`new_regressions_before.xml`](../outputs/script_audit_20261007/new_regressions_before.xml)，该运行不修改正式源码，避免把源码推断或新增断言本身冒充已复现缺陷。

首轮全套复测的 D 盘临时目录父级未创建，35 项 fixture 初始化失败，已有测试本体没有失败；补齐父目录后完整重跑通过，原日志保留在 `full_suite_setup_error.xml`。旧研究归档不因审计回放被改写；本次完整测试产物、媒体附件和正式证据保存在 D 盘，两个初次测试留在 C 盘临时目录的自有 PNG 已移除。

```powershell
New-Item -ItemType Directory -Path .\outputs\tmp -Force | Out-Null
python -X utf8 -B -m pytest tests -q -p no:cacheprovider --basetemp=outputs/tmp/script_audit_20261007_tests_recheck --junitxml=outputs/script_audit_20261007/full_suite_recheck.xml
python -X utf8 -B outputs/script_audit_20261007/verify_before_regressions.py
python -X utf8 -B outputs/script_audit_20261007/verify_replay.py
python -X utf8 -B outputs/script_audit_20261007/math_probe.py
python -X utf8 -B outputs/script_audit_20261007/capture_current.py
git diff --check
```

详细分工与反例分别见 [`data_audit_findings.md`](../outputs/script_audit_20261007/data_audit_findings.md)、[`execution_report_findings.md`](../outputs/script_audit_20261007/execution_report_findings.md) 及三个 `tests/test_v13_audit_*_20261007.py`。

结论限于本地脚本正确性、同输入计算及当前数据／报告路径。Poe 托管端发布、券商持仓和可卖数量接入、实盘成交、全历史逐笔停牌／涨跌停／T+1／容量、公司行动点时数据都未因此取得认证。正式同收盘模型假设保留；含 SELL 腿仍需要已验证可卖数量，实际交易必须另行核对。
