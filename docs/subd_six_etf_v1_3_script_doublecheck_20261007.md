# 六 ETF V1.3 上一轮审计的独立 Double-check（2026-10-07）

复核与补修完成。三个新的独立 Agent 分别挑战数据修复、执行／报告边界和审计证据。**上一轮 14 类缺陷及其数值、测试证据得到支持，但审计完整性被三个新增反例推翻；三处遗漏均已补修并复测。** 正常真实输入上的正式参数、持仓、换手、费用、逐日净值和五窗口结果保持一致。

审计对象仍为 [`poe_subd_six_etf_v1_3_bot.py`](../poe_subd_six_etf_v1_3_bot.py)。最终累计 **690 个唯一测试通过、1 个可选网络测试跳过**：全仓运行 685 passed／1 skipped／1 warning；收集完成后追加的 5 个数据保护测试另行实跑通过。不是虚构的一次 690 项运行；合并 XML 只追加实际通过且原全仓 XML 未包含的 testcase。详见 [`delivery_verification.json`](../outputs/doublecheck_script_audit_20261007/delivery_verification.json) 与 [`verification_combined.xml`](../outputs/doublecheck_script_audit_20261007/verification_combined.xml)。警告仍为 fastapi_poe/Pydantic 的已有弃用提示。

## 版本与回滚

- 上一轮待复核源码 SHA256：`7a4cf15ff1603764dbf3469aab9b85f33756c98129116b4ce7dedb46eb48e1e3`。
- 本轮最终源码 SHA256：`e6934e11f76fb5b35a0b7ec61401189735710d96735d3431d9f7be1dd30af881`。
- 本轮修改前的完整恢复点：[`../.codex_backups/20261007_200248/poe_subd_six_etf_v1_3_bot.py`](../.codex_backups/20261007_200248/poe_subd_six_etf_v1_3_bot.py)，与待复核 SHA256 一致；保留第一次修改前的 b49 备份。
- [第一轮报告](subd_six_etf_v1_3_script_audit_20261007.md)及旧证据保留；首段补充精确的 37／22 测试划分，并明确指向本轮补修。未改变 V1.1、mixed-pool V1.3 或研究参数。

## 被证实的三处遗漏

所有增删日期、坏价格和翻页顺序均为标明诊断的故障注入，使用真实冻结价格证明代码行为；不表示真实供应商在本次下载出现这些故障。

| ID／级别 | 上一轮未覆盖的反例及影响 | 最终处理 |
| --- | --- | --- |
| DC01／P1，扩展 D05 | 日历检查从六只都有历史的 2019-12-05 开始，早期 Full 样本不受检查。删除真实 2012-06-11，正式构建仍返回，持仓 1 行不同，终值 NAV 错增 0.415197；删除该年 6 月全部 20 个真实交易日，持仓 4 行不同、终值 NAV 错增 0.473232。插入早期周末或节假日也进入 daily，污染交易日计数及年化。 | 按首个任意资产已有真实价格的日期至 `common_last` 校验任意资产行情日集，拒绝整池缺日／非交易日；保留上市前 NaN 和单资产真实缺价的前填政策。 |
| DC02／P2，扩展 D03 | 主源只多一个周末或已知节假日，完整正常 Tencent 备用未调用。早期假 bar 被接受，较晚假 bar 则到对齐才失败，使可恢复的数据故障终止查询。 | provider 固定拒绝周末，中心接收前复用现有日历检查多余日期；失败进入原 qfq 备用链。日历从第一份合法候选实际首日读取，正常仅一次，后续更早历史才扩展；`None`／空日历保留原 required 保护。未要求单资产天天有价格，未新增数据源或缺价阈值。 |
| DC03／P2，修正 D02 的排序边界 | 2,560 个真实观察值分成四个完整 640 行页，合法尾部空页；升序页通过，同数据每页倒序却被误拒，因为 `rows[0]` 并非累计最早日期。已有推进和最终排序代码本来支持页内倒序。 | 空页终止判断使用累计日期最小值。提前空页／重复页仍拒绝。已保存实际腾讯响应为升序，此项只认证排序边界的诊断反例。 |

故障影响的原始实跑见 [`data_probe_results.json`](../outputs/doublecheck_script_audit_20261007/data_probe_results.json)；分工报告见 [`data_findings.md`](../outputs/doublecheck_script_audit_20261007/data_findings.md)。首日覆盖锚点不能独自证明完整单资产历史；长期单资产缺日与真实停牌需要独立数据才能区分，本次保留此边界。

## 原审计证据是否可靠

独立证据 Agent 未导入上一轮数学 probe，也未用正式评分、持仓或绩效函数产生独立结果。用矩阵加权最小二乘、ETF 份额／现金账本和 NAV 比率另算，见 [`evidence_findings.md`](../outputs/doublecheck_script_audit_20261007/evidence_findings.md)。

- 原报告的 14 类问题每类都对应至少一个修改前失败、修改后通过的真实 testcase；新增 59 项为 **37 项原失败＋22 项原已通过的对照／保护复测**。625 是全仓计数，不是 625 个正式六 ETF 缺陷。
- 原最终 XML 确为 625 passed／1 skipped／0 failures／0 errors，首次临时目录初始化错误没有被算成脚本 bug。
- 原 manifest 列明的 15 个文件 hash 全匹配（另有 manifest 本身，共 16 个文件）；source 表与 raw 价格首尾、行数、代码相符。腾讯／新浪的实际 60 对近期价格一致，并与正式面板一致。
- 9/24 同输入修复前后全部 104 个数据列逐值相同；两批共 10 个窗口的独立年化与回撤相符。9/30 独立账本持仓、候选、换手、成本零差异，NAV 最大浮点差 `8.53e-14`。
- 原 `data_probe_results.json` 是修改前归档。复现第一轮缺陷使用原报告的 `verify_before_regressions.py` 与 b49 备份；默认导入当前源码的旧 probe 不能冒充完整重现旧 JSON。本轮 `evidence_recompute.py` 已固定到 7a 恢复点，实际重跑通过；旧 57 份证据集合及 hash 不变。

## 修复后的验证

本轮新增 65 项：数据 27 项、执行／报告 38 项。数据同一批 27 项在 7a 备份上为 **9 failed／18 passed／0 error**，最终 27 passed；38 项执行／报告独立挑战没有推翻 E01–E06，最终全仓运行中也通过。涵盖真实查询范围、非法输出数据、单资产收盘元数据、未来 bar、混合刷新竞态及缓存副本隔离。额外 2,592 次已有年月语法枚举无差异，保留其当时版本与 JSON，未发明小数月份语义。见 [`execution_findings.md`](../outputs/doublecheck_script_audit_20261007/execution_findings.md)。

主 Agent 在 9/30 真实快照上分别运行 b49、7a 与最终源码的正式构建链，仅替换下载为同一真实输入、日历使用归档副本；正常持仓、费用、换手和净值逐值一致。另独立重算评分／账本，并检查 9 个历史前缀及完整 mask 截止日期，均通过。见 [`math_replay_result.json`](../outputs/doublecheck_script_audit_20261007/math_replay_result.json)。数据 Agent 还经实际 AkShare parser → 中心校验 → 对齐 → 正式 engine 完整回放，2 个原有填价标记和五窗口结果保持一致，见 [`data_current_replay_results.json`](../outputs/doublecheck_script_audit_20261007/data_current_replay_results.json)。

最终源码于 **2026-10-07 20:16–20:18（北京时间）** 再次实际走正式下载链，得到 **3,597 行、2011-12-09～2026-09-30**，六只均来自既有接受的 Tencent qfq／已验证 day-key。随后六种本地 Poe 兼容查询共用该次实际构建结果，生成报告及 PNG／CSV。日历可用、信号有效，当前休市状态禁止执行。没有把冻结反例或不同下载混成同一次结果。见 [`final_network/manifest.json`](../outputs/doublecheck_script_audit_20261007/final_network/manifest.json)。交付验证核对新旧真实下载的 raw、daily 和五窗口表全部列相同。

| 窗口 | 实际区间 | 年化收益 | 最大回撤 |
| --- | --- | ---: | ---: |
| Full | 2011-12-09～2026-09-30 | 30.56% | -22.01% |
| 10Y | 2016-05-19～2026-09-30 | 36.23% | -16.31% |
| 5Y | 2021-07-22～2026-09-30 | 55.58% | -15.96% |
| 3Y | 2023-08-18～2026-09-30 | 65.36% | -14.34% |
| 1Y | 2025-09-16～2026-09-30 | 63.68% | -13.87% |

数字来自最终同次正式模型输出 [`window_metrics.csv`](../outputs/doublecheck_script_audit_20261007/final_network/window_metrics.csv)。规则仍为 WLS25、严格 `0.5 < Score < 5.5`、R²≥0.25、筛选后 Top1、一次全额建仓、Buffer=1、最大杠杆 1、单边成本 0.001、现金收益 0，无分批／过热／目标波动率。窗口为尾部 N×252 行，首行 NAV 作基点，N−1 次变化年化；旧仓拥有当日 close-close 收益，新仓从下一行开始，纸面同收盘成交。Full／10Y 是可用资产逐步加入的模型，不是固定六只共同存续期或实际账户表现。

## 复现与边界

新检出目录需先按[远端同步记录](remote_sync_audit_20261007.md)恢复已验证的 b49／7a 源码输入；原本机备份目录不直接上传。

```powershell
New-Item -ItemType Directory -Path .\outputs\tmp -Force | Out-Null
python -X utf8 -B -m pytest tests -q -p no:cacheprovider --basetemp=outputs/tmp/doublecheck_recheck --junitxml=outputs/doublecheck_script_audit_20261007/full_suite_recheck.xml
python -X utf8 -B outputs/doublecheck_script_audit_20261007/evidence_recompute.py
python -X utf8 -B outputs/doublecheck_script_audit_20261007/verify_math_and_replay.py
python -X utf8 -B outputs/doublecheck_script_audit_20261007/verify_delivery.py
git diff --check
```

全仓重跑现会收集全部新增 65 项；本次交付的组合 XML 保留真实分批运行依据。`capture_final.py` 为另行实际刷新入口；已保存的 final_network 是本次实跑，不需要刷新才能核验其 hash。所有媒体及任务临时文件均在 D 盘，未新增 C 盘媒体库。

结论限于本地脚本、真实输入计算、数据接受和报告行为。审计完成时未推送远端，后续 GitHub 同步由用户另行授权并记录在上述同步说明。未部署 Poe 托管端、创建订单或晋级策略参数；全历史点时公司行动、真实停牌／涨跌停／T+1／容量、券商持仓与可卖数量、实际成交仍未因此获得认证。
