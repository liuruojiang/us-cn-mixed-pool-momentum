# L0 独立审计 B：输入快照与旧产物身份（2026-09-26）

范围：只审版本、代码和输入/旧产物的元信息；不复用执行者绩效函数，不做 L1 行级数据质量或 L2 账户复算。此文件独立于审计 A；旧报告及 `parity.json` 均是待核记录，不当作新的正确性证明。

## 结论

**L0 身份链 PASS，当前数据新鲜度限制。**本仓库的最新六只中国上市 ETF 正式代码为 `poe_subd_six_etf_v1_3_bot.py`，当前工作树 SHA256 `21a5867f51367d215a6f9913dafae1a462bf2316f7c59e7a860d43448c63ee72`，Git blob 与 HEAD 相同（`d4aa3f9346ce2f0c26549edfeb904ee58d4bfc4f`）。`poe_subd_mixed_pool_v1_3_bot.py` 是另一家族（QQQ/GLD/创业板指数/KMLM/豆粕），SHA256 `cd4235b0dddab8e07695bf852239e5fc473ad2cf09e7c22980a7441cced9753e`；不能以同名 V1.3 混用。证据：`AGENTS.md:11-13`、`README.md:6-16`、`docs/subd_six_etf_v1_3_20260904.md:3-7`、两源码的 `ASSETS` 定义 `poe_subd_six_etf_v1_3_bot.py:98-105` / `poe_subd_mixed_pool_v1_3_bot.py:98-104`。

| 身份 | 文件 | 本次 SHA256 | 实测覆盖 | 角色 |
| --- | --- | --- | --- | --- |
| 冻结六 ETF qfq 价格面板 | `quant_param_scan_runs/20260903_mixed_us_cn_momentum_subd_v1_1_clean_momentum_base_six_etf_mixed_pool_r2_threshold_x_switch_buffer/price_snapshot_qfq.csv.gz` | `0cc4af45158d6aaab4594b869b79309a96e8e3cc2f21a0205c38128913bec2aa` | 2011-12-09—2026-09-02，3578 行，`date` 加六只 ETF 列 | 回放的冻结输入；不是最新行情 |
| Score 5.5 旧研究选择曲线 | `quant_comparison_runs/20260904_subd_selected_score_max_5p5/cap_5p5_daily.csv.gz` | `8913d725d912d328dfa8d8d90f63b5a395d95771a025da803e29f34fd5f36356` | 同上 3578 行；`version=selected_research`、`scenario=cap_5p5` | V1.3 成版前的比较对象，不是价格输入或正式回测 |
| 六 ETF V1.3 验收曲线 | `outputs/subd_six_etf_v1_3_acceptance_20260904/daily.csv.gz` | `e8065c1706320d27bf9333065de99c26327331375fd534ecbe14b8946558d5ce` | 同上 3578 行；`version=1.3`、`scenario=v1_3_naive_score_0p5_5p5_r2_0p25` | 旧正式成版的冻结回放产物，待独立复算 |
| 9/4 盘中网络抓取 | `outputs/subd_six_etf_v1_3_acceptance_20260904/network/confirmed_daily.csv.gz` | `672c1dd9132c013bb16d287df2998814acafa5900eb8776b51f8a5025da89a3d` | 2011-12-09—2026-09-04，3580 行 | 不属于上述冻结一致性测试；末行 9/4 盘中，不可按文件名当完整收盘 |

以上哈希、列、首末日期和行数由本次只读读取压缩 CSV 与 `Get-FileHash -Algorithm SHA256` 实测。冻结面板身份与 `scan_meta.json:44-76`、研究报告 `quant_comparison_runs/20260904_subd_selected_score_max_5p5/report.md:7-17`、正式版本文档 `docs/subd_six_etf_v1_3_20260904.md:9-26,48-50` 的记载一致。旧验收 `outputs/subd_six_etf_v1_3_acceptance_20260904/parity.json` 记载对研究曲线的 NAV 最大差 `7.105427357601002e-15`，但这只是旧记录，L2 应独立重建。验收测试的输入哈希门禁在 `tests/test_poe_subd_six_etf_v1_3.py:29-40`，旧 `parity.json` 在同文件 `:55-76` 写出。

源码正式取数序列是逐 ETF `AkShare/Eastmoney qfq -> Tencent fqkline qfq -> Eastmoney HTTP qfq`，原始未复权 helper 不进入正式入口；见 `poe_subd_six_etf_v1_3_bot.py:1246-1285,1305-1318`。冻结研究面板来源是 Tencent qfq；正式入口再次联网时可因逐代码 fallback 产生不同来源组合，故同名 V1.3 不保证字节相同。见 `docs/subd_six_etf_v1_3_20260904.md:64-76`。历史文档明确当日盘中 bar 不进正式表现，`network/confirmed_daily.csv.gz` 末行虽为 9/4，但旧表现截止 9/3；见该文档 `:66,90-91`。当前日期 9/26，所列冻结面板终点 9/2，只能用于旧回测重认证；若要声称“当前表现/信号”，须另行刷新、保存并核定最新完整交易日快照。

## 独立拒绝反例与首个差异

1. 把旧研究曲线喂给价格入口：其列包含 `position/nav/return`，不等于冻结面板的 `date` 加六只 ETF；本次集合门禁输出 `research_curve_rejected_as_price_input=True`。即使两者同为 3578 行也应拒绝。
2. 用混合池 V1.3 源码冒充六 ETF V1.3：其 SHA256 不等于验收 `parity.json` 的 `bot_sha256`；资产集合只与六 ETF 重合 `159985.SZ`，本次门禁输出 `mixed_code_rejected_by_hash=True`。同样不能将 QQQ/GLD/KMLM 价格列填入六 ETF qfq 面板。
3. 用 9/4 网络 CSV 覆盖 9/2 冻结面板：行数 3580 对 3578，终点 9/4 对 9/2，哈希不同；末行抓取时间 `2026-09-04 13:32:42`，`cached_bar_state=intraday`。本次门禁输出 `network_capture_newer_than_frozen=True`。该文件名含 `confirmed` 不能代替时点字段。
4. 将 9/13 两个研究目录当正式版本：两目录 `scan_meta.json` 的 `decision` 分别是 `research_only_keep_daily`、`research_only_no_production_change`，均引用相同六 ETF 正式源码哈希及 9/2 冻结 close 哈希；目录当前未被 Git 跟踪。周频或次日开盘结果不能反向改写正式每日收盘模型。证据：各 `scan_meta.json:9-14,30-43,58-82` 与 `git status --short`、`git ls-files`。
5. 旧研究上限 5 与 5.5 曲线来自同一旧比较目录，本次只读找出的首个 `position/return` 差异为 **2013-05-08**：上限 5 的 `position=CASH`，5.5 的 `position=159915.SZ`。这证实两条研究臂不可误当同一曲线，但不证明其中任何收益计算正确；该事件归 L2/L6 复核。

## 对 L0 的影响和后续边界

9/13 研究目录未改变正式代码或冻结输入身份；当前 `git hash-object poe_subd_six_etf_v1_3_bot.py` 与 `git rev-parse HEAD:poe_subd_six_etf_v1_3_bot.py` 都为 `d4aa3f9346ce2f0c26549edfeb904ee58d4bfc4f`。旧上限 5/5.5 首个分歧只说明参数谱系中有真实不同路径，不构成 L0 版本冲突。价格面板/旧曲线/正式验收曲线的元信息可以冻结；尚未验证关键行、供应商调整、历史可知性和成交时钟，交给 L1。绩效在 L0 标为 N/A。
