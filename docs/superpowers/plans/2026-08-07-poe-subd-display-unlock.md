# Poe SubD V1.1 / V1.3 Display Unlock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore normal Poe display of V1.3 signals and report outputs without policy-only warnings or refusal, while confirming V1.1 remains open and preserving every genuine data-integrity safeguard.

**Architecture:** Remove the V1.3 presentation-wide cross-market policy from the Poe surface instead of falsifying the policy flag. The existing signal/performance loaders, calculations, calendars, freshness checks, adjusted-price checks, stale-trade checks, and request-local response state remain unchanged. V1.1 production code is characterization-tested but not modified.

**Tech Stack:** Python 3.14, pandas, fastapi-poe, pytest, PowerShell, Git.

---

## File Map

- Modify: `tests/test_poe_subd_mixed_pool_v1_3_regressions.py` — replace policy-refusal expectations with normal-display expectations.
- Modify: `poe_subd_mixed_pool_v1_3_bot.py` — remove the policy-only display/refusal layer; retain loaders and calculations.
- Verify unchanged: `poe_subd_six_etf_v1_1_bot.py` — V1.1 signal and performance display paths must remain open.
- Verify unchanged: `tests/test_poe_subd_external_review_regressions.py` — existing V1.1 handler and report coverage.
- Modify: `docs/poe_subd_p1_correctness_repair_20260711.md` — append a narrow supersession note for the display policy without rewriting the historical P1 record.

The production and test files already contain uncommitted P1 repair work. Back them up before editing, keep the diff narrow, and do not commit overlapping pre-existing changes without explicit user authorization.

### Task 1: Back Up The Overlapping P1 Files

**Files:**
- Back up: `poe_subd_mixed_pool_v1_3_bot.py`
- Back up: `tests/test_poe_subd_mixed_pool_v1_3_regressions.py`
- Back up: `docs/poe_subd_p1_correctness_repair_20260711.md`

- [ ] **Step 1: Record the starting diff**

Run:

```powershell
git status --short
git diff -- poe_subd_mixed_pool_v1_3_bot.py tests/test_poe_subd_mixed_pool_v1_3_regressions.py
```

Expected: the two code/test files already contain the P1 repair; unrelated dirty files remain untouched.

- [ ] **Step 2: Create a filesystem backup**

Run:

```powershell
python D:\Codex\home\skills\quant-research\scripts\backup_paths.py --root D:\动量策略\美股A股混合池子动量策略 poe_subd_mixed_pool_v1_3_bot.py tests\test_poe_subd_mixed_pool_v1_3_regressions.py docs\poe_subd_p1_correctness_repair_20260711.md
```

Expected: the command prints a new `.codex_backups/<timestamp>` directory containing all three paths.

- [ ] **Step 3: Verify backup contents**

Run `Get-ChildItem -Recurse <reported-backup-directory>`.

Expected: all three named files are present.

### Task 2: Write V1.3 Normal-Display Regression Tests

**Files:**
- Modify: `tests/test_poe_subd_mixed_pool_v1_3_regressions.py:35-295`

- [ ] **Step 1: Replace the performance-refusal test with a provider-reach test**

Use this behavior:

```python
def test_v13_performance_reaches_provider_without_policy_only_refusal(monkeypatch):
    module = load_bot_module()
    provider_calls = []

    class ProviderReached(Exception):
        pass

    def provider_spy(*args, **kwargs):
        provider_calls.append((args, kwargs))
        raise ProviderReached

    monkeypatch.setattr(module, "_get_daily_for_today", provider_spy)

    with pytest.raises(ProviderReached):
        module.SubDMixedPoolV13Bot()._handle_performance("表现")

    assert len(provider_calls) == 1
```

- [ ] **Step 2: Replace the introduction refusal assertions with normal query promises**

Use these assertions after capturing `fastapi_poe.update_settings`:

```python
introduction = captured[0].introduction_message
assert "research-only" not in introduction
assert "不可执行" not in introduction
assert '发送 **"交易记录 过去两个月"** -> 调仓记录表 + 完整CSV' in introduction
assert '发送 **"净值曲线 过去两年"** / **"收益曲线 今年"** -> 绩效表 + 净值曲线' in introduction
```

- [ ] **Step 3: Replace the research-banner signal test with normal-display assertions**

Keep `minimal_signal_daily()` and the existing deterministic calendar monkeypatch, then assert:

```python
report = module.format_signal_report(
    daily,
    "unit-test",
    live=True,
    now=datetime(2026, 6, 18, 14, 55),
)

assert "research-only" not in report
assert "不可执行" not in report.split("### 信号摘要", 1)[0]
assert "## SubD混合池子 V1.3 实时操作信号" in report
assert "动量排名" in report
```

- [ ] **Step 4: Replace the global-policy status test with a no-policy-metadata test**

After calling `signal_data_status()` for `purpose="execution"`, assert the ordinary live checks determine the status:

```python
assert execution["exchange_all_legs_can_submit"] is True
assert execution["strategy_actionable_now"] is True
assert execution["actionable_now"] is True
assert execution["tradable"] is True
assert "research_only" not in execution
assert "research_only_reason" not in execution
```

- [ ] **Step 5: Add parameter and introduction no-warning coverage**

Use the existing `FakeMessage` pattern and assert:

```python
module.SubDMixedPoolV13Bot()._handle_params(live=False)
surface_text = "".join(writes) + module._v13_introduction_message()
assert "research-only" not in surface_text
assert "不可执行" not in surface_text
```

- [ ] **Step 6: Run the focused tests and verify RED**

Run:

```powershell
python -m pytest -q tests/test_poe_subd_mixed_pool_v1_3_regressions.py -k "performance_reaches_provider_without_policy_only_refusal or introduction or normal_display or policy_metadata or parameter"
```

Expected: failures show the current `V1.3 performance unavailable` `BotError`, research-only banners, or policy metadata. Syntax/import errors do not count as RED and must be corrected before proceeding.

### Task 3: Remove Only The V1.3 Presentation Policy

**Files:**
- Modify: `poe_subd_mixed_pool_v1_3_bot.py:151-200`
- Modify: `poe_subd_mixed_pool_v1_3_bot.py:4523-4870`
- Modify: `poe_subd_mixed_pool_v1_3_bot.py:5983-6020`
- Modify: `poe_subd_mixed_pool_v1_3_bot.py:6441-6610`

- [ ] **Step 1: Remove the global policy constants and helpers**

Delete only:

```python
FORMAL_CROSS_MARKET_MODEL_AVAILABLE = False
V13_RESEARCH_ONLY_REASON = (...)

def _v13_policy_state() -> dict[str, object]:
    ...

def _v13_policy_notice() -> str:
    ...
```

Do not change `START_DATE`, strategy parameters, data-source constants, or validation thresholds.

- [ ] **Step 2: Remove policy mutation from `signal_data_status()`**

Remove `policy = _v13_policy_state()`, the `and not policy["research_only"]` condition, the policy-only `execution_note` branch, and these return fields:

```python
"research_only": policy["research_only"],
"research_only_reason": policy["research_only_reason"],
```

Keep all ordinary calendar, quote, staleness, price-limit, session, and execution-window checks unchanged.

- [ ] **Step 3: Restore the normal signal report title and conclusion**

Replace the policy-conditional title and conclusion with the normal path:

```python
lines: list[str] = []
lines.append(f"## SubD混合池子 V1.3 {mode_label}操作信号")
lines.append("")
lines.append(f"信号日: **{sig['date']}** | 数据: **{data_status['label']}** | 来源: **{source_note}**")
lines.append("")
lines.append("### 结论")
lines.append("")
lines.append(f"**{conclusion}**")
```

Leave rankings, exposures, costs, and exception rendering unchanged.

- [ ] **Step 4: Remove the parameter warning**

Delete only the `_v13_policy_notice()` block in `_handle_params()`. Keep the parameter table unchanged.

- [ ] **Step 5: Remove the performance refusal**

Make `_handle_performance()` begin directly with the existing provider call:

```python
def _handle_performance(self, query: str):
    daily, source_note = _get_daily_for_today(data_state="confirmed")
```

Keep performance-window resolution, mandatory-window N/A handling, NAV rendering, trade records, CSV attachment, and request-local rendered state unchanged.

- [ ] **Step 6: Simplify the introduction to the normal display contract**

Implement `_v13_introduction_message()` as one normal response:

```python
def _v13_introduction_message() -> str:
    return (
        "**SubD混合池子 V1.3 信号查询**\n\n"
        "- 发送 **\"信号\"** -> 最新收盘确认信号（查询时刷新；收盘确认前不使用当天盘中bar）\n"
        "- 发送 **\"实时信号\"** -> 盘中/最新日线快照下的假设收盘信号\n"
        "- 发送 **\"参数\"** -> V1.3参数总览\n"
        "- 发送 **\"实时参数\"** -> 参数 + 实时数据快照\n"
        '- 发送 **"表现"** / **"表现 过去两年"** / **"今年收益"** -> 绩效表\n'
        '- 发送 **"交易记录 过去两个月"** -> 调仓记录表 + 完整CSV\n'
        '- 发送 **"净值曲线 过去两年"** / **"收益曲线 今年"** -> 绩效表 + 净值曲线\n'
    )
```

- [ ] **Step 7: Run the focused V1.3 tests and verify GREEN**

Run:

```powershell
python -m pytest -q tests/test_poe_subd_mixed_pool_v1_3_regressions.py
```

Expected: all tests in the file pass. The existing fastapi-poe Pydantic deprecation warning may remain; no new warning is accepted.

### Task 4: Confirm V1.1 Has No Equivalent Display Block

**Files:**
- Verify unchanged: `poe_subd_six_etf_v1_1_bot.py`
- Verify unchanged: `tests/test_poe_subd_external_review_regressions.py`
- Verify unchanged: `tests/test_poe_subd_live_signal_freshness.py`
- Verify unchanged: `tests/test_poe_subd_trade_records.py`

- [ ] **Step 1: Search for policy-only display blockers**

Run:

```powershell
rg -n -S "FORMAL_CROSS_MARKET_MODEL_AVAILABLE|V13_RESEARCH_ONLY_REASON|research-only|performance unavailable" poe_subd_six_etf_v1_1_bot.py
```

Expected: no matches.

- [ ] **Step 2: Run V1.1 Poe regression suites**

Run:

```powershell
python -m pytest -q tests/test_poe_subd_external_review_regressions.py tests/test_poe_subd_live_signal_freshness.py tests/test_poe_subd_trade_records.py
```

Expected: all tests pass. If a test exposes a genuine V1.1 display block, stop and add a failing test before changing V1.1 production code.

- [ ] **Step 3: Confirm V1.1 production source is unchanged by this task**

Run:

```powershell
git diff -- poe_subd_six_etf_v1_1_bot.py
```

Expected: only the pre-existing P1 diff is present; no new display-unlock hunk was added.

### Task 5: Reconcile Documentation Without Rewriting History

**Files:**
- Modify: `docs/poe_subd_p1_correctness_repair_20260711.md`

- [ ] **Step 1: Append a dated display-policy supersession note**

Append this section:

```markdown
## 2026-08-07 Poe Display Policy Supersession

The V1.3 policy-only Poe display block is superseded. Poe is a reporting surface and does not submit orders, so signal, performance, NAV-curve, and trade-record queries are displayed normally without research-only or non-executable banners.

This does not reverse the P1 data-integrity repairs. Cross-market timestamp alignment, executable-instrument mapping, next-session fill modelling, and USD/CNY conversion remain limitations of the displayed calculations; adjusted-price provenance, calendar validation, partial-response rejection, stale-transaction blocking, and request-local response state remain enforced.
```

- [ ] **Step 2: Verify documentation consistency**

Run:

```powershell
rg -n "2026-08-07 Poe Display Policy Supersession|does not reverse the P1 data-integrity repairs" docs/poe_subd_p1_correctness_repair_20260711.md
```

Expected: both phrases occur in the new final section.

### Task 6: Full Verification And Handoff

**Files:**
- Verify: `poe_subd_mixed_pool_v1_3_bot.py`
- Verify: `poe_subd_six_etf_v1_1_bot.py`
- Verify: all `tests/`

- [ ] **Step 1: Compile both Poe bots**

Run:

```powershell
python -m py_compile poe_subd_mixed_pool_v1_3_bot.py poe_subd_six_etf_v1_1_bot.py
```

Expected: exit code 0 and no output.

- [ ] **Step 2: Run the full test suite**

Run:

```powershell
python -m pytest -q
```

Expected: all tests pass; report the exact pass count and any existing warning.

- [ ] **Step 3: Check textual policy removal and diff hygiene**

Run:

```powershell
rg -n -S "FORMAL_CROSS_MARKET_MODEL_AVAILABLE|V13_RESEARCH_ONLY_REASON|research-only / 不可执行|V1.3 performance unavailable" poe_subd_mixed_pool_v1_3_bot.py tests/test_poe_subd_mixed_pool_v1_3_regressions.py
git diff --check
git status --short
```

Expected: the targeted code/test search returns no matches; `git diff --check` exits 0 apart from possible LF/CRLF conversion warnings; unrelated user files remain unchanged.

- [ ] **Step 4: Review the final scoped diff**

Run:

```powershell
git diff -- poe_subd_mixed_pool_v1_3_bot.py tests/test_poe_subd_mixed_pool_v1_3_regressions.py docs/poe_subd_p1_correctness_repair_20260711.md
```

Expected: only normal-display changes plus the pre-existing P1 work appear. Do not stage or commit the overlapping code files unless the user explicitly requests it.

- [ ] **Step 5: Report observed versus inferred results**

Report the backup directory, exact commands, exact test count, and whether any live provider/data run was attempted. State that display behavior is verified by tests and that no strategy calculation, order routing, or live execution was added.
