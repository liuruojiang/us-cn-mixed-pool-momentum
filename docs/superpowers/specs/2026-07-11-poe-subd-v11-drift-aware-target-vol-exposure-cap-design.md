# PoE SubD V1.1 漂移感知目标波动率与可执行敞口上限设计

日期：2026-07-11

范围：`poe_subd_six_etf_v1_1_bot.py` 及其回归测试

状态：已按两轮独立书面规格审查修订

## 1. 背景与问题

V1.1 当前先在基础曲线的 `return` 上计算滚动波动率，再用目标波动率 scale 重算最终净值。基础曲线按策略计划仓位生成，不完整反映两次真实调仓之间因资产涨跌形成的持仓敞口漂移。因此，目标波动率估计输入与最终执行账本不是同一种仓位语义。

此外，`max_lev` 当前只裁剪目标波动率 scale。若杠杆持仓上涨，收盘前漂移敞口可能超过 `max_lev`；只要基础信号和各 overlay 没有变化，现有执行器不会在模型边界生成减仓，因而 `max_lev` 不是带交易会计约束的目标上限。

本批修复这两个正确性问题。融资成本需要可靠利率来源和独立口径决策，不在本批假设或补造。

## 2. 目标与非目标

### 目标

1. 目标波动率使用“scale=1、按真实持仓漂移和真实交易成本执行”的基础执行曲线估计。
2. 保持现有抽象收盘边界时序：截至交易日 `t` 收盘可观察到的滚动波动率产生边界 `t` 的目标，目标作为 `t+1` 持有期的有效敞口。
3. 将 `max_lev` 同时作为目标 scale 上限和模型内成交完成后的敞口上限。
4. 漂移敞口越过上限时生成模型减仓、换手和成本，而不是静默裁剪数值。
5. 若减仓所需资产价格为陈旧/填充价格，保持真实持仓，不伪造成交，并在后续交易日按最新目标重新判断。
6. 在输出中保留足够审计字段，区分未裁剪目标、上限后目标、是否触发以及是否因陈旧价格阻塞。

### 非目标

1. 不引入融资利率或融资成本。
2. 不改变目标波动率、窗口、scale 调仓阈值、过热防御、净值防御或基础选券参数。
3. 不加入涨跌停、T+1、成交量、冲击成本、MOC 截止时间或次日开盘成交模型。
4. 不修改 V1.3 的研究限制或跨市场正式模型。
5. 不用新回测结果宣称策略收益改善；本批属于会改变历史结果的执行正确性修复。

## 3. 方案选择

采用“估计 pass + 中间状态 pass + 最终正式 pass”：

1. 先把 staged-entry 基础计划送入统一执行账本，target-vol 和 overheat scale 均设为 1、且不施加最终敞口 cap，得到漂移感知的“未加 target-vol 基础执行曲线”。
2. 使用这条曲线的净收益计算滚动已实现波动率及下一期 scale。
3. target-vol 中间 pass 从同一份不可变基础计划独立重放，只为 overheat 状态机提供 target-vol 后的持仓状态；其交易、成本、pending 和阻塞审计不是最终事实。
4. overheat scale 确定后，最终正式 pass 再从不可变基础计划独立重放，且只由这个 pass 生成正式净值、换手、成本和 overlay/cap 审计。

不直接对现有基础 `return` 做局部修补，因为那会继续保留计划仓位收益与真实持仓状态的双重语义。也不直接对输出敞口 `clip`，因为静默裁剪不会产生交易、成本或陈旧价格阻塞记录。

## 4. 市场时序边界

本策略当前是**抽象日线收盘边界回测**，不是已验证可成交的 MOC 或次日开盘模型。每行先用进入当日时已经持有的实际敞口计算 `t-1 close -> t close` 收益；在边界 `t` 观察到收盘数据后计算目标，并在模型中记为边界成交，从而成为 `t+1` 持有期的实际敞口。

因此：

- `realized_vol[t]` 可以决定 `next_scale[t]`；
- `next_scale[t]` 只决定边界 `t` 的目标，不影响第 `t` 行已经实现的收益；
- 成交后的实际敞口在第 `t+1` 行记为 `effective/actual exposure`；
- “可执行上限”仅指模型内必须经过交易、换手、成本和 stale gate，不再称为真实市场可保证成交的收盘后硬上限；
- 实时报告必须把它称为“模型边界目标上限”，并继续提示真实下单仍受交易时间和市场可成交性约束。

真实 MOC/next-open、涨跌停、T+1 和流动性执行将在后续执行现实性项目中统一处理，不能在本批局部伪装解决。

## 5. 三阶段账本契约

三个 pass 都从同一份不可变基础计划字段独立重放，不以上一 pass 的 `return/nav/turnover/cost/actual_position/pending/overlay stale` 作为下一 pass 的计划输入。

| Pass | 用途 | Cap | 正式成本/审计归属 |
|---|---|---:|---|
| estimator | scale=1 漂移感知波动率输入 | 不施加最终 cap | 只写 `unscaled_execution_*` 命名空间，不进入正式绩效或日报阻塞 |
| target-vol intermediate | 供 overheat 状态机计算 | `max_lev` | 纯中间状态；交易、成本、pending、stale/cap 审计不得累积到最终输出 |
| final | target-vol + overheat 的最终执行 | `max_lev` | 唯一正式 `return/nav/turnover/cost` 和 overlay/cap 审计来源 |

基础 staged-entry 自身已经形成的不可变事实需在重放前复制为 `base_*` 字段。最终审计只合并 `base_* + final pass local`，并按资产去重；不得合并 estimator 或 target-vol intermediate 的 pass-local 事实。同日 target-vol 与 overheat 同时改变目标时，只按最终目标与真实漂移敞口之间的最终 turnover 计费一次。

成本模型沿用当前约定：目标敞口是模型记账的成本后持有比例，交易成本作为当日 NAV 的独立比例折减，执行后 carried exposure 仍记录为目标比例。该约定不是完整自融资资产负债表模型，必须在绩效说明中披露；在此约定下 cap 对记录的 carried exposure 成立。

## 6. 数据流

对每条基础曲线：

1. 保存原始基础计划字段，包括基础持仓、基础交易意图和各资产收益。
2. 以全 1 scale、无最终 cap 调用统一执行账本，产生漂移感知基础收益 `unscaled_execution_return` 和对应净值。
3. 对该净收益做 `vol_window` 日滚动标准差，年化后得到 `realized_vol[t]`。
4. 定义 `initial_scale = min(1.0, max_lev)`。前 `vol_window - 1` 个预热行的 `realized_vol` 保留为策略性 NaN，但 `raw_next_scale/next_scale` 使用有限的 `initial_scale`。
5. 完整窗口内若 `realized_vol == 0`，`raw_next_scale` 取 `max_lev`；若 `realized_vol > 0`，计算 `target_vol / realized_vol`，再限制到 `[0, max_lev]`。完整窗口内出现 NaN、负数或非有限 realized vol 必须失败关闭。
6. scale 调仓阈值状态也从 `initial_scale` 开始，不能硬编码从 1.0 开始。
7. `effective_scale[t] = next_scale[t-1]`；首行 effective scale 使用 `initial_scale`，保持无前视且在 `max_lev < 1` 时不越界。
8. 从不可变基础计划独立执行 target-vol 中间 pass，仅计算 overheat 所需状态。
9. overheat overlay 产生 scale 后，从不可变基础计划独立执行 final pass，生成唯一正式收益、换手、成本与审计。

用于波动率估计的基础执行曲线包含基础策略自身交易成本，因为它代表 scale=1 策略净值实际可经历的波动。它不包含 target-vol、overheat 或后续防御 overlay，避免反馈循环。

## 7. 上限执行语义

统一执行账本新增显式可选 `exposure_cap` 参数；estimator 传入 `None`，明确表示完全不裁剪目标、cap trigger/blocked 字段全为 false；两个正式语义 pass 传入 `max_lev`。

每日顺序：

1. 根据上一日实际收盘后持仓和当日资产收益计算 `drifted_exposure_before_trade`。
2. 根据基础持仓、target-vol scale 与 overheat scale 计算 `uncapped_target_exposure`。
3. 得到 `capped_target_exposure = min(uncapped_target_exposure, exposure_cap)`。
4. 若计划目标变化、存在未解决状态，或漂移敞口高于上限，则进入模型交易路径。
5. 同资产减仓换手为 `drifted_exposure - capped_target_exposure`，并按现有单边成本计费。
6. 若交易腿价格陈旧，则整笔交易原子阻塞：实际收盘持仓保持为漂移后持仓，换手与成本为零，并保留 pending 状态。
7. 后续每个交易日都先从真实持仓继续漂移，再用当日最新 base/target-vol/overheat 目标重新裁 cap；不得机械执行旧的 pending 数量。若最新目标撤销交易或实际敞口已不再超限，按最新目标决定是否交易。

该上限约束模型边界交易成功后的 carried exposure。价格陈旧时无法合法声称已成交，因此允许实际敞口暂时越界，但必须明确称为“上限未实现的执行阻塞”，不能报告为仍满足硬上限。

漂移会计严格使用：

```text
gross_t = exposure_t * asset_return_t
wealth_factor_t = 1 + gross_t
drifted_exposure_t = exposure_t * (1 + asset_return_t) / wealth_factor_t
```

仅当 `wealth_factor_t > 0` 且结果有限、非负时有效。否则失败关闭，不得把破产、负净值或非有限结果回退为现金或零敞口。

## 8. 审计字段与报告

每日曲线至少增加或明确以下字段：

- `unscaled_execution_return`：scale=1 漂移感知基础执行净收益，作为波动率输入。
- `virtual_base_realized_vol`：字段为兼容保留，但报告文字改为“漂移感知基础执行已实现波动率”。
- `exposure_cap`：模型边界目标上限。
- `target_vol_uncapped_target_exposure`：target-vol 中间 pass 的未裁剪目标，仅作诊断。
- `pre_overheat_capped_target_exposure`：target-vol 中间 pass 的上限后目标，仅作诊断。
- `final_uncapped_target_exposure`：final pass 的未裁剪目标。
- `final_capped_target_exposure`：final pass 的上限后目标。
- `cap_triggered_by_target`：final 未裁剪目标高于 cap。
- `cap_triggered_by_drift`：final pass 开始时实际漂移敞口高于 cap。
- `exposure_cap_trade_blocked`：cap 实际改变了最终所需交易，且该 cap 所需交易未完成；不能因无关 stale 交易置真。
- `pending_rebalance` 与 `pending_rebalance_reasons`：记录未解决状态及原因，不保存待执行旧数量。
- 既有 `trade_blocked_by_stale_price` 和 `stale_price_trade_assets` 继续作为统一阻塞汇总。

实时信号与报告必须显示模型边界目标上限；若越界减仓被阻塞，应明确说明“实际漂移敞口仍高于上限，未成交，不应按目标仓位记账”。融资成本仍未计入时，绩效说明继续明确披露。

中间 pass 的上述诊断字段可以保留，但其中的 blocked assets/reasons 不得进入最终统一 stale 汇总。最终统一汇总只合并基础事实与 final pass-local 事实。

## 9. 失败关闭与不变量

必须满足：

1. `target_vol` 必须有限且 `> 0`；`vol_window` 必须是非 bool 的整数且 `>= 2`；`max_lev` 必须有限且 `>= 0`；`one_way_cost` 必须有限且满足 `0 <= cost < 1`。
2. 除前 `vol_window - 1` 行有明确政策含义的 `realized_vol` NaN 外，所有 scale、资产收益、目标敞口和中间会计值必须有限；scale 与敞口不得为负。策略性 NaN 不得传播到 scale、敞口、收益或 NAV。
3. cap 比较与交易触发统一使用 `EXPOSURE_EPS = 1e-12`。
4. final pass 模型交易成功后，`final_exposure_after_overheat <= exposure_cap + EXPOSURE_EPS`。
5. 无陈旧价格阻塞时，上限实际改变最终目标所产生的交易必须计入换手和成本。
6. 原子阻塞时，实际持仓、净值收益、换手、成本均按未成交事实计算，不按目标值计算；不支持部分成功状态。
7. scale 使用 `shift(1)`，当日波动率不得影响当日已完成持有期的收益敞口。
8. 波动率输入必须来自无 cap、scale=1 的漂移感知估计曲线，而非固定计划仓位列。
9. final pass 不得丢失 `base_*` 事实，但必须覆盖而不是累积未实际执行的中间 overlay pass 审计。

## 10. 测试策略

先写失败测试，再改生产代码。覆盖：

1. 同一资产以部分仓位连续持有且无计划调仓时，scale=1 基础执行敞口发生漂移，波动率输入与旧固定权重收益不同。
2. `next_scale[t]` 只在 `t+1` 成为 effective scale。
3. 漂移敞口超过上限且价格新鲜时，自动减至上限，产生正确换手与成本。
4. 未裁剪 overlay 目标超过上限时，被执行到上限并记录触发。
5. 越界减仓价格陈旧时，保留漂移敞口、零换手零成本、标记阻塞；后续新鲜日按最新目标执行。
6. stale 后分别覆盖目标进一步降低、目标撤销和资产切换，证明不保存旧数量。
7. target-vol 中间 pass 被 stale 阻塞、但 final overheat 目标为零时，最终不得误报中间阻塞。
8. estimator pass 的成本、pending、stale/cap 审计不进入正式绩效或日报；target-vol 与 overheat 同日变化只按 final turnover 计费一次。
9. overheat 最终重算后 cap 仍成立，且 `base_*` 审计按字段规则保留、pass-local 审计正确替换。
10. 预热期和首行 scale 等于 `min(1, max_lev)`；零波动完整窗口映射到 `max_lev`；分别覆盖 `max_lev > 1`、`< 1` 和 `== 0`。
11. `exposure_cap=None` 时不裁剪且所有 cap 审计为 false。
12. 非法 cap/参数、非政策性 NaN/inf/负值、`wealth_factor <= 0` 均失败关闭。
13. 成本约定下 carried exposure 保持为 capped target，成本只折减 NAV 一次。
14. 既有 P1 陈旧交易、staged-entry 状态、成本和收益回归测试保持通过。
15. 全量 `pytest`、`py_compile`、`git diff --check` 通过。

如正式 qfq 数据源可用，使用同一数据切片、成本和收盘执行时序重建并比较全样本、10Y、5Y、3Y、1Y 年化收益和最大回撤；若数据源不可用，明确记录 `N/A` 原因，不用 raw 数据替代正式结果。

## 11. 兼容与迁移

既有列尽量保留；`virtual_base_realized_vol` 仅改变计算语义和展示名称，不立即删除，以免破坏下游。新增字段附加到日报、信号字典和必要的表格导出。由于历史净值可能变化，旧 `outputs/` 只作诊断证据，不自动覆盖；正式结果必须通过当前代码与受信数据重建。

## 12. 验收条件

1. 所有新增测试先红后绿，并保留为回归测试。
2. 全量测试和静态编译通过。
3. 独立规格审查与代码质量审查均无 P1/P2 未解决项。
4. 报告能区分目标、实际漂移敞口、模型边界目标上限和未成交阻塞。
5. 不引入未经验证的融资利率，也不掩盖融资成本尚未计入的事实。
