"""Verify final evidence and combine only additional, already executed test cases."""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
ENTRY = ROOT / "poe_subd_six_etf_v1_3_bot.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def case_key(case):
    return case.get("classname"), case.get("name")


def main():
    code_sha = sha(ENTRY)
    ast.parse(ENTRY.read_text(encoding="utf-8"))
    before = ROOT / ".codex_backups/20261007_200248/poe_subd_six_etf_v1_3_bot.py"
    assert sha(before) == "7a4cf15ff1603764dbf3469aab9b85f33756c98129116b4ce7dedb46eb48e1e3"
    full_path = OUT / "full_suite_after.xml"
    data_path = OUT / "data_second_audit_lazy_after.xml"
    full_cases = ET.parse(full_path).getroot().findall(".//testcase")
    data_cases = ET.parse(data_path).getroot().findall(".//testcase")
    full_keys = {case_key(case) for case in full_cases}
    extras = [case for case in data_cases if case_key(case) not in full_keys]
    assert len(full_cases) == 686 and len(data_cases) == 27 and len(extras) == 5
    for case in extras:
        assert all(case.find(tag) is None for tag in ("failure", "error", "skipped"))
    combined = full_cases + extras
    assert len({case_key(case) for case in combined}) == len(combined)
    summary = {"tests": len(combined), "failures": 0, "errors": 0, "skipped": 0, "passed": 0}
    suite = ET.Element("testsuite", name="doublecheck_combined_executed_evidence")
    for case in combined:
        suite.append(copy.deepcopy(case))
        if case.find("failure") is not None:
            summary["failures"] += 1
        elif case.find("error") is not None:
            summary["errors"] += 1
        elif case.find("skipped") is not None:
            summary["skipped"] += 1
        else:
            summary["passed"] += 1
    assert summary == {"tests": 691, "failures": 0, "errors": 0, "skipped": 1, "passed": 690}
    for name in ("tests", "failures", "errors", "skipped"):
        suite.set(name, str(summary[name]))
    properties = ET.SubElement(suite, "properties")
    for name, value in {"basis": "685-pass full run plus five newly added executed data guards; no rerun inferred",
                        "code_sha256": code_sha, "full_xml_sha256": sha(full_path),
                        "extra_source_xml_sha256": sha(data_path)}.items():
        ET.SubElement(properties, "property", name=name, value=value)
    ET.ElementTree(suite).write(OUT / "verification_combined.xml", encoding="utf-8", xml_declaration=True)

    math_result = json.loads((OUT / "math_replay_result.json").read_text(encoding="utf-8"))
    assert math_result["status"] == "PASS" and math_result["code_sha256"]["final"] == code_sha
    final_network = OUT / "final_network"
    manifest = json.loads((final_network / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "PASS" and manifest["code_sha256"] == code_sha
    for name, recorded in manifest["files"].items():
        assert sha(final_network / name) == recorded, name
    previous_network = ROOT / "outputs/script_audit_20261007/current_network"
    old_raw = pd.read_csv(previous_network / "raw_prices_qfq.csv.gz", parse_dates=["date"])
    new_raw = pd.read_csv(final_network / "raw_prices_qfq.csv.gz", parse_dates=["date"])
    pd.testing.assert_frame_equal(new_raw, old_raw)
    old_daily = pd.read_csv(previous_network / "confirmed_daily.csv.gz", parse_dates=["date"])
    new_daily = pd.read_csv(final_network / "confirmed_daily.csv.gz", parse_dates=["date"])
    pd.testing.assert_frame_equal(new_daily, old_daily)
    old_metrics = pd.read_csv(previous_network / "window_metrics.csv")
    new_metrics = pd.read_csv(final_network / "window_metrics.csv")
    pd.testing.assert_frame_equal(new_metrics, old_metrics)
    docs = (ROOT / "docs/subd_six_etf_v1_3_script_doublecheck_20261007.md",
            ROOT / "docs/subd_six_etf_v1_3_script_audit_20261007.md")
    checked_links = 0
    for doc in docs:
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", doc.read_text(encoding="utf-8")):
            if re.match(r"^[a-z]+://", target):
                continue
            target = target.split("#", 1)[0]
            if target:
                linked_path = (doc.parent / target).resolve()
                # This report's own result is created after the other checks.
                assert linked_path.exists() or linked_path == (OUT / "delivery_verification.json").resolve(), (doc.name, target)
                checked_links += 1
    result = {"status": "PASS", "code_sha256": code_sha, "restore_point": str(before),
              "tests": summary, "full_run": {"passed": 685, "skipped": 1, "errors": 0, "failures": 0},
              "additional_tests_after_full_collection": len(extras),
              "additional_test_names": [case.get("name") for case in extras],
              "final_network": {"manifest_sha256": sha(final_network / "manifest.json"),
                                "rows": manifest["rows"], "end": manifest["end"],
                                "raw_prices_vs_first_audit": "all columns exact equal",
                                "daily_vs_first_audit": "all columns exact equal",
                                "window_metrics_vs_first_audit": "all columns exact equal"},
              "math_and_replay": "PASS", "checked_document_links": checked_links}
    (OUT / "delivery_verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
