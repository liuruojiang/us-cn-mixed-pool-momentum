# Poe SubD V1.1 / V1.3 External Review Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair verified V1.1/V1.3 correctness, disclosure, retry, cache, and defensive-programming defects without changing the accepted strategy, data, cost, or execution assumptions.

**Architecture:** Keep both Poe bots self-contained and apply paired fixes symmetrically where their copied implementations match. Add one focused review-regression test module that imports both bots independently, then use typed errors, request-local diagnostics, narrow cache locks, and generated report text to remove the verified failure modes. Performance work is a separate final task with a predeclared parity and speed gate.

**Tech Stack:** Python 3.14, pandas, NumPy, pytest, fastapi-poe, ContextVar, threading.RLock.

---

### Task 1: Establish focused review regression coverage

**Files:**
- Create: `tests/test_poe_subd_review_20260808.py`
- Reference: `tests/test_poe_subd_external_review_regressions.py`
- Reference: `tests/test_poe_subd_mixed_pool_v1_3_regressions.py`

- [ ] **Step 1: Create independent module loaders and minimal daily-frame helper**

```python
import importlib.util
import math
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
V11_PATH = ROOT / "poe_subd_six_etf_v1_1_bot.py"
V13_PATH = ROOT / "poe_subd_mixed_pool_v1_3_bot.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=[(V11_PATH, "review_v11"), (V13_PATH, "review_v13")])
def bot_module(request):
    path, name = request.param
    return load_module(path, name)


def yearly_daily(module):
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-12-31", "2026-01-02"]),
            "nav": [1.0, 1.1],
            "turnover": [0.0, 0.0],
            "exposure_effective": [1.0, 1.0],
        }
    )
```

- [ ] **Step 2: Add failing tests for findings 1, 2, 3, 15, and 24**

```python
def test_v13_eval_range_label_matches_eval_start():
    module = load_module(V13_PATH, "review_v13_label")
    labels = [item[0] for item in module._default_performance_ranges(pd.Timestamp("2026-08-07"))]
    assert f"from_{module.EVAL_START.year}" in labels
    assert "from_2020" not in labels


def test_v13_short_mandatory_window_reports_insufficient_rows():
    module = load_module(V13_PATH, "review_v13_short_window")
    dates = pd.bdate_range("2026-01-01", periods=100)
    daily = pd.DataFrame({"date": dates})
    start = dict((label, value) for label, value, _ in module._default_performance_ranges_for_daily(
        daily, dates[-1], dates[0]
    ))["1Y"]
    reason = module._mandatory_window_na_reason("1Y", start, dates[0], available_rows=len(dates))
    assert reason == "insufficient history: 100 rows < 252 trading days"


def test_v13_mandatory_windows_keep_252_row_convention():
    module = load_module(V13_PATH, "review_v13_window_convention")
    dates = pd.bdate_range("2015-01-01", periods=3000)
    daily = pd.DataFrame({"date": dates})
    ranges = {label: (start, end) for label, start, end in module._default_performance_ranges_for_daily(
        daily, dates[-1], dates[0]
    )}
    assert dates.get_loc(ranges["1Y"][1]) - dates.get_loc(ranges["1Y"][0]) + 1 == 252
    assert dates.get_loc(ranges["10Y"][1]) - dates.get_loc(ranges["10Y"][0]) + 1 == 2520


def test_yearly_returns_keep_first_session_after_year_boundary(bot_module):
    rows = bot_module.calc_yearly_performance(
        yearly_daily(bot_module), pd.Timestamp("2025-12-31"), pd.Timestamp("2026-01-02")
    )
    assert rows[1]["return"] == pytest.approx(0.10)


def test_standalone_iso_date_is_not_parsed_as_month_range(bot_module):
    start, end = bot_module.parse_date_range("2026-08-05的表现")
    assert start == pd.Timestamp("2026-08-05")
    assert end == pd.Timestamp("2026-08-05")
```

- [ ] **Step 3: Run the five tests and verify RED**

Run: `python -m pytest tests/test_poe_subd_review_20260808.py -k "eval_range or short_mandatory or mandatory_windows or yearly_returns or standalone_iso" -q`

Expected: label, short-history, yearly-return, and standalone-date tests fail for the observed current behavior; the 252-row convention test passes and guards the rejected finding 3.

- [ ] **Step 4: Commit only the RED tests**

```powershell
git add -- tests/test_poe_subd_review_20260808.py
git commit -m "test: reproduce SubD external review defects"
```

### Task 2: Back up the production scripts

**Files:**
- Back up: `poe_subd_six_etf_v1_1_bot.py`
- Back up: `poe_subd_mixed_pool_v1_3_bot.py`

- [ ] **Step 1: Run the required quant-research backup helper**

```powershell
python D:/Codex/home/skills/quant-research/scripts/backup_paths.py --root D:/动量策略/美股A股混合池子动量策略 poe_subd_six_etf_v1_1_bot.py poe_subd_mixed_pool_v1_3_bot.py
```

Expected: the command prints a newly created timestamp-named directory under `.codex_backups` containing both scripts.

- [ ] **Step 2: Verify the backup and record its exact path for the audit record**

Run: `$subdBackupDir = Get-ChildItem -Directory .codex_backups | Sort-Object LastWriteTime -Descending | Select-Object -First 1; Get-ChildItem -Recurse -LiteralPath $subdBackupDir.FullName`

Expected: both bot filenames are present. Do not begin Task 3 until this check passes.

### Task 3: Repair performance windows, annual compounding, and date parsing

**Files:**
- Modify: `poe_subd_mixed_pool_v1_3_bot.py:5590-5697`
- Modify: `poe_subd_mixed_pool_v1_3_bot.py:5400-5540`
- Modify: `poe_subd_six_etf_v1_1_bot.py:4611-4644`
- Modify: `poe_subd_mixed_pool_v1_3_bot.py:5297-5330`
- Modify: `poe_subd_six_etf_v1_1_bot.py:4714-4854`
- Test: `tests/test_poe_subd_review_20260808.py`

- [ ] **Step 1: Generate the evaluation label and count mandatory rows**

In V1.3, add and use:

```python
MANDATORY_WINDOW_TRADING_DAYS = {"10Y": 10 * TRADING_DAYS, "5Y": 5 * TRADING_DAYS,
                                 "3Y": 3 * TRADING_DAYS, "1Y": TRADING_DAYS}


def _eval_start_label() -> str:
    return f"from_{EVAL_START.year}"


def _mandatory_window_na_reason(label, start, earliest, available_rows=None):
    required_rows = MANDATORY_WINDOW_TRADING_DAYS.get(label)
    if required_rows is not None and available_rows is not None and available_rows < required_rows:
        return f"insufficient history: {available_rows} rows < {required_rows} trading days"
    if required_rows is not None and earliest > pd.Timestamp(start).normalize():
        return (
            f"insufficient history: first available {earliest.date().isoformat()} "
            f"after required {pd.Timestamp(start).date().isoformat()}"
        )
    return None
```

Replace both V1.3 `("from_2020", EVAL_START, latest)` tuples with `(_eval_start_label(), EVAL_START, latest)`. In `_handle_performance`, compute `available_rows = int((pd.to_datetime(daily["date"]).dt.normalize() <= latest).sum())` and pass it to `_mandatory_window_na_reason`.

- [ ] **Step 2: Preserve one continuous return series for annual rows**

In both `calc_yearly_performance` functions, compute returns once before grouping:

```python
sub = sub.sort_values("date")
sub["_report_return"] = _daily_returns_for_window(sub).to_numpy(dtype=float)
rows = []
for year, part in sub.groupby(sub["date"].dt.year):
    if part.empty:
        continue
    ret = part["_report_return"].astype(float)
```

Keep the remaining metrics unchanged.

- [ ] **Step 3: Add standalone ISO-date recognition to both parsers**

Immediately after the existing `YYYY-MM-DD至今` branch and before all month-only patterns, add:

```python
match = re.search(r"(?<!\d)(\d{4})[-年/.](\d{1,2})[-月/.](\d{1,2})\s*" + day_suffix, text)
if match:
    day = _checked_timestamp(int(match.group(1)), int(match.group(2)), int(match.group(3)), match.group(0))
    return day, day
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m pytest tests/test_poe_subd_review_20260808.py -k "eval_range or short_mandatory or mandatory_windows or yearly_returns or standalone_iso" -q`

Expected: all selected tests pass.

- [ ] **Step 5: Commit the performance-report fixes**

```powershell
git add -- poe_subd_six_etf_v1_1_bot.py poe_subd_mixed_pool_v1_3_bot.py tests/test_poe_subd_review_20260808.py
git commit -m "fix: correct SubD performance window reporting"
```

### Task 4: Repair generated text and preserve explicit safety boundaries

**Files:**
- Modify: `poe_subd_six_etf_v1_1_bot.py:5630-5800,5900-5938,6015-6030`
- Modify: `poe_subd_mixed_pool_v1_3_bot.py:6364-6500,6646-6684,6765-6785`
- Test: `tests/test_poe_subd_review_20260808.py`

- [ ] **Step 1: Add failing source-text and safety-disclosure tests**

```python
def test_v11_params_describe_cross_validated_raw_fallback(monkeypatch):
    module = load_module(V11_PATH, "review_v11_params")
    writes = []
    class Message:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None
        def write(self, value):
            writes.append(value)
        def overwrite(self, *_):
            return None
    message = Message()
    monkeypatch.setattr(module.poe, "start_message", lambda: message)
    module.SubDSixEtfV11Bot()._handle_params(live=False)
    text = "".join(writes)
    assert "Sina + CNFin交叉验证raw fallback" in text
    assert "SELL腿" in text and "可卖数量" in text


def test_v13_params_and_snapshot_disclose_actual_rules(monkeypatch):
    module = load_module(V13_PATH, "review_v13_params_text")
    assert str(module.LOOKBACK) in module._score_rule_text()
    assert "R²过滤关闭" in module._score_rule_text()
    assert "跨市场" in module._mixed_market_timing_notice(live=False)
    assert "盘前/隔夜" in module._mixed_market_timing_notice(live=True)


def test_introduction_describes_confirmed_cache(bot_module):
    path = V11_PATH if bot_module.VERSION == "1.1" else V13_PATH
    text = path.read_text(encoding="utf-8")
    assert "5分钟缓存" in text
    assert "查询时刷新" not in text
```

- [ ] **Step 2: Run the text tests and verify RED**

Run: `python -m pytest tests/test_poe_subd_review_20260808.py -k "params or introduction" -q`

Expected: helper/text assertions fail because the current text is hard-coded or misleading.

- [ ] **Step 3: Add generated rule and timing helpers**

In V1.3:

```python
def _score_rule_text() -> str:
    r2_rule = "R²过滤关闭" if R2_THRESHOLD is None else f"R²≥{R2_THRESHOLD:.2f}"
    return (
        f"Score 为{LOOKBACK}日加权对数斜率年化动量；只有 "
        f"{SCORE_MIN:g} < Score < {SCORE_MAX:g} 的 ETF 才进入候选池；{r2_rule}。"
    )


def _mixed_market_timing_notice(live: bool) -> str:
    base = "跨市场提示：美国日期T收盘晚于中国日期T收盘，US→CN切换不代表同日收盘可执行；中国长假会压缩累计美国收益到节后首个中国交易日。"
    if live:
        base += " Yahoo 1分钟价在北京时间下午通常属于美股盘前/隔夜，仅作监控估算，不是美国正式收盘价。"
    return base
```

Use `_score_rule_text()` in the snapshot, and show `_mixed_market_timing_notice(live)` in V1.3 parameter/snapshot output.

- [ ] **Step 4: Update both parameter and introduction messages**

Add this parameter row to both bots:

```python
msg.write("| SELL腿执行校验 | **需要已验证可卖数量** | 未接券商可卖数量时，含SELL腿的换仓保持monitor-only，不生成可执行动作 |\n")
```

Change V1.1's source row to include `Sina + CNFin交叉验证raw fallback（仅允许白名单品种）`. Change both introductions to `收盘确认信号（最多复用5分钟缓存；收盘确认前不使用当天盘中bar）`.

- [ ] **Step 5: Run text tests and verify GREEN**

Run: `python -m pytest tests/test_poe_subd_review_20260808.py -k "params or introduction" -q`

Expected: all selected tests pass.

- [ ] **Step 6: Commit disclosure repairs**

```powershell
git add -- poe_subd_six_etf_v1_1_bot.py poe_subd_mixed_pool_v1_3_bot.py tests/test_poe_subd_review_20260808.py
git commit -m "fix: align SubD reports with implemented rules"
```

### Task 5: Harden live-quote and dormant target-vol boundaries

**Files:**
- Modify: `poe_subd_mixed_pool_v1_3_bot.py:637-650,726-744,1273-1281,3017-3044,3993-4009`
- Test: `tests/test_poe_subd_review_20260808.py`

- [ ] **Step 1: Add failing typed-error, non-CN, and target-vol parity tests**

```python
def test_v13_unsupported_live_symbols_use_typed_error():
    module = load_module(V13_PATH, "review_v13_unsupported")
    with pytest.raises(module.UnsupportedLiveQuoteSymbols) as caught:
        module.load_live_quotes(["NOT_SUPPORTED"], now=datetime(2026, 8, 5, 14, 55))
    assert caught.value.codes == ("NOT_SUPPORTED",)
    assert module._is_proxy_live_quote_unsupported_error(caught.value)


def test_v13_non_cn_price_limit_bounds_are_nan():
    module = load_module(V13_PATH, "review_v13_non_cn_bounds")
    lower, upper = module._price_limit_bounds_from_prev_close("QQQ", 100.0)
    assert math.isnan(lower) and math.isnan(upper)


@pytest.mark.parametrize("args", [(True, 20, 1.0), (0.2, True, 1.0), (0.2, 20, True)])
def test_v13_target_vol_helpers_reject_bool_inputs(args):
    module = load_module(V13_PATH, "review_v13_target_vol")
    curve = pd.DataFrame({"return": [0.0] * 30})
    with pytest.raises(ValueError):
        module._compute_target_vol_scales(curve, *args)
```

- [ ] **Step 2: Run selected tests and verify RED**

Run: `python -m pytest tests/test_poe_subd_review_20260808.py -k "unsupported_live or non_cn_price or target_vol_helpers" -q`

Expected: all selected tests fail against current V1.3.

- [ ] **Step 3: Introduce and use a typed unsupported-symbol error**

```python
class UnsupportedLiveQuoteSymbols(IncompleteLiveSnapshot):
    def __init__(self, codes):
        self.codes = tuple(sorted(str(code) for code in codes))
        super().__init__("live quotes unsupported for proxy/non-CN symbols: " + _format_code_list(set(self.codes)))


def _is_proxy_live_quote_unsupported_error(exc: Exception) -> bool:
    return isinstance(exc, UnsupportedLiveQuoteSymbols)
```

Raise `UnsupportedLiveQuoteSymbols(unsupported)` in both `load_live_quotes` and `_load_live_quotes_for_prices`. Update existing V1.3 regression tests that deliberately construct the old text-only exception so they construct the typed exception instead.

- [ ] **Step 4: Guard non-CN price-limit ratios**

```python
ratio_value = _live_price_limit_ratio(code)
if not math.isfinite(ratio_value):
    return math.nan, math.nan
ratio = Decimal(str(ratio_value))
```

- [ ] **Step 5: Copy the validated V1.1 target-vol contract into V1.3**

Add `initial_scale` to `apply_target_vol_scale_rebalance_threshold`; copy V1.1's bool/type/finite validation, zero-vol handling, warmup checks, capped `initial_scale`, and `shift(1, fill_value=initial_scale)` into V1.3 `_compute_target_vol_scales`. Do not change `build_curves`, `TARGET_VOL`, or formal V1.3 scale columns.

- [ ] **Step 6: Run selected tests and existing V1.3 regressions**

Run: `python -m pytest tests/test_poe_subd_review_20260808.py -k "unsupported_live or non_cn_price or target_vol_helpers" -q`

Run: `python -m pytest tests/test_poe_subd_mixed_pool_v1_3_regressions.py -q`

Expected: both commands pass.

- [ ] **Step 7: Commit live-boundary hardening**

```powershell
git add -- poe_subd_mixed_pool_v1_3_bot.py tests/test_poe_subd_review_20260808.py tests/test_poe_subd_mixed_pool_v1_3_regressions.py
git commit -m "fix: harden V1.3 live and target-vol boundaries"
```

### Task 6: Repair historical-loader limits and deterministic retry behavior

**Files:**
- Modify: `poe_subd_six_etf_v1_1_bot.py:411-465,1086-1210`
- Modify: `poe_subd_mixed_pool_v1_3_bot.py:398-534,1366-1490`
- Test: `tests/test_poe_subd_review_20260808.py`

- [ ] **Step 1: Add failing dynamic-start, cap-warning, and short-circuit tests**

```python
def test_v13_qfq_loaders_use_strategy_start(monkeypatch):
    module = load_module(V13_PATH, "review_v13_qfq_start")
    calls = []
    monkeypatch.setattr(module, "_HAS_AKSHARE", True)
    monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    monkeypatch.setattr(module.ak, "fund_etf_hist_em", lambda **kwargs: calls.append(kwargs) or pd.DataFrame())
    with pytest.raises(RuntimeError):
        module._load_akshare_eastmoney_qfq_one_close("159985.SZ", pd.Timestamp("2026-01-02"))
    assert calls[0]["start_date"] == module.START_DATE.strftime("%Y%m%d")


def test_cross_validated_raw_warns_before_sina_cap(monkeypatch):
    module = load_module(V11_PATH, "review_v11_sina_cap")
    index = pd.bdate_range("2019-12-05", periods=module.SINA_DAILY_KLINE_WARN_ROWS)
    series = pd.Series(1.0, index=index, name="159985.SZ")
    monkeypatch.setattr(module, "_load_sina_raw_one_close", lambda *_: series.copy())
    monkeypatch.setattr(module, "_load_cnfin_raw_one_close", lambda *_: series.copy())
    monkeypatch.setattr(module, "_validate_adjusted_close_continuity", lambda *_: None)
    out = module._load_cross_validated_raw_one_close("159985.SZ", index[-1])
    assert "Sina history cap warning" in out.attrs["source_detail"]


def test_tencent_schema_failure_does_not_retry(bot_module, monkeypatch):
    calls = []
    response = SimpleNamespace(raise_for_status=lambda: None,
                               json=lambda: {"data": {bot_module._tencent_fq_symbol("159941.SZ"): {"day": []}}})
    monkeypatch.setattr(bot_module, "_http_get", lambda *args, **kwargs: calls.append(1) or response)
    with pytest.raises(RuntimeError, match="missing qfqday"):
        bot_module._load_tencent_qfq_one_close("159941.SZ", pd.Timestamp("2026-01-02"))
    assert len(calls) == 1
```

- [ ] **Step 2: Run selected tests and verify RED**

Run: `python -m pytest tests/test_poe_subd_review_20260808.py -k "qfq_loaders or sina_cap or schema_failure" -q`

Expected: dynamic-start and cap-warning tests fail; schema failures make three calls instead of one.

- [ ] **Step 3: Use V1.3 START_DATE in both qfq requests**

Replace both V1.3 `"20100101"` literals in the AkShare `start_date` and Eastmoney `beg` parameters with `START_DATE.strftime("%Y%m%d")`.

- [ ] **Step 4: Propagate a pre-cap warning without weakening validation**

Add `SINA_DAILY_KLINE_WARN_ROWS = 1900` to both bots. In `_load_cross_validated_raw_one_close`:

```python
source_detail = SOURCE_DETAIL_SINA_CNFIN_CROSS_VALIDATED
if len(sina) >= SINA_DAILY_KLINE_WARN_ROWS:
    source_detail += f"; Sina history cap warning: {len(sina)}/{SINA_DAILY_KLINE_MAX_ROWS} rows"
close.attrs["source_detail"] = source_detail
```

Keep the listing-date, overlap, price-difference, and continuity checks unchanged.

- [ ] **Step 5: Short-circuit deterministic Tencent schema failures**

```python
class DeterministicProviderSchemaError(RuntimeError):
    pass
```

Raise this type for missing `qfqday` and payload-key changes. Add `except DeterministicProviderSchemaError: raise` before the broad retry exception in both loaders.

- [ ] **Step 6: Run selected and historical-loader regression tests**

Run: `python -m pytest tests/test_poe_subd_review_20260808.py -k "qfq_loaders or sina_cap or schema_failure" -q`

Run: `python -m pytest tests/test_poe_subd_external_review_regressions.py -k "tencent or public_loader" -q`

Expected: both commands pass.

- [ ] **Step 7: Commit loader hardening**

```powershell
git add -- poe_subd_six_etf_v1_1_bot.py poe_subd_mixed_pool_v1_3_bot.py tests/test_poe_subd_review_20260808.py
git commit -m "fix: harden SubD historical fallbacks"
```

### Task 7: Make retry and cache state concurrency-safe

**Files:**
- Modify: `poe_subd_six_etf_v1_1_bot.py:1-15,1900-2333,3331-3383,1005-1083`
- Modify: `poe_subd_mixed_pool_v1_3_bot.py:1-15,2490-2931,4012-4064,1267-1363`
- Modify: `tests/test_poe_subd_external_review_regressions.py:632-642,2128-2154`
- Test: `tests/test_poe_subd_review_20260808.py`

- [ ] **Step 1: Add failing request-local, cache-path, backoff, and Yahoo-reuse tests**

```python
def test_calendar_failure_has_no_process_global_fallback(bot_module):
    bot_module._set_calendar_failure("request-local")
    assert bot_module._calendar_failure_reason() == "request-local"
    assert not hasattr(bot_module, "_CN_TRADING_DAY_FAILURE_REASON")


def test_calendar_cache_path_is_keyed_by_strategy_start(bot_module):
    assert bot_module.START_DATE.strftime("%Y%m%d") in bot_module.TRADING_CALENDAR_CACHE_PATH.name


def test_v13_yahoo_quotes_are_reused_across_eastmoney_attempts(monkeypatch):
    module = load_module(V13_PATH, "review_v13_yahoo_reuse")
    yahoo_calls = []
    monkeypatch.setattr(module, "_load_yahoo_live_quotes", lambda *args, **kwargs: yahoo_calls.append(1) or pd.DataFrame([
        {column: ("QQQ" if column == "code" else 1.0) for column in module.LIVE_QUOTE_COLUMNS}
    ]))
    monkeypatch.setattr(module, "_fetch_eastmoney_live_quotes_from_endpoint",
                        lambda *args, **kwargs: (_ for _ in ()).throw(module.IncompleteLiveSnapshot("bad CN quote")))
    with pytest.raises(RuntimeError):
        module.load_live_quotes(list(module.ASSETS), now=datetime(2026, 8, 5, 14, 55))
    assert len(yahoo_calls) == 1


def test_daily_cache_build_is_single_flight(bot_module, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Lock
    import time

    bot_module._clear_daily_cache()
    calls = []
    calls_lock = Lock()
    fixed_now = bot_module._as_bj_datetime(datetime(2026, 8, 5, 14, 0))
    monkeypatch.setattr(bot_module, "_now_bj", lambda: fixed_now)

    def build(*_):
        with calls_lock:
            calls.append(1)
        time.sleep(0.05)
        return pd.DataFrame({"date": [pd.Timestamp("2026-08-04")]}), "test-source"

    monkeypatch.setattr(bot_module, "_call_build_v11_daily", build)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: bot_module._cached_daily("2026-08-05"), range(2)))
    assert len(calls) == 1
    assert [source for _, source in results] == ["test-source", "test-source"]
```

For retry backoff, patch `time.sleep` and a price-quality validator that always raises; assert sleep is called after the first rejection in both bots.

- [ ] **Step 2: Run selected tests and verify RED**

Run: `python -m pytest tests/test_poe_subd_review_20260808.py -k "calendar_failure or calendar_cache_path or yahoo_quotes or retry_backoff" -q`

Expected: process-global fallback and shared cache-path tests fail; V1.3 fetches Yahoo multiple times; price-quality rejection skips sleep.

- [ ] **Step 3: Use request-local calendar failures only**

Remove `_CN_TRADING_DAY_FAILURE_REASON`. Keep only:

```python
_CN_TRADING_DAY_FAILURE_REASON_VAR = ContextVar("_CN_TRADING_DAY_FAILURE_REASON", default="")

def _set_calendar_failure(reason: str) -> None:
    _CN_TRADING_DAY_FAILURE_REASON_VAR.set(reason)

def _calendar_failure_reason() -> str:
    return _CN_TRADING_DAY_FAILURE_REASON_VAR.get()
```

Update existing tests to assert `_calendar_failure_reason()` rather than the deleted global.

- [ ] **Step 4: Add reentrant cache locks**

Import `RLock` and define separate `_CALENDAR_CACHE_LOCK` and `_DAILY_CACHE_LOCK` per module. Protect the full calendar refresh transaction and `_cached_daily` cache-check/build/store transaction with their locks; protect cache clears with `_DAILY_CACHE_LOCK`. Use `RLock` because tests and refresh helpers can re-enter cache-clearing paths.

- [ ] **Step 5: Separate calendar cache files by required start**

In both bots:

```python
TRADING_CALENDAR_CACHE_PATH = Path(
    f"outputs/cn_trading_days_cache_{START_DATE.strftime('%Y%m%d')}.csv"
)
```

- [ ] **Step 6: Reuse Yahoo and restore backoff**

Fetch `yahoo_frame` once before the V1.3 endpoint loops and append `yahoo_frame.copy()` to each candidate. Before each price/temporal/source-permission `continue`, call `time.sleep(0.5 * attempt)` only when `attempt < 2`. Apply the same conditional sleep to V1.1's corresponding rejection paths.

- [ ] **Step 7: Run concurrency/retry tests and both existing suites**

Run: `python -m pytest tests/test_poe_subd_review_20260808.py -k "calendar_failure or calendar_cache_path or yahoo_quotes or retry_backoff" -q`

Run: `python -m pytest tests/test_poe_subd_external_review_regressions.py tests/test_poe_subd_mixed_pool_v1_3_regressions.py -q`

Expected: all tests pass.

- [ ] **Step 8: Commit cache and retry fixes**

```powershell
git add -- poe_subd_six_etf_v1_1_bot.py poe_subd_mixed_pool_v1_3_bot.py tests/test_poe_subd_review_20260808.py tests/test_poe_subd_external_review_regressions.py
git commit -m "fix: isolate SubD cache and retry state"
```

### Task 8: Repair latest-row, Beijing-date, and repeated date-conversion defects

**Files:**
- Modify: `poe_subd_six_etf_v1_1_bot.py:1435-1475,3242-3249,3829-3865`
- Modify: `poe_subd_mixed_pool_v1_3_bot.py:2030-2070,3909-3916,4515-4550`
- Test: `tests/test_poe_subd_review_20260808.py`

- [ ] **Step 1: Add failing ordering and Beijing-date tests**

```python
def test_execution_legs_uses_latest_date_from_unsorted_input(bot_module, monkeypatch):
    daily = pd.DataFrame([
        {"date": pd.Timestamp("2026-08-05"), "sell_delta": 0.0, "buy_delta": 0.0,
         "actual_position_before": "CASH", "actual_position_next": "CASH"},
        {"date": pd.Timestamp("2026-08-04"), "sell_delta": 0.0, "buy_delta": 1.0,
         "actual_position_before": "CASH", "actual_position_next": bot_module.ASSETS[0]},
    ])
    legs = bot_module._execution_legs_status(daily, datetime(2026, 8, 5, 14, 55), True, True, True)
    assert legs == []


def test_build_config_defaults_to_beijing_date(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, "_bj_today_naive", lambda: pd.Timestamp("2026-08-08"))
    assert bot_module._build_config().end_date == pd.Timestamp("2026-08-08")


def test_live_metadata_parses_daily_dates_once(bot_module, monkeypatch):
    daily = pd.DataFrame({"date": [pd.Timestamp("2026-08-05")]})
    metadata = {
        code: {"quote_date": pd.Timestamp("2026-08-05"), "quote_price": 1.0, "quote_time": "2026-08-05 14:55:00"}
        for code in bot_module.ASSETS[:2]
    }
    original = bot_module.pd.to_datetime
    calls = []
    def counting_to_datetime(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(bot_module.pd, "to_datetime", counting_to_datetime)
    bot_module._attach_live_quote_metadata(daily, metadata)
    assert len(calls) == 1
```

- [ ] **Step 2: Run selected tests and verify RED**

Run: `python -m pytest tests/test_poe_subd_review_20260808.py -k "execution_legs_uses or build_config_defaults or metadata_parses" -q`

Expected: unsorted input uses the wrong row and `_build_config` bypasses the patched Beijing helper.

- [ ] **Step 3: Sort and use Beijing defaults**

Change both functions to:

```python
row = daily.sort_values("date").iloc[-1]
```

and both config defaults to:

```python
end_date = _bj_today_naive() if end_date is None else pd.Timestamp(end_date).normalize()
```

- [ ] **Step 4: Move date parsing outside metadata loops**

In both `_attach_live_quote_metadata` functions, compute `dates = pd.to_datetime(out["date"]).dt.normalize()` once immediately after the empty-input guard, before iterating over `live_quote_metadata.items()`. Preserve all masks and assignments.

- [ ] **Step 5: Run focused and metadata tests**

Run: `python -m pytest tests/test_poe_subd_review_20260808.py -k "execution_legs_uses or build_config_defaults or metadata_parses" -q`

Run: `python -m pytest tests/test_poe_subd_external_review_regressions.py tests/test_poe_subd_mixed_pool_v1_3_regressions.py -k "metadata or execution_legs" -q`

Expected: both commands pass.

- [ ] **Step 6: Commit engineering fixes**

```powershell
git add -- poe_subd_six_etf_v1_1_bot.py poe_subd_mixed_pool_v1_3_bot.py tests/test_poe_subd_review_20260808.py
git commit -m "fix: normalize SubD latest-row and date handling"
```

### Task 9: Benchmark and conditionally promote bias-momentum vectorization

**Files:**
- Modify if gate passes: `poe_subd_six_etf_v1_1_bot.py:2775-2797`
- Modify if gate passes: `poe_subd_mixed_pool_v1_3_bot.py:3335-3357`
- Test: `tests/test_poe_subd_review_20260808.py`
- Reference: `run_subd_six_etf_v1_1.py:837-863`

- [ ] **Step 1: Add parity tests against a retained scalar oracle in the test file**

Copy the current nested-loop algorithm into a test-only `_scalar_bias_momentum(module, close)` oracle. Test monotonic, random seeded, NaN-containing, zero, and short series with:

```python
np.testing.assert_allclose(
    module.calc_bias_momentum(close).to_numpy(),
    _scalar_bias_momentum(module, close).to_numpy(),
    rtol=1e-10,
    atol=1e-10,
    equal_nan=True,
)
```

- [ ] **Step 2: Measure the current implementation**

Use `time.perf_counter()` for five runs over a seeded 5,000-row positive price series and record the median in the audit record. Do not use network data for this pure numerical benchmark.

- [ ] **Step 3: Replace both functions with the existing runner vectorization**

Copy `run_subd_six_etf_v1_1.py`'s `sliding_window_view`, centered-x closed-form slope implementation exactly, changing only the referenced module constants.

- [ ] **Step 4: Run parity tests and benchmark the vectorized implementation**

Run: `python -m pytest tests/test_poe_subd_review_20260808.py -k "bias_momentum" -q`

Expected: exact parity within the declared tolerance.

Promotion gate: keep the vectorized code only if the 5,000-row median is at least 5x faster than the recorded scalar median. Otherwise restore the backed-up scalar functions and document finding 25 as benchmarked but not promoted.

- [ ] **Step 5: Commit only if the promotion gate passes**

```powershell
git add -- poe_subd_six_etf_v1_1_bot.py poe_subd_mixed_pool_v1_3_bot.py tests/test_poe_subd_review_20260808.py
git commit -m "perf: vectorize SubD bias momentum"
```

### Task 10: Record audit disposition and verify the complete change

**Files:**
- Create: `docs/poe_subd_v11_v13_external_review_repair_20260808.md`
- Verify: all modified production and test files

- [ ] **Step 1: Write the 29-item audit record**

The record must include a table with columns `#`, `Disposition`, `Evidence`, and `Notes`. Use `fixed` for implemented findings, `documented` for 7 and 12-14, `rejected` for 3, `deferred` for 22/26/27/29, and the measured promotion result for 25. Record the backup path, baseline `287 passed`, red-test evidence, final verification commands, provider availability, and any formal real-data `N/A` reasons.

- [ ] **Step 2: Run fresh targeted and full test verification**

Run: `python -m pytest tests/test_poe_subd_review_20260808.py -q`

Run: `python -m pytest tests/test_poe_subd_external_review_regressions.py tests/test_poe_subd_mixed_pool_v1_3_regressions.py -q`

Run: `python -m pytest -q`

Expected: all commands exit 0 with no failures.

- [ ] **Step 3: Compile both production scripts**

Run: `python -m py_compile poe_subd_six_etf_v1_1_bot.py poe_subd_mixed_pool_v1_3_bot.py`

Expected: exit 0 and no output.

- [ ] **Step 4: Run the smallest official-path real-data builds**

Invoke each bot's `_call_build_v11_daily` through its normal `confirmed` state with the current Beijing date, without monkey-patching loaders or freshness checks. Record the actual provider/source summary, date range, row count, adjustment mode, and active strategy flags. If qfq providers or the CN calendar are unavailable, record the exact exception and mark mandatory performance windows `N/A`; do not substitute CNFin raw data into a formal qfq result.

- [ ] **Step 5: Review the final diff and user changes**

Run: `git diff --check` and `git status --short`. Confirm no pre-existing output, scan, or unrelated documentation file was staged or edited. Review every production hunk against the design's preserved assumptions.

- [ ] **Step 6: Commit the audit record**

```powershell
git add -- docs/poe_subd_v11_v13_external_review_repair_20260808.md
git commit -m "docs: record SubD external review repairs"
```
