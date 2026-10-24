# 日历修复的独立复审

结论：本轮针对性复核未发现新增缺陷。相关旧测试及首轮 6 个反例合计 **59 passed**；新增修复对抗测试 **10 passed**，总计 69 个不同测试通过。非全仓测试，不代表当前实时数据/部署验证。

## 独立验证内容

- 首轮行情与日历共同漏掉 2026-09-22 已被拒绝；已知官方休市日 2026-01-01 被供应商日历多报时，完整真实行情不再被误拒。
- 行情和日历共同添加假期/周末假 bar 均拒绝；同时再混入真实交易日漏日亦拒绝。
- 官方覆盖外 2025 会话集合保持供应商原样，未利用 2026 官方参考猜测其他年份。
- 正常日历不触发刷新、不替换缓存对象；修复后的复合日历内存衔接有效，不伪装供应商日历写盘。
- expected=None 仍保持无日历关闭，不借官方参考无限扩权。
- 从不可变提交 f1fe6ac 提取原代码，使用相同真实行情、日历、时点，分别跑正式 provider -> load_close -> _build_v13_daily；整个 daily DataFrame `assert_frame_equal(check_exact=True)` 及来源描述完全一致。此项验证正常输入全部输出列不变，未报告故障注入收益。

## 数据与运行

真实冻结行情：outputs/doublecheck_script_audit_20261007/final_network/raw_prices_qfq.csv.gz，截取至 2026-09-24，共3594行、6个ETF。

日历：outputs/script_audit_20261007/calendar_cache_for_replay.csv。故障通过内存注入，不改历史源文件，无远端调用。

新增测试：tests/test_v13_takeover_fix_data_20261024.py。

旧测试命令：
```
python -B -m pytest -q -p no:cacheprovider tests/test_v13_takeover_data_20261024.py tests/test_v13_postfix_data_20261024.py tests/test_v13_doublecheck_data_20261007.py tests/test_v13_audit_data_20261007.py tests/test_v13_repair_20261024.py -k "calendar or trading or history or hole or provider or alignment or recovery or unchanged_real" --basetemp=outputs/takeover_fix_20261024/data/scratch/prior --junitxml=outputs/takeover_fix_20261024/data/prior_results.xml
```

新增测试命令：
```
python -B -m pytest -q -p no:cacheprovider tests/test_v13_takeover_fix_data_20261024.py --basetemp=outputs/takeover_fix_20261024/data/scratch/paired --junitxml=outputs/takeover_fix_20261024/data/final_results.xml
```

证据：prior_pytest.txt / prior_results.xml 与 final_pytest.txt / final_results.xml。第一次新增测试未包含配对重放的 9 passed 记录另存 new_pytest.txt，仅作过程记录，不累计重复数。

没有改正式源码、删除文件或推送。可手动清理临时范围为本目录 scratch/，含从 Git 提取、可再次生成的旧代码副本。测试文件及结果日志属于复现证据，建议保留。
