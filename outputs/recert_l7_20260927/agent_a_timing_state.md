# L7 独立审计 A：版本、状态与信号时序

审计日：2026-09-27（北京时间）。**裁决：批量重放与时序门禁 PASS；信号报告成交措辞 FAIL；持久增量/恢复 N/A。** 六只中国上市 ETF V1.3 的正式源码保持冻结，批量重放有前缀一致性；已确认信号与实时估算分流，09-27 休市时的 09-24 历史调仓信号被标为不可执行。但同页把纸面模型换手日期称为“上次实际成交日”，会误导为券商真实成交。源码时序 PASS 只针对本地冻结数据重放；同价收盘成交仍是纸面假设，不代表交易所委托、成交或 Poe 托管端验收。

## 审计边界和输入

- 唯一正式入口：`poe_subd_six_etf_v1_3_bot.py` 的 `SubDSixEtfV13Bot`，Git `5f539ff7ef93aa805c563bfa4d6581fc841f0bb6`，源码 SHA256 `21a5867f51367d215a6f9913dafae1a462bf2316f7c59e7a860d43448c63ee72`。资产池是 `159915.SZ, 159941.SZ, 513030.SH, 513520.SH, 159985.SZ, 518880.SH`，`VERSION=1.3` 且 `V13_SCENARIO=v1_3_naive_score_0p5_5p5_r2_0p25`。同名 V1.3 的 `poe_subd_mixed_pool_v1_3_bot.py` 是 QQQ/GLD 等混合代理池，不能套用。
- 真实历史输入沿用 L1 独立保存的前复权标签面板 `outputs/recert_l1_20260926/prices_aligned_qfq_through_20260924.csv.gz` 与相应 `price_ffill_flags_through_20260924.csv.gz`，2011-12-09 至最新完整交易日 2026-09-24，共 3,594 行。价格为供应商历史市场数据；仓位、费用、净值与同收盘价模型成交均为模拟。复权语义、点时可知性、真实成交限制继承 L1/L2，不在本层重认证。
- 本层不重新报告收益比较：Full、10Y、5Y、3Y、1Y 的年化和最大回撤均 **N/A（L7 不重算绩效）**；应使用 L2 已校正 N−1 年化基点的同次输入结果，不引用旧 09-02 指标。

## 源码链与状态结论

1. `SubDSixEtfV13Bot.run` 分派普通信号、实时信号、参数和绩效；普通信号走 `data_state="confirmed"`，实时信号强制刷新 `data_state="live"`（6153–6197 行）。`_build_v13_daily` 每次通过 `_build_config -> load_close -> align_prices_to_common_valid_date -> build_curves -> run_staged_entry` 重建历史（3402–3451 行）。`run_staged_entry` 从 `holding="CASH"`, `nav=1.0` 开始逐日计算，旧仓获得当日 close-to-close 收益，然后当日信号扣成本并设置下一行持仓（1691–1725、1842–1875 行）。因此无需从上一次调用恢复模型持仓，且**没有持久增量算法或持仓检查点可认证：N/A**。
2. 仅存在进程内 `_DAILY_CACHE`，键为北京时间日期与 confirmed/live 状态，普通缓存 TTL 五分钟，跨越 15:30 确认边界失效；实时刷新失败只可短时沿用同状态缓存，返回来源提示（3468–3529、4544–4567 行）。交易日历 CSV 是日历资料缓存，不是仓位或净值恢复状态（1935–1939、2072–2202 行）。缓存不是增量账本；程序重启后会重新取数并全量重算。
3. `_normalize_daily` 同时按 `VERSION` 与 `V13_SCENARIO` 筛选且空结果报错（3389–3399 行）。实际把同样 `version=1.3` 但混合池 `scenario` 的行送入该适配器会被拒绝；README 与版本文档也分别列明两个入口。此处针对误混 `scenario`，不能据此声称 Poe 托管页面已发布正确脚本。

## 运行证据与首差

本地隔离脚本 `outputs/recert_l7_20260927/agent_a_timing_state_probe.py` 导入正式策略函数、读取 L1 冻结输入，不联网、不写正式代码或缓存。`python -X utf8 outputs/recert_l7_20260927/agent_a_timing_state_probe.py` 返回成功；机器可读结果在 `agent_a_timing_state_probe.json`。

| 检查 | 观测 |
| --- | --- |
| 全量 vs 前缀重放 | 全量 3,594 行截至 09-24，前缀 3,578 行截至 09-02；共同日期 `position_before/position/trade_target` 错行数均 0；`turnover/cost/return/nav` 最大绝对差均 0。无经济首差。 |
| 故意错误的“只跑新增尾段即续接” | 从 09-03 单独调用正式入口，首行错误重启为 `CASH`、NAV 1，评分尚无 25 日热身；全量重放该日旧仓为 `159985.SZ`、NAV 44.9930323382，评分已有值。**首差 2026-09-03**。证明尾段独跑不等于持久增量恢复；不是正式算法缺陷。 |
| 15:30 确认边界 | 用真实 09-24 冻结价格和模拟北京时间 09-24 14:55/15:31，未确认普通信号仅到 09-23；源日线六资产都标为最终 bar 后，普通信号可含 09-24。此为时间门禁重放，不是假称当时真实收到的实时快照。 |
| 09-27 周日新鲜度 | 在保存的 09-24 已确认日线和项目交易日历上，预期最近确认交易日为 09-24；`signal_valid=True`、`raw_signal_has_trade=True`，但 `delayed_execution=True`、`model_execution_price_available=False`、`strategy_actionable_now=False`、`tradable=False`，提示休市并要求下一交易日重新确认价格。 |
| 版本错例 | `version=1.3` 但换成混合池 `scenario`，`_normalize_daily` 拒绝，无静默混入。 |

### 信号报告的成交措辞：FAIL

`_last_actual_trade_date` 只对日曲线筛选 `turnover > 1e-12` 并返回最后日期（5400–5408 行），而 `turnover` 是 `run_staged_entry` 按模型目标仓位与旧仓位计算、同日扣纸面成本的变量（1856–1875 行）。报告直接输出 `上次实际成交日`（5799 行），没有读取券商委托、成交回报或账户持仓。用 L1 保存价格重放并在 2026-09-27 12:00 生成普通信号页，实际出现 **`上次实际成交日: 2026-09-24`**，同页执行状态却写明休市、执行前须重新确认价格；证据在 `agent_a_timing_state_probe.json`。此标签与数据来源不符，足以让读者误以为 09-24 已真实成交。应在后续获授权的正式代码修复中改为明确的“上次模型调仓日”等措辞，并检查同类成交/交易记录标签；本层按要求不改正式代码，因此报告语义保持 FAIL。

源码额外门禁：实时六只行情要逐只配对价格和时间，要求当天报价、≤2 分钟年龄、≤30 秒跨资产偏斜，且验证来源、价格/交易状态（859–887、3803–3899 行）。历史 signal 经过 `prepare_daily_for_signal` 剔除未确认当日 bar（4177–4201 行）；`signal_data_status` 检查预期交易日、源最终 bar、实时新鲜度、交易腿和执行窗口（4204–4541 行）。当前 `POST_CLOSE_FIXED_PRICE_EXECUTION_ENABLED=False`；周日上例虽有历史模型交易，不能把 09-24 的收盘同价成交延时称为 09-27 可执行指令。

## 限制和复现

- 本地真实数据前缀和反例 PASS；信号页成交日期措辞 FAIL。未做 Poe 托管环境验收、实时交易所报价捕获或券商持仓/可卖数量验收；历史模型的同收盘信号/成交非可实现性仍是重要限制。09-27 的模拟时钟检查只证明门禁逻辑，不证明实际 09-24 当时能取得最终收盘价并成交。
- 补充执行 `python -X utf8 -m pytest -q tests/test_poe_subd_six_etf_v1_3_safety.py -k "cache_and_confirmation_contracts or test_replay_adversarial_check_on_v13"`：**33 passed**、一条第三方 Pydantic 弃用警告。覆盖旧有陈旧/偏斜/未来报价、缓存/确认边界等对抗用例；本层只把它作回归旁证，不替代上表的新快照独立重放。
- 未修改正式策略、旧版本、生产参数或信号发布状态；本报告是 L7 的独立时序/状态证据，不进入 L8。
