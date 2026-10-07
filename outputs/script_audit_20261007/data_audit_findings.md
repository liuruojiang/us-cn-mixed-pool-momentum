# 六 ETF V1.3 数据链对抗审计（2026-10-07）

范围：`poe_subd_six_etf_v1_3_bot.py`，修复前 HEAD `5ddedd4`，不是旧 mixed-pool V1.3。正式参数冻结。主 Agent 统一修改源码，本审计仅写独立探针、回归测试和证据。

## 已复现缺陷及最小修复

| 严重性 | 修复前函数／行号 | 可运行反例与影响 | 修复建议 |
| --- | --- | --- | --- |
| P1 | `_load_public_close_with_per_code_fallback` 1246–1285 | 首选 AkShare 对 159915.SZ 只返回真实冻结面板最后 20 行或 640 行，仍当成功；完整 Tencent 备用源未调用。20 行案例经 `load_close` → `_build_v13_daily` 正式链运行，daily 起点从 2011-12-09 缩至 2013-07-29，最新 159915 原始评分为 NaN。最新日期正确不能证明历史或评分池完整。 | 各 provider 成功接收前校验完整日期结构、有限正价、评分行数和既有已验证历史第一日；失效触发原有备用源。第一日锚点是项目现有历史覆盖证据，不声称 ETF 上市日。 |
| P1 | `_load_tencent_qfq_one_close` 426–527 | 第一页为真实最新 640 行，次页连续空响应或重复同页，原码返回去重后的 640 行（2024-02-02–2026-09-24），把已存在的 2011–2024 历史丢掉。 | 校验每页请求范围、日期合法性、分页进展和最终已验证首日覆盖；未满足时拒绝部分历史并让上层 fallback。 |
| P2 | 同一 per-code fallback，AkShare parser 338–364 | 重复日期直到 concat 才报错，备用源不触发；常量 0／Inf 主源先被接收而非 fallback；NaT 经 parser 的日期切片静默丢弃，接收端校验已看不到原始错误。 | 在切片前校验日期和价格；统一 provider 校验后先生成 source record，再 append 数据与 record，避免半提交污染。 |
| P2 | `align_prices_to_common_valid_date` 2425–2434 与 `_price_forward_fill_flags` 1387 | `not-a-price` 被转换成 NaN 并前填成 3.42，原始 `.isna()` 为 False，故填价 mask 为 False。 | 对非空非数字价格直接拒绝。此为 helper 合同漏洞；三个正式 loader 的 `.astype(float)` 已拒绝普通文本，因此没有冒称文本可从真实供应商 parser 直接漏入生产。 |
| P2 | `align_prices_to_common_valid_date` 2454 | expected calendar 为空集合时跳过所有日期校验，单行周末 10-03 或国庆休市 10-07 正价面板被接受。 | 即使 expected 为空仍检查 unexpected common dates。完整多年面板原本会检查非交易日；此反例对应短窗口 helper 合同。 |
| P2 | `_status_calendar_sessions` 4093 | provider 日历为 None 时不使用已有可信 2026 官方日历，10-07 被普通工作日 fallback 当作交易日，期望确认日期变成 10-07。 | None／空集合同样尝试官方 2026 后备。原状态 `calendar_available=False` 已关闭执行，因此属于可用性和显示错误，并非原码允许节假日下单。 |
| P2 | `_cached_daily` 3515 | 正常 live 缓存时间晚于现在 3 分钟，`age <= TTL` 成立而复用未来时间缓存。 | 缓存命中条件要求 `0 <= age <= TTL`。force-refresh 失败分支原已有负 age 拒绝。 |

## 真实数据证据与故障注入边界

- 故障注入基于真实 `outputs/recert_l1_20260926/prices_raw_qfq_through_20260924.csv.gz`：3594 行，2011-12-09 至 2026-09-24。它不是本次最新数据，不用于声称当前信号或新绩效。
- 修复前独立代码探针：`data_probe.py` 和 `data_probe_results.json`。完整 source chain 只在内存中替换供应商响应，使用正式 parser、loader、alignment、curve builder；未写正式价格或日历缓存。
- 修复前 20 项对抗测试为 **13 FAIL / 7 PASS**，见 `data_tests_before.txt`。正常完整分页、0／负数／Inf 对齐拒绝、全市场中间缺日拒绝、单资产缺价填充标记均通过。
- 主 Agent 修复后独立重跑：`python -X utf8 -B -m pytest tests/test_v13_audit_data_20261007.py -p no:cacheprovider -q --tb=short`，**20 PASS**，pytest 用时 4.98 秒；仅出现第三方 Pydantic 弃用警告。日期／价格比较保持严格，只忽略不同供应商的 index 名称标注。NaT 在 AkShare／Eastmoney 切片前被拒，避免静默丢弃。
- 最新真实双源独立抽样是 2026-09-16 至 2026-09-30 的 10 个交易日，排除 09-25。Tencent 和 Sina 六只各 10 行，精确日期集一致，共 60 个配对收盘，最大绝对差 **0**，末日均为 **2026-09-30**。见 `data_recent_final_comparison.json`；每个 raw payload、请求参数、接收时间与 SHA256 均保留。
- 腾讯实际键：159915／159941／518880 为 `qfqday`；513030／513520／159985 为 `day`。Sina 为原始未复权日线。这验证近期现价／日期一致，不延长 `day` 全历史前复权语义认证，也不证明过去点时可得性。
- 首轮 Sina 四只出现 12 秒读取超时；降低并发至 2、25 秒超时仅一次重试后全部成功。首轮与恢复轮分别保留，不把超时说成来源不存在。

## 官方日历

上交所公告：<https://www.sse.com.cn/disclosure/announcement/general/c/c_20251222_10802507.shtml>，上证公告〔2025〕45号，2025-12-22；本次实时打开核对。10 月 1 日至 7 日休市，10 月 8 日开市。因此本次 2026-10-07 最新完整中国 ETF 交易日应为 2026-09-30。

## 覆盖与限制

覆盖 qfq allowlist、正式 source chain、分资产 fallback、腾讯分页、首日／行数、无效价格／日期、共享缺日、单只缺价、填价标记、节假日日历、负 age 缓存。未部署、提交、下单或外发；未增加正式数据源；未使用 QVeris。

未重新认证完整历史 qfq 的供应商语义、公司行动时点、点时历史快照、可成交价或账户卖出资格；本审计不输出策略收益指标。主 Agent 的完整源码／回放／执行验证和最终报告负责整体裁决。
