# Sub-D V1.1 / V1.3 对抗测试修复记录（2026-08-12）

## 结论

- V1.1 保持正式 qfq 路径，runner 与 Poe 已统一为同一 carried-exposure 账本，并加入实际敞口硬上限、破产保护、窗口重置和数据完整性校验。
- V1.3 的确定性数据缺陷已修复。按 2026-08-12 用户确认，V1.1/V1.3 在 Poe 上只负责提供交易信号，不直接连接券商执行；汇率、跨市场成交时点和下一场次映射只作普通提示，不得作为停发信号的全局门禁。
- V1.3 已恢复原有 Poe 信号协议、状态字段、净值图标题和交易 CSV schema，不再强制标为 `diagnostic_only`。`159985.SZ` 的冻结参数与独立样本外验证仍是研究质量建议，但不阻断 Poe 信号。

## 回滚点

修改前备份位于：

`D:\动量策略\美股A股混合池子动量策略\.codex_backups\20260812_114431`

备份包含四个实现文件和当时相关测试文件。恢复时应只覆盖本记录列出的实现/测试文件，不要覆盖工作区中无关的用户改动。

撤销 V1.3 全局诊断门禁前的中间版本另备份于：

`D:\动量策略\美股A股混合池子动量策略\.codex_backups\20260812_123423`

## 已修复问题

### V1.1

1. **runner/Poe 账本漂移**
   - 无策略事件时携带价格漂移后的实际敞口，不再每日强制回到目标敞口。
   - 仓位、fraction、target-vol、过热状态、pending retry 或 hard cap 变化时才产生调仓。
   - stale/前值填充价格会原子阻断整笔换仓并在后续有效价格日重试。

2. **实际敞口硬上限与破产保护**
   - `max_lev` 同时约束目标敞口和漂移后的实际敞口。
   - 纯 hard-cap 调仓记录 `exposure_cap_rebalance/turnover/cost`；与策略调仓同日发生时不重复归因成本。
   - `max_lev` 的 bool、NaN、正负无穷、负数和不可转换值均拒绝。
   - NAV 因子、成本后 NAV 或累计 NAV 非有限/非正时立即 fail-closed。

3. **绩效窗口口径**
   - 每个查询窗口先校验全部 return/nav，再把窗口首行收益重置为 0，避免带入窗口前收益。
   - 1Y/3Y/5Y/10Y 统一为 252/756/1260/2520 个唯一、严格递增交易日。
   - 重复日期、乱序日期、非有限收益、`return <= -1`、非正 NAV/wealth 和样本不足均拒绝。

4. **数据源与指标完整性**
   - AkShare/Eastmoney/Tencent qfq 首选路径均经过 35% 单日连续性闸门。
   - 正式 `load_close` 只接受 qfq；Sina/raw 和交叉验证 raw 只保留诊断用途。
   - runner 的 raw 输出自动加 `diagnostic_only`，不能生成未标记的正式前缀结果。
   - weighted-slope 拒绝常量/近常量与非有限价格，并保持正比例价格缩放不变。
   - live 强制刷新失败只允许复用不超过 2 分钟的同状态缓存；未来时间或超龄缓存拒绝。

### V1.3

1. **历史数据与分页**
   - CNFin index 分页中途失败、字段变化、重复日期、页数耗尽或覆盖不到请求起点时拒绝部分历史。
   - Yahoo adjusted、qfq ETF 与三个 index provider 均经过连续性闸门。
   - 正式 qfq 链不再尝试 raw/unadjusted fallback；direct raw cross-validation helper 仅用于诊断。

2. **动态资产与实时缓存**
   - 动态资产最多允许 3 个中国交易日的尾部缺失，以容忍正常异市场休市/发布滞后；第 4 个交易日起 fail-closed。
   - live force-refresh 失败只允许复用 2 分钟内缓存，与 `LIVE_QUOTE_MAX_AGE` 相同。

3. **日度与绩效数值**
   - signal/performance 入口拒绝归一化后重复日期、非有限或 `<= -1` 收益、非有限或非正 NAV/wealth。
   - wealth 与所有输出指标必须有限；零波动 Sharpe 定义为 0。
   - weighted-slope 使用相对尺度容差、归一化 log-price 和 `expm1`；常量资产永不入选。

4. **Poe 信号服务边界**
   - 移除跨市场全局 `diagnostic_only` 门禁，恢复 `action_required(_now)`、`actionable_now`、`strategy_actionable_now` 与 `tradable` 的原有数据新鲜度/时段逻辑。
   - 汇率、市场日历差异和 US→CN 同日收盘不可执行性保留为提示，不参与是否生成持仓与调仓信号的判定。
   - 移除新增的日度/source/CSV provenance 列和诊断 PNG 标题，避免改变既有 Poe 输出协议及下游 schema。
   - 没有新增券商、订单、汇率或外部执行依赖；两个 Poe 文件继续是自包含信号服务。

## 自动化验证

最终执行：

```text
python -m pytest -q tests
495 passed, 1 warning in 30.61s

python -m py_compile poe_subd_six_etf_v1_1_bot.py poe_subd_mixed_pool_v1_3_bot.py research_subd_six_etf_weighted_slope.py run_subd_six_etf_v1_1.py
passed

git diff --check
passed（仅工作区既有 LF/CRLF 提示）
```

唯一 warning 来自 `fastapi_poe` 对 Pydantic class-based config 的弃用提示，不是本次策略逻辑失败。

Hypothesis 当前未安装，因此没有新增运行时依赖；缩放不变性、常量序列、重复日期、非有限值、破产边界、hard-cap 与 runner/Poe parity 均由确定性 metamorphic/regression cases 覆盖。

## 真实数据验证

### V1.1 正式 qfq 同输入重建

- 请求截止：2026-08-11。
- 对齐区间：2011-12-09 至 2026-08-11，共 3,562 个中国交易日。
- 六资产最后有效日均为 2026-08-11。
- 首次正式 fallback 路径实际选中：Tencent qfq（`159915.SZ`、`159941.SZ`、`513520.SH`、`159985.SZ`、`518880.SH`）和 AkShare Eastmoney qfq（`513030.SH`）。
- 最终同输入 parity 复核使用六条 Tencent qfq 序列；runner 与 Poe 在 return、NAV、gross return、turnover、cost、实际敞口、漂移敞口、最终敞口及三个 hard-cap 审计字段上最大绝对差均为 0，持仓字段也无差异。
- 最终 NAV 为 74.5344982070；73 个纯 hard-cap 调仓日；845 个总交易日；最大实际敞口为 1.5x（浮点容差内）；NAV 全程有限且为正。

按修复后的统一窗口口径，V1.1 正式结果如下。最大回撤沿用代码的负数记法：

| 窗口 | 实际区间 | 交易日 | 年化收益 | 最大回撤 |
|---|---|---:|---:|---:|
| full_sample | 2011-12-09 ~ 2026-08-11 | 3,562 | 35.6636% | -30.2207% |
| 10Y | 2016-03-29 ~ 2026-08-11 | 2,520 | 39.5150% | -29.7408% |
| 5Y | 2021-06-02 ~ 2026-08-11 | 1,260 | 71.3606% | -17.3535% |
| 3Y | 2023-06-30 ~ 2026-08-11 | 756 | 89.4750% | -16.3357% |
| 1Y | 2025-07-29 ~ 2026-08-11 | 252 | 89.7885% | -12.8491% |

这些数值是当前正式 qfq 代码路径的重建结果，不是对未来收益的承诺。

### V1.3 真实数据 smoke

- 截止 2026-08-11 的真实构建成功：4,764 行，2007-01-04 至 2026-08-11，五资产最后对齐日均为 2026-08-11。
- 日期唯一，日度与核心绩效 primitive 均有限。
- CNFin index direct probe 的字段契约可解析，但 2010 至 2026 请求只返回 2,001 行、首日为 2018-05-17；新逻辑按预期拒绝该残缺历史。
- 本轮真实 smoke 用于验证数据构建与 Poe 信号路径，没有重新发布 V1.3 CAGR/回撤；这不影响 V1.3 在 Poe 上继续提供信号。

## 观察、推断与假设

### 已观察

- 全量测试、语法编译、真实 qfq 重建和真实同输入双路径 parity 均通过。
- 35% continuity gate 未在本次 V1.1/V1.3 真实历史上触发。
- V1.3 CNFin 长历史确实存在“返回 2,001 行但未覆盖请求起点”的情况。

### 推断/策略选择

- live stale-if-error 上限取 2 分钟，是为了与报价最大年龄一致，避免“技术上同日、实际上已过时”的快照被重新包装成实时结果。
- 动态资产尾差上限取 3 个中国交易日，用于容忍正常异市场休市与短暂发布滞后；这是保守的数据完整性阈值，不是收益参数。
- 35% 单日跳变是 fail-closed 数据质量闸门。当前池子是非杠杆 ETF/指数且使用 adjusted/qfq 序列；若未来加入杠杆品种或真实极端事件，应以公司行动和独立源复核替代简单放宽阈值。

## 可选的后续研究（不阻断 Poe 信号）

如果未来要把 V1.3 扩展成自动下单系统或评估可成交的基础货币 PnL，可再单独研究事件时间、可交易品种映射、下一场次成交、交易限制、成本和 USD/CNY。候选池晋级也可补做冻结参数、one-at-a-time 同路径基线及独立 OOS/holdout；这些都不是当前 Poe 信号服务的运行前置条件。
