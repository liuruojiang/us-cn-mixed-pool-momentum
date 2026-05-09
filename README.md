# 美股A股混合池子动量策略

本目录是该策略后续的专门库区。当前放置两类内容：

- `SubD 六 ETF V1.1`：六资产动量策略，已纳入乖离率动量过热过滤和先进 50% 逻辑。
- `ABCDE 组合对比`：按 A 10%、B 15%、C 10%、D 20%、E 40% 的组合脚本，并保留 B 60% 基准对比。

## 主要脚本

- `research_subd_six_etf_weighted_slope.py`：SubD 六 ETF 研究和回测核心。
- `run_subd_six_etf_v1_1.py`：SubD V1.1 正式输出入口。
- `analyze_subd_six_etf_v1_1_qveris_robustness.py`：QVeris 数据源复核和 V1.1 参数稳健性扫描。
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
python .\analyze_abcde_combo_20260509.py
```

数据源规则见 `AGENTS.md`。QVeris 可用时优先用于 A 股行情复核，密钥只从环境变量读取。
