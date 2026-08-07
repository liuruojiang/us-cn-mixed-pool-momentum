# Poe 159985 Cross-Validated Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give both self-contained Poe bots a last-resort `159985.SZ` historical source that uses only the date intersection of independently fetched Sina and CNFin raw closes after all qfq providers fail.

**Architecture:** Add identical direct HTTP loaders and a strict code-specific cross-validator to V1.1 and V1.3. The normal AkShare/Tencent/Eastmoney qfq chain remains first; the raw pair is accepted only for `159985.SZ`, only when both sources cover listing, overlap sufficiently, agree within `0.001`, and pass continuity checks. A new parameterized regression file runs the same contract against both scripts.

**Tech Stack:** Python 3.14, requests, pandas, NumPy, fastapi-poe, pytest, PowerShell, Git.

---

## File Map

- Create: `tests/test_poe_subd_159985_cross_validated_fallback.py` — shared contract tests parameterized over V1.1 and V1.3.
- Modify: `poe_subd_six_etf_v1_1_bot.py` — Poe-native Sina/CNFin loaders, cross-validation, code-specific source approval, provider routing.
- Modify: `poe_subd_mixed_pool_v1_3_bot.py` — the same self-contained implementation for V1.3.
- Modify: `docs/poe_subd_p1_correctness_repair_20260711.md` — record the approved code-specific runtime fallback and real-source evidence.

The two production files already contain uncommitted P1 work. Back them up before editing and do not commit their overlapping changes without explicit user authorization.

### Task 1: Preserve The Dirty Baseline

**Files:**
- Back up: `poe_subd_six_etf_v1_1_bot.py`
- Back up: `poe_subd_mixed_pool_v1_3_bot.py`
- Back up: `tests/test_poe_subd_external_review_regressions.py`
- Back up: `tests/test_poe_subd_mixed_pool_v1_3_regressions.py`
- Back up: `docs/poe_subd_p1_correctness_repair_20260711.md`

- [ ] **Step 1: Record current source and test diffs**

Run:

```powershell
git status --short
git diff --stat -- poe_subd_six_etf_v1_1_bot.py poe_subd_mixed_pool_v1_3_bot.py tests/test_poe_subd_external_review_regressions.py tests/test_poe_subd_mixed_pool_v1_3_regressions.py
```

Expected: pre-existing P1 modifications are visible; no task file is staged.

- [ ] **Step 2: Create a filesystem backup**

Run:

```powershell
python D:\Codex\home\skills\quant-research\scripts\backup_paths.py --root D:\动量策略\美股A股混合池子动量策略 poe_subd_six_etf_v1_1_bot.py poe_subd_mixed_pool_v1_3_bot.py tests\test_poe_subd_external_review_regressions.py tests\test_poe_subd_mixed_pool_v1_3_regressions.py docs\poe_subd_p1_correctness_repair_20260711.md
```

Expected: a new timestamped directory under `.codex_backups` is printed.

- [ ] **Step 3: Verify all backup paths**

Run:

```powershell
$backupDir = (Get-ChildItem -LiteralPath .codex_backups -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
Get-ChildItem -Recurse -File -LiteralPath $backupDir
```

Expected: the two bots, two existing regression files, documentation record, and `manifest.json` are present.

- [ ] **Step 4: Record the existing full-suite baseline**

Run:

```powershell
python -m pytest -q
```

Expected on the current dirty baseline: `278 passed, 14 failed, 1 warning`; all 14 failures are the already identified V1.1 target-vol initial-scale/validation tests in `tests/test_poe_subd_external_review_regressions.py`. Save the exact failing node IDs for final comparison.

### Task 2: Write The Shared Failing Contract Tests

**Files:**
- Create: `tests/test_poe_subd_159985_cross_validated_fallback.py`

- [ ] **Step 1: Add the two-script module fixture and fake response**

Create the file with:

```python
import importlib.util
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
BOT_PATHS = (
    ROOT / "poe_subd_six_etf_v1_1_bot.py",
    ROOT / "poe_subd_mixed_pool_v1_3_bot.py",
)


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


@pytest.fixture(params=BOT_PATHS, ids=("v1_1", "v1_3"))
def module(request):
    path = request.param
    spec = importlib.util.spec_from_file_location(f"{path.stem}_cross_validated_test", path)
    loaded = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(loaded)
    return loaded


def close_series(values, dates, name="159985.SZ"):
    return pd.Series(values, index=pd.to_datetime(dates), name=name, dtype="float64")
```

- [ ] **Step 2: Add direct Sina and CNFin parser tests**

Append:

```python
def test_direct_sina_loader_parses_raw_daily_close_without_akshare(module, monkeypatch):
    payload = {
        "result": {
            "status": {"code": 0},
            "data": [
                {"day": "2019-12-05", "close": "0.986"},
                {"day": "2019-12-06", "close": "0.984"},
            ],
        }
    }
    monkeypatch.setattr(module, "_http_get", lambda *args, **kwargs: FakeResponse(payload))

    close = module._load_sina_raw_one_close("159985.SZ", pd.Timestamp("2019-12-06"))

    assert close.index.tolist() == list(pd.to_datetime(["2019-12-05", "2019-12-06"]))
    assert close.tolist() == pytest.approx([0.986, 0.984])
    assert close.attrs["adjustment"] == module.ADJUSTMENT_CROSS_VALIDATED_RAW


def test_direct_cnfin_loader_parses_raw_daily_close(module, monkeypatch):
    payload = {
        "data": {
            "candle": {
                "fields": ["min_time", "open_px", "high_px", "low_px", "close_px"],
                "159985.SZ": [
                    [20191205, 0.983, 0.995, 0.978, 0.986],
                    [20191206, 0.993, 0.996, 0.982, 0.984],
                ],
            }
        }
    }
    monkeypatch.setattr(module, "_http_get", lambda *args, **kwargs: FakeResponse(payload))

    close = module._load_cnfin_raw_one_close("159985.SZ", pd.Timestamp("2019-12-06"))

    assert close.index.tolist() == list(pd.to_datetime(["2019-12-05", "2019-12-06"]))
    assert close.tolist() == pytest.approx([0.986, 0.984])
    assert close.attrs["adjustment"] == module.ADJUSTMENT_CROSS_VALIDATED_RAW
```

- [ ] **Step 3: Add acceptance and rejection tests for runtime cross-validation**

Append:

```python
def test_cross_validated_raw_uses_only_common_dates(module, monkeypatch):
    dates = pd.bdate_range("2019-12-05", periods=600)
    sina = pd.Series(1.0 + pd.RangeIndex(600) / 10000.0, index=dates, name="159985.SZ")
    cnfin_dates = dates.append(pd.DatetimeIndex([dates[-1] + pd.offsets.BDay(1)]))
    cnfin = pd.Series(
        list(sina.to_numpy() + 0.001) + [float(sina.iloc[-1] + 0.002)],
        index=cnfin_dates,
        name="159985.SZ",
    )
    monkeypatch.setattr(module, "_load_sina_raw_one_close", lambda *args, **kwargs: sina)
    monkeypatch.setattr(module, "_load_cnfin_raw_one_close", lambda *args, **kwargs: cnfin)

    close = module._load_cross_validated_raw_one_close("159985.SZ", cnfin_dates[-1])

    assert close.index.equals(dates)
    assert close.tolist() == pytest.approx(sina.tolist())
    assert close.attrs["source_detail"] == module.SOURCE_DETAIL_SINA_CNFIN_CROSS_VALIDATED


@pytest.mark.parametrize(
    ("code", "first_date", "rows", "difference", "match"),
    [
        ("513030.SH", "2019-12-05", 600, 0.0, "unsupported"),
        ("159985.SZ", "2019-12-06", 600, 0.0, "listing"),
        ("159985.SZ", "2019-12-05", 499, 0.0, "overlap"),
        ("159985.SZ", "2019-12-05", 600, 0.002, "difference"),
    ],
)
def test_cross_validated_raw_rejects_invalid_contract(
    module, monkeypatch, code, first_date, rows, difference, match
):
    dates = pd.bdate_range(first_date, periods=rows)
    sina = pd.Series(1.0 + pd.RangeIndex(rows) / 10000.0, index=dates, name=code)
    cnfin = pd.Series(sina.to_numpy() + difference, index=dates, name=code)
    monkeypatch.setattr(module, "_load_sina_raw_one_close", lambda *args, **kwargs: sina)
    monkeypatch.setattr(module, "_load_cnfin_raw_one_close", lambda *args, **kwargs: cnfin)

    with pytest.raises(RuntimeError, match=match):
        module._load_cross_validated_raw_one_close(code, dates[-1])
```

- [ ] **Step 4: Add provider-order and metadata tests**

Append:

```python
def test_public_loader_uses_cross_validated_raw_only_after_qfq_failures(module, monkeypatch):
    dates = pd.bdate_range("2019-12-05", periods=600)
    fallback = pd.Series(1.0 + pd.RangeIndex(600) / 10000.0, index=dates, name="159985.SZ")
    fallback.attrs["source_detail"] = module.SOURCE_DETAIL_SINA_CNFIN_CROSS_VALIDATED
    calls = []

    def fail(name):
        def loader(*args, **kwargs):
            calls.append(name)
            raise RuntimeError(name)
        return loader

    def cross_loader(*args, **kwargs):
        calls.append("cross")
        return fallback

    monkeypatch.setattr(module, "_load_akshare_eastmoney_qfq_one_close", fail("akshare"))
    monkeypatch.setattr(module, "_load_tencent_qfq_one_close", fail("tencent"))
    monkeypatch.setattr(module, "_load_eastmoney_one_close", fail("eastmoney"))
    monkeypatch.setattr(module, "_load_cross_validated_raw_one_close", cross_loader)

    prices, sources = module._load_public_close_with_per_code_fallback(
        ["159985.SZ"], dates[-1]
    )

    assert calls == ["akshare", "tencent", "eastmoney", "cross"]
    assert prices.columns.tolist() == ["159985.SZ"]
    assert sources.loc[0, "source"] == module.SOURCE_SINA_CNFIN_CROSS_VALIDATED
    assert sources.loc[0, "adjustment"] == module.ADJUSTMENT_CROSS_VALIDATED_RAW
    assert sources.loc[0, "source_detail"] == module.SOURCE_DETAIL_SINA_CNFIN_CROSS_VALIDATED


def test_public_loader_never_tries_raw_pair_for_other_codes(module, monkeypatch):
    calls = []
    monkeypatch.setattr(
        module,
        "_load_akshare_eastmoney_qfq_one_close",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("akshare")),
    )
    monkeypatch.setattr(
        module,
        "_load_tencent_qfq_one_close",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("tencent")),
    )
    monkeypatch.setattr(
        module,
        "_load_eastmoney_one_close",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("eastmoney")),
    )
    monkeypatch.setattr(
        module,
        "_load_cross_validated_raw_one_close",
        lambda *args, **kwargs: calls.append("cross"),
    )

    with pytest.raises(RuntimeError, match="All historical data sources failed"):
        module._load_public_close_with_per_code_fallback(["513030.SH"], pd.Timestamp("2026-08-07"))

    assert calls == []
```

- [ ] **Step 5: Run the new file and verify RED**

Run:

```powershell
python -m pytest -q tests/test_poe_subd_159985_cross_validated_fallback.py
```

Expected: tests fail because `ADJUSTMENT_CROSS_VALIDATED_RAW`, the direct loaders, cross-validator, and provider route do not exist. Fix any collection or fixture error before proceeding.

### Task 3: Implement The Identical Poe-Native Source Contract

**Files:**
- Modify: `poe_subd_six_etf_v1_1_bot.py:160-300, 1055-1095`
- Modify: `poe_subd_mixed_pool_v1_3_bot.py:190-375, 1344-1385`
- Test: `tests/test_poe_subd_159985_cross_validated_fallback.py`

- [ ] **Step 1: Add the code-specific constants to both scripts**

Add the following block after the existing adjustment/source constants in both files:

```python
ADJUSTMENT_CROSS_VALIDATED_RAW = "raw/unadjusted cross-validated"
SOURCE_SINA_CNFIN_CROSS_VALIDATED = "Sina direct + CNFin quote kline"
SOURCE_DETAIL_SINA_CNFIN_CROSS_VALIDATED = (
    "159985.SZ exact-date intersection; listing coverage from 2019-12-05; "
    "min_rows=500; min_shorter_overlap=99%; max_abs_close_diff=0.001"
)
CROSS_VALIDATED_RAW_CODES = {"159985.SZ": pd.Timestamp("2019-12-05")}
SINA_DAILY_KLINE_MAX_ROWS = 1970
CROSS_VALIDATED_RAW_MIN_ROWS = 500
CROSS_VALIDATED_RAW_MIN_SHORTER_OVERLAP = 0.99
CROSS_VALIDATED_RAW_MAX_ABS_CLOSE_DIFF = 0.001
CNFIN_KLINE_PAGE_SIZE = 2001
```

- [ ] **Step 2: Add `_sina_symbol()` to V1.1 and retain V1.3's existing helper**

Add to V1.1 after `_tencent_fq_symbol()`:

```python
def _sina_symbol(code: str) -> str:
    ticker, suffix = code.split(".")
    if suffix == "SZ":
        return f"sz{ticker}"
    if suffix == "SH":
        return f"sh{ticker}"
    raise ValueError(f"Unsupported suffix: {code}")
```

Do not duplicate this function in V1.3 because it already exists.

- [ ] **Step 3: Add the direct Sina loader to both scripts**

Insert this identical function before `_load_public_close_with_per_code_fallback()` in both files:

```python
def _load_sina_raw_one_close(code: str, end_date: pd.Timestamp) -> pd.Series:
    url = "https://quotes.sina.cn/cn/api/openapi.php/CN_MarketDataService.getKLineData"
    params = {
        "symbol": _sina_symbol(code),
        "scale": "240",
        "ma": "no",
        "datalen": str(SINA_DAILY_KLINE_MAX_ROWS),
    }
    last_error = None
    rows = None
    for attempt in range(1, 4):
        try:
            resp = _http_get(url, params=params, timeout=30, headers=HTTP_HEADERS)
            resp.raise_for_status()
            payload = resp.json()
            rows = ((payload.get("result") or {}).get("data") or [])
            if rows:
                break
        except Exception as exc:
            last_error = exc
        time.sleep(0.5 * attempt)
    if not rows:
        raise RuntimeError(f"Sina direct kline returned no data for {code}; last_error={last_error}")
    frame = pd.DataFrame(rows)
    if "day" not in frame.columns or "close" not in frame.columns:
        raise RuntimeError(f"Sina direct kline missing day/close for {code}")
    close = pd.Series(
        pd.to_numeric(frame["close"], errors="coerce").to_numpy(),
        index=pd.to_datetime(frame["day"], errors="coerce"),
        name=code,
        dtype="float64",
    ).dropna().sort_index()
    close = close[~close.index.duplicated(keep="last")].loc[:pd.Timestamp(end_date).normalize()]
    if close.empty or not np.isfinite(close.to_numpy()).all() or not (close > 0).all():
        raise RuntimeError(f"Sina direct kline normalized to invalid close series for {code}")
    close.attrs["adjustment"] = ADJUSTMENT_CROSS_VALIDATED_RAW
    return close
```

- [ ] **Step 4: Add the paginated CNFin loader to both scripts**

Insert this identical function after the Sina loader in both files:

```python
def _load_cnfin_raw_one_close(code: str, end_date: pd.Timestamp) -> pd.Series:
    if code not in CROSS_VALIDATED_RAW_CODES:
        raise RuntimeError(f"CNFin raw fallback unsupported for {code}")
    url = "https://quotedata.cnfin.com/quote/v1/kline"
    required_start = CROSS_VALIDATED_RAW_CODES[code]
    current_end = pd.Timestamp(end_date).normalize()
    rows: list[list[object]] = []
    fields: list[str] = []
    last_error = None
    for _page in range(10):
        page_rows = None
        params = {
            "prod_code": code,
            "candle_period": "6",
            "get_type": "range",
            "start_date": required_start.strftime("%Y%m%d"),
            "end_date": current_end.strftime("%Y%m%d"),
            "fields": "open_px,high_px,low_px,close_px,business_amount,business_balance",
        }
        for attempt in range(1, 4):
            try:
                resp = _http_get(url, params=params, timeout=30, headers=HTTP_HEADERS)
                resp.raise_for_status()
                candle = ((resp.json().get("data") or {}).get("candle") or {})
                fields = list(candle.get("fields") or [])
                page_rows = candle.get(code) or []
                if page_rows:
                    break
            except Exception as exc:
                last_error = exc
            time.sleep(0.5 * attempt)
        if not page_rows:
            if not rows:
                raise RuntimeError(f"CNFin raw kline returned no data for {code}; last_error={last_error}")
            break
        rows = page_rows + rows
        first_date = pd.Timestamp(str(page_rows[0][0])).normalize()
        if len(page_rows) < CNFIN_KLINE_PAGE_SIZE or first_date <= required_start:
            break
        next_end = first_date - pd.Timedelta(days=1)
        if next_end >= current_end or next_end < required_start:
            raise RuntimeError(f"CNFin raw kline pagination stalled for {code}")
        current_end = next_end
    if "min_time" not in fields or "close_px" not in fields:
        raise RuntimeError(f"CNFin raw kline missing min_time/close_px for {code}")
    frame = pd.DataFrame(rows, columns=fields)
    close = pd.Series(
        pd.to_numeric(frame["close_px"], errors="coerce").to_numpy(),
        index=pd.to_datetime(frame["min_time"].astype(str), errors="coerce"),
        name=code,
        dtype="float64",
    ).dropna().sort_index()
    close = close[~close.index.duplicated(keep="last")]
    close = close.loc[required_start:pd.Timestamp(end_date).normalize()]
    if close.empty or not np.isfinite(close.to_numpy()).all() or not (close > 0).all():
        raise RuntimeError(f"CNFin raw kline normalized to invalid close series for {code}")
    close.attrs["adjustment"] = ADJUSTMENT_CROSS_VALIDATED_RAW
    return close
```

- [ ] **Step 5: Add the strict cross-validator to both scripts**

Insert this identical function after the two direct loaders:

```python
def _load_cross_validated_raw_one_close(code: str, end_date: pd.Timestamp) -> pd.Series:
    listing_date = CROSS_VALIDATED_RAW_CODES.get(code)
    if listing_date is None:
        raise RuntimeError(f"cross-validated raw fallback unsupported for {code}")
    sina = _load_sina_raw_one_close(code, end_date)
    cnfin = _load_cnfin_raw_one_close(code, end_date)
    if sina.index.min() != listing_date or cnfin.index.min() != listing_date:
        raise RuntimeError(f"cross-validated raw listing coverage missing for {code}")
    common_index = sina.index.intersection(cnfin.index).sort_values()
    shorter_rows = min(len(sina), len(cnfin))
    if len(common_index) < CROSS_VALIDATED_RAW_MIN_ROWS:
        raise RuntimeError(f"cross-validated raw overlap rows insufficient for {code}")
    if len(common_index) / shorter_rows < CROSS_VALIDATED_RAW_MIN_SHORTER_OVERLAP:
        raise RuntimeError(f"cross-validated raw overlap ratio insufficient for {code}")
    sina_common = sina.reindex(common_index)
    cnfin_common = cnfin.reindex(common_index)
    max_diff = float((sina_common - cnfin_common).abs().max())
    if max_diff > CROSS_VALIDATED_RAW_MAX_ABS_CLOSE_DIFF + 1e-12:
        raise RuntimeError(
            f"cross-validated raw close difference too large for {code}: {max_diff:.6f}"
        )
    close = sina_common.copy()
    _validate_adjusted_close_continuity(code, close, SOURCE_SINA_CNFIN_CROSS_VALIDATED)
    close.attrs["adjustment"] = ADJUSTMENT_CROSS_VALIDATED_RAW
    close.attrs["source_detail"] = SOURCE_DETAIL_SINA_CNFIN_CROSS_VALIDATED
    return close
```

- [ ] **Step 6: Make source validation code-specific in both scripts**

Replace `_validate_qfq_sources()` with this behavior in both files:

```python
def _is_approved_cross_validated_raw_source(row: object) -> bool:
    return (
        str(getattr(row, "code", "") or "").strip() == "159985.SZ"
        and str(getattr(row, "source", "") or "").strip() == SOURCE_SINA_CNFIN_CROSS_VALIDATED
        and str(getattr(row, "adjustment", "") or "").strip().lower()
        == ADJUSTMENT_CROSS_VALIDATED_RAW
        and str(getattr(row, "source_detail", "") or "").strip()
        == SOURCE_DETAIL_SINA_CNFIN_CROSS_VALIDATED
    )


def _validate_qfq_sources(sources: pd.DataFrame) -> None:
    if sources.empty or "adjustment" not in sources.columns:
        raise RuntimeError("No historical source metadata was returned")
    rejected: list[str] = []
    for row in sources.itertuples(index=False):
        if _is_approved_cross_validated_raw_source(row):
            continue
        code = str(getattr(row, "code", "") or "").strip()
        source = str(getattr(row, "source", "") or "").strip()
        adjustment = str(getattr(row, "adjustment", "") or "").strip().lower()
        detail = str(getattr(row, "source_detail", "") or "").strip()
        if adjustment not in QFQ_ADJUSTMENT_ALLOWLIST:
            rejected.append(f"{code}:{source}[{adjustment}]")
        elif (source, detail) not in APPROVED_QFQ_HISTORICAL_SOURCES:
            rejected.append(f"{code}:{source}[{detail}]")
    if rejected:
        raise RuntimeError("Unapproved historical source rejected: " + ", ".join(rejected[:6]))
```

- [ ] **Step 7: Append the fourth provider only for `159985.SZ`**

In both `_load_public_close_with_per_code_fallback()` implementations, build a mutable provider list per code:

```python
providers = [
    (
        "akshare.fund_etf_hist_em daily close",
        ADJUSTMENT_QFQ,
        SOURCE_DETAIL_AKSHARE_QFQ,
        _load_akshare_eastmoney_qfq_one_close,
    ),
    ("Tencent fqkline", ADJUSTMENT_QFQ, SOURCE_DETAIL_TENCENT_QFQ, _load_tencent_qfq_one_close),
    (
        "Eastmoney push2his kline",
        ADJUSTMENT_QFQ,
        SOURCE_DETAIL_EASTMONEY_FQT1,
        _load_eastmoney_one_close,
    ),
]
if code in CROSS_VALIDATED_RAW_CODES:
    providers.append(
        (
            SOURCE_SINA_CNFIN_CROSS_VALIDATED,
            ADJUSTMENT_CROSS_VALIDATED_RAW,
            SOURCE_DETAIL_SINA_CNFIN_CROSS_VALIDATED,
            _load_cross_validated_raw_one_close,
        )
    )
for source_name, adjustment, source_detail, loader in providers:
    try:
        close = loader(code, end_date)
        source_detail = str(close.attrs.get("source_detail") or source_detail)
        series.append(close)
        sources.append(_source_record(code, source_name, adjustment, close, source_detail))
        break
    except Exception as exc:
        errors.append(f"{code} {source_name}: {str(exc)[:160]}")
else:
    raise RuntimeError("All historical data sources failed. " + " | ".join(errors[-8:]))
```

Keep the existing `close.attrs["source_detail"]` override as shown.

- [ ] **Step 8: Run the new shared contract file and verify GREEN**

Run:

```powershell
python -m pytest -q tests/test_poe_subd_159985_cross_validated_fallback.py
```

Expected: all parameterized V1.1/V1.3 tests pass.

### Task 4: Run Existing Regression Suites And Repair Only Contract Regressions

**Files:**
- Verify: `tests/test_poe_subd_external_review_regressions.py`
- Verify: `tests/test_poe_subd_mixed_pool_v1_3_regressions.py`
- Verify: `tests/test_poe_subd_live_signal_freshness.py`
- Verify: `tests/test_poe_subd_trade_records.py`

- [ ] **Step 1: Run V1.3 existing tests**

Run:

```powershell
python -m pytest -q tests/test_poe_subd_mixed_pool_v1_3_regressions.py
```

Expected: the existing 47 V1.3 tests pass.

- [ ] **Step 2: Run V1.1 display/data tests while excluding known target-vol baseline failures**

Run:

```powershell
python -m pytest -q tests/test_poe_subd_external_review_regressions.py tests/test_poe_subd_live_signal_freshness.py tests/test_poe_subd_trade_records.py -k "not target_vol_warmup_uses_capped_initial_scale and not target_vol_rejects_invalid_parameters and not target_vol_rejects_nonfinite_returns and not target_vol_scale_threshold_starts_from_explicit_initial_scale"
```

Expected: all selected tests pass; only the 14 known target-vol node IDs are deselected.

- [ ] **Step 3: Inspect failures before any adjustment**

If a newly failing existing test concerns exact old error text (`All qfq data sources failed`) or rejects the new exact code-specific metadata, update only that assertion after confirming the behavior still fails closed for other raw sources. Do not modify target-vol logic or unrelated strategy behavior.

### Task 5: Validate Both Current Public Sources With Real Data

**Files:**
- Execute: `poe_subd_six_etf_v1_1_bot.py`
- Execute: `poe_subd_mixed_pool_v1_3_bot.py`

- [ ] **Step 1: Run both real cross-validated loaders**

Use an inline Python probe that imports each script and calls:

```python
close = module._load_cross_validated_raw_one_close(
    "159985.SZ", pd.Timestamp("2026-08-07")
)
```

Print module filename, row count, first date, last common date, last close, `adjustment`, and `source_detail`.

Expected from the 2026-08-07 observation: 1,617 common rows, first date `2019-12-05`, last common date `2026-08-06`, last close `2.119`, and exact cross-validated metadata. If current remote data has advanced, record the observed new common end date instead of forcing the old value.

- [ ] **Step 2: Independently report source agreement**

In the same probe, load Sina and CNFin separately and print:

```python
common = sina.index.intersection(cnfin.index)
max_diff = float((sina.reindex(common) - cnfin.reindex(common)).abs().max())
overlap_ratio = len(common) / min(len(sina), len(cnfin))
```

Expected: `max_diff <= 0.001000000001`, overlap ratio at least `0.99`, and both start on `2019-12-05`.

- [ ] **Step 3: Exercise the real provider chain with qfq providers forced unavailable**

In an inline diagnostic only, monkeypatch the three qfq loader functions in each imported module to raise and call `_load_public_close_with_per_code_fallback(["159985.SZ"], end_date)`.

Expected: the real Sina/CNFin pair supplies the output, and source metadata uses the exact cross-validated raw label. Clearly label this a diagnostic forced-fallback run; do not report strategy performance metrics from it.

### Task 6: Document The Accepted Runtime Fallback

**Files:**
- Modify: `docs/poe_subd_p1_correctness_repair_20260711.md`

- [ ] **Step 1: Append a dated source-availability note**

Append a section that records:

```markdown
## 2026-08-07 159985.SZ Cross-Validated Poe Fallback

V1.1 and V1.3 now retain the original qfq provider order and add one code-specific last resort for `159985.SZ`: the exact-date intersection of direct Sina raw daily closes and CNFin raw daily closes. The fallback requires both sources, listing coverage from 2019-12-05, at least 500 common rows, at least 99% coverage of the shorter series, maximum absolute close difference of 0.001, and the existing continuity guard.

The source is labelled `raw/unadjusted cross-validated`, never qfq. It is not available to any other instrument and fails closed if either provider fails or the two series disagree.
```

Add the actual real-probe row count, range, last common close, and maximum difference underneath after Task 5.

- [ ] **Step 2: Verify the record**

Run:

```powershell
rg -n "159985.SZ Cross-Validated Poe Fallback|raw/unadjusted cross-validated|maximum absolute close difference" docs/poe_subd_p1_correctness_repair_20260711.md
```

Expected: all three phrases occur in the new final section.

### Task 7: Final Verification And Handoff

**Files:**
- Verify: `poe_subd_six_etf_v1_1_bot.py`
- Verify: `poe_subd_mixed_pool_v1_3_bot.py`
- Verify: `tests/test_poe_subd_159985_cross_validated_fallback.py`
- Verify: all tests

- [ ] **Step 1: Compile both Poe scripts**

Run:

```powershell
python -m py_compile poe_subd_six_etf_v1_1_bot.py poe_subd_mixed_pool_v1_3_bot.py
```

Expected: exit code 0 and no output.

- [ ] **Step 2: Run the new and focused suites together**

Run:

```powershell
python -m pytest -q tests/test_poe_subd_159985_cross_validated_fallback.py tests/test_poe_subd_mixed_pool_v1_3_regressions.py
python -m pytest -q tests/test_poe_subd_external_review_regressions.py tests/test_poe_subd_live_signal_freshness.py tests/test_poe_subd_trade_records.py -k "not target_vol_warmup_uses_capped_initial_scale and not target_vol_rejects_invalid_parameters and not target_vol_rejects_nonfinite_returns and not target_vol_scale_threshold_starts_from_explicit_initial_scale"
```

Expected: both commands pass with only the existing fastapi-poe Pydantic warning.

- [ ] **Step 3: Run the full suite and compare against baseline**

Run:

```powershell
python -m pytest -q
```

Expected: no new failing node IDs. The same 14 pre-existing V1.1 target-vol failures may remain; the passed count increases by the number of new parameterized tests. Do not claim the full suite is green while those baseline failures exist.

- [ ] **Step 4: Check diff hygiene and task-only delta**

Run:

```powershell
git diff --check
git status --short
$backupDir = (Get-ChildItem -LiteralPath .codex_backups -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
git diff --no-index -- (Join-Path $backupDir 'poe_subd_six_etf_v1_1_bot.py') poe_subd_six_etf_v1_1_bot.py
git diff --no-index -- (Join-Path $backupDir 'poe_subd_mixed_pool_v1_3_bot.py') poe_subd_mixed_pool_v1_3_bot.py
```

Expected: the backup comparisons show only the cross-validated fallback changes for this task; `git diff --check` exits 0 apart from possible LF/CRLF warnings.

- [ ] **Step 5: Report rollback and deployment**

Report the backup directory, exact focused/full test results, real source rows/range/difference, and the unchanged 14-failure baseline. State that both updated self-contained scripts must be redeployed to Poe and that no implementation files were committed because they overlap pre-existing user/P1 changes.
