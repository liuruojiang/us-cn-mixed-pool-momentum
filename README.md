# 美股A股混合池子动量策略

本目录是该策略后续的专门库区。当前包含以下策略系列：

- `SubD 六 ETF V1.1`：六资产动量策略，已纳入乖离率动量过热过滤和先进 50% 逻辑。
- `SubD 六 ETF 朴素版 V1.3`：本轮选定的简化组合，全额建仓、不加杠杆。
- `SubD 混合代理池 V1.3`：另一资产池的历史独立版本，不与六ETF朴素版混用。
- `ABCDE 组合对比`：按 A 10%、B 15%、C 10%、D 20%、E 40% 的组合脚本，并保留 B 60% 基准对比。

## 主要脚本

- `research_subd_six_etf_weighted_slope.py`：SubD 六 ETF 研究和回测核心。
- `run_subd_six_etf_v1_1.py`：SubD V1.1 正式输出入口。
- `poe_subd_six_etf_v1_1_bot.py`：SubD V1.1 自包含 Poe 展示脚本。
- `poe_subd_six_etf_v1_3_bot.py`：2026-09-04 六 ETF 朴素版 V1.3，自包含 Poe 脚本；`0.5 < Score < 5.5`、`R² >= 0.25`、25日线性加权Top1、全额建仓，Buffer/分批/过热/目标波动率关闭，现金收益0、单边成本0.10%。与下一项混合代理池V1.3不是同一策略。版本说明及验收见 `docs/subd_six_etf_v1_3_20260904.md`。
- `poe_subd_mixed_pool_v1_3_bot.py`：A 股/美股混合池 V1.3 自包含 Poe 展示脚本。
- `analyze_subd_six_etf_v1_1_qveris_robustness.py`：历史归档的 QVeris 数据源复核脚本；当前正式入口不再使用 QVeris。
- `analyze_abcde_combo_20260509.py`：ABCDE 组合和 B60 基准对比。
- `mnt_bot V 7.6 plus.py`：组合脚本依赖的 A/B/C 官方路径快照。

## 主要结果

- `outputs/subd_six_etf_v1_1_20260509_summary.csv`
- `outputs/subd_six_etf_v1_1_20260509_daily.csv`
- `docs/subd_six_etf_v1_1_20260509/`
- `docs/abcde_combo_20260509/`

组合结果以 2020-01-02 之后为主，因为 D 策略只适合从 2020 年开始纳入对比。

## 运行

```powershell
python .\run_subd_six_etf_v1_1.py
python -X utf8 .\poe_subd_six_etf_v1_3_bot.py 参数
python -X utf8 .\poe_subd_six_etf_v1_3_bot.py 信号
python -X utf8 .\poe_subd_six_etf_v1_3_bot.py 表现
python .\analyze_abcde_combo_20260509.py
```

数据源规则见 `AGENTS.md`。Poe 脚本的正式 A 股历史路径只接受 AkShare/Eastmoney qfq、已验证的 Tencent fqkline `qfqday/day` 和 Eastmoney HTTP qfq；所有候选序列都经过连续性与覆盖范围校验。新浪与新华财经原始日线的精确日期交集仅保留为 `159985.SZ` 的诊断 helper，不得进入正式信号或绩效路径。QVeris 相关材料只作为历史归档证据保留。

V1.1/V1.3 的 2026-08-12 对抗修复、正式同输入回测和回滚信息见 `docs/subd_v11_v13_adversarial_repair_20260812.md` 与 `outputs/subd_v11_v13_repair_formal_comparison_20260812/report.md`。
