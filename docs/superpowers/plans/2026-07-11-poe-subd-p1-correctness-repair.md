# Poe SubD P1 Correctness Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the confirmed P1 correctness failures from the current working-tree versions of the Poe SubD 1.1 and 1.3 scripts without overwriting the user's existing edits.

**Architecture:** Preserve raw price availability through the strategy engine, fail closed when formal calendar or adjustment provenance is unavailable, isolate Poe response state per request, and downgrade the current V1.3 cross-market proxy surfaces to explicit diagnostic research. Each behavior is introduced through an observed RED regression before the smallest production change.

**Tech Stack:** Python 3.14, pandas, NumPy, pytest, ContextVar, existing Poe compatibility layer and provider loaders.

---

## Workspace Constraints

The current target scripts and regression tests already contain user modifications. They are the authoritative repair baseline. Do not reset, checkout, reformat, or replace them from `HEAD`.

Do not create task commits that would absorb pre-existing user edits. Use the quant-research filesystem backup plus focused `git diff` checkpoints. Only the already isolated design/plan documents may be committed separately.

## File Map

- Modify: `poe_subd_six_etf_v1_1_bot.py` — V1.1 loader, strategy engine, calendar validation, and Poe request state.
- Modify: `poe_subd_mixed_pool_v1_3_bot.py` — V1.3 loader, diagnostic/formal policy, strategy engine, calendar validation, and Poe request state.
- Modify: `tests/test_poe_subd_external_review_regressions.py` — shared V1.1 regressions and provider/calendar/request-state tests.
- Modify: `tests/test_poe_subd_mixed_pool_v1_3_regressions.py` — V1.3 provider, calendar, stale-trade, and research-only surface tests.
- Read/reference only: `run_subd_six_etf_v1_1.py:244-267` — accepted atomic stale-trade rejection behavior.
- Create: `docs/poe_subd_p1_correctness_repair_20260711.md` — verification record and rollback information.

### Task 1: Back up the authoritative dirty baseline

**Files:**
- Back up: `poe_subd_six_etf_v1_1_bot.py`
- Back up: `poe_subd_mixed_pool_v1_3_bot.py`
- Back up: `tests/test_poe_subd_external_review_regressions.py`
- Back up: `tests/test_poe_subd_mixed_pool_v1_3_regressions.py`

- [ ] **Step 1: Record the current state**

Run:

```powershell
git status --short
git diff -- poe_subd_six_etf_v1_1_bot.py poe_subd_mixed_pool_v1_3_bot.py tests/test_poe_subd_external_review_regressions.py tests/test_poe_subd_mixed_pool_v1_3_regressions.py
```

Expected: the known calendar-boundary edits and their regression tests are present; unrelated user outputs remain untouched.

- [ ] **Step 2: Create the quant-research backup**

Run:

```powershell
python D:/Codex/home/skills/quant-research/scripts/backup_paths.py --root D:/动量策略/美股A股混合池子动量策略 poe_subd_six_etf_v1_1_bot.py poe_subd_mixed_pool_v1_3_bot.py tests/test_poe_subd_external_review_regressions.py tests/test_poe_subd_mixed_pool_v1_3_regressions.py
```

Expected: the command prints a backup directory containing all four files.

- [ ] **Step 3: Verify the backup and baseline tests**

Run:

```powershell
python -m pytest -q
```

Expected baseline: `210 passed, 1 warning`.

### Task 2: Reject unproven adjusted-price fallbacks

**Files:**
- Modify: `tests/test_poe_subd_external_review_regressions.py:233-255`
- Modify: `tests/test_poe_subd_mixed_pool_v1_3_regressions.py`
- Modify: `poe_subd_six_etf_v1_1_bot.py:373-432`
- Modify: `poe_subd_mixed_pool_v1_3_bot.py:451-510,1354-1386`

- [ ] **Step 1: Change the Tencent fallback regression to require rejection**

Replace the acceptance test with this behavior in the V1.1 regression file, then add the equivalent V1.3 test:

```python
def test_tencent_qfq_loader_rejects_day_key_when_qfqday_missing(monkeypatch):
    module = load_bot_module()

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "code": 0,
                "msg": "",
                "data": {
                    "sh513030": {
                        "day": [["2026-01-02", "1.0", "1.1", "1.2", "0.9", "1000"]]
                    }
                },
            }

    monkeypatch.setattr(module, "_http_get", lambda *args, **kwargs: FakeResponse())

    with pytest.raises(RuntimeError, match="qfqday"):
        module._load_tencent_qfq_one_close("513030.SH", pd.Timestamp("2026-01-02"))
```

- [ ] **Step 2: Add the V1.3 Yahoo adjusted-close regression**

```python
def test_v13_yahoo_history_rejects_missing_adjclose(monkeypatch):
    module = load_bot_module()

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "chart": {
                    "result": [{
                        "timestamp": [1609459200, 1609545600],
                        "indicators": {"quote": [{"close": [100.0, 50.0]}]},
                    }]
                }
            }

    monkeypatch.setattr(module, "_http_get", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(module.time, "sleep", lambda *_: None)

    with pytest.raises(RuntimeError, match="adjusted close"):
        module._fetch_yahoo_adj_close("QQQ", pd.Timestamp("2021-01-01"), pd.Timestamp("2021-01-02"))
```

- [ ] **Step 3: Run RED tests**

Run:

```powershell
python -m pytest -q tests/test_poe_subd_external_review_regressions.py::test_tencent_qfq_loader_rejects_day_key_when_qfqday_missing tests/test_poe_subd_mixed_pool_v1_3_regressions.py::test_tencent_qfq_loader_rejects_day_key_when_qfqday_missing tests/test_poe_subd_mixed_pool_v1_3_regressions.py::test_v13_yahoo_history_rejects_missing_adjclose
```

Expected: all new tests fail because raw fallback is still accepted.

- [ ] **Step 4: Implement the minimal strict loaders**

In both Tencent loaders, replace the `qfqday or day` selection with explicit `qfqday` validation:

```python
node = payload.get("data", {}).get(symbol) or {}
rows = node.get("qfqday") or []
if not rows:
    raise RuntimeError(f"Tencent qfqday missing for {code}; raw day is diagnostic-only")
```

In V1.3 Yahoo history, require one non-empty `adjclose` array and do not read `quote.close`:

```python
adj_nodes = payload.get("indicators", {}).get("adjclose") or []
if not adj_nodes or not adj_nodes[0].get("adjclose"):
    raise RuntimeError(f"Yahoo adjusted close missing for {ticker}; raw close is diagnostic-only")
values = adj_nodes[0]["adjclose"]
```

- [ ] **Step 5: Run GREEN and related provider tests**

Run:

```powershell
python -m pytest -q tests/test_poe_subd_external_review_regressions.py -k "tencent or qfq"
python -m pytest -q tests/test_poe_subd_mixed_pool_v1_3_regressions.py -k "yahoo or qfq"
```

Expected: all selected tests pass.

### Task 3: Fail closed on formal calendar loss and accept source-confirmed holiday boundaries

**Files:**
- Modify: `tests/test_poe_subd_external_review_regressions.py:1101-1125`
- Modify: `tests/test_poe_subd_mixed_pool_v1_3_regressions.py:275-298,381-423`
- Modify: `poe_subd_six_etf_v1_1_bot.py:1595-1622,1644-1693,1732-1815`
- Modify: `poe_subd_mixed_pool_v1_3_bot.py:1587-1592,2204-2231,2253-2301,2341-2430`

- [ ] **Step 1: Add holiday-boundary RED tests**

Add to both regression files:

```python
def test_cnfin_calendar_accepts_weekday_holiday_required_start(monkeypatch, tmp_path):
    module = load_bot_module()
    calendar = pd.DatetimeIndex(pd.to_datetime(["2026-01-05", "2026-01-06"]))
    monkeypatch.setattr(module, "TRADING_CALENDAR_CACHE_PATH", tmp_path / "missing.csv")
    monkeypatch.setattr(module, "_HAS_AKSHARE", False)
    monkeypatch.setattr(module, "_CN_TRADING_DAY_CACHE", None)
    monkeypatch.setattr(module, "_CN_TRADING_DAY_CACHE_COVERAGE_END", None)
    monkeypatch.setattr(
        module,
        "_load_cnfin_trading_calendar",
        lambda start, end: (calendar, pd.Timestamp("2026-01-06"), pd.Timestamp(start), pd.Timestamp(end)),
    )

    sessions = module._expected_cn_trading_days(pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-06"))

    assert sessions.tolist() == [pd.Timestamp("2026-01-05"), pd.Timestamp("2026-01-06")]
```

The extra returned request boundaries are source coverage metadata, not inferred sessions.

- [ ] **Step 2: Change the V1.3 weekday fallback test to fail closed**

```python
def test_v13_load_close_fails_closed_when_cn_calendar_unavailable(monkeypatch):
    module = load_bot_module()
    monkeypatch.setattr(module, "_expected_cn_trading_days", lambda start, end: None)

    with pytest.raises(RuntimeError, match="trading calendar"):
        module.load_close(module._build_config(end_date=pd.Timestamp("2026-01-02")))
```

- [ ] **Step 3: Run RED tests**

Run the three new/changed test node IDs. Expected: holiday tests fail on the existing weekday check, and V1.3 fallback test fails because `pd.bdate_range` is returned.

- [ ] **Step 4: Implement explicit calendar coverage metadata**

Return the queried start/end alongside the CNFin session index. Extend `_calendar_is_usable` with optional `request_start` and `request_end`; accept a session minimum after `required_start` only when the source confirms `request_start <= required_start`, and accept a session maximum before a non-session boundary only when `request_end >= required_end`. Cached/AkShare candidates continue using their own full published coverage metadata.

Remove this V1.3 fallback:

```python
if calendar is None or calendar.empty:
    calendar = pd.bdate_range(config.start_date, config.end_date)
```

Replace it with:

```python
if calendar is None or calendar.empty:
    raise RuntimeError(_calendar_failure_reason() or "formal trading calendar unavailable")
```

- [ ] **Step 5: Run GREEN and complete calendar tests**

Run:

```powershell
python -m pytest -q tests/test_poe_subd_external_review_regressions.py -k calendar
python -m pytest -q tests/test_poe_subd_mixed_pool_v1_3_regressions.py -k calendar
```

Expected: all calendar tests pass and no formal test expects a weekday fallback.

### Task 4: Atomically reject stale-price historical trades

**Files:**
- Modify: `tests/test_poe_subd_external_review_regressions.py`
- Modify: `tests/test_poe_subd_mixed_pool_v1_3_regressions.py`
- Modify: `poe_subd_six_etf_v1_1_bot.py:1335-1535,2543-2559,2590-2636`
- Modify: `poe_subd_mixed_pool_v1_3_bot.py:1941-2144,3248-3277,3307-3362`
- Reference: `run_subd_six_etf_v1_1.py:244-267`

- [ ] **Step 1: Add a shared stale-switch RED pattern to each test module**

Construct `LOOKBACK + 1` rows where asset A leads until the final row and asset B becomes the preferred target while its final price is forward-filled. Call `run_staged_entry(..., price_ffill_flags=flags)` and assert:

```python
last = curve.iloc[-1]
assert bool(last["trade_blocked_by_stale_price"]) is True
assert last["blocked_trade_target"] == target_asset
assert last["position"] == last["position_before"]
assert last["turnover"] == pytest.approx(0.0)
```

Add a staged-entry case asserting `pending_entry_target`, `pending_entry_since`, `pending_entry_days`, and staged counters remain equal to their previous-row values when the fill trade is blocked.

- [ ] **Step 2: Run RED tests**

Expected: `run_staged_entry` rejects the new keyword or completes the stale trade.

- [ ] **Step 3: Port the accepted runner behavior**

Add `price_ffill_flags: pd.DataFrame | None = None` to both Poe `run_staged_entry` functions. Before signal state mutation, snapshot:

```python
old_pending_entry_target = pending_entry_target
old_pending_entry_since = pending_entry_since
old_pending_entry_days = pending_entry_days
old_staged_initial_count = staged_initial_count
old_staged_fill_count = staged_fill_count
```

After selecting `trade_target` but before return/cost calculation, identify stale sell and buy legs from the mask. If any are stale, restore the snapshots, clear `trade_target`, reset `trade_fraction` to `old_fraction`, and emit `trade_blocked_by_stale_price`, `blocked_trade_target`, and `stale_price_trade_assets` columns exactly as the runner does.

- [ ] **Step 4: Thread the mask through the official Poe build path**

Pass the raw-derived mask from `_build_v11_daily` through `build_curves` into `run_staged_entry`. Do not reconstruct it after the curve is built.

- [ ] **Step 5: Run GREEN tests and compare with the runner**

Run the new tests plus:

```powershell
python -m pytest -q tests/test_subd_runner_regressions.py tests/test_poe_subd_external_review_regressions.py -k "stale or forward_fill or held_asset"
python -m pytest -q tests/test_poe_subd_mixed_pool_v1_3_regressions.py -k "stale or forward_fill"
```

Expected: stale trades are atomically cancelled in both Poe scripts and the existing runner behavior remains unchanged.

### Task 5: Downgrade V1.3 proxy surfaces to explicit diagnostic research

**Files:**
- Modify: `tests/test_poe_subd_mixed_pool_v1_3_regressions.py`
- Modify: `poe_subd_mixed_pool_v1_3_bot.py:150-171,4103-4439,5491-5681,5937-6112`

- [ ] **Step 1: Add RED tests for the formal/diagnostic boundary**

```python
def test_v13_performance_refuses_unreconciled_cross_market_proxy(monkeypatch):
    module = load_bot_module()
    bot = module.SubDMixedPoolV13Bot()

    with pytest.raises(module.poe.BotError, match="research-only|timestamp|FX"):
        bot._handle_performance("performance")


def test_v13_signal_report_labels_proxy_result_research_only():
    module = load_bot_module()
    daily = minimal_v13_daily(module)

    report = module.format_signal_report(daily, "unit", live=False)

    assert "research-only" in report.lower()
    assert "not executable" in report.lower()
```

If the test module lacks `minimal_v13_daily`, add a focused helper matching the columns consumed by `format_signal_report`.

- [ ] **Step 2: Run RED tests**

Expected: performance proceeds to data loading and the current report lacks the required research-only banner.

- [ ] **Step 3: Implement one policy constant and centralized guard**

```python
FORMAL_CROSS_MARKET_MODEL_AVAILABLE = False
V13_RESEARCH_ONLY_REASON = (
    "research-only: cross-market bar availability, executable instrument mapping, "
    "next-session fills, and USD/CNY conversion are not reconciled"
)


def _require_formal_cross_market_model() -> None:
    if not FORMAL_CROSS_MARKET_MODEL_AVAILABLE:
        raise poe.BotError(V13_RESEARCH_ONLY_REASON)
```

Call the guard before V1.3 performance data loading. Add the same reason prominently to confirmed/live signal reports and ensure `tradable`/`strategy_actionable_now` remain false for the proxy model.

- [ ] **Step 4: Run GREEN and all V1.3 surface tests**

Run:

```powershell
python -m pytest -q tests/test_poe_subd_mixed_pool_v1_3_regressions.py
```

Expected: the new policy tests and all existing V1.3 tests pass.

### Task 6: Isolate streamed-performance state per request

**Files:**
- Modify: `tests/test_poe_subd_external_review_regressions.py`
- Modify: `tests/test_poe_subd_mixed_pool_v1_3_regressions.py`
- Modify: `poe_subd_six_etf_v1_1_bot.py:2730,5167-5174,5258-5259`
- Modify: `poe_subd_mixed_pool_v1_3_bot.py:3461,5951-5958,6059-6060`

- [ ] **Step 1: Add request-isolation RED tests**

For each module, create two copied contexts and set the rendered marker only in one:

```python
from contextvars import copy_context


def test_performance_rendered_state_is_request_local():
    module = load_bot_module()
    left = copy_context()
    right = copy_context()

    left.run(module._set_performance_response_rendered, True)

    assert left.run(module._performance_response_rendered) is True
    assert right.run(module._performance_response_rendered) is False
```

- [ ] **Step 2: Run RED tests**

Expected: helper functions do not exist or the process-global boolean leaks.

- [ ] **Step 3: Implement ContextVar-backed helpers**

```python
_PERFORMANCE_RESPONSE_RENDERED_VAR: ContextVar[bool] = ContextVar(
    "_PERFORMANCE_RESPONSE_RENDERED", default=False
)


def _set_performance_response_rendered(value: bool) -> None:
    _PERFORMANCE_RESPONSE_RENDERED_VAR.set(bool(value))


def _performance_response_rendered() -> bool:
    return bool(_PERFORMANCE_RESPONSE_RENDERED_VAR.get())
```

At the start of the performance branch, set false and use a token; restore the token in `finally`. Set true immediately before the first performance table write that makes the streamed response non-replaceable. Remove all `global _PERFORMANCE_RESPONSE_RENDERED` usage.

- [ ] **Step 4: Run GREEN and response-handler tests**

Run:

```powershell
python -m pytest -q tests/test_poe_subd_external_review_regressions.py -k performance
python -m pytest -q tests/test_poe_subd_mixed_pool_v1_3_regressions.py -k performance
```

Expected: request-local tests and existing N/A/streaming behavior pass.

### Task 7: Integrated verification and evidence record

**Files:**
- Create: `docs/poe_subd_p1_correctness_repair_20260711.md`
- Verify: both Poe scripts and all tests

- [ ] **Step 1: Run compile, full tests, and diff checks**

Run:

```powershell
python -m py_compile poe_subd_six_etf_v1_1_bot.py poe_subd_mixed_pool_v1_3_bot.py
python -m pytest -q
git diff --check
```

Expected: both scripts compile, all tests pass, and diff check exits 0.

- [ ] **Step 2: Run real-data V1.1 validation**

Build the official confirmed V1.1 daily curve through `_build_v11_daily` for the latest confirmed session. Record source labels, adjustment mode, sample start/end, row count, forward-filled rows, blocked stale trades, and whether any completed trade still has a stale leg.

Acceptance: completed stale-leg trades equal zero.

- [ ] **Step 3: Run real-data V1.3 diagnostic validation**

Build the V1.3 proxy curve only through its diagnostic path. Confirm its user-facing signal contains the research-only reason and its performance handler refuses formal metrics. Do not report CAGR/drawdown as a repaired formal result.

- [ ] **Step 4: Cross-check current A-share source data**

For at least one active ETF, compare recent dates, row count, and prices between the selected formal qfq source and CNFin/raw or another independent source. Record that raw agreement validates recent observations only, not full-history adjustment provenance.

- [ ] **Step 5: Write the verification record**

The record must include:

- backup directory and rollback command;
- files and functions changed;
- every RED command and observed reason;
- every GREEN/full-suite command and result;
- real data sources, adjustment modes, calendars, sample dates, and row counts;
- explicit deferred P2 risks;
- statement that existing user outputs and unrelated dirty files were preserved.

- [ ] **Step 6: Run spec-compliance and code-quality reviews**

Dispatch a fresh reviewer for the approved design requirements, resolve every Critical/Important issue, then dispatch a separate code-quality reviewer. Re-run focused and full tests after any review fix.

