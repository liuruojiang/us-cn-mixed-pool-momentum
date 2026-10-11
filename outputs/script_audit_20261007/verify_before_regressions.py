"""Replay the new counterexamples against the recoverable pre-edit source."""
from __future__ import annotations

import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEST = ROOT / "outputs/tmp/script_audit_20261007_before"
DEST.mkdir(parents=True, exist_ok=True)
copies = []
for name in ("math", "data", "execution_report"):
    original = ROOT / f"tests/test_v13_audit_{name}_20261007.py"
    source = original.read_text(encoding="utf-8")
    source = source.replace("ROOT = Path(__file__).resolve().parents[1]", f"ROOT = Path({str(ROOT)!r})")
    source = source.replace('"poe_subd_six_etf_v1_3_bot.py"',
                            '".codex_backups/20261007_163920/poe_subd_six_etf_v1_3_bot.py"')
    destination = DEST / original.name
    destination.write_text(source, encoding="utf-8")
    copies.append(str(destination))
environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
xml = HERE / "new_regressions_before.xml"
run = subprocess.run([sys.executable, "-X", "utf8", "-B", "-m", "pytest", *copies,
                      "-q", "-p", "no:cacheprovider", "--tb=line", f"--junitxml={xml}"],
                     cwd=ROOT, env=environment, capture_output=True, text=True, encoding="utf-8")
(HERE / "new_regressions_before.txt").write_text(run.stdout + run.stderr, encoding="utf-8")
suite = ET.parse(xml).getroot().find("testsuite")
assert suite is not None
assert suite.attrib["errors"] == "0", suite.attrib
assert run.returncode == 1 and suite.attrib["failures"] == "37", suite.attrib
print("Pre-edit counterexamples:", suite.attrib)
