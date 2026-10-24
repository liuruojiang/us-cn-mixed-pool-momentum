# 报告查询修复独立验收

结论：35 项全部通过。原 20 项中的 4 个真实失败已转为通过；新增 15 个边界全部通过。本轮没有发现逗号修复引入的新缺陷。

- 验收源码 SHA256：`daf96cf4b39ab2919c9e8b7d82e74f96177748a1f4c5a6be2da7b5637e4965ca`。
- 修复位置：`parse_all_date_ranges` 支持 `[、，,；;]` 切分，并保留 `以及` / `和`、日期范围连词和原有去重语义。
- 原 20 项：`original20.txt`，20 passed。
- 新 15 项：`new_boundaries15.txt`，15 passed。
- 新测试源码：`tests/test_v13_takeover_fix_reporting_20261024.py`。

新增验收覆盖：混合分隔符、空白与连续逗号、头尾空片段、重复日期窗口及不同语法的同义窗口、跨月重叠窗口、闰日单日、无交易记录区间、0.5/1.5 年相对区间。每个有效查询都通过正式 `SubDSixEtfV13Bot.run()` 输出 CSV，再独立从真实冻结 daily 按日期和非零 turnover 选行，核对全部日期、成本总和、换手总和。后续项目包含非法日期或逆序范围时，正式处理器在产生附件前报错，没有只交付前半请求。

冻结数据沿用 `outputs/doublecheck_script_audit_20261007/final_network/confirmed_daily.csv.gz`，2011-12-09 至 2026-09-30，共 3597 行；SHA256 `9907b425ec3b1c8c816e6bc3e73c72af315a7cd5e738e702d92d7709f99f6456`。Poe 传输由捕获器替代，禁止网络，没有改动价格、收益、成本或换手。验收属于本地冻结输出链验证，不等于线上 Poe 或当前市场行情验收。

运行前明确设置 `V13_TAKEOVER_REPORT_EVIDENCE` 为 `outputs/takeover_fix_20261024/report_review`，原 20 项的新结果只写新目录，没有覆盖旧审计失败证据。运行使用 `python -B -m pytest ... -p no:cacheprovider -q --tb=short`，未生成 pytest 缓存。仅发现既有 `fastapi_poe` / Pydantic 弃用警告，不影响本轮通过结果。

未改正式源码、未删除文件、未推送。新测试与证据保留，未产生待清理临时文件。
