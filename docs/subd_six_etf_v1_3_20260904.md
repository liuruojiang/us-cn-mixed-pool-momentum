# 六 ETF 朴素版 V1.3：版本冻结与 Poe 运行验收

## 1. 范围和交付

按用户2026-09-04指令，将最新已选组合做成独立 `poe_subd_six_etf_v1_3_bot.py`，Poe名称 `SubD-Six-ETF-Naive-V13`，入口 `SubDSixEtfV13Bot`。这是六只中国上市ETF的朴素动量版本，**不是**已有 `poe_subd_mixed_pool_v1_3_bot.py` 的QQQ/GLD/KMLM等混合代理池版本。

原六ETF V1.1与已有混合池V1.3均不覆盖。新脚本自包含，不依赖本仓库其他Python模块；可使用Poe注入的 `poe` 运行对象，也可通过原有本地兼容入口运行。本地成版不代表已发布到poe.com，更不代表自动下单。

## 2. 代码、数据和冻结参数

代码基于已修复的 `poe_subd_six_etf_v1_1_bot.py`；保留既有前复权数据链、逐资产缺失/陈旧价格保护、交易日历、盘中/确认bar分离、缓存、交易腿校验和图表/CSV接口。

| 项目 | V1.3冻结值 |
| --- | --- |
| 资产池 | 159915.SZ、159941.SZ、513030.SH、513520.SH、159985.SZ、518880.SH |
| 动量 | 25日加权对数价格回归，线性时间权重p=1，Top1 |
| Score | 严格 `0.5 < Score < 5.5` |
| R² | `>= 0.25`，与Score同一25日回归 |
| 建仓/切换 | 一次全额建仓；Buffer=1.00，无额外保护门槛 |
| 关闭层 | 分批建仓、目标波动率、MA60过热防御 |
| 杠杆/现金 | 最大1倍，现金收益0；无合格候选则现金 |
| 成本 | 单边0.10%综合费用/滑点；ETF切换为双边换手 |

冻结验证数据：`quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/price_snapshot_qfq.csv.gz`。Tencent前复权，2011-12-09至2026-09-02，3578行，SHA256 `0cc4af45158d6aaab4594b869b79309a96e8e3cc2f21a0205c38128913bec2aa`。

中国ETF交易所日历、Asia/Shanghai、252交易日年化，尾部N×252行窗口。保留原上市前NaN和既有填价标记，未代理补齐。六ETF共同可用历史从2019-12-05开始；Full/10Y是资产随上市逐步加入的历史研究，不是固定六ETF共同存续期正式证据。

## 3. 实现和执行

正式计算链：`_build_v13_daily -> load_close -> align_prices_to_common_valid_date -> build_curves -> run_staged_entry(full_entry)`，随后补充报告字段、确认收盘/实时行情元数据并标准化输出。

`build_curves`直接使用动量底座净收益与成本，不调用目标波动率、过热或最终敞口再平衡重算。显示适配层填充日初/收盘仓位和买卖交易腿；资产互换必须同时显示卖出100%与买入100%，不能因净敞口变化为0而误显示无交易。旧叠加层函数只作为未调用的历史兼容实现保留，不进入V1.3正式链。

单文件运行：

```powershell
python -X utf8 poe_subd_six_etf_v1_3_bot.py 参数
python -X utf8 poe_subd_six_etf_v1_3_bot.py 信号
python -X utf8 poe_subd_six_etf_v1_3_bot.py 实时信号
python -X utf8 poe_subd_six_etf_v1_3_bot.py 实时参数
python -X utf8 poe_subd_six_etf_v1_3_bot.py 表现
python -X utf8 poe_subd_six_etf_v1_3_bot.py 交易记录 过去两个月
python -X utf8 poe_subd_six_etf_v1_3_bot.py 净值曲线 过去两年
```

运行依赖延续原版：numpy、pandas、requests；AkShare可选但为优先来源，matplotlib用于图片。Poe正式环境使用平台提供的运行对象，附件能力通过 `start_message/attach_file` 测试；本地命令行的兼容类本身不会上传附件，验收捕获器另行检查并保存真实PNG/CSV字节。

## 4. 同口径对照

比较基准是用户最后选定的研究曲线 `quant_comparison_runs/20260904_subd_selected_score_max_5p5/cap_5p5_daily.csv.gz`。在同一冻结价格、成本、缺失规则和收益时点下，V1.3与该曲线的日持仓、换手、成本、仓位完全相同，最大NAV误差仅 `7.11e-15`，属于CSV浮点误差。

## 5. 五窗口结果

以下为本次实际执行的新V1.3，不是从旧报告手抄代替运行；相对已选研究组合的指标差异均为0（舍入后）。

| 窗口 | 年化收益 | 最大回撤 | 年化差异 | 回撤改善 |
| --- | ---: | ---: | ---: | ---: |
| Full | 30.58% | -22.01% | 0.00pp | 0.00pp |
| 10Y | 35.36% | -16.31% | 0.00pp | 0.00pp |
| 5Y | 54.70% | -15.96% | 0.00pp | 0.00pp |
| 3Y | 69.12% | -14.34% | 0.00pp | 0.00pp |
| 1Y | 69.38% | -13.43% | 0.00pp | 0.00pp |

Full波动率21.65%、Sharpe1.3405、375个有交易日、平均敞口67.97%。完整结果：`outputs/subd_six_etf_v1_3_acceptance_20260904/metrics.csv`、`daily.csv.gz`、`parity.json`。没有新增市场基准或容量估计。

另行真实网络查询在2026-09-04盘中获取了3580行原始日线，正式表现接口正确剔除当天未确认bar，最终截止2026-09-03（3579行）。这组重新获取的数据不是冻结验证面板，不用于替代冻结一致性证据：

| 窗口 | 刷新后年化 | 刷新后最大回撤 |
| --- | ---: | ---: |
| Full | 30.74% | -22.01% |
| 10Y | 35.70% | -16.31% |
| 5Y | 55.18% | -15.96% |
| 3Y | 69.12% | -14.34% |
| 1Y | 73.56% | -13.43% |

原始查询全文见 `outputs/subd_six_etf_v1_3_acceptance_20260904/network/表现.txt`。来源为已验证Tencent前复权与AkShare/Eastmoney前复权；实时入口另请求Eastmoney快照。不同时间/供应商的历史修订可能改变结果，不能将刷新差异归因于版本变动。

## 6. 摩擦和安全边界

沿用收盘信号/收盘成交研究口径：旧持仓赚取当日close-close收益，新持仓从下一行开始。未新增盘口容量、QDII溢价、开盘冲击、逐笔涨跌停/T+1成交仿真。实时展示保留价格tick/涨跌停参考价、行情时间差、日历、交易时间窗与SELL可卖数量保护；未接券商实盘持仓，输出仅为模型信号和手动执行参考。

## 7. BUG排查与验证证据

本次已修复/防止：

- Score参数、筛选状态和红灯提示使用非整数格式，正确显示0.5及5.5，不再四舍五入成0/6。
- 目标波动率关闭后不对None做百分比格式化；参数、信号、实时参数统一标明关闭。
- 去除报告中的“先建50%/等下跌日补足”生效描述，明确一次全额建仓。
- 资产互换正确保留双边交易腿、换手和费用；无杠杆、无额外叠加层重算。
- 正式前复权来源全部失败时直接失败，不调用最终会被正式入口拒绝的未复权fallback；原始helper仅保留诊断用途。
- 未确认当日bar不进入正式历史表现；实时信号明确为假设收盘结果。

测试分层：

1. 冻结实数逐日核对、五窗口正式指标核对、Score/R²精确边界、无候选现金、热身期、前缀无未来泄漏、输出交易腿恒等式。
2. Poe注入对象启动、参数/信号/实时信号/实时参数/表现/CSV/PNG输出，图片已视觉检查；这些是本地兼容接口测试，不冒充托管端。
3. 复用33项已存在的对抗场景，在新模块上检查陈旧/偏斜报价、不可信来源、价格质量、tick/涨跌停、交易腿禁用、未复权拒绝、缓存刷新与收盘边界。
4. 全库 `566 passed, 1 skipped, 1 warning`；跳过项是默认关闭的真实网络冒烟，另用显式开关执行。警告来自第三方fastapi_poe/Pydantic弃用提示，不是策略异常。

复现命令：

```powershell
python -X utf8 -m pytest -q --junitxml=outputs/subd_six_etf_v1_3_acceptance_20260904/pytest_full.xml
$env:SUBD_V13_NETWORK_SMOKE='1'
python -X utf8 -m pytest -q -s tests/test_poe_subd_six_etf_v1_3.py -k real_network
python -X utf8 -m py_compile poe_subd_six_etf_v1_3_bot.py
git diff --check
```

真实网络测试已完成：`1 passed, 25 deselected, 1 warning`，253.01秒，七个入口全部通过（参数、信号、表现、交易记录、净值曲线、实时信号、实时参数）。逐项状态及来源保存在 `outputs/subd_six_etf_v1_3_acceptance_20260904/network/results.json`。真实盘中Eastmoney快照成功返回；行情变化仍按未确认bar处理，没有生成自动订单。最终编译和diff检查通过，原两份Poe脚本及V1.1研究核心/runner的git差异为空。

## 8. 未完成的外部验证与风险

尚未获得poe.com目标Bot/编辑页，也未上传或发布，因此**不声称完成Poe托管端实测**。本地测试不能排除平台包版本、运行时限、网络权限或附件配额差异；需要目标Poe环境再验证。测试能排除已覆盖的问题，不能保证不存在任何BUG。

参数仍来自多轮重叠历史样本，没有新独立OOS/走步验证，不因脚本成版就宣称消除过拟合。

## 9. 备份与回退

原版脚本与文档备份在 `.codex_backups/20260904_132612/`；新V1.3首次修正前快照在 `.codex_backups/20260904_133136/`，已验证目录存在。旧版源码未改变，回退使用原文件即可，不需覆盖或删除任何历史版本。研究决定记录和README已增加新六ETF V1.3的明确指向。
