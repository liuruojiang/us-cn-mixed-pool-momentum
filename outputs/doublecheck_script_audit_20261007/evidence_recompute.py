"""Independent read-only check of first audit's preserved evidence.

No official strategy/metric helper or previous math probe is imported.
Real preserved prices are used for the paper ledger; no network or synthetic
performance input is used. All outputs are scoped to this double-check folder.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path, PureWindowsPath

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PREVIOUS = ROOT / "outputs/script_audit_20261007"
CURRENT = PREVIOUS / "current_network"
# Preserve the first audit's repaired version even after the second audit edits
# production. The expected 7a hash below verifies this snapshot explicitly.
SOURCE = ROOT / ".codex_backups/20261007_200248/poe_subd_six_etf_v1_3_bot.py"
BACKUP = ROOT / ".codex_backups/20261007_163920/poe_subd_six_etf_v1_3_bot.py"
EXPECTED_HASH = "7a4cf15ff1603764dbf3469aab9b85f33756c98129116b4ce7dedb46eb48e1e3"
EXPECTED_OLD_HASH = "b49c86944f0ef843f0eb23eebe396122fee0db5a90c6250789f21b3d110df988"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def frame(path):
    df = pd.read_csv(path, parse_dates=["date"])
    assert not df.date.isna().any() and df.date.is_unique
    assert df.date.is_monotonic_increasing
    assert df.date.eq(df.date.dt.normalize()).all()
    return df.set_index("date")


def max_abs(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    assert np.array_equal(np.isnan(a), np.isnan(b))
    return float(np.nanmax(np.abs(a - b)))


def constants(path):
    names = {
        "LOOKBACK", "SCORE_MIN", "SCORE_MAX", "R2_THRESHOLD", "SWITCH_BUFFER",
        "INITIAL_ENTRY_FRACTION", "DEFAULT_MAX_LEV", "ONE_WAY_COST",
        "TARGET_VOL", "TARGET_VOL_ENABLED", "OVERHEAT_ENABLED", "STAGED_ENTRY_ENABLED",
    }
    result = {}
    for node in ast.parse(path.read_text(encoding="utf-8-sig")).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in names:
                    result[target.id] = ast.literal_eval(node.value)
    return result


def xml_summary(path):
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    result = {
        "path": str(path.relative_to(ROOT)), "sha256": sha(path),
        "declared": {key: sum(int(s.attrib.get(key, 0)) for s in suites)
                     for key in ("tests", "errors", "failures", "skipped")},
    }
    cases = root.findall(".//testcase")
    outcomes = Counter()
    by_module = {}
    for case in cases:
        outcome = ("error" if case.find("error") is not None else
                   "failure" if case.find("failure") is not None else
                   "skipped" if case.find("skipped") is not None else "passed")
        outcomes[outcome] += 1
        module = case.attrib["classname"].split(".")[-1]
        by_module.setdefault(module, Counter())[outcome] += 1
    result.update({"actual_case_count": len(cases), "actual_outcomes": dict(outcomes),
                   "by_module": {key: dict(value) for key, value in by_module.items()}})
    assert len(cases) == result["declared"]["tests"]
    for xml_key, case_key in (("errors", "error"), ("failures", "failure"), ("skipped", "skipped")):
        assert result["declared"][xml_key] == outcomes[case_key]
    return result


def test_mapping(before_path, after_path):
    """Map actual testcase names to report issue IDs, including preexisting guards."""
    mapping = {
        "primary_truncated_history": "D01", "incomplete_pagination": "D02",
        "complete_real_history_pagination": "D02_unchanged_guard",
        "primary_invalid_history_structure": "D03", "alignment_rejects_nonempty_invalid": "D04",
        "alignment_rejects_nontrading_row": "D05", "official_2026_calendar_preserves_holiday": "D06",
        "normal_live_cache_rejects_negative_age": "D07", "build_curves_cutoff": "M01",
        "single_day_trade_query": "E01", "no_session_trade_query": "E01",
        "date_range_trade_query": "E01", "requested_no_trade_day": "E01",
        "reporting_apis_reject": "E02", "performance_preparation": "E03",
        "year_month_to_now": "E04", "half_year_decimal": "E05", "older_force_refresh": "E06",
        "critical_execution_and_response_guards": "unchanged_execution_guards",
        "alignment_rejects_whole_market_missing": "unchanged_alignment_guards",
        "alignment_records_single_asset_missing": "unchanged_alignment_guards",
    }
    before = ET.parse(before_path).getroot().findall(".//testcase")
    after = ET.parse(after_path).getroot().findall(".//testcase")
    before = {c.attrib["name"]: c for c in before}
    after = {c.attrib["name"]: c for c in after
             if "test_v13_audit_" in c.attrib.get("classname", "")}
    assert set(before) == set(after) and len(before) == 59
    rows = []
    for name, case in sorted(before.items()):
        matches = [issue for fragment, issue in mapping.items() if fragment in name]
        assert len(matches) == 1, (name, matches)
        post = after[name]
        assert post.find("failure") is None and post.find("error") is None and post.find("skipped") is None
        rows.append({"issue": matches[0], "test": name,
                     "before": "failed" if case.find("failure") is not None else "passed",
                     "after": "passed"})
    pd.DataFrame(rows).to_csv(OUT / "evidence_test_issue_mapping.csv", index=False, encoding="utf-8-sig")
    return {str(issue): {"cases": len(group), "before_failed": int(group.before.eq("failed").sum()),
                        "before_passed": int(group.before.eq("passed").sum()), "after_passed": len(group)}
            for issue, group in pd.DataFrame(rows).groupby("issue")}


def paper_replay(raw, daily):
    """Weighted least-squares via matrix solve; share/cash book independently updates wealth."""
    assets = list(raw.columns)
    aligned = raw.ffill()
    flags = raw.isna() & aligned.notna()
    assert raw.index.equals(daily.index)
    px = aligned.to_numpy(float)
    stored_px = daily[["signal_price_" + code for code in assets]].to_numpy(float)
    assert max_abs(px, stored_px) == 0
    assert np.array_equal(flags.to_numpy(bool), daily[["price_ffill_" + code for code in assets]].to_numpy(bool))
    weights = np.arange(1.0, 26.0)
    x = np.arange(25.0) - 12.0
    design = np.column_stack([np.ones(25), x])
    weighted_design = design * np.sqrt(weights)[:, None]
    scores = np.full(px.shape, np.nan)
    r2 = np.full(px.shape, np.nan)
    for i in range(24, len(px)):
        for j in range(len(assets)):
            prices = px[i - 24:i + 1, j]
            if not np.isfinite(prices).all() or np.any(prices <= 0):
                continue
            log_prices = np.log(prices / prices[0])
            if np.ptp(log_prices) <= 1e-12:
                continue
            coeff, *_ = np.linalg.lstsq(weighted_design, log_prices * np.sqrt(weights), rcond=None)
            residual = log_prices - design @ coeff
            centered = log_prices - np.average(log_prices, weights=weights)
            r2[i, j] = 1.0 - np.dot(weights, residual ** 2) / np.dot(weights, centered ** 2)
            scores[i, j] = np.expm1(coeff[1] * 252)
    # Input score thresholds and full allocation are verified separately against AST constants.
    old_position, cash, units, old_nav = "CASH", 1.0, 0.0, 1.0
    rows = []
    for i, date in enumerate(raw.index):
        eligible = np.isfinite(scores[i]) & (scores[i] > 0.5) & (scores[i] < 5.5) & (r2[i] >= 0.25)
        desired = assets[int(np.argmax(np.where(eligible, scores[i], -np.inf)))] if eligible.any() else "CASH"
        old_j = assets.index(old_position) if old_position != "CASH" else None
        wealth = cash if old_j is None else units * px[i, old_j]
        legs = [asset for asset in (old_position, desired) if asset != "CASH"] if desired != old_position else []
        blocked = bool(any(flags.iloc[i][asset] for asset in legs))
        next_position = old_position if blocked else desired
        turnover = 0.0 if next_position == old_position else float((old_position != "CASH") + (next_position != "CASH"))
        fee = turnover * 0.001
        gross_return = wealth / old_nav - 1.0
        wealth *= 1 - fee
        if next_position != old_position:
            if next_position == "CASH":
                cash, units = wealth, 0.0
            else:
                cash, units = 0.0, wealth / px[i, assets.index(next_position)]
        next_nav = cash if next_position == "CASH" else units * px[i, assets.index(next_position)]
        rows.append({"date": date, "position_before": old_position, "position": next_position,
                     "best_candidate": desired, "trade_blocked_by_stale_price": blocked,
                     "nav": next_nav, "return": next_nav / old_nav - 1.0,
                     "gross_return": gross_return, "turnover": turnover, "cost": fee})
        old_position, old_nav = next_position, next_nav
    replay = pd.DataFrame(rows).set_index("date")
    differences = {}
    for col in ("position_before", "position", "best_candidate", "trade_blocked_by_stale_price"):
        differences[col + "_different_rows"] = int((replay[col] != daily[col]).sum())
        assert differences[col + "_different_rows"] == 0
    for col in ("nav", "return", "gross_return", "turnover", "cost"):
        differences[col + "_max_abs_difference"] = max_abs(replay[col], daily[col])
        np.testing.assert_allclose(replay[col], daily[col], rtol=2e-11, atol=2e-11)
    differences["score_max_abs_difference"] = max_abs(scores, daily[["raw_score_" + code for code in assets]])
    differences["r2_max_abs_difference"] = max_abs(r2, daily[["r2_" + code for code in assets]])
    np.testing.assert_allclose(scores, daily[["raw_score_" + code for code in assets]], rtol=2e-11, atol=2e-11, equal_nan=True)
    np.testing.assert_allclose(r2, daily[["r2_" + code for code in assets]], rtol=2e-11, atol=2e-11, equal_nan=True)
    return replay, differences


def window_recompute(daily, reported, label):
    rows = []
    for _, record in reported.iterrows():
        width = None if record.window == "full_sample" else int(str(record.window)[:-1]) * 252
        sub = daily if width is None else daily.iloc[-width:]
        assert len(sub) == int(record.rows)
        assert str(sub.index[0].date()) == record.start and str(sub.index[-1].date()) == record.end
        # Check NAV-ratio and compounded stored returns independently agree.
        nav = sub.nav.to_numpy(float)
        wealth = nav / nav[0]
        returns = sub["return"].to_numpy(float).copy()
        returns[0] = 0.0
        product = np.cumprod(1 + returns)
        np.testing.assert_allclose(wealth, product, rtol=2e-12, atol=2e-12)
        total = wealth[-1] - 1
        annual = math.expm1(math.log(wealth[-1]) * 252 / (len(sub) - 1))
        maxdd = float(np.min(wealth / np.maximum.accumulate(wealth) - 1))
        row = {"dataset": label, "window": record.window, "rows": len(sub),
               "start": str(sub.index[0].date()), "end": str(sub.index[-1].date()),
               "total": total, "annual": annual, "maxdd": maxdd,
               "total_delta": total - record.total, "annual_delta": annual - record.annual,
               "maxdd_delta": maxdd - record.maxdd,
               "nav_ratio_vs_return_product_max_abs": max_abs(wealth, product)}
        assert max(abs(row[key]) for key in ("total_delta", "annual_delta", "maxdd_delta")) < 2e-12
        rows.append(row)
    return rows


def recent_payload_recompute(raw_current):
    expected = read_json(PREVIOUS / "data_recent_final_comparison.json")["expected_sessions"]
    result = []
    for code in raw_current.columns:
        symbol = ("sz" if code.endswith("SZ") else "sh") + code.split(".")[0]
        tencent_path = PREVIOUS / f"data_recent_tencent_{code}.json"
        tencent = read_json(tencent_path)["data"][symbol]
        key = "qfqday" if "qfqday" in tencent else "day"
        tencent = {row[0][:10]: float(row[2]) for row in tencent[key]}
        sina_path = PREVIOUS / f"data_recent_sina_{code}.json"
        if not sina_path.exists():
            sina_path = PREVIOUS / f"data_recent_sina_{code}_retry25s.json"
        sina = {row["day"][:10]: float(row["close"]) for row in read_json(sina_path)["result"]["data"]}
        assert sorted(tencent) == sorted(sina) == expected
        provider_difference = max(abs(tencent[date] - sina[date]) for date in expected)
        formal_difference = max(abs(tencent[date] - raw_current.loc[date, code]) for date in expected)
        assert provider_difference == formal_difference == 0
        result.append({"code": code, "rows": len(expected), "last": max(expected), "payload_key": key,
                       "tencent_sina_max_abs_difference": provider_difference,
                       "formal_panel_vs_recent_payload_max_abs_difference": formal_difference,
                       "tencent_saved_json_sha256": sha(tencent_path), "sina_saved_json_sha256": sha(sina_path)})
    return result


def main():
    assert sha(SOURCE) == EXPECTED_HASH and sha(BACKUP) == EXPECTED_OLD_HASH
    old_constants, new_constants = constants(BACKUP), constants(SOURCE)
    assert old_constants == new_constants and len(new_constants) == 12
    result = {"scope": "Independent offline recheck of preserved evidence; paper model only",
              "source_path": str(SOURCE.relative_to(ROOT)),
              "source_sha256": sha(SOURCE), "backup_sha256": sha(BACKUP),
              "formal_parameters_unchanged": new_constants}
    network_manifest = read_json(CURRENT / "manifest.json")
    verified_files = {}
    for name, expected_hash in network_manifest["files"].items():
        verified_files[name] = sha(CURRENT / name)
        assert verified_files[name] == expected_hash, name
    result["current_manifest_verified_file_count"] = len(verified_files)
    result["current_manifest_actual_file_hashes"] = verified_files
    replay_manifest = read_json(PREVIOUS / "same_input_replay.json")
    for item in replay_manifest["data"].values():
        # Recorded Windows paths describe provenance; verify this checkout's
        # matching frozen input rather than depending on the original machine.
        local_input = ROOT / "outputs/recert_l1_20260926" / PureWindowsPath(item["path"]).name
        assert sha(local_input) == item["sha256"]
    result["xml"] = {path.stem: xml_summary(path) for path in PREVIOUS.glob("*.xml")}
    result["test_issue_mapping"] = test_mapping(PREVIOUS / "new_regressions_before.xml", PREVIOUS / "full_suite_after.xml")
    current_daily, current_raw = frame(CURRENT / "confirmed_daily.csv.gz"), frame(CURRENT / "raw_prices_qfq.csv.gz")
    sources = pd.read_csv(CURRENT / "sources.csv")
    checks = []
    for _, row in sources.iterrows():
        values = current_raw[row.code].dropna()
        assert len(values) == int(row.rows)
        assert str(values.index[0].date()) == row["first"] and str(values.index[-1].date()) == row["last"]
        assert np.isfinite(values).all() and (values > 0).all()
        checks.append({"code": row.code, "source": row.source, "adjustment": row.adjustment,
                       "rows": len(values), "start": str(values.index[0].date()), "end": str(values.index[-1].date())})
    result["source_table_vs_raw_panel"] = checks
    assert len(current_daily) == network_manifest["rows"] == 3597
    assert str(current_daily.index[-1].date()) == network_manifest["end"] == "2026-09-30"
    current_replay, differences = paper_replay(current_raw, current_daily)
    current_replay.to_csv(OUT / "evidence_independent_current_ledger.csv.gz", index_label="date")
    result["independent_current_ledger_vs_saved_daily"] = differences
    frozen_old, frozen_new = frame(PREVIOUS / "daily_before.csv.gz"), frame(PREVIOUS / "daily_after.csv.gz")
    assert frozen_old.index.equals(frozen_new.index) and len(frozen_new) == 3594
    # Compare every stored field, not only the fields selected in the first audit.
    pd.testing.assert_frame_equal(frozen_old, frozen_new, check_exact=True)
    result["same_input_before_after"] = {"rows": len(frozen_new), "all_columns": len(frozen_new.columns), "exact_equal": True}
    result["latest_vs_frozen_overlap"] = {"rows": len(frozen_new),
        "numeric_nav_max_abs": max_abs(current_daily.loc[frozen_new.index, "nav"], frozen_new.nav),
        "positions_different_rows": int((current_daily.loc[frozen_new.index, "position"] != frozen_new.position).sum())}
    frozen_raw = frame(Path(replay_manifest["data"]["raw"]["path"]))
    _, frozen_differences = paper_replay(frozen_raw, frozen_new)
    result["independent_frozen_ledger_vs_saved_daily"] = frozen_differences
    window_rows = window_recompute(current_daily, pd.read_csv(CURRENT / "window_metrics.csv"), "current_0930")
    window_rows += window_recompute(frozen_new, pd.read_csv(PREVIOUS / "same_input_window_metrics.csv"), "frozen_0924")
    pd.DataFrame(window_rows).to_csv(OUT / "evidence_independent_window_metrics.csv", index=False, encoding="utf-8-sig")
    result["five_window_recomputations"] = window_rows
    result["recent_raw_payload_recomputation"] = recent_payload_recompute(current_raw)
    nav_export = frame(CURRENT / "subd_v13_nav_2011-12-09_2026-09-30.csv")
    assert nav_export.index.equals(current_daily.index)
    result["nav_export_max_abs_difference"] = max_abs(nav_export.nav_norm, current_daily.nav / current_daily.nav.iloc[0])
    result["drawdown_export_max_abs_difference"] = max_abs(nav_export.drawdown, nav_export.nav_norm / nav_export.nav_norm.cummax() - 1)
    assert result["nav_export_max_abs_difference"] < 2e-12 and result["drawdown_export_max_abs_difference"] < 2e-12
    result["status"] = "PASS"
    result["limitations"] = [
        "Rechecks saved received data, not a fresh network pull or independent source for full history",
        "Weighted least-squares and cash/share book validate the retained same-close fee convention only",
        "No point-in-time corporate-action, real fill, broker position, hosted Poe, capacity, T+1 or market-limit certification",
        "XML proves preserved test outcomes; regression bugs and preexisting defense rechecks are counted separately",
    ]
    output = OUT / "evidence_recomputed.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"artifact": str(output), "status": result["status"],
                      "current_ledger": differences,
                      "same_input_before_after": result["same_input_before_after"],
                      "test_issue_mapping": result["test_issue_mapping"],
                      "xml_final": result["xml"]["full_suite_after"],
                      "xml_before": result["xml"]["new_regressions_before"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
