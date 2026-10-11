# L0 独立审计 A：六 ETF V1.3 版本身份与谱系

## 裁决范围

本审计只核对本地登记、Git、源码和已保存产物的身份，不重新运行绩效，也不检查 L1 数据可知时点或 L2 账户正确性。用户下载目录中的《量化策略回测重新认证：通用执行手册 v1.2》是测试流程，不是本项目版本/参数的授权登记。L0 年化收益、最大回撤、关停路径和候选路径均为 **N/A：本层不作绩效运行**。

**身份结论：**本仓库最新登记并冻结的六只中国上市 ETF 朴素版是 `poe_subd_six_etf_v1_3_bot.py`，Poe 名称 `SubD-Six-ETF-Naive-V13`，入口 `SubDSixEtfV13Bot`。本地 HEAD 为 `5f539ff7ef93aa805c563bfa4d6581fc841f0bb6`（2026-09-04）。源码 SHA256 `21a5867f51367d215a6f9913dafae1a462bf2316f7c59e7a860d43448c63ee72`，与旧验收 `outputs/subd_six_etf_v1_3_acceptance_20260904/parity.json` 记载一致；Git blob 与 HEAD 一致，登记文档和 README 无工作区改动。证据：`README.md:5-16,33-36`，`docs/subd_six_etf_v1_3_20260904.md:5-7,118-120`，`poe_subd_six_etf_v1_3_bot.py:6153`，本次 `git rev-parse HEAD`、`git hash-object` 和 `Get-FileHash`。

这属于**本地已成版、已验收的回测/Poe 展示实现**；`docs/subd_six_etf_v1_3_20260904.md:112-116` 明确未在 poe.com 托管端上传或测试，不能据此声称已部署、正在自动交易或拥有实盘收益。`README.md:13` 仍把 `run_subd_six_etf_v1_1.py` 列为 V1.1 正式输出入口；不能用它的 V1.1 结果冒充六 ETF 朴素版 V1.3。

## 冻结对象与谱系

| 对象 | 本层识别结果 | 证据 |
| --- | --- | --- |
| 最新六 ETF V1.3 | 六只中国上市 ETF；25 日线性加权对数回归 Top1；严格 `0.5 < Score < 5.5`；`R² >= 0.25`；全额建仓；Buffer 1；1 倍上限；目标波动率、过热、分批关闭；现金收益 0；单边成本 0.001 | `poe_subd_six_etf_v1_3_bot.py:98-142,3324-3347`；`docs/subd_six_etf_v1_3_20260904.md:13-22` |
| 正式计算链 | `_build_v13_daily -> load_close -> align_prices_to_common_valid_date -> build_curves -> run_staged_entry(full_entry)`；禁用的增强层未进入主计算链 | `poe_subd_six_etf_v1_3_bot.py:3324-3347,3402-3429`；`docs/subd_six_etf_v1_3_20260904.md:30-32` |
| 冻结输入 | `quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/price_snapshot_qfq.csv.gz`；Tencent 前复权，2011-12-09 至 2026-09-02，3578 行；本次重算 SHA256 为 `0cc4af45158d6aaab4594b869b79309a96e8e3cc2f21a0205c38128913bec2aa` | `docs/subd_six_etf_v1_3_20260904.md:24-26`；本次 `Get-FileHash` |
| 上一研究选择 | 六 ETF 的 Score 上限 5，且下限 0.5、R² 0.25；2026-09-04 被上限 5.5 替代 | `docs/subd_v11_naive_simplification_decisions_20260903.md:21-26,40-44`；`quant_comparison_runs/20260904_subd_selected_score_max_5p5/report.md` |
| 更旧完整线 | 六 ETF V1.1，含分批、波动率与过热等机制；不可将其总收益差归因于单参数 | `quant_comparison_runs/20260904_subd_selected_vs_original_v11/report.md` 的第 2、3 节 |
| 同名另一家族 | `poe_subd_mixed_pool_v1_3_bot.py` 为 QQQ/GLD/KMLM/中国代理的旧混合池；代码参数为回看 28、Score 0–5、R² 关闭等，不能替代六 ETF V1.3 | `README.md:6-16`；`poe_subd_mixed_pool_v1_3_bot.py:98-154` |

六 ETF V1.3 自 `poe_subd_six_etf_v1_1_bot.py` 的修复后代码改造，独立脚本在 `5f539ff` 进入 Git；另一混合池 V1.3 的脚本始于旧提交 `055fcbc`。本层仅从当前本地分支及可见 Git 历史判断“最新”；未联网检查远端新提交。V1.3 的当前冻结价截至 2026-09-02，不等于 2026-09-26 最新市场数据。

## 旧曲线、正式验收曲线与首个差异

旧研究对象 `quant_comparison_runs/20260904_subd_selected_score_max_5p5/cap_5p5_daily.csv.gz` 的标识是 `selected_research / cap_5p5`，正式验收对象 `outputs/subd_six_etf_v1_3_acceptance_20260904/daily.csv.gz` 的标识是 `1.3 / v1_3_naive_score_0p5_5p5_r2_0p25`。本次只读取两份已保存 CSV：均为 3578 行，同一日期；`position` 完全一致，`holding_fraction`、`turnover`、`cost`、`return`、`nav` 的最大绝对差均为 0。旧验收 `parity.json` 记录最大 NAV 差 `7.11e-15`，说明其当时所用序列/读写浮点口径可能与本次保存 CSV 的逐值比较略有不同。逐日 parity 支持“最新六 ETF V1.3 成版实现忠实承接此前用户选定研究曲线”的 **L0 身份桥接**；它不能证明历史行情正确、无未来泄漏、账户恒等、可执行性、独立样本外有效或当前绩效。上述问题交给 L1/L2 等后续层。

与上限 5 的旧研究曲线 `quant_comparison_runs/20260904_subd_selected_score_max_5p5/cap_5_daily.csv.gz` 比，**首个真实差异在 2013-05-08**：旧上限 5 将 `159915.SZ` 过滤，候选为现金，收盘卖出，换手 1、成本 0.001；新上限 5.5 的该 ETF Score 为 `5.01309741497797`、R² 为 `0.8012891076655534`，继续持有，换手/成本为 0。当日旧/新净收益分别为 `0.0326505263157894` / `0.0336842105263157`，NAV 分别为 `1.3112053499036336` / `1.312517867771405`。两线前一日 `2013-05-07` 的持仓、净收益、NAV 相同。该差异符合上限从 5 扩至 5.5 的预期，只是定位差异，未重新推算绩效；旧报告不是新版本真值。

## 2026-09-13 两个未跟踪目录的处理

`quant_param_scan_runs/20260913_mixed_us_cn_momentum_six_etf_v1_3_execution_next_open/` 与 `..._rebalance_weekly/` 均在 `git status --short` 中是未跟踪目录；`git ls-files` 对两目录无输出。其 `scan_meta.json` 分别写 `research_only_no_production_change`、`research_only_keep_daily`，同为 `5f539ff` 上的时点/频率研究。正式源码 `git hash-object` 与 `git rev-parse HEAD:poe_subd_six_etf_v1_3_bot.py` 同为 `d4aa3f9346ce2f0c26549edfeb904ee58d4bfc4f`；登记文档亦与 HEAD 相同。因此这两份研究没有改变本地正式 V1.3 身份。它们的次日开盘/周频输出不是应替换的正式曲线；L0 不据此评价其回测正确性。

## 可执行反例

只读身份闸门：`python -X utf8 outputs/recert_l0_version_audit_20260926/agent_a_version_identity.py --self-test`。本次退出码 0，结果如下：

- 正确六 ETF V1.3：`ACCEPT`；冻结数据 SHA256：`MATCH`。
- 错用同名 `poe_subd_mixed_pool_v1_3_bot.py`：`REJECT`，资产集合、回看期、Score、R² 等均不符。
- 在内存里把正确脚本的 Score 上限错认成旧值 5：`REJECT`，报告 `SCORE_MAX: got 5.0, expected 5.5`。该注入不写回正式文件。

这是身份拒绝测试，不是信号或账户独立复算。它依赖冻结清单，未来若用户正式变更策略应更新清单并重做 L0，不能靠改清单消除当前不一致。

## L0 状态与限制

审计 A 对**本地版本身份与冻结输入文件哈希**给出 PASS。L0 仍须主 Agent 汇总独立审计 B 与交叉质询后裁决。尚未核当前市场刷新、真实供应商修订、逐行数据质量、成本与账户逻辑、任何绩效或生产上线；这些均不从本层 PASS 推出。下一层 L1 应检查该冻结输入的来源、覆盖、复权、交易日及 2026-09-02 截止后如需刷新时的新增数据与可知时间。按用户要求，本层报告后停下等待确认。
