# 数据链独立二轮复核（2026-10-07）

上一轮 D01–D07 的修复有效，但 D03/D05 仍有边界遗漏，D02 引入一项分页顺序误拒。根 Agent 已统一补修，数据 Agent 在最终源码上独立复测通过。

本分工没有编辑生产源码、旧测试、上一轮报告或旧证据。新增测试为 `tests/test_v13_doublecheck_data_20261007.py`，新增证据保存在本目录。所有日期增删、坏价格和翻页顺序均为明确诊断故障注入；不主张当前供应商真实行情曾出现这些故障。

## 冻结基线与独立数据

- 待反证源码：`.codex_backups/20261007_200248/poe_subd_six_etf_v1_3_bot.py`，SHA256 `7a4cf15ff1603764dbf3469aab9b85f33756c98129116b4ce7dedb46eb48e1e3`。
- 根 Agent 补修后的复测源码：`poe_subd_six_etf_v1_3_bot.py`，SHA256 `e6934e11f76fb5b35a0b7ec61401189735710d96735d3431d9f7be1dd30af881`。
- 故障输入为真实 `outputs/recert_l1_20260926/prices_raw_qfq_through_20260924.csv.gz`，3,594 行、2011-12-09～2026-09-24，SHA256 `1e14b2c2eddfaeb42b0b802ab61650229c702a0657d3f4dd80cbd6b7dcbe3fc0`。
- 独立日期依据为既有 `calendar_cache_for_audit.csv` 中的 AkShare/Sina 交易日历。实际运行核对其对应区间与真实价格面板日期完全相等；没有把故障后面板自身当作应有交易日。日历只读，未写入旧证据。

## 已证实遗漏与影响

| 问题 | 基线源码位置 | 实际反例 | 影响与窄修复 |
| --- | --- | --- | --- |
| P1：完整样本前段交易日未校验 | `align_prices_to_common_valid_date`，原 2497–2503 附近 | 首共同日为 2019-12-05，校验只从该日起。删除 2012-06-11，或删除 2012 年 6 月全部 20 个真实交易日，正式 `_build_v13_daily` 均成功返回。插入 2012-06-09 周末、2012-10-01 假日也成功返回。 | 单日遗漏使 1 行持仓不同、终值 NAV 增 `0.4151974727517995`；整月遗漏使 4 行持仓不同、终值 NAV 增 `0.4732315657789954`。假 bar 即使不改变本例 NAV，也使 Full 年化从 `0.3043564408483703` 变为 `0.30426001139954284`。补修按首个任意资产真实行情日至 `common_last` 的任意资产行情日集验证，不要求尚未有历史的 ETF 提前有价。 |
| P2：非交易日主源未在备用选择阶段拒绝 | `_validate_historical_close` / `_load_public_close_with_per_code_fallback`，原 436 / 1301 | 完整 AkShare 输入仅增加一个周末或已知节假日，Tencent 保留正常完整真实数据；`load_close` 未调用备用。前共同期假 bar 进入 daily；后共同期 2026-09-19 或 2026-01-01 假 bar 到对齐阶段才报错。 | 正常备用可救的主源日期故障导致错误输出或整次查询失败。补修固定拒绝周末，中心 validator 复用现有有效日历，仅对供应商观察日期做 membership 校验。没有强制单资产日日有价。 |
| P2：完整倒序分页被误判为局部历史 | `_load_tencent_qfq_one_close`，原 542–544 | 使用前 2,560 个真实观察值，实际 640 页大小、四个完整页，再合法空页。升序页通过；同数据每页倒序失败。 | 空页检查以 `rows[0][0]` 当最早日期，与已有按日期最小值推进、最终排序的合同不一致。补修用累计日期最小值判断是否已到锚点。已保存的真实腾讯响应为升序；该项是排序边界的诊断反例，不冒充实际供应商改序证据。 |

上表 NAV 与收益数字仅用来说明被污染输入对正式脚本的影响，不能作为策略收益。本次未修改正式六 ETF、WLS25、Score、R²、Buffer、成本或执行参数。

## 验证结果

1. 首批 18 个独立新测试在 7a 基线上为 **5 failed / 13 passed**，证据 `data_second_audit_before.xml`。
2. 补入前共同期节假日、后共同期节假日和整月删除后，同一 22 项在固定 7a 备份上为 **9 failed / 13 passed / 0 error**，证据 `data_second_audit_expanded_before.xml`。初版 18 项证据保留。
3. 22 项与上一轮 20 个数据测试一起在根 Agent 首次补修上为 **42 passed**，证据 `data_second_audit_after.xml`。
4. 最终 lazy-calendar 源码再补 5 项保护用例，**27 个独立新测试全部通过**，证据 `data_second_audit_lazy_after.xml`。同一最终 27 项在固定 7a 基线重跑为 **9 failed / 18 passed / 0 error**，证据 `data_second_audit_final_before.xml`；没有把新加的保护合同算成旧 bug。新增检查包括仅覆盖真实首日的合法日历缓存、无效主源在取日历之前回退、较早合法候选扩展日历、None/empty 区分。正常默认资产顺序供应商校验实测只取一次日历；仅覆盖 2011-12-09 起的合法缓存不要求扩到 2010，也不触发 HTTP。
5. 最终源码用此前真实下载的 9 月 30 日快照经真实 AkShare parser、中心 validator、对齐、填价 mask、正式 engine、bar metadata 和正式五窗口指标回放，得到 **3,597 行、2011-12-09～2026-09-30**。与保存的上一轮 daily 日期、持仓、费用、换手和全部填价标记相同；NAV 最大差为 CSV 往返精度 `7.11e-15`、收益最大差 `9.95e-17`，五窗口年化与最大回撤一致。仅外部价格响应以同一真实冻结快照替代，并预载同一只读日历，不声称新增网络或托管端验收。

正常真实快照的两个单资产缺价仍前填且标记；未有历史之前的 NaN 保留。D04 非数字价格拒绝、D05 空日历拒假 bar、D06 官方日历后备覆盖之外关闭执行、D07 `[0, TTL]` 缓存年龄区间均有独立通过用例。D01 首行截断/最低评分行数、D02 真正的空/重复页、D03 NaT/重复日/坏价格等原反例也仍通过上一轮数据回归。首日锚点本身不等于整个单资产历史完整性认证；单资产长期缺日与真实停牌需要独立数据才可区分，本次没有发明缺价阈值。

## 主要产物与复现

- `data_probe.py` / `data_probe_results.json`：固定 7a 源码上的正式构建链故障影响，含所有五窗口的诊断指标。
- `data_replay_current.py` / `data_current_replay_results.json`：最终正常真实快照回放、hash、calendar 调用范围及逐列差异。
- 所有新测试不生成媒体、Python 字节码或 pytest 缓存；没有新下载源、QVeris、托管端部署或下单。

```powershell
$env:V13_DOUBLECHECK_DATA_CODE_PATH='D:\动量策略\美股A股混合池子动量策略\.codex_backups\20261007_200248\poe_subd_six_etf_v1_3_bot.py'
python -X utf8 -B -m pytest tests/test_v13_doublecheck_data_20261007.py -q -p no:cacheprovider
# 正常复测时先在当前进程清除上述任务专用变量。
Remove-Item Env:V13_DOUBLECHECK_DATA_CODE_PATH
python -X utf8 -B -m pytest tests/test_v13_doublecheck_data_20261007.py -q -p no:cacheprovider
python -X utf8 -B outputs/doublecheck_script_audit_20261007/data_probe.py
python -X utf8 -B outputs/doublecheck_script_audit_20261007/data_replay_current.py
```

本报告仅覆盖所委派的数据链独立复核。没有因此完成全历史公司行动点时认证、真实停牌与涨跌停成交、持仓与可卖数量、托管端行为或实际账户验收。
