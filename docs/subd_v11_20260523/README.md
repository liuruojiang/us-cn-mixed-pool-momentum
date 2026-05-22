# SubD V1.1 2026-05-23 收尾记录

## 结论

本轮只正式保留一个生产参数改动：SubD V1.1 的 target-vol scale 调整阈值设为 `0.075`。该阈值已经同步到正式脚本和 Poe 脚本：

- `run_subd_six_etf_v1_1.py`
- `poe_subd_six_etf_v1_1_bot.py`

半仓建仓规则不改。对照结果显示，当前“任意新资产先 50%，等待下跌日补足”的 1.1 规则在 5 年和 3 年窗口同时优于 cash-only 半仓和直接全仓进入；近 1 年直接全仓收益略高，但回撤明显更深。

## 数据与口径

- 基准 artifact：`outputs/subd_six_etf_v1_1_20260509_daily.csv`
- 样本：2011-12-09 至 2026-05-08，共 3496 行
- 官方记录的数据源：AkShare/Sina ETF 日收盘，raw/unadjusted as served by Sina
- 成本：单边换手成本 `0.001`
- Target-vol：目标波动 `25%`，窗口 `80`，最大杠杆 `1.5`
- 执行时点：target-vol scale 继续使用一日 shift 后才影响收益
- 未建模：额外开盘冲击、融资成本

## Target-Vol Scale 阈值

规则：只有当 `abs(raw_next_scale - last_confirmed_scale) >= threshold` 时，才更新确认后的 target-vol scale；否则沿用上次确认值。

细扫 `0.05` 至 `0.10` 的关键结果：

| threshold | 5Y ann | 5Y maxDD | 3Y ann | 3Y maxDD | 1Y ann | 1Y maxDD | 5Y scale days |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.000 | 61.43% | -18.05% | 99.01% | -16.55% | 92.74% | -12.75% | 1260 |
| 0.055 | 61.65% | -18.10% | 99.35% | -16.40% | 93.13% | -12.86% | 78 |
| 0.075 | 62.39% | -18.10% | 100.80% | -16.30% | 94.41% | -12.86% | 53 |
| 0.100 | 61.74% | -18.35% | 98.78% | -16.30% | 92.68% | -12.86% | 34 |

选择 `0.075` 的原因：5 年 scale 调整天数从 1260 降到 53，近期 5/3/1 年收益和回撤没有恶化，且在细扫里近期综合表现最好。

## 半仓规则对照

该对照不作为生产改动，只用于确认是否应删除半仓规则。

| window | current all-new 50% | cash-only 50% | full entry | cash-only delta | full-entry delta |
|---|---:|---:|---:|---:|---:|
| 5Y ann | 61.43% | 54.71% | 56.18% | -6.72pct | -5.24pct |
| 5Y maxDD | -18.05% | -23.34% | -20.93% | -5.29pct | -2.88pct |
| 3Y ann | 99.01% | 96.14% | 95.90% | -2.87pct | -3.12pct |
| 3Y maxDD | -16.55% | -18.67% | -18.81% | -2.12pct | -2.26pct |
| 1Y ann | 92.74% | 93.62% | 95.65% | +0.88pct | +2.91pct |
| 1Y maxDD | -12.75% | -15.30% | -15.27% | -2.55pct | -2.52pct |

判断：直接全仓只在近 1 年提高收益，但回撤变深；5 年和 3 年都不如当前规则。保留当前“换任意新资产也先半仓”的 V1.1 行为。

## 归档文件

- `target_vol_threshold_coarse_record.md`
- `target_vol_threshold_fine_record.md`
- `artifacts/target_vol_threshold_coarse_window_metrics.csv`
- `artifacts/target_vol_threshold_coarse_scan_summary.csv`
- `artifacts/target_vol_threshold_fine_window_metrics.csv`
- `artifacts/target_vol_threshold_fine_scan_summary.csv`
- `artifacts/entry_scope_comparison.csv`
- `artifacts/entry_scope_summary.csv`

未归档大文件：

- `daily_curves.csv`
- `subd_v11_entry_scope_impact_artifact_20260508_daily.csv`

这些是可重建诊断曲线，体积较大，不进入正式文档包。

## 清理计划

归档后删除以下临时测试/扫描产物：

- `test_subd_v11_scale_threshold.py`
- `__pycache__/`
- `quant_param_scan_runs/20260523_mixed_us_cn_momentum_subd_v1_1_six_etf_mixed_pool_target_vol_scale_rebalance_threshold/`
- `quant_param_scan_runs/20260523_mixed_us_cn_momentum_subd_v1_1_six_etf_mixed_pool_target_vol_scale_rebalance_threshold_fine_0p05_0p10/`
- `quant_param_scan_runs/20260523_subd_v11_entry_scope_impact/`

保留 `quant_param_scan_runs` 下已有的历史扫描目录，不做额外清理。
