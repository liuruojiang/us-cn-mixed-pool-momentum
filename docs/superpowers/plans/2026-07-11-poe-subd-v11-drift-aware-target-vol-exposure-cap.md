# PoE SubD V1.1 Drift-Aware Target Vol and Exposure Cap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make V1.1 target-vol use a scale=1 drift-aware execution curve and enforce `max_lev` through the model ledger with transaction costs, stale-price blocking, fail-closed accounting, and auditable final-pass-only output.

**Architecture:** Freeze the staged-entry plan and its base execution facts once, then replay it independently for estimator, target-vol intermediate, and final target-vol-plus-overheat passes. Extend the single execution ledger with an optional exposure cap and pass-local audit fields; only the final pass owns official NAV, turnover, cost, pending, stale, and cap audit. Preserve the repository's documented abstract close-boundary timing and simplified cost/exposure convention.

**Tech Stack:** Python 3, pandas, NumPy, pytest, FastAPI Poe reporting code.

---

## File map and constraints

- Modify: `poe_subd_six_etf_v1_1_bot.py`
  - Target-vol validation and scale computation around `_compute_target_vol_scales`.
  - Immutable plan snapshot/replay helpers and `_recompute_final_exposure_nav`.
  - `apply_target_vol_overlay`, `apply_overheat_overlay`, signal extraction, and report wording.
- Modify: `tests/test_poe_subd_external_review_regressions.py`
  - Add focused unit and integration regressions for every invariant below.
- Create: `docs/poe_subd_v11_drift_target_vol_cap_20260711.md`
  - Record verification commands, real-data rebuild outcome, mandatory performance windows or explicit `N/A` reasons.
- Reference only: `docs/superpowers/specs/2026-07-11-poe-subd-v11-drift-aware-target-vol-exposure-cap-design.md`.

The two source/test files were already modified before this batch. Before editing, create a timestamped `.codex_backups/<timestamp>/` copy of both files and record `git diff -- <files>` there. Do not commit mixed pre-existing user changes. Use timestamped backup checkpoints after each green task; commit only new standalone documentation files that can be isolated safely.

### Task 1: Snapshot baseline and lock parameter/scale policy

**Files:**
- Modify: `tests/test_poe_subd_external_review_regressions.py`
- Modify: `poe_subd_six_etf_v1_1_bot.py:2175-2202`

- [ ] **Step 1: Create the pre-edit backup**

Run:

```powershell
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$dir = ".codex_backups/$stamp"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
Copy-Item -LiteralPath 'poe_subd_six_etf_v1_1_bot.py' -Destination $dir
Copy-Item -LiteralPath 'tests/test_poe_subd_external_review_regressions.py' -Destination $dir
git diff -- 'poe_subd_six_etf_v1_1_bot.py' 'tests/test_poe_subd_external_review_regressions.py' | Set-Content -LiteralPath "$dir/preexisting.diff" -Encoding UTF8
```

Expected: backup directory contains both files and `preexisting.diff`; no tracked file changes.

- [ ] **Step 2: Write failing warmup, zero-vol, threshold-initialization, and validation tests**

Add tests with these exact assertions:

```python
@pytest.mark.parametrize(
    ("max_lev", "initial"),
    [(1.2, 1.0), (0.6, 0.6), (0.0, 0.0)],
)
def test_target_vol_warmup_and_first_effective_scale_respect_max_lev(max_lev, initial):
    module = load_bot_module()
    curve = pd.DataFrame({"return": [0.01, -0.01, 0.02]}, index=pd.date_range("2026-01-01", periods=3))
    realized, effective, next_scale = module._compute_target_vol_scales(curve, 0.20, 3, max_lev)
    assert realized.iloc[:2].isna().all()
    assert next_scale.iloc[:2].tolist() == pytest.approx([initial, initial])
    assert effective.iloc[0] == pytest.approx(initial)
    assert (next_scale <= max_lev + module.EXPOSURE_EPS).all()


def test_target_vol_zero_vol_complete_window_maps_to_max_lev():
    module = load_bot_module()
    curve = pd.DataFrame({"return": [0.0, 0.0, 0.0]}, index=pd.date_range("2026-01-01", periods=3))
    realized, _, next_scale = module._compute_target_vol_scales(curve, 0.20, 3, 0.7)
    assert realized.iloc[-1] == pytest.approx(0.0)
    assert next_scale.iloc[-1] == pytest.approx(0.7)


@pytest.mark.parametrize(
    ("target_vol", "vol_window", "max_lev"),
    [(0.0, 20, 1.2), (math.nan, 20, 1.2), (0.2, True, 1.2), (0.2, 1, 1.2), (0.2, 20, -0.1)],
)
def test_target_vol_rejects_invalid_parameters(target_vol, vol_window, max_lev):
    module = load_bot_module()
    curve = pd.DataFrame({"return": [0.0, 0.0]}, index=pd.date_range("2026-01-01", periods=2))
    with pytest.raises(ValueError):
        module._compute_target_vol_scales(curve, target_vol, vol_window, max_lev)
```

Also add a test where the first confirmed threshold value remains `0.6`, proving threshold initialization does not start at `1.0`.

- [ ] **Step 3: Run the new tests and confirm RED**

Run the exact node IDs with:

```powershell
python -m pytest -q tests/test_poe_subd_external_review_regressions.py -k "target_vol_warmup or target_vol_zero_vol or target_vol_rejects_invalid or threshold_initial"
```

Expected: failures show current `fillna(1.0)`/fixed threshold state and missing validation.

- [ ] **Step 4: Implement deterministic scale policy**

Add `EXPOSURE_EPS = 1e-12` near target-vol constants. Change the threshold helper to accept its initial state:

```python
def apply_target_vol_scale_rebalance_threshold(
    raw_next_scale: pd.Series,
    threshold: float = TARGET_VOL_SCALE_REBALANCE_THRESHOLD,
    initial_scale: float = 1.0,
) -> pd.Series:
    raw = raw_next_scale.astype(float)
    confirmed: list[float] = []
    last_confirmed = float(initial_scale)
    for value in raw:
        value = float(value)
        if threshold <= 0 or abs(value - last_confirmed) >= threshold:
            last_confirmed = value
        confirmed.append(last_confirmed)
    return pd.Series(confirmed, index=raw.index, dtype=float)
```

Refactor `_compute_target_vol_scales` so it validates inputs, rejects non-finite input returns, uses `initial_scale = min(1.0, max_lev)`, allows NaN realized vol only during the first `vol_window - 1` rows, maps a complete zero-vol window to `max_lev`, initializes threshold state from `initial_scale`, and uses `shift(1, fill_value=initial_scale)`. Never create an intermediate infinity by dividing rows whose realized vol is zero.

- [ ] **Step 5: Run focused and existing target-vol tests GREEN**

Run:

```powershell
python -m pytest -q tests/test_poe_subd_external_review_regressions.py -k "target_vol or scale_rebalance_threshold"
```

Expected: all selected tests pass.

- [ ] **Step 6: Create a checkpoint backup**

Copy both modified files to a new `.codex_backups/<timestamp>/` directory and run `git diff --check --` on the two files. Expected: exit code 0.

### Task 2: Make ledger drift accounting fail closed

**Files:**
- Modify: `tests/test_poe_subd_external_review_regressions.py`
- Modify: `poe_subd_six_etf_v1_1_bot.py:2205-2449`

- [ ] **Step 1: Write failing drift-domain tests**

Create this minimal one-asset curve fixture and add the tests:

```python
def make_single_asset_ledger_curve(asset_return: float, exposure: float):
    date = pd.Timestamp("2026-01-02")
    gross = exposure * asset_return
    curve = pd.DataFrame(
        {
            "position_before": ["159915.SZ"],
            "position": ["159915.SZ"],
            "fraction_before": [exposure],
            "holding_fraction": [exposure],
            "asset_return": [asset_return],
            "gross_return": [gross],
            "return": [gross],
            "nav": [1.0 + gross],
            "turnover": [0.0],
            "cost": [0.0],
        },
        index=[date],
    )
    return curve, pd.Series(1.0, index=curve.index, dtype=float)


@pytest.mark.parametrize("asset_return", [-1.0, -1.1, math.nan, math.inf])
def test_recompute_nav_fails_closed_on_nonpositive_or_nonfinite_wealth(asset_return):
    module = load_bot_module()
    curve, ones = make_single_asset_ledger_curve(asset_return=asset_return, exposure=1.0)
    with pytest.raises((ValueError, RuntimeError)):
        module._recompute_final_exposure_nav(curve, ones, ones, ones, ones, 0.0)


def test_recompute_nav_uses_exact_drift_formula_for_partial_position():
    module = load_bot_module()
    curve, ones = make_single_asset_ledger_curve(asset_return=0.10, exposure=0.50)
    out = module._recompute_final_exposure_nav(curve, ones, ones, ones, ones, 0.0)
    expected = 0.50 * 1.10 / 1.05
    assert out.iloc[0]["drifted_exposure_before_trade"] == pytest.approx(expected)
```

- [ ] **Step 2: Run tests RED**

Run:

```powershell
python -m pytest -q tests/test_poe_subd_external_review_regressions.py -k "fails_closed_on_nonpositive or exact_drift_formula"
```

Expected: current fallback-to-zero behavior fails the new test.

- [ ] **Step 3: Replace fallback-to-zero with fail-closed checks**

In `_recompute_final_exposure_nav`, validate `one_way_cost` as finite and `0 <= cost < 1`. For non-cash actual positions require finite `asset_ret`; calculate:

```python
gross = asset_ret * exposure_before
wealth_factor = 1.0 + gross
if not math.isfinite(wealth_factor) or wealth_factor <= 0.0:
    raise RuntimeError(f"Non-positive wealth factor at {idx}: {wealth_factor}")
drifted = exposure_before * (1.0 + asset_ret) / wealth_factor
if not math.isfinite(drifted) or drifted < -EXPOSURE_EPS:
    raise RuntimeError(f"Invalid drifted exposure at {idx}: {drifted}")
drifted = max(drifted, 0.0)
```

Cash remains exactly zero and does not require a held-asset return.

- [ ] **Step 4: Run drift tests and prior stale-ledger tests GREEN**

Run:

```powershell
python -m pytest -q tests/test_poe_subd_external_review_regressions.py -k "recompute_nav or stale_trade or stale_target_vol or stale_overheat"
```

Expected: all selected tests pass.

### Task 3: Add pass-local exposure-cap execution and audit

**Files:**
- Modify: `tests/test_poe_subd_external_review_regressions.py`
- Modify: `poe_subd_six_etf_v1_1_bot.py:2205-2449`

- [ ] **Step 1: Write failing fresh-price cap tests**

Add this two-day fixture and tests:

```python
def make_two_day_levered_curve(first_close_exposure: float, second_return: float):
    dates = pd.date_range("2026-01-02", periods=2)
    curve = pd.DataFrame(
        {
            "position_before": ["159915.SZ", "159915.SZ"],
            "position": ["159915.SZ", "159915.SZ"],
            "fraction_before": [1.0, 1.0],
            "holding_fraction": [1.0, 1.0],
            "asset_return": [0.0, second_return],
            "gross_return": [0.0, second_return],
            "return": [0.0, second_return],
            "nav": [1.0, 1.0 + second_return],
            "turnover": [0.0, 0.0],
            "cost": [0.0, 0.0],
        },
        index=dates,
    )
    return curve, pd.Series(first_close_exposure, index=dates, dtype=float)


def test_ledger_rebalances_drifted_exposure_to_cap_and_charges_once():
    module = load_bot_module()
    curve, scale = make_two_day_levered_curve(first_close_exposure=1.2, second_return=0.10)
    ones = pd.Series(1.0, index=curve.index, dtype=float)
    out = module._recompute_final_exposure_nav(
        curve, scale, scale, ones, ones, one_way_cost=0.001, exposure_cap=1.2
    )
    row = out.iloc[-1]
    assert row["cap_triggered_by_drift"]
    assert row["final_capped_target_exposure"] == pytest.approx(1.2)
    assert row["turnover"] == pytest.approx(row["drifted_exposure_before_trade"] - 1.2)
    assert row["cost"] == pytest.approx(row["turnover"] * 0.001)
    assert row["final_exposure_after_overheat"] <= 1.2 + module.EXPOSURE_EPS


def test_ledger_caps_uncapped_overlay_target():
    module = load_bot_module()
    curve, ones = make_single_asset_ledger_curve(asset_return=0.0, exposure=1.0)
    out = module._recompute_final_exposure_nav(
        curve, ones * 1.5, ones * 1.5, ones, ones, 0.0, exposure_cap=1.2
    )
    assert out.iloc[0]["final_uncapped_target_exposure"] == pytest.approx(1.5)
    assert out.iloc[0]["final_capped_target_exposure"] == pytest.approx(1.2)
    assert bool(out.iloc[0]["cap_triggered_by_target"]) is True
```

Add parameter tests rejecting NaN, infinity, and negative cap. Add `exposure_cap=None` coverage asserting no clipping and all cap flags false.

- [ ] **Step 2: Run cap tests RED**

Run:

```powershell
python -m pytest -q tests/test_poe_subd_external_review_regressions.py -k "exposure_to_cap or caps_uncapped or exposure_cap_none or invalid_exposure_cap"
```

Expected: missing `exposure_cap` argument/fields or wrong no-rebalance behavior.

- [ ] **Step 3: Extend the ledger API and decision state**

Add `exposure_cap: float | None = None` to `_recompute_final_exposure_nav`. Validate finite nonnegative caps. For every row compute:

```python
uncapped_target = desired_final * oh_next
capped_target = uncapped_target if exposure_cap is None else min(uncapped_target, exposure_cap)
cap_by_target = exposure_cap is not None and uncapped_target > exposure_cap + EXPOSURE_EPS
cap_by_drift = exposure_cap is not None and drifted > exposure_cap + EXPOSURE_EPS
should_rebalance = existing_rebalance_reason or pending_rebalance or cap_by_drift
```

Use `capped_target` in the same-asset and switch turnover calculations. Record pass-local `final_uncapped_target_exposure`, `final_capped_target_exposure`, `cap_triggered_by_target`, `cap_triggered_by_drift`, `exposure_cap`, `pending_rebalance`, and comma-separated `pending_rebalance_reasons`. When cap is `None`, cap flags are false and the cap column is NaN.

- [ ] **Step 4: Run cap tests GREEN**

Run the Step 2 command. Expected: all selected tests pass.

- [ ] **Step 5: Checkpoint files and diff**

Create another timestamped backup and run `git diff --check --` on the two target files. Expected: exit code 0.

### Task 4: Make stale cap blocking atomic and retry latest targets

**Files:**
- Modify: `tests/test_poe_subd_external_review_regressions.py`
- Modify: `poe_subd_six_etf_v1_1_bot.py:2271-2405`

- [ ] **Step 1: Write failing state-sequence tests**

Build three-to-four-day fixtures and add separate tests for:

- cap sell is stale: actual position carries, `turnover == cost == 0`, `exposure_cap_trade_blocked` is true;
- next fresh day with a lower current target executes the lower current capped target, not the stale-day amount;
- next fresh day after target cancellation performs no obsolete cap order when no current trade is required;
- next fresh day after an asset switch uses the current sell/buy legs atomically;
- an unrelated stale buy whose final target is already below cap sets general stale blocking but not `exposure_cap_trade_blocked`.

The essential assertions are:

```python
assert stale_row["final_exposure_after_overheat"] == pytest.approx(stale_row["drifted_exposure_before_trade"])
assert stale_row["turnover"] == pytest.approx(0.0)
assert stale_row["cost"] == pytest.approx(0.0)
assert bool(stale_row["pending_rebalance"]) is True
assert fresh_row["final_exposure_after_overheat"] == pytest.approx(expected_latest_target)
```

- [ ] **Step 2: Run sequence tests RED**

Run:

```powershell
python -m pytest -q tests/test_poe_subd_external_review_regressions.py -k "stale_cap or latest_cap_target or cap_target_cancel or cap_asset_switch or unrelated_stale"
```

Expected: missing cap-specific pending/causal audit or stale retries use insufficient state.

- [ ] **Step 3: Implement causal blocking without storing quantities**

Keep `pending_rebalance` as a boolean/reason set only. On every row recompute current uncapped/capped targets from current policy state. Set `exposure_cap_trade_blocked` only when cap changed the trade required by this final pass and a stale leg atomically blocked that trade. Never store a target quantity across rows. On stale block preserve carried position/exposure, set turnover/cost to zero, and merge reason labels; on a fresh row clear reasons only after the current desired transaction succeeds or is no longer required.

- [ ] **Step 4: Run sequence and all existing stale tests GREEN**

Run:

```powershell
python -m pytest -q tests/test_poe_subd_external_review_regressions.py -k "stale or pending_rebalance or exposure_cap"
```

Expected: all selected tests pass.

### Task 5: Isolate estimator/intermediate/final passes and costs

**Files:**
- Modify: `tests/test_poe_subd_external_review_regressions.py`
- Modify: `poe_subd_six_etf_v1_1_bot.py:2456-2482, 2871-2897, 2925-2949`

- [ ] **Step 1: Write failing pass-isolation tests**

Add integration tests that monkeypatch or construct deterministic curves to prove:

1. Partial staged exposure drifts in the estimator, and `virtual_base_realized_vol` equals rolling volatility of `unscaled_execution_return`, not the old plan `return`.
2. Estimator uses `exposure_cap=None` even when `max_lev < 1`.
3. A target-vol intermediate stale buy followed by final overheat target zero leaves no intermediate stale/cap block in final output.
4. Base staged-entry stale facts remain in `base_*` and are merged into final output.
5. Target-vol and overheat changing on the same boundary produce exactly one final turnover/cost calculation.

For cost uniqueness assert:

```python
expected_cost = final_row["turnover"] * config.one_way_cost
assert final_row["cost"] == pytest.approx(expected_cost)
assert final_row["return"] == pytest.approx((1.0 + final_row["gross_return"]) * (1.0 - expected_cost) - 1.0)
```

- [ ] **Step 2: Run isolation tests RED**

Run:

```powershell
python -m pytest -q tests/test_poe_subd_external_review_regressions.py -k "unscaled_execution or pass_isolation or intermediate_stale or final_cost_once or base_stale_fact"
```

Expected: old fixed-return estimator and audit OR-merging fail.

- [ ] **Step 3: Add immutable-plan helpers**

Implement helpers with explicit responsibilities:

```python
def _freeze_base_execution_plan(curve: pd.DataFrame) -> pd.DataFrame:
    plan = curve.copy(deep=True)
    plan["base_plan_return"] = pd.to_numeric(plan["return"], errors="raise")
    plan["base_plan_nav"] = pd.to_numeric(plan["nav"], errors="raise")
    plan["base_plan_gross_return"] = pd.to_numeric(plan["gross_return"], errors="raise")
    plan["base_plan_turnover"] = _float_series(plan, "turnover", 0.0)
    plan["base_plan_cost"] = _float_series(plan, "cost", 0.0)
    plan["base_trade_blocked_by_stale_price"] = plan.get("trade_blocked_by_stale_price", False)
    plan["base_stale_price_trade_assets"] = plan.get("stale_price_trade_assets", "")
    return plan


def _fresh_ledger_replay(plan: pd.DataFrame) -> pd.DataFrame:
    replay = plan.copy(deep=True)
    pass_local_columns = {
        "actual_position_before", "actual_position_next",
        "trade_blocked_by_stale_price", "stale_price_trade_assets",
        "target_vol_scale_effective", "target_vol_scale_next",
        "overheat_scale_effective", "overheat_scale_next",
        "exposure_effective", "final_exposure", "final_exposure_after_overheat",
        "drifted_exposure_before_trade", "rebalance_delta", "buy_delta", "sell_delta",
        "final_uncapped_target_exposure", "final_capped_target_exposure",
        "cap_triggered_by_target", "cap_triggered_by_drift",
        "exposure_cap_trade_blocked", "pending_rebalance", "pending_rebalance_reasons",
    }
    replay = replay.drop(columns=[c for c in pass_local_columns if c in replay.columns])
    replay["return"] = replay["base_plan_return"]
    replay["nav"] = replay["base_plan_nav"]
    replay["gross_return"] = replay["base_plan_gross_return"]
    replay["turnover"] = replay["base_plan_turnover"]
    replay["cost"] = replay["base_plan_cost"]
    return replay
```

The ledger must merge only `base_trade_blocked_by_stale_price/base_stale_price_trade_assets` with its current pass-local audit; it must not OR arbitrary incoming final/intermediate fields.

- [ ] **Step 4: Build the drift-aware estimator and target intermediate independently**

In `apply_target_vol_overlay`:

1. freeze the plan once;
2. replay estimator with all-one scales and `exposure_cap=None`;
3. store estimator `return/nav/turnover/cost` under `unscaled_execution_*` columns;
4. compute scales from a DataFrame whose `return` is `unscaled_execution_return`;
5. replay the immutable plan with target-vol scales and `exposure_cap=max_lev`;
6. attach only estimator diagnostic columns and intermediate target fields.

Do not add estimator or intermediate costs to final costs.

- [ ] **Step 5: Replay final pass after overheat state calculation**

Let `apply_overheat_overlay` compute overheat states/scales from the target-vol intermediate state, but before official ledger recomputation call `_fresh_ledger_replay` and copy only policy/state columns required for the final target. Call the ledger once with target-vol scales, final overheat scales, and `exposure_cap=max_lev`. Preserve diagnostic target-vol target columns under their named intermediate columns, but replace intermediate audit with final pass-local audit.

- [ ] **Step 6: Run isolation, target-vol, overheat, and stale suites GREEN**

Run:

```powershell
python -m pytest -q tests/test_poe_subd_external_review_regressions.py -k "target_vol or overheat or stale or pass_isolation or unscaled_execution or final_cost_once"
```

Expected: all selected tests pass.

### Task 6: Surface cap and timing semantics in signal/report output

**Files:**
- Modify: `tests/test_poe_subd_external_review_regressions.py`
- Modify: `poe_subd_six_etf_v1_1_bot.py:3790-4239, 5120-5460`

- [ ] **Step 1: Write failing output tests**

Add tests that assert the live signal dictionary exposes `exposure_cap`, both trigger reasons, cap blocked status, final uncapped/capped target, and pending reasons. Add report tests that require the phrases:

```text
模型边界目标上限
抽象日线收盘边界，不代表已验证的 MOC/next-open 成交
漂移感知基础执行已实现波动率
融资成本未计入
```

When cap reduction is stale-blocked, require wording that actual drifted exposure remains above the cap and the transaction was not recorded.

- [ ] **Step 2: Run output tests RED**

Run:

```powershell
python -m pytest -q tests/test_poe_subd_external_review_regressions.py -k "cap_report or cap_signal or close_boundary_wording or drift_aware_vol_wording"
```

Expected: missing fields/old “虚拟底层” wording.

- [ ] **Step 3: Extend signal extraction and rendering**

Map the new daily columns into the signal dictionary with finite numeric validation. Replace “虚拟底层已实现波动率” with “漂移感知基础执行已实现波动率”. Display `max_lev` as “模型边界目标上限”. Add the abstract close-boundary and simplified cost/exposure caveats near the execution/performance assumptions. Preserve the existing financing-cost exclusion disclosure.

- [ ] **Step 4: Run output and entire regression file GREEN**

Run:

```powershell
python -m pytest -q tests/test_poe_subd_external_review_regressions.py
```

Expected: all tests in the file pass; only known dependency deprecation warnings are acceptable.

### Task 7: Independent adversarial review and final verification

**Files:**
- Modify if defects are found: `poe_subd_six_etf_v1_1_bot.py`
- Modify if defects are found: `tests/test_poe_subd_external_review_regressions.py`
- Create: `docs/poe_subd_v11_drift_target_vol_cap_20260711.md`

- [ ] **Step 1: Dispatch independent reviewers**

Use one agent for design compliance and one for adversarial accounting review. They must independently inspect immutable plan replay, pass-local audit replacement, single cost ownership, scale timing, drift failure closure, cap/stale causality, and output semantics. Reviewers do not edit files.

Expected: findings classified Critical/Important/Minor with file/line evidence.

- [ ] **Step 2: Fix findings with TDD and re-review**

For each accepted finding, first add a failing regression, run it RED, implement the smallest correction, run focused tests GREEN, then return the same increment to both reviewers. Continue until there are no unresolved Critical or Important findings.

- [ ] **Step 3: Run fresh full verification**

Run:

```powershell
python -m py_compile poe_subd_six_etf_v1_1_bot.py poe_subd_mixed_pool_v1_3_bot.py
python -m pytest -q
git diff --check
```

Expected: compile exit 0; full pytest passes; diff check exit 0. Record exact counts and warnings, not estimates.

- [ ] **Step 4: Attempt formal real-data rebuild**

Invoke the official V1.1 build path with current trusted qfq loaders and the same data slices, cost assumptions, and close-boundary timing. Do not substitute CNFin raw prices for formal adjusted history. If successful, record full-sample, 10Y, 5Y, 3Y, and 1Y annualized return plus max drawdown. If unavailable, record each window as `N/A` with the exact provider/data-provenance failure.

- [ ] **Step 5: Write verification record**

Create `docs/poe_subd_v11_drift_target_vol_cap_20260711.md` containing:

- design and implementation scope;
- backup paths;
- tests added and RED/GREEN evidence;
- compile/full-test/diff-check results;
- reviewer verdicts and resolved findings;
- formal data-source result and required performance windows or explicit `N/A` reasons;
- deferred financing and execution-realism limitations.

- [ ] **Step 6: Final workspace audit**

Run `git status --short` and compare target files against the initial backup. Confirm unrelated user files were not touched and no old `outputs/` were presented as rebuilt evidence. Commit only the isolated verification document if safe; leave mixed dirty source/test changes uncommitted for user review.
