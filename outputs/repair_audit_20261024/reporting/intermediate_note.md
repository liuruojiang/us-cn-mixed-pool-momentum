# 中间测试记录

- 首轮16项通过，72.76秒，运行起点源码 SHA256 为 `aead84a29508c28df28c1b10e4b75a7eb98acfb93927c46b3f897545d9b59a7b`。
- 随后将9月1日双缺价测试收紧为实际买卖双腿 `518880.SH` 与 `159985.SZ`，并要求每条缺价交易腿均保留于状态输出。
- 第二轮16项通过，64.76秒，输出 `pytest.xml`。此轮跨越主Agent补修源码的时间，可能混合加载中间版本，不作为最终版本验收。
- 最终验收另存 `final_pytest.xml` 与 `report.md`；不将中间结果混作最终hash的证据。
- `f8953b458cad5bc3947c7d5c4833fa67394a909eb60b549dbd89da4931cfd13f` 第一次运行15通过、1失败（58.67秒），保留为 `fixture_gap_pytest.xml`。原因是旧测试替换了完整日历loader、却没有实现正式loader发布内存日历的副作用；2025-01-01因此缺少覆盖证据并保守关闭信号。正式loader源码确认会发布该缓存。
- 修正测试边界为只注入真实归档 `_load_cached_cn_trading_days` 输入、禁用网络AkShare，保留完整正式日历loader、内存状态及覆盖验证。没有改变任何期望日期、有效性或导出断言，也没有改变生产代码。
- `f895` 版修正夹具后16项通过（42.50秒），XML另存 `f895_16_passed_pytest.xml`。随后独立完整查询反例发现混合顿号和“和”遗漏2026年，新增三个手写期望用例；补修前导出子集1失败、6通过（7.16秒），保留 `mixed_before_pytest.xml`。
- 主分支补修为 `8354e9c4b835c77f11809d5d0b727f54e75e7f7bc5a1fc5aa282ccb73bfd1f57` 后重新运行完整查询探针，默认 `mixed_conjunction_result.json` 与 `.txt` 为修复后版本；`after_copy` 文件也是修复后副本，其JSON内嵌hash已核对。补修前反例以 `mixed_before_pytest.xml` 为落盘证据，不以这些after文件冒充before。
